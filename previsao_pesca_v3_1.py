#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVISÃO DE PESCA v3.1 — Snapshot Diário & SQLite ML-Ready
=============================================================
NOVIDADES v3.1 (esta revisão):

  [HIDRO]  Cascata hidrológica de 3 camadas portada do v2.10:
             1. PDF Semanal APA/SNIRH  (pdfplumber)
             2. VOST Portugal API      (espelho SNIRH, inativo mai-2026)
             3. Fallback Sazonal       (medianas SNIRH 2018-2024)
           — fonte registada em hidro['fonte'] e gravada no SQLite
           — parâmetros físicos reais de Castelo de Bode incluídos

  [LUNAR]  Precisão lunar via biblioteca `astral`:
             • moonrise / moonset calculados para lat/lon exatos
             • moon_illumination via astral.moon.phase (ciclo real)
             • 8 fases por posição relativa ao ciclo sinódico
             • fallback matemático automático se astral não disponível
             • ValueError tratado quando a Lua não nasce/põe no dia civil

  [DB]     Coluna 'fonte_hidro' e dados hidrológicos reais persistidos
           (anteriormente hardcoded como 115.0 m / 72% / "Sazonal_v3.1")

Dependências novas (opcionais com fallback):
  pip install astral pdfplumber
"""

import os
import sys
import re
import math
import logging
import sqlite3
import tempfile
import pathlib
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from config_loader import CONFIG, is_fishing_day

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(CONFIG["paths"]["log_file"], encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pesca_v3_1")

# ── Imports opcionais com detecção suave ──────────────────────────────────────
try:
    from astral import LocationInfo
    from astral.moon import moonrise as _astral_moonrise
    from astral.moon import moonset  as _astral_moonset
    from astral.moon import phase    as _astral_phase
    _HAS_ASTRAL = True
    logger.debug("astral disponível — precisão lunar ativada.")
except ImportError:
    _HAS_ASTRAL = False
    logger.warning("[LUNAR] astral não instalado — usando cálculo matemático de fallback. "
                   "Instale: pip install astral")

try:
    import pdfplumber as _pdfplumber
    _HAS_PDFPLUMBER = True
    logger.debug("pdfplumber disponível — cascata hidrológica PDF ativada.")
except ImportError:
    _HAS_PDFPLUMBER = False
    logger.warning("[HIDRO] pdfplumber não instalado — Camada 1 (PDF APA) desativada. "
                   "Instale: pip install pdfplumber")

# ==============================================================================
# CONSTANTES FÍSICAS — BARRAGEM DE CASTELO DE BODE
# (APA / barragens.pt — valores confirmados)
# ==============================================================================
CASTELO_BODE = {
    "nome":             "Castelo de Bode",
    "codigo_rede":      "16H/01A",
    "npa_m":            121.0,       # Nível Pleno de Armazenamento
    "nivel_min_m":      70.0,        # Mínimo técnico operacional
    "cota_coroamento":  124.3,       # Cota do coroamento da barragem
    "cap_total_hm3":    1095.0,      # Capacidade total até NPA
    "cap_activa_hm3":   900.5,       # Volume activo (NPA - volume morto)
}

# ==============================================================================
# LOCALIZAÇÃO — para astral
# ==============================================================================
_LOC_ASTRAL = (
    LocationInfo(
        "Castelo de Bode", "Portugal", "Europe/Lisbon",
        CONFIG["location"]["lat"], CONFIG["location"]["lon"],
    )
    if _HAS_ASTRAL else None
)

# ==============================================================================
# UTILITÁRIOS GERAIS
# ==============================================================================
def get_cardinal(deg) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int(round((float(deg) + 11.25) / 22.5)) % 16]


# ==============================================================================
# MÓDULO HIDROLÓGICO — CASCATA 3 CAMADAS  (portado de previsao_pesca_v2_10.py)
# ==============================================================================

def _nivel_para_pct(nivel_m: float) -> float:
    """Cota (m) → % armazenamento, com limites físicos reais."""
    npa = CASTELO_BODE["npa_m"]
    mn  = CASTELO_BODE["nivel_min_m"]
    return float(np.clip((nivel_m - mn) / (npa - mn) * 100.0, 0.0, 100.0))


def _validar_nivel(nivel: float) -> bool:
    """Aceita apenas cotas dentro do intervalo operacional real."""
    return CASTELO_BODE["nivel_min_m"] <= nivel <= CASTELO_BODE["cota_coroamento"]


def _dam3_to_hm3(s) -> "float | None":
    """
    Converte string dam³ (ex: '1 005 000') → hm³.
    1 dam³ = 1 000 m³ → 1 hm³ = 1 000 dam³
    """
    try:
        val = float(re.sub(r"\s+", "", str(s)).replace(",", ".").replace("%", ""))
        return round(val / 1000.0, 1) if val > 1000 else val
    except (ValueError, TypeError):
        return None


def _vol_hm3_para_cota(vol_hm3: float) -> float:
    """
    Volume (hm³) → cota (m) por interpolação linear.
    Âncoras: 0 hm³ = 70 m (mín), 1095 hm³ = 121 m (NPA).
    """
    cota = CASTELO_BODE["nivel_min_m"] + (
        vol_hm3 / CASTELO_BODE["cap_total_hm3"]
    ) * (CASTELO_BODE["npa_m"] - CASTELO_BODE["nivel_min_m"])
    return round(float(np.clip(cota,
                               CASTELO_BODE["nivel_min_m"],
                               CASTELO_BODE["cota_coroamento"])), 1)


# ── Camada 1: PDF Semanal APA / SNIRH ─────────────────────────────────────────
def _hidro_pdf_semanal() -> "dict | None":
    """
    Extrai dados de Castelo de Bode do Boletim Semanal de Albufeiras (PDF APA/SNIRH).
    Estrutura confirmada da tabela PDF (Pág. 7):
      Col: Nome | Uso | Cap(dam³) | Vol(dam³) | %NPA | Variação
    Tenta 2 URLs alternativas (APA oficial + SNIRH legado).
    Requer: pip install pdfplumber
    """
    if not _HAS_PDFPLUMBER:
        logger.warning("[PDF] pdfplumber não disponível — Camada 1 ignorada.")
        return None

    urls_pdf = [
        "https://apambiente.pt/sites/default/files/_SNIAMB_Agua/DRH/"
        "MonitorizacaoAvaliacao/BoletimAlbufeiras/Semanal.pdf",
        "https://snirh.apambiente.pt/snirh/download/Semanal.pdf",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
    }
    NOMES_CB = {"castelo de bode", "castelo do bode", "cast. de bode", "cast. do bode"}

    for url in urls_pdf:
        try:
            r = requests.get(url, headers=headers, timeout=25, stream=True)
            if r.status_code != 200 or r.content[:4] != b"%PDF":
                logger.warning(f"[PDF] {url} → HTTP {r.status_code} ou não é PDF")
                continue
            logger.info(f"[PDF] Descarregado: {len(r.content):,} bytes de {url}")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(r.content)
                tmp_path = tmp.name

            try:
                with _pdfplumber.open(tmp_path) as pdf:
                    for pnum, page in enumerate(pdf.pages):

                        # --- Via tabela estruturada (preferencial) ---
                        for tabela in (page.extract_tables() or []):
                            for row in tabela:
                                if not row:
                                    continue
                                nome_cell = " ".join(str(c or "") for c in row[:3]).lower()
                                if not any(n in nome_cell for n in NOMES_CB):
                                    continue
                                logger.info(f"[PDF tabela] Pág.{pnum+1} row={row}")
                                cells = [c for c in row if c is not None and str(c).strip()]
                                pct_vals = [
                                    float(re.sub(r"[^\d.]", "", c))
                                    for c in cells
                                    if re.match(r"^\s*\d+%?\s*$", str(c))
                                    and 0 < float(re.sub(r"[^\d.]", "", c)) <= 100
                                ]
                                vol_vals = [
                                    _dam3_to_hm3(c) for c in cells
                                    if re.match(r"^[\d\s]+$", re.sub(r",", "", str(c)))
                                    and _dam3_to_hm3(c) and _dam3_to_hm3(c) > 100
                                ]
                                if pct_vals:
                                    pct = pct_vals[0]
                                    vol_atual = (vol_vals[1] if len(vol_vals) >= 2
                                                 else (vol_vals[0] if vol_vals else None))
                                    nivel = (_vol_hm3_para_cota(vol_atual) if vol_atual
                                             else _vol_hm3_para_cota(
                                                 pct / 100 * CASTELO_BODE["cap_total_hm3"]))
                                    logger.info(
                                        f"[PDF OK] Pág.{pnum+1}: "
                                        f"Vol={vol_atual} hm³  Pct={pct}%  Cota={nivel} m")
                                    return {
                                        "nivel": nivel, "pct": round(pct, 1),
                                        "vol_hm3": vol_atual,
                                        "fonte": "PDF Semanal APA",
                                    }

                        # --- Fallback: texto posicional ---
                        texto = page.extract_text() or ""
                        for variante in ["Castelo de Bode", "Castelo do Bode"]:
                            if variante.lower() not in texto.lower():
                                continue
                            idx = texto.lower().find(variante.lower())
                            viz = texto[max(0, idx - 20): idx + 250]
                            pct_m = re.search(r"\b(\d{1,3})%", viz)
                            vols_raw = re.findall(
                                r"\b(\d{1,2}\s\d{3}\s\d{3}|\d{6,7})\b", viz)
                            vol_atual = None
                            if len(vols_raw) >= 2:
                                vol_atual = _dam3_to_hm3(vols_raw[1].replace(" ", ""))
                            if pct_m:
                                pct = float(pct_m.group(1))
                                nivel = (_vol_hm3_para_cota(vol_atual) if vol_atual
                                         else _vol_hm3_para_cota(
                                             pct / 100 * CASTELO_BODE["cap_total_hm3"]))
                                logger.info(
                                    f"[PDF texto OK] Pág.{pnum+1}: Pct={pct}%  Cota={nivel} m")
                                return {
                                    "nivel": nivel, "pct": round(pct, 1),
                                    "vol_hm3": vol_atual,
                                    "fonte": "PDF Semanal APA",
                                }
            finally:
                pathlib.Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"[PDF] {url} falhou: {type(e).__name__}: {e}")

    logger.warning("[PDF] Não foi possível extrair dados do boletim semanal.")
    return None


# ── Camada 2: VOST Portugal (espelho SNIRH) ───────────────────────────────────
def _hidro_vost() -> "dict | None":
    """
    API VOST Portugal — espelha dados SNIRH higienizados.
    Estado: timeout em mai-2026. Mantida para reativação automática.
    """
    endpoints = [
        "https://api.vost.pt/v1/albufeiras/castelo_bode",
        "https://api.vost.pt/v1/rios/albufeiras/castelo_bode",
    ]
    for url in endpoints:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=6,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            if not isinstance(data, dict):
                continue
            nivel = data.get("cota_m") or data.get("nivel") or data.get("cota")
            pct   = data.get("percentagem") or data.get("armazenamento_pct")
            if nivel and _validar_nivel(float(nivel)):
                nivel = float(nivel)
                pct   = float(pct) if pct else _nivel_para_pct(nivel)
                logger.info(f"[VOST] Cota={nivel} m  {pct:.1f}%")
                return {
                    "nivel": round(nivel, 2),
                    "pct":   round(float(np.clip(pct, 0.0, 100.0)), 1),
                    "fonte": "VOST/Rios (Espelho)",
                }
        except Exception as e:
            logger.warning(f"[VOST] {url}: {e}")
    return None


# ── Camada 3: Fallback sazonal calibrado ──────────────────────────────────────
def _hidro_fallback_sazonal() -> dict:
    """
    Medianas históricas mensais calibradas com dados SNIRH 2018-2024.
    Usada apenas quando todas as fontes online falham.
    """
    mes = datetime.now().month
    tabela = {
        1:  (118.5, 86.0),  2: (119.2, 90.0),  3: (119.8, 93.0),
        4:  (119.0, 89.0),  5: (117.5, 81.0),  6: (115.2, 73.0),
        7:  (112.0, 62.0),  8: (109.2, 53.0),  9: (107.8, 49.0),
        10: (110.0, 57.0), 11: (114.3, 70.0), 12: (117.2, 80.0),
    }
    nivel_f, pct_f = tabela.get(mes, (115.0, 72.0))
    logger.info(f"[Fallback Sazonal] Cota={nivel_f} m  {pct_f}%  (mês={mes})")
    return {"nivel": nivel_f, "pct": pct_f, "fonte": "Historico Sazonal (Estimado)"}


# ── Orquestrador da cascata ────────────────────────────────────────────────────
def get_hidrologia_real() -> dict:
    """
    Cascata 3 camadas para dados hidrológicos de Castelo de Bode:
      1. PDF Semanal APA/SNIRH  — fonte confirmada operacional
      2. VOST Portugal API       — inativo mai-2026, mantida para reativação
      3. Fallback Sazonal        — sempre disponível, valores estimados
    hidro['fonte'] regista qual camada foi usada.
    """
    logger.info("=== Hidrologia: cascata 3 camadas ===")

    r = _hidro_pdf_semanal()
    if r:
        logger.info(f"Hidrologia OK via Camada 1 (PDF): {r['nivel']} m  {r['pct']}%")
        return r

    logger.info("Camada 1 falhou → Camada 2 (VOST)")
    r = _hidro_vost()
    if r:
        logger.info(f"Hidrologia OK via Camada 2 (VOST): {r['nivel']} m  {r['pct']}%")
        return r

    logger.info("Camada 2 falhou → Camada 3 (Fallback Sazonal)")
    return _hidro_fallback_sazonal()


# ==============================================================================
# MÓDULO LUNAR — astral (preciso) com fallback matemático
# ==============================================================================
_CICLO_SINODICO = 29.53058867  # dias
_FASES_8 = [
    "Nova", "Crescente I", "Q. Crescente", "Crescente Fim",
    "Cheia", "Minguante I", "Q. Minguante", "Minguante Fim",
]


def _moonrise_set_str(d: "date") -> "tuple[str, str]":
    """
    Devolve (moonrise_HH:MM, moonset_HH:MM) para a data dada.
    Usa astral se disponível; caso contrário devolve 'N/A'.
    ValueError tratado: quando a Lua não nasce/põe no dia civil.
    """
    if not (_HAS_ASTRAL and _LOC_ASTRAL):
        return "N/A", "N/A"

    def _safe(fn, obs, dt, tz):
        try:
            t = fn(obs, dt, tzinfo=tz)
            return t.strftime("%H:%M") if t else "N/A"
        except Exception:
            return "N/A"

    mr = _safe(_astral_moonrise, _LOC_ASTRAL.observer, d, _LOC_ASTRAL.timezone)
    ms = _safe(_astral_moonset,  _LOC_ASTRAL.observer, d, _LOC_ASTRAL.timezone)
    return mr, ms


def calc_lunar(date_str: str) -> dict:
    """
    Calcula dados lunares completos para uma data (YYYY-MM-DD).

    Com astral:
      • phase()      → dias no ciclo sinódico (0–29.53), base astronómica real
      • moonrise/moonset → horários exactos para lat/lon de Castelo de Bode
      • illumination  → cos(fase) — consistente com phase()

    Sem astral (fallback matemático):
      • Referência: Lua Nova de 16-mai-2026 17:00 UTC (confirmada)
      • moonrise/moonset → 'N/A'
    """
    from datetime import date as _date

    d = _date.fromisoformat(date_str)

    # ── Fase e iluminação ──
    if _HAS_ASTRAL:
        ph_days = _astral_phase(d)                          # dias desde última LN
        pos     = ph_days / _CICLO_SINODICO                 # 0.0 – 1.0
    else:
        # Fallback: referência fixa calibrada
        dt_utc = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
        ref    = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
        ph_days = (dt_utc - ref).total_seconds() / 86400.0 % _CICLO_SINODICO
        pos     = ph_days / _CICLO_SINODICO

    illumination = round((1 - math.cos(pos * 2 * math.pi)) / 2 * 100, 1)
    fase_idx     = min(int(pos * 8), 7)
    fase         = _FASES_8[fase_idx]

    dist_nova  = round(min(ph_days, _CICLO_SINODICO - ph_days), 2)
    dist_cheia = round(min(abs(ph_days - _CICLO_SINODICO / 2),
                           _CICLO_SINODICO - abs(ph_days - _CICLO_SINODICO / 2)), 2)

    # ── Moonrise / Moonset ──
    moonrise_str, moonset_str = _moonrise_set_str(d)

    logger.debug(
        f"[LUNAR] {date_str}: fase={fase}  illum={illumination}%  "
        f"dist_nova={dist_nova}d  rise={moonrise_str}  set={moonset_str}"
    )

    return {
        "fase_lua":             fase,
        "dias_desde_lua_nova":  dist_nova,
        "dias_desde_lua_cheia": dist_cheia,
        "moon_illumination":    illumination,
        "moonrise":             moonrise_str,
        "moonset":              moonset_str,
    }


# ==============================================================================
# MÓDULO METEOROLÓGICO
# ==============================================================================
def fetch_meteo_archive(date_str: str) -> "tuple[pd.Series, dict]":
    """
    Puxa dados horários do Open-Meteo Archive para a data indicada.
    Devolve (última hora do dia, dados diários de sol).
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":   CONFIG["location"]["lat"],
        "longitude":  CONFIG["location"]["lon"],
        "start_date": date_str,
        "end_date":   date_str,
        "hourly": [
            "temperature_2m", "relative_humidity_2m", "precipitation",
            "cloudcover", "wind_speed_10m", "wind_direction_10m", "surface_pressure",
        ],
        "daily":    ["sunrise", "sunset"],
        "timezone": CONFIG["location"]["timezone"],
    }
    r = requests.get(url, params=params, timeout=CONFIG["api"]["timeout_s"])
    r.raise_for_status()
    d = r.json()
    df_h = pd.DataFrame(d["hourly"])
    return df_h.iloc[-1], d["daily"]


# ==============================================================================
# BASE DE DADOS SQLite
# ==============================================================================
def init_db():
    logger.info("🗄️ Inicializando/Verificando base de dados SQLite v3.1...")
    conn = sqlite3.connect(CONFIG["paths"]["db_sqlite"])
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meteo (
            datetime    TEXT PRIMARY KEY,
            temp_ar     REAL, temp_agua   REAL,
            vento_kmh   REAL, vento_dir   TEXT,
            pressao     REAL, humidade    REAL,
            chuva_1h    REAL, chuva_24h   REAL, chuva_72h REAL,
            nuvens      REAL, mes         TEXT,
            estacao     TEXT, hora        REAL,
            dia_semana  TEXT, amanhecer   TEXT, anoitecer TEXT
        );
        CREATE TABLE IF NOT EXISTS hidro (
            datetime        TEXT PRIMARY KEY,
            nivel_barragem  REAL, delta_24h    REAL, delta_72h   REAL,
            percentagem     REAL, caudal       REAL, fonte_hidro TEXT
        );
        CREATE TABLE IF NOT EXISTS lunar (
            datetime              TEXT PRIMARY KEY,
            fase_lua              TEXT,
            dias_desde_lua_nova   REAL,
            dias_desde_lua_cheia  REAL,
            moon_illumination     REAL,
            moonrise              TEXT,
            moonset               TEXT
        );
        CREATE TABLE IF NOT EXISTS capturas (
            datetime      TEXT PRIMARY KEY,
            especie       TEXT,  quantidade  INTEGER,
            peso_total    REAL,  horas_pesca REAL,
            local         TEXT,  sucesso_score REAL
        );
    """)
    conn.commit()
    conn.close()


# ==============================================================================
# SNAPSHOT DIÁRIO
# ==============================================================================
_ESTACAO_MAP = {
    1: "Inverno",  2: "Inverno",  3: "Primavera",
    4: "Primavera",5: "Primavera",6: "Verão",
    7: "Verão",    8: "Verão",    9: "Outono",
    10: "Outono",  11: "Outono",  12: "Inverno",
}


def gerar_snapshot_diario():
    hoje = datetime.now().date()
    modo = "Pesca Ativa" if is_fishing_day(hoje) else "Monitorização"
    logger.info(f"📸 Gerando snapshot para {hoje} | Modo: {modo}")

    ds     = hoje.strftime("%Y-%m-%d")
    dt_str = f"{ds} 20:00"

    conn = sqlite3.connect(CONFIG["paths"]["db_sqlite"])
    c    = conn.cursor()

    # Verificar duplicado
    if c.execute("SELECT 1 FROM meteo WHERE datetime LIKE ?", (f"{ds}%",)).fetchone():
        logger.info(f"⏭️  {ds} já registado.")
        conn.close()
        return

    try:
        # ── Meteorologia ──────────────────────────────────────────────────────
        row_h, sun = fetch_meteo_archive(ds)
        ta = round(float(row_h["temperature_2m"]), 1)
        tw = round(
            CONFIG["water_temp_model"]["tw_slope"] * ta
            + CONFIG["water_temp_model"]["tw_intercept"],
            1,
        )
        mes = hoje.month

        c.execute(
            """INSERT INTO meteo (
                datetime, temp_ar, temp_agua, vento_kmh, vento_dir,
                pressao, humidade, chuva_1h, chuva_24h, chuva_72h,
                nuvens, mes, estacao, hora, dia_semana, amanhecer, anoitecer
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                dt_str, ta, tw,
                float(row_h["wind_speed_10m"]),
                get_cardinal(row_h["wind_direction_10m"]),
                float(row_h["surface_pressure"]),
                float(row_h["relative_humidity_2m"]),
                float(row_h["precipitation"]),          # chuva_1h
                float(row_h["precipitation"]),          # chuva_24h (proxy)
                float(row_h["precipitation"]) * 3,      # chuva_72h (proxy)
                float(row_h["cloudcover"]),
                str(mes),
                _ESTACAO_MAP[mes],
                20.0,
                hoje.strftime("%A"),
                sun["sunrise"][0].split("T")[1],
                sun["sunset"][0].split("T")[1],
            ),
        )

        # ── Hidrologia — cascata 3 camadas ───────────────────────────────────
        hidro = get_hidrologia_real()

        # delta_24h: diferença face ao dia anterior (se disponível no DB)
        prev_ds  = (hoje - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_row = c.execute(
            "SELECT nivel_barragem FROM hidro WHERE datetime LIKE ?",
            (f"{prev_ds}%",),
        ).fetchone()
        delta_24h = (round(hidro["nivel"] - prev_row[0], 2)
                     if prev_row and prev_row[0] else 0.0)

        c.execute(
            """INSERT INTO hidro (
                datetime, nivel_barragem, delta_24h, delta_72h,
                percentagem, caudal, fonte_hidro
            ) VALUES (?,?,?,?,?,?,?)""",
            (
                dt_str,
                hidro["nivel"],
                delta_24h,
                0.0,                          # delta_72h: calculado em batch futuro
                hidro["pct"],
                None,                         # caudal: sem fonte disponível
                hidro["fonte"],
            ),
        )

        # ── Lunar — astral preciso ────────────────────────────────────────────
        lunar = calc_lunar(ds)

        c.execute(
            """INSERT INTO lunar (
                datetime, fase_lua, dias_desde_lua_nova,
                dias_desde_lua_cheia, moon_illumination, moonrise, moonset
            ) VALUES (?,?,?,?,?,?,?)""",
            (
                dt_str,
                lunar["fase_lua"],
                lunar["dias_desde_lua_nova"],
                lunar["dias_desde_lua_cheia"],
                lunar["moon_illumination"],
                lunar["moonrise"],
                lunar["moonset"],
            ),
        )

        conn.commit()
        logger.info(
            f"✅ Snapshot v3.1 inserido: "
            f"Ta={ta}°C  Tw={tw}°C  "
            f"Hidro={hidro['nivel']}m/{hidro['pct']}% [{hidro['fonte']}]  "
            f"Lua={lunar['fase_lua']} {lunar['moon_illumination']}%  "
            f"Rise={lunar['moonrise']}  Set={lunar['moonset']}"
        )

    except Exception as e:
        logger.error(f"❌ Falha no snapshot: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    init_db()
    gerar_snapshot_diario()

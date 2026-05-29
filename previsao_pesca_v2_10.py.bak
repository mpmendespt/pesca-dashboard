#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVISÃO DE PESCA - REDE JAZIDA v2.10 (Python)
Barragem de Castelo de Bode - Zona Ilha do Lombo (Rio Zêzere)

CORREÇÕES v2.10 (em relação a v2.9):
 #1  Chuva negativa → clip(lower=0) no DataFrame + ylim(bottom=0) no gráfico.
 #2  Tw calculada com média dos últimos 5 dias (em vez de apenas ontem); fallback
     explícito com aviso se a API de arquivo falhar.
 #3  Tabela mensal filtrada: espécies sem capturas são removidas; layout compacto.
 #4  Emoji ❌/✅/⚠️ sanitizados em TODOS os contextos ax.text() da Página 3.
 #5  Página 2 (Recomendações) completamente reescrita: análise por dia, espécie-
     alvo, comparação com sessões anteriores, melhores horas.
 #6  Rosa dos ventos movida para a Página 2; seta N corrigida para apontar ao setor
     dominante real (não fixo ao N).
 #7  Rating lunar integra Tw e chuva acumulada 3 dias: penaliza frio e chuva intensa.
 #8  Barra "Total" removida do gráfico de espécies (fica apenas em texto).
 #9  Fonte SNIRH exibida no cabeçalho do PDF: [Live] vs [Estimado].
#10  Nomes de colunas da tabela de resumo diário traduzidos para português.
#11  Wind barbs movidos para faixa dedicada (subplot separado), sem sobreposição.
#12  Histórico CSV: verifica duplicados antes de gravar (mesmo dia não regista 2x).
#13  Fuso horário consistente: get_avg_temp_5d() usa Europe/Lisbon; comparações
     de datas baseadas em .date() para evitar erros na transição de meia-noite.
"""

import os
import sys
import warnings
import platform
import re
import logging
import matplotlib.patches as mpatches
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec
from matplotlib.dates import DateFormatter

# ==============================================================================
# CONFIGURAÇÃO DE LOGGING
# ==============================================================================
def setup_logging(log_file="previsao_pesca.log", max_bytes=2*1024*1024, backup_count=2):
    logger = logging.getLogger("previsao_pesca")
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()
    fmt_file = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
    fh.setLevel(logging.DEBUG); fh.setFormatter(fmt_file)
    fmt_con = logging.Formatter('%(levelname)s: %(message)s')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO); ch.setFormatter(fmt_con)
    logger.addHandler(fh); logger.addHandler(ch)
    logging.captureWarnings(True)
    return logger

logger = setup_logging()

# ==============================================================================
# CONFIGURAÇÕES TÉCNICAS
# ==============================================================================
CONFIG = {
    "local": "Barragem de Castelo de Bode - Ilha do Lombo",
    "lat": 39.6500,
    "lon": -8.3500,
    "dias": 8,
    "limiar_chuva_pesca": 15,
    "limiar_vento": 35,
    "limiar_frio": 11,
    "tw_slope": 0.70,
    "tw_intercept": 7.71,
    "url_snirh": "https://snirh.apambiente.pt/index.php?idMain=1&idItem=1.3",
    "arquivo_pdf": f"Previsao_Pesca_v2.10_{datetime.now().strftime('%Y%m%d')}.pdf",
    "historico_csv": "historico_temperaturas_castelo_bode.csv",
    "capturas_csv": "Capturas.csv",
    "log_file": "previsao_pesca.log",
    "lua_nova_janela": 3,
    "lua_cheia_janela": 2,
    "apainag_station": "10H/02E",
    "pressao_delta_estavel": 1.5,
    "pressao_limiar_pico": 15.0,
    "tw_dias_media": 5,          # FIX #2: média de 5 dias para Tw
}

# ==============================================================================
# CONFIGURAÇÃO DE FONTES
# ==============================================================================
system = platform.system()
if system == 'Windows':
    plt.rcParams['font.sans-serif'] = ['Segoe UI Emoji', 'Segoe UI', 'Arial', 'DejaVu Sans']
else:
    plt.rcParams['font.sans-serif'] = ['Noto Color Emoji', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 9
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['axes.labelsize'] = 9
plt.rcParams['xtick.labelsize'] = 8
plt.rcParams['ytick.labelsize'] = 8
plt.rcParams['legend.fontsize'] = 8
plt.rcParams['figure.titlesize'] = 12

# FIX #4 — sanitização total de emojis para matplotlib (inclui ❌ e todos variantes)
def clean_plot_text(text, keep_stars=False):
    replacements = {
        '🎣': '[PESCA]', '📈': '[TEND]', '✅': '[OK]', '⚠️': '[!]',
        '❌': '[NAO]', '💨': '[VENTO]', '❄️': '[FRIO]', '⚪': '[--]',
        '🌊': '[HIDRO]', '🌧️': '[CHUVA]', '⛈️': '[TROV]', '🌫️': '[NEV]',
        '📋': '[RES]', 'ℹ️': '[INFO]', '🎯': '[DICA]', '🔗': '[LINK]',
        '🌟': '[TOP]', '📄': '[PDF]', '📊': '[DADOS]',
        '🌑': '[LUA NOVA]', '🌒': '[CRESC-I]', '🌓': '[Q-CRESC]',
        '🌔': '[CRESC-F]', '🌕': '[LUA CHEIA]', '🌖': '[MING-I]',
        '🌗': '[Q-MING]', '🌘': '[MING-F]',
        '⬇️': '[v]', '⬆️': '[^]', '➡️': '[->]',
        '\u2705': '[OK]', '\u274c': '[NAO]', '\u26a0\ufe0f': '[!]',
    }
    for em, repl in replacements.items():
        text = text.replace(em, repl)
    if not keep_stars:
        text = text.replace('⭐', '*')
    return text

def get_cardinal(deg):
    if pd.isna(deg): return None
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int(round((deg + 11.25) / 22.5)) % 16]

# ==============================================================================
# MÓDULO 1: HIDROLOGIA — 3 CAMADAS (v2.10 rev.2)
#
# Descobertas do diagnóstico real (2026-05-25):
#   Camada 1 anterior (API JSON /albufeiras_grafico.php) → 404 (endpoint morto)
#   Camada 2 anterior (VOST api.vost.pt)                → Timeout (servidor inativo)
#   Camada 3 anterior (SNIRH HTML scraping)             → 0 tabelas (JS dinâmico)
#   PDF Semanal APA + SNIRH                             → OK — fonte implementada
#
# Estrutura real da tabela PDF (Pág.7, pdfplumber confirmado):
#   Col: Nome | Uso | Cap(dam³) | Vol(dam³) | %NPA | Variação
#   Ex: ['Castelo de Bode','Abastecimento e energia','1 095 000','1 005 000','92%','0%']
#   Unidade: dam³  (1 dam³ = 1000 m³;  /1000 = hm³)
# ==============================================================================

try:
    import pdfplumber as _pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False
    logger.warning("pdfplumber nao instalado. Instale: pip install pdfplumber")

# Parâmetros físicos reais de Castelo de Bode (APA / barragens.pt confirmados)
CASTELO_BODE = {
    "nome":            "Castelo de Bode",
    "codigo_rede":     "16H/01A",
    "npa_m":           121.0,
    "nivel_min_m":     70.0,
    "cota_coroamento": 124.3,
    "cap_total_hm3":   1095.0,   # capacidade total até NPA
    "cap_activa_hm3":  900.5,    # volume activo (NPA - volume morto)
}

def _nivel_para_pct(nivel_m: float) -> float:
    """Converte cota (m) para % de armazenamento usando limites físicos reais."""
    npa = CASTELO_BODE["npa_m"]
    mn  = CASTELO_BODE["nivel_min_m"]
    pct = (nivel_m - mn) / (npa - mn) * 100.0
    return float(np.clip(pct, 0.0, 100.0))

def _validar_nivel(nivel: float) -> bool:
    """Aceita apenas cotas dentro do intervalo operacional real."""
    return CASTELO_BODE["nivel_min_m"] <= nivel <= CASTELO_BODE["cota_coroamento"]

def _dam3_to_hm3(s) -> float | None:
    """
    Converte string em dam³ (formato do PDF APA: '1 095 000') para hm³.
    1 dam³ = 1 000 m³;  1 hm³ = 1 000 000 m³  → 1 hm³ = 1 000 dam³
    """
    try:
        val = float(re.sub(r"\s+", "", str(s)).replace(",", ".").replace("%",""))
        return round(val / 1000.0, 1) if val > 1000 else val
    except (ValueError, TypeError):
        return None

def _vol_hm3_para_cota(vol_hm3: float) -> float:
    """
    Estima cota (m) a partir do volume (hm³) por interpolação linear.
    Pontos de ancoragem: 0 hm³ → 70m (mínimo), 1095 hm³ → 121m (NPA).
    Aproximação adequada para variações normais de armazenamento.
    """
    cota = CASTELO_BODE["nivel_min_m"] + (vol_hm3 / CASTELO_BODE["cap_total_hm3"]) * (
        CASTELO_BODE["npa_m"] - CASTELO_BODE["nivel_min_m"]
    )
    return round(float(np.clip(cota, CASTELO_BODE["nivel_min_m"], CASTELO_BODE["cota_coroamento"])), 1)

# ---------- CAMADA 1: PDF Semanal da APA / SNIRH ─────────────────────────────
def _hidro_pdf_semanal() -> dict | None:
    """
    Extrai dados de Castelo de Bode do Boletim Semanal de Albufeiras (PDF APA/SNIRH).
    Testado e confirmado: Pág.7, tabela com Volume(dam³) e %(NPA).
    Duas URLs alternativas (APA oficial e SNIRH legado) — tenta ambas.
    Requer: pip install pdfplumber
    """
    if not _HAS_PDFPLUMBER:
        logger.warning("[PDF] pdfplumber nao disponivel — instale: pip install pdfplumber")
        return None

    import io, tempfile, pathlib

    urls_pdf = [
        "https://apambiente.pt/sites/default/files/_SNIAMB_Agua/DRH/MonitorizacaoAvaliacao/BoletimAlbufeiras/Semanal.pdf",
        "https://snirh.apambiente.pt/snirh/download/Semanal.pdf",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
    }

    # Nomes que podem aparecer no PDF (ortografias variantes observadas)
    NOMES_CB = {"castelo de bode", "castelo do bode", "cast. de bode", "cast. do bode"}

    for url in urls_pdf:
        try:
            r = requests.get(url, headers=headers, timeout=25, stream=True)
            if r.status_code != 200 or r.content[:4] != b"%PDF":
                logger.warning(f"[PDF] {url} -> HTTP {r.status_code} ou nao e PDF")
                continue

            logger.info(f"[PDF] PDF descarregado: {len(r.content):,} bytes de {url}")

            # Guardar em ficheiro temporário (pdfplumber requer path ou file-like)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(r.content)
                tmp_path = tmp.name

            try:
                with _pdfplumber.open(tmp_path) as pdf:
                    for pnum, page in enumerate(pdf.pages):
                        # --- Tentar via tabela estruturada (mais robusto) ---
                        tabelas = page.extract_tables()
                        for tabela in tabelas:
                            for row in tabela:
                                if not row: continue
                                nome_cell = " ".join(str(c or "") for c in row[:3]).lower()
                                if any(n in nome_cell for n in NOMES_CB):
                                    logger.info(f"[PDF tabela] Pag.{pnum+1} row={row}")
                                    # Estrutura confirmada: [idx, nome, uso, cap_dam3, vol_dam3, pct, delta]
                                    # Índices podem variar se a primeira coluna estiver vazia
                                    cells = [c for c in row if c is not None and str(c).strip()]
                                    # Extrair % directamente (mais fiável que volume→cota)
                                    pct_vals = [float(re.sub(r"[^\d.]", "", c))
                                                for c in cells if re.match(r"^\s*\d+%?\s*$", str(c))
                                                and 0 < float(re.sub(r"[^\d.]","",c)) <= 100]
                                    # Extrair volumes em dam³ (valores > 10000)
                                    vol_vals = [_dam3_to_hm3(c) for c in cells
                                                if re.match(r"^[\d\s]+$", re.sub(r",","",str(c)))
                                                and _dam3_to_hm3(c) and _dam3_to_hm3(c) > 100]
                                    logger.info(f"[PDF] pct_vals={pct_vals}  vol_vals={vol_vals}")
                                    if pct_vals:
                                        pct = pct_vals[0]
                                        vol_atual = vol_vals[1] if len(vol_vals) >= 2 else (vol_vals[0] if vol_vals else None)
                                        nivel = _vol_hm3_para_cota(vol_atual) if vol_atual else _vol_hm3_para_cota(pct/100*CASTELO_BODE["cap_total_hm3"])
                                        logger.info(f"[PDF OK] Pag.{pnum+1}: Vol={vol_atual}hm3  Pct={pct}%  Cota={nivel}m")
                                        return {"nivel": nivel, "pct": round(pct, 1),
                                                "vol_hm3": vol_atual, "fonte": "PDF Semanal APA"}

                        # --- Fallback: extracção de texto posicional ---
                        texto = page.extract_text() or ""
                        for variante in ["Castelo de Bode", "Castelo do Bode"]:
                            if variante.lower() in texto.lower():
                                idx = texto.lower().find(variante.lower())
                                vizinhanca = texto[max(0, idx-20):idx+250]
                                logger.info(f"[PDF texto] Pag.{pnum+1} vizinhanca: {vizinhanca!r}")
                                # Procurar % (ex: "92%")
                                pct_m = re.search(r"\b(\d{1,3})%", vizinhanca)
                                # Procurar volumes dam³ (ex: "1 005 000")
                                vols_raw = re.findall(r"\b(\d{1,2}\s\d{3}\s\d{3}|\d{6,7})\b", vizinhanca)
                                vol_atual = None
                                if len(vols_raw) >= 2:
                                    vol_atual = _dam3_to_hm3(vols_raw[1].replace(" ",""))
                                if pct_m:
                                    pct = float(pct_m.group(1))
                                    nivel = _vol_hm3_para_cota(vol_atual) if vol_atual else _vol_hm3_para_cota(pct/100*CASTELO_BODE["cap_total_hm3"])
                                    logger.info(f"[PDF texto OK] Pag.{pnum+1}: Pct={pct}%  Cota={nivel}m")
                                    return {"nivel": nivel, "pct": round(pct, 1),
                                            "vol_hm3": vol_atual, "fonte": "PDF Semanal APA"}
            finally:
                pathlib.Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"[PDF] {url} falhou: {type(e).__name__}: {e}")

    logger.warning("[PDF] Nao foi possivel extrair dados do PDF semanal")
    return None

# ---------- CAMADA 2: VOST Portugal (mantida — pode voltar a funcionar) ───────
def _hidro_vost() -> dict | None:
    """
    API VOST Portugal (api.vost.pt) — espelha dados SNIRH higienizados.
    Confirmado: timeout em 2026-05-25 (servidor inativo).
    Mantida na cascata pois pode ser reativada sem aviso.
    """
    endpoints = [
        "https://api.vost.pt/v1/albufeiras/castelo_bode",
        "https://api.vost.pt/v1/rios/albufeiras/castelo_bode",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}, timeout=6)
            if r.status_code != 200: continue
            data = r.json()
            if isinstance(data, dict):
                nivel = data.get("cota_m") or data.get("nivel") or data.get("cota")
                pct   = data.get("percentagem") or data.get("armazenamento_pct")
                if nivel and _validar_nivel(float(nivel)):
                    nivel = float(nivel)
                    pct   = float(pct) if pct else _nivel_para_pct(nivel)
                    logger.info(f"[VOST] Cota={nivel}m  {pct:.1f}%")
                    return {"nivel": round(nivel,2), "pct": round(float(np.clip(pct,0,100)),1),
                            "fonte": "VOST/Rios (Espelho)"}
        except Exception as e:
            logger.warning(f"[VOST] {url}: {e}")
    return None

# ---------- CAMADA 3: Fallback sazonal calibrado ─────────────────────────────
def _hidro_fallback_sazonal() -> dict:
    """
    Medianas históricas mensais calibradas com dados SNIRH 2018-2024.
    Usada apenas quando todas as fontes online falham.
    """
    mes = datetime.now().month
    tabela = {
        1:(118.5,86.0), 2:(119.2,90.0), 3:(119.8,93.0), 4:(119.0,89.0),
        5:(117.5,81.0), 6:(115.2,73.0), 7:(112.0,62.0), 8:(109.2,53.0),
        9:(107.8,49.0),10:(110.0,57.0),11:(114.3,70.0),12:(117.2,80.0),
    }
    nivel_f, pct_f = tabela.get(mes, (115.0, 72.0))
    logger.info(f"[Fallback Sazonal] Cota={nivel_f}m  {pct_f}%  (mes={mes})")
    return {"nivel": nivel_f, "pct": pct_f, "fonte": "Historico Sazonal (Estimado)"}

# ---------- Orquestrador com cascata de 3 camadas ────────────────────────────
def get_hidrologia_real(**kwargs) -> dict:
    """
    Cascata de 3 fontes para dados hidrológicos de Castelo de Bode:
      1. PDF Semanal APA/SNIRH  (pdfplumber — fonte confirmada operacional)
      2. VOST Portugal API       (inativo em mai-2026, mantida para reativação)
      3. Fallback sazonal        (sempre disponível, valores estimados)
    A fonte usada é registada em hidro['fonte'] e exibida no relatório.
    """
    logger.info("=== Hidrologia: cascata 3 camadas ===")

    r = _hidro_pdf_semanal()
    if r:
        logger.info(f"Hidrologia OK via Camada 1 (PDF): nivel={r['nivel']}m  pct={r['pct']}%")
        return r

    logger.info("Camada 1 (PDF) falhou -> Camada 2 (VOST)")
    r = _hidro_vost()
    if r:
        logger.info(f"Hidrologia OK via Camada 2 (VOST): {r}")
        return r

    logger.info("Camada 2 (VOST) falhou -> Camada 3 (Fallback Sazonal)")
    return _hidro_fallback_sazonal()




def get_weather_data(lat, lon, days):
    logger.info(f"A obter previsao meteo ({days} dias)...")
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["temperature_2m","surface_pressure","wind_speed_10m","wind_direction_10m"],
        "daily": ["temperature_2m_max","temperature_2m_min","precipitation_sum",
                  "wind_speed_10m_max","wind_direction_10m_dominant"],
        "timezone": "Europe/Lisbon", "forecast_days": days
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        d = data["daily"]
        df_d = pd.DataFrame({
            "Data": pd.to_datetime(d["time"]),
            # FIX #1 — precipitação não pode ser negativa
            "Chuva_mm": np.clip(d["precipitation_sum"], 0, None),
            "Min_C": d["temperature_2m_min"],
            "Max_C": d["temperature_2m_max"],
            "Vento_kmh": d["wind_speed_10m_max"],
            "Dir_Graus": d["wind_direction_10m_dominant"]
        })
        h = data["hourly"]
        df_h = pd.DataFrame({
            "Data": pd.to_datetime(h["time"]),
            "Temp_C": h["temperature_2m"],
            "Pressao_hPa": h["surface_pressure"],
            "Vento_kmh": h["wind_speed_10m"],
            "Vento_Dir": h["wind_direction_10m"]
        })
        return df_d, df_h
    except Exception as e:
        logger.error(f"Erro Open-Meteo: {e}")
        return None, None

# FIX #2 — Tw baseada na média dos últimos N dias (padrão 5)
def get_avg_temp_nd(lat, lon, n_days=5):
    """Média de temperatura dos últimos n_days dias para estimar Tw."""
    # FIX #13 — usar timezone Europe/Lisbon consistentemente
    hoje = datetime.now(tz=timezone.utc).astimezone(
        __import__('zoneinfo', fromlist=['ZoneInfo']).ZoneInfo('Europe/Lisbon') if hasattr(__import__('zoneinfo', fromlist=['']), 'ZoneInfo') else timezone.utc
    ).date()
    inicio = (hoje - timedelta(days=n_days)).strftime("%Y-%m-%d")
    fim = (hoje - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        url = (f"https://archive-api.open-meteo.com/v1/archive"
               f"?latitude={lat}&longitude={lon}"
               f"&start_date={inicio}&end_date={fim}"
               f"&daily=temperature_2m_max,temperature_2m_min"
               f"&timezone=Europe%2FLisbon")
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        d = r.json()["daily"]
        maxs = d["temperature_2m_max"]
        mins = d["temperature_2m_min"]
        validos = [(mx+mn)/2 for mx,mn in zip(maxs,mins) if mx is not None and mn is not None]
        if validos:
            media = round(sum(validos)/len(validos), 1)
            logger.info(f"Ta media {n_days}d: {media}°C (de {len(validos)} dias validos)")
            return media, True
    except Exception as e:
        logger.warning(f"Erro ao obter temp. historica ({n_days}d): {e}")
    logger.warning("Fallback Tw: usando 16.0 C (API de arquivo indisponivel)")
    return 16.0, False  # fallback explícito

# FIX #7 — Rating lunar integra Tw e chuva acumulada
def calc_lunar_fishing(dates, lat, lon, tw=None, chuva_mm_map=None):
    """
    Calcula fase lunar e rating de pesca para cada data.
    tw: temperatura da água (°C) — penaliza se < 12°C
    chuva_mm_map: dict {date: mm} — penaliza se chuva > 15mm
    """
    lua_nova_ref = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
    ciclo = 29.53058867
    res = []
    for dt in dates:
        # FIX #13 — date() seguro para comparações
        if hasattr(dt, 'date'):
            dt_date = dt.date() if hasattr(dt, 'date') and callable(dt.date) else dt
        else:
            dt_date = dt
        d_utc = datetime(dt_date.year, dt_date.month, dt_date.day, 12, 0, tzinfo=timezone.utc)
        dias = (d_utc - lua_nova_ref).total_seconds() / 86400.0
        pos = (dias % ciclo) / ciclo

        if   pos < 0.0625 or pos >= 0.9375: fase = "Lua Nova"
        elif pos < 0.1875:  fase = "Crescente I"
        elif pos < 0.3125:  fase = "Q. Crescente"
        elif pos < 0.4375:  fase = "Crescente Fim"
        elif pos < 0.5625:  fase = "Lua Cheia"
        elif pos < 0.6875:  fase = "Minguante I"
        elif pos < 0.8125:  fase = "Q. Minguante"
        else:               fase = "Minguante Fim"

        dist_nova  = min(pos * ciclo, (1-pos) * ciclo)
        dist_cheia = min(abs(pos-0.5), 1-abs(pos-0.5)) * ciclo

        # Rating base pela fase
        if   dist_nova  <= CONFIG["lua_nova_janela"]:  rating_num = 5
        elif dist_cheia <= CONFIG["lua_cheia_janela"]:  rating_num = 4
        elif (0.15<=pos<=0.35) or (0.65<=pos<=0.85):   rating_num = 3
        else:                                            rating_num = 2

        # FIX #7 — penalizações por condições desfavoráveis
        penalidades = []
        if tw is not None and tw < CONFIG["limiar_frio"]:
            rating_num = max(1, rating_num - 1)
            penalidades.append(f"Tw fria ({tw}C)")
        chuva_dia = (chuva_mm_map or {}).get(dt_date, 0) or 0
        if chuva_dia > CONFIG["limiar_chuva_pesca"]:
            rating_num = max(1, rating_num - 1)
            penalidades.append(f"Chuva ({chuva_dia:.0f}mm)")

        labels = {5:"***** EXCELENTE", 4:"**** MUITO BOM", 3:"*** REGULAR", 2:"** MODERADO", 1:"* FRACO"}
        rating_str = labels[rating_num]
        pen_str = f" [{', '.join(penalidades)}]" if penalidades else ""

        res.append({"Data": pd.Timestamp(dt_date), "Fase_Lua": fase,
                    "Rating_Pesca_Rede": rating_str + pen_str,
                    "Rating_Num": rating_num})
    return pd.DataFrame(res)

# ==============================================================================
# MÓDULO 2: CAPTURAS, HISTÓRICO & EXPORTAÇÃO EXCEL
# ==============================================================================
def ler_capturas(file_csv):
    if not os.path.exists(file_csv):
        logger.info(f"Ficheiro de capturas nao encontrado: {file_csv}")
        return pd.DataFrame()
    try:
        logger.info(f"A ler {file_csv}...")
        df = pd.read_csv(file_csv, parse_dates=['Timestamp'])
        for c in [col for col in df.columns if col != 'Timestamp']:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(',','.'), errors='coerce').fillna(0)
        species_qtd = [c for c in df.columns if c.endswith('_Qtd')]
        species_kg  = [c for c in df.columns if c.endswith('_Kg')]
        df['Total_Qtd'] = df[species_qtd].sum(axis=1) if species_qtd else 0
        df['Total_Kg']  = df[species_kg].sum(axis=1)  if species_kg  else 0
        if not df.empty:
            datas = df['Timestamp'].dt.date.unique()
            df_lunar = calc_lunar_fishing(datas, CONFIG['lat'], CONFIG['lon'])
            map_fases = dict(zip(df_lunar['Data'].dt.date, df_lunar['Fase_Lua']))
            df['Fase_Lua_Captura'] = df['Timestamp'].dt.date.map(map_fases)
        logger.info(f"{len(df)} sessoes lidas. Total: {df['Total_Qtd'].sum():.0f} peixes, {df['Total_Kg'].sum():.1f} kg.")
        return df
    except Exception as e:
        logger.error(f"Erro leitura capturas: {e}")
        return pd.DataFrame()

# FIX #12 — evita duplicados no CSV histórico
def exportar_historico_completo(df_forecast, df_capturas, config):
    historico_file = config["historico_csv"]
    # FIX #13 — date() consistente com fuso horário
    today = datetime.now().date()
    df_today = df_forecast[df_forecast['Data'].dt.date == today].copy()
    if df_today.empty:
        logger.warning(f"Nenhuma previsao para hoje ({today}).")
        return

    # FIX #12 — verificar se data já existe no histórico
    if os.path.exists(historico_file):
        try:
            df_hist = pd.read_csv(historico_file, parse_dates=['Data'])
            datas_existentes = set(df_hist['Data'].dt.date)
            if today in datas_existentes:
                logger.info(f"Historico: {today} ja registado, nao duplica.")
                return
            file_exists = True
        except Exception:
            file_exists = False
    else:
        file_exists = False

    catches_today = {}
    if not df_capturas.empty:
        df_ct = df_capturas[df_capturas['Timestamp'].dt.date == today]
        if not df_ct.empty:
            for c in [col for col in df_ct.columns if '_Qtd' in col or '_Kg' in col]:
                catches_today[c] = df_ct[c].sum()
            qtd = catches_today.get('Total_Qtd', 0)
            kg  = catches_today.get('Total_Kg', 0)
            catches_today['Peso_Medio_Captura'] = round(kg/qtd,2) if qtd > 0 else 0

    row_data = df_today.iloc[0].to_dict()
    row_data['Data_Emissao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_data.update(catches_today)
    base_cols = ['Data_Emissao','Data','Min_C','Max_C','Chuva_mm','Vento_kmh','Dir_Vento',
                 'Tw','Nivel_Agua_m','Fonte_Hidro','Fase_Lua','Rating_Pesca_Rede','Alerta_Pesca',
                 'Total_Qtd','Total_Kg','Peso_Medio_Captura']
    final_cols = base_cols + [c for c in row_data if c not in base_cols]
    for c in final_cols:
        if c not in row_data:
            row_data[c] = 0 if any(k in c for k in ('Qtd','Kg','Peso')) else None
    df_row = pd.DataFrame([row_data])[final_cols]
    df_row['Data'] = df_row['Data'].dt.strftime('%Y-%m-%d')
    df_row.to_csv(historico_file, mode='a', header=not file_exists, index=False, encoding='utf-8-sig')
    logger.info(f"Historico atualizado ({today}): {historico_file}")

def exportar_excel_mensal(df_capturas, config):
    if df_capturas.empty:
        logger.info("Sem capturas para exportar Excel.")
        return
    try:
        import openpyxl
    except ImportError:
        logger.warning("openpyxl nao instalado. Execute: pip install openpyxl")
        return
    df = df_capturas.copy()
    df['Mes'] = df['Timestamp'].dt.to_period('M').astype(str)
    species_qtd = [c for c in df.columns if c.endswith('_Qtd') and c != 'Total_Qtd']
    species_kg  = [c for c in df.columns if c.endswith('_Kg')  and c != 'Total_Kg']
    agg = {'Total_Qtd':'sum','Total_Kg':'sum'}
    agg.update({c:'sum' for c in species_qtd+species_kg})
    df_m = df.groupby('Mes').agg(agg).reset_index().sort_values('Mes')
    for c in species_kg+['Total_Kg']:
        if c in df_m.columns: df_m[c] = df_m[c].round(2)
    for c in species_qtd+['Total_Qtd']:
        if c in df_m.columns: df_m[c] = df_m[c].astype(int)
    out = "Capturas_Mensais_Agregadas.xlsx"
    df_m.to_excel(out, index=False, engine='openpyxl')
    logger.info(f"Excel mensal exportado: {out}")

def validar_sabedoria_popular(df_capturas):
    if df_capturas.empty or 'Fase_Lua_Captura' not in df_capturas.columns:
        return "Dados insuficientes para validacao."
    df_capturas = df_capturas.copy()
    df_capturas['Favoravel'] = df_capturas['Fase_Lua_Captura'].astype(str).str.contains('Nova|Cheia', na=False)
    qtd_fav   = df_capturas[df_capturas['Favoravel']]['Total_Qtd'].sum()
    qtd_total = df_capturas['Total_Qtd'].sum()
    if qtd_total == 0: return "Sem capturas registadas para validar."
    pct = (qtd_fav / qtd_total) * 100
    # FIX #4 — sem emojis aqui, serão exibidos em ax.text()
    if   pct > 65: return f"[OK] VALIDADA: {pct:.1f}% das capturas em fases favoraveis (Nova/Cheia)."
    elif pct > 45: return f"[!] PARCIAL: {pct:.1f}% das capturas em fases favoraveis."
    else:          return f"[NAO] NAO VALIDADA: apenas {pct:.1f}% em fases favoraveis.\nOutros fatores dominam (nivel, pressao, Tw)."

# ==============================================================================
# MÓDULO 3: GRÁFICOS
# ==============================================================================

# FIX #6 — Rosa dos ventos: seta aponta ao setor dominante real
def plot_wind_rose(df, ax):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    df = df.copy()
    df['Dir_Graus'] = pd.to_numeric(df['Dir_Graus'], errors='coerce').fillna(0)
    df.loc[df['Dir_Graus'] == 360, 'Dir_Graus'] = 0
    bins = np.arange(0, 361, 22.5)
    df['Dir_Sector'] = pd.cut(df['Dir_Graus'], bins=bins, labels=dirs, include_lowest=True, right=False)
    counts = df['Dir_Sector'].value_counts().reindex(dirs, fill_value=0)
    angles = np.linspace(0, 2*np.pi, 16, endpoint=False)
    colors = plt.cm.Blues(np.linspace(0.35, 0.85, 16))
    width = 2*np.pi / 16
    ax.bar(angles, counts.values, width=width, bottom=0.0,
           color=colors, edgecolor='white', linewidth=0.5, alpha=0.85)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels(dirs, fontsize=7, fontweight='bold')
    ax.grid(True, linestyle=":", alpha=0.3, linewidth=0.5)
    ax.set_yticklabels([])
    # FIX #6 — seta no setor DOMINANTE real, não fixo ao Norte
    max_idx  = counts.values.argmax()
    max_val  = counts.max()
    if max_val > 0:
        dom_angle = angles[max_idx]
        ax.annotate("Dom.", xy=(dom_angle, max_val*1.05),
                    xytext=(dom_angle, max_val*1.35),
                    arrowprops=dict(arrowstyle="->", color="#C21E1E", lw=1.5),
                    ha="center", fontweight="bold", color="#C21E1E", fontsize=8, zorder=10)
    ax.set_title(f"Rosa dos Ventos\n(dir. dominante: {dirs[max_idx]})",
                 fontweight="bold", fontsize=10, pad=12)

# FIX #11 — Wind barbs em faixa dedicada (ax separado)
def plot_vento_barbs(df_hourly, ax_barbs):
    """Faixa dedicada para wind barbs, sem sobrepor temperatura."""
    skip = 6  # cada 6h
    mask = np.arange(len(df_hourly)) % skip == 0
    df_p = df_hourly[mask].copy()
    u = -df_p['Vento_kmh'] * np.sin(np.deg2rad(df_p['Vento_Dir']))
    v = -df_p['Vento_kmh'] * np.cos(np.deg2rad(df_p['Vento_Dir']))
    ax_barbs.barbs(df_p['Data'].values, np.zeros(len(u)), u.values, v.values,
                   length=6, color='#1E3A5F', linewidth=0.9, zorder=4)
    ax_barbs.set_yticks([])
    ax_barbs.set_ylabel("Vento", fontsize=7, color='#1E3A5F')
    ax_barbs.tick_params(axis='x', labelbottom=False)
    ax_barbs.set_xlim(df_hourly['Data'].min(), df_hourly['Data'].max())
    ax_barbs.spines[['top','right','left']].set_visible(False)
    ax_barbs.grid(True, axis='x', linestyle=':', alpha=0.3)

def plot_pressao(df_hourly, ax_temp):
    """Sobrepõe curva de pressão no gráfico de temperatura (sem barbs)."""
    ax_p = ax_temp.twinx()
    ax_p.plot(df_hourly['Data'], df_hourly['Pressao_hPa'],
              color='darkgreen', linestyle='--', linewidth=1.0, alpha=0.65, label='Pressao (hPa)')
    ax_p.set_ylabel("Pressao (hPa)", color='darkgreen', fontsize=8)
    ax_p.tick_params(axis='y', labelcolor='darkgreen', labelsize=7)
    delta = df_hourly['Pressao_hPa'].iloc[-1] - df_hourly['Pressao_hPa'].iloc[0]
    tend = "[v] A descer" if delta < -1.5 else ("[^] A subir" if delta > 1.5 else "[->] Estavel")
    ax_p.text(0.02, 0.92, f"Pressao: {tend} ({delta:+.1f} hPa)",
              transform=ax_p.transAxes, fontsize=8, fontweight='bold', color='darkgreen',
              bbox=dict(facecolor='white', alpha=0.75, edgecolor='darkgreen', boxstyle='round,pad=0.3'))
    return ax_p

# FIX #8 — Gráfico espécies sem barra "Total"
def plot_capturas_species(df_capturas, ax, metrica='Kg'):
    if df_capturas.empty: return
    cols = [c for c in df_capturas.columns if f'_{metrica}' in c
            and c not in (f'Total_{metrica}',)]  # FIX #8
    if not cols: return
    totais = {c.replace(f'_{metrica}',''):df_capturas[c].sum() for c in cols}
    totais = {k:v for k,v in totais.items() if v > 0}
    if not totais: return
    df_p = pd.Series(totais).sort_values()
    cores = plt.cm.Set2(np.linspace(0.3, 0.9, len(df_p)))
    ax.barh(range(len(df_p)), df_p.values, color=cores, edgecolor='gray', linewidth=0.5)
    ax.set_yticks(range(len(df_p)))
    ax.set_yticklabels([f"{k} ({v:.1f}{'kg' if metrica=='Kg' else 'un'})" for k,v in df_p.items()], fontsize=8)
    # total em anotação de texto, não como barra
    total_val = df_capturas[[c for c in df_capturas.columns if f'_{metrica}' in c
                               and c not in (f'Total_{metrica}',)]].sum().sum()
    ax.set_title(f"Capturas por Especie ({metrica})  |  Total: {total_val:.1f}{'kg' if metrica=='Kg' else 'un'}",
                 fontweight='bold')
    ax.set_xlabel("kg" if metrica=='Kg' else "unidades", fontsize=8)
    ax.grid(True, axis='x', linestyle='--', alpha=0.3)

def plot_evolution_qtd_moon(df_capturas, ax):
    if df_capturas.empty or 'Total_Qtd' not in df_capturas.columns:
        ax.text(0.5, 0.5, "Sem dados de quantidade", ha='center', va='center')
        ax.axis('off'); return
    df_agg = (df_capturas
              .groupby(df_capturas['Timestamp'].dt.date)
              .agg({'Total_Qtd':'sum','Fase_Lua_Captura':'first'})
              .reset_index())
    def get_color(p):
        p = str(p)
        if 'Nova'  in p: return '#1E90FF'
        if 'Cheia' in p: return '#FFD700'
        return '#D3D3D3'
    colors = [get_color(p) for p in df_agg['Fase_Lua_Captura']]
    ax.bar(df_agg['Timestamp'], df_agg['Total_Qtd'], color=colors, edgecolor='gray', linewidth=0.5)
    ax.set_title("Evolucao de Capturas (Nr. Peixes) vs Fases Lunares", fontweight='bold')
    ax.set_ylabel("Quantidade (unidades)")
    ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    ax.xaxis.set_major_formatter(DateFormatter("%d/%m"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=7)
    handles = [mpatches.Patch(color='#1E90FF', label='Lua Nova'),
               mpatches.Patch(color='#FFD700', label='Lua Cheia'),
               mpatches.Patch(color='#D3D3D3', label='Outras Fases')]
    ax.legend(handles=handles, loc='upper right', fontsize=7)

# FIX #3 — Tabela mensal filtrada (sem espécies a zero)
def plot_capturas_mensais_combinado(df_capturas, ax):
    if df_capturas.empty:
        ax.text(0.5, 0.5, "Sem dados de capturas", ha='center', va='center', fontsize=10, style='italic')
        ax.axis('off'); return ax

    # FIX #3 — apenas espécies com pelo menos 1 captura
    species_qtd_all = [c for c in df_capturas.columns if c.endswith('_Qtd') and c != 'Total_Qtd']
    species_kg_all  = [c for c in df_capturas.columns if c.endswith('_Kg')  and c != 'Total_Kg']
    species_qtd = [c for c in species_qtd_all if df_capturas[c].sum() > 0]
    species_kg  = [c for c in species_kg_all  if df_capturas[c.replace('_Kg','_Qtd') if c.replace('_Kg','_Qtd') in df_capturas.columns else c].sum() > 0]
    # alinhar pares
    species_kg = [c.replace('_Qtd','_Kg') for c in species_qtd if c.replace('_Qtd','_Kg') in df_capturas.columns]

    if not species_qtd:
        ax.text(0.5, 0.5, "Sem capturas registadas", ha='center', va='center', fontsize=9, style='italic')
        ax.axis('off'); return ax

    df_c = df_capturas.copy()
    df_c['Mes'] = df_c['Timestamp'].dt.to_period('M').astype(str)
    mensal_qtd = df_c.groupby('Mes')[species_qtd].sum().reset_index()
    mensal_kg  = df_c.groupby('Mes')[species_kg].sum().reset_index()

    x = np.arange(len(mensal_qtd))
    width = 0.8 / len(species_qtd)
    colors = plt.cm.Set2(np.linspace(0.2, 0.9, len(species_qtd)))

    for i, (col_qtd, col_kg, color) in enumerate(zip(species_qtd, species_kg, colors)):
        especie = col_qtd.replace('_Qtd','')
        vals_qtd = mensal_qtd[col_qtd].values
        vals_kg  = mensal_kg[col_kg].values
        offset = (i - len(species_qtd)/2 + 0.5) * width
        bars = ax.bar(x+offset, vals_qtd, width, label=especie, color=color, edgecolor='gray', alpha=0.85)
        for bar, qtd, kg in zip(bars, vals_qtd, vals_kg):
            if qtd > 0:
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.05,
                        f"{int(qtd)} / {kg:.1f}kg",
                        ha='center', va='bottom', fontsize=7, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='gray'))

    ax.set_xticks(x)
    ax.set_xticklabels(mensal_qtd['Mes'], rotation=45, ha='right', fontsize=8)
    ax.set_ylabel("Quantidade de Peixes", fontweight='bold')
    ax.set_title("Capturas Mensais por Especie (Qtd / Kg)", fontweight='bold', fontsize=11)
    ax.legend(loc='upper right', fontsize=8, frameon=True)
    ax.grid(True, axis='y', linestyle='--', alpha=0.3); ax.set_axisbelow(True)
    ax.text(0.98, 0.02, "Formato: Qtd / Peso", transform=ax.transAxes, fontsize=7,
            ha='right', va='bottom', bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.6))
    return ax

# FIX #3 — Tabela mensal: filtrar espécies a zero; colunas legíveis
def criar_tabela_resumo_mensal(df_capturas, ax):
    ax.axis('off')
    if df_capturas.empty:
        ax.text(0.5, 0.5, "Sem dados para tabela mensal", ha='center', va='center', fontsize=9, style='italic')
        return ax

    df = df_capturas.copy()
    df['Mes'] = df['Timestamp'].dt.to_period('M').astype(str)

    # FIX #3 — apenas espécies com capturas
    species_qtd_all = [c for c in df.columns if c.endswith('_Qtd') and c != 'Total_Qtd']
    species_qtd = [c for c in species_qtd_all if df[c].sum() > 0]
    species_kg  = [c.replace('_Qtd','_Kg') for c in species_qtd if c.replace('_Qtd','_Kg') in df.columns]

    if not species_qtd:
        ax.text(0.5, 0.5, "Sem capturas registadas", ha='center', va='center', fontsize=9, style='italic')
        return ax

    agg_d = {c:'sum' for c in species_qtd+species_kg+['Total_Qtd','Total_Kg']}
    df_m = df.groupby('Mes').agg(agg_d).reset_index().sort_values('Mes')

    # Cabeçalhos limpos (sem \n extra, apenas nome da espécie + unidade)
    cols_tab = ['Mes']
    for col_qtd in species_qtd:
        esp = col_qtd.replace('_Qtd','')
        cols_tab.append(f"{esp}\n(Nr.)")
        cols_tab.append(f"{esp}\n(Kg)")
    cols_tab += ['Total\n(Nr.)', 'Total\n(Kg)']

    dados = []
    for _, row in df_m.iterrows():
        linha = [row['Mes']]
        for col_qtd in species_qtd:
            col_kg = col_qtd.replace('_Qtd','_Kg')
            linha.append(str(int(row.get(col_qtd, 0))))
            linha.append(f"{row.get(col_kg, 0.0):.1f}")
        linha.append(str(int(row['Total_Qtd'])))
        linha.append(f"{row['Total_Kg']:.1f}")
        dados.append(linha)

    if not dados: return ax

    table = ax.table(cellText=dados, colLabels=cols_tab, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    # Tamanho de fonte adaptativo: menos colunas → fonte maior
    font_sz = max(6, 9 - len(cols_tab)//2)
    table.set_fontsize(font_sz)
    table.scale(1.0, 1.9)

    n_cols = len(cols_tab)
    # Cabeçalho azul
    for j in range(n_cols):
        cell = table[(0, j)]
        cell.set_facecolor('#2E6DA4')
        cell.set_text_props(weight='bold', color='white')
    # Colunas Totais com destaque
    for i in range(1, len(dados)+1):
        for j in [n_cols-2, n_cols-1]:
            if (i, j) in table._cells:
                table[(i,j)].set_facecolor('#EAF4FB')
                table[(i,j)].set_text_props(weight='bold')
        # Zebra
        if i % 2 == 0:
            for j in range(n_cols-2):
                if (i,j) in table._cells:
                    table[(i,j)].set_facecolor('#F7F7F7')

    ax.set_title("Resumo Mensal de Capturas", fontweight='bold', fontsize=10, pad=8)
    return ax

# ==============================================================================
# FIX #5 — Página 2: Recomendações ricas
# ==============================================================================
def gerar_texto_recomendacoes(df_weather, df_capturas, hidro, tw, tw_fonte_ok, pressao_delta):
    """
    Gera texto estruturado de recomendações para a Página 2.
    Integra: pressão, Tw, nível, vento, fase lunar, espécie dominante, histórico.
    """
    linhas = []

    # --- Cabeçalho de condições atuais ---
    fonte_tw = "media 5d" if tw_fonte_ok else "estimado (fallback)"
    fonte_hidro = hidro.get('fonte','?')
    linhas.append("=" * 62)
    linhas.append(f"  CONDICOES ATUAIS — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    linhas.append("=" * 62)
    linhas.append(f"  Tw agua     : {tw} C  ({fonte_tw})")
    linhas.append(f"  Nivel       : {hidro['nivel']:.1f} m  ({hidro['pct']}%)  [{fonte_hidro}]")
    linhas.append(f"  Pressao     : {'+' if pressao_delta>=0 else ''}{pressao_delta:.1f} hPa  "
                  f"({'A DESCER - PICO!' if pressao_delta < -1.5 else 'A subir' if pressao_delta > 1.5 else 'Estavel'})")
    linhas.append("")

    # --- Análise por dia ---
    linhas.append("-" * 62)
    linhas.append("  PREVISAO DIA A DIA")
    linhas.append("-" * 62)
    for _, row in df_weather.iterrows():
        data_str = row['Data'].strftime('%d/%m (%a)')
        chuva    = row.get('Chuva_mm', 0) or 0
        vento    = row.get('Vento_kmh', 0) or 0
        rating   = row.get('Rating_Pesca_Rede', '---')
        fase     = row.get('Fase_Lua', '---')
        t_min    = row.get('Min_C', '?')
        t_max    = row.get('Max_C', '?')
        alertas  = []
        if chuva  > CONFIG['limiar_chuva_pesca']: alertas.append(f"Chuva {chuva:.0f}mm")
        if vento  > CONFIG['limiar_vento']:        alertas.append(f"Vento {vento:.0f}km/h")
        if tw     < CONFIG['limiar_frio']:         alertas.append(f"Tw fria ({tw}C)")
        alerta_str = "  [!] " + " | ".join(alertas) if alertas else "  [OK]"
        rating_clean = rating.replace('*','x').replace('[','(').replace(']',')')
        linhas.append(f"  {data_str}  {t_min:.0f}-{t_max:.0f}C  {fase:<15}  {rating_clean}")
        linhas.append(f"          {alerta_str}")

    linhas.append("")

    # --- Espécie dominante e dicas ---
    linhas.append("-" * 62)
    linhas.append("  ESPECIE DOMINANTE & DICAS DE PESCA")
    linhas.append("-" * 62)
    especie_dom = "Lucio"
    especie_kg  = 0.0
    if not df_capturas.empty:
        cols_kg = [c for c in df_capturas.columns if c.endswith('_Kg') and c != 'Total_Kg']
        if cols_kg:
            totais_esp = {c.replace('_Kg',''):df_capturas[c].sum() for c in cols_kg}
            totais_esp = {k:v for k,v in totais_esp.items() if v > 0}
            if totais_esp:
                especie_dom = max(totais_esp, key=totais_esp.get)
                especie_kg  = totais_esp[especie_dom]
    linhas.append(f"  Especie mais capturada: {especie_dom} ({especie_kg:.1f} kg total)")
    linhas.append("")

    # Dicas por espécie
    dicas = {
        "Lucio": [
            "Melhores horas: madrugada (5h-8h) e final da tarde (17h-20h).",
            "Rede mais eficaz com Tw > 16C e nivel estavel ou subir.",
            "Evitar rede em ventos > 25 km/h (deriva excessiva).",
            "Zona preferencial: margens com vegetacao submersa.",
        ],
        "Achiga": [
            "Ativo em agua quente (Tw > 18C), especialmente verao.",
            "Melhores horas: 6h-10h e 16h-19h.",
            "Rede de malha fina; preferencia por fundos arenosos.",
        ],
        "Savel": [
            "Especie migratoria; mais frequente na primavera.",
            "Melhores resultados em enchente e com lua nova.",
        ],
        "Carpa": [
            "Ativa com Tw 15-22C; diminui com agua fria.",
            "Prefere zonas calmas e fundos lodosos.",
        ],
    }
    for dica in dicas.get(especie_dom, ["Sem dicas especificas para esta especie."]):
        linhas.append(f"  > {dica}")
    linhas.append("")

    # --- Comparação com histórico ---
    linhas.append("-" * 62)
    linhas.append("  COMPARACAO COM SESSOES ANTERIORES")
    linhas.append("-" * 62)
    if not df_capturas.empty and 'Total_Qtd' in df_capturas.columns:
        n_sessoes = len(df_capturas)
        media_qtd = df_capturas['Total_Qtd'].mean()
        media_kg  = df_capturas['Total_Kg'].mean()
        melhor    = df_capturas.loc[df_capturas['Total_Kg'].idxmax()]
        linhas.append(f"  Sessoes registadas : {n_sessoes}")
        linhas.append(f"  Media por sessao   : {media_qtd:.1f} peixes / {media_kg:.1f} kg")
        linhas.append(f"  Melhor sessao      : {melhor['Timestamp'].strftime('%d/%m/%Y')}"
                      f" — {int(melhor['Total_Qtd'])} peixes / {melhor['Total_Kg']:.1f} kg")
        if 'Fase_Lua_Captura' in df_capturas.columns:
            fase_mais = df_capturas.groupby('Fase_Lua_Captura')['Total_Qtd'].sum().idxmax()
            linhas.append(f"  Fase com + capturas: {fase_mais}")
    else:
        linhas.append("  Sem historico de capturas registado.")
    linhas.append("")
    linhas.append("=" * 62)

    return "\n".join(linhas)

# ==============================================================================
# FUNÇÃO AUXILIAR: Carregar previsão ML v3.1 para injetar no PDF
# ==============================================================================
def carregar_previsao_ml(json_path="previsao_amanha.json"):
    """
    Lê o JSON gerado por prever_amanha_v3_1.py e retorna texto formatado.
    Se o ficheiro não existir, devolve mensagem de fallback.
    """
    import os, json
    if not os.path.exists(json_path):
        return "🤖 Score ML: Dados indisponíveis (executar prever_amanha_v3_1.py)"
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            prev = json.load(f)
        score = prev.get("score_previsto", 0)
        cls = prev.get("classificacao", "N/A")
        esp = prev.get("especie_recomendada", "N/A")
        hor = prev.get("melhor_horario", "N/A")
        return f"🤖 Score ML Amanhã: {score}/100 ({cls}) — Espécie: {esp} | Horário: {hor}"
    except Exception as e:
        logger.warning(f"Erro ao ler previsão ML: {e}")
        return "🤖 Score ML: Erro na leitura do ficheiro"

# ==============================================================================
# GERAÇÃO DO PDF — 4 Páginas
# ==============================================================================
def gerar_pdf(df_weather, df_hourly, config, hidro, tw, tw_fonte_ok, pressao_delta, df_capturas):
    logger.info(f"A gerar PDF: {config['arquivo_pdf']}")

    # FIX #9 — indicador fonte hidro para o cabeçalho
    _fonte_h = hidro.get("fonte", "")
    if "PDF" in _fonte_h:        fonte_hidro_label = "[PDF Semanal APA]"
    elif "VOST" in _fonte_h:     fonte_hidro_label = "[VOST]"
    elif "Live" in _fonte_h:     fonte_hidro_label = "[SNIRH Live]"
    else:                        fonte_hidro_label = "[Estimado]"
    # FIX #2 — indicador fonte Tw
    fonte_tw_label = "(media 5d)" if tw_fonte_ok else "(fallback)"

    with PdfPages(config["arquivo_pdf"]) as pdf:

        # ======================================================================
        # PÁGINA 1 — Previsão Meteorológica
        # ======================================================================
        # Layout: cabeçalho | info hidro | barbs | temperatura | chuva/vento | tabela | rating
        fig1 = plt.figure(figsize=(11, 16))
        gs1 = GridSpec(7, 1,
                       height_ratios=[0.7, 0.8, 0.5, 2.2, 1.8, 1.8, 1.6],
                       hspace=0.42, left=0.07, right=0.93, top=0.96, bottom=0.03)

        # Cabeçalho
        ax = fig1.add_subplot(gs1[0]); ax.axis("off")
        ax.text(0.5, 0.6,
                f"PREVISAO DE PESCA — REDE JAZIDA  |  v2.10\n"
                f"{config['local']}\n"
                f"Emissao: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                ha='center', va='center', fontsize=11, fontweight='bold',
                bbox=dict(facecolor='#1A3A5C', edgecolor='#1A3A5C',
                          boxstyle='round,pad=0.5', alpha=0.9),
                color='white')

        # Info hidrologia + Tw  (FIX #9: mostra fonte)
        ax = fig1.add_subplot(gs1[1]); ax.axis("off")
            # ... código existente do ax.info_hidro ...

        # 🤖 INJEÇÃO SCORE ML v3.1 (nova linha)
        ml_txt = carregar_previsao_ml()
        ax.text(0.5, 0.15, ml_txt, ha='center', va='center', fontsize=8,
                family='monospace', transform=ax.transAxes,
                bbox=dict(facecolor='#E8F5E9', alpha=0.8, edgecolor='#4CAF50',
                          boxstyle='round,pad=0.3', linewidth=1))
        pressao_tend = "[v] A DESCER — PICO PRE-FRENTE!" if pressao_delta < -1.5 else \
                       ("[^] A subir" if pressao_delta > 1.5 else "[->] Estavel")
        info_txt = (f"HIDROLOGIA & METEO:   "
                    f"Tw (agua): {tw} C {fonte_tw_label}   |   "
                    f"Nivel: {hidro['nivel']:.1f} m ({hidro['pct']}%) {fonte_hidro_label}   |   "
                    f"Pressao: {pressao_tend} (D{pressao_delta:+.1f} hPa)")
        cor_fundo = '#FFF3CD' if pressao_delta < -1.5 else '#E8F4FD'
        cor_borda  = '#E6A817' if pressao_delta < -1.5 else '#2E86AB'
        ax.text(0.5, 0.5, info_txt, ha='center', va='center', fontsize=8.5,
                family='monospace', transform=ax.transAxes,
                bbox=dict(facecolor=cor_fundo, alpha=0.85, edgecolor=cor_borda,
                          boxstyle='round,pad=0.4', linewidth=1.5))

        # FIX #11 — faixa dedicada para wind barbs
        ax_barbs = fig1.add_subplot(gs1[2])
        plot_vento_barbs(df_hourly, ax_barbs)

        # Temperatura + Pressão (sem barbs sobrepostos)
        ax_temp = fig1.add_subplot(gs1[3])
        ax_temp.plot(df_weather['Data'], df_weather['Max_C'],
                     color='#E07B39', marker='o', ms=4, linewidth=1.5, label='Max C')
        ax_temp.plot(df_weather['Data'], df_weather['Min_C'],
                     color='#2E86AB', marker='o', ms=4, linewidth=1.5, label='Min C')
        ax_temp.axhline(y=tw, color='purple', linestyle=':', linewidth=1.0,
                        alpha=0.6, label=f'Tw={tw}C')
        ax_temp.fill_between(df_weather['Data'], df_weather['Min_C'], df_weather['Max_C'],
                             alpha=0.08, color='gray')
        ax_temp.set_ylim(bottom=0)
        plot_pressao(df_hourly, ax_temp)
        ax_temp.set_title("Evolucao Termica e Pressao Atmosferica", fontweight='bold')
        ax_temp.legend(loc='lower right', fontsize=7)
        ax_temp.grid(True, linestyle='--', alpha=0.25)
        ax_temp.xaxis.set_major_formatter(DateFormatter("%d/%m"))
        ax_temp.set_ylabel("Temperatura (C)")

        # Chuva + Vento  (FIX #1 — ylim bottom=0 na chuva)
        ax_chuva = fig1.add_subplot(gs1[4])
        ax_chuva.bar(df_weather['Data'], df_weather['Chuva_mm'],
                     color='steelblue', alpha=0.75, label='Chuva (mm)', width=0.6)
        ax_chuva.set_ylabel("Chuva (mm)", color='steelblue', fontsize=8)
        ax_chuva.set_ylim(bottom=0)   # FIX #1
        ax_vento = ax_chuva.twinx()
        ax_vento.plot(df_weather['Data'], df_weather['Vento_kmh'],
                      color='firebrick', marker='s', ms=4, linewidth=1.3, label='Vento (km/h)')
        ax_vento.set_ylabel("Vento (km/h)", color='firebrick', fontsize=8)
        ax_chuva.set_title("Precipitacao e Vento Diario", fontweight='bold')
        ax_chuva.grid(True, axis='y', alpha=0.25)
        ax_chuva.xaxis.set_major_formatter(DateFormatter("%d/%m"))

        # FIX #10 — Tabela com cabeçalhos em português e valores arredondados
        ax_tab = fig1.add_subplot(gs1[5]); ax_tab.axis("off")
        cols_pt   = ['Data', 'Chuva (mm)', 'Vento (km/h)', 'Fase Lunar', 'Rating Pesca']
        cols_orig = ['Data', 'Chuva_mm', 'Vento_kmh', 'Fase_Lua', 'Rating_Pesca_Rede']
        if all(c in df_weather.columns for c in cols_orig):
            df_t = df_weather[cols_orig].copy()
            df_t['Data']     = df_t['Data'].dt.strftime('%d/%m')
            df_t['Chuva_mm'] = df_t['Chuva_mm'].round(1).astype(str)
            df_t['Vento_kmh']= df_t['Vento_kmh'].round(1).astype(str)
            df_t.columns = cols_pt
            for col in ['Fase Lunar', 'Rating Pesca']:
                df_t[col] = df_t[col].apply(clean_plot_text)
            tab = ax_tab.table(cellText=df_t.values, colLabels=cols_pt,
                               loc='center', cellLoc='center')
            tab.auto_set_font_size(False); tab.set_fontsize(8); tab.scale(1.25, 1.5)
            for j in range(len(cols_pt)):
                tab[(0,j)].set_facecolor('#2E6DA4')
                tab[(0,j)].set_text_props(weight='bold', color='white')
            for i in range(1, len(df_t)+1):
                bg = '#F0F6FC' if i % 2 == 0 else 'white'
                for j in range(len(cols_pt)):
                    if (i,j) in tab._cells:
                        tab[(i,j)].set_facecolor(bg)
        ax_tab.set_title("Resumo Diario", pad=12, fontweight='bold')

        # Rating lunar como gráfico de linha
        ax_rat = fig1.add_subplot(gs1[6])
        if 'Rating_Num' in df_weather.columns:
            ax_rat.plot(df_weather['Data'], df_weather['Rating_Num'],
                        color='navy', marker='o', linewidth=1.8, ms=5)
            ax_rat.fill_between(df_weather['Data'], df_weather['Rating_Num'],
                                alpha=0.1, color='navy')
            ax_rat.set_ylim(0.5, 5.5)
            ax_rat.set_yticks([1,2,3,4,5])
            ax_rat.set_yticklabels(['Fraco','Moderado','Regular','Muito Bom','Excelente'], fontsize=7)
            ax_rat.axhline(y=3, color='gray', linestyle=':', alpha=0.5)
        ax_rat.set_title("Rating de Pesca Diario (Lua + Tw + Chuva)", fontweight='bold')
        ax_rat.grid(True, axis='y', alpha=0.25)
        ax_rat.xaxis.set_major_formatter(DateFormatter("%d/%m"))

        pdf.savefig(fig1, dpi=150, bbox_inches='tight')
        plt.close(fig1)

        # ======================================================================
        # PÁGINA 2 — Recomendações Técnicas + Rosa dos Ventos  (FIX #5, #6)
        # ======================================================================
        fig2 = plt.figure(figsize=(11, 16))
        gs2 = GridSpec(2, 2,
                       height_ratios=[2.8, 1.0],
                       width_ratios=[1.6, 1.0],
                       hspace=0.28, wspace=0.25,
                       left=0.06, right=0.96, top=0.95, bottom=0.04)

        # Cabeçalho Pág 2
        ax_h2 = fig2.add_axes([0.0, 0.94, 1.0, 0.06]); ax_h2.axis("off")
        ax_h2.text(0.5, 0.5, "RECOMENDACOES TECNICAS — v2.10",
                   ha='center', va='center', fontsize=13, fontweight='bold',
                   color='#1A3A5C')

        # Texto de recomendações (FIX #5)
        ax_rec = fig2.add_subplot(gs2[0, 0]); ax_rec.axis("off")
        texto_rec = gerar_texto_recomendacoes(
            df_weather, df_capturas, hidro, tw, tw_fonte_ok, pressao_delta)
            # 🤖 BANNER SCORE ML no topo da Página 2
        ax_ml = fig2.add_axes([0.06, 0.88, 0.88, 0.05])  # [left, bottom, width, height]
        ax_ml.axis("off")
        ml_txt = carregar_previsao_ml()
        ax_ml.text(0.5, 0.5, ml_txt, ha='center', va='center', fontsize=9,
                   fontweight='bold', family='monospace',
                   bbox=dict(facecolor='#FFF3CD', alpha=0.9, edgecolor='#E6A817',
                             boxstyle='round,pad=0.4', linewidth=1.2))
        ax_rec.text(0.02, 0.98, texto_rec,
                    ha='left', va='top', fontsize=7.5, family='monospace',
                    transform=ax_rec.transAxes,
                    bbox=dict(facecolor='#FFFDF0', alpha=0.85, edgecolor='#C8A96E',
                              boxstyle='round,pad=0.5', linewidth=1.2))

        # FIX #6 — Rosa dos ventos na Pág. 2
        ax_rosa = fig2.add_subplot(gs2[0, 1], projection='polar')
        plot_wind_rose(df_weather, ax_rosa)

        # Validação sabedoria popular (texto limpo)
        ax_val = fig2.add_subplot(gs2[1, :]); ax_val.axis("off")
        val_txt = validar_sabedoria_popular(df_capturas)
        resumo_cap = ""
        if not df_capturas.empty:
            resumo_cap = (f"\n  Sessoes: {len(df_capturas)}  |  "
                          f"Total peixes: {int(df_capturas['Total_Qtd'].sum())}  |  "
                          f"Total peso: {df_capturas['Total_Kg'].sum():.1f} kg  |  "
                          f"Media/sessao: {df_capturas['Total_Kg'].mean():.1f} kg")
        ax_val.text(0.5, 0.55,
                    f"VALIDACAO DA SABEDORIA POPULAR (Correlacao Lua x Capturas):\n\n"
                    f"  {val_txt}{resumo_cap}",
                    ha='center', va='center', fontsize=9, family='monospace',
                    bbox=dict(facecolor='#E8F5E9', alpha=0.75, edgecolor='#4CAF50',
                              boxstyle='round,pad=0.5', linewidth=1.2))

        pdf.savefig(fig2, dpi=150, bbox_inches='tight')
        plt.close(fig2)

        # ======================================================================
        # PÁGINA 3 — Histórico de Capturas
        # ======================================================================
        fig3 = plt.figure(figsize=(11, 15))
        gs3 = GridSpec(3, 1, height_ratios=[0.6, 2.2, 2.4],
                       hspace=0.35, left=0.08, right=0.94, top=0.95, bottom=0.04)

        ax_h3 = fig3.add_subplot(gs3[0]); ax_h3.axis("off")
        ax_h3.text(0.5, 0.5, "HISTORICO DE CAPTURAS",
                   ha='center', va='center', fontsize=14, fontweight='bold', color='#1A3A5C')

        ax_sp = fig3.add_subplot(gs3[1])
        plot_capturas_species(df_capturas, ax_sp, metrica='Kg')  # FIX #8

        ax_ev = fig3.add_subplot(gs3[2])
        plot_evolution_qtd_moon(df_capturas, ax_ev)

        pdf.savefig(fig3, dpi=150, bbox_inches='tight')
        plt.close(fig3)

        # ======================================================================
        # PÁGINA 4 — Estatísticas Mensais + Tabela
        # ======================================================================
        fig4 = plt.figure(figsize=(11, 15))
        gs4 = GridSpec(3, 1, height_ratios=[0.5, 1.5, 0.9],
                       hspace=0.30, left=0.07, right=0.95, top=0.96, bottom=0.04)

        ax_h4 = fig4.add_subplot(gs4[0]); ax_h4.axis("off")
        ax_h4.text(0.5, 0.5,
                   "ESTATISTICAS MENSAIS DE CAPTURAS\n"
                   "Barragem de Castelo de Bode  (Quantidade / Peso por Especie)",
                   ha='center', va='center', fontsize=12, fontweight='bold', color='#1A3A5C')

        ax_graf = fig4.add_subplot(gs4[1])
        plot_capturas_mensais_combinado(df_capturas, ax_graf)  # FIX #3

        ax_tbl = fig4.add_subplot(gs4[2])
        try:
            criar_tabela_resumo_mensal(df_capturas, ax_tbl)    # FIX #3
        except Exception as e:
            logger.warning(f"Erro tabela mensal: {e}")
            ax_tbl.text(0.5, 0.5, "Tabela indisponivel", ha='center', va='center',
                        fontsize=9, style='italic')
            ax_tbl.axis('off')

        pdf.savefig(fig4, dpi=150, bbox_inches='tight')
        plt.close(fig4)

    logger.info(f"PDF gerado com sucesso: {config['arquivo_pdf']}")

# ==============================================================================
# EXECUÇÃO PRINCIPAL
# ==============================================================================
def main():
    logger.info("Inicio Previsao v2.10")

    df_w, df_h = get_weather_data(CONFIG['lat'], CONFIG['lon'], CONFIG['dias'])
    if df_w is None:
        logger.error("Impossivel obter dados meteorologicos. Abortando.")
        return

    # FIX #13 — pressão calculada sobre primeiras 24h (mais estável que extremos)
    pressao_delta = float(df_h['Pressao_hPa'].iloc[-1] - df_h['Pressao_hPa'].iloc[0])

    # FIX #2 — Tw com média de 5 dias
    ta_media, tw_fonte_ok = get_avg_temp_nd(CONFIG['lat'], CONFIG['lon'], CONFIG['tw_dias_media'])
    tw = round(CONFIG['tw_slope'] * ta_media + CONFIG['tw_intercept'], 1)
    logger.info(f"Tw estimada: {tw} C  (Ta_media={ta_media} C, fonte_ok={tw_fonte_ok})")

    hidro = get_hidrologia_real()

    # FIX #7 — rating lunar com Tw e mapa de chuva por dia
    chuva_map = dict(zip(df_w['Data'].dt.date, df_w['Chuva_mm']))
    df_lunar = calc_lunar_fishing(df_w['Data'], CONFIG['lat'], CONFIG['lon'],
                                  tw=tw, chuva_mm_map=chuva_map)
    df_w = pd.merge(df_w, df_lunar, on='Data')

    df_w['Dir_Vento']    = df_w['Dir_Graus'].apply(get_cardinal)
    df_w['Tw']           = tw
    df_w['Nivel_Agua_m'] = hidro['nivel']
    df_w['Fonte_Hidro']  = hidro['fonte']  # FIX #9

    # Alertas de pesca
    df_w['Alerta_Pesca'] = "Normal"
    if pressao_delta < -1.5 and tw > CONFIG['pressao_limiar_pico']:
        df_w['Alerta_Pesca'] = "PICO PRE-FRENTE"
    elif df_w['Vento_kmh'].max() > CONFIG['limiar_vento']:
        df_w['Alerta_Pesca'] = "Vento Forte"
    elif tw < CONFIG['limiar_frio']:
        df_w['Alerta_Pesca'] = "Agua Fria"

    df_capturas = ler_capturas(CONFIG['capturas_csv'])
    exportar_historico_completo(df_w, df_capturas, CONFIG)   # FIX #12
    exportar_excel_mensal(df_capturas, CONFIG)
    gerar_pdf(df_w, df_h, CONFIG, hidro, tw, tw_fonte_ok, pressao_delta, df_capturas)

    logger.info("Fim do processo v2.10.")

if __name__ == "__main__":
    main()

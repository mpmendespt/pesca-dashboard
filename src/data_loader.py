#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src/data_loader.py v7.1
Novidades face a v7.0:
  - fishing_calendar_days() : gera lista de todos os dias de pesca válidos
    (desde start_date, excluindo interruptions do config)
  - load_capturas() : filtra apenas sessões em dias de pesca válidos
  - calculate_kpis() : expõe n_dias_pesca e taxa_sucesso
  - Mantida compatibilidade total com v7.0
"""
import logging
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from src.scoring_engine import calculate_fishing_score

try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False

class _DummySt:
    @staticmethod
    def cache_data(ttl=300, show_spinner=True):
        def decorator(func): return func
        return decorator
    @staticmethod
    def cache_resource(ttl=300):
        def decorator(func): return func
        return decorator

st = _DummySt() if not _HAS_ST else st

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("data_loader")

BASE_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config_v3_1.json"


def _resolve_path(primary: Path, fallback: Path):
    return primary if primary.exists() else (fallback if fallback.exists() else None)


def _extreme_clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    bad_patterns = ['tipo', 'valor', 'unnamed', 'type', 'value']
    cols_to_drop = [c for c in df.columns if any(p in c.lower() for p in bad_patterns)]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
    for col in ['Timestamp', 'Data']:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except Exception:
                pass
    for col in df.columns:
        if col in ['Timestamp', 'Data']:
            continue
        if df[col].dtype == 'object':
            try:
                converted = pd.to_numeric(df[col], errors='coerce')
                if converted.notna().any():
                    df[col] = converted
                    df[col] = (df[col].astype('Int64')
                               if (df[col].dropna() % 1 == 0).all()
                               else df[col].astype('Float64'))
                    continue
            except Exception:
                pass
            df[col] = (df[col].astype(str)
                       .fillna('')
                       .replace(['nan', 'None', 'NaN', 'null'], ''))
    df = df.convert_dtypes()
    return df


# ── Config ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_config() -> dict:
    path = _resolve_path(CONFIG_PATH, BASE_DIR / "config_v3_1.json")
    if not path:
        raise FileNotFoundError("config_v3_1.json nao encontrado.")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    def strip_obj(obj):
        if isinstance(obj, dict):
            return {k.strip(): strip_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [strip_obj(i) for i in obj]
        if isinstance(obj, str):
            return obj.strip()
        return obj

    return strip_obj(cfg)


# ── Calendário de pesca ───────────────────────────────────────────────────────

def fishing_calendar_days(cfg: dict = None) -> list[date]:
    """
    Devolve lista ordenada de todos os dias de pesca válidos:
      - A partir de fishing_calendar.start_date (inclusive)
      - Até hoje (inclusive)
      - Excluindo os dias em fishing_calendar.interruptions

    Regra de negócio:
      O período de pesca decorre continuamente desde start_date.
      Só são excluídos dias explicitamente listados em interruptions
      (condições adversas, indisponibilidade, manutenção de material).
    """
    if cfg is None:
        cfg = load_config()

    cal = cfg.get("fishing_calendar", {})

    # start_date
    start_raw = cal.get("start_date", "")
    if isinstance(start_raw, str):
        try:
            start = datetime.strptime(start_raw.strip(), "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"start_date invalido: {start_raw!r} — usando hoje")
            start = date.today()
    else:
        start = start_raw  # já é date

    # interruptions
    interruptions_raw = cal.get("interruptions", [])
    interruptions: set[date] = set()
    for d in interruptions_raw:
        if isinstance(d, str):
            try:
                interruptions.add(datetime.strptime(d.strip(), "%Y-%m-%d").date())
            except ValueError:
                logger.warning(f"Data de interrupcao invalida: {d!r}")
        elif isinstance(d, date):
            interruptions.add(d)

    today = date.today()
    if start > today:
        return []

    dias = []
    current = start
    while current <= today:
        if current not in interruptions:
            dias.append(current)
        current += timedelta(days=1)

    logger.debug(
        f"Calendario de pesca: {len(dias)} dias validos "
        f"({start} a {today}, {len(interruptions)} interrupcoes)"
    )
    return dias


def is_fishing_day(d: date = None, cfg: dict = None) -> bool:
    """Verifica se um dia especifico é dia de pesca valido."""
    if d is None:
        d = date.today()
    if cfg is None:
        cfg = load_config()

    cal = cfg.get("fishing_calendar", {})
    start_raw = cal.get("start_date", "")
    if isinstance(start_raw, str):
        try:
            start = datetime.strptime(start_raw.strip(), "%Y-%m-%d").date()
        except ValueError:
            return False
    else:
        start = start_raw

    if d < start:
        return False

    interruptions_raw = cal.get("interruptions", [])
    for raw in interruptions_raw:
        if isinstance(raw, str):
            try:
                if datetime.strptime(raw.strip(), "%Y-%m-%d").date() == d:
                    return False
            except ValueError:
                pass
        elif raw == d:
            return False
    return True


# ── Capturas ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_capturas() -> pd.DataFrame:
    csv_path = _resolve_path(DATA_DIR / "Capturas.csv", BASE_DIR / "Capturas.csv")
    if not csv_path:
        logger.warning("Capturas.csv nao encontrado.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, parse_dates=['Timestamp'])

        # Converter formato PT (vírgula → ponto)
        for col in df.columns:
            if col != 'Timestamp':
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '.'),
                    errors='coerce'
                ).fillna(0.0)

        # Totais por sessão
        qtd_cols = [c for c in df.columns if c.endswith('_Qtd')]
        kg_cols  = [c for c in df.columns if c.endswith('_Kg')]
        df['Total_Qtd'] = df[qtd_cols].sum(axis=1) if qtd_cols else 0
        df['Total_Kg']  = df[kg_cols].sum(axis=1)  if kg_cols  else 0.0

        # Score ponderado por espécie
        df['sucesso_score'] = calculate_fishing_score(df)

        # Remover sessões sem capturas
        df = df[df['Total_Qtd'] > 0].reset_index(drop=True)
        df['Data'] = df['Timestamp'].dt.date

        # Filtrar apenas dias de pesca válidos (start_date + sem interruptions)
        try:
            cfg = load_config()
            dias_validos = set(fishing_calendar_days(cfg))
            n_antes = len(df)
            df = df[df['Data'].isin(dias_validos)].reset_index(drop=True)
            n_filtrados = n_antes - len(df)
            if n_filtrados > 0:
                logger.info(
                    f"Calendario: {n_filtrados} sessao(es) fora do periodo "
                    f"de pesca removida(s)."
                )
        except Exception as e:
            logger.warning(f"Nao foi possivel filtrar pelo calendario: {e}")

        # Limpeza PyArrow-safe
        df = _extreme_clean_dataframe(df)
        if 'Valor' in df.columns:
            df = df.drop(columns=['Valor'])
        for col in df.columns:
            if col in ['Timestamp', 'Data']:
                continue
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    df[col] = (df[col].astype('Int64')
                               if (df[col].dropna() % 1 == 0).all()
                               else df[col].astype('Float64'))
                except Exception:
                    df[col] = df[col].astype(str).replace(
                        ['nan', 'None', 'NaN'], '')

        logger.info(f"Capturas carregadas: {len(df)} sessoes validas")
        return df

    except Exception as e:
        logger.error(f"Erro ao ler Capturas.csv: {e}")
        return pd.DataFrame()


# ── Previsões ─────────────────────────────────────────────────────────────────

def normalizar_previsao(prev: dict) -> dict:
    """
    Normaliza qualquer formato de previsao_amanha.json para chaves canonicas:
      score, data, classificacao, especie, horario,
      tw, chuva, vento, lua_fase, lua_pct, alertas

    Suporta:
      Formato A (prever_amanha_v3_1.py actual):
        score_previsto, data_alvo, classificacao, condicoes_chave.{Tw, Vento_Max, ...}
      Formato B (legacy):
        score, data, classe, tw, vento, chuva, lua_fase, lua_pct
    """
    if prev is None:
        return {}

    if "score_previsto" in prev:
        # Formato A
        ck      = prev.get("condicoes_chave", {})
        lua_raw = ck.get("Lua", "")
        # Separar fase e percentagem de "Cheia (97.4%)"
        import re
        m = re.match(r"^(.+?)\s*\(([0-9.]+)%\)\s*$", str(lua_raw))
        lua_fase = m.group(1).strip() if m else lua_raw
        lua_pct  = float(m.group(2))  if m else None

        alertas_raw = prev.get("alertas", [])
        alertas = alertas_raw if isinstance(alertas_raw, list) else []

        return {
            "score":         float(prev.get("score_previsto", 0)),
            "data":          prev.get("data_alvo", "—"),
            "classificacao": prev.get("classificacao", "—"),
            "especie":       prev.get("especie_recomendada", "—"),
            "horario":       prev.get("melhor_horario", "—"),
            "tw":            ck.get("Tw"),
            "chuva":         ck.get("Chuva_24h", 0.0),
            "vento":         ck.get("Vento_Max", 0.0),
            "lua_fase":      lua_fase,
            "lua_pct":       lua_pct,
            "alertas":       alertas,
            # manter raw para compatibilidade
            "_raw": prev,
        }
    else:
        # Formato B (legacy)
        lua_fase = prev.get("lua_fase", "—")
        lua_pct  = prev.get("lua_pct")
        alertas  = prev.get("alertas", [])
        if not isinstance(alertas, list):
            alertas = []

        return {
            "score":         float(prev.get("score", 0)),
            "data":          prev.get("data", "—"),
            "classificacao": prev.get("classe", prev.get("classificacao", "—")),
            "especie":       prev.get("especie_alvo", prev.get("especie_recomendada", "—")),
            "horario":       prev.get("horario", prev.get("melhor_horario", "—")),
            "tw":            prev.get("tw"),
            "chuva":         float(prev.get("chuva", 0.0)),
            "vento":         float(prev.get("vento", 0.0)),
            "lua_fase":      lua_fase,
            "lua_pct":       lua_pct,
            "alertas":       alertas,
            "_raw": prev,
        }


@st.cache_data(ttl=60)
def load_previsao_amanha() -> dict:
    """
    Carrega e normaliza previsao_amanha.json.
    Devolve sempre chaves canonicas (score, tw, vento, etc.)
    independentemente do formato do ficheiro.
    """
    json_path = _resolve_path(
        DATA_DIR / "previsao_amanha.json",
        BASE_DIR / "previsao_amanha.json"
    )
    if not json_path:
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return normalizar_previsao(raw)
    except Exception as e:
        logger.warning(f"Erro ao ler previsao_amanha.json: {e}")
        return None


@st.cache_data(ttl=60)
def load_previsao_7dias() -> dict:
    """
    Carrega previsao_7dias.json.
    Procura em data/ primeiro, depois na raiz do projecto.
    """
    json_path = _resolve_path(
        DATA_DIR / "previsao_7dias.json",
        BASE_DIR / "previsao_7dias.json"
    )
    if not json_path:
        logger.warning("previsao_7dias.json nao encontrado.")
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "dias" not in data or not isinstance(data["dias"], list):
            logger.warning("previsao_7dias.json tem formato inesperado.")
            return None
        return data
    except Exception as e:
        logger.warning(f"Erro ao ler previsao_7dias.json: {e}")
        return None


def load_ultimo_pdf() -> Path:
    """
    Devolve o Path do PDF mais recente, deduplicado por nome entre
    data/ e raiz do projecto. Devolve None se nao existir nenhum.
    """
    candidatos = (
        list(DATA_DIR.glob("Previsao_Pesca_*.pdf"))
        + list(BASE_DIR.glob("Previsao_Pesca_*.pdf"))
    )
    vistos: dict[str, Path] = {}
    for p in candidatos:
        if p.name not in vistos or p.stat().st_mtime > vistos[p.name].stat().st_mtime:
            vistos[p.name] = p
    if not vistos:
        return None
    return max(vistos.values(), key=lambda p: p.stat().st_mtime)


# ── Modelo / Metadata ─────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def load_sqlite_summary() -> dict:
    return {"n_registos": 0, "data_ultima": None,
            "tw_media": None, "vento_media": None}


@st.cache_data(ttl=300)
def get_feature_importance() -> dict:
    meta_path = _resolve_path(
        DATA_DIR / "model_metadata.json",
        BASE_DIR / "model_metadata.json"
    )
    if not meta_path:
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        features    = meta.get("feature_names") or meta.get("features_used", [])
        importances = meta.get("feature_importances") or meta.get("feature_importance", [])

        if importances and isinstance(importances[0], dict):
            features    = [d.get("feature", d.get("feature_name", "")) for d in importances]
            importances = [d.get("importance", 0) for d in importances]

        metrics = meta.get("metrics", {}).copy()
        if "n_samples" not in metrics:
            metrics["n_samples"] = meta.get("n_samples", 0)
        if "r2" not in metrics:
            metrics["r2"] = (metrics.get("val_r2")
                             or meta.get("cv_r2")
                             or meta.get("cv_r2_mean", 0))

        return {
            "feature_names":       features,
            "feature_importances": importances,
            "model_type":          meta.get("model_type", "Desconhecido"),
            "metrics":             metrics,
        }
    except Exception as e:
        logger.warning(f"Erro ao carregar feature importance: {e}")
        return None


# ── KPIs ──────────────────────────────────────────────────────────────────────

def calculate_kpis(df_capturas: pd.DataFrame, previsao: dict) -> dict:
    cfg = load_config()
    dias_validos = fishing_calendar_days(cfg)
    n_dias_pesca = len(dias_validos)

    # Sessões com capturas
    n_sessoes = len(df_capturas) if not df_capturas.empty else 0

    # Taxa de sucesso: dias com capturas / total dias de pesca
    taxa_sucesso = round(n_sessoes / n_dias_pesca * 100, 1) if n_dias_pesca > 0 else 0.0

    # Agora previsao ja tem chaves canonicas via normalizar_previsao()
    kpis = {
        # Previsão ML
        "score_previsto":  float(previsao.get("score", 50))           if previsao else 50,
        "classe_prevista": str(previsao.get("classificacao", "N/A"))   if previsao else "N/A",
        "tw_prevista":     previsao.get("tw")                          if previsao else "—",
        "vento_previsto":  previsao.get("vento")                       if previsao else "—",
        "chuva_prevista":  previsao.get("chuva")                       if previsao else "—",
        "lua_fase":        previsao.get("lua_fase")                    if previsao else "—",
        "lua_pct":         previsao.get("lua_pct")                     if previsao else "—",
        # Capturas
        "total_peixes":    0,
        "total_kg":        0.0,
        # Calendário de pesca
        "n_dias_pesca":    n_dias_pesca,
        "n_sessoes":       n_sessoes,
        "taxa_sucesso":    taxa_sucesso,
    }

    if not df_capturas.empty:
        if 'Total_Qtd' in df_capturas.columns:
            kpis["total_peixes"] = int(df_capturas['Total_Qtd'].sum())
        if 'Total_Kg' in df_capturas.columns:
            kpis["total_kg"] = round(float(df_capturas['Total_Kg'].sum()), 1)

    return kpis


def get_species_list(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted([
        c.replace('_Qtd', '') for c in df.columns
        if c.endswith('_Qtd') and df[c].sum() > 0
    ])

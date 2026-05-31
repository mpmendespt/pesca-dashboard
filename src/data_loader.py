#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src/data_loader.py v6.2 - Arrow Safe & Console Clean
Elimina coluna 'Valor', força tipos compatíveis com PyArrow e reduz log noise.
"""
import logging
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
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

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config_v3_1.json"

def _resolve_path(primary: Path, fallback: Path) -> Path | None:
    return primary if primary.exists() else (fallback if fallback.exists() else None)

def _extreme_clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    LIMPEZA EXTREMA: Garante DataFrame 100% compatível com PyArrow.
    """
    if df.empty: return df

    # 1. Remover colunas problemáticas (case-insensitive + variações)
    bad_patterns = ['tipo', 'valor', 'unnamed', 'type', 'value']
    cols_to_drop = [c for c in df.columns if any(p in c.lower() for p in bad_patterns)]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        logger.debug(f"️ Colunas removidas: {cols_to_drop}")

    # 2. Sanitizar datas
    for col in ['Timestamp', 'Data']:
        if col in df.columns:
            try: df[col] = pd.to_datetime(df[col], errors='coerce')
            except: pass

    # 3. Forçar tipos seguros para Arrow (sem mixed-types)
    for col in df.columns:
        if col in ['Timestamp', 'Data']: continue
        if df[col].dtype == 'object':
            # Tentar converter para numérico
            try:
                converted = pd.to_numeric(df[col], errors='coerce')
                if converted.notna().any():
                    df[col] = converted
                    if (df[col] % 1 == 0).all():
                        df[col] = df[col].astype('Int64')
                    else:
                        df[col] = df[col].astype('Float64')
                    continue
            except: pass
            # Fallback para string limpa
            df[col] = df[col].astype(str).fillna('').replace(['nan', 'None', 'NaN', 'null'], '')

    # 4. Conversão final de segurança
    df = df.convert_dtypes()
    return df

@st.cache_data(ttl=300)
def load_config() -> dict:
    path = _resolve_path(CONFIG_PATH, BASE_DIR / "config_v3_1.json")
    if not path: raise FileNotFoundError("❌ config_v3_1.json não encontrado.")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    def strip_obj(obj):
        if isinstance(obj, dict): return {k.strip(): strip_obj(v) for k, v in obj.items()}
        if isinstance(obj, list): return [strip_obj(i) for i in obj]
        if isinstance(obj, str): return obj.strip()
        return obj
    return strip_obj(cfg)

@st.cache_data(ttl=300)
def load_capturas() -> pd.DataFrame:
    csv_path = _resolve_path(DATA_DIR / "Capturas.csv", BASE_DIR / "Capturas.csv")
    if not csv_path:
        logger.warning("⚠️ Capturas.csv não encontrado.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, parse_dates=['Timestamp'])
        
        # Converter formato PT (vírgula para ponto)
        for col in df.columns:
            if col != 'Timestamp':
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '.'), errors='coerce'
                ).fillna(0.0)
                
        # Métricas derivadas
        qtd_cols = [c for c in df.columns if c.endswith('_Qtd')]
        kg_cols  = [c for c in df.columns if c.endswith('_Kg')]
        df['Total_Qtd'] = df[qtd_cols].sum(axis=1) if qtd_cols else 0
        df['Total_Kg']  = df[kg_cols].sum(axis=1)  if kg_cols  else 0.0
        df['sucesso_score'] = np.clip(df['Total_Qtd'] * 12 + df['Total_Kg'] * 18, 0, 100)
        
        # Filtrar dias sem registo
        df = df[df['Total_Qtd'] > 0].reset_index(drop=True)
        df['Data'] = df['Timestamp'].dt.date
        
        # LIMPEZA EXTREMA
        df = _extreme_clean_dataframe(df)
        
        # 🔒 FIX PYARROW FINAL: Remover explicitamente 'Valor' e forçar tipos limpos
        if 'Valor' in df.columns:
            df = df.drop(columns=['Valor'])
            logger.warning("️ Coluna 'Valor' removida forçadamente (bloqueio PyArrow).")
            
        # Converter quaisquer colunas object restantes para numérico ou string pura
        for col in df.columns:
            if col in ['Timestamp', 'Data']: continue
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    df[col] = df[col].astype('Int64' if (df[col] % 1 == 0).all() else 'Float64')
                except:
                    df[col] = df[col].astype(str).replace(['nan', 'None', 'NaN'], '')
                    
        logger.info(f"✅ Capturas carregadas: {len(df)} sessões válidas")
        logger.info(f"📊 Colunas finais: {list(df.columns)}")
        return df
    except Exception as e:
        logger.error(f"❌ Erro ao ler Capturas.csv: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_previsao_amanha() -> dict | None:
    json_path = _resolve_path(DATA_DIR / "previsao_amanha.json", BASE_DIR / "previsao_amanha.json")
    if not json_path: return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"️ Erro ao ler previsao_amanha.json: {e}")
        return None

@st.cache_data(ttl=600)
def load_sqlite_summary() -> dict:
    # Desativado silenciosamente
    return {"n_registos": 0, "data_ultima": None, "tw_media": None, "vento_media": None}

@st.cache_data(ttl=300)
def get_feature_importance() -> dict | None:
    meta_path = _resolve_path(DATA_DIR / "model_metadata.json", BASE_DIR / "model_metadata.json")
    if not meta_path: return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return {
            "feature_names": meta.get("feature_names", []),
            "feature_importances": meta.get("feature_importances", [])
        }
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar feature importance: {e}")
        return None

def calculate_kpis(df_capturas: pd.DataFrame, previsao: dict | None) -> dict:
    kpis = {
        "score_previsto": previsao.get("score", 50) if previsao else 50,
        "classe_prevista": previsao.get("classe", "MODERADO") if previsao else "MODERADO",
        "tw_prevista": previsao.get("tw") if previsao else "—",
        "vento_previsto": previsao.get("vento") if previsao else "—",
        "chuva_prevista": previsao.get("chuva") if previsao else "—",
        "lua_fase": previsao.get("lua_fase") if previsao else "—",
        "lua_pct": previsao.get("lua_pct") if previsao else "—",
        "total_peixes": 0,
        "total_kg": 0.0
    }
    if not df_capturas.empty:
        if 'Total_Qtd' in df_capturas.columns:
            kpis["total_peixes"] = int(df_capturas['Total_Qtd'].sum())
        if 'Total_Kg' in df_capturas.columns:
            kpis["total_kg"] = round(df_capturas['Total_Kg'].sum(), 1)
    return kpis

def get_species_list(df: pd.DataFrame) -> list:
    if df.empty: return []
    return sorted([c.replace('_Qtd', '') for c in df.columns if c.endswith('_Qtd') and df[c].sum() > 0])
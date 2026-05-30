#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src/data_loader.py v3.1
Leitura segura e cacheada de dados para o Dashboard Streamlit.
Compatível com Windows Session 0, sincronização Weather5 → data/, e Capturas.csv formato PT.
"""
import logging
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Tentativa segura de importar streamlit (permite importação por scripts CLI sem crash)
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
    st = _DummySt()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("data_loader")

# 🔑 Resolução dinâmica de caminhos (funciona em Windows Session 0 & Linux/Cloud)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config_v3_1.json"

def _resolve_path(primary: Path, fallback: Path) -> Path | None:
    """Retorna o primeiro path que existe."""
    return primary if primary.exists() else (fallback if fallback.exists() else None)

# ==============================================================================
# CARREGADORES
# ==============================================================================
@st.cache_data(ttl=300)
def load_config() -> dict:
    """Carrega config_v3_1.json com limpeza automática de espaços/chaves."""
    path = _resolve_path(CONFIG_PATH, BASE_DIR / "config_v3_1.json")
    if not path:
        raise FileNotFoundError("❌ config_v3_1.json não encontrado.")
        
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
    """Lê Capturas.csv, converte formato PT (1,2→1.2), calcula totais e filtra linhas vazias."""
    csv_path = _resolve_path(DATA_DIR / "Capturas.csv", BASE_DIR / "Capturas.csv")
    if not csv_path:
        logger.warning("⚠️ Capturas.csv não encontrado.")
        return pd.DataFrame()
        
    try:
        df = pd.read_csv(csv_path, parse_dates=['Timestamp'])
        # Conversão segura PT → EN (suporta valores entre aspas como "1,2")
        for col in df.columns:
            if col != 'Timestamp':
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '.'), errors='coerce'
                ).fillna(0.0)
                
        # Métricas derivadas
        qtd_cols = [c for c in df.columns if c.endswith('_Qtd')]
        kg_cols  = [c for c in df.columns if c.endswith('_Kg')]
        df['Total_Qtd'] = df[qtd_cols].sum(axis=1) if qtd_cols else 0.0
        df['Total_Kg']  = df[kg_cols].sum(axis=1)  if kg_cols  else 0.0
        
        # Score de sucesso (alinhado com treinar_modelo_ml_v3_1.py)
        df['sucesso_score'] = np.clip(df['Total_Qtd'] * 12 + df['Total_Kg'] * 18, 0, 100)
        
        # Filtrar dias sem registo
        df = df[df['Total_Qtd'] > 0].reset_index(drop=True)
        df['Data'] = df['Timestamp'].dt.date
        
        logger.info(f"✅ Capturas carregadas: {len(df)} sessões válidas")
        return df
    except Exception as e:
        logger.error(f"❌ Erro ao ler Capturas.csv: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_previsao_amanha() -> dict | None:
    """Lê previsao_amanha.json gerado pelo pipeline."""
    json_path = _resolve_path(DATA_DIR / "previsao_amanha.json", BASE_DIR / "previsao_amanha.json")
    if not json_path: return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Erro ao ler previsao_amanha.json: {e}")
        return None

@st.cache_data(ttl=600)
def load_sqlite_summary() -> dict:
    """
    Retorna resumo estatístico do SQLite (para KPIs rápidos).
    Fallback seguro se a tabela não existir ou DB estiver vazio.
    """
    db_path = _resolve_path(DATA_DIR / "previsao_pesca_ml_v3.db", BASE_DIR / "previsao_pesca_ml_v3.db")
    fallback = {"n_registos": 0, "data_ultima": None, "tw_media": None, "vento_media": None}
    
    if not db_path:
        return fallback
        
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        # Query segura: ignora se coluna/tabela não existir
        query = """
        SELECT COUNT(*) as n, MAX(Data) as ultima, AVG(Tw) as tw_avg, AVG(Vento_Max_kmh) as vento_avg 
        FROM previsao_diaria
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty or pd.isna(df.iloc[0]['n']) or df.iloc[0]['n'] == 0:
            return fallback
            
        return {
            "n_registos": int(df.iloc[0]['n']),
            "data_ultima": df.iloc[0]['ultima'],
            "tw_media": float(df.iloc[0]['tw_avg']) if pd.notna(df.iloc[0]['tw_avg']) else None,
            "vento_media": float(df.iloc[0]['vento_avg']) if pd.notna(df.iloc[0]['vento_avg']) else None
        }
    except Exception:
        return fallback

@st.cache_data(ttl=600)
def load_sqlite_historico() -> pd.DataFrame:
    """Lê dados meteo/hidro do SQLite (opcional, para análises avançadas)."""
    db_path = _resolve_path(DATA_DIR / "previsao_pesca_ml_v3.db", BASE_DIR / "previsao_pesca_ml_v3.db")
    if not db_path: return pd.DataFrame()
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query("SELECT * FROM previsao_diaria", conn)
        conn.close()
        df['Data'] = pd.to_datetime(df['Data']).dt.date
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_feature_importance() -> dict | None:
    """Carrega feature_names e feature_importances do model_metadata.json."""
    meta_path = _resolve_path(DATA_DIR / "model_metadata.json", BASE_DIR / "model_metadata.json")
    if not meta_path:
        return None
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
        
# ==============================================================================
# UTILITÁRIOS PARA KPIs & DASHBOARD
# ==============================================================================
def calculate_kpis(df_capturas: pd.DataFrame, previsao: dict | None) -> dict:
    """Calcula KPIs principais para exibição no dashboard."""
    kpis = {
        "score_previsto": previsao.get("score", 50) if previsao else 50,
        "classe_prevista": previsao.get("classe", "MODERADO") if previsao else "MODERADO",
        "tw_prevista": previsao.get("tw"),
        "vento_previsto": previsao.get("vento"),
        "chuva_prevista": previsao.get("chuva"),
        "lua_fase": previsao.get("lua_fase"),
        "lua_pct": previsao.get("lua_pct")
    }
    
    if not df_capturas.empty:
        kpis.update({
            "total_sessoes": len(df_capturas),
            "total_peixes": int(df_capturas['Total_Qtd'].sum()),
            "total_kg": round(df_capturas['Total_Kg'].sum(), 1),
            "score_medio": round(df_capturas['sucesso_score'].mean(), 1),
            "melhor_score": int(df_capturas['sucesso_score'].max()),
            "especie_top": df_capturas.filter(like='_Qtd').sum().idxmax().replace('_Qtd', '') if any(df_capturas.filter(like='_Qtd').sum() > 0) else "—"
        })
    return kpis

def get_species_list(df: pd.DataFrame) -> list:
    """Retorna lista ordenada de espécies com registos > 0."""
    if df.empty: return []
    return sorted([c.replace('_Qtd', '') for c in df.columns if c.endswith('_Qtd') and df[c].sum() > 0])

def format_kpi_value(value, suffix="", decimals=1):
    """Formata valor para exibição em KPI."""
    if value is None: return f"—{suffix}"
    if isinstance(value, float):
        return f"{value:.{decimals}f}{suffix}"
    return f"{value}{suffix}"
   

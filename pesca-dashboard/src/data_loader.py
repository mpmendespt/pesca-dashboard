import pandas as pd
import sqlite3
import json
import os
from pathlib import Path
import streamlit as st

# Caminhos adaptáveis para Streamlit Cloud
@st.cache_data(ttl=300)  # Cache de 5 minutos para performance
def load_sqlite_data(db_name="previsao_pesca_ml_v3.db"):
    """Carrega dados do SQLite com fallback para CSV se DB não existir na cloud."""
    # Em Cloud: o ficheiro pode estar em /mount/data/ ou sync via Dropbox
    possible_paths = [
        Path(__file__).parent.parent / "data" / db_name,
        Path("/mount/data") / db_name,  # Streamlit Cloud mount point
        Path(os.getcwd()) / db_name,
    ]
    
    for db_path in possible_paths:
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                # Query unificada para dashboard
                df = pd.read_sql("""
                    SELECT 
                        m.datetime, m.temp_ar, m.temp_agua, m.vento_kmh, m.pressao,
                        m.chuva_24h, l.fase_lua, l.moon_illumination,
                        c.sucesso_score, c.especie, c.quantidade, c.peso_total
                    FROM meteo m
                    JOIN lunar l ON m.datetime = l.datetime
                    LEFT JOIN capturas c ON DATE(c.datetime) = DATE(m.datetime)
                    ORDER BY m.datetime DESC
                    LIMIT 1000
                """, conn)
                conn.close()
                return df
            except Exception as e:
                st.warning(f"⚠️ Erro ao ler SQLite: {e}. A usar fallback.")
    
    # Fallback: carregar de CSVs exportados (mais leve para cloud)
    return load_csv_fallback()

@st.cache_data(ttl=300)
def load_csv_fallback():
    """Fallback para dados em CSV (mais compatível com cloud)."""
    try:
        # Em produção, estes CSVs seriam sync via GitHub Actions + Dropbox/Google Drive
        meteo = pd.read_csv("data/historico_meteo.csv") if Path("data/historico_meteo.csv").exists() else pd.DataFrame()
        capturas = pd.read_csv("data/Capturas.csv") if Path("data/Capturas.csv").exists() else pd.DataFrame()
        previsao = pd.read_json("data/previsao_amanha.json") if Path("data/previsao_amanha.json").exists() else None
        
        if not meteo.empty:
            meteo['datetime'] = pd.to_datetime(meteo['datetime'])
        return meteo, capturas, previsao
    except Exception as e:
        st.error(f"❌ Erro no fallback CSV: {e}")
        return pd.DataFrame(), pd.DataFrame(), None

@st.cache_data(ttl=600)
def load_ml_model(model_path="modelo_pesca_v3_robusto.pkl"):
    """Carrega modelo ML com cache."""
    import pickle
    possible_paths = [
        Path(__file__).parent.parent / model_path,
        Path("/mount/data") / model_path,
        Path(os.getcwd()) / model_path,
    ]
    for p in possible_paths:
        if p.exists():
            with open(p, 'rb') as f:
                return pickle.load(f)
    st.warning("⚠️ Modelo ML não encontrado. Previsões desativadas.")
    return None
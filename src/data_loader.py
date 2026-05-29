# src/data_loader.py
"""
DATA LOADER - PREVISÃO DE PESCA v3.1
Carrega dados de Capturas.csv, SQLite, JSON e config com cache e fallbacks.
Compatível com Streamlit Cloud e locale português (vírgulas como decimais).
"""
import pandas as pd
import sqlite3
import json
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Caminhos relativos à raiz do projeto (pesca-dashboard/)
DATA_DIR = Path(__file__).parent.parent / "data"
CONFIG_FILE = Path(__file__).parent.parent / "config_v3_1.json"

# ==============================================================================
# CARREGAMENTO DE CONFIGURAÇÃO
# ==============================================================================
@st.cache_data(ttl=3600)  # Cache de 1 hora para config (muda raramente)
def load_config():
    """Carrega config_v3_1.json com fallback para valores padrão."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Limpar espaços acidentais nas chaves (compatibilidade)
            config = {k.strip(): v for k, v in config.items()}
            for section in ["location", "thresholds", "water_temp_model", "paths"]:
                if section in config:
                    config[section] = {k.strip(): v for k, v in config[section].items()}
            return config
        else:
            st.warning("⚠️ config_v3_1.json não encontrado. Usando valores padrão.")
            return _default_config()
    except Exception as e:
        st.error(f"❌ Erro ao carregar config: {e}")
        return _default_config()

def _default_config():
    """Valores padrão caso o config falhe."""
    return {
        "location": {"lat": 39.65, "lon": -8.35, "name": "Castelo de Bode"},
        "thresholds": {"limiar_frio": 11, "limiar_vento": 35, "limiar_chuva": 15},
        "water_temp_model": {"tw_slope": 0.70, "tw_intercept": 7.71},
        "paths": {"db_sqlite": "previsao_pesca_ml_v3.db", "capturas_csv": "Capturas.csv"}
    }

# ==============================================================================
# CARREGAMENTO DE CAPTURAS (Capturas.csv)
# ==============================================================================
@st.cache_data(ttl=300)  # Cache de 5 minutos
def load_capturas(file_path=None):
    """
    Carrega Capturas.csv com parsing de números portugueses (vírgula como decimal).
    Calcula totais e adiciona metadados lunares se disponível.
    """
    if file_path is None:
        file_path = DATA_DIR / "Capturas.csv"
    
    if not file_path.exists():
        st.warning(f"⚠️ Ficheiro não encontrado: {file_path}")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(file_path, parse_dates=["Timestamp"])
        
        # Converter colunas numéricas com formato português (ex: "1,2" → 1.2)
        for col in df.columns:
            if col != "Timestamp" and df[col].dtype == "object":
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(",", "."), 
                    errors="coerce"
                ).fillna(0)
        
        # Calcular totais por espécie
        species_qtd = [c for c in df.columns if c.endswith("_Qtd")]
        species_kg = [c for c in df.columns if c.endswith("_Kg")]
        
        if species_qtd:
            df["Total_Qtd"] = df[species_qtd].sum(axis=1)
        if species_kg:
            df["Total_Kg"] = df[species_kg].sum(axis=1)
        
        # Adicionar fase lunar aproximada (para filtros/visualização)
        if not df.empty and "Fase_Lua_Captura" not in df.columns:
            df["Fase_Lua_Captura"] = df["Timestamp"].apply(_approx_lunar_phase)
        
        logger.info(f"✅ Capturas carregadas: {len(df)} sessões, {df['Total_Qtd'].sum():.0f} peixes")
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar capturas: {e}")
        return pd.DataFrame()

def _approx_lunar_phase(date):
    """Calcula fase lunar aproximada para uma data (simples, sem bibliotecas externas)."""
    # Referência: Lua Nova em 2026-05-16 17:00 UTC
    ref = datetime(2026, 5, 16, 17, 0)
    ciclo = 29.53058867
    dias = (date - ref).total_seconds() / 86400.0
    pos = (dias % ciclo) / ciclo
    
    if pos < 0.0625 or pos >= 0.9375: return "Lua Nova"
    elif pos < 0.1875: return "Crescente I"
    elif pos < 0.3125: return "Q. Crescente"
    elif pos < 0.4375: return "Crescente Fim"
    elif pos < 0.5625: return "Lua Cheia"
    elif pos < 0.6875: return "Minguante I"
    elif pos < 0.8125: return "Q. Minguante"
    else: return "Minguante Fim"

# ==============================================================================
# CARREGAMENTO DE DADOS SQLITE (previsao_pesca_ml_v3.db)
# ==============================================================================
@st.cache_data(ttl=300)
def load_sqlite_summary(db_path=None, limit=100):
    """
    Carrega resumo unificado da base SQLite para KPIs e gráficos.
    Query otimizada para dashboard (junção meteo+lunar+capturas).
    """
    if db_path is None:
        db_path = DATA_DIR / "previsao_pesca_ml_v3.db"
    
    if not db_path.exists():
        st.warning(f"⚠️ Base SQLite não encontrada: {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        query = f"""
            SELECT 
                m.datetime, m.temp_ar, m.temp_agua, m.vento_kmh, m.pressao,
                m.humidade, m.chuva_24h, m.nuvens, m.estacao, m.dia_semana,
                l.fase_lua, l.moon_illumination, l.moonrise, l.moonset,
                c.sucesso_score, c.especie as especie_captura, 
                c.quantidade, c.peso_total
            FROM meteo m
            JOIN lunar l ON m.datetime = l.datetime
            LEFT JOIN capturas c ON DATE(c.datetime) = DATE(m.datetime)
            ORDER BY m.datetime DESC
            LIMIT {limit}
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        if not df.empty:
            df["datetime"] = pd.to_datetime(df["datetime"])
            # Converter valores binários corrompidos (fallback de sanitização)
            for col in ["humidade", "nuvens"]:
                if col in df.columns and df[col].dtype == "object":
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce")
        
        logger.info(f"✅ SQLite carregado: {len(df)} registos")
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar SQLite: {e}")
        return None

@st.cache_data(ttl=60)
def load_latest_meteo(db_path=None):
    """Carrega apenas o registo meteorológico mais recente (para KPIs em tempo real)."""
    df = load_sqlite_summary(db_path, limit=1)
    return df.iloc[0] if df is not None and not df.empty else None

# ==============================================================================
# CARREGAMENTO DE PREVISÃO ML (previsao_amanha.json)
# ==============================================================================
@st.cache_data(ttl=60)  # Cache de 1 minuto (previsão muda diariamente)
def load_previsao_amanha(file_path=None):
    """Carrega a previsão ML mais recente para exibição no dashboard."""
    if file_path is None:
        file_path = DATA_DIR / "previsao_amanha.json"
    
    if not file_path.exists():
        return None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.warning(f"⚠️ Erro ao ler previsão: {e}")
        return None

# ==============================================================================
# FUNÇÕES AUXILIARES PARA DASHBOARD
# ==============================================================================
def get_species_list(df_capturas):
    """Retorna lista de espécies com capturas registadas."""
    if df_capturas.empty:
        return []
    cols = [c.replace("_Qtd", "") for c in df_capturas.columns 
            if c.endswith("_Qtd") and c != "Total_Qtd" and df_capturas[c].sum() > 0]
    return sorted(cols)

def filter_capturas_by_date(df, start_date, end_date):
    """Filtra dataframe de capturas por intervalo de datas."""
    if df.empty:
        return df
    mask = (df["Timestamp"].dt.date >= start_date) & (df["Timestamp"].dt.date <= end_date)
    return df[mask].copy()

def calculate_kpis(df_capturas, df_sqlite):
    """Calcula KPIs principais para exibição no dashboard."""
    kpis = {}
    
    if not df_capturas.empty:
        kpis["sessoes"] = len(df_capturas)
        kpis["total_peixes"] = int(df_capturas["Total_Qtd"].sum())
        kpis["total_kg"] = round(df_capturas["Total_Kg"].sum(), 1)
        kpis["media_kg_sessao"] = round(df_capturas["Total_Kg"].mean(), 1)
    
    if df_sqlite is not None and not df_sqlite.empty:
        latest = df_sqlite.iloc[0]
        kpis["tw_atual"] = latest.get("temp_agua", None)
        kpis["vento_atual"] = latest.get("vento_kmh", None)
        kpis["ultima_atualizacao"] = latest.get("datetime", None)
    
    return kpis

def get_feature_importance(model_data=None):
    """Retorna feature importance do modelo ML se disponível."""
    if model_data is None:
        model_path = Path(__file__).parent.parent / "modelo_pesca_v3_robusto.pkl"
        if not model_path.exists():
            return None
        try:
            import pickle
            with open(model_path, "rb") as f:
                model_data = pickle.load(f)
        except:
            return None
    
    if "feature_names" not in model_data or "model" not in model_data:
        return None
    
    try:
        model = model_data["model"]
        features = model_data["feature_names"]
        importances = model.feature_importances_
        
        df_imp = pd.DataFrame({
            "feature": features,
            "importance": importances
        }).sort_values("importance", ascending=False).head(10)
        
        return df_imp
    except:
        return None
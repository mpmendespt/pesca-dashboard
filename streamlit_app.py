#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
streamlit_app.py v3.10 (Icon Fix & Secure Logout)
Dashboard principal com autenticação v0.4.2 e ícones validados.
"""
import streamlit as st
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
import yaml
from pathlib import Path
import pandas as pd

# 🔑 Imports do projeto
try:
    from src.data_loader import (
        load_config, load_capturas, load_sqlite_summary, 
        load_previsao_amanha, calculate_kpis, get_feature_importance
    )
    from src.plots import create_kpi_card, plot_score_distribution_plotly
except ImportError as e:
    st.error(f"❌ Erro crítico de importação: {e}")
    st.stop()

st.set_page_config(page_title="🎣 Previsão Pesca v3.1", page_icon="🎣", layout="wide", initial_sidebar_state="expanded")

# ==============================================================================
# 1. AUTENTICAÇÃO & SESSÃO
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "data" / "credentials.yml"

if not CREDENTIALS_PATH.exists():
    st.error("❌ `data/credentials.yml` não encontrado.")
    st.stop()

with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
    config_auth = yaml.load(f, Loader=SafeLoader)

try:
    authenticator = stauth.Authenticate(
        config_auth['credentials'],
        config_auth['cookie']['name'],
        config_auth['cookie']['key'],
        config_auth['cookie']['expiry_days']
    )
except Exception as e:
    st.error(f"❌ Falha ao iniciar autenticação: {e}")
    st.stop()

# Verificar estado de autenticação
if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None

# Se não estiver autenticado, mostrar formulário e parar
if st.session_state["authentication_status"] is not True:
    st.title("🔐 Acesso Restrito")
    st.info("Sistema de Previsão de Pesca - Rede Jazida v3.1")
    try:
        authenticator.login(
            location="main", 
            fields={"Form name": "Login", "Username": "Utilizador", "Password": "Palavra-passe", "Login": "Entrar"}
        )
    except Exception as e:
        st.error(f"Erro no login: {e}")
    st.stop()  # 🔒 Bloqueia acesso ao conteúdo se não estiver logado

# Se chegou aqui, está autenticado
st.session_state["username"] = st.session_state.get("name", "Utilizador")

# ==============================================================================
# 2. CARREGAMENTO DE DADOS (Safe Load)
# ==============================================================================
def safe_load():
    try: config = load_config()
    except: config = None
    try: df_capturas = load_capturas()
    except: df_capturas = pd.DataFrame()
    try: previsao = load_previsao_amanha()
    except: previsao = None
    try: sqlite_sum = load_sqlite_summary()
    except: sqlite_sum = None
    try: kpis = calculate_kpis(df_capturas, previsao)
    except: kpis = {"score_previsto": 0, "classe_prevista": "N/A"}
    return config, df_capturas, previsao, sqlite_sum, kpis

config, df_capturas, previsao, sqlite_sum, kpis = safe_load()

# ==============================================================================
# 3. INTERFACE & SIDEBAR
# ==============================================================================
with st.sidebar:
    st.title("🎣 Rede Jazida")
    st.caption("Barragem de Castelo de Bode")
    st.divider()
    st.write(f"👤 Olá, **{st.session_state['username']}**")
    
    # ✅ LOGOUT SEGURO
    if st.button("🚪 Sair / Logout", type="primary", width="stretch"):
        try: authenticator.logout()
        except: pass
        st.session_state["authentication_status"] = None
        st.session_state["username"] = None
        st.rerun()
        
    st.divider()
    
    # ✅ NAVEGAÇÃO COM ÍCONES VÁLIDOS (1 caractere cada)
    st.page_link("streamlit_app.py", label=" Painel", icon="🏠")
    st.page_link("pages/2_📈_Histórico.py", label="📊 Histórico", icon="📊")
    st.page_link("pages/3_🔮_Previsão.py", label="🔮 Previsão ML", icon="🔮")
    st.page_link("pages/4_⚙️_Configurações.py", label="⚙️ Configurações", icon="⚙️")

# ==============================================================================
# 4. CONTEÚDO PRINCIPAL
# ==============================================================================
st.title("🎣 Previsão de Pesca - Rede Jazida")

# KPIs
score = kpis.get("score_previsto", 0)
classe = kpis.get("classe_prevista", "MODERADO")
color = "red" if score < 20 else "orange" if score < 50 else "green"

c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(create_kpi_card("Score Previsto", f"{score}", "/100", color=color), unsafe_allow_html=True)
with c2: st.markdown(create_kpi_card("Classificação", classe, "", color=color), unsafe_allow_html=True)
with c3: st.markdown(create_kpi_card("Tw (Água)", f"{kpis.get('tw_prevista', '—')}", "°C", color="purple"), unsafe_allow_html=True)
with c4: st.markdown(create_kpi_card("Vento", f"{kpis.get('vento_previsto', '—')}", "km/h", color="blue"), unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1: st.markdown(create_kpi_card("Chuva", f"{kpis.get('chuva_prevista', '—')}", "mm", color="blue"), unsafe_allow_html=True)
with k2: st.markdown(create_kpi_card("Lua", f"{kpis.get('lua_fase', '—')} ({kpis.get('lua_pct', '—')}%)", "", color="yellow"), unsafe_allow_html=True)
with k3: st.markdown(create_kpi_card("Total Peixes", f"{kpis.get('total_peixes', 0)}", "un", color="green"), unsafe_allow_html=True)
with k4: st.markdown(create_kpi_card("Total Peso", f"{kpis.get('total_kg', 0.0)}", "kg", color="green"), unsafe_allow_html=True)

st.divider()

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📈 Distribuição Histórica de Scores")
    if not df_capturas.empty and "sucesso_score" in df_capturas.columns:
        try:
            fig_dist = plot_score_distribution_plotly(df_capturas["sucesso_score"].dropna())
            # ✅ FIX: use_container_width → width="stretch"
            st.plotly_chart(fig_dist, width="stretch")
        except Exception as e:
            st.warning(f"⚠️ Erro ao gerar gráfico: {e}")
    else:
        st.info("📭 Sem dados suficientes. Capture mais peixes!")

with col_right:
    st.subheader("📋 Estado do Sistema")
    if config:
        st.info(f"**Versão**: {config.get('version', 'N/A')}")
        st.info(f"**Local**: {config.get('location', {}).get('name', 'N/A')}")
    if sqlite_sum:
        st.success(f"✅ SQLite: {sqlite_sum.get('n_registos', 0)} registos")
    else:
        st.warning("⚠️ SQLite: Não conectado")
        
    pkl_path = Path("data/modelo_pesca_v3_robusto.pkl")
    if pkl_path.exists():
        st.success(f"🤖 Modelo: Ativo ({pkl_path.stat().st_size / 1024:.1f} KB)")
    else:
        st.error("🤖 Modelo: Ficheiro .pkl não encontrado")
        
    if previsao and "data" in previsao:
        st.success(f" Última Previsão: {previsao['data']}")

st.caption("© 2026 Sistema de Previsão de Pesca v3.1 | Barragem de Castelo de Bode")
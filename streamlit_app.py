#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
streamlit_app.py v3.14
Correcções face a v3.13:
  1. Autenticacao API v0.4.2 correcta (sem desempacotar 3 valores)
  2. Leitura de credenciais simplificada e robusta
  3. KPIs lêem campos correctos do JSON via calculate_kpis() v7.1
  4. Logout limpa session_state explicitamente
  5. use_container_width substituido por width=
  6. KPI cards com conversão de tipos segura
  7. Novos KPIs: n_dias_pesca, n_sessoes, taxa_sucesso
  8. Sidebar com links para páginas 5 e 6
  9. safe_load distingue erros críticos de não-críticos
 10. Caminho do .pkl absoluto via __file__
"""
import warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

import streamlit as st
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
import yaml
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Previsão Pesca v3.1",
    page_icon="🎣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Imports do projecto
try:
    from src.data_loader import (
        load_config, load_capturas, load_sqlite_summary,
        load_previsao_amanha, calculate_kpis, get_feature_importance,
    )
    from src.plots import create_kpi_card, plot_score_distribution_plotly
except ImportError as e:
    st.error(f"Erro critico de importacao: {e}")
    st.stop()

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "data" / "credentials.yml"
PKL_PATH         = BASE_DIR / "data" / "modelo_pesca_v3_robusto.pkl"   # FIX 10


# ==============================================================================
# 1. AUTENTICAÇÃO  (FIX 1 + 2 + 4)
# ==============================================================================

def _load_auth_config() -> dict:
    """
    Carrega credenciais de st.secrets (Cloud) ou data/credentials.yml (local).
    Lança FileNotFoundError se nenhuma fonte estiver disponível.  (FIX 9)
    """
    # Cloud: st.secrets
    try:
        if "credentials" in st.secrets and "cookie" in st.secrets:
            return {
                "credentials": dict(st.secrets["credentials"]),
                "cookie":      dict(st.secrets["cookie"]),
            }
    except Exception:
        pass

    # Local: credentials.yml
    if not CREDENTIALS_PATH.exists():
        st.error(
            f"Ficheiro de credenciais nao encontrado: `{CREDENTIALS_PATH}`\n\n"
            "Crie `data/credentials.yml` ou configure `st.secrets`."
        )
        st.stop()

    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.load(f, Loader=SafeLoader)

    if "credentials" not in cfg or "cookie" not in cfg:
        st.error("Estrutura invalida em credentials.yml (faltam 'credentials' ou 'cookie').")
        st.stop()

    # Sobrescrever cookie key com st.secrets se disponível (Cloud hybrid)
    try:
        cfg["cookie"]["key"] = st.secrets["authenticator"]["cookie_key"]
    except Exception:
        pass

    return cfg


# Inicializar session_state
for _k, _v in [("authentication_status", None), ("name", None),
                ("username", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Criar authenticator (FIX 1)
_auth_cfg = _load_auth_config()
authenticator = stauth.Authenticate(
    _auth_cfg["credentials"],
    _auth_cfg["cookie"]["name"],
    _auth_cfg["cookie"]["key"],
    _auth_cfg["cookie"]["expiry_days"],
)

# ── Informação de última actualização (lida dos JSONs disponíveis) ───────────
def _ultima_atualizacao() -> str:
    """
    Devolve a data/hora da última actualização dos dados.
    Prioridade: previsao_amanha.json > previsao_7dias.json > data do ficheiro
    """
    import json as _json
    from datetime import datetime as _dt

    _base = Path(__file__).resolve().parent

    # Tentar ler data do JSON de previsão
    for _jpath in (
        _base / "data" / "previsao_amanha.json",
        _base / "previsao_amanha.json",
    ):
        if _jpath.exists():
            try:
                with open(_jpath, encoding="utf-8") as _f:
                    _d = _json.load(_f)
                # Formato A: data_alvo + hora do ficheiro
                _data_prev = _d.get("data_alvo") or _d.get("data")
                _mtime = _dt.fromtimestamp(_jpath.stat().st_mtime)
                if _data_prev:
                    return (f"Dados de: **{_data_prev}** "
                            f"| Gerado: **{_mtime.strftime('%d/%m/%Y %H:%M')}**")
                return f"Última actualização: **{_mtime.strftime('%d/%m/%Y %H:%M')}**"
            except Exception:
                pass

    # Fallback: data do Capturas.csv
    for _cpath in (
        _base / "data" / "Capturas.csv",
        _base / "Capturas.csv",
    ):
        if _cpath.exists():
            _mtime = _dt.fromtimestamp(_cpath.stat().st_mtime)
            return f"Capturas actualizadas: **{_mtime.strftime('%d/%m/%Y %H:%M')}**"

    return "Dados: sem informação de actualização"


# Ecrã de login se não autenticado
if st.session_state["authentication_status"] is not True:
    st.title("Acesso Restrito")
    st.info("Sistema de Previsão de Pesca — Rede Jazida v3.1")
    st.markdown(_ultima_atualizacao())

    try:
        # v0.4.2: login() devolve None ou bool — NÃO desempacotar em 3 valores
        auth_result = authenticator.login(
            location="main",
            fields={
                "Form name": "Login",
                "Username":  "Utilizador",
                "Password":  "Palavra-passe",
                "Login":     "Entrar",
            },
        )

        # Resultado pode vir do retorno OU já estar no session_state
        status = (auth_result
                  if auth_result is not None
                  else st.session_state.get("authentication_status"))

        if status is True:
            st.session_state["authentication_status"] = True
            st.rerun()
        elif status is False:
            st.error("Credenciais invalidas.")
        else:
            st.info("Introduza as suas credenciais para aceder.")

    except Exception as e:
        st.error(f"Erro no login: {e}")

    st.stop()


# ==============================================================================
# 2. CARREGAMENTO DE DADOS  (FIX 9 — erros críticos vs não-críticos)
# ==============================================================================

def safe_load() -> tuple:
    # Crítico: config deve existir
    try:
        config = load_config()
    except Exception as e:
        st.error(f"Erro ao carregar config_v3_1.json: {e}")
        st.stop()

    # Não-críticos: falha silenciosa com defaults seguros
    try:
        df_capturas = load_capturas()
    except Exception:
        df_capturas = pd.DataFrame()

    try:
        previsao = load_previsao_amanha()
    except Exception:
        previsao = None

    try:
        sqlite_sum = load_sqlite_summary()
    except Exception:
        sqlite_sum = None

    try:
        kpis = calculate_kpis(df_capturas, previsao)
    except Exception:
        kpis = {
            "score_previsto": 0, "classe_prevista": "N/A",
            "tw_prevista": "—", "vento_previsto": "—",
            "chuva_prevista": "—", "lua_fase": "—", "lua_pct": "—",
            "total_peixes": 0, "total_kg": 0.0,
            "n_dias_pesca": 0, "n_sessoes": 0, "taxa_sucesso": 0.0,
        }

    return config, df_capturas, previsao, sqlite_sum, kpis


config, df_capturas, previsao, sqlite_sum, kpis = safe_load()


# ==============================================================================
# 3. SIDEBAR  (FIX 4 + 8)
# ==============================================================================

with st.sidebar:
    st.title("Rede Jazida")
    st.caption("Barragem de Castelo de Bode")
    st.divider()

    nome_utilizador = st.session_state.get("name") or st.session_state.get("username") or "Utilizador"
    st.write(f"👤 Olá, **{nome_utilizador}**")

    # Logout — FIX 4: limpar session_state após logout
    if st.button("🚪 Sair / Logout", type="secondary"):
        try:
            authenticator.logout(location="unrendered")
        except Exception:
            pass
        for _k in ["authentication_status", "name", "username"]:
            st.session_state[_k] = None
        st.rerun()

    st.divider()

    # Navegação — entrypoint dinâmico (funciona com qualquer nome de ficheiro)
    _entrypoint = Path(__file__).name
    st.page_link(_entrypoint,                              label="🏠 Painel")
    st.page_link("pages/2_📈_Histórico.py",               label="📊 Histórico")
    st.page_link("pages/3_🔮_Previsão.py",                label="🔮 Previsão ML")
    st.page_link("pages/4_⚙️_Configurações.py",           label="⚙️ Configurações")
    st.page_link("pages/5_📅_Calendário.py",              label="📅 Calendário")
    st.page_link("pages/6_📄_Relatório_PDF.py",           label="📄 Relatório PDF")


# ==============================================================================
# 4. CONTEÚDO PRINCIPAL
# ==============================================================================

st.title("🎣 Previsão de Pesca — Rede Jazida")

# ── KPIs de previsão ML  (FIX 3 + 6) ─────────────────────────────────────────
# calculate_kpis() v7.1 já normaliza os campos do JSON
score = float(kpis.get("score_previsto") or 0)
classe = str(kpis.get("classe_prevista") or "N/A")
color  = "red" if score < 20 else ("orange" if score < 50 else "green")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        create_kpi_card("Score Previsto", f"{int(score)}", "/100", color=color),
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        create_kpi_card("Classificacao", classe, "", color=color),
        unsafe_allow_html=True,
    )
with c3:
    tw_val = kpis.get("tw_prevista", "—")
    st.markdown(
        create_kpi_card("Tw (Agua)", f"{tw_val}", "C", color="purple"),
        unsafe_allow_html=True,
    )
with c4:
    vento_val = kpis.get("vento_previsto", "—")
    st.markdown(
        create_kpi_card("Vento", f"{vento_val}", "km/h", color="blue"),
        unsafe_allow_html=True,
    )

# Segunda linha de KPIs
k1, k2, k3, k4 = st.columns(4)
with k1:
    chuva_val = kpis.get("chuva_prevista", "—")
    st.markdown(
        create_kpi_card("Chuva", f"{chuva_val}", "mm", color="blue"),
        unsafe_allow_html=True,
    )
with k2:
    lua_fase = kpis.get("lua_fase", "—")
    lua_pct  = kpis.get("lua_pct", "—")
    st.markdown(
        create_kpi_card("Lua", f"{lua_fase}", f" ({lua_pct}%)", color="purple"),
        unsafe_allow_html=True,
    )
with k3:
    # FIX 6: conversão segura para int
    total_peixes = kpis.get("total_peixes", 0)
    try:
        total_peixes = int(total_peixes)
    except (TypeError, ValueError):
        total_peixes = 0
    st.markdown(
        create_kpi_card("Total Peixes", str(total_peixes), " un", color="green"),
        unsafe_allow_html=True,
    )
with k4:
    total_kg = kpis.get("total_kg", 0.0)
    try:
        total_kg = float(total_kg)
    except (TypeError, ValueError):
        total_kg = 0.0
    st.markdown(
        create_kpi_card("Total Peso", f"{total_kg:.1f}", " kg", color="green"),
        unsafe_allow_html=True,
    )

# ── KPIs do calendário de pesca  (FIX 7) ──────────────────────────────────────
n_dias    = kpis.get("n_dias_pesca", 0)
n_sessoes = kpis.get("n_sessoes", 0)
taxa      = kpis.get("taxa_sucesso", 0.0)

if n_dias > 0:
    st.divider()
    st.caption("Período de pesca activo")
    p1, p2, p3 = st.columns(3)
    p1.metric("Dias de pesca (total)", n_dias)
    p2.metric("Sessões com captura",   n_sessoes,
              delta=f"{n_dias - n_sessoes} sem captura")
    p3.metric("Taxa de sucesso",       f"{taxa:.1f}%")

st.divider()

# ── Gráfico de distribuição de scores  (FIX 5) ────────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Distribuicao Historica de Scores")
    if not df_capturas.empty and "sucesso_score" in df_capturas.columns:
        try:
            scores = pd.to_numeric(
                df_capturas["sucesso_score"].dropna(), errors='coerce'
            )
            if len(scores) > 0:
                fig_dist = plot_score_distribution_plotly(scores)
                st.plotly_chart(fig_dist, width="stretch")   # FIX 5
        except Exception as e:
            st.warning(f"Erro ao gerar grafico: {e}")
    else:
        st.info("Sem dados suficientes. Capture mais peixes!")

with col_right:
    st.subheader("Estado do Sistema")

    if config:
        st.info(f"**Versao**: {config.get('version', 'N/A')}")
        loc = config.get('location', {})
        st.info(f"**Local**: {loc.get('name', 'N/A')}")

    if sqlite_sum and sqlite_sum.get("n_registos", 0) > 0:
        st.success(f"SQLite: {sqlite_sum['n_registos']} registos")
    else:
        st.warning("SQLite: sem registos")

    # FIX 10: caminho absoluto
    if PKL_PATH.exists():
        st.success(
            f"Modelo: Activo ({PKL_PATH.stat().st_size / 1024:.1f} KB)"
        )
    else:
        st.error("Modelo: ficheiro .pkl nao encontrado")

    if previsao:
        data_prev = (previsao.get("data_alvo")
                     or previsao.get("data")
                     or "—")
        st.success(f"Ultima Previsao: {data_prev}")
    else:
        st.warning("Previsao: JSON nao encontrado")

st.caption(
    "Sistema de Previsao de Pesca v3.1 | Barragem de Castelo de Bode"
)

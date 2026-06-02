#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/3_Previsao.py v2.0
Correcções face ao original:
  - Lê chaves canónicas (score, tw, vento, lua_fase, lua_pct)
    via load_previsao_amanha() normalizado em data_loader v7.1
  - KPIs mostram valores reais em vez de --
  - sanitize_dataframe() mantida para compatibilidade PyArrow
  - use_container_width -> width=
"""
import streamlit as st

if not st.session_state.get("authentication_status"):
    st.warning("Acesso restrito. Sessao expirada ou nao autenticada.")
    st.page_link("streamlit_app.py", label="Ir para Login", icon="🔑")
    st.stop()

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.data_loader import load_config, load_previsao_amanha, get_feature_importance
from src.plots import create_kpi_card

st.set_page_config(page_title="Previsao ML", page_icon="🔮", layout="wide")


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Garante DataFrame compatível com PyArrow."""
    if df is None or df.empty:
        return df
    df_clean = df.copy()
    bad_cols = [c for c in df_clean.columns
                if c.lower() in ['valor', 'tipo', 'unnamed', 'type', 'value']]
    if bad_cols:
        df_clean = df_clean.drop(columns=bad_cols)
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            try:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            except Exception:
                df_clean[col] = (df_clean[col].astype(str)
                                 .fillna('')
                                 .replace(['nan', 'None', 'NaN'], ''))
    return df_clean


def _fmt(val, suffix="", default="—") -> str:
    """Formata um valor para exibição, com fallback seguro."""
    if val is None or val == "" or val == "—":
        return default
    try:
        f = float(val)
        return f"{f:.1f}{suffix}"
    except (TypeError, ValueError):
        return f"{val}{suffix}"


# ── Página principal ──────────────────────────────────────────────────────────

def main():
    st.title("🔮 Previsão ML para Amanhã")

    config   = load_config()
    previsao = load_previsao_amanha()   # já normalizado pelo data_loader v7.1

    if not previsao:
        st.error(
            "Sem previsão disponível. Execute o pipeline "
            "(`prever_amanha_v3_1.py`)."
        )
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    score  = float(previsao.get("score", 0))
    classe = str(previsao.get("classificacao", "N/A")).upper()
    color  = "green" if score >= 70 else ("orange" if score >= 40 else "red")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            create_kpi_card("Score", f"{score:.0f}", "/100", color=color),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            create_kpi_card("Classificacao", classe, "", color=color),
            unsafe_allow_html=True,
        )
    with c3:
        tw_val = previsao.get("tw")
        st.markdown(
            create_kpi_card("Tw (Agua)", _fmt(tw_val), "C", color="purple"),
            unsafe_allow_html=True,
        )
    with c4:
        vento_val = previsao.get("vento")
        st.markdown(
            create_kpi_card("Vento", _fmt(vento_val), "km/h", color="blue"),
            unsafe_allow_html=True,
        )

    # Segunda linha
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        chuva_val = previsao.get("chuva", 0.0)
        st.markdown(
            create_kpi_card("Chuva", _fmt(chuva_val), "mm", color="blue"),
            unsafe_allow_html=True,
        )
    with k2:
        lua_fase = previsao.get("lua_fase", "—") or "—"
        lua_pct  = previsao.get("lua_pct")
        lua_str  = f"{lua_fase} ({lua_pct:.0f}%)" if lua_pct is not None else lua_fase
        st.markdown(
            create_kpi_card("Lua", lua_str, "", color="purple"),
            unsafe_allow_html=True,
        )
    with k3:
        especie = previsao.get("especie", "—") or "—"
        st.markdown(
            create_kpi_card("Especie Alvo", especie, "", color="green"),
            unsafe_allow_html=True,
        )
    with k4:
        horario = previsao.get("horario", "—") or "—"
        st.markdown(
            create_kpi_card("Melhor Horario", horario, "", color="green"),
            unsafe_allow_html=True,
        )

    # Alertas (se existirem)
    alertas = previsao.get("alertas", [])
    if alertas:
        st.warning("⚠️ " + " | ".join(str(a) for a in alertas))
    else:
        st.success("Condicoes dentro dos parametros normais.")

    st.divider()

    col_main, col_meta = st.columns([2, 1])

    with col_main:
        # ── Feature Importance ────────────────────────────────────────────────
        st.subheader("O que influenciou esta previsao?")
        feat_data = get_feature_importance()

        if feat_data:
            features    = feat_data.get("feature_names", [])
            importances = feat_data.get("feature_importances", [])

            # Formato lista de dicts (v3.2)
            if importances and isinstance(importances[0], dict):
                features    = [d.get("feature", "") for d in importances]
                importances = [d.get("importance", 0) for d in importances]

            if features and importances and len(features) == len(importances):
                df_imp = pd.DataFrame({
                    'Feature':    features,
                    'Importance': importances,
                }).sort_values('Importance', ascending=True).tail(10)

                fig = px.bar(
                    df_imp, x='Importance', y='Feature', orientation='h',
                    title="Top Variaveis Mais Importantes",
                    labels={'Importance': 'Peso na Decisao', 'Feature': 'Variavel'},
                    color='Importance',
                    color_continuous_scale='Viridis',
                )
                st.plotly_chart(fig, width="stretch")
            else:
                st.warning("Metadados inconsistentes. Retreine o modelo.")
        else:
            st.warning("Metadados do modelo nao disponiveis.")

        # ── Tabela de detalhes ────────────────────────────────────────────────
        st.subheader("Detalhes da Previsao")
        data_prev = previsao.get("data", "N/A")
        lua_fase  = previsao.get("lua_fase", "—") or "—"
        lua_pct_v = previsao.get("lua_pct")
        lua_disp  = f"{lua_fase} ({lua_pct_v:.0f}%)" if lua_pct_v is not None else lua_fase

        details = {
            "Data":           data_prev,
            "Score":          f"{score:.1f} / 100",
            "Classificacao":  classe,
            "Melhor Horario": previsao.get("horario", "N/A"),
            "Especie Alvo":   previsao.get("especie", "N/A"),
            "Chuva Prevista": _fmt(previsao.get("chuva", 0), " mm"),
            "Tw (Agua)":      _fmt(previsao.get("tw"), "C"),
            "Vento Max":      _fmt(previsao.get("vento"), " km/h"),
            "Lua":            lua_disp,
        }
        df_details = pd.DataFrame(
            list(details.items()), columns=["Parametro", "Valor"]
        )
        df_details = sanitize_dataframe(df_details)
        st.table(df_details)

    with col_meta:
        st.subheader("Info do Modelo")
        if feat_data:
            metrics = feat_data.get("metrics", {})
            st.info(f"Modelo: {feat_data.get('model_type', 'N/A')}")
            st.info(f"Dados Treino: {metrics.get('n_samples', 0)} sessoes")
            r2_val = metrics.get('r2', 'N/A')
            st.info(f"R² (Validacao): {r2_val if r2_val != 0 else '0.0 (Baseline)'}")
        else:
            st.info("Execute o treino para ver metricas do modelo.")

        st.divider()
        st.markdown(
            "**Como funciona:**\n\n"
            "O score é gerado diariamente pelo pipeline às 18:50. "
            "O modelo usa:\n"
            "- Temperatura da Água (Tw) estimada\n"
            "- Vento e Chuva (Open-Meteo)\n"
            "- Fase Lunar\n"
            "- Histórico de Capturas\n\n"
            "_Use como referência complementar._"
        )


if __name__ == "__main__":
    main()

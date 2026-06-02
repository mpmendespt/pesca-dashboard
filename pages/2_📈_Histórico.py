#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/2_Historico.py v2.0
Adiciona gráfico de Score Real vs Score Previsto sobrepostos.
"""
import streamlit as st

if not st.session_state.get("authentication_status"):
    st.warning("Acesso restrito. Sessao expirada ou nao autenticada.")
    st.page_link("streamlit_app.py", label="Ir para Login", icon="🔑")
    st.stop()

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
from src.data_loader import load_capturas, load_config, load_previsao_7dias

st.set_page_config(page_title="Historico", page_icon="📈", layout="wide")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _score_cor(score: float) -> str:
    if score >= 70: return "#28A745"
    if score >= 50: return "#FD7E14"
    if score >= 30: return "#FFC107"
    return "#DC3545"


def _score_label(score: float) -> str:
    if score >= 70: return "EXCELENTE"
    if score >= 50: return "BOM"
    if score >= 30: return "MODERADO"
    return "FRACO"


def build_score_timeline(df_capturas: pd.DataFrame, previsao_7d: dict) -> go.Figure:
    """
    Gráfico combinado:
      - Barras azuis  : score real calculado das capturas (histórico)
      - Linha laranja : score previsto pelo modelo ML (7 dias futuros)
    """
    fig = go.Figure()

    # ── Score real (histórico) ────────────────────────────────────────────────
    if not df_capturas.empty and "sucesso_score" in df_capturas.columns:
        df_hist = (
            df_capturas
            .groupby(df_capturas["Timestamp"].dt.date)
            .agg(score_real=("sucesso_score", "mean"))
            .reset_index()
            .rename(columns={"Timestamp": "data"})
            .sort_values("data")
        )
        df_hist["score_real"] = df_hist["score_real"].clip(0, 100)

        fig.add_trace(go.Bar(
            x=df_hist["data"],
            y=df_hist["score_real"],
            name="Score Real (capturas)",
            marker_color=[_score_cor(s) for s in df_hist["score_real"]],
            opacity=0.80,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Score Real: <b>%{y:.1f}</b><br>"
                "<extra></extra>"
            ),
        ))

    # ── Score previsto (7 dias futuros) ───────────────────────────────────────
    if previsao_7d and "dias" in previsao_7d:
        dias = previsao_7d["dias"]
        datas_prev  = [d["data"] for d in dias]
        scores_prev = [d["score"] for d in dias]
        fases_prev  = [d["lua_fase"] for d in dias]

        fig.add_trace(go.Scatter(
            x=datas_prev,
            y=scores_prev,
            mode="lines+markers",
            name="Score Previsto (ML)",
            line=dict(color="#E07B39", width=2.5, dash="dot"),
            marker=dict(size=9, color="#E07B39", symbol="diamond"),
            customdata=list(zip(fases_prev, scores_prev)),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Score Previsto: <b>%{customdata[1]:.1f}</b><br>"
                "Lua: %{customdata[0]}<br>"
                "<extra></extra>"
            ),
        ))

    # Linha de referência "MODERADO"
    fig.add_hline(
        y=30, line_dash="dash", line_color="gray", opacity=0.5,
        annotation_text="Limiar MODERADO (30)",
        annotation_position="top left",
        annotation_font_size=10,
    )

    fig.update_layout(
        title="Score de Pesca: Histórico Real vs Previsto ML",
        xaxis_title="Data",
        yaxis_title="Score (0–100)",
        yaxis=dict(range=[0, 105]),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#F0F0F0")
    fig.update_yaxes(showgrid=True, gridcolor="#F0F0F0")
    return fig


# ── Página principal ──────────────────────────────────────────────────────────

def main():
    st.title("📈 Histórico de Capturas e Condições")

    df_capturas  = load_capturas()
    config       = load_config()
    previsao_7d  = load_previsao_7dias()

    if df_capturas.empty:
        st.warning("Sem dados de capturas disponíveis. Verifique Capturas.csv.")
        return

    # ── Filtro lateral ────────────────────────────────────────────────────────
    st.sidebar.header("Filtros")
    species_list     = [c.replace("_Qtd", "") for c in df_capturas.columns if c.endswith("_Qtd")]
    selected_species = st.sidebar.multiselect(
        "Espécies", species_list,
        default=species_list[:5] if len(species_list) > 5 else species_list
    )

    # ── Score Real vs Previsto ────────────────────────────────────────────────
    st.subheader("📊 Score de Pesca: Histórico Real vs Previsto ML")

    if previsao_7d is None:
        st.info("previsao_7dias.json não encontrado. Execute o pipeline para gerar previsões futuras.")

    fig_score = build_score_timeline(df_capturas, previsao_7d)
    st.plotly_chart(fig_score, width='stretch')

    # Métricas rápidas abaixo do gráfico
    if not df_capturas.empty and "sucesso_score" in df_capturas.columns:
        scores_hist = df_capturas["sucesso_score"].dropna()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score Médio (histórico)", f"{scores_hist.mean():.1f}")
        c2.metric("Score Máximo",            f"{scores_hist.max():.1f}")
        c3.metric("Score Mínimo",            f"{scores_hist.min():.1f}")
        if previsao_7d:
            melhor_dia = max(previsao_7d["dias"], key=lambda d: d["score"])
            c4.metric("Melhor dia (7d)",
                      melhor_dia["data"],
                      delta=f"{melhor_dia['score']:.0f} pts")

    st.divider()

    # ── Evolução temporal de capturas ─────────────────────────────────────────
    st.subheader("📅 Evolução de Capturas (Quantidade)")
    if selected_species:
        qtd_cols  = [f"{s}_Qtd" for s in selected_species if f"{s}_Qtd" in df_capturas.columns]
        df_plot   = df_capturas[["Timestamp"] + qtd_cols].copy()
        df_plot["Data"] = df_plot["Timestamp"].dt.date
        df_plot = df_plot.drop("Timestamp", axis=1).groupby("Data").sum().reset_index()
        df_melt = df_plot.melt(id_vars="Data", value_vars=qtd_cols, var_name="Especie", value_name="Qtd")
        df_melt["Especie"] = df_melt["Especie"].str.replace("_Qtd", "")
        df_melt = df_melt[df_melt["Qtd"] > 0]
        if not df_melt.empty:
            fig = px.bar(
                df_melt, x="Data", y="Qtd", color="Especie",
                title="Capturas Diárias por Espécie",
                labels={"Qtd": "Quantidade", "Data": "Data"},
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(xaxis_type="category", height=320)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Sem dados para os filtros seleccionados.")

    # ── Peso total por espécie ────────────────────────────────────────────────
    st.subheader("⚖️ Peso Total Acumulado (Kg)")
    kg_cols = [f"{s}_Kg" for s in selected_species if f"{s}_Kg" in df_capturas.columns]
    if kg_cols:
        totals = df_capturas[kg_cols].sum()
        totals = totals[totals > 0]
        if not totals.empty:
            totals.index = totals.index.str.replace("_Kg", "")
            fig_pie = px.pie(
                values=totals.values, names=totals.index,
                title="Distribuição de Peso por Espécie",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_pie.update_layout(height=340)
            st.plotly_chart(fig_pie, width='stretch')

    # ── Sucesso por fase lunar ────────────────────────────────────────────────
    st.subheader("🌙 Sucesso por Fase Lunar")
    if "sucesso_score" in df_capturas.columns:
        if "Fase_Lua" not in df_capturas.columns:
            df_capturas["Dia"] = pd.to_datetime(df_capturas["Timestamp"]).dt.day
            def dia_para_fase(dia):
                if   dia <  7: return "Nova"
                elif dia < 14: return "Crescente"
                elif dia < 21: return "Cheia"
                else:          return "Minguante"
            df_capturas["Fase_Lua"] = df_capturas["Dia"].apply(dia_para_fase)
            df_capturas = df_capturas.drop("Dia", axis=1)

        df_lua = df_capturas[["Fase_Lua", "sucesso_score"]].dropna()
        if not df_lua.empty:
            fig_box = px.box(
                df_lua, x="Fase_Lua", y="sucesso_score",
                title="Distribuição do Score por Fase Lunar",
                points="all", color="Fase_Lua",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_box.update_layout(height=340, showlegend=False)
            st.plotly_chart(fig_box, width='stretch')

    # ── Tabela de dados recentes ──────────────────────────────────────────────
    with st.expander("📋 Ver Tabela de Dados Recentes"):
        display_cols  = ["Timestamp", "Total_Qtd", "Total_Kg", "sucesso_score"]
        available_cols = [c for c in display_cols if c in df_capturas.columns]
        df_display = (
            df_capturas[available_cols]
            .sort_values("Timestamp", ascending=False)
            .head(20)
        )
        st.dataframe(df_display, width='stretch')

    # ── Estatísticas resumo ───────────────────────────────────────────────────
    with st.expander("📊 Estatísticas Resumo"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Sessões", len(df_capturas))
        c2.metric("Total Peixes",  f"{int(df_capturas['Total_Qtd'].sum()):,}" if "Total_Qtd" in df_capturas.columns else "—")
        c3.metric("Total Peso",    f"{df_capturas['Total_Kg'].sum():.1f} kg"  if "Total_Kg"  in df_capturas.columns else "—")
        c4.metric("Score Médio",   f"{df_capturas['sucesso_score'].mean():.1f}" if "sucesso_score" in df_capturas.columns else "—")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/5_Calendario.py
Calendário mensal: dias passados com score real, dias futuros com score previsto.
Cores: verde (>=70), laranja (>=50), amarelo (>=30), vermelho (<30), cinzento (sem dados).
"""
import streamlit as st

if not st.session_state.get("authentication_status"):
    st.warning("Acesso restrito. Sessao expirada ou nao autenticada.")
    st.page_link("streamlit_app.py", label="Ir para Login", icon="🔑")
    st.stop()

import calendar
import pandas as pd
from datetime import datetime, date
from src.data_loader import load_capturas, load_previsao_7dias

st.set_page_config(page_title="Calendário", page_icon="📅", layout="wide")


# ── Paleta de cores ───────────────────────────────────────────────────────────
CORES = {
    "excelente": "#1a7a1a",   # verde escuro
    "bom":       "#e07b00",   # laranja
    "moderado":  "#c8a200",   # amarelo escuro
    "fraco":     "#c0392b",   # vermelho
    "sem_dados": "#bdbdbd",   # cinzento
    "futuro_bg": "#e8f4fd",   # azul claro (fundo dia futuro)
    "hoje_bg":   "#fff3cd",   # amarelo claro (hoje)
    "header":    "#1a3a5c",   # azul escuro (cabeçalho)
}

DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _cor_score(score: float) -> str:
    if score >= 70: return CORES["excelente"]
    if score >= 50: return CORES["bom"]
    if score >= 30: return CORES["moderado"]
    return CORES["fraco"]


def _label_score(score: float) -> str:
    if score >= 70: return "EXCELENTE"
    if score >= 50: return "BOM"
    if score >= 30: return "MODERADO"
    return "FRACO"


def _fase_emoji(fase: str) -> str:
    mapa = {
        "Nova": "🌑", "Crescente I": "🌒", "Q. Crescente": "🌓",
        "Crescente Fim": "🌔", "Cheia": "🌕",
        "Minguante I": "🌖", "Q. Minguante": "🌗", "Minguante Fim": "🌘",
    }
    return mapa.get(fase, "")


def build_dia_data(
    df_capturas: pd.DataFrame,
    previsao_7d: dict,
    ano: int,
    mes: int,
) -> dict:
    """
    Devolve um dict {date: {...}} com os dados de cada dia do mês.
    Origem: 'real' (capturas) ou 'previsto' (ML) ou None.
    """
    dados = {}

    # ── Dias com capturas reais ───────────────────────────────────────────────
    if not df_capturas.empty and "sucesso_score" in df_capturas.columns:
        df_mes = df_capturas[
            (df_capturas["Timestamp"].dt.year  == ano) &
            (df_capturas["Timestamp"].dt.month == mes)
        ].copy()
        if not df_mes.empty:
            df_agg = (
                df_mes
                .groupby(df_mes["Timestamp"].dt.date)
                .agg(
                    score=("sucesso_score", "mean"),
                    total_qtd=("Total_Qtd", "sum"),
                    total_kg=("Total_Kg",  "sum"),
                )
                .reset_index()
                .rename(columns={"Timestamp": "data"})
            )
            for _, row in df_agg.iterrows():
                dados[row["data"]] = {
                    "origem":    "real",
                    "score":     round(float(row["score"]), 1),
                    "total_qtd": int(row["total_qtd"]),
                    "total_kg":  round(float(row["total_kg"]), 2),
                    "lua_fase":  None,
                    "lua_pct":   None,
                    "alertas":   [],
                }

    # ── Dias com previsão ML ──────────────────────────────────────────────────
    if previsao_7d and "dias" in previsao_7d:
        for d in previsao_7d["dias"]:
            dt = datetime.strptime(d["data"], "%Y-%m-%d").date()
            if dt.year == ano and dt.month == mes:
                # Previsão não sobrescreve dados reais
                if dt not in dados:
                    dados[dt] = {
                        "origem":    "previsto",
                        "score":     d["score"],
                        "total_qtd": None,
                        "total_kg":  None,
                        "lua_fase":  d.get("lua_fase"),
                        "lua_pct":   d.get("lua_pct"),
                        "alertas":   d.get("alertas", []),
                    }
    return dados


def render_legenda():
    st.markdown(
        """
        <div style="display:flex; gap:18px; flex-wrap:wrap; margin-bottom:10px; font-size:0.85em;">
            <span>
                <span style="background:#1a7a1a;color:white;padding:2px 8px;border-radius:4px;">
                    ≥70 EXCELENTE
                </span>
            </span>
            <span>
                <span style="background:#e07b00;color:white;padding:2px 8px;border-radius:4px;">
                    ≥50 BOM
                </span>
            </span>
            <span>
                <span style="background:#c8a200;color:white;padding:2px 8px;border-radius:4px;">
                    ≥30 MODERADO
                </span>
            </span>
            <span>
                <span style="background:#c0392b;color:white;padding:2px 8px;border-radius:4px;">
                    &lt;30 FRACO
                </span>
            </span>
            <span>
                <span style="background:#bdbdbd;color:white;padding:2px 8px;border-radius:4px;">
                    Sem dados
                </span>
            </span>
            &nbsp;|&nbsp;
            <span style="border:2px dashed #2e86ab;padding:2px 8px;border-radius:4px;">
                Previsão ML
            </span>
            <span style="border:2px solid #28a745;padding:2px 8px;border-radius:4px;">
                Dado Real
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_calendario(ano: int, mes: int, dados: dict):
    """Renderiza o calendário completo do mês em HTML."""
    hoje = date.today()
    cal  = calendar.monthcalendar(ano, mes)

    # Cabeçalho dos dias da semana
    header_cells = "".join(
        f'<th style="text-align:center;padding:6px 4px;'
        f'background:{CORES["header"]};color:white;font-size:0.85em;">'
        f'{d}</th>'
        for d in DIAS_SEMANA_PT
    )

    linhas = []
    for semana in cal:
        celulas = []
        for dia_num in semana:
            if dia_num == 0:
                celulas.append('<td style="background:#f8f8f8;border:1px solid #e0e0e0;"></td>')
                continue

            dt = date(ano, mes, dia_num)
            info = dados.get(dt)
            is_hoje   = (dt == hoje)
            is_futuro = (dt > hoje)

            # ── Estilos base da célula ────────────────────────────────────────
            if is_hoje:
                cell_bg     = CORES["hoje_bg"]
                border_style = f"border:3px solid {CORES['header']};"
            elif is_futuro:
                cell_bg      = CORES["futuro_bg"]
                border_style = "border:1px dashed #aac8e0;"
            else:
                cell_bg      = "white"
                border_style = "border:1px solid #e0e0e0;"

            cell_style = (
                f"background:{cell_bg};{border_style}"
                f"padding:6px 4px;vertical-align:top;"
                f"min-width:90px;min-height:70px;position:relative;"
            )

            # ── Número do dia ─────────────────────────────────────────────────
            dia_color  = CORES["header"] if is_hoje else "#333"
            dia_weight = "bold" if is_hoje else "normal"
            conteudo   = (
                f'<div style="font-size:0.9em;font-weight:{dia_weight};'
                f'color:{dia_color};margin-bottom:3px;">{dia_num}</div>'
            )

            # ── Badge de score ────────────────────────────────────────────────
            if info:
                score  = info["score"]
                origem = info["origem"]
                cor    = _cor_score(score)
                label  = _label_score(score)
                border_badge = (
                    "border:2px dashed white;" if origem == "previsto"
                    else "border:2px solid white;"
                )
                conteudo += (
                    f'<div style="background:{cor};color:white;'
                    f'border-radius:4px;padding:2px 4px;'
                    f'font-size:0.75em;font-weight:bold;{border_badge}'
                    f'margin-bottom:2px;text-align:center;">'
                    f'{score:.0f} {label}</div>'
                )

                # Capturas (se reais)
                if origem == "real" and info["total_qtd"] is not None:
                    conteudo += (
                        f'<div style="font-size:0.7em;color:#555;text-align:center;">'
                        f'🐟 {info["total_qtd"]} un / {info["total_kg"]:.1f}kg</div>'
                    )

                # Fase lunar
                if info["lua_fase"]:
                    emoji = _fase_emoji(info["lua_fase"])
                    pct   = f" {info['lua_pct']:.0f}%" if info["lua_pct"] is not None else ""
                    conteudo += (
                        f'<div style="font-size:0.7em;color:#666;text-align:center;">'
                        f'{emoji}{pct}</div>'
                    )

                # Alertas
                if info["alertas"]:
                    conteudo += (
                        '<div style="font-size:0.65em;color:#c0392b;text-align:center;">⚠️</div>'
                    )

            else:
                # Sem dados
                cor_sem = "#9e9e9e" if not is_futuro else "#b0c4de"
                conteudo += (
                    f'<div style="font-size:0.7em;color:{cor_sem};'
                    f'text-align:center;margin-top:6px;">—</div>'
                )

            celulas.append(f'<td style="{cell_style}">{conteudo}</td>')
        linhas.append("<tr>" + "".join(celulas) + "</tr>")

    tabela = f"""
    <table style="border-collapse:collapse;width:100%;table-layout:fixed;">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{"".join(linhas)}</tbody>
    </table>
    """
    st.markdown(tabela, unsafe_allow_html=True)


def render_previsao_7d_cards(previsao_7d: dict, mes: int, ano: int):
    """Cards horizontais com os 7 dias previstos (filtrados pelo mês actual)."""
    if not previsao_7d or "dias" not in previsao_7d:
        return
    dias_mes = [
        d for d in previsao_7d["dias"]
        if datetime.strptime(d["data"], "%Y-%m-%d").month == mes
        and datetime.strptime(d["data"], "%Y-%m-%d").year  == ano
    ]
    if not dias_mes:
        return

    st.markdown("#### Previsão dos próximos dias (ML)")
    cols = st.columns(min(len(dias_mes), 7))
    for col, d in zip(cols, dias_mes):
        cor    = _cor_score(d["score"])
        emoji  = _fase_emoji(d["lua_fase"]) if d.get("lua_fase") else ""
        alerta = "⚠️" if d.get("alertas") else "✅"
        dt_obj = datetime.strptime(d["data"], "%Y-%m-%d")
        dia_pt = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"][dt_obj.weekday()]

        with col:
            st.markdown(
                f"""
                <div style="background:{cor};color:white;border-radius:8px;
                            padding:10px 6px;text-align:center;
                            border:2px dashed rgba(255,255,255,0.6);">
                    <div style="font-size:0.75em;opacity:0.9;">{dia_pt}</div>
                    <div style="font-size:1em;font-weight:bold;">
                        {dt_obj.day}/{dt_obj.month}
                    </div>
                    <div style="font-size:1.3em;font-weight:bold;">
                        {d['score']:.0f}
                    </div>
                    <div style="font-size:0.7em;">{_label_score(d['score'])}</div>
                    <div style="font-size:0.85em;">{emoji}</div>
                    <div style="font-size:0.85em;">{alerta}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── Página principal ──────────────────────────────────────────────────────────

def main():
    st.title("📅 Calendário de Pesca")

    df_capturas = load_capturas()
    previsao_7d = load_previsao_7dias()

    # Mês/ano actuais (fixo — mês atual conforme especificado)
    hoje = date.today()
    ano  = hoje.year
    mes  = hoje.month
    nome_mes = {
        1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",
        5:"Maio",6:"Junho",7:"Julho",8:"Agosto",
        9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
    }[mes]

    st.markdown(
        f"<h3 style='color:{CORES['header']};margin-bottom:4px;'>"
        f"{nome_mes} {ano}</h3>",
        unsafe_allow_html=True,
    )
    render_legenda()

    # Dados do mês
    dados = build_dia_data(df_capturas, previsao_7d, ano, mes)

    # Calendário
    render_calendario(ano, mes, dados)

    st.divider()

    # Cards dos 7 dias previstos
    render_previsao_7d_cards(previsao_7d, mes, ano)

    # Resumo do mês
    st.divider()
    st.markdown("#### Resumo do mês")

    dias_reais    = [v for v in dados.values() if v["origem"] == "real"]
    dias_previstos = [v for v in dados.values() if v["origem"] == "previsto"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sessões registadas", len(dias_reais))
    c2.metric(
        "Score médio (real)",
        f"{sum(d['score'] for d in dias_reais)/len(dias_reais):.1f}" if dias_reais else "—"
    )
    c3.metric(
        "Peixes capturados",
        sum(d["total_qtd"] for d in dias_reais if d["total_qtd"]) if dias_reais else "—"
    )
    c4.metric(
        "Melhor dia previsto",
        max(dias_previstos, key=lambda d: d["score"])["score"] if dias_previstos else "—",
        delta="score ML" if dias_previstos else None,
    )


if __name__ == "__main__":
    main()

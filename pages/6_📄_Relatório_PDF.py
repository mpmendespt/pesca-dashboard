#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/6_Relatorio_PDF.py
Download do último PDF gerado pelo pipeline local (previsao_pesca_v2_10.py).
Mostra metadados do ficheiro e botão de download.
"""
import streamlit as st

if not st.session_state.get("authentication_status"):
    st.warning("Acesso restrito. Sessao expirada ou nao autenticada.")
    st.page_link("streamlit_app.py", label="Ir para Login", icon="🔑")
    st.stop()

from pathlib import Path
from datetime import datetime
from src.data_loader import load_ultimo_pdf

st.set_page_config(page_title="Relatório PDF", page_icon="📄", layout="wide")


def _formatar_tamanho(n_bytes: int) -> str:
    if n_bytes < 1024:         return f"{n_bytes} B"
    if n_bytes < 1024 ** 2:   return f"{n_bytes/1024:.1f} KB"
    return f"{n_bytes/1024**2:.1f} MB"


def _formatar_data(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


def main():
    st.title("📄 Relatório PDF")
    st.caption(
        "O PDF é gerado automaticamente pelo pipeline local (`previsao_pesca_v2_10.py`) "
        "e sincronizado para esta pasta. Clique em **Download** para guardar."
    )

    pdf_path = load_ultimo_pdf()

    if pdf_path is None:
        st.warning(
            "Nenhum PDF encontrado em `data/` ou na raiz do projecto.\n\n"
            "Para gerar um PDF, execute o pipeline completo:\n"
            "```\npython pipeline_orquestrador_v3_1.py\n```\n"
            "ou apenas:\n"
            "```\npython previsao_pesca_v2_10.py\n```"
        )
        return

    stat = pdf_path.stat()

    # ── Metadados ─────────────────────────────────────────────────────────────
    st.markdown("#### Último relatório disponível")

    c1, c2, c3 = st.columns(3)
    c1.metric("Ficheiro",  pdf_path.name)
    c2.metric("Tamanho",   _formatar_tamanho(stat.st_size))
    c3.metric("Gerado em", _formatar_data(stat.st_mtime))

    st.divider()

    # ── Botão de download ─────────────────────────────────────────────────────
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    st.download_button(
        label="⬇️  Download do Relatório PDF",
        data=pdf_bytes,
        file_name=pdf_path.name,
        mime="application/pdf",
        type="primary",
        key="dl_principal",
    )

    st.info(
        "**Conteúdo do PDF (4 páginas):**\n"
        "- Pág. 1 — Previsão meteorológica, Wind Barbs, Rosa dos Ventos, Rating Lunar\n"
        "- Pág. 2 — Recomendações técnicas por dia, espécie dominante, histórico\n"
        "- Pág. 3 — Histórico de capturas, correlação Lua × peixes\n"
        "- Pág. 4 — Estatísticas mensais por espécie (gráfico + tabela resumo)"
    )

    st.divider()

    # ── Outros PDFs disponíveis (deduplicados por nome) ─────────────────────
    base_dir = Path(__file__).resolve().parent.parent
    _candidatos = (
        list((base_dir / "data").glob("Previsao_Pesca_*.pdf"))
        + list(base_dir.glob("Previsao_Pesca_*.pdf"))
    )
    _vistos: dict = {}
    for _p in _candidatos:
        if _p.name not in _vistos or _p.stat().st_mtime > _vistos[_p.name].stat().st_mtime:
            _vistos[_p.name] = _p
    todos_pdfs = sorted(_vistos.values(), key=lambda p: p.stat().st_mtime, reverse=True)

    if len(todos_pdfs) > 1:
        st.markdown("#### Relatórios anteriores")
        for idx, p in enumerate(todos_pdfs[1:6], start=1):
            s = p.stat()
            col_a, col_b, col_c = st.columns([3, 1, 1])
            col_a.markdown(f"`{p.name}`")
            col_b.markdown(_formatar_tamanho(s.st_size))
            col_c.markdown(_formatar_data(s.st_mtime))

            with open(p, "rb") as f:
                st.download_button(
                    label=f"⬇️  {p.name}",
                    data=f.read(),
                    file_name=p.name,
                    mime="application/pdf",
                    key=f"dl_anterior_{idx}",
                )


if __name__ == "__main__":
    main()

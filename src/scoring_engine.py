#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src/scoring_engine.py v2.0
Motor de cálculo de Score de Sucesso ponderado por espécie.

Novidades v2.0:
  - Contexto do calendário de pesca: dias sem interrupção desde start_date
  - calculate_fishing_score() aceita parâmetro cfg opcional
  - calculate_session_context() devolve métricas relativas ao período de pesca
  - Pesos de espécie ajustados e documentados
"""
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path

# Pesos de dificuldade/valor por espécie
# Base: Savel=1.5 (difícil, migratório)
# Carpa=0.5 (mais abundante, menor dificuldade técnica)
SPECIES_WEIGHTS = {
    'Savel':   1.5,   # Migratório, difícil de capturar em rede jazida
    'Truta':   1.4,   # Exigente em qualidade de água e temperatura
    'Achiga':  1.3,   # Black Bass, predador activo, agressivo
    'Lucio':   1.2,   # Pike, forte, agressivo
    'Savelha': 1.1,   # Parente do Savel, menor porte
    'Pimpao':  0.8,   # Pimpão, abundante
    'Carpa':   0.5,   # Carpa, mais fácil, maior peso médio
}

# Score máximo teórico por sessão (usado para normalização)
_SCORE_MAX = 100.0


def calculate_fishing_score(df_capturas: pd.DataFrame) -> pd.Series:
    """
    Calcula o score ponderado por sessão (0-100).

    Fórmula:
      Score = clip(Sum(Qtd_esp * peso_esp * 15) + Sum(Kg_esp * peso_esp * 5), 0, 100)

    Os factores 15 e 5 foram calibrados para que:
      - 1 Lucio de 1kg ≈ 20 pontos
      - 3 Saveis totalizando 2kg ≈ 77.5 pontos (sessão muito boa)
    """
    if df_capturas.empty:
        return pd.Series(dtype=float)

    df = df_capturas.copy()
    score = np.zeros(len(df))

    # Contribuição por Quantidade
    for col in [c for c in df.columns if c.endswith('_Qtd') and c != 'Total_Qtd']:
        especie = col.replace('_Qtd', '')
        peso    = SPECIES_WEIGHTS.get(especie, 0.5)
        score  += pd.to_numeric(df[col], errors='coerce').fillna(0) * peso * 15

    # Contribuição por Peso (bónus para peixes grandes)
    for col in [c for c in df.columns if c.endswith('_Kg') and c != 'Total_Kg']:
        especie = col.replace('_Kg', '')
        peso    = SPECIES_WEIGHTS.get(especie, 0.5)
        score  += pd.to_numeric(df[col], errors='coerce').fillna(0) * peso * 5

    return pd.Series(np.clip(score, 0, _SCORE_MAX), index=df.index)


def calculate_session_context(
    df_capturas: pd.DataFrame,
    cfg: dict = None,
) -> dict:
    """
    Devolve métricas de contexto do período de pesca:
      - n_dias_pesca      : total de dias válidos desde start_date
      - n_dias_com_captura: dias em que houve pelo menos 1 peixe
      - n_dias_sem_captura: dias de pesca sem registo de capturas
      - taxa_sucesso_pct  : % de dias com captura sobre total de dias de pesca
      - score_medio       : média dos scores das sessões com captura
      - melhor_especie    : espécie com maior peso total capturado
      - dias_interrupcao  : número de dias de interrupção configurados

    Usa fishing_calendar_days() do data_loader para garantir
    consistência com a lógica central de calendário.
    """
    # Import local para evitar circularidade
    from src.data_loader import fishing_calendar_days, load_config

    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = {}

    dias_validos   = fishing_calendar_days(cfg)
    n_dias_pesca   = len(dias_validos)
    # interruptions ja foi expandido para set de dates pelo config_loader
    _raw_int     = cfg.get("fishing_calendar", {}).get("interruptions", [])
    interrupcoes = len(_raw_int) if isinstance(_raw_int, set) else len(_raw_int)

    if df_capturas.empty or 'Data' not in df_capturas.columns:
        return {
            "n_dias_pesca":       n_dias_pesca,
            "n_dias_com_captura": 0,
            "n_dias_sem_captura": n_dias_pesca,
            "taxa_sucesso_pct":   0.0,
            "score_medio":        0.0,
            "melhor_especie":     None,
            "dias_interrupcao":   interrupcoes,
        }

    # Dias com capturas reais
    datas_captura = set(
        d if isinstance(d, date) else pd.Timestamp(d).date()
        for d in df_capturas['Data']
    )
    dias_validos_set   = set(dias_validos)
    n_dias_com_captura = len(datas_captura & dias_validos_set)
    n_dias_sem_captura = max(0, n_dias_pesca - n_dias_com_captura)
    taxa               = round(n_dias_com_captura / n_dias_pesca * 100, 1) if n_dias_pesca > 0 else 0.0

    # Score médio das sessões
    score_medio = 0.0
    if 'sucesso_score' in df_capturas.columns:
        scores = pd.to_numeric(df_capturas['sucesso_score'], errors='coerce').dropna()
        score_medio = round(float(scores.mean()), 1) if not scores.empty else 0.0

    # Espécie dominante (por kg)
    melhor_especie = None
    kg_cols = [c for c in df_capturas.columns
               if c.endswith('_Kg') and c != 'Total_Kg' and df_capturas[c].sum() > 0]
    if kg_cols:
        totais = {c.replace('_Kg', ''): df_capturas[c].sum() for c in kg_cols}
        melhor_especie = max(totais, key=totais.get)

    return {
        "n_dias_pesca":       n_dias_pesca,
        "n_dias_com_captura": n_dias_com_captura,
        "n_dias_sem_captura": n_dias_sem_captura,
        "taxa_sucesso_pct":   taxa,
        "score_medio":        score_medio,
        "melhor_especie":     melhor_especie,
        "dias_interrupcao":   interrupcoes,
    }


if __name__ == "__main__":
    print("Motor de Scoring v2.0 inicializado.")
    print(f"Especies conhecidas: {list(SPECIES_WEIGHTS.keys())}")

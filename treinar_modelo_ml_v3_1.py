#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TREINO ML v3.1 — Pipeline Corrigido
=====================================
CORREÇÕES desta versão:

  [SCORE]  sucesso_score calculado a partir do Capturas.csv real.
           Anteriormente: coluna capturas.sucesso_score estava sempre NULL
           → fillna(0.0) fazia o modelo aprender que tudo vale 0
           → output fixo de ~1.3/100 em qualquer condição.

           Agora: score misto ponderado (70% peso / 30% quantidade),
           normalizado para 0-100 com base no máximo histórico.
           Fórmula: score = (0.7 × Kg/max_Kg + 0.3 × Qtd/max_Qtd) × 100
           Dias com registo no CSV mas zero capturas → score = 0 (legítimo).
           Dias sem registo (monitorização) → score = 0 via LEFT JOIN.
           Dias de interrupção → excluídos pelo filtro do config.

  [PKL]    Parâmetros de normalização guardados no .pkl junto com o modelo:
           'norm_params': {'max_kg', 'max_qtd', 'data_calibracao'}
           Garante que retreinos futuros com novos dados não invalidam
           scores históricos (a escala é re-calibrada a cada treino).

  [KFOLD]  Validação cruzada KFold automática quando n >= 10.
           Abaixo de 10 registos usa treino completo (fase actual de
           arranque) mas emite aviso explícito sobre memorização.
"""

import os
import sqlite3
import logging
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import KFold, cross_val_score
from config_loader import CONFIG

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

CAT_COLS = ["estacao", "dia_semana", "fase_lua"]

# Limiar para ativar KFold — abaixo usa treino completo com aviso
KFOLD_MIN_N  = 10
KFOLD_SPLITS = 3   # aumentar para 5 quando n >= 20


# ==============================================================================
# MÓDULO 1: CALCULAR sucesso_score A PARTIR DO Capturas.csv
# ==============================================================================

def calcular_scores_csv(capturas_csv: str) -> "tuple[pd.DataFrame, dict]":
    """
    Lê o Capturas.csv e devolve um DataFrame com colunas:
      data_str (YYYY-MM-DD), sucesso_score (0-100)

    Fórmula (mista 70/30):
      score = (0.7 × Kg/max_Kg + 0.3 × Qtd/max_Qtd) × 100

    Também devolve norm_params para guardar no .pkl.
    Dias com registo mas zero capturas → score = 0.0 (sessão registada = tentativa).
    """
    if not os.path.exists(capturas_csv):
        logger.warning(f"[SCORE] {capturas_csv} não encontrado — scores permanecem 0.")
        return pd.DataFrame(columns=["data_str", "sucesso_score"]), {}

    df = pd.read_csv(capturas_csv, parse_dates=["Timestamp"])
    for c in df.columns:
        if c != "Timestamp":
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "."), errors="coerce"
            ).fillna(0.0)

    cols_kg  = [c for c in df.columns if c.endswith("_Kg")]
    cols_qtd = [c for c in df.columns if c.endswith("_Qtd")]
    df["Total_Kg"]  = df[cols_kg].sum(axis=1).clip(lower=0)
    df["Total_Qtd"] = df[cols_qtd].sum(axis=1).clip(lower=0)

    # Parâmetros de normalização (guardados no pkl para auditoria)
    max_kg  = float(df["Total_Kg"].max())
    max_qtd = float(df["Total_Qtd"].max())
    norm_params = {
        "max_kg":           max_kg,
        "max_qtd":          max_qtd,
        "n_sessoes":        int(len(df)),
        "data_calibracao":  datetime.now().strftime("%Y-%m-%d"),
    }

    if max_kg == 0:
        logger.warning("[SCORE] max_kg=0 — todas as sessões têm 0 kg. Scores serão 0.")
        df["sucesso_score"] = 0.0
    else:
        kg_norm  = df["Total_Kg"]  / max_kg
        qtd_norm = (df["Total_Qtd"] / max_qtd) if max_qtd > 0 else 0.0
        df["sucesso_score"] = ((0.7 * kg_norm + 0.3 * qtd_norm) * 100).round(1)

    df["data_str"] = df["Timestamp"].dt.strftime("%Y-%m-%d")

    logger.info(
        f"[SCORE] {len(df)} sessões | max_kg={max_kg:.2f} | max_qtd={max_qtd:.0f} | "
        f"score_min={df['sucesso_score'].min():.1f} | score_max={df['sucesso_score'].max():.1f}"
    )
    return df[["data_str", "sucesso_score"]], norm_params


# ==============================================================================
# MÓDULO 2: TREINO
# ==============================================================================

def treinar():
    logger.info("🚀 Pipeline ML v3.1 | Ignorando dias de interrupção...")

    # ── 1. Carregar dados do SQLite ───────────────────────────────────────────
    conn = sqlite3.connect(CONFIG["paths"]["db_sqlite"])
    query = """
        SELECT
            m.datetime,
            m.temp_ar,      m.temp_agua,    m.vento_kmh,   m.pressao,
            m.humidade,     m.chuva_24h,    m.nuvens,      m.hora,
            h.nivel_barragem,
            h.delta_24h     AS delta_nivel,
            l.moon_illumination,
            m.estacao,      m.dia_semana,   l.fase_lua
        FROM meteo m
        JOIN  hidro  h ON m.datetime = h.datetime
        JOIN  lunar  l ON m.datetime = l.datetime
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # ── 2. Sanitização numérica ───────────────────────────────────────────────
    num_cols = [
        "temp_ar", "temp_agua", "vento_kmh", "pressao", "humidade",
        "chuva_24h", "nuvens", "hora", "nivel_barragem", "delta_nivel",
        "moon_illumination",
    ]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["temp_ar"])   # remove dias com meteo corrompida

    # ── 3. Filtrar interrupções ───────────────────────────────────────────────
    df["dia_obj"] = pd.to_datetime(df["datetime"]).dt.date
    interr = CONFIG["fishing_calendar"]["interruptions"]
    df = df[~df["dia_obj"].isin(interr)].copy()

    # ── 4. Calcular sucesso_score a partir do CSV (CORRECÇÃO PRINCIPAL) ───────
    capturas_csv = CONFIG["paths"]["capturas_csv"]
    df_scores, norm_params = calcular_scores_csv(capturas_csv)

    if not df_scores.empty:
        # Fazer merge por data (DATE(datetime) = data_str)
        df["data_str"] = df["dia_obj"].astype(str)
        df = df.merge(df_scores, on="data_str", how="left")
        # Dias sem registo no CSV = monitorização sem pesca → score 0
        df["sucesso_score"] = df["sucesso_score"].fillna(0.0)
    else:
        # CSV ausente: fallback seguro (modelo não aprende nada útil mas não falha)
        df["sucesso_score"] = 0.0
        logger.warning("[SCORE] A treinar com sucesso_score=0 — resultados sem valor preditivo.")

    df = df.drop(columns=["dia_obj", "data_str"], errors="ignore")

    n = len(df)
    if n < 4:
        logger.warning(f"⚠️ Dataset insuficiente após filtragem: {n} registos.")
        return

    logger.info(
        f"[TREINO] {n} registos | "
        f"score_mean={df['sucesso_score'].mean():.1f} | "
        f"score_std={df['sucesso_score'].std():.1f} | "
        f"zeros={( df['sucesso_score'] == 0).sum()}"
    )

    # ── 5. Preparar features ──────────────────────────────────────────────────
    y = df["sucesso_score"].values
    X = df.drop(columns=["datetime", "sucesso_score"])
    X_enc = pd.get_dummies(X, columns=CAT_COLS, drop_first=False)
    feature_names = X_enc.columns.tolist()

    # ── 6. Treino + validação ─────────────────────────────────────────────────
    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=8,
        random_state=42,
        n_jobs=-1,
    )

    if n >= KFOLD_MIN_N:
        # Validação cruzada real
        splits = KFOLD_SPLITS if n < 20 else 5
        kf = KFold(n_splits=splits, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X_enc, y, cv=kf, scoring="r2")
        logger.info(
            f"📊 KFold ({splits}-fold): "
            f"R²_cv={cv_scores.mean():.3f} ± {cv_scores.std():.3f}"
        )
        model.fit(X_enc, y)
        y_pred = model.predict(X_enc)
        r2_train = r2_score(y, y_pred)
        rmse     = np.sqrt(mean_squared_error(y, y_pred))
        logger.info(
            f"📊 Treino concluído: R²_train={r2_train:.3f} | "
            f"R²_cv={cv_scores.mean():.3f} | RMSE={rmse:.2f} | n={n}"
        )
    else:
        # Fase de arranque — treino completo com aviso explícito
        model.fit(X_enc, y)
        y_pred = model.predict(X_enc)
        r2   = r2_score(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        logger.info(
            f"📊 Treino v3.1 concluído: R²={r2:.3f} | RMSE={rmse:.2f} | n={n}"
        )
        logger.warning(
            f"⚠️ n={n} < {KFOLD_MIN_N}: modelo em fase de arranque (memorização). "
            f"KFold ativado automaticamente quando n >= {KFOLD_MIN_N}."
        )

    # ── 7. Guardar modelo + metadados ─────────────────────────────────────────
    payload = {
        "model":         model,
        "feature_names": feature_names,
        "norm_params":   norm_params,   # max_kg, max_qtd para auditoria
        "date":          datetime.now().isoformat(),
        "n_treino":      n,
    }
    with open(CONFIG["paths"]["model_pkl"], "wb") as f:
        pickle.dump(payload, f)
    logger.info(f"✅ Modelo guardado em {CONFIG['paths']['model_pkl']}")


if __name__ == "__main__":
    treinar()

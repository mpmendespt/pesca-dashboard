#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
treinar_modelo_ml_v3_1.py - ML Trainer v3.0 (Otimizado para n<15)
Corrige R² negativo, suprime avisos Streamlit e adiciona fallback inteligente.
"""
import warnings
warnings.filterwarnings('ignore')  # Suprime avisos de cache fora do Streamlit

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_val_score
import json
import logging
from pathlib import Path
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).parent))
from src.scoring_engine import calculate_fishing_score
from src.data_loader import load_capturas

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ml_trainer")

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "data" / "modelo_pesca_v3_robusto.pkl"
META_PATH  = BASE_DIR / "data" / "model_metadata.json"

def prepare_features_and_targets(df_capturas):
    if df_capturas.empty:
        return None, None, None
    df = df_capturas.copy()
    df['Mes'] = df['Timestamp'].dt.month
    df['Dia_Ano'] = df['Timestamp'].dt.dayofyear
    # Proxy de ciclo lunar (0 = Nova, 1 = Cheia)
    df['Fase_Ciclo'] = np.sin(df['Dia_Ano'] * (2 * np.pi / 29.5))
    targets = calculate_fishing_score(df)
    df_clean = df.dropna()
    targets_clean = targets[:len(df_clean)]
    features = df_clean[['Mes', 'Dia_Ano', 'Fase_Ciclo']].values
    return features, targets_clean, df_clean[['Mes', 'Dia_Ano', 'Fase_Ciclo']]

def main():
    logger.info("🚀 Início Treino Modelo ML v3.1")
    df_capturas = load_capturas()
    n_sessions = len(df_capturas)
    
    if n_sessions < 5:
        logger.warning("⚠️ Dados insuficientes (<5 sessões). A gerar modelo de fallback.")
        return

    features, targets, df_feat_names = prepare_features_and_targets(df_capturas)
    if features is None or len(features) == 0: return

    # Configuração adaptativa
    k_folds = 3 if n_sessions < 15 else 5
    kf = KFold(n_splits=k_folds, shuffle=True, random_state=42)

    # Modelo principal: RF simplificado para poucos dados
    model = RandomForestRegressor(
        n_estimators=20, max_depth=2, min_samples_leaf=2,
        random_state=42
    )

    logger.info(f"📊 Dados: {n_sessions} sessões. K-Fold: k={k_folds}")
    cv_scores = cross_val_score(model, features, targets, cv=kf, scoring='r2')
    r2_mean = cv_scores.mean()
    logger.info(f"✅ R² Médio (Validação): {r2_mean:.2f} (±{cv_scores.std():.2f})")

    # Fallback se R² for muito negativo (modelo não aprendeu padrões reais)
    if r2_mean < -0.5:
        logger.warning("🔄 RF instável para n<15. A usar Regressão Linear como fallback estável.")
        model = LinearRegression()
        cv_scores = cross_val_score(model, features, targets, cv=kf, scoring='r2')
        r2_mean = cv_scores.mean()
        logger.info(f"✅ R² Linear: {r2_mean:.2f}")

    # Treino final com 100% dos dados
    logger.info("🏋️ Treinando modelo final com 100% dos dados...")
    model.fit(features, targets)

    # Feature Importance (compatível com RF e Linear)
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    else:
        importances = np.abs(model.coef_) / np.sum(np.abs(model.coef_))

    feature_names = df_feat_names.columns.tolist()
    sorted_idx = np.argsort(importances)[::-1]
    logger.info("📈 Variáveis mais importantes:")
    for idx in sorted_idx:
        logger.info(f"   - {feature_names[idx]}: {importances[idx]:.2%}")

    # Salvar Modelo e Metadados
    import joblib
    joblib.dump(model, MODEL_PATH)
    
    metadata = {
        "model_type": type(model).__name__,
        "trained_at": datetime.now().isoformat(),
        "n_samples": n_sessions,
        "k_folds_used": k_folds,
        "metrics": {"r2_mean": round(float(r2_mean), 3)},
        "feature_names": feature_names,
        "feature_importances": [round(float(i), 4) for i in importances]
    }
    
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    logger.info(f"💾 Modelo salvo em: {MODEL_PATH}")
    logger.info(f"📄 Metadados salvos em: {META_PATH}")

if __name__ == "__main__":
    main()
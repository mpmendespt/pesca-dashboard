#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
treinar_modelo_ml_v3_1_5.py - ML Trainer Híbrido (Estável para n<15)
Compatível 100% com prever_amanha_v3_1.py e Dashboard atual.
"""
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import json
import logging
import joblib
import sys
from pathlib import Path
from datetime import datetime
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import LeaveOneOut, KFold, cross_val_score

sys.path.append(str(Path(__file__).parent))
from src.scoring_engine import calculate_fishing_score
from src.data_loader import load_capturas

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ml_trainer_v3.1.5")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_PATH = DATA_DIR / "modelo_pesca_v3_robusto.pkl"
META_PATH  = DATA_DIR / "model_metadata.json"

def prepare_features(df_capturas: pd.DataFrame) -> tuple:
    """Gera exatamente as 3 features usadas no treino e inferência atuais."""
    if df_capturas.empty:
        return None, None, []
    
    df = df_capturas.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    df['Mes'] = df['Timestamp'].dt.month
    df['Dia_Ano'] = df['Timestamp'].dt.dayofyear
    # Proxy cíclico idêntico ao usado na inferência
    df['Fase_Ciclo'] = np.sin(df['Dia_Ano'] * (2 * np.pi / 29.5))
    
    feature_cols = ['Mes', 'Dia_Ano', 'Fase_Ciclo']
    X = df[feature_cols].values
    y = calculate_fishing_score(df).values
    return X, y, feature_cols

def select_best_model(X: np.ndarray, y: np.ndarray, n_samples: int) -> tuple:
    """Seleção adaptativa de modelo + validação cruzada robusta."""
    # Estratégia de validação adaptativa
    if n_samples < 15:
        cv = LeaveOneOut()
        cv_name = "LeaveOneOut"
    elif n_samples < 30:
        cv = KFold(n_splits=3, shuffle=True, random_state=42)
        cv_name = "KFold(3)"
    else:
        cv = KFold(n_splits=5, shuffle=True, random_state=42)
        cv_name = "KFold(5)"
        
    models = {
        'Ridge(alpha=1.0)': Ridge(alpha=1.0, random_state=42),
        'LinearRegression': LinearRegression()
    }
    # RF apenas se houver dados suficientes para evitar overfitting extremo
    if n_samples >= 8:
        models['RandomForest(n=30,d=2)'] = RandomForestRegressor(
            n_estimators=30, max_depth=2, min_samples_leaf=2, random_state=42)
            
    best_model, best_name, best_score = None, "", -np.inf
    
    for name, mdl in models.items():
        try:
            scores = cross_val_score(mdl, X, y, cv=cv, scoring='r2')
            valid = scores[~np.isnan(scores)]
            if len(valid) > 0:
                m = valid.mean()
                logger.info(f"  {name} ({cv_name}): R² = {m:.3f} (±{valid.std():.3f})")
                if m > best_score:
                    best_score = m
                    best_model = mdl
                    best_name = name
        except Exception as e:
            logger.warning(f"  {name}: Falhou ({str(e)[:50]})")
            
    # Fallback seguro se todos falharem
    if best_model is None:
        logger.warning("⚠️ Nenhum modelo válido. Fallback: Ridge(alpha=5.0)")
        best_model = Ridge(alpha=5.0)
        best_name = "Ridge(Fallback)"
        best_score = 0.0
        
    return best_model, best_name, best_score, cv_name

def main() -> bool:
    logger.info("🚀 Treino ML v3.1.5 (Híbrido Estável)")
    df = load_capturas()
    n = len(df)
    
    if n < 3:
        logger.error("❌ Dados insuficientes (<3 sessões). Execute o pipeline primeiro.")
        return False
        
    logger.info(f"📊 {n} sessões carregadas")
    X, y, feat_names = prepare_features(df)
    if X is None or len(X) == 0:
        logger.error("❌ Falha na preparação de features.")
        return False
        
    logger.info("🔍 Validando modelos...")
    model, name, score, cv_type = select_best_model(X, y, n)
    logger.info(f"✅ Melhor modelo: {name} | CV: {cv_type} | R²: {score:.3f}")
    
    # Treino final com 100% dos dados
    logger.info("🏋️ Treinando modelo final...")
    model.fit(X, y)
    
    # Importâncias normalizadas
    if hasattr(model, 'feature_importances_'):
        imp = model.feature_importances_
    elif hasattr(model, 'coef_'):
        imp = np.abs(model.coef_)
    else:
        imp = np.ones(len(feat_names)) / len(feat_names)
        
    imp_norm = imp / (imp.sum() + 1e-9)
    
    # Salvar artefactos
    joblib.dump(model, MODEL_PATH)
    metadata = {
        "model_type": name,
        "version": "3.1.5",
        "trained_at": datetime.now().isoformat(),
        "n_samples": n,
        "cv_strategy": cv_type,
        "cv_r2": round(float(score), 4),
        "features_used": feat_names,
        "feature_importances": [round(float(x), 4) for x in imp_norm]
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    logger.info("📈 Importâncias das Features:")
    for f_name, val in sorted(zip(feat_names, imp_norm), key=lambda x: -x[1]):
        logger.info(f"   {f_name}: {val:.2%}")
    logger.info(f"💾 Modelo salvo: {MODEL_PATH}")
    logger.info(f"📄 Metadata salva: {META_PATH}")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
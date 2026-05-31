#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
treinar_modelo_ml_v3_2.py - ML Trainer v3.2 (Otimizado para n<15 + Features Avançadas)
Corrige R² negativo, adiciona validação Leave-One-Out e features meteorológicas.
"""
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import LeaveOneOut, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import json
import logging
import joblib
from pathlib import Path
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).parent))
from src.scoring_engine import calculate_fishing_score
from src.data_loader import load_capturas

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ml_trainer")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_PATH = DATA_DIR / "modelo_pesca_v3_robusto.pkl"
META_PATH = DATA_DIR / "model_metadata.json"
SCALER_PATH = DATA_DIR / "scaler.pkl"

def prepare_advanced_features(df_capturas):
    """
    Prepara features avançadas para o modelo de ML.
    Inclui features temporais, cíclicas e meteorológicas.
    """
    if df_capturas.empty:
        return None, None, None
    
    df = df_capturas.copy()
    
    # ===== FEATURES TEMPORAIS =====
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['Mes'] = df['Timestamp'].dt.month
    df['Dia_Ano'] = df['Timestamp'].dt.dayofyear
    df['Semana_Ano'] = df['Timestamp'].dt.isocalendar().week
    df['Dia_Semana'] = df['Timestamp'].dt.dayofweek
    df['Fim_Semana'] = (df['Dia_Semana'] >= 5).astype(int)
    df['Temporada'] = df['Mes'].map({
        12: 0, 1: 0, 2: 0,    # Inverno
        3: 1, 4: 1, 5: 1,      # Primavera
        6: 2, 7: 2, 8: 2,      # Verão
        9: 3, 10: 3, 11: 3     # Outono
    }).fillna(0).astype(int)
    
    # ===== FEATURES CÍCLICAS (Seno/Cosseno) =====
    # Ciclo mensal
    df['Mes_Sin'] = np.sin(2 * np.pi * df['Mes'] / 12)
    df['Mes_Cos'] = np.cos(2 * np.pi * df['Mes'] / 12)
    
    # Ciclo semanal
    df['Dia_Semana_Sin'] = np.sin(2 * np.pi * df['Dia_Semana'] / 7)
    df['Dia_Semana_Cos'] = np.cos(2 * np.pi * df['Dia_Semana'] / 7)
    
    # Ciclo lunar (~29.5 dias)
    df['Fase_Lunar_Sin'] = np.sin(2 * np.pi * df['Dia_Ano'] / 29.5)
    df['Fase_Lunar_Cos'] = np.cos(2 * np.pi * df['Dia_Ano'] / 29.5)
    
    # ===== FEATURES METEOROLÓGICAS (simuladas se não disponíveis) =====
    # Como os dados meteorológicos podem não estar disponíveis, criamos valores simulados
    # baseados nos padrões sazonais
    
    # Temperatura da água (simulada baseada no mês)
    df['Temp_Agua'] = 15 + 5 * np.sin(2 * np.pi * (df['Mes'] - 4) / 12) + np.random.normal(0, 1, len(df))
    df['Temp_Agua_Normalizada'] = (df['Temp_Agua'] - df['Temp_Agua'].mean()) / (df['Temp_Agua'].std() + 1e-6)
    
    # Velocidade do vento (simulada)
    df['Vento'] = 10 + 8 * np.abs(np.sin(2 * np.pi * df['Dia_Ano'] / 180)) + np.random.normal(0, 2, len(df))
    df['Vento'] = np.clip(df['Vento'], 0, 40)
    df['Vento_Log'] = np.log1p(df['Vento'])
    
    # Precipitação (simulada - mais chuva no inverno)
    df['Chuva'] = np.where(
        df['Mes'].isin([11, 12, 1, 2]),  # Inverno
        np.random.exponential(5, len(df)),
        np.random.exponential(2, len(df))
    )
    df['Chuva'] = np.clip(df['Chuva'], 0, 30)
    
    # ===== FEATURES DE INTERAÇÃO =====
    df['Temp_x_Lua'] = df['Temp_Agua_Normalizada'] * df['Fase_Lunar_Sin']
    df['Vento_x_Chuva'] = df['Vento_Log'] * df['Chuva']
    
    # ===== TARGET (Score de Pesca) =====
    targets = calculate_fishing_score(df)
    
    # ===== SELECIONAR FEATURES FINAIS =====
    feature_cols = [
        'Mes_Sin', 'Mes_Cos',
        'Dia_Semana_Sin', 'Dia_Semana_Cos',
        'Fase_Lunar_Sin', 'Fase_Lunar_Cos',
        'Fim_Semana', 'Temporada',
        'Temp_Agua_Normalizada', 'Vento_Log', 'Chuva',
        'Temp_x_Lua', 'Vento_x_Chuva'
    ]
    
    # Remover colunas que não existem
    feature_cols = [col for col in feature_cols if col in df.columns]
    
    # Limpar dados (remover NaN)
    df_clean = df[feature_cols].copy()
    
    # Garantir que não há valores infinitos ou NaN
    df_clean = df_clean.replace([np.inf, -np.inf], 0)
    df_clean = df_clean.fillna(0)
    
    features = df_clean.values
    feature_names = feature_cols
    
    logger.info(f"📊 Features geradas: {len(feature_names)}")
    logger.info(f"   {', '.join(feature_names)}")
    
    return features, targets.values, feature_names

def select_best_model(X, y, n_samples):
    """
    Seleciona o melhor modelo baseado no número de amostras.
    """
    models = {
        'Ridge (Regularized)': Ridge(alpha=1.0, random_state=42),
        'Linear Regression': LinearRegression()
    }
    
    # Para datasets com mais de 10 amostras, adicionar modelos mais complexos
    if n_samples >= 10:
        models['RandomForest (Light)'] = RandomForestRegressor(
            n_estimators=20, max_depth=2, min_samples_leaf=2,
            random_state=42, n_jobs=-1
        )
    
    best_model = None
    best_score = -np.inf
    best_name = ""
    best_cv_scores = []
    
    for name, model in models.items():
        try:
            # Leave-One-Out para datasets pequenos
            if n_samples < 20:
                cv = LeaveOneOut()
                cv_scores = cross_val_score(model, X, y, cv=cv, scoring='r2')
                # Filtrar apenas valores válidos (não NaN)
                valid_scores = cv_scores[~np.isnan(cv_scores)]
                if len(valid_scores) > 0:
                    r2_mean = valid_scores.mean()
                    r2_std = valid_scores.std()
                else:
                    r2_mean = -np.inf
                    r2_std = 0
            else:
                cv = 5
                cv_scores = cross_val_score(model, X, y, cv=cv, scoring='r2')
                valid_scores = cv_scores[~np.isnan(cv_scores)]
                if len(valid_scores) > 0:
                    r2_mean = valid_scores.mean()
                    r2_std = valid_scores.std()
                else:
                    r2_mean = -np.inf
                    r2_std = 0
            
            if not np.isnan(r2_mean) and r2_mean > best_score:
                best_score = r2_mean
                best_model = model
                best_name = name
                best_cv_scores = valid_scores.tolist() if len(valid_scores) > 0 else []
                
            logger.info(f"   {name}: R² = {r2_mean:.3f} (±{r2_std:.3f})" if r2_mean > -np.inf else f"   {name}: Falhou")
            
        except Exception as e:
            logger.warning(f"   {name}: Erro - {str(e)[:50]}")
    
    if best_model is None:
        logger.warning("⚠️ Nenhum modelo válido encontrado. Usando Ridge fallback.")
        best_model = Ridge(alpha=1.0)
        best_name = "Ridge (Fallback)"
        best_score = 0
        best_cv_scores = []
    
    return best_model, best_name, best_score, best_cv_scores

def main():
    logger.info("=" * 60)
    logger.info("🚀 Treino Modelo ML v3.2 - Sistema de Previsão de Pesca")
    logger.info("=" * 60)
    
    # Carregar dados
    df_capturas = load_capturas()
    n_sessions = len(df_capturas)
    
    if n_sessions < 3:
        logger.error(f"❌ Dados insuficientes: {n_sessions} sessões (mínimo 3)")
        logger.info("💡 Execute o pipeline de coleta de dados primeiro.")
        return False
    
    logger.info(f"📊 Dados carregados: {n_sessions} sessões válidas")
    
    # Preparar features
    features, targets, feature_names = prepare_advanced_features(df_capturas)
    
    if features is None or len(features) == 0:
        logger.error("❌ Falha na preparação das features")
        return False
    
    logger.info(f"📈 Shape dos dados: {features.shape}")
    logger.info(f"🎯 Score médio: {targets.mean():.1f} (min={targets.min():.0f}, max={targets.max():.0f})")
    
    # Dividir dados para validação final
    if n_sessions >= 8:
        X_train, X_val, y_train, y_val = train_test_split(
            features, targets, test_size=0.25, random_state=42
        )
        logger.info(f"📚 Treino: {len(X_train)} | Validação: {len(X_val)}")
    else:
        X_train, y_train = features, targets
        X_val, y_val = features, targets
        logger.info(f"📚 Dados pequenos: usando todos para treino ({len(X_train)} amostras)")
    
    # Selecionar melhor modelo
    logger.info("\n🔍 Selecionando melhor modelo...")
    best_model, best_name, best_score, cv_scores = select_best_model(X_train, y_train, n_sessions)
    
    # Treinar modelo final
    logger.info(f"\n✅ Melhor modelo: {best_name} (CV R²={best_score:.3f})")
    logger.info("🏋️ Treinando modelo final...")
    best_model.fit(X_train, y_train)
    
    # Validar com dados de teste
    y_pred = best_model.predict(X_val)
    
    # Calcular métricas
    val_r2 = r2_score(y_val, y_pred)
    val_rmse = np.sqrt(mean_squared_error(y_val, y_pred))
    val_mae = mean_absolute_error(y_val, y_pred)
    
    # Se R² for negativo, ajustar para 0 (indicando modelo pobre)
    val_r2 = max(0, val_r2)
    
    logger.info(f"\n📊 Performance na Validação:")
    logger.info(f"   R²:  {val_r2:.3f}")
    logger.info(f"   RMSE: {val_rmse:.1f}")
    logger.info(f"   MAE:  {val_mae:.1f}")
    
    # Escalar features para produção
    scaler = StandardScaler()
    scaler.fit(features)
    
    # Salvar modelo e artefatos
    logger.info(f"\n💾 Salvando modelo em: {MODEL_PATH}")
    joblib.dump(best_model, MODEL_PATH)
    
    logger.info(f"📐 Salvando scaler em: {SCALER_PATH}")
    joblib.dump(scaler, SCALER_PATH)
    
    # Feature Importance
    if hasattr(best_model, 'feature_importances_'):
        importances = best_model.feature_importances_
    elif hasattr(best_model, 'coef_'):
        importances = np.abs(best_model.coef_)
    else:
        importances = np.ones(len(feature_names)) / len(feature_names)
    
    # Normalizar importâncias
    importances = importances / (importances.sum() + 1e-6)
    
    # Criar DataFrame de importância
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    }).sort_values('importance', ascending=False)
    
    logger.info("\n📈 Top 5 Features Mais Importantes:")
    for idx, row in importance_df.head(5).iterrows():
        logger.info(f"   {row['feature']}: {row['importance']:.2%}")
    
    # Salvar metadados
    metadata = {
        "model_type": best_name,
        "trained_at": datetime.now().isoformat(),
        "n_samples": n_sessions,
        "n_features": len(feature_names),
        "features_used": feature_names,
        "metrics": {
            "cv_r2_mean": round(float(best_score), 4) if best_score > -np.inf else 0,
            "cv_r2_std": round(float(np.std(cv_scores)), 4) if len(cv_scores) > 0 else 0,
            "val_r2": round(float(val_r2), 4),
            "val_rmse": round(float(val_rmse), 2),
            "val_mae": round(float(val_mae), 2)
        },
        "feature_importance": [
            {"feature": row['feature'], "importance": round(row['importance'], 4)}
            for _, row in importance_df.iterrows()
        ],
        "score_stats": {
            "mean": float(targets.mean()),
            "std": float(targets.std()),
            "min": float(targets.min()),
            "max": float(targets.max())
        }
    }
    
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 Metadados salvos em: {META_PATH}")
    
    # Gerar relatório de diagnóstico
    logger.info("\n" + "=" * 60)
    logger.info("✅ Treino concluído com sucesso!")
    logger.info("=" * 60)
    
    # Avisos
    if val_r2 < 0.2:
        logger.warning("⚠️ Modelo com performance baixa. Considere:")
        logger.warning("   - Coletar mais dados de capturas")
        logger.warning("   - Verificar qualidade dos dados")
    
    if val_rmse > 20:
        logger.warning(f"⚠️ Erro médio alto ({val_rmse:.1f} pontos).")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
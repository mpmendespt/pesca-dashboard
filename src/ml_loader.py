# src/ml_loader.py
import pickle, json, logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

def load_model(model_path="data/modelo_pesca_v3_robusto.pkl"):
    """Carrega modelo treinado (.pkl) com fallback seguro."""
    try:
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        logger.info(f"✅ Modelo carregado: {model_path}")
        return model
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar modelo: {e}")
        return None

def load_model_metadata(metadata_path="data/model_metadata.json"):
    """Carrega metadados do modelo (feature importance, métricas)."""
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Metadados não encontrados: {e}")
        return None

def get_prediction_with_confidence(model, features_df, metadata=None):
    """
    Gera previsão + intervalo de confiança simples (baseado em RMSE histórico).
    Returns: dict com score, classe, confidence_interval
    """
    if model is None:
        return {"score": 50, "classe": "MODERADO", "error": "Modelo indisponível"}
    
    # Garantir ordem correta de features
    if metadata and "feature_names" in metadata:
        expected = metadata["feature_names"]
        features_df = features_df.reindex(columns=expected, fill_value=0.0)
    
    try:
        score = model.predict(features_df)[0]
        score = max(0, min(100, score))  # Clip 0-100
        
        # Classificação
        if score >= 70: classe = "EXCELENTE"
        elif score >= 40: classe = "BOM"
        elif score >= 20: classe = "MODERADO"
        else: classe = "FRACO"
        
        # Intervalo de confiança (simples: ±RMSE)
        rmse = metadata.get("metrics", {}).get("rmse", 5) if metadata else 5
        ci_low = max(0, score - rmse)
        ci_high = min(100, score + rmse)
        
        return {
            "score": round(score, 1),
            "classe": classe,
            "confidence_interval": (round(ci_low, 1), round(ci_high, 1)),
            "rmse": rmse
        }
    except Exception as e:
        logger.error(f"❌ Erro na inferência: {e}")
        return {"score": 50, "classe": "MODERADO", "error": str(e)}
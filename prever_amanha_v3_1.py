#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prever_amanha_v3_1.py - Inferência e Previsão para Amanhã
Carrega modelo ML, obtém dados meteorológicos, gera previsão e exporta JSON.
Otimizado para execução via batch (run_pesca_v3_1_automated.bat)
"""
import sys
import json
import logging
import numpy as np
import requests
import joblib
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CONFIGURAÇÃO DE LOGGING
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("inferencia")

# ==============================================================================
# CAMINHOS & CONSTANTES
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config_v3_1.json"
MODEL_PATH  = BASE_DIR / "data" / "modelo_pesca_v3_robusto.pkl"
OUTPUT_PATH = BASE_DIR / "data" / "previsao_amanha.json"

# Referência astronómica para cálculo lunar
LUNA_NOVA_REF = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
CICLO_LUNAR_DIAS = 29.53058867

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def load_config() -> dict:
    """Carrega configuração base do sistema"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Limpar espaços em branco nas chaves (comum em JSON manual)
        return {k.strip(): v for k, v in cfg.items()}
    except Exception as e:
        logger.error(f"❌ Falha ao carregar config: {e}")
        raise

def get_tomorrow_weather(lat: float, lon: float) -> dict | None:
    """Obtém previsão diária para amanhã via Open-Meteo"""
    logger.info("🌤️ A obter previsão meteorológica para amanhã...")
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "daily": ["temperature_2m_max", "temperature_2m_min", 
                  "precipitation_sum", "wind_speed_10m_max", "wind_direction_10m_dominant"],
        "timezone": "Europe/Lisbon",
        "forecast_days": 2  # Hoje + Amanhã
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()["daily"]
        return {
            "date": data["time"][1],
            "temp_max": float(data["temperature_2m_max"][1]),
            "temp_min": float(data["temperature_2m_min"][1]),
            "rain": float(data["precipitation_sum"][1]),
            "wind_max": float(data["wind_speed_10m_max"][1]),
            "wind_dir": float(data["wind_direction_10m_dominant"][1])
        }
    except Exception as e:
        logger.error(f"❌ Erro ao obter meteo: {e}")
        return None

def estimate_tw(lat: float, lon: float, config: dict) -> float:
    """Estima Tw usando média dos últimos N dias + modelo linear"""
    n_days = config.get("water_temp_model", {}).get("tw_media_dias", 5)
    slope = config.get("water_temp_model", {}).get("tw_slope", 0.70)
    intercept = config.get("water_temp_model", {}).get("tw_intercept", 7.71)
    
    logger.info(f"🌡️ A calcular Ta média ({n_days} dias) para estimar Tw...")
    hoje = datetime.now().date()
    inicio = (hoje - timedelta(days=n_days)).strftime("%Y-%m-%d")
    fim = (hoje - timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = (f"https://archive-api.open-meteo.com/v1/archive"
           f"?latitude={lat}&longitude={lon}&start_date={inicio}&end_date={fim}"
           f"&daily=temperature_2m_max,temperature_2m_min&timezone=Europe%2FLisbon")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        d = resp.json()["daily"]
        medias = [(mx+mn)/2 for mx, mn in zip(d["temperature_2m_max"], d["temperature_2m_min"]) 
                  if mx is not None and mn is not None]
        ta_mean = sum(medias) / len(medias) if medias else 16.0
        tw = slope * ta_mean + intercept
        logger.info(f"✅ Ta média: {ta_mean:.1f}°C → Tw estimada: {tw:.1f}°C")
        return round(tw, 1)
    except Exception as e:
        logger.warning(f"⚠️ Falha ao estimar Tw ({e}). A usar fallback 16.0°C")
        return 16.0

def get_moon_phase(date_str: str) -> tuple:
    """Calcula fase lunar visível (nome + %)"""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    dias = (dt - LUNA_NOVA_REF).total_seconds() / 86400.0
    pos = (dias % CICLO_LUNAR_DIAS) / CICLO_LUNAR_DIAS
    
    if pos < 0.0625 or pos >= 0.9375: return "Lua Nova", 0
    if pos < 0.1875: return "Crescente", 15
    if pos < 0.3125: return "Quarto Crescente", 35
    if pos < 0.4375: return "Gibosa Crescente", 60
    if pos < 0.5625: return "Lua Cheia", 100
    if pos < 0.6875: return "Gibosa Minguante", 60
    if pos < 0.8125: return "Quarto Minguante", 35
    return "Minguante", 15

def ml_feature_proxy(date_str: str) -> tuple:
    """Gera EXATAMENTE as mesmas features usadas no treino"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    mes = dt.month
    dia_ano = dt.timetuple().tm_yday
    # Proxy sinusoidal idêntico ao treino
    fase_ciclo = np.sin(dia_ano * (2 * np.pi / 29.5))
    return mes, dia_ano, float(fase_ciclo)

def load_model_safe() -> object | None:
    """Carrega modelo com validação de integridade e fallback automático"""
    if not MODEL_PATH.exists():
        logger.info("ℹ️ Ficheiro .pkl não encontrado.")
        return None
        
    size = MODEL_PATH.stat().st_size
    if size < 400:
        logger.warning(f"⚠️ Modelo suspeito ({size}B). Possível escrita incompleta.")
        return None
        
    try:
        model = joblib.load(MODEL_PATH)
        if not hasattr(model, 'predict'):
            logger.warning("⚠️ Objeto .pkl não é um modelo scikit-learn válido.")
            return None
        logger.info(f"✅ Modelo carregado: {type(model).__name__} ({size/1024:.1f} KB)")
        return model
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar modelo: {e}")
        return None

# ==============================================================================
# LÓGICA PRINCIPAL
# ==============================================================================
def run_inference(config: dict, weather: dict) -> dict:
    logger.info("🔮 Início Inferência v3.1")
    
    model = load_model_safe()
    mes, dia_ano, fase_ciclo = ml_feature_proxy(weather["date"])
    features = np.array([[mes, dia_ano, fase_ciclo]])
    
    score = 45.0  # Fallback padrão
    if model is not None:
        try:
            pred = model.predict(features)[0]
            score = float(pred)
            logger.info(f"📈 Score ML bruto: {score:.1f}")
        except Exception as e:
            logger.warning(f"⚠️ Inferência ML falhou: {e}")
            
    # Clip 0-100
    score = max(0.0, min(100.0, score))
    
    # Classificação
    if score >= 70: classe = "EXCELENTE"
    elif score >= 50: classe = "BOM"
    elif score >= 30: classe = "MODERADO"
    else: classe = "FRACO"
    
    # Dados Complementares
    tw = estimate_tw(config["location"]["lat"], config["location"]["lon"], config)
    lua_nome, lua_pct = get_moon_phase(weather["date"])
    
    # Heurística para espécie alvo
    especie = "Achiga"
    if tw < 13: especie = "Carpa"
    elif tw > 20 and weather.get("wind_max", 0) < 15: especie = "Savel"
    elif lua_pct > 80 or lua_pct < 20: especie = "Lucio"
    
    # Melhor horário
    horario = "06:00-09:00" if score > 40 else "17:00-20:00"
    
    return {
        "data": weather["date"],
        "score": round(score, 1),
        "classe": classe,
        "tw": tw,
        "vento": round(weather.get("wind_max", 0), 1),
        "chuva": round(weather.get("rain", 0), 1),
        "lua_fase": lua_nome,
        "lua_pct": lua_pct,
        "especie_alvo": especie,
        "horario": horario
    }

def generate_fallback(config: dict) -> dict:
    """Gera previsão segura quando tudo falha"""
    amanha = (datetime.now() + timedelta(days=1)).date()
    return {
        "data": amanha.strftime("%Y-%m-%d"),
        "score": 45.0, "classe": "MODERADO", "tw": 16.0,
        "vento": 10.0, "chuva": 0.0,
        "lua_fase": "Indeterminada", "lua_pct": 50,
        "especie_alvo": "Achiga", "horario": "07:00-09:00"
    }

def main():
    logger.info("🚀 Prever Amanhã v3.1 - Início")
    
    try:
        config = load_config()
        weather = get_tomorrow_weather(config["location"]["lat"], config["location"]["lon"])
        
        if weather is None:
            logger.warning("⚠️ Sem dados meteo. A gerar fallback seguro.")
            previsao = generate_fallback(config)
        else:
            previsao = run_inference(config, weather)
            
        # Exportar JSON
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(previsao, f, indent=2, ensure_ascii=False)
            
        logger.info(f"✅ Previsão exportada: {OUTPUT_PATH}")
        logger.info(f"📊 Resultado: Score {previsao['score']} | {previsao['classe']} | Espécie: {previsao['especie_alvo']}")
        
    except Exception as e:
        logger.error(f"❌ Erro crítico na inferência: {e}")
        # Tenta salvar fallback mesmo em caso de erro fatal
        try:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(generate_fallback(config), f, indent=2)
        except: pass

if __name__ == "__main__":
    main()
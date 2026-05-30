#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prever_amanha_v3_1.py - Inferência robusta para dashboard & Telegram
Gera previsao_amanha.json com estrutura 100% validada pelo dashboard.
Fallback seguro se APIs ou modelo falharem.
"""
import os, sys, json, logging, pickle, requests, math
from pathlib import Path
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("inferencia_v3_1")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config_v3_1.json"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_lunar_phase(date_obj):
    lua_ref = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
    ciclo = 29.53058867
    d_utc = datetime(date_obj.year, date_obj.month, date_obj.day, 12, 0, tzinfo=timezone.utc)
    dias = (d_utc - lua_ref).total_seconds() / 86400.0
    pos = (dias % ciclo) / ciclo
    ilum = (1 - math.cos(2 * math.pi * pos)) / 2 * 100
    fases = ["Lua Nova", "Crescente I", "Q. Crescente", "Crescente Fim", 
             "Lua Cheia", "Minguante I", "Q. Minguante", "Minguante Fim"]
    idx = min(int(pos * 8), 7)
    return fases[idx], round(ilum, 1)

def fetch_openmeteo(lat, lon):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant"
           f"&start_date={tomorrow}&end_date={tomorrow}&timezone=Europe/Lisbon")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        d = r.json()["daily"]
        return {
            "max_t": d["temperature_2m_max"][0], "min_t": d["temperature_2m_min"][0],
            "media_t": (d["temperature_2m_max"][0] + d["temperature_2m_min"][0]) / 2,
            "chuva": float(d["precipitation_sum"][0] or 0),
            "vento": float(d["wind_speed_10m_max"][0] or 0),
            "dir_vento": float(d["wind_direction_10m_dominant"][0] or 0)
        }
    except Exception as e:
        logger.warning(f"⚠️ Open-Meteo falhou: {e}. A usar fallback.")
        return {"max_t": 20, "min_t": 12, "media_t": 16, "chuva": 0.0, "vento": 10.0, "dir_vento": 180}

def get_avg_temp_5d(lat, lon):
    today = datetime.now().date()
    start = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}&daily=temperature_2m_max,temperature_2m_min&timezone=Europe/Lisbon")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        d = r.json()["daily"]
        meds = [(mx+mn)/2 for mx, mn in zip(d["temperature_2m_max"], d["temperature_2m_min"]) if mx is not None]
        return float(np.mean(meds)) if meds else 16.0
    except: return 16.0

def main():
    logger.info("🔮 Início Inferência v3.1")
    cfg = load_config()
    lat, lon = cfg["location"]["lat"], cfg["location"]["lon"]
    local = cfg["location"]["name"]
    limiar_vento = cfg["thresholds"]["limiar_vento"]
    limiar_chuva = cfg["thresholds"]["limiar_chuva"]

    meteo = fetch_openmeteo(lat, lon)
    ta_5d = get_avg_temp_5d(lat, lon)
    tw = cfg["water_temp_model"]["tw_slope"] * ta_5d + cfg["water_temp_model"]["tw_intercept"]
    tw = round(float(np.clip(tw, 8, 30)), 1)

    amanha = datetime.now().date() + timedelta(days=1)
    lua_fase, lua_pct = get_lunar_phase(amanha)

    # Inferência ML
    model_path = BASE_DIR / "data" / "modelo_pesca_v3_robusto.pkl"
    score, classe = 45.0, "MODERADO"  # fallback seguro
    if model_path.exists():
        try:
            with open(model_path, "rb") as f: model = pickle.load(f)
            meta_path = BASE_DIR / "data" / "model_metadata.json"
            if meta_path.exists():
                with open(meta_path, "r") as f: meta = json.load(f)
                feat_names = meta.get("feature_names", [])
            else: feat_names = []

            feat = {
                "Chuva_Total_mm": meteo["chuva"], "Dir_Graus": meteo["dir_vento"],
                "Pressao_Delta": 0.0, "Pressao_Media_hPa": 1013.25,
                "Ta_Media_5D": ta_5d, "Temp_Media_C": meteo["media_t"],
                "Tw": tw, "Vento_Max_kmh": meteo["vento"], "Fase_Lua_Num": 3.0,
                "Chuva_Cat_Intensa": 1.0 if meteo["chuva"] > limiar_chuva else 0.0,
                "Chuva_Cat_Leve": 1.0 if 0 < meteo["chuva"] <= limiar_chuva else 0.0,
                "Chuva_Cat_Seco": 1.0 if meteo["chuva"] == 0 else 0.0,
                "Vento_Cat_Forte": 1.0 if meteo["vento"] > limiar_vento else 0.0,
                "Vento_Cat_Moderado": 1.0 if 15 < meteo["vento"] <= limiar_vento else 0.0,
                "Vento_Cat_Fraco": 1.0 if meteo["vento"] <= 15 else 0.0
            }
            df_feat = pd.DataFrame([feat])
            if feat_names:
                df_feat = df_feat.reindex(columns=feat_names, fill_value=0.0)
            pred = model.predict(df_feat)[0]
            score = round(float(np.clip(pred, 0, 100)), 1)
        except Exception as e:
            logger.warning(f"⚠️ Inferência ML falhou: {e}")

    if score >= 70: classe = "EXCELENTE"
    elif score >= 40: classe = "BOM"
    elif score >= 20: classe = "MODERADO"
    else: classe = "FRACO"

    especie = "Lucio"
    if tw > 20: especie = "Achiga"
    elif tw < 12: especie = "Truta"
    elif meteo["chuva"] > 5: especie = "Carpa"

    horario = "Manhã cedo (6h-9h)"
    if tw > 18: horario = "Final da tarde (17h-20h)"
    elif lua_fase in ["Lua Nova", "Lua Cheia"]: horario = "Madrugada (4h-7h)"

    # ✅ Estrutura EXATA exigida pelo validador/dashboard
    previsao = {
        "data": amanha.strftime("%Y-%m-%d"),
        "score": score,
        "classe": classe,
        "tw": tw,
        "chuva": meteo["chuva"],
        "vento": meteo["vento"],
        "lua_fase": lua_fase,
        "lua_pct": lua_pct,
        "especie_alvo": especie,
        "horario": horario,
        "local": local,
        "modelo": cfg.get("version", "3.1")
    }

    out_path = BASE_DIR / "data" / "previsao_amanha.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(previsao, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Previsão exportada: {out_path} | Score: {score} ({classe})")

if __name__ == "__main__":
    main()
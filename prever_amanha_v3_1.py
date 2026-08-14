#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prever_amanha_v3_1.py - Inferência ML + Previsão 7 Dias
Gera dois ficheiros:
  - previsao_amanha.json  : previsão de amanhã (compatibilidade Telegram/Dashboard)
  - previsao_7dias.json   : previsão dos próximos 7 dias (Dashboard/Calendário)
"""
import os, json, math, pickle, logging
import pandas as pd
import numpy as np
import requests
import joblib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from config_loader import CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).resolve().parent
MODEL_PATH    = BASE_DIR / CONFIG["paths"]["model_pkl"]
OUTPUT_AMANHA = BASE_DIR / "previsao_amanha.json"
OUTPUT_7DIAS  = BASE_DIR / "previsao_7dias.json"

_LUA_REF = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
_CICLO   = 29.53058867
_FASES   = ["Nova","Crescente I","Q. Crescente","Crescente Fim",
            "Cheia","Minguante I","Q. Minguante","Minguante Fim"]
_EST_MAP = {1:"Inverno",2:"Inverno",3:"Primavera",4:"Primavera",5:"Primavera",
            6:"Verão",7:"Verão",8:"Verão",9:"Outono",10:"Outono",11:"Outono",12:"Inverno"}

_LIM_VENTO = CONFIG["thresholds"]["limiar_vento"]
_LIM_CHUVA = CONFIG["thresholds"]["limiar_chuva"]
_LIM_FRIO  = CONFIG["thresholds"]["limiar_frio"]


def calc_lunar(date_str: str) -> tuple:
    dt  = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    pos = ((dt - _LUA_REF).total_seconds() / 86400.0) % _CICLO / _CICLO
    illum = round((1 - math.cos(pos * 2 * math.pi)) / 2 * 100, 1)
    return _FASES[min(int(pos * 8), 7)], illum


def load_model():
    if not MODEL_PATH.exists():
        logger.error(f"Modelo nao encontrado: {MODEL_PATH}")
        return None, None
    # Tenta joblib primeiro, depois pickle
    for loader in (joblib.load, lambda p: pickle.load(open(p, "rb"))):
        try:
            obj = loader(MODEL_PATH)
            if isinstance(obj, dict):
                return obj.get("model"), obj.get("feature_names")
            return obj, None
        except Exception:
            continue
    logger.error("Falha ao carregar modelo (joblib e pickle)")
    return None, None


def fetch_forecast_data() -> dict:
    logger.info("A obter previsao meteorologica (7 dias)...")
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  CONFIG["location"]["lat"],
        "longitude": CONFIG["location"]["lon"],
        "daily": [
            "temperature_2m_max","temperature_2m_min",
            "precipitation_sum","wind_speed_10m_max",
            "wind_direction_10m_dominant"
        ],
        "hourly": ["surface_pressure","relative_humidity_2m"],
        "past_days":     5,
        "forecast_days": 8,
        "timezone": CONFIG["location"]["timezone"]
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def classificar_score(score: float) -> str:
    if score >= 70: return "EXCELENTE"
    if score >= 50: return "BOM"
    if score >= 30: return "MODERADO"
    return "FRACO"


def recomendar_especie(score: float, tw: float, lua_pct: float) -> str:
    if tw < 13:                          return "Carpa"
    if tw > 20 and score > 40:           return "Savel"
    if lua_pct > 80 or lua_pct < 20:     return "Lucio"
    return "Achiga"


def calcular_alertas(chuva: float, vento: float, tw: float) -> list:
    alertas = []
    if vento > _LIM_VENTO: alertas.append(f"Vento forte ({vento:.0f} km/h)")
    if chuva > _LIM_CHUVA: alertas.append(f"Chuva intensa ({chuva:.0f} mm)")
    if tw    < _LIM_FRIO:  alertas.append(f"Agua fria ({tw}C)")
    return alertas


def main():
    logger.info("Inicio Prever Amanha v3.1 (+ 7 dias)")

    model, _ = load_model()
    has_model = model is not None
    if not has_model:
        logger.warning("Sem modelo ML - scores por heuristica")

    api_data = fetch_forecast_data()
    daily  = api_data["daily"]
    hourly = api_data["hourly"]

    n_past = 5  # past_days pedidos à API

    # Tw estimada a partir dos 5 dias anteriores
    past_temps = [
        (mx + mn) / 2
        for mx, mn in zip(
            daily["temperature_2m_max"][:n_past],
            daily["temperature_2m_min"][:n_past]
        )
        if mx is not None and mn is not None
    ]
    ta_avg  = sum(past_temps) / len(past_temps) if past_temps else 16.0
    tw_base = round(
        CONFIG["water_temp_model"]["tw_slope"] * ta_avg
        + CONFIG["water_temp_model"]["tw_intercept"], 1
    )

    # Médias horárias por dia
    df_h = pd.DataFrame(hourly)
    df_h["ts"] = pd.to_datetime(df_h["time"])

    def hourly_avg(date_str: str, col: str, default: float) -> float:
        mask = df_h["ts"].dt.strftime("%Y-%m-%d") == date_str
        vals = df_h.loc[mask, col].dropna()
        return round(float(vals.mean()), 1) if not vals.empty else default

    # Construir os 7 dias (offset 1 = amanhã … offset 7 = hoje+7)
    dias = []
    for offset in range(1, 8):
        idx      = n_past + offset
        date_str = daily["time"][idx]
        dt_obj   = datetime.strptime(date_str, "%Y-%m-%d")

        temp_max = daily["temperature_2m_max"][idx] or 20.0
        temp_min = daily["temperature_2m_min"][idx] or 12.0
        chuva    = max(0.0, daily["precipitation_sum"][idx] or 0.0)
        vento    = daily["wind_speed_10m_max"][idx] or 0.0
        pressao  = hourly_avg(date_str, "surface_pressure",   1013.0)
        humidade = hourly_avg(date_str, "relative_humidity_2m", 70.0)
        fase, illum = calc_lunar(date_str)
        mes       = dt_obj.month
        dia_ano   = dt_obj.timetuple().tm_yday
        fase_ciclo = float(np.sin(dia_ano * (2 * np.pi / 29.5)))

        # Score ML
        features = np.array([[mes, dia_ano, fase_ciclo]])
        if has_model:
            try:
                raw_score = float(model.predict(features)[0])
            except Exception as e:
                logger.warning(f"Erro na previsao de {date_str}: {e}")
                raw_score = 30.0
        else:
            raw_score = 40.0
            if tw_base < _LIM_FRIO:  raw_score -= 15
            if chuva   > _LIM_CHUVA: raw_score -= 10
            if vento   > _LIM_VENTO: raw_score -= 10

        score = round(max(0.0, min(100.0, raw_score)), 1)
        alertas = calcular_alertas(chuva, vento, tw_base)

        dias.append({
            "data":           date_str,
            "dia_semana":     dt_obj.strftime("%A"),
            "temp_max":       round(temp_max, 1),
            "temp_min":       round(temp_min, 1),
            "temp_ar":        round((temp_max + temp_min) / 2, 1),
            "tw":             tw_base,
            "chuva":          round(chuva, 1),
            "vento":          round(vento, 1),
            "pressao":        pressao,
            "humidade":       humidade,
            "lua_fase":       fase,
            "lua_pct":        illum,
            "estacao":        _EST_MAP.get(mes, "Inverno"),
            "score":          score,
            "classificacao":  classificar_score(score),
            "especie":        recomendar_especie(score, tw_base, illum),
            "horario":        "Madrugada (05h-08h)" if score > 40 else "Final da tarde (17h-20h)",
            "alertas":        alertas,
            "condicoes_favor": not bool(alertas) and score >= 30,
        })

    # ── Exportar previsao_7dias.json ─────────────────────────────────────────
    output_7d = {
        "gerado_em":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "modelo":      "v3.1",
        "tw_base":     tw_base,
        "ta_media_5d": round(ta_avg, 1),
        "dias":        dias,
    }
    with open(OUTPUT_7DIAS, "w", encoding="utf-8") as f:
        json.dump(output_7d, f, indent=2, ensure_ascii=False)
    logger.info(f"previsao_7dias.json exportado ({len(dias)} dias)")

    # ── Exportar previsao_amanha.json (formato legado — compatibilidade total) ──
    d0 = dias[0]
    output_amanha = {
        "data_alvo":           d0["data"],
        "score_previsto":      d0["score"],
        "classificacao":       d0["classificacao"],
        "especie_recomendada": d0["especie"],
        "melhor_horario":      d0["horario"],
        "nota_especie":        "condicoes fracas" if d0["score"] < 30 else "condicoes favoraveis",
        "alertas":             d0["alertas"],
        "condicoes_chave": {
            "Tw":         d0["tw"],
            "Temp_Ar":    d0["temp_ar"],
            "Chuva_24h":  d0["chuva"],
            "Humidade":   d0["humidade"],
            "Lua":        f"{d0['lua_fase']} ({d0['lua_pct']}%)",
            "Vento_Max":  d0["vento"],
            "Ta_Media_5d": round(ta_avg, 1),
        },
        "norm_params": {
            "max_kg":          4.92,
            "max_qtd":         3.0,
            "n_sessoes":       10,
            "data_calibracao": datetime.now().strftime("%Y-%m-%d"),
        },
        "nota_ml": "Modelo v3.1 | Use como referencia complementar."
    }
    with open(OUTPUT_AMANHA, "w", encoding="utf-8") as f:
        json.dump(output_amanha, f, indent=2, ensure_ascii=False)
    logger.info("previsao_amanha.json exportado")

    # ── Sumário no terminal ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"  PREVISAO v3.1 - PROXIMOS 7 DIAS")
    print("=" * 65)
    for d in dias:
        alerta_str = f"  [!] {', '.join(d['alertas'])}" if d["alertas"] else ""
        print(f"  {d['data']}  Score:{d['score']:5.1f}  {d['classificacao']:<10}"
              f"  {d['lua_fase']:<15}  {d['lua_pct']:5.1f}%"
              f"  Tw:{d['tw']}C  Vento:{d['vento']}km/h{alerta_str}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

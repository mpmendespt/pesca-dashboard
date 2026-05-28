#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVER AMANHÃ v3.1 — Inferência ML Corrigida
=============================================
CORREÇÕES desta versão:

  [ESPÉCIE]  Lógica anterior estava invertida e inacessível:
               especie = "Lucio" if score > 35
                       else "Achiga" if score > 55   ← nunca avaliado
                       else "Savel"
             Com o score sempre ~1.3, a recomendação era sempre "Savel"
             (1 captura / 0.60 kg) — a espécie menos representada.

             Lógica corrigida, baseada no histórico real (Capturas.csv):
               Lúcio  → score >= 50  (domina: 6un / 9.88 kg / 5 sessões)
               Carpa  → score >= 30  (melhor pm: 3.00 kg/un)
               Achiga → score >= 15  (condições médias: 1.20 kg/un)
               Savel  → score <  15  (condições fracas: 0.60 kg/un)

  [HORÁRIO]  Anterior: fixo por score (sempre "Fim de tarde" com score ~1.3).
             Corrigido: por espécie, com base em conhecimento de domínio
             confirmado para rede jazida em albufeiras:
               Lúcio  → Madrugada (05h-08h)     — ativo em baixa luminosidade
               Carpa  → Final da tarde (17h-20h) — pico crepuscular
               Achiga → Manhã (08h-11h)          — ativo com água aquecida
               Savel  → Final da tarde (17h-20h) — espécie migratória

  [LUNAR]    calc_lunar() substituído por import do módulo astral já
             integrado em previsao_pesca_v3_1.py. Fallback matemático
             preservado se astral não estiver disponível.

  [PKL]      Lê norm_params do .pkl para incluir contexto de calibração
             no output JSON (max_kg, n_sessoes, data_calibracao).

  [JSON]     Campo 'condicoes_chave' enriquecido com 'Temp_Ar' e 'Humidade'.
             Campo 'norm_params' adicionado para auditoria do score.
             Campo 'nota_ml' actualizado com estado do modelo.
"""

import os
import json
import math
import pickle
import logging
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from config_loader import CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

CAT_COLS = ["estacao", "dia_semana", "fase_lua"]

_CICLO = 29.53058867
_FASES = [
    "Nova", "Crescente I", "Q. Crescente", "Crescente Fim",
    "Cheia", "Minguante I", "Q. Minguante", "Minguante Fim",
]
_EST_MAP = {
    1: "Inverno",  2: "Inverno",  3: "Primavera",
    4: "Primavera",5: "Primavera",6: "Verão",
    7: "Verão",    8: "Verão",    9: "Outono",
    10: "Outono",  11: "Outono",  12: "Inverno",
}

# ==============================================================================
# TABELA DE RECOMENDAÇÃO — baseada no histórico real (Capturas.csv mai-2026)
# Actualizar os thresholds conforme o histórico crescer.
# ==============================================================================
#
#  Espécie | Qtd | Kg total | pm (kg/un) | Sessões | Score típico
#  Lúcio   |  6  |   9.88   |    1.65    |    5    |  >= 50
#  Carpa   |  1  |   3.00   |    3.00    |    1    |  >= 30
#  Achiga  |  1  |   1.20   |    1.20    |    1    |  >= 15
#  Sável   |  1  |   0.60   |    0.60    |    1    |  <  15
#
_REC_TABLE = [
    # (score_min, especie, horario, nota)
    (50, "Lucio",  "Madrugada (05h-08h)",      "pico em baixa luminosidade"),
    (30, "Carpa",  "Final da tarde (17h-20h)",  "pico crepuscular"),
    (15, "Achiga", "Manhã (08h-11h)",           "ativo com água aquecida"),
    ( 0, "Savel",  "Final da tarde (17h-20h)",  "condições fracas"),
]


# ==============================================================================
# MÓDULO LUNAR — astral com fallback matemático
# ==============================================================================

def _calc_lunar_astral(date_str: str) -> "tuple[str, float]":
    """
    Tenta usar astral para fase e iluminação reais.
    Devolve (fase_str, illumination_pct).
    """
    try:
        from astral.moon import phase as _phase
        from datetime import date as _date
        d   = _date.fromisoformat(date_str)
        ph  = _phase(d)
        pos = ph / _CICLO
        illum = round((1 - math.cos(pos * 2 * math.pi)) / 2 * 100, 1)
        fase  = _FASES[min(int(pos * 8), 7)]
        return fase, illum
    except ImportError:
        pass  # cai no fallback

    # Fallback matemático — referência Lua Nova 16-mai-2026 17:00 UTC
    dt  = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    ref = datetime(2026, 5, 16, 17, 0, tzinfo=timezone.utc)
    ph  = (dt - ref).total_seconds() / 86400.0 % _CICLO
    pos = ph / _CICLO
    illum = round((1 - math.cos(pos * 2 * math.pi)) / 2 * 100, 1)
    fase  = _FASES[min(int(pos * 8), 7)]
    return fase, illum


# ==============================================================================
# MÓDULO METEOROLÓGICO — fetch Open-Meteo Forecast
# ==============================================================================

def fetch_tomorrow_features() -> pd.DataFrame:
    """
    Obtém features meteorológicas para amanhã via Open-Meteo Forecast.
    past_days=5 para calcular Tw por média de 5 dias (modelo calibrado).
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  CONFIG["location"]["lat"],
        "longitude": CONFIG["location"]["lon"],
        "daily": [
            "temperature_2m_max", "temperature_2m_min",
            "precipitation_sum", "wind_speed_10m_max",
        ],
        "hourly": ["relative_humidity_2m", "cloudcover", "surface_pressure"],
        "past_days":     5,
        "forecast_days": 2,
        "timezone":      CONFIG["location"]["timezone"],
    }
    r = requests.get(url, params=params, timeout=CONFIG["api"]["timeout_s"])
    r.raise_for_status()
    d = r.json()

    # Tw: média dos últimos 5 dias de temperatura do ar
    past = [
        (mx + mn) / 2
        for mx, mn in zip(
            d["daily"]["temperature_2m_max"][:5],
            d["daily"]["temperature_2m_min"][:5],
        )
        if mx is not None and mn is not None
    ]
    ta_avg = sum(past) / len(past) if past else 16.0
    tw = round(
        CONFIG["water_temp_model"]["tw_slope"] * ta_avg
        + CONFIG["water_temp_model"]["tw_intercept"],
        1,
    )

    # Amanhã = índice 5 (5 dias passados + hoje=idx4, amanhã=idx5)
    idx      = 5
    tomorrow = datetime.now() + timedelta(days=1)

    # Linha horária das 10h de amanhã para humidade/nuvens/pressão
    df_h = pd.DataFrame(d["hourly"])
    df_h["ts"] = pd.to_datetime(df_h["time"])
    row_h = df_h[
        df_h["ts"].dt.strftime("%Y-%m-%d %H:00:00")
        == tomorrow.strftime("%Y-%m-%d 10:00:00")
    ]

    def _safe_hourly(col, default):
        return round(float(row_h.iloc[0][col]), 1) if not row_h.empty else default

    fase, illum = _calc_lunar_astral(tomorrow.strftime("%Y-%m-%d"))
    ta_amanha   = round(
        (d["daily"]["temperature_2m_max"][idx] + d["daily"]["temperature_2m_min"][idx]) / 2, 1
    )

    return pd.DataFrame([{
        "temp_ar":         ta_amanha,
        "temp_agua":       tw,
        "vento_kmh":       float(d["daily"]["wind_speed_10m_max"][idx] or 0.0),
        "pressao":         _safe_hourly("surface_pressure", 1013.0),
        "humidade":        _safe_hourly("relative_humidity_2m", 70.0),
        "chuva_24h":       float(d["daily"]["precipitation_sum"][idx] or 0.0),
        "nuvens":          _safe_hourly("cloudcover", 50.0),
        "nivel_barragem":  115.0,   # substituído pela cascata hidro quando disponível
        "delta_nivel":     0.0,
        "moon_illumination": illum,
        "hora":            10.0,
        "estacao":         _EST_MAP.get(tomorrow.month, "Inverno"),
        "dia_semana":      tomorrow.strftime("%A"),
        "fase_lua":        fase,
        # campos auxiliares para o JSON de output (não entram no modelo)
        "_fase_lua_str":   fase,
        "_illum":          illum,
        "_ta_avg_5d":      round(ta_avg, 1),
        "_tomorrow_str":   tomorrow.strftime("%Y-%m-%d"),
    }])


# ==============================================================================
# MÓDULO DE RECOMENDAÇÃO — lógica corrigida
# ==============================================================================

def recomendar(score: float) -> "tuple[str, str, str, str]":
    """
    Devolve (classificacao, especie, horario, nota_especie)
    com base na tabela _REC_TABLE calibrada pelo histórico real.
    """
    classificacao = (
        "FRACO"     if score < 20 else
        "MODERADO"  if score < 40 else
        "BOM"       if score < 60 else
        "EXCELENTE"
    )
    for score_min, especie, horario, nota in _REC_TABLE:
        if score >= score_min:
            return classificacao, especie, horario, nota

    # Nunca chega aqui, mas por segurança
    return classificacao, "Savel", "Final da tarde (17h-20h)", "fallback"


# ==============================================================================
# INFERÊNCIA PRINCIPAL
# ==============================================================================

def prever():
    # ── 1. Carregar modelo ────────────────────────────────────────────────────
    pkl_path = CONFIG["paths"]["model_pkl"]
    if not os.path.exists(pkl_path):
        logger.error(
            "❌ Modelo não encontrado. Execute treinar_modelo_ml_v3_1.py primeiro."
        )
        return

    with open(pkl_path, "rb") as f:
        model_data = pickle.load(f)

    model         = model_data["model"]
    expected_cols = model_data["feature_names"]
    norm_params   = model_data.get("norm_params", {})
    n_treino      = model_data.get("n_treino", "?")

    logger.info(
        f"🔮 Modelo carregado | n_treino={n_treino} | "
        f"max_kg={norm_params.get('max_kg','?')} | "
        f"calibrado em {norm_params.get('data_calibracao','?')}"
    )

    # ── 2. Obter features de amanhã ───────────────────────────────────────────
    logger.info("🔮 A obter condições previstas para amanhã...")
    df_raw = fetch_tomorrow_features()

    # Separar colunas auxiliares (prefixo _) antes de entrar no modelo
    aux_cols = [c for c in df_raw.columns if c.startswith("_")]
    aux      = df_raw[aux_cols].iloc[0].to_dict()
    df_feat  = df_raw.drop(columns=aux_cols)

    # ── 3. Inferência — mesma transformação do treino ─────────────────────────
    X_new = pd.get_dummies(df_feat, columns=CAT_COLS, drop_first=False)
    X_new = X_new.reindex(columns=expected_cols, fill_value=0.0)

    try:
        score = float(model.predict(X_new)[0])
    except Exception as e:
        logger.error(f"❌ Falha na previsão: {e}")
        return

    score = round(max(0.0, min(100.0, score)), 1)

    # ── 4. Recomendação corrigida ─────────────────────────────────────────────
    classificacao, especie, horario, nota_esp = recomendar(score)

    # ── 5. Alertas de condições desfavoráveis ─────────────────────────────────
    alertas = []
    vento  = float(df_feat["vento_kmh"].iloc[0])
    chuva  = float(df_feat["chuva_24h"].iloc[0])
    tw     = float(df_feat["temp_agua"].iloc[0])
    if score  < CONFIG["thresholds"].get("pressao_limiar_pico", 20):
        alertas.append("Score baixo — condições desfavoráveis")
    if vento  > CONFIG["thresholds"]["limiar_vento"]:
        alertas.append(f"Vento forte ({vento:.0f} km/h > {CONFIG['thresholds']['limiar_vento']})")
    if chuva  > CONFIG["thresholds"]["limiar_chuva"]:
        alertas.append(f"Chuva intensa ({chuva:.1f} mm > {CONFIG['thresholds']['limiar_chuva']})")
    if tw     < CONFIG["thresholds"]["limiar_frio"]:
        alertas.append(f"Água fria (Tw={tw}°C < {CONFIG['thresholds']['limiar_frio']}°C)")

    # ── 6. Construir output JSON ──────────────────────────────────────────────
    output = {
        "data_alvo":           aux["_tomorrow_str"],
        "score_previsto":      score,
        "classificacao":       classificacao,
        "especie_recomendada": especie,
        "melhor_horario":      horario,
        "nota_especie":        nota_esp,
        "alertas":             alertas,
        "condicoes_chave": {
            "Tw":         tw,
            "Temp_Ar":    float(df_feat["temp_ar"].iloc[0]),
            "Chuva_24h":  chuva,
            "Humidade":   float(df_feat["humidade"].iloc[0]),
            "Lua":        f"{aux['_fase_lua_str']} ({aux['_illum']}%)",
            "Vento_Max":  vento,
            "Ta_Media_5d": aux["_ta_avg_5d"],
        },
        "norm_params": norm_params,
        "nota_ml": (
            f"Modelo v3.1 | n_treino={n_treino} | "
            f"max_kg={norm_params.get('max_kg','?')} kg | "
            f"Use como referência complementar."
        ),
    }

    # ── 7. Print sumário ──────────────────────────────────────────────────────
    sep = "=" * 57
    print(f"\n{sep}")
    print(f"🎣  PREVISÃO v3.1 PARA {output['data_alvo']}")
    print(sep)
    print(f"📊  Score ML   : {score}/100  ({classificacao})")
    print(f"🐟  Espécie    : {especie}  —  {nota_esp}")
    print(f"⏰  Horário    : {horario}")
    print(f"🌡️  Tw         : {tw}°C  (Ta_5d={aux['_ta_avg_5d']}°C)")
    print(f"🌧️  Chuva      : {chuva} mm  |  💨 Vento: {vento} km/h")
    print(f"🌙  Lua        : {aux['_fase_lua_str']} ({aux['_illum']}%)")
    if alertas:
        print(f"⚠️  Alertas:")
        for a in alertas:
            print(f"    • {a}")
    print(f"{sep}\n")

    # ── 8. Exportar JSON ──────────────────────────────────────────────────────
    json_path = "previsao_amanha.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Previsão exportada para {json_path}")


if __name__ == "__main__":
    prever()

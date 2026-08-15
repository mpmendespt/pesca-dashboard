#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TREINO ML v3.1 - Robusto, ignora interrupções, get_dummies estável"""
import os, sqlite3, logging, pickle, warnings
import pandas as pd, numpy as np
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error
from config_loader import CONFIG

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

CAT_COLS = ['estacao', 'dia_semana', 'fase_lua']

def treinar():
    logger.info("🚀 Pipeline ML v3.1 | Ignorando dias de interrupção...")
    conn = sqlite3.connect(CONFIG["paths"]["db_sqlite"])
    query = """
        SELECT m.datetime, m.temp_ar, m.temp_agua, m.vento_kmh, m.pressao, m.humidade,
               m.chuva_24h, m.nuvens, m.hora, h.nivel_barragem, h.delta_24h as delta_nivel,
               l.moon_illumination, m.estacao, m.dia_semana, l.fase_lua, c.sucesso_score
        FROM meteo m
        JOIN hidro h ON m.datetime = h.datetime
        JOIN lunar l ON m.datetime = l.datetime
        LEFT JOIN capturas c ON DATE(c.datetime) = DATE(m.datetime)
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # Sanitização & Filtro de Interrupções
    num_cols = ['temp_ar','temp_agua','vento_kmh','pressao','humidade','chuva_24h','nuvens',
                'hora','nivel_barragem','delta_nivel','moon_illumination','sucesso_score']
    for c in num_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
    df['sucesso_score'] = df['sucesso_score'].fillna(0.0)
    
    # Ignora dias de interrupcao (set de dates — suporta dias simples e periodos)
    df['dia_obj'] = pd.to_datetime(df['datetime']).dt.date
    interr = CONFIG["fishing_calendar"]["interruptions"]  # set[date] expandido
    df = df[~df['dia_obj'].isin(interr)].drop(columns=['dia_obj'])
    df = df.dropna(subset=['temp_ar']) # Remove meteo corrompido/faltante

    if len(df) < 4:
        return logger.warning(f"⚠️ Dataset insuficiente após filtragem: {len(df)} registos.")

    y = df['sucesso_score']
    X = df.drop(columns=['datetime', 'sucesso_score'])

    # ✅ Codificação estável (evita bugs do sklearn)
    X_enc = pd.get_dummies(X, columns=CAT_COLS, drop_first=False)
    feature_names = X_enc.columns.tolist()

    model = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(X_enc, y)

    y_pred = model.predict(X_enc)
    r2 = r2_score(y, y_pred)
    logger.info(f"📊 Treino v3.1 concluído: R²={r2:.3f} | RMSE={np.sqrt(mean_squared_error(y,y_pred)):.2f} | n={len(df)}")

    with open(CONFIG["paths"]["model_pkl"], 'wb') as f:
        pickle.dump({'model': model, 'feature_names': feature_names, 'date': datetime.now().isoformat()}, f)
    logger.info(f"✅ Modelo guardado em {CONFIG['paths']['model_pkl']}")

if __name__ == "__main__":
    treinar()
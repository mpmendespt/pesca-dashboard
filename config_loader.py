#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""config_loader.py - Carregador centralizado para v3.1"""
import json, os
from datetime import datetime, date

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config_v3_1.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"❌ config_v3_1.json não encontrado em: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    
    # Remove espaços acidentais nas chaves (compatibilidade com edição manual)
    cfg = {k.strip(): v for k, v in raw.items()}
    for section in ["location", "fishing_calendar", "thresholds", "water_temp_model", "api", "paths", "logging"]:
        if section in cfg: cfg[section] = {k.strip(): v for k, v in cfg[section].items()}
        
    cfg["fishing_calendar"]["start_date"] = datetime.strptime(cfg["fishing_calendar"]["start_date"].strip(), "%Y-%m-%d").date()
    cfg["fishing_calendar"]["interruptions"] = [
        datetime.strptime(d.strip(), "%Y-%m-%d").date() for d in cfg["fishing_calendar"]["interruptions"]
    ]
    return cfg

CONFIG = load_config()

def is_fishing_day(dt=None):
    """Verifica se o dia é válido para pesca (pós-início e não interrompido)."""
    if dt is None: dt = date.today()
    if dt < CONFIG["fishing_calendar"]["start_date"]: return False
    return dt not in CONFIG["fishing_calendar"]["interruptions"]
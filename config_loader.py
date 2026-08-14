#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""config_loader.py - Carregador centralizado para v3.1"""
import json, os
from datetime import datetime, date, timedelta

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config_v3_1.json")

def expandir_interruptions(raw_list: list) -> set:
    """
    Expande a lista de interruptions do config para um set de dates.

    Formatos aceites:
      - "YYYY-MM-DD"                              : dia unico
      - {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}: periodo fechado (inclusivo)
      - {"from": "YYYY-MM-DD"}                    : periodo aberto (from ate hoje)
    """
    hoje = date.today()
    resultado = set()

    for item in raw_list:
        if isinstance(item, str):
            try:
                resultado.add(datetime.strptime(item.strip(), "%Y-%m-%d").date())
            except ValueError:
                pass  # data invalida ignorada silenciosamente

        elif isinstance(item, dict):
            from_raw = item.get("from", "").strip()
            to_raw   = item.get("to",   "").strip()
            if not from_raw:
                continue
            try:
                d_from = datetime.strptime(from_raw, "%Y-%m-%d").date()
                d_to   = datetime.strptime(to_raw,   "%Y-%m-%d").date() if to_raw else hoje
                if d_from > d_to:
                    d_from, d_to = d_to, d_from   # tolerancia: inverter se necessario
                current = d_from
                while current <= d_to:
                    resultado.add(current)
                    current += timedelta(days=1)
            except ValueError:
                pass  # periodo invalido ignorado silenciosamente

    return resultado


def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"config_v3_1.json nao encontrado em: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Remove espacos acidentais nas chaves
    cfg = {k.strip(): v for k, v in raw.items()}
    for section in ["location", "fishing_calendar", "thresholds",
                    "water_temp_model", "api", "paths", "logging"]:
        if section in cfg:
            cfg[section] = {k.strip(): v for k, v in cfg[section].items()}

    cfg["fishing_calendar"]["start_date"] = datetime.strptime(
        cfg["fishing_calendar"]["start_date"].strip(), "%Y-%m-%d"
    ).date()

    # Expandir interruptions (suporta dias simples E periodos)
    cfg["fishing_calendar"]["interruptions"] = expandir_interruptions(
        cfg["fishing_calendar"].get("interruptions", [])
    )
    return cfg

CONFIG = load_config()

def is_fishing_day(dt=None):
    """Verifica se o dia e valido para pesca (pos-inicio e nao interrompido)."""
    if dt is None: dt = date.today()
    if dt < CONFIG["fishing_calendar"]["start_date"]: return False
    return dt not in CONFIG["fishing_calendar"]["interruptions"]
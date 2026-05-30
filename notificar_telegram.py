#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notificar_telegram.py v3.2 (Rich Format)
Lê previsao_amanha.json e envia alerta formatado para o Telegram.
Compatível com Session 0, variáveis de ambiente, e fallback seguro.
"""
import os, sys, json, logging, requests
from pathlib import Path
from dotenv import load_dotenv
# No topo de cada script (após imports)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.logging_setup import setup_pipeline_logger

logger = setup_pipeline_logger(name="notificar_telegram.py")  # Mude o 'name' por script se quiser

# logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
                    # handlers=[logging.StreamHandler(sys.stdout)])
# logger = logging.getLogger("telegram_notifier")

# Carrega .env se existir (para CLI/Task Scheduler)
load_dotenv(Path(__file__).resolve().parent / ".env")

def get_credentials():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("⚠️ Credenciais Telegram ausentes. Notificação ignorada.")
        return None, None
    return token, chat_id

def send_telegram_message(text: str, parse_mode="HTML"):
    token, chat_id = get_credentials()
    if not token or not chat_id: return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("✅ Alerta Telegram enviado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"❌ Erro Telegram (HTML): {e}")
        # Fallback texto puro
        payload["parse_mode"] = None
        try:
            requests.post(url, json=payload, timeout=10).raise_for_status()
            return True
        except Exception as e2:
            logger.error(f"❌ Falha total: {e2}"); return False

def format_message(data: dict) -> str:
    score = data.get("score", 50)
    classe = str(data.get("classe", "DESCONHECIDO")).upper()
    data_prev = data.get("data", "Amanhã")
    especie = data.get("especie_alvo", "—")
    horario = data.get("horario", "—")
    tw = data.get("tw", "—")
    chuva = data.get("chuva", "—")
    lua_fase = data.get("lua_fase", "—")
    lua_pct = data.get("lua_pct", "—")
    vento = data.get("vento", "—")
    local = data.get("local", "Barragem Castelo de Bode")
    modelo = data.get("modelo", "v3.1")

    # Formatação segura
    tw_str = f"{tw}°C" if isinstance(tw, (int, float)) else tw
    chuva_str = f"{chuva}mm" if isinstance(chuva, (int, float)) else chuva
    vento_str = f"{vento} km/h" if isinstance(vento, (int, float)) else vento
    lua_str = f"{lua_fase} ({lua_pct}%)" if isinstance(lua_pct, (int, float)) else lua_fase

    msg = f"📅 Data: {data_prev}\n"
    msg += f"📊 Score: {score}/100 ({classe})\n"
    if especie != "—": msg += f"🐟 Espécie: {especie} | ⏰ {horario}\n"
    if tw != "—": msg += f"🌡️ Tw: {tw_str} | 🌧️ Chuva: {chuva_str}\n"
    if lua_fase != "—": msg += f"🌙 Lua: {lua_str} | 💨 Vento: {vento_str}\n"

    # Alertas dinâmicos
    alertas = []
    if isinstance(score, (int, float)) and score < 20:
        alertas.append("⚠️ ALERTA: Score muito baixo (<20)")
    if isinstance(vento, (int, float)) and vento > 35:
        alertas.append("💨 Vento Forte (>35km/h)")
    if isinstance(chuva, (int, float)) and chuva > 15:
        alertas.append("🌧️ Chuva Intensa (>15mm)")

    if alertas:
        msg = f"🚨 CONDIÇÕES DESFAVORÁVEIS 🚨\n{msg}\n" + "\n".join(alertas)
    else:
        msg = f"✅ Condições favoráveis previstas.\n{msg}"

    msg += f"\n\n💡 Modelo {modelo} | {local}"
    return msg

def main():
    # Tenta data/ primeiro, depois raiz
    json_path = Path(__file__).resolve().parent / "data" / "previsao_amanha.json"
    if not json_path.exists():
        json_path = Path(__file__).resolve().parent / "previsao_amanha.json"
    if not json_path.exists():
        logger.info("ℹ️ previsao_amanha.json não encontrado. Ignorando.")
        return
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON inválido: {e}"); return

    msg = format_message(data)
    logger.info("📤 A enviar notificação...")
    send_telegram_message(msg)

if __name__ == "__main__":
    main()
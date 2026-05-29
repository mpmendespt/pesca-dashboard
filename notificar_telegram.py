#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notificar_telegram.py v3.1 (Seguro)
Lê previsao_amanha.json e envia alerta para o Telegram.
O Token é carregado via Variáveis de Ambiente (NUNCA no código).
"""
import os
import sys
import json
import logging
import requests
from pathlib import Path
from datetime import datetime

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("telegram_notifier")

def get_credentials():
    """
    Cadeia de resolução segura: 
    1. Variáveis de Ambiente do SO (Task Scheduler / Windows)
    2. Fallback .env (apenas se python-dotenv estiver instalado)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    # Fallback opcional para desenvolvimento local
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        except ImportError:
            pass
            
    if not token or not chat_id:
        logger.warning("⚠️ Credenciais Telegram não encontradas (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        return None, None
    return token, chat_id

def send_telegram_message(text: str, parse_mode="HTML"):
    """Envia mensagem formatada via API do Telegram."""
    token, chat_id = get_credentials()
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("✅ Alerta Telegram enviado com sucesso.")
        return True
    except Exception as e:
        # Fallback para texto puro se HTML falhar
        logger.error(f"❌ Erro ao enviar Telegram (HTML): {e}")
        logger.info("⚠️ A tentar reenvio em modo Texto Puro...")
        payload["parse_mode"] = None
        try:
            requests.post(url, json=payload, timeout=10).raise_for_status()
            return True
        except Exception as e2:
            logger.error(f"❌ Falha total no envio: {e2}")
            return False

def main():
    """Lê previsão e decide se notifica."""
    # Caminho relativo seguro
    base_dir = Path(__file__).resolve().parent
    json_path = base_dir / "previsao_amanha.json"
    
    if not json_path.exists():
        logger.info("ℹ️ previsao_amanha.json não encontrado. A ignorar.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            logger.error("❌ JSON inválido em previsao_amanha.json")
            return

    score = data.get("score", 50)
    classe = data.get("classe", "DESCONHECIDO")
    data_prev = data.get("data", "Amanhã")
    
    # Construir mensagem
    msg = (
        f"🎣 <b>Previsão Pesca - {data_prev}</b>\n"
        f"📊 Score: <b>{score}/100</b>\n"
        f"🏷️ Classificação: <b>{classe}</b>"
    )
    
    # Adicionar detalhes se houver
    if "melhor_horario" in data:
        msg += f"\n⏰ Melhor Horário: {data['melhor_horario']}"
    
    if "especie_alvo" in data:
        msg += f"\n🐟 Espécie Alvo: {data['especie_alvo']}"

    # Alertas críticos
    alertas = []
    if score < 20: alertas.append("⚠️ <b>Condições Desfavoráveis</b>")
    if data.get("vento_max", 0) > 35: alertas.append("💨 Vento Forte (>35km/h)")
    if data.get("chuva_total", 0) > 15: alertas.append("🌧️ Chuva Intensa (>15mm)")
    
    if alertas:
        msg += "\n" + "\n".join(alertas)

    logger.info(f"📤 A enviar notificação (Score: {score})...")
    send_telegram_message(msg)

if __name__ == "__main__":
    main()
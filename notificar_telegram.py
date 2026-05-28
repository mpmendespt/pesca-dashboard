#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NOTIFICAÇÃO TELEGRAM v3.1 - Corrigido: escape HTML + fallback seguro"""
import os, json, requests, logging, html
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# 🔑 SUBSTITUA PELAS SUAS CREDENCIAIS
BOT_TOKEN = "5862376391:AAFA7QvTlZfVe1hTtly1Bj9lg7kKI4OnT80"
CHAT_ID   = "5273969582"  # Pode ser número (int) ou string
API_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
JSON_PATH = "previsao_amanha.json"

def escape_html(text):
    """Escapa caracteres especiais para parse_mode=HTML do Telegram."""
    if text is None: return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

def enviar_mensagem(texto, parse_mode="HTML"):
    """Envia mensagem com retry simples e logging de erro detalhado."""
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": parse_mode}
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        if r.status_code == 200 and r.json().get("ok"):
            logger.info("✅ Notificação enviada com sucesso.")
            return True
        else:
            err = r.json().get("description", "Erro desconhecido")
            logger.error(f"❌ Falha ao enviar ({r.status_code}): {err}")
            # Fallback: tentar sem parse_mode (texto puro)
            if parse_mode == "HTML":
                logger.info("🔄 Tentando fallback em texto puro...")
                payload["parse_mode"] = None
                r2 = requests.post(API_URL, json=payload, timeout=10)
                if r2.status_code == 200 and r2.json().get("ok"):
                    logger.info("✅ Fallback em texto puro funcionou.")
                    return True
            return False
    except Exception as e:
        logger.error(f"❌ Exceção ao enviar: {e}")
        return False

def gerar_notificacao():
    if not os.path.exists(JSON_PATH):
        msg = "<b>⚠️ Previsão ML indisponível</b>\nO ficheiro previsao_amanha.json não foi gerado."
        return enviar_mensagem(msg)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        prev = json.load(f)

    score = prev.get("score_previsto", 0)
    vento = prev.get("condicoes_chave", {}).get("Vento_Max", 0)
    data  = prev.get("data_alvo", "Desconhecida")
    esp   = prev.get("especie_recomendada", "-")
    hor   = prev.get("melhor_horario", "-")
    tw    = prev.get("condicoes_chave", {}).get("Tw", "-")
    chuva = prev.get("condicoes_chave", {}).get("Chuva_24h", 0)
    lua_raw = prev.get("condicoes_chave", {}).get("Lua", "-")
    
    # ✅ ESCAPAR caracteres HTML na descrição da Lua (ex: "Crescente Fim (87.0%)")
    lua = escape_html(lua_raw)

    # 🚨 Lógica de Alertas
    alertas = []
    if score < 20: alertas.append("Score muito baixo (&lt;20)")
    if vento > 35: alertas.append("Vento perigoso (&gt;35 km/h)")
    if chuva > 15: alertas.append("Chuva intensa (&gt;15 mm)")
    
    alerta_txt = "<br>".join([f"<b>⚠️ ALERTA:</b> {a}" for a in alertas])
    header = "🚨 <b>CONDIÇÕES DESFAVORÁVEIS</b> 🚨" if alertas else "🎣 <b>Previsão Diária</b>"

    # ✅ Mensagem com HTML válido e caracteres escapados
    msg = f"""{header}
📅 <b>Data:</b> {escape_html(data)}
📊 <b>Score:</b> {score}/100
🐟 <b>Espécie:</b> {escape_html(esp)} | ⏰ {escape_html(hor)}
🌡️ <b>Tw:</b> {tw}°C | 🌧️ Chuva: {chuva}mm
🌙 <b>Lua:</b> {lua} | 💨 Vento: {vento} km/h
{alerta_txt if alertas else "✅ Condições dentro dos parâmetros normais."}

💡 <i>Modelo v3.1 | Barragem Castelo de Bode</i>"""

    enviar_mensagem(msg)

if __name__ == "__main__":
    # Teste rápido de credenciais (opcional)
    if "SEU_BOT_TOKEN" in BOT_TOKEN or "SEU_CHAT_ID" in str(CHAT_ID):
        logger.error("❌ Configure BOT_TOKEN e CHAT_ID em notificar_telegram.py primeiro.")
    else:
        gerar_notificacao()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notificar_telegram.py v3.3
Lê previsao_amanha.json e envia alerta formatado para o Telegram.

Compatível com AMBOS os formatos de JSON:
  Formato A (prever_amanha_v3_1.py actual):
    score_previsto, data_alvo, classificacao, especie_recomendada,
    melhor_horario, condicoes_chave.{Tw, Chuva_24h, Vento_Max, Lua}, alertas

  Formato B (prever_amanha legacy / fallback):
    score, data, classe, especie_alvo, horario,
    tw, chuva, vento, lua_fase, lua_pct

Credenciais via .env ou variáveis de ambiente:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""
import os, json, logging, requests
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("telegram_notifier")

# Carregar .env se existir (para CLI / Task Scheduler)
load_dotenv(Path(__file__).resolve().parent / ".env")

# Caminhos possíveis do JSON (raiz e data/)
_BASE = Path(__file__).resolve().parent
JSON_PATHS = [
    _BASE / "previsao_amanha.json",
    _BASE / "data" / "previsao_amanha.json",
]

# Limiares (devem coincidir com config_v3_1.json)
_LIM_SCORE = 20
_LIM_VENTO = 35
_LIM_CHUVA = 15


# ── Credenciais ───────────────────────────────────────────────────────────────

def get_credentials() -> tuple:
    """
    Prioridade: st.secrets (Cloud) → .env / variáveis de ambiente.
    Devolve (token, chat_id) ou (None, None).
    """
    try:
        import streamlit as st
        token   = st.secrets["telegram"]["bot_token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        if token and chat_id:
            return str(token), str(chat_id)
    except Exception:
        pass

    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID",   "").strip()
    if token and chat_id:
        return token, chat_id

    logger.error("Credenciais Telegram nao encontradas "
                 "(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
    return None, None


# ── Envio ─────────────────────────────────────────────────────────────────────

def enviar_mensagem(texto: str, parse_mode: str = "HTML") -> bool:
    token, chat_id = get_credentials()
    if not token:
        return False

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id":                  chat_id,
        "text":                     texto,
        "parse_mode":               parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200 and r.json().get("ok"):
            logger.info("Alerta Telegram enviado com sucesso.")
            return True
        err = r.json().get("description", "Erro desconhecido")
        logger.error(f"Falha ao enviar ({r.status_code}): {err}")
        # Fallback sem parse_mode
        payload["parse_mode"] = None
        r2 = requests.post(url, json=payload, timeout=10)
        if r2.status_code == 200 and r2.json().get("ok"):
            logger.info("Fallback texto puro funcionou.")
            return True
        return False
    except Exception as e:
        logger.error(f"Excepcao ao enviar: {e}")
        return False


# ── Normalização do JSON ──────────────────────────────────────────────────────

def normalizar(prev: dict) -> dict:
    """
    Normaliza qualquer formato de previsao_amanha.json para um dict
    com chaves canónicas:
      score, data, classificacao, especie, horario,
      tw, chuva, vento, lua, alertas_lista
    """
    # ── Formato A: prever_amanha_v3_1.py actual ───────────────────────────────
    if "score_previsto" in prev:
        ck = prev.get("condicoes_chave", {})
        alertas_raw = prev.get("alertas", [])
        # alertas pode ser lista de strings ou lista vazia
        if isinstance(alertas_raw, list):
            alertas = alertas_raw
        else:
            alertas = []

        score = float(prev.get("score_previsto", 0))
        vento = float(ck.get("Vento_Max", 0))
        chuva = float(ck.get("Chuva_24h", 0))

        # Gerar alertas automáticos se a lista vier vazia
        if not alertas:
            if score < _LIM_SCORE: alertas.append(f"Score baixo ({score:.0f}/100)")
            if vento > _LIM_VENTO: alertas.append(f"Vento perigoso ({vento:.0f} km/h)")
            if chuva > _LIM_CHUVA: alertas.append(f"Chuva intensa ({chuva:.0f} mm)")

        return {
            "score":          score,
            "data":           prev.get("data_alvo", "—"),
            "classificacao":  prev.get("classificacao", "—"),
            "especie":        prev.get("especie_recomendada", "—"),
            "horario":        prev.get("melhor_horario", "—"),
            "tw":             ck.get("Tw", "—"),
            "chuva":          chuva,
            "vento":          vento,
            "lua":            ck.get("Lua", "—"),
            "alertas_lista":  alertas,
        }

    # ── Formato B: prever_amanha legacy (score, classe, data…) ───────────────
    lua_fase = prev.get("lua_fase", "—")
    lua_pct  = prev.get("lua_pct", "")
    lua_str  = f"{lua_fase} ({lua_pct}%)" if lua_pct != "" else lua_fase

    score = float(prev.get("score", 0))
    vento = float(prev.get("vento", 0))
    chuva = float(prev.get("chuva", 0))

    alertas = []
    if score < _LIM_SCORE: alertas.append(f"Score baixo ({score:.0f}/100)")
    if vento > _LIM_VENTO: alertas.append(f"Vento perigoso ({vento:.0f} km/h)")
    if chuva > _LIM_CHUVA: alertas.append(f"Chuva intensa ({chuva:.0f} mm)")

    return {
        "score":         score,
        "data":          prev.get("data", "—"),
        "classificacao": prev.get("classe", prev.get("classificacao", "—")),
        "especie":       prev.get("especie_alvo", prev.get("especie_recomendada", "—")),
        "horario":       prev.get("horario", prev.get("melhor_horario", "—")),
        "tw":            prev.get("tw", "—"),
        "chuva":         chuva,
        "vento":         vento,
        "lua":           lua_str,
        "alertas_lista": alertas,
    }


# ── Formatação da mensagem ────────────────────────────────────────────────────

def _esc(text) -> str:
    """Escapa caracteres HTML para o Telegram."""
    if text is None: return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def formatar_mensagem(p: dict) -> str:
    """
    Constrói a mensagem HTML para o Telegram a partir do dict normalizado.
    """
    score         = p["score"]
    classificacao = p["classificacao"].upper()
    alertas       = p["alertas_lista"]

    # Cabeçalho dinâmico
    if alertas:
        header = "🚨 <b>CONDIÇÕES DESFAVORÁVEIS</b> 🚨"
    elif score >= 60:
        header = "🌟 <b>Boas condições de pesca!</b>"
    else:
        header = "🎣 <b>Previsão Diária</b>"

    # Linha de alertas (se houver)
    alertas_html = ""
    if alertas:
        linhas = [f"<b>⚠️ ALERTA:</b> {_esc(a)}" for a in alertas]
        alertas_html = "\n" + "\n".join(linhas)
    else:
        alertas_html = "\n✅ Condições dentro dos parâmetros normais."

    # Score com classificação
    score_str = f"{score:.1f}" if score != int(score) else f"{int(score)}"

    msg = (
        f"{header}\n"
        f"📅 <b>Data:</b> {_esc(p['data'])}\n"
        f"📊 <b>Score:</b> {score_str}/100 ({_esc(classificacao)})\n"
        f"🐟 <b>Espécie:</b> {_esc(p['especie'])} | "
        f"⏰ {_esc(p['horario'])}\n"
        f"🌡️ <b>Tw:</b> {_esc(p['tw'])}°C | "
        f"🌧️ Chuva: {p['chuva']}mm\n"
        f"🌙 <b>Lua:</b> {_esc(p['lua'])} | "
        f"💨 Vento: {p['vento']} km/h"
        f"{alertas_html}\n\n"
        f"💡 <i>Modelo v3.1 | Barragem Castelo de Bode</i>"
    )
    return msg


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    # Encontrar o JSON (raiz tem prioridade sobre data/)
    json_path = None
    for p in JSON_PATHS:
        if p.exists():
            json_path = p
            break

    if json_path is None:
        logger.warning("previsao_amanha.json nao encontrado. Ignorando.")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON invalido: {e}")
        return

    logger.info(f"A ler: {json_path}")

    dados = normalizar(prev)
    msg   = formatar_mensagem(dados)

    logger.info(f"Score: {dados['score']} | {dados['classificacao']} | "
                f"Especie: {dados['especie']}")
    logger.info("A enviar notificacao...")
    enviar_mensagem(msg)


if __name__ == "__main__":
    main()

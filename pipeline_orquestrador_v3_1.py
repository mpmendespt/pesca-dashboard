#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIPELINE ORQUESTRADOR v3.1 (Completo: ML + PDF + Sync Dashboard)
Local de Execução: D:\_WORK_\work_python_and_R\___WORK5___\Weather5\
Sequência: Snapshot → Treino → Previsão → Telegram → PDF → Sync Dashboard
"""
import subprocess
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# 🔑 Definição de Caminhos Base
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))  # Weather5
DASHBOARD_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca")

# Configuração de Logging (escreve na mesma pasta do script)
LOG_FILE = BASE_DIR / "automacao_orquestrador.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("orquestrador_v3.1")

# 📋 Sequência Obrigatória de Execução
# Nota: scripts 1-5 residem em BASE_DIR (Weather5)
#       script 6 reside em DASHBOARD_DIR (caminho absoluto para evitar conflitos de cwd)
PIPELINE_STEPS = [
    {"name": "1/6 Snapshot Meteo/Lunar/Hidro", "script": BASE_DIR / "previsao_pesca_v3_1.py"},
    {"name": "2/6 Treino ML",                  "script": BASE_DIR / "treinar_modelo_ml_v3_1.py"},
    {"name": "3/6 Previsão ML (JSON)",         "script": BASE_DIR / "prever_amanha_v3_1.py"},
    {"name": "4/6 Notificação Telegram",       "script": BASE_DIR / "notificar_telegram.py"},
    {"name": "5/6 Geração PDF v2.10",          "script": BASE_DIR / "previsao_pesca_v2_10.py"},
    {"name": "6/6 Sync Dashboard Data",        "script": DASHBOARD_DIR / "sync_dados_dashboard.py"},
]

def main():
    logger.info("="*60)
    logger.info("🚀 INICIANDO PIPELINE ORQUESTRADOR v3.1")
    logger.info(f"📍 Diretório Base: {BASE_DIR}")
    logger.info(f"🌐 Python: {sys.executable}")
    
    python_exe = sys.executable

    for step in PIPELINE_STEPS:
        script_path = step["script"]
        logger.info(f"▶️ A executar: {step['name']}")
        logger.info(f"   📄 {script_path}")
        
        if not script_path.exists():
            logger.error(f"❌ Ficheiro não encontrado: {script_path}")
            sys.exit(1)
            
        try:
            # Executa sequencialmente, herdando variáveis de ambiente do .bat
            result = subprocess.run(
                [python_exe, str(script_path)],
                cwd=str(script_path.parent),  # Garante que cada script corre na sua pasta
                capture_output=False,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.warning(f"⚠️ {step['name']} terminou com código {result.returncode}")
            else:
                logger.info(f"✅ {step['name']} concluído com sucesso.")
                
        except Exception as e:
            logger.error(f"❌ Exceção ao executar {step['name']}: {e}")
            
        logger.info("-" * 60)

    logger.info("🏁 PIPELINE v3.1 FINALIZADO. Todos os passos concluídos.")
    logger.info("="*60)
    sys.exit(0)

if __name__ == "__main__":
    main()
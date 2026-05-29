#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIPELINE ORQUESTRADOR v3.1.1
Executa os 6 módulos em sequência obrigatória:
1. Snapshot -> 2. Treino ML -> 3. Previsão -> 4. Telegram -> 5. PDF -> 6. Sync Dashboard
"""
import subprocess
import sys
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("orquestrador_v3_1")

# 🔒 Lista oficial de scripts (ordem de execução crítica)
SCRIPTS = [
    "previsao_pesca_v3_1.py",          # 1. Snapshot meteo/lunar/hidro → SQLite
    "treinar_modelo_ml_v3_1.py",       # 2. Treino/Retreino → modelo .pkl
    "prever_amanha_v3_1.py",           # 3. Inferência ML → previsao_amanha.json
    "notificar_telegram.py",           # 4. Alerta/Resumo via Telegram
    "previsao_pesca_v2_10.py",         # 🆕 5. Geração PDF 4 págs + histórico CSV + Excel
    "sync_dados_dashboard.py"          # 🆕 6. Cópia unidirecional → pesca-dashboard/data/
]

def main():
    python_exe = sys.executable
    logger.info(f"🚀 Iniciando Orquestrador v3.1.1 | Python: {python_exe}")
    
    # Garante que estamos na pasta onde o script está guardado
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for i, script in enumerate(SCRIPTS, 1):
        if not os.path.exists(script):
            logger.error(f"❌ Script obrigatório não encontrado: {script}")
            sys.exit(1)
            
        logger.info(f"▶️ [{i}/{len(SCRIPTS)}] A executar: {script}")
        # capture_output=False redireciona stdout/stderr para o terminal (e depois para o .log do .bat)
        result = subprocess.run([python_exe, script], capture_output=False, text=True)
        
        if result.returncode != 0:
            logger.warning(f"⚠️ {script} terminou com código {result.returncode} (não crítico)")
        else:
            logger.info(f"✅ {script} concluído com sucesso.")
        logger.info("-" * 45)

    logger.info("🏁 Pipeline v3.1.1 finalizado (6 módulos). A sair...")
    sys.exit(0)

if __name__ == "__main__":
    main()
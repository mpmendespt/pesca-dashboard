#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PIPELINE ORQUESTRADOR v3.1 - Executa os 4 módulos em sequência"""
import subprocess
import sys
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("orquestrador_v3.1")

# Lista de scripts na ordem obrigatória de execução
SCRIPTS = [
    "previsao_pesca_v3_1.py",
    "treinar_modelo_ml_v3_1.py",
    "prever_amanha_v3_1.py",
    "notificar_telegram.py"
]

def main():
    # Usa exatamente o mesmo Python que invocou este script (Conda Pesquisas)
    python_exe = sys.executable
    logger.info(f"🚀 Iniciando Orquestrador v3.1 | Python: {python_exe}")
    
    # Garante que estamos na pasta correta
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for script in SCRIPTS:
        if not os.path.exists(script):
            logger.error(f"❌ Script não encontrado: {script}")
            sys.exit(1)
            
        logger.info(f"▶️ A executar: {script}")
        # Executa e aguarda término limpo
        result = subprocess.run([python_exe, script], capture_output=False, text=True)
        
        if result.returncode != 0:
            logger.warning(f"⚠️ {script} terminou com código {result.returncode}")
        else:
            logger.info(f"✅ {script} concluído com sucesso.")
        logger.info("-" * 40)

    logger.info("🏁 Pipeline v3.1 finalizado. A sair...")
    sys.exit(0)

if __name__ == "__main__":
    main()
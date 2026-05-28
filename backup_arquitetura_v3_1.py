#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKUP ARQUITETURA v3.1
Copia todos os ficheiros do sistema para a pasta 'Backup3'.
Usa apenas bibliotecas padrão do Python. Compatível com Windows.
"""
import os
import shutil
from datetime import datetime

# Diretório base (onde este script está guardado)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "Backup3")

# Lista oficial da arquitetura v3.1
FILES_TO_BACKUP = [
    "config_v3_1.json",
    "config_loader.py",
    "previsao_pesca_v3_1.py",
    "treinar_modelo_ml_v3_1.py",
    "prever_amanha_v3_1.py",
    "notificar_telegram.py",
    "pipeline_orquestrador_v3_1.py",
    "run_pesca_v3_1_automated.bat",
    "previsao_pesca_v2_10.py",
    "previsao_pesca_ml_v3.db",
    "modelo_pesca_v3_robusto.pkl",
    "previsao_amanha.json",
    "Capturas.csv",
    "automacao_v3.1.log"
]

def criar_backup():
    print("📦 Iniciando backup da arquitetura v3.1...")
    os.makedirs(BACKUP_DIR, exist_ok=True)

    copied = 0
    skipped = 0
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_log = os.path.join(BACKUP_DIR, f"backup_log_{timestamp}.txt")

    with open(backup_log, "w", encoding="utf-8") as log:
        log.write(f"Backup iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Origem: {BASE_DIR}\nDestino: {BACKUP_DIR}\n\n")

        for filename in FILES_TO_BACKUP:
            src = os.path.join(BASE_DIR, filename)
            dst = os.path.join(BACKUP_DIR, filename)

            if os.path.exists(src):
                try:
                    shutil.copy2(src, dst)  # copy2 preserva metadados/data de modificação
                    msg = f"[✅] Copiado: {filename}"
                    print(msg)
                    log.write(msg + "\n")
                    copied += 1
                except Exception as e:
                    msg = f"[❌] Erro ao copiar {filename}: {e}"
                    print(msg)
                    log.write(msg + "\n")
                    skipped += 1
            else:
                msg = f"[⏭️] Não encontrado (ignorado): {filename}"
                print(msg)
                log.write(msg + "\n")
                skipped += 1

        log.write(f"\n📊 Resumo: {copied} ficheiros copiados | {skipped} ignorados.\n")

    print(f"\n📁 Backup guardado em: {BACKUP_DIR}")
    print(f"📝 Log de auditoria: {os.path.basename(backup_log)}")
    print("✅ Processo concluído.")

if __name__ == "__main__":
    criar_backup()
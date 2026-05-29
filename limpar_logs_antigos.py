#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIMPAR LOGS ANTIGOS - Mantém apenas últimos 7 dias"""
import os
from pathlib import Path
from datetime import datetime, timedelta

LOG_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca")
MAX_AGE_DAYS = 7
MAX_SIZE_MB = 50  # Rotaciona se ultrapassar 50 MB

def limpar_logs():
    print(f"🧹 Limpando logs antigos em {LOG_DIR}...")
    now = datetime.now()
    removidos = 0
    
    for log_file in LOG_DIR.glob("*.log"):
        # Verificar idade
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        idade = now - mtime
        
        # Verificar tamanho
        size_mb = log_file.stat().st_size / (1024 * 1024)
        
        if idade.days > MAX_AGE_DAYS or size_mb > MAX_SIZE_MB:
            # Rotacionar em vez de apagar: renomear com timestamp
            backup_name = f"{log_file.stem}.{mtime.strftime('%Y%m%d')}.log.bak"
            backup_path = log_file.parent / backup_name
            log_file.rename(backup_path)
            print(f"📦 Rotacionado: {log_file.name} → {backup_name} ({size_mb:.1f} MB, {idade.days} dias)")
            removidos += 1
    
    print(f"✅ Conclusão: {removidos} ficheiros rotacionados.")

if __name__ == "__main__":
    limpar_logs()
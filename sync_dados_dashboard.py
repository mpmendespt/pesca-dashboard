#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNC DADOS DASHBOARD v1.1
Copia ficheiros de dados da origem para o dashboard (unidirecional).
DESTINO ATUALIZADO: D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca\data
"""
import shutil
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS
# ==============================================================================
SRC_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK5___\Weather5")
# ✅ DESTINO ATUALIZADO: pasta 'data' na raiz de Previsao_Pesca
DST_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca\data")

# Ficheiros de dados a sincronizar
DATA_FILES = [
    "Capturas.csv",              # Registos de pesca
    "previsao_pesca_ml_v3.db",   # Base SQLite com meteo/hidro/lunar
    "previsao_amanha.json",      # Previsão ML mais recente
]

def sync_files():
    print("🔄 Sincronização de dados: Origem → Dashboard")
    print(f"📍 Origem: {SRC_DIR}")
    print(f"📍 Destino: {DST_DIR}")
    
    # Criar pasta de destino se não existir
    DST_DIR.mkdir(parents=True, exist_ok=True)
    
    synced = 0
    errors = 0
    
    for filename in DATA_FILES:
        src = SRC_DIR / filename
        dst = DST_DIR / filename
        
        if not src.exists():
            print(f"⏭️  Não encontrado na origem: {filename}")
            errors += 1
            continue
        
        try:
            # Copiar com preservação de metadados
            shutil.copy2(src, dst)
            
            # Info do ficheiro
            size_kb = dst.stat().st_size / 1024
            mtime = datetime.fromtimestamp(dst.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            
            print(f"✅ {filename} ({size_kb:.1f} KB) | Atualizado: {mtime}")
            synced += 1
            
        except Exception as e:
            print(f"❌ Erro ao copiar {filename}: {e}")
            errors += 1
    
    # Resumo
    print(f"\n📊 Resumo: {synced} ficheiros sincronizados | {errors} erros")
    
    if synced > 0:
        print("💡 Os dados do dashboard foram atualizados.")
        print("🔁 Para automatizar: adicione este script ao Task Scheduler.")

if __name__ == "__main__":
    sync_files()
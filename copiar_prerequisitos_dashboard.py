#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COPIAR PRÉ-REQUISITOS PARA DASHBOARD v1.0
Copia os ficheiros essenciais de Weather5 → Previsao_Pesca para execução do .bat
"""
import shutil
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS
# ==============================================================================
SRC_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK5___\Weather5")
DST_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca")

# Ficheiros Python essenciais para o pipeline
PYTHON_SCRIPTS = [
    "pipeline_orquestrador_v3_1.py",
    "previsao_pesca_v3_1.py",
    "treinar_modelo_ml_v3_1.py",
    "prever_amanha_v3_1.py",
    "notificar_telegram.py",
    "previsao_pesca_v2_10.py",
    "config_loader.py",
    "sync_dados_dashboard.py",
]

# Ficheiros de dados e configuração
DATA_FILES = [
    "config_v3_1.json",
    "Capturas.csv",
    "previsao_pesca_ml_v3.db",
    "modelo_pesca_v3_robusto.pkl",
    "previsao_amanha.json",
    "historico_temperaturas_castelo_bode.csv",
]

# Ficheiros de automação
BAT_FILES = [
    "run_pesca_v3_1_automated.bat",
    "previsao_pesca_v2.8.bat",  # Referência legada
]

# Pastas do dashboard Streamlit (já existentes, mas garantimos .gitkeep)
DASHBOARD_FOLDERS = [
    "src",
    "pages", 
    "data",
    "assets",
    ".streamlit",
]

def copiar_ficheiro(src: Path, dst: Path, log_file) -> bool:
    """Copia um ficheiro com tratamento de erros e logging."""
    try:
        if not src.exists():
            log_file.write(f"[⏭️] Não encontrado: {src.name}\n")
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        size_kb = dst.stat().st_size / 1024
        log_file.write(f"[✅] Copiado: {src.name} ({size_kb:.1f} KB)\n")
        return True
    except Exception as e:
        log_file.write(f"[❌] Erro em {src.name}: {e}\n")
        return False

def main():
    print("📦 Copiando pré-requisitos para Previsao_Pesca...")
    print(f"📍 Origem: {SRC_DIR}")
    print(f"📍 Destino: {DST_DIR}")
    
    DST_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = DST_DIR / f"copiar_prerequisitos_{timestamp}.log"
    
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"Cópia iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 1. Copiar scripts Python
        log.write("🐍 Scripts Python:\n" + "-"*40 + "\n")
        for f in PYTHON_SCRIPTS:
            copiar_ficheiro(SRC_DIR / f, DST_DIR / f, log)
        
        # 2. Copiar dados e config
        log.write("\n📊 Dados e Configuração:\n" + "-"*40 + "\n")
        for f in DATA_FILES:
            copiar_ficheiro(SRC_DIR / f, DST_DIR / f, log)
        
        # 3. Copiar .bat
        log.write("\n⚙️ Ficheiros de Automação:\n" + "-"*40 + "\n")
        for f in BAT_FILES:
            copiar_ficheiro(SRC_DIR / f, DST_DIR / f, log)
        
        # 4. Garantir pastas do dashboard
        log.write("\n📁 Pastas do Dashboard:\n" + "-"*40 + "\n")
        for folder in DASHBOARD_FOLDERS:
            path = DST_DIR / folder
            path.mkdir(parents=True, exist_ok=True)
            (path / ".gitkeep").touch(exist_ok=True)
            log.write(f"[✅] Pasta criada: {folder}/\n")
        
        log.write(f"\n🏁 Cópia concluída: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"✅ Pré-requisitos copiados. Log: {log_path.name}")
    print("💡 Agora pode executar: run_pesca_v3_1_automated.bat")

if __name__ == "__main__":
    main()
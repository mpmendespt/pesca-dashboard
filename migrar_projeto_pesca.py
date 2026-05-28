#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIGRAÇÃO DE PROJETO - PREVISÃO DE PESCA v3.1
Copia todos os ficheiros essenciais de:
  ORIGEM: D:\_WORK_\work_python_and_R\___WORK5___\Weather5
  DESTINO: D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS
# ==============================================================================
SRC_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK5___\Weather5")
DST_DIR = Path(r"D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca")

# Lista oficial de ficheiros essenciais do projeto v3.1
FILES_ESSENCIAIS = [
    # Configuração e autenticação
    "config_v3_1.json",
    "config_loader.py",
    
    # Pipeline v3.1 (ML + Automação)
    "previsao_pesca_v3_1.py",
    "treinar_modelo_ml_v3_1.py",
    "prever_amanha_v3_1.py",
    "notificar_telegram.py",
    "pipeline_orquestrador_v3_1.py",
    "run_pesca_v3_1_automated.bat",
    
    # Relatório PDF v2.10 (integrado com ML)
    "previsao_pesca_v2_10.py",
    
    # Dados e modelos
    "previsao_pesca_ml_v3.db",
    "modelo_pesca_v3_robusto.pkl",
    "previsao_amanha.json",
    "Capturas.csv",
    "historico_temperaturas_castelo_bode.csv",
    
    # Logs (opcionais, mas úteis para debugging)
    "automacao_v3.1.log",
    "previsao_pesca_v3.1.log",
    
    # Scripts auxiliares
    "backup_arquitetura_v3_1.py",
    "migrar_projeto_pesca.py",  # Este próprio script
    
    # Referências históricas (opcionais)
    "previsao_pesca_v2.9.py",
    "previsao_pesca_v2.8.bat",
    "Previsao_Chuva_Vento_v2.1.R",
]

# Pastas inteiras a copiar (se existirem)
FOLDERS_ESSENCIAIS = [
    ".streamlit",      # Config Streamlit Cloud
    "assets",          # Imagens, CSS personalizado
    "data",            # Dados auxiliares para cloud
    "src",             # Módulos Python para dashboard
    "pages",           # Páginas Streamlit
]

# Ficheiros de configuração do repositório
REPO_FILES = [
    "requirements.txt",
    "README.md",
    ".gitignore",
]

# ==============================================================================
# FUNÇÕES DE CÓPIA
# ==============================================================================
def copiar_ficheiro(src: Path, dst: Path, log_file) -> bool:
    """Copia um ficheiro individual com tratamento de erros."""
    try:
        if not src.exists():
            log_file.write(f"[⏭️] Não encontrado: {src.name}\n")
            return False
        
        # Criar diretoria de destino se necessário
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Copiar preservando metadados (datas, permissões)
        shutil.copy2(src, dst)
        
        size = dst.stat().st_size / 1024  # KB
        log_file.write(f"[✅] Copiado: {src.name} ({size:.1f} KB)\n")
        return True
        
    except Exception as e:
        log_file.write(f"[❌] Erro ao copiar {src.name}: {e}\n")
        return False

def copiar_pasta(src_folder: Path, dst_folder: Path, log_file) -> int:
    """Copia uma pasta inteira recursivamente. Retorna número de ficheiros copiados."""
    if not src_folder.exists():
        log_file.write(f"[⏭️] Pasta não encontrada: {src_folder.name}\n")
        return 0
    
    copied = 0
    try:
        for item in src_folder.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(src_folder)
                dst_file = dst_folder / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_file)
                copied += 1
        log_file.write(f"[✅] Pasta copiada: {src_folder.name} ({copied} ficheiros)\n")
    except Exception as e:
        log_file.write(f"[❌] Erro ao copiar pasta {src_folder.name}: {e}\n")
    return copied

def validar_destino():
    """Valida e prepara a diretoria de destino."""
    if DST_DIR.exists():
        print(f"⚠️  Diretório de destino já existe: {DST_DIR}")
        resp = input("Deseja continuar e sobrescrever ficheiros existentes? (s/N): ").strip().lower()
        if resp not in ('s', 'sim', 'y', 'yes'):
            print("❌ Migração cancelada pelo utilizador.")
            return False
    else:
        DST_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✅ Diretório criado: {DST_DIR}")
    return True

# ==============================================================================
# MAIN: PROCESSO DE MIGRAÇÃO
# ==============================================================================
def migrar_projeto():
    print("📦 Iniciando migração do projeto Previsão de Pesca v3.1...")
    print(f"📍 Origem: {SRC_DIR}")
    print(f"📍 Destino: {DST_DIR}")
    
    if not validar_destino():
        return
    
    # Criar log de auditoria
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = DST_DIR / f"migracao_log_{timestamp}.txt"
    
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"Migração iniciada em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Origem: {SRC_DIR}\nDestino: {DST_DIR}\n\n")
        
        # 1. Copiar ficheiros essenciais
        log.write("📋 Copiando ficheiros essenciais:\n" + "-"*50 + "\n")
        copied_files = 0
        skipped_files = 0
        
        for filename in FILES_ESSENCIAIS:
            src = SRC_DIR / filename
            dst = DST_DIR / filename
            if copiar_ficheiro(src, dst, log):
                copied_files += 1
            else:
                skipped_files += 1
        
        # 2. Copiar pastas inteiras
        log.write("\n📁 Copiando pastas:\n" + "-"*50 + "\n")
        copied_folders = 0
        for folder in FOLDERS_ESSENCIAIS:
            src = SRC_DIR / folder
            dst = DST_DIR / folder
            n = copiar_pasta(src, dst, log)
            if n > 0:
                copied_folders += 1
        
        # 3. Copiar ficheiros de repositório
        log.write("\n🗂️ Copiando ficheiros de repositório:\n" + "-"*50 + "\n")
        for filename in REPO_FILES:
            src = SRC_DIR / filename
            dst = DST_DIR / filename
            if copiar_ficheiro(src, dst, log):
                copied_files += 1
            else:
                skipped_files += 1
        
        # Resumo final
        log.write("\n" + "="*50 + "\n")
        log.write(f"📊 RESUMO DA MIGRAÇÃO:\n")
        log.write(f"  Ficheiros copiados: {copied_files}\n")
        log.write(f"  Ficheiros ignorados: {skipped_files}\n")
        log.write(f"  Pastas copiadas: {copied_folders}\n")
        log.write(f"  Log gerado: {log_path.name}\n")
        log.write(f"Migração concluída em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Output no console
    print(f"\n✅ Migração concluída!")
    print(f"📁 Destino: {DST_DIR}")
    print(f"📝 Log detalhado: {log_path.name}")
    print(f"📊 Resumo: {copied_files} ficheiros | {copied_folders} pastas")
    
    # Pós-migração: atualizar paths no config (opcional)
    atualizar_config_paths()

def atualizar_config_paths():
    """Atualiza paths relativos no config_v3_1.json se necessário."""
    config_file = DST_DIR / "config_v3_1.json"
    if not config_file.exists():
        return
    
    try:
        import json
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Paths no config são relativos por design, mas podemos validar
        print("🔍 Verificando configurações de paths...")
        
        # Exemplo: se algum path for absoluto e apontar para a origem, converter para relativo
        updated = False
        for section in ["paths", "api"]:
            if section in config:
                for key, value in config[section].items():
                    if isinstance(value, str) and str(SRC_DIR) in value:
                        # Converter para path relativo ou novo absoluto
                        new_value = value.replace(str(SRC_DIR), str(DST_DIR))
                        config[section][key] = new_value
                        updated = True
                        print(f"  🔄 Atualizado: {section}.{key}")
        
        if updated:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print("✅ Configuração atualizada para novo diretório.")
        else:
            print("✅ Paths já estão compatíveis com novo diretório.")
            
    except Exception as e:
        print(f"⚠️  Aviso ao atualizar config: {e}")

# ==============================================================================
# EXECUÇÃO
# ==============================================================================
if __name__ == "__main__":
    migrar_projeto()
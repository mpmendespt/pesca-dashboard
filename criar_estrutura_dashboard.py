#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRIAR ESTRUTURA DE PASTAS - DASHBOARD STREAMLIT
Gera apenas as diretórios necessários para o repositório GitHub/Streamlit Cloud.
"""
import os
from pathlib import Path

# Diretório base (onde este script for executado)
BASE_DIR = Path.cwd()
DASHBOARD_DIR = BASE_DIR / "pesca-dashboard"

# Estrutura oficial definida para o projeto Streamlit
FOLDERS = [
    ".streamlit",   # Configurações do app (theme, secrets, etc.)
    "assets",       # Imagens, logos, CSS personalizado
    "data",         # Ficheiros de dados (CSV, JSON, credentials.yml, etc.)
    "src",          # Módulos Python reutilizáveis (auth, data_loader, plots, etc.)
    "pages"         # Páginas secundárias do Streamlit (rotas automáticas)
]

def criar_estrutura():
    print("📁 A criar estrutura do Dashboard Streamlit...")
    print(f"📍 Diretório alvo: {DASHBOARD_DIR}\n")
    
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    
    for folder in FOLDERS:
        path = DASHBOARD_DIR / folder
        path.mkdir(parents=True, exist_ok=True)
        
        # Cria .gitkeep para o Git rastrear pastas vazias
        (path / ".gitkeep").touch()
        
        print(f"  ✅ {path.relative_to(BASE_DIR)}/")
        
    print(f"\n🎉 Estrutura criada com sucesso!")
    print("📌 Próximo passo recomendado:")
    print("   cd pesca-dashboard")
    print("   git init && git add . && git commit -m 'Init: estrutura base dashboard'")

if __name__ == "__main__":
    criar_estrutura()
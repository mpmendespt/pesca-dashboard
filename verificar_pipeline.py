#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verificar_pipeline.py - Script de Verificação Rápida
Confirma o estado da última execução e resume os dados atualizados.
"""
import os  # ✅ Garantir que está no topo do ficheiro
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

def get_last_log_status():
    """Verifica o último log e retorna estado (Sucesso/Falha)"""
    if not LOGS_DIR.exists():
        return "⚠️ Pasta 'logs/' não encontrada."
    
    # Ordenar pela data de modificação real do ficheiro
    log_files = sorted(LOGS_DIR.glob("pipeline_*.log"), key=os.path.getmtime)
    if not log_files:
        return "⚠️ Nenhum log de pipeline encontrado."
        
    latest = log_files[-1]
    with open(latest, "r", encoding="utf-8") as f:
        content = f.read()
        
    # ✅ FIX: Usar mtime (data real de criação/modificação do ficheiro)
    mtime = os.path.getmtime(latest)
    timestamp = datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M:%S')
    
    if "✅ Pipeline Concluído" in content:
        return f"✅ SUCESSO | Último run: {timestamp}"
    elif "❌" in content or "Falhou" in content:
        return f"❌ FALHA DETETADA | Último run: {timestamp}\n   Verifique: {latest.name}"
    return f"⏳ ESTADO INCONCLUSIVO | Último run: {timestamp}"

def get_data_summary():
    """Resume os ficheiros de dados críticos"""
    summary = []
    
    # 1. Previsão
    prev_path = DATA_DIR / "previsao_amanha.json"
    if prev_path.exists():
        try:
            with open(prev_path, "r", encoding="utf-8") as f:
                p = json.load(f)
            summary.append(f"🔮 Previsão: {p.get('data', 'N/A')} | Score: {p.get('score', '?')} | Espécie: {p.get('especie_alvo', '?')}")
        except Exception as e:
            summary.append(f"🔮 Previsão: Erro ao ler ({e})")
    else:
        summary.append("🔮 Previsão: Ficheiro ausente")
        
    # 2. Modelo ML
    model_path = DATA_DIR / "modelo_pesca_v3_robusto.pkl"
    if model_path.exists():
        kb = model_path.stat().st_size / 1024
        summary.append(f"🤖 Modelo ML: Ativo ({kb:.1f} KB)")
    else:
        summary.append("🤖 Modelo ML: Ausente")
        
    # 3. Capturas (contagem rápida sem Pandas)
    csv_path = DATA_DIR / "Capturas.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        n_sessoes = max(0, len(lines) - 1)  # -1 pelo cabeçalho
        summary.append(f"📊 Capturas: {n_sessoes} sessões registadas")
    else:
        summary.append("📊 Capturas: Ficheiro ausente")
        
    return "\n   ".join(summary)

def main():
    print("=" * 55)
    print("🔍 VERIFICAÇÃO RÁPIDA DO PIPELINE v3.1")
    print("=" * 55)
    print(get_last_log_status())
    print("-" * 55)
    print(get_data_summary())
    print("=" * 55)
    print(f"⏱️ Verificado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("💡 Dica: Execute `python verificar_pipeline.py` sempre que necessário.")

if __name__ == "__main__":
    main()
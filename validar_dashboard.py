#!/usr/bin/env python3
# validar_dashboard.py
import sys, json, pickle, pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
errors = []

# 1. Verificar config
cfg_path = BASE / "config_v3_1.json"
if not cfg_path.exists():
    errors.append("❌ config_v3_1.json não encontrado")
else:
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        print(f"✅ config_v3_1.json: version={cfg.get('version', '?')}")
    except Exception as e:
        errors.append(f"❌ Erro ao ler config: {e}")

# 2. Verificar dados em data/
data_dir = BASE / "data"
required_files = ["Capturas.csv", "previsao_amanha.json", "modelo_pesca_v3_robusto.pkl", "model_metadata.json"]
for fname in required_files:
    fpath = data_dir / fname
    if fpath.exists():
        size = fpath.stat().st_size
        print(f"✅ data/{fname}: {size:,} bytes")
    else:
        # Tentar fallback na raiz
        fallback = BASE / fname
        if fallback.exists():
            print(f"⚠️ {fname} encontrado na raiz (copiar para data/)")
        else:
            errors.append(f"❌ {fname} não encontrado em data/ nem na raiz")

# 3. Validar model_metadata.json
meta_path = data_dir / "model_metadata.json"
if meta_path.exists():
    try:
        meta = json.load(open(meta_path, "r", encoding="utf-8"))
        feats = meta.get("feature_names", [])
        imps = meta.get("feature_importances", [])
        if len(feats) == len(imps) and len(feats) > 0:
            print(f"✅ model_metadata.json: {len(feats)} features, importâncias válidas")
        else:
            errors.append(f"❌ Mismatch features/importances: {len(feats)} vs {len(imps)}")
    except Exception as e:
        errors.append(f"❌ Erro ao ler model_metadata.json: {e}")

# 4. Validar previsao_amanha.json
prev_path = data_dir / "previsao_amanha.json"
if prev_path.exists():
    try:
        prev = json.load(open(prev_path, "r", encoding="utf-8"))
        required_keys = ["score", "classe", "tw", "chuva", "vento", "lua_fase"]
        missing = [k for k in required_keys if k not in prev]
        if not missing:
            print(f"✅ previsao_amanha.json: score={prev['score']} ({prev['classe']})")
        else:
            errors.append(f"❌ previsao_amanha.json falta chaves: {missing}")
    except Exception as e:
        errors.append(f"❌ Erro ao ler previsao_amanha.json: {e}")

# 5. Testar imports do Streamlit
try:
    import streamlit as st
    import plotly.graph_objects as go
    from src import data_loader, plots, ml_loader
    print("✅ Imports Streamlit/Plotly/src: OK")
except ImportError as e:
    errors.append(f"❌ Erro de import: {e}")

# Resultado
print("\n" + "="*60)
if errors:
    print("⚠️ VALIDAÇÃO COM AVISOS/ERROS:")
    for err in errors:
        print(f"  {err}")
    print("\nCorrija os erros acima antes de lançar o dashboard.")
    sys.exit(1)
else:
    print("🎉 TODOS OS COMPONENTES VALIDADOS. PRONTO PARA LANÇAR!")
    print("\nComando para iniciar:")
    print("  streamlit run streamlit_app.py --server.port 8501 --server.headless true")
    sys.exit(0)
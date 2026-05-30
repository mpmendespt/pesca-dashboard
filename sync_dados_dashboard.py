#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_dados_dashboard.py v3.1 (Ajustado à estrutura real)
Sincronização unidirecional: Weather5 (Fonte) → ./data/ (Destino)
Ficheiros da app na raiz. Dados isolados em data/.
Compatível com Session 0, comparação de timestamps e falha silenciosa.
"""
import os, sys, shutil, logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("sync_dashboard")

# 📍 Caminhos fixos conforme estrutura real
PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_DIR   = Path(r"D:\_WORK_\work_python_and_R\___WORK5___\Weather5")
TARGET_DIR   = PROJECT_ROOT / "data"  # ✅ Destino correto (já existe no tree)

FILES_TO_SYNC = [
    "Capturas.csv",
    "previsao_amanha.json",
    "modelo_pesca_v3_robusto.pkl",
    "historico_temperaturas_castelo_bode.csv",
    "previsao_pesca_ml_v3.db"
]

def needs_update(src: Path, dst: Path) -> bool:
    if not src.exists(): return False
    if not dst.exists(): return True
    return src.stat().st_mtime > dst.stat().st_mtime

def sync_files():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    synced = 0; skipped = 0; errors = 0

    logger.info(f"🔄 Sincronização: {SOURCE_DIR.name} → {TARGET_DIR.name}")
    
    for fname in FILES_TO_SYNC:
        src = SOURCE_DIR / fname
        dst = TARGET_DIR / fname
        
        if not src.exists():
            logger.warning(f"⚠️ Fonte não encontrada: {src}")
            continue
            
        if needs_update(src, dst):
            try:
                shutil.copy2(src, dst)
                logger.info(f"✅ Sincronizado: {fname} ({src.stat().st_size:,} bytes)")
                synced += 1
            except Exception as e:
                logger.error(f"❌ Falha ao copiar {fname}: {e}")
                errors += 1
        else:
            skipped += 1

    logger.info(f"📦 Conclusão: {synced} copiados, {skipped} ignorados, {errors} erros.")
    return errors == 0

if __name__ == "__main__":
    success = sync_files()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_dados_dashboard.py v3.4
Copia apenas ficheiros que existem FORA do projecto (Weather5) para data/.
Ficheiros gerados dentro do proprio projecto (JSONs, PKL, PDFs) ja estao
no sitio certo e NAO sao movidos.

Mapa definitivo:
  Weather5/ -> Previsao_Pesca/data/
    - Capturas.csv
    - historico_temperaturas_castelo_bode.csv
    - previsao_pesca_ml_v3.db   (se existir)

  Previsao_Pesca/ (raiz) -> Previsao_Pesca/data/
    - previsao_amanha.json
    - previsao_7dias.json

  Previsao_Pesca/data/ (ja esta la, ignorado)
    - modelo_pesca_v3_robusto.pkl
    - model_metadata.json

  PDFs: Previsao_Pesca/ e Weather5/ -> Previsao_Pesca/data/
    - Previsao_Pesca_*.pdf (3 mais recentes de cada origem)
"""
import sys, shutil, logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("sync_dashboard")

# ── Caminhos absolutos ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_DIR   = PROJECT_ROOT / "data"
WEATHER5_DIR = Path("D:\\_WORK_\\work_python_and_R\\___WORK5___\\Weather5")
PDF_GLOB     = "Previsao_Pesca_*.pdf"
PDF_DIR      = TARGET_DIR / "pdfs"          # pasta dedicada para PDFs

# ── Mapeamento (src_path, dst_path, label) ────────────────────────────────────
def build_file_map() -> list:
    """
    Constroi a lista de pares (src, dst) de forma explicita.
    Pares em que src == dst sao automaticamente ignorados pelo sync_file().
    """
    return [
        # De Weather5 para data\
        (WEATHER5_DIR / "Capturas.csv",
         TARGET_DIR   / "Capturas.csv",
         "Capturas.csv [Weather5->data]"),

        (WEATHER5_DIR / "historico_temperaturas_castelo_bode.csv",
         TARGET_DIR   / "historico_temperaturas_castelo_bode.csv",
         "historico_temperaturas.csv [Weather5->data]"),

        (WEATHER5_DIR / "previsao_pesca_ml_v3.db",
         TARGET_DIR   / "previsao_pesca_ml_v3.db",
         "previsao_pesca_ml_v3.db [Weather5->data]"),

        # Da raiz do projecto para data\
        (PROJECT_ROOT / "previsao_amanha.json",
         TARGET_DIR   / "previsao_amanha.json",
         "previsao_amanha.json [raiz->data]"),

        (PROJECT_ROOT / "previsao_7dias.json",
         TARGET_DIR   / "previsao_7dias.json",
         "previsao_7dias.json [raiz->data]"),

        # Ja estao em data\ — src == dst, ignorados silenciosamente
        (TARGET_DIR / "modelo_pesca_v3_robusto.pkl",
         TARGET_DIR / "modelo_pesca_v3_robusto.pkl",
         "modelo.pkl [ja em data, ignorado]"),

        (TARGET_DIR / "model_metadata.json",
         TARGET_DIR / "model_metadata.json",
         "model_metadata.json [ja em data, ignorado]"),
    ]


def needs_update(src: Path, dst: Path) -> bool:
    if not src.exists(): return False
    if not dst.exists(): return True
    return src.stat().st_mtime > dst.stat().st_mtime


def sync_file(src: Path, dst: Path, label: str) -> str:
    """Copia src->dst se necessario. Devolve estado: copiado|ignorado|erro|ausente."""
    # Mesmo ficheiro fisico — nada a fazer
    try:
        if src.resolve() == dst.resolve():
            logger.debug(f"Ignorado (mesmo path): {label}")
            return "ignorado"
    except OSError:
        pass

    if not src.exists():
        logger.warning(f"Ausente  : {label}")
        return "ausente"

    if needs_update(src, dst):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info(f"Copiado  : {label}  ({src.stat().st_size:,} bytes)")
            return "copiado"
        except Exception as e:
            logger.error(f"Erro     : {label} -- {e}")
            return "erro"

    logger.debug(f"Actual   : {label}")
    return "ignorado"


def sync_pdfs(cnt: dict) -> None:
    """
    Copia PDFs para data/pdfs/ (pasta dedicada).
    Origens:
      - data/pdfs/  (gerados pelo previsao_pesca_v2_10.py — ja estao no destino)
      - Weather5/   (legacy, se existirem)
    Nao procura na raiz do projecto — PDFs nao devem ficar na raiz.
    """
    origens = [PDF_DIR, WEATHER5_DIR]
    vistos: dict[str, Path] = {}

    for origem in origens:
        if not origem.exists():
            continue
        for pdf in sorted(origem.glob(PDF_GLOB),
                          key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
            nome = pdf.name
            if nome not in vistos or pdf.stat().st_mtime > vistos[nome].stat().st_mtime:
                vistos[nome] = pdf

    for nome, src_pdf in vistos.items():
        dst = PDF_DIR / nome
        resultado = sync_file(src_pdf, dst, f"{nome} [PDF->data/pdfs]")
        cnt[resultado] = cnt.get(resultado, 0) + 1


def sync_files() -> dict:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    cnt: dict[str, int] = {"copiado": 0, "ignorado": 0, "erro": 0, "ausente": 0}

    logger.info("=" * 60)
    logger.info("Sincronizacao v3.4")
    logger.info(f"  Projecto  : {PROJECT_ROOT}")
    logger.info(f"  Weather5  : {WEATHER5_DIR}")
    logger.info(f"  Destino   : {TARGET_DIR}")
    logger.info(f"  PDFs      : {PDF_DIR}")
    logger.info("=" * 60)

    for src, dst, label in build_file_map():
        resultado = sync_file(src, dst, label)
        cnt[resultado] = cnt.get(resultado, 0) + 1

    sync_pdfs(cnt)

    logger.info(
        f"Conclusao : {cnt.get('copiado',0)} copiados | "
        f"{cnt.get('ignorado',0)} sem alteracoes | "
        f"{cnt.get('ausente',0)} ausentes | "
        f"{cnt.get('erro',0)} erros"
    )
    return {
        "success": cnt.get("erro", 0) == 0,
        "copied":  cnt.get("copiado", 0),
        "message": f"{cnt.get('copiado',0)} ficheiros actualizados",
    }


if __name__ == "__main__":
    result = sync_files()
    sys.exit(0 if result["success"] else 1)

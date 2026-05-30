#!/usr/bin/env python3
# src/logging_setup.py
"""
Configuração centralizada e segura de logging para o pipeline v3.1.
- Nível INFO em produção
- Rotação automática: 2MB por ficheiro, máx 3 backups (6MB total)
- Previne handlers duplicados
- Formato compacto e legível
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_pipeline_logger(
    name: str = "pesca_v3_1",
    log_file: str = "previsao_pesca_v3.1.log",
    level: int = logging.INFO,
    max_bytes: int = 2_097_152,  # 2 MB
    backup_count: int = 3,
    console: bool = True
) -> logging.Logger:
    
    logger = logging.getLogger(name)
    
    # Evita duplicação de handlers em execuções consecutivas
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    logger.propagate = False  # Impede propagação para root logger
    
    # Formato compacto (evita bloat)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler de ficheiro com rotação estrita
    log_path = Path(__file__).resolve().parent.parent / log_file
    file_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    
    # Handler de consola (opcional)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)
        
    return logger
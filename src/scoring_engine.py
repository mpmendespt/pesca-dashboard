#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src/scoring_engine.py
Motor de cálculo de Score de Sucesso ponderado por espécie.
"""
import numpy as np

# Pesos de dificuldade/valor por espécie (Base 1.0 para Savel)
SPECIES_WEIGHTS = {
    'Savel': 1.5,    # Robalo (Difícil de capturar)
    'Achiga': 1.3,   # Black Bass (Predador ativo)
    'Lucio': 1.2,    # Pike (Forte e agressivo)
    'Truta': 1.4,    # Trout (Exigente em qualidade de água)
    'Savelha': 1.1,  # Bass menor
    'Pimpao': 0.8,   # Pimpão
    'Carpa': 0.5,    # Carpa (Mais fácil, maior peso)
}

def calculate_fishing_score(df_capturas) -> np.ndarray:
    """
    Calcula o score baseado na quantidade e peso, mas ponderado pela espécie.
    Formula: Sum(Qtd * Peso_Espécie * 15) + Sum(Kg * Peso_Espécie * 5)
    """
    if df_capturas.empty:
        return np.array([])
    
    df = df_capturas.copy()
    score = np.zeros(len(df))
    
    # Contribuição por Quantidade
    qtd_cols = [c for c in df.columns if c.endswith('_Qtd')]
    for col in qtd_cols:
        species = col.replace('_Qtd', '')
        weight = SPECIES_WEIGHTS.get(species, 0.5) # Fallback para espécies novas
        score += df[col] * weight * 15
        
    # Contribuição por Peso (Bónus para peixes grandes)
    kg_cols = [c for c in df.columns if c.endswith('_Kg')]
    for col in kg_cols:
        species = col.replace('_Kg', '')
        weight = SPECIES_WEIGHTS.get(species, 0.5)
        score += df[col] * weight * 5
        
    # Normalização para escala 0-100
    return np.clip(score, 0, 100)

if __name__ == "__main__":
    print("✅ Motor de Scoring inicializado.")
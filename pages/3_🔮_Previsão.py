#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/3_🔮_Previsão.py - Previsão ML com PyArrow Safe
"""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from src.data_loader import load_previsao_amanha, get_feature_importance, load_config
from src.plots import create_kpi_card

st.set_page_config(page_title="🔮 Previsão ML", page_icon="🔮", layout="wide")

# ==============================================================================
# FUNÇÃO DE LIMPEZA PARA PYARROW (Obrigatória)
# ==============================================================================
def sanitize_dataframe(df):
    """
    Remove colunas problemáticas ('Valor', 'Tipo', etc.) e converte 
    tipos mistos para garantir compatibilidade com PyArrow/Streamlit.
    """
    if df is None or df.empty:
        return df
    
    df_clean = df.copy()
    
    # 1. Remover colunas conhecidas por causar erros (case-insensitive)
    bad_cols = [c for c in df_clean.columns if c.lower() in ['valor', 'tipo', 'unnamed', 'type', 'value']]
    if bad_cols:
        df_clean = df_clean.drop(columns=bad_cols)
        
    # 2. Converter colunas 'object' para numérico ou string pura
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            try:
                # Tenta converter para numérico primeiro
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            except Exception:
                # Se falhar, converte para string limpa
                df_clean[col] = df_clean[col].astype(str).fillna('').replace(['nan', 'None', 'NaN'], '')
                
    return df_clean

# ==============================================================================
# 🔐 GUARD DE AUTENTICAÇÃO (Impede acesso sem login)
# ==============================================================================
if not st.session_state.get("authentication_status"):
    st.warning("🔐 Acesso restrito. A sessão expirou ou não está autenticada.")
    st.page_link("streamlit_app.py", label="🔑 Ir para Login", icon="🔑")
    st.stop()

# ==============================================================================
# CONTEÚDO PRINCIPAL
# ==============================================================================
def main():
    st.title("🔮 Previsão ML para Amanhã")
    
    config = load_config()
    previsao = load_previsao_amanha()
    
    if not previsao:
        st.error("❌ Sem previsão disponível. Execute o pipeline (`prever_amanha_v3_1.py`).")
        return

    # --- KPIs de Previsão ---
    c1, c2, c3, c4 = st.columns(4)
    score = previsao.get('score', 50)
    classe = previsao.get('classe', 'MODERADO')
    color = "green" if score >= 70 else "orange" if score >= 40 else "red"
    
    with c1: st.markdown(create_kpi_card("Score", f"{score}", "/100", color=color), unsafe_allow_html=True)
    with c2: st.markdown(create_kpi_card("Classificação", classe, "", color=color), unsafe_allow_html=True)
    with c3: st.markdown(create_kpi_card("Tw (Água)", f"{previsao.get('tw', '--')}", "°C", color="purple"), unsafe_allow_html=True)
    with c4: st.markdown(create_kpi_card("Vento", f"{previsao.get('vento', '--')}", "km/h", color="blue"), unsafe_allow_html=True)

    st.divider()

    col_main, col_meta = st.columns([2, 1])

    with col_main:
        # --- Gráfico de Feature Importance ---
        st.subheader("📊 O que influenciou esta previsão?")
        feat_data = get_feature_importance()
        
        if feat_data:
            # 🔑 Normalizar chaves (compatível com v3.1.5 e v3.2)
            features = feat_data.get("feature_names") or feat_data.get("features_used", [])
            importances = feat_data.get("feature_importances") or feat_data.get("feature_importance", [])
            
            # Se o formato for lista de dicionários (v3.2), converter para listas paralelas
            if importances and isinstance(importances[0], dict):
                features = [d.get("feature", d.get("feature_name", "")) for d in importances]
                importances = [d.get("importance", 0) for d in importances]
                
            # ✅ Validação de segurança antes de criar o DataFrame
            if features and importances and len(features) == len(importances):
                df_imp = pd.DataFrame({
                    'Feature': features,
                    'Importance': importances
                }).sort_values('Importance', ascending=True).tail(10)
                
                fig = px.bar(df_imp, x='Importance', y='Feature', orientation='h',
                             title="Top 10 Variáveis Mais Importantes",
                             labels={'Importance': 'Peso na Decisão', 'Feature': 'Variável'},
                             color='Importance', color_continuous_scale='Viridis')
                st.plotly_chart(fig, width="stretch")
            else:
                st.warning("⚠️ Metadados inconsistentes. Retreine o modelo para corrigir.")
        else:
            st.warning("⚠️ Metadados do modelo não disponíveis.")

        # --- Tabela de Previsão Detalhada ---
        st.subheader("📋 Detalhes da Previsão")
        details = {
            "Data": previsao.get('data', 'N/A'),
            "Score": previsao.get('score'),
            "Classificação": previsao.get('classe'),
            "Melhor Horário": previsao.get('horario', 'N/A'),
            "Espécie Alvo": previsao.get('especie_alvo', 'N/A'),
            "Chuva Prevista": f"{previsao.get('chuva', 0)} mm",
            "Lua": f"{previsao.get('lua_fase', '?')} ({previsao.get('lua_pct', 0)}%)"
        }
        df_details = pd.DataFrame(details.items(), columns=["Parâmetro", "Valor"])
        
        # ✅ FIX: Aplicar sanitize à tabela também (boa prática)
        df_details = sanitize_dataframe(df_details)
        
        st.table(df_details)

    with col_meta:
        st.subheader("ℹ️ Info do Modelo")
        # Já está normalizado via get_feature_importance()
        st.info(f"🤖 Modelo: {feat_data.get('model_type', 'N/A')}")
        st.info(f"📚 Dados Treino: {feat_data.get('metrics', {}).get('n_samples', 0)} sessões")
        r2_val = feat_data.get('metrics', {}).get('r2', 'N/A')
        st.info(f"📈 R² (Validação): {r2_val if r2_val != 0 else '0.0 (Baseline)'}")
            
        st.divider()
        st.markdown("""
        **Nota:** A previsão é gerada automaticamente todos os dias às 18:50 pelo Task Scheduler. 
        O modelo utiliza dados de:
        - Temperatura da Água (Tw) estimada
        - Vento e Chuva (Open-Meteo)
        - Fase Lunar
        - Histórico de Capturas
        """)

if __name__ == "__main__":
    main()
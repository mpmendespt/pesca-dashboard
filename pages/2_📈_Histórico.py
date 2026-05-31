import streamlit as st

# 🔐 GUARD DE AUTENTICAÇÃO (Impede acesso sem login)
if not st.session_state.get("authentication_status"):
    st.warning("⚠️ Acesso restrito. A sessão expirou ou não está autenticada.")
    st.page_link("streamlit_app.py", label="🔑 Ir para Login", icon="🔑")
    st.stop()

import pandas as pd
import numpy as np  # ✅ IMPORT ADICIONADO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from src.data_loader import load_capturas, load_config

st.set_page_config(page_title="Histórico", page_icon="📈", layout="wide")

def main():
    st.title("📈 Histórico de Capturas e Condições")
    
    # Carregar dados
    df_capturas = load_capturas()
    config = load_config()

    if df_capturas.empty:
        st.warning("⚠️ Sem dados de capturas disponíveis. Verifique `Capturas.csv`.")
        return

    # Filtro Lateral
    st.sidebar.header("🔍 Filtros")
    species_list = [c.replace('_Qtd', '') for c in df_capturas.columns if c.endswith('_Qtd')]
    selected_species = st.sidebar.multiselect("Espécies", species_list, default=species_list[:5] if len(species_list) > 5 else species_list)

    # --- Gráfico 1: Evolução Temporal de Capturas ---
    st.subheader("📅 Evolução de Capturas (Quantidade)")
    if not df_capturas.empty and selected_species:
        # Preparar dados para gráfico de barras
        df_plot = df_capturas[['Timestamp'] + [f'{s}_Qtd' for s in selected_species]].copy()
        
        # Verificar tipo da coluna Timestamp
        if pd.api.types.is_datetime64_any_dtype(df_plot['Timestamp']):
            df_plot['Data'] = df_plot['Timestamp'].dt.date
        else:
            df_plot['Timestamp'] = pd.to_datetime(df_plot['Timestamp'], errors='coerce')
            df_plot['Data'] = df_plot['Timestamp'].dt.date
        
        # Remover linhas com data inválida
        df_plot = df_plot.dropna(subset=['Data'])
        
        if not df_plot.empty:
            df_plot = df_plot.drop('Timestamp', axis=1).groupby('Data').sum().reset_index()
            
            # Transformar para formato longo
            df_melt = df_plot.melt(id_vars='Data', value_vars=[f'{s}_Qtd' for s in selected_species], 
                                   var_name='Especie', value_name='Qtd')
            df_melt['Especie'] = df_melt['Especie'].str.replace('_Qtd', '')
            
            # Filtrar zeros
            df_melt = df_melt[df_melt['Qtd'] > 0]

            if not df_melt.empty:
                fig = px.bar(df_melt, x='Data', y='Qtd', color='Especie',
                             title="Capturas Diárias por Espécie",
                             labels={'Qtd': 'Quantidade', 'Data': 'Data'})
                fig.update_layout(xaxis_type='category')
                st.plotly_chart(fig, width="stretch")  # ✅ Mudado para width="stretch"
            else:
                st.info("📊 Sem dados para exibir com os filtros selecionados")
        else:
            st.info("📊 Sem dados válidos para o período selecionado")

    # --- Gráfico 2: Peso Total por Espécie ---
    st.subheader("⚖️ Peso Total Acumulado (Kg)")
    kg_cols = [f'{s}_Kg' for s in selected_species if f'{s}_Kg' in df_capturas.columns]
    if kg_cols:
        totals = df_capturas[kg_cols].sum()
        totals = totals[totals > 0]
        if not totals.empty:
            totals.index = totals.index.str.replace('_Kg', '')
            fig_pie = px.pie(values=totals.values, names=totals.index,
                             title="Distribuição de Peso por Espécie",
                             hole=0.4)
            st.plotly_chart(fig_pie, width="stretch")  # ✅ Mudado para width="stretch"
        else:
            st.info("📊 Sem dados de peso para exibir")

    # --- Gráfico 3: Relação com Lua ---
    st.subheader("🌙 Sucesso por Fase Lunar")
    
    # Calcular score se não existir
    if 'sucesso_score' not in df_capturas.columns:
        q_cols = [c for c in df_capturas.columns if c.endswith('_Qtd') and c != 'Total_Qtd']
        k_cols = [c for c in df_capturas.columns if c.endswith('_Kg') and c != 'Total_Kg']
        if q_cols and k_cols:
            df_capturas['sucesso_score'] = (df_capturas[q_cols].sum(axis=1) * 12 + 
                                            df_capturas[k_cols].sum(axis=1) * 18).clip(0, 100)

    # Verificar se temos dados para o gráfico
    if 'sucesso_score' in df_capturas.columns:
        # Criar fase lunar simulada se não existir
        if 'Fase_Lua' not in df_capturas.columns:
            # Distribuição baseada no dia do mês (mais consistente que random)
            df_capturas['Dia'] = pd.to_datetime(df_capturas['Timestamp']).dt.day
            # Mapear dia para fase lunar aproximada
            def dia_para_fase(dia):
                if dia < 7: return 'Nova'
                elif dia < 14: return 'Crescente'
                elif dia < 21: return 'Cheia'
                else: return 'Minguante'
            df_capturas['Fase_Lua'] = df_capturas['Dia'].apply(dia_para_fase)
            df_capturas = df_capturas.drop('Dia', axis=1)
        
        df_lua = df_capturas[['Fase_Lua', 'sucesso_score']].dropna()
        if not df_lua.empty and len(df_lua['Fase_Lua'].unique()) > 1:
            fig_box = px.box(df_lua, x='Fase_Lua', y='sucesso_score',
                             title="Distribuição do Score por Fase Lunar",
                             points="all", color='Fase_Lua')
            st.plotly_chart(fig_box, width="stretch")  # ✅ Mudado para width="stretch"
        else:
            st.info("🌙 Dados insuficientes para análise por fase lunar")

    # --- Tabela de Dados Recentes ---
    with st.expander("📋 Ver Tabela de Dados Recentes"):
        display_cols = ['Timestamp', 'Total_Qtd', 'Total_Kg', 'sucesso_score']
        available_cols = [c for c in display_cols if c in df_capturas.columns]
        
        if available_cols:
            df_display = df_capturas[available_cols].sort_values('Timestamp', ascending=False).head(20)
            st.dataframe(df_display, width="stretch")  # ✅ Mudado para width="stretch"
        else:
            st.dataframe(df_capturas.head(20), width="stretch")  # ✅ Mudado para width="stretch"
    
    # --- Estatísticas Resumo ---
    with st.expander("📊 Estatísticas Resumo"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sessões", len(df_capturas))
        with col2:
            total_peixes = int(df_capturas['Total_Qtd'].sum()) if 'Total_Qtd' in df_capturas.columns else 0
            st.metric("Total Peixes", f"{total_peixes:,}")
        with col3:
            total_peso = df_capturas['Total_Kg'].sum() if 'Total_Kg' in df_capturas.columns else 0
            st.metric("Total Peso", f"{total_peso:.1f} kg")
        with col4:
            score_medio = df_capturas['sucesso_score'].mean() if 'sucesso_score' in df_capturas.columns else 0
            st.metric("Score Médio", f"{score_medio:.1f}")

if __name__ == "__main__":
    main()
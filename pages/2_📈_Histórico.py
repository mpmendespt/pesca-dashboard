import streamlit as st

# 🔐 GUARD DE AUTENTICAÇÃO (Impede acesso sem login)
if not st.session_state.get("authentication_status"):
    st.warning(" Acesso restrito. A sessão expirou ou não está autenticada.")
    st.page_link("streamlit_app.py", label="🔑 Ir para Login", icon="🔑")
    st.stop()
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.data_loader import load_capturas, load_sqlite_historico, load_config

st.set_page_config(page_title="Histórico", page_icon="📈", layout="wide")

def main():
    st.title("📈 Histórico de Capturas e Condições")
    
    # Carregar dados
    df_capturas = load_capturas()
    df_sqlite = load_sqlite_historico()  # Devolve DataFrame (não dict)
    config = load_config()

    if df_capturas.empty:
        st.warning("⚠️ Sem dados de capturas disponíveis. Verifique `Capturas.csv`.")
        return

    # Filtro Lateral
    st.sidebar.header("🔍 Filtros")
    species_list = [c.replace('_Qtd', '') for c in df_capturas.columns if c.endswith('_Qtd')]
    selected_species = st.sidebar.multiselect("Espécies", species_list, default=species_list)

    # --- Gráfico 1: Evolução Temporal de Capturas ---
    st.subheader("📅 Evolução de Capturas (Quantidade)")
    if not df_capturas.empty:
        # Preparar dados para gráfico de barras
        df_plot = df_capturas[['Timestamp'] + [f'{s}_Qtd' for s in selected_species]].copy()
        df_plot['Data'] = df_plot['Timestamp'].dt.date
        df_plot = df_plot.drop('Timestamp', axis=1).groupby('Data').sum().reset_index()
        
        # Transformar para formato longo
        df_melt = df_plot.melt(id_vars='Data', value_vars=[f'{s}_Qtd' for s in selected_species], 
                               var_name='Especie', value_name='Qtd')
        df_melt['Especie'] = df_melt['Especie'].str.replace('_Qtd', '')
        
        # Filtrar zeros para visualização mais limpa
        df_melt = df_melt[df_melt['Qtd'] > 0]

        fig = px.bar(df_melt, x='Data', y='Qtd', color='Especie',
                     title="Capturas Diárias por Espécie",
                     labels={'Qtd': 'Quantidade', 'Data': 'Data'})
        fig.update_layout(xaxis_type='category')
        st.plotly_chart(fig, width="stretch")

    # --- Gráfico 2: Peso Total por Espécie (Histórico) ---
    st.subheader("⚖️ Peso Total Acumulado (Kg)")
    kg_cols = [f'{s}_Kg' for s in selected_species if f'{s}_Kg' in df_capturas.columns]
    if kg_cols:
        totals = df_capturas[kg_cols].sum()
        totals.index = totals.index.str.replace('_Kg', '')
        
        fig_pie = px.pie(values=totals.values, names=totals.index,
                         title="Distribuição de Peso por Espécie",
                         hole=0.4)
        st.plotly_chart(fig_pie, width="stretch")

    # --- Gráfico 3: Relação com Lua (Boxplot) ---
    st.subheader("🌙 Sucesso por Fase Lunar")
    # Tenta calcular score se não existir
    if 'sucesso_score' not in df_capturas.columns:
        q_cols = [c for c in df_capturas.columns if c.endswith('_Qtd')]
        k_cols = [c for c in df_capturas.columns if c.endswith('_Kg')]
        df_capturas['sucesso_score'] = (df_capturas[q_cols].sum(axis=1) * 12 + 
                                        df_capturas[k_cols].sum(axis=1) * 18).clip(0, 100)

    # Simular Fase Lunar se não houver coluna (fallback básico)
    if 'Fase_Lua' not in df_capturas.columns:
        # Cria colunas fictícias para teste se o CSV não tiver
        df_capturas['Fase_Lua'] = 'Variada' 
    
    if 'Fase_Lua' in df_capturas.columns:
        fig_box = px.box(df_capturas, x='Fase_Lua', y='sucesso_score',
                         title="Distribuição do Score de Sucesso por Fase Lunar",
                         points="all", color='Fase_Lua')
        st.plotly_chart(fig_box, width="stretch")
    else:
        st.info("🌙 Dados de Fase Lunar não encontrados no CSV para este gráfico.")

    # --- Tabela de Dados Recentes ---
    with st.expander("📋 Ver Tabela de Dados Recentes"):
        st.dataframe(df_capturas.tail(10), width="stretch")

if __name__ == "__main__":
    main()
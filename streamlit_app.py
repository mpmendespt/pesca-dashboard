#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STREAMLIT DASHBOARD - PREVISÃO DE PESCA v3.1
Deploy: Streamlit Community Cloud (gratuito)
Auth: streamlit-authenticator
"""
import streamlit as st
from src.auth import login_page, logout_button
from src.data_loader import load_sqlite_data, load_ml_model

# Configuração inicial da página
st.set_page_config(
    page_title="🎣 Pesca Dashboard",
    page_icon="🎣",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    # 1. Autenticação
    authenticator = login_page()
    if not authenticator:
        return  # Aguarda login
    
    # 2. Botão de logout na sidebar
    logout_button(authenticator)
    
    # 3. Sidebar com navegação
    with st.sidebar:
        st.title("🧭 Navegação")
        page = st.radio(
            "Ir para:",
            ["🏠 Início", "📈 Histórico", "🔮 Previsão", "⚙️ Configurações", "📥 Importar"],
            index=0,
            label_visibility="collapsed"
        )
        st.divider()
        st.info("💡 Dica: Os dados atualizam automaticamente a cada 5 minutos.")
    
    # 4. Router de páginas
    if page == "🏠 Início":
        show_home()
    elif page == "📈 Histórico":
        show_historico()
    elif page == "🔮 Previsão":
        show_previsao()
    elif page == "⚙️ Configurações":
        show_config()
    elif page == "📥 Importar":
        show_importar()

def show_home():
    """Página inicial com resumo executivo."""
    st.title("🎣 Dashboard de Previsão de Pesca")
    st.subheader("Rede Jazida • Barragem de Castelo de Bode")
    
    # Carregar dados
    df, capturas, previsao = load_sqlite_data()
    
    if df.empty:
        st.warning("⚠️ Nenhum dado disponível. Verifique a sincronização da base de dados.")
        return
    
    # KPIs em cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Sessões Registadas", len(capturas) if not capturas.empty else 0)
    with col2:
        total_kg = capturas['Total_Kg'].sum() if not capturas.empty and 'Total_Kg' in capturas.columns else 0
        st.metric("🐟 Peso Total", f"{total_kg:.1f} kg")
    with col3:
        score_atual = previsao['score_previsto'].iloc[0] if previsao is not None and not previsao.empty else None
        st.metric("🎯 Score ML (Amanhã)", f"{score_atual}/100" if score_atual is not None else "N/A")
    with col4:
        ultima = df['datetime'].max().strftime("%d/%m") if not df.empty else "N/A"
        st.metric("📅 Última Atualização", ultima)
    
    # Gráfico rápido: evolução de scores
    if not df.empty and 'sucesso_score' in df.columns:
        st.subheader("📈 Evolução do Score de Sucesso")
        df_plot = df.dropna(subset=['sucesso_score']).sort_values('datetime').tail(30)
        st.line_chart(df_plot.set_index('datetime')['sucesso_score'], use_container_width=True)
    
    # Tabela recente de capturas
    if not capturas.empty:
        st.subheader("🎣 Últimas Capturas")
        st.dataframe(
            capturas.sort_values('Timestamp', ascending=False).head(10),
            use_container_width=True,
            hide_index=True
        )

def show_historico():
    """Página de histórico com gráficos interativos."""
    st.title("📈 Histórico de Capturas")
    df, capturas, _ = load_sqlite_data()
    
    if capturas.empty:
        st.info("📭 Sem registos de capturas ainda.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        especie_filter = st.multiselect(
            "Filtrar por espécie:",
            options=[c.replace('_Qtd','') for c in capturas.columns if '_Qtd' in c],
            default=None
        )
    with col2:
        date_range = st.date_input("Período:", value=(capturas['Timestamp'].min().date(), capturas['Timestamp'].max().date()))
    
    # Gráfico: capturas por espécie (Plotly)
    import plotly.express as px
    species_cols = [c for c in capturas.columns if '_Kg' in c and c != 'Total_Kg']
    if species_cols:
        df_melt = capturas.melt(
            id_vars=['Timestamp'], 
            value_vars=species_cols,
            var_name='Especie', 
            value_name='Peso_Kg'
        )
        df_melt['Especie'] = df_melt['Especie'].str.replace('_Kg', '')
        
        fig = px.bar(
            df_melt.groupby(['Timestamp', 'Especie'])['Peso_Kg'].sum().reset_index(),
            x='Timestamp', y='Peso_Kg', color='Especie',
            title="🐟 Peso por Espécie ao Longo do Tempo",
            labels={'Peso_Kg': 'Peso (kg)', 'Timestamp': 'Data'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabela detalhada
    st.subheader("📋 Dados Detalhados")
    st.dataframe(capturas, use_container_width=True)

def show_previsao():
    """Página de previsão ML."""
    st.title("🔮 Previsão para Amanhã")
    
    # Carregar previsão
    _, _, previsao = load_sqlite_data()
    model_data = load_ml_model()
    
    if previsao is None or previsao.empty:
        st.warning("⚠️ Previsão não disponível. Execute `prever_amanha_v3_1.py` localmente.")
        return
    
    # Mostrar previsão formatada
    p = previsao.iloc[0] if not previsao.empty else None
    if p is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 Score ML", f"{p.get('score_previsto', 0):.1f}/100")
            st.metric("🐟 Espécie Recomendada", p.get('especie_recomendada', 'N/A'))
        with col2:
            st.metric("⏰ Melhor Horário", p.get('melhor_horario', 'N/A'))
            st.metric("🌡️ Tw Prevista", f"{p.get('condicoes_chave', {}).get('Tw', 0):.1f}°C")
        
        # Condições detalhadas
        with st.expander("🔍 Ver Condições Detalhadas"):
            st.json(p.get('condicoes_chave', {}), expanded=False)
    
    # Gráfico: feature importance se modelo carregado
    if model_data and 'feature_names' in model_data:
        st.subheader("🧠 Fatores que Influenciam a Previsão")
        # Nota: feature importance requer retreino com feature_names guardados
        st.info("💡 Feature importance disponível após retreino com `treinar_modelo_ml_v3_1.py`")

def show_config():
    """Página de configurações (apenas admin)."""
    st.title("⚙️ Configurações")
    
    if st.session_state.get('username') != 'admin':
        st.warning("🔐 Apenas administradores podem aceder a esta página.")
        return
    
    st.subheader("👥 Gestão de Utilizadores")
    st.info("Para adicionar/remover utilizadores, edite `data/credentials.yml` no repositório GitHub.")
    
    st.subheader("🔗 Sincronização de Dados")
    st.markdown("""
    **Opções para manter dados atualizados na cloud:**
    
    1. **GitHub Actions + Dropbox** (recomendado):
       - Configure um workflow que faz push dos CSVs/SQLite para uma pasta Dropbox
       - O dashboard lê dessa pasta via `dropbox` API
    
    2. **Google Sheets** (simples):
       - Exporte `Capturas.csv` para Google Sheets
       - Use `gspread` para ler diretamente no dashboard
    
    3. **Streamlit Cloud Mount** (avançado):
       - Conecte uma conta Dropbox/Google Drive no Streamlit Cloud
       - Monte em `/mount/data/` e aponte os paths no `data_loader.py`
    """)
    
    st.subheader("🔄 Forçar Atualização")
    if st.button("🔄 Recarregar Dados Agora"):
        st.cache_data.clear()
        st.success("✅ Cache limpo. Dados recarregados na próxima interação.")

def show_importar():
    """Página para upload manual de Capturas.csv."""
    st.title("📥 Importar Dados de Capturas")
    
    uploaded = st.file_uploader("Selecionar Capturas.csv", type=['csv'])
    if uploaded:
        try:
            df_new = pd.read_csv(uploaded, parse_dates=['Timestamp'])
            st.success(f"✅ Ficheiro lido: {len(df_new)} registos")
            st.dataframe(df_new.head(), use_container_width=True)
            
            if st.button("💾 Guardar no Sistema"):
                # Em cloud: guardar em Google Sheets ou trigger para sync
                st.info("💡 Em produção, isto dispararia um sync para a base de dados principal.")
                st.success("✅ Dados processados (simulação)")
        except Exception as e:
            st.error(f"❌ Erro ao processar: {e}")

if __name__ == "__main__":
    main()
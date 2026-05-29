# streamlit_app.py
import streamlit as st
from src.auth import get_authenticator, render_login, render_logout, init_session_state
from src.data_loader import (
    load_config, load_capturas, load_sqlite_summary, 
    load_previsao_amanha, calculate_kpis, get_species_list
)

st.set_page_config(
    page_title="🎣 Pesca Dashboard",
    page_icon="🎣",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    # 1. Inicializar sessão e autenticação
    init_session_state()
    authenticator = get_authenticator()
    
    if not st.session_state.get("authentication_status"):
        if render_login(authenticator):
            st.rerun()
        return

    # 2. Logout e navegação
    render_logout(authenticator)
    
    with st.sidebar:
        st.title("🧭 Navegação")
        page = st.radio(
            "Ir para:",
            ["🏠 Início", "📈 Histórico", "🔮 Previsão", "⚙️ Configurações"],
            index=0,
            label_visibility="collapsed"
        )
        st.divider()
        st.info("💡 Dados atualizados a cada 5 minutos.")
    
    # 3. Carregar dados (com cache)
    config = load_config()
    df_capturas = load_capturas()
    df_sqlite = load_sqlite_summary()
    previsao = load_previsao_amanha()
    kpis = calculate_kpis(df_capturas, df_sqlite)
    
    # 4. Router de páginas
    if page == "🏠 Início":
        show_home(kpis, previsao, df_capturas, config)
    elif page == "📈 Histórico":
        show_historico(df_capturas, df_sqlite, config)
    elif page == "🔮 Previsão":
        show_previsao(previsao, df_sqlite, config)
    elif page == "⚙️ Configurações":
        show_config(config, authenticator)

def show_home(kpis, previsao, df_capturas, config):
    """Página inicial com KPIs e resumo executivo."""
    st.title("🎣 Dashboard de Previsão de Pesca")
    st.subheader(f"{config['location']['name']} • Rede Jazida")
    
    # KPIs em cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Sessões", kpis.get("sessoes", 0))
    with col2:
        st.metric("🐟 Peso Total", f"{kpis.get('total_kg', 0):.1f} kg")
    with col3:
        score = previsao.get("score_previsto") if previsao else None
        st.metric("🎯 Score ML (Amanhã)", f"{score:.1f}/100" if score is not None else "N/A")
    with col4:
        ultima = kpis.get("ultima_atualizacao")
        st.metric("📅 Última Atualização", 
                 ultima.strftime("%d/%m %H:%M") if ultima else "N/A")
    
    # Gráfico rápido: evolução de capturas (últimos 30 dias)
    if not df_capturas.empty:
        st.subheader("📈 Evolução de Capturas (Últimos 30 dias)")
        df_recent = df_capturas[
            df_capturas["Timestamp"] >= (df_capturas["Timestamp"].max() - pd.Timedelta(days=30))
        ].sort_values("Timestamp")
        
        if not df_recent.empty:
            import plotly.express as px
            fig = px.area(
                df_recent, x="Timestamp", y="Total_Kg",
                title="Peso Total por Sessão",
                labels={"Total_Kg": "Peso (kg)", "Timestamp": "Data"}
            )
            fig.update_layout(height=300, margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de últimas capturas
    if not df_capturas.empty:
        st.subheader("🎣 Últimas Capturas")
        species = get_species_list(df_capturas)
        cols_display = ["Timestamp"] + [f"{s}_Qtd" for s in species[:3]] + ["Total_Qtd", "Total_Kg"]
        cols_display = [c for c in cols_display if c in df_capturas.columns]
        
        st.dataframe(
            df_capturas.sort_values("Timestamp", ascending=False).head(10)[cols_display],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Timestamp": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                "Total_Qtd": st.column_config.NumberColumn("Total (un)", format="%d"),
                "Total_Kg": st.column_config.NumberColumn("Total (kg)", format="%.1f")
            }
        )

def show_historico(df_capturas, df_sqlite, config):
    """Página de histórico com filtros e gráficos interativos."""
    st.title("📈 Histórico de Capturas")
    
    if df_capturas.empty:
        st.info("📭 Sem registos de capturas ainda. Adicione dados em `Capturas.csv`.")
        return
    
    # Filtros na sidebar
    with st.sidebar:
        st.subheader("🔍 Filtros")
        especies = get_species_list(df_capturas)
        especie_sel = st.multiselect("Espécie:", especies, default=None)
        
        date_range = st.date_input(
            "Período:",
            value=(df_capturas["Timestamp"].min().date(), df_capturas["Timestamp"].max().date())
        )
        
        if st.button("🔄 Aplicar Filtros"):
            st.rerun()
    
    # Aplicar filtros
    df_filtered = df_capturas.copy()
    if especie_sel:
        cols_filtro = [f"{esp}_Qtd" for esp in especie_sel if f"{esp}_Qtd" in df_filtered.columns]
        if cols_filtro:
            df_filtered = df_filtered[df_filtered[cols_filtro].sum(axis=1) > 0]
    
    if len(date_range) == 2:
        mask = (df_filtered["Timestamp"].dt.date >= date_range[0]) & \
               (df_filtered["Timestamp"].dt.date <= date_range[1])
        df_filtered = df_filtered[mask]
    
    if df_filtered.empty:
        st.warning("⚠️ Nenhum dado corresponde aos filtros selecionados.")
        return
    
    # Gráfico 1: Peso por espécie ao longo do tempo
    import plotly.express as px
    species_kg = [c for c in df_filtered.columns if c.endswith("_Kg") and c != "Total_Kg"]
    if species_kg:
        df_melt = df_filtered.melt(
            id_vars=["Timestamp"],
            value_vars=species_kg,
            var_name="Especie",
            value_name="Peso_Kg"
        )
        df_melt["Especie"] = df_melt["Especie"].str.replace("_Kg", "")
        
        fig1 = px.bar(
            df_melt.groupby(["Timestamp", "Especie"])["Peso_Kg"].sum().reset_index(),
            x="Timestamp", y="Peso_Kg", color="Especie",
            title="🐟 Peso por Espécie ao Longo do Tempo",
            labels={"Peso_Kg": "Peso (kg)", "Timestamp": "Data"}
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    # Gráfico 2: Quantidade vs Fase Lunar
    if "Fase_Lua_Captura" in df_filtered.columns:
        fig2 = px.box(
            df_filtered, x="Fase_Lua_Captura", y="Total_Qtd",
            title="🌙 Distribuição de Capturas por Fase Lunar",
            labels={"Total_Qtd": "Quantidade (un)", "Fase_Lua_Captura": "Fase"}
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Tabela detalhada expansível
    with st.expander("📋 Ver dados detalhados"):
        st.dataframe(df_filtered, use_container_width=True)

def show_previsao(previsao, df_sqlite, config):
    """Página de previsão ML com condições e recomendações."""
    st.title("🔮 Previsão para Amanhã")
    
    if previsao is None:
        st.warning("⚠️ Previsão não disponível. Execute `prever_amanha_v3_1.py` localmente.")
        return
    
    # Cards de previsão
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Score ML", f"{previsao.get('score_previsto', 0):.1f}/100")
    with col2:
        st.metric("🐟 Espécie Recomendada", previsao.get("especie_recomendada", "N/A"))
    with col3:
        st.metric("⏰ Melhor Horário", previsao.get("melhor_horario", "N/A"))
    with col4:
        classificacao = previsao.get("classificacao", "N/A")
        color = "🟢" if classificacao in ["BOM", "EXCELENTE"] else "🟡" if classificacao == "MODERADO" else "🔴"
        st.metric("🎯 Classificação", f"{color} {classificacao}")
    
    # Condições detalhadas
    st.subheader("🌤️ Condições Previstas")
    cond = previsao.get("condicoes_chave", {})
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Tw (Água)", f"{cond.get('Tw', 0):.1f}°C")
    c2.metric("🌧️ Chuva 24h", f"{cond.get('Chuva_24h', 0):.1f} mm")
    c3.metric("🌙 Lua", cond.get("Lua", "N/A"))
    c4.metric("💨 Vento Máx", f"{cond.get('Vento_Max', 0):.1f} km/h")
    
    # Feature importance (se disponível)
    from src.data_loader import get_feature_importance
    df_imp = get_feature_importance()
    if df_imp is not None and not df_imp.empty:
        st.subheader("🧠 Fatores que Influenciam a Previsão")
        import plotly.express as px
        fig = px.bar(
            df_imp, x="importance", y="feature", orientation="h",
            title="Importância das Features (Top 10)",
            labels={"importance": "Importância", "feature": "Feature"}
        )
        fig.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    
    # Nota informativa
    st.info("💡 Modelo em fase inicial. Use como referência complementar à sua experiência.")

def show_config(config, authenticator):
    """Página de configurações (apenas admin)."""
    st.title("⚙️ Configurações")
    
    if st.session_state.get("username") != "admin":
        st.warning("🔐 Apenas administradores podem aceder a esta página.")
        return
    
    st.subheader("👥 Gestão de Utilizadores")
    st.info("Para adicionar/remover utilizadores, edite `data/credentials.yml` ou use Streamlit Secrets.")
    
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
    
    st.subheader("📋 Informações do Sistema")
    st.json({
        "versão_config": config.get("version", "desconhecida"),
        "local": config.get("location", {}).get("name", ""),
        "thresholds": config.get("thresholds", {}),
        "water_temp_model": config.get("water_temp_model", {})
    }, expanded=False)

if __name__ == "__main__":
    main()
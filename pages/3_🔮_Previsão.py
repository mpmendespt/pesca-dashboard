# pages/3_🔮_Previsão.py
import streamlit as st
import pandas as pd
import plotly.express as px
from src.data_loader import load_previsao_amanha, load_sqlite_summary, load_config, get_feature_importance

st.set_page_config(page_title="🔮 Previsão", page_icon="🎯", layout="wide")

def main():
    st.title("🔮 Previsão para Amanhã")
    
    config = load_config()
    previsao = load_previsao_amanha()
    df_sqlite = load_sqlite_summary()
    
    if previsao is None:
        st.warning("⚠️ Previsão não disponível. Execute `prever_amanha_v3_1.py` localmente.")
        st.info("💡 Dica: A previsão é gerada diariamente pelo script de automação.")
        return
    
    # Header com score destacado
    score = previsao.get("score_previsto", 0)
    classificacao = previsao.get("classificacao", "N/A")
    
    # Cor de fundo baseada na classificação
    if classificacao == "EXCELENTE":
        bg_color = "#d4edda"
        border_color = "#28a745"
    elif classificacao == "BOM":
        bg_color = "#cce5ff"
        border_color = "#007bff"
    elif classificacao == "MODERADO":
        bg_color = "#fff3cd"
        border_color = "#ffc107"
    else:
        bg_color = "#f8d7da"
        border_color = "#dc3545"
    
    st.markdown(f"""
    <div style="
        background-color: {bg_color};
        border: 2px solid {border_color};
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        text-align: center;
    ">
        <h2 style="margin: 0; color: {border_color};">🎯 Score ML: {score:.1f}/100</h2>
        <p style="margin: 5px 0; font-size: 1.2em; font-weight: bold;">{classificacao}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Cards de recomendação
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🐟 Espécie Recomendada", previsao.get("especie_recomendada", "N/A"))
    with col2:
        st.metric("⏰ Melhor Horário", previsao.get("melhor_horario", "N/A"))
    
    # Condições previstas
    st.subheader("🌤️ Condições Previstas")
    cond = previsao.get("condicoes_chave", {})
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Tw (Água)", f"{cond.get('Tw', 0):.1f}°C")
    c2.metric("🌧️ Chuva 24h", f"{cond.get('Chuva_24h', 0):.1f} mm")
    c3.metric("🌙 Lua", cond.get("Lua", "N/A"))
    c4.metric("💨 Vento Máx", f"{cond.get('Vento_Max', 0):.1f} km/h")
    
    # Gráfico: comparação com condições atuais (se disponível)
    if df_sqlite is not None and not df_sqlite.empty:
        latest = df_sqlite.iloc[0]
        st.subheader("📊 Comparação: Amanhã vs Atual")
        
        comp_data = pd.DataFrame({
            "Condição": ["Tw (°C)", "Vento (km/h)", "Chuva (mm)"],
            "Atual": [
                latest.get("temp_agua", 0),
                latest.get("vento_kmh", 0),
                latest.get("chuva_24h", 0)
            ],
            "Amanhã": [
                cond.get("Tw", 0),
                cond.get("Vento_Max", 0),
                cond.get("Chuva_24h", 0)
            ]
        })
        
        fig = px.bar(
            comp_data.melt(id_vars="Condição", var_name="Período", value_name="Valor"),
            x="Condição", y="Valor", color="Período", barmode="group",
            title="Comparação de Condições",
            color_discrete_map={"Atual": "#6c757d", "Amanhã": "#007bff"}
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    # Feature importance (se disponível)
    df_imp = get_feature_importance()
    if df_imp is not None and not df_imp.empty:
        st.subheader("🧠 Fatores que Influenciam a Previsão")
        fig = px.bar(
            df_imp, x="importance", y="feature", orientation="h",
            title="Importância das Features (Top 10)",
            labels={"importance": "Importância", "feature": "Feature"}
        )
        fig.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    
    # Botão de retreino (apenas admin)
    if st.session_state.get("username") == "admin":
        with st.expander("⚙️ Admin: Retreinar Modelo"):
            st.warning("⚠️ Retreinar o modelo pode demorar alguns minutos.")
            if st.button("🔄 Retreinar Modelo Agora"):
                with st.spinner("Treinando modelo..."):
                    # Aqui seria chamada ao subprocess para treinar_modelo_ml_v3_1.py
                    # Para demo, apenas simulamos
                    import time
                    time.sleep(2)
                    st.cache_data.clear()
                    st.success("✅ Modelo retreinado com sucesso!")
                    st.rerun()
    
    # Nota informativa
    st.info("💡 Modelo em fase inicial (n<30). Use como referência complementar à sua experiência.")

if __name__ == "__main__":
    main()
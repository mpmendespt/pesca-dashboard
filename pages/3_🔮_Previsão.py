import streamlit as st

# 🔐 GUARD DE AUTENTICAÇÃO (Impede acesso sem login)
if not st.session_state.get("authentication_status"):
    st.warning(" Acesso restrito. A sessão expirou ou não está autenticada.")
    st.page_link("streamlit_app.py", label="🔑 Ir para Login", icon="🔑")
    st.stop()
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from src.data_loader import load_previsao_amanha, get_feature_importance, load_config
from src.plots import create_kpi_card

st.set_page_config(page_title="Previsão ML", page_icon="🔮", layout="wide")

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
        
        if feat_data and feat_data["feature_importances"]:
            # Criar dataframe para plot
            df_imp = pd.DataFrame({
                'Feature': feat_data["feature_names"],
                'Importance': feat_data["feature_importances"]
            }).sort_values('Importance', ascending=True).tail(10)
            
            fig = px.bar(df_imp, x='Importance', y='Feature', orientation='h',
                         title="Top 10 Variáveis Mais Importantes (Random Forest)",
                         labels={'Importance': 'Peso na Decisão', 'Feature': 'Variável'},
                         color='Importance', color_continuous_scale='Viridis')
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning("⚠️ Metadados do modelo não disponíveis. Retreine o modelo para ver a análise.")

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
        st.table(pd.DataFrame(details.items(), columns=["Parâmetro", "Valor"]))

    with col_meta:
        st.subheader("ℹ️ Info do Modelo")
        meta = get_feature_importance()
        if meta:
            st.info(f"🤖 Modelo: {meta.get('model_type', 'N/A')}")
            st.info(f"📚 Dados Treino: {meta.get('metrics', {}).get('n_samples', 0)} sessões")
            st.info(f"📈 R² (Validação): {meta.get('metrics', {}).get('r2', 'N/A')}")
        else:
            st.info("Sem metadados.")
            
        st.divider()
        st.markdown("""
        **Nota:** A previsão é gerada automaticamente todos os dias às 06:00 pelo Task Scheduler. 
        O modelo utiliza dados de:
        - Temperatura da Água (Tw) estimada
        - Vento e Chuva (Open-Meteo)
        - Fase Lunar
        - Histórico de Capturas
        """)

if __name__ == "__main__":
    main()
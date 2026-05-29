# pages/2_🔮_Previsão.py (trecho principal)
import streamlit as st
import pandas as pd
from src import data_loader, plots, ml_loader
from pathlib import Path

st.set_page_config(page_title="🔮 Previsão ML", layout="wide")

# Carregar dados
config = data_loader.load_config()
df_capturas = data_loader.load_capturas()
previsao_json = data_loader.load_previsao_amanha()  # previsao_amanha.json

# Carregar modelo e metadados (cache)
@st.cache_resource
def get_model_and_metadata():
    model = ml_loader.load_model(config["paths"]["model_pkl"])
    metadata = ml_loader.load_model_metadata("data/model_metadata.json")
    return model, metadata

model, metadata = get_model_and_metadata()

# KPIs principais
st.title("🔮 Previsão de Pesca com Machine Learning")

if previsao_json and "score" in previsao_json:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(plots.create_kpi_card(
            "Score Previsto", previsao_json["score"], "/100",
            color="green" if previsao_json["score"] >= 70 else "orange" if previsao_json["score"] >= 40 else "red"
        ), unsafe_allow_html=True)
    with col2:
        st.markdown(plots.create_kpi_card(
            "Classificação", previsao_json.get("classe", "—"),
            color="green" if previsao_json.get("classe") == "EXCELENTE" else "blue"
        ), unsafe_allow_html=True)
    with col3:
        ci = previsao_json.get("confidence_interval", (0, 100))
        st.markdown(plots.create_kpi_card(
            "Intervalo (95%)", f"{ci[0]}–{ci[1]}", "",
            color="purple"
        ), unsafe_allow_html=True)
    with col4:
        n = metadata.get("metrics", {}).get("n_samples", 0) if metadata else 0
        st.markdown(plots.create_kpi_card(
            "Dados de Treino", str(n), " sessões",
            color="blue" if n >= 30 else "orange"
        ), unsafe_allow_html=True)

# Gráfico: Feature Importance
if metadata and "feature_importances" in metadata:
    with st.expander("📊 Importância das Variáveis", expanded=True):
        fig_imp = plots.plot_feature_importance_plotly(
            model if model else type('obj', (object,), {'feature_importances_': metadata["feature_importances"]})(),
            metadata["feature_names"],
            top_n=10
        )
        st.plotly_chart(fig_imp, use_container_width=True)

# Gráfico: Distribuição de Scores Históricos
if not df_capturas.empty and "sucesso_score" in df_capturas.columns:
    with st.expander("📈 Distribuição Histórica de Scores"):
        scores = df_capturas["sucesso_score"].dropna()
        if len(scores) > 0:
            fig_dist = plots.plot_score_distribution_plotly(scores)
            st.plotly_chart(fig_dist, use_container_width=True)

# Botão de retreino (apenas admin)
if st.session_state.get("is_admin", False):
    st.divider()
    st.subheader("⚙️ Gestão do Modelo")
    if st.button("🔄 Retreinar Modelo Agora", type="primary"):
        with st.spinner("A treinar novo modelo..."):
            # Chamar script de treino (subprocess)
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "treinar_modelo_ml_v3_1.py"],
                capture_output=True, text=True, cwd=Path(__file__).parent.parent
            )
            if result.returncode == 0:
                st.success("✅ Modelo retreinado com sucesso!")
                st.cache_resource.clear()  # Forçar recarregamento
                st.rerun()
            else:
                st.error(f"❌ Erro no treino:\n```\n{result.stderr}\n```")

# Previsões diárias (tabela interativa)
if previsao_json and "previsao_diaria" in previsao_json:
    st.divider()
    st.subheader("📅 Previsão Dia-a-Dia")
    df_prev = pd.DataFrame(previsao_json["previsao_diaria"])
    if not df_prev.empty:
        # Formatar para exibição
        df_display = df_prev.copy()
        if "Data" in df_display.columns:
            df_display["Data"] = pd.to_datetime(df_display["Data"]).dt.strftime("%d/%m")
        
        # Colorir linhas por score
        def highlight_score(val):
            if isinstance(val, (int, float)) and 0 <= val <= 100:
                if val >= 70: return "background-color: #d4edda"
                elif val >= 40: return "background-color: #fff3cd"
                elif val >= 20: return "background-color: #f8d7da"
            return ""
        
        st.dataframe(
            df_display.style.map(highlight_score, subset=["score"]),
            use_container_width=True, hide_index=True
        )
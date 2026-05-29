# pages/2_📈_Histórico.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.data_loader import load_capturas, load_sqlite_summary, load_config, get_species_list

st.set_page_config(page_title="📈 Histórico", page_icon="📊", layout="wide")

def main():
    st.title("📈 Histórico de Capturas")
    
    # Carregar dados
    config = load_config()
    df_capturas = load_capturas()
    df_sqlite = load_sqlite_summary()
    
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
        
        metrica = st.radio("Métrica:", ["Peso (kg)", "Quantidade (un)"], index=0)
        
        if st.button("🔄 Aplicar Filtros"):
            st.rerun()
    
    # Aplicar filtros
    df_filtered = df_capturas.copy()
    if especie_sel:
        suffix = "_Kg" if metrica == "Peso (kg)" else "_Qtd"
        cols_filtro = [f"{esp}{suffix}" for esp in especie_sel if f"{esp}{suffix}" in df_filtered.columns]
        if cols_filtro:
            df_filtered = df_filtered[df_filtered[cols_filtro].sum(axis=1) > 0]
    
    if len(date_range) == 2:
        mask = (df_filtered["Timestamp"].dt.date >= date_range[0]) & \
               (df_filtered["Timestamp"].dt.date <= date_range[1])
        df_filtered = df_filtered[mask]
    
    if df_filtered.empty:
        st.warning("⚠️ Nenhum dado corresponde aos filtros selecionados.")
        return
    
    # KPIs do período filtrado
    col1, col2, col3 = st.columns(3)
    suffix = "_Kg" if metrica == "Peso (kg)" else "_Qtd"
    total_col = f"Total{suffix}"
    
    col1.metric("📊 Sessões", len(df_filtered))
    col2.metric(f"🐟 Total {metrica}", f"{df_filtered[total_col].sum():.1f}")
    col3.metric(f"📈 Média/Sessão", f"{df_filtered[total_col].mean():.1f}")
    
    # Gráfico 1: Evolução temporal por espécie
    species_cols = [c for c in df_filtered.columns if c.endswith(suffix) and c != total_col]
    if species_cols:
        df_melt = df_filtered.melt(
            id_vars=["Timestamp"],
            value_vars=species_cols,
            var_name="Especie",
            value_name="Valor"
        )
        df_melt["Especie"] = df_melt["Especie"].str.replace(suffix, "")
        
        fig1 = px.area(
            df_melt.groupby(["Timestamp", "Especie"])["Valor"].sum().reset_index(),
            x="Timestamp", y="Valor", color="Especie",
            title=f"📈 Evolução de {metrica} por Espécie",
            labels={"Valor": metrica, "Timestamp": "Data"}
        )
        fig1.update_layout(height=400, hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)
    
    # Gráfico 2: Distribuição por fase lunar
    if "Fase_Lua_Captura" in df_filtered.columns:
        fig2 = px.box(
            df_filtered, 
            x="Fase_Lua_Captura", 
            y=total_col,
            color="Fase_Lua_Captura",
            title=f"🌙 {metrica} por Fase Lunar",
            labels={total_col: metrica, "Fase_Lua_Captura": "Fase"}
        )
        fig2.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    
    # Gráfico 3: Heatmap de capturas por dia da semana × hora (se disponível)
    if "hora" in df_sqlite.columns if df_sqlite is not None else False:
        st.subheader("🕐 Padrão por Dia da Semana × Hora")
        # Implementação futura quando dados horários estiverem disponíveis
    
    # Tabela detalhada expansível
    with st.expander("📋 Ver dados detalhados"):
        cols_display = ["Timestamp"] + [c for c in df_filtered.columns if c.endswith("_Qtd") or c.endswith("_Kg")]
        cols_display = [c for c in cols_display if c in df_filtered.columns]
        st.dataframe(
            df_filtered[cols_display].sort_values("Timestamp", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Timestamp": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm")
            }
        )

if __name__ == "__main__":
    main()
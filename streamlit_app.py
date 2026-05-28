# streamlit_app.py
import streamlit as st
from src.auth import get_authenticator, render_login, render_logout

st.set_page_config(page_title="🎣 Pesca Dashboard", page_icon="🎣", layout="wide", initial_sidebar_state="expanded")

def main():
    authenticator = get_authenticator()
    
    # 1. Gestão de sessão
    if not st.session_state.get("authentication_status"):
        if render_login(authenticator):
            st.rerun()
        return

    # 2. Logout & Navegação
    render_logout(authenticator)
    with st.sidebar:
        st.title("🧭 Navegação")
        page = st.radio("Ir para:", ["🏠 Início", "📈 Histórico", "🔮 Previsão", "⚙️ Configurações"], index=0, label_visibility="collapsed")
        st.divider()
        st.info("💡 Os dados atualizam automaticamente a cada 5 minutos.")

    # 3. Router de páginas
    if page == "🏠 Início":
        st.title("🎣 Dashboard de Previsão de Pesca")
        st.subheader("Rede Jazida • Barragem de Castelo de Bode")
        st.success("✅ Sistema v3.1 operacional | Autenticação ativa")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📊 Sessões", "Carregando...")
        c2.metric("🐟 Peso Total", "Carregando...")
        c3.metric("🎯 Score ML", "Carregando...")
        c4.metric("📅 Última Atualização", "Carregando...")

    elif page == "📈 Histórico":
        st.title("📈 Histórico de Capturas")
        st.info("📊 Integração com `Capturas.csv` e `previsao_pesca_ml_v3.db` será adicionada na próxima iteração.")

    elif page == "🔮 Previsão":
        st.title("🔮 Previsão para Amanhã")
        st.info("🤖 Leitura de `previsao_amanha.json` e modelo ML em integração.")

    elif page == "⚙️ Configurações":
        st.title("⚙️ Configurações")
        st.info("🔐 Gestão de utilizadores e sincronização de dados via `st.secrets`.")

if __name__ == "__main__":
    main()
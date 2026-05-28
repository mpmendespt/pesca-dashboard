# src/auth.py
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from pathlib import Path

CREDENTIALS_FILE = Path(__file__).parent.parent / "data" / "credentials.yml"

@st.cache_resource
def get_authenticator():
    """Carrega autenticação via st.secrets (Cloud) ou ficheiro YAML local."""
    try:
        if "credentials" in st.secrets:
            config = {
                "credentials": st.secrets["credentials"],
                "cookie": st.secrets["cookie"]
            }
        elif CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                config = yaml.load(f, Loader=SafeLoader)
        else:
            st.error("❌ Credenciais não encontradas. Configure `data/credentials.yml` ou `st.secrets`.")
            st.stop()
            
        return stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"]
        )
    except Exception as e:
        st.error(f"Erro ao inicializar autenticação: {e}")
        st.stop()

def render_login(authenticator):
    """Interface de login com CSS personalizado."""
    st.markdown("""
    <style>
        .login-box { background: #ffffff; padding: 2.5rem; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.12); max-width: 400px; margin: 3rem auto; }
        .stApp { background: linear-gradient(135deg, #1a3a5c 0%, #2e6da4 100%); }
        .stTextInput>div>div>input { border-radius: 8px; }
        .stButton>button { background: #2e6da4; color: white; border-radius: 8px; font-weight: 600; }
        .stButton>button:hover { background: #1a3a5c; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown("### 🎣 Pesca Dashboard v3.1")
        st.caption("Rede Jazida • Barragem de Castelo de Bode")
        st.divider()
        
        # API v0.3+: retorna (nome, status, username)
        name, auth_status, username = authenticator.login()
        
        if auth_status is False:
            st.error("❌ Utilizador ou password incorretos")
        elif auth_status is None:
            st.info("🔐 Introduza as suas credenciais para aceder")
        elif auth_status:
            st.success(f"✅ Bem-vindo, {name}!")
        st.markdown('</div>', unsafe_allow_html=True)
    return auth_status

def render_logout(authenticator):
    """Botão de logout na sidebar."""
    with st.sidebar:
        st.success(f"👤 {st.session_state.get('name', 'Utilizador')}")
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            authenticator.logout("Logout", "unrendered")
            st.rerun()
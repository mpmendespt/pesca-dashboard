# src/auth.py
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from pathlib import Path

CREDENTIALS_FILE = Path(__file__).parent.parent / "data" / "credentials.yml"

@st.cache_data(ttl=300)  # ✅ Cache APENAS do YAML (dados estáticos), não do objeto Authenticate
def _load_credentials():
    """Carrega credenciais do YAML ou st.secrets (apenas dados, sem widgets)."""
    try:
        if "credentials" in st.secrets:
            return {
                "credentials": st.secrets["credentials"],
                "cookie": st.secrets["cookie"]
            }
        elif CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                return yaml.load(f, Loader=SafeLoader)
        else:
            st.error("❌ Credenciais não encontradas.")
            st.stop()
    except Exception as e:
        st.error(f"Erro ao carregar credenciais: {e}")
        st.stop()

def get_authenticator():
    """Cria instância do authenticator (NÃO cacheada — contém widgets)."""
    config = _load_credentials()
    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"]
    )

def init_session_state():
    """Inicializa chaves obrigatórias do session_state para o authenticator."""
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None
    if "name" not in st.session_state:
        st.session_state["name"] = None
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "logout" not in st.session_state:  # ✅ Chave crítica para CookieController
        st.session_state["logout"] = False

def render_login(authenticator):
    """Interface de login com CSS personalizado."""
    init_session_state()  # ✅ Inicializa antes de qualquer widget
    
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
        
        # ✅ API v0.3+: retorna (nome, status, username)
        name, auth_status, username = authenticator.login()
        
        if auth_status is False:
            st.error("❌ Utilizador ou password incorretos")
        elif auth_status is None:
            st.info("🔐 Introduza as suas credenciais para aceder")
        elif auth_status:
            st.success(f"✅ Bem-vindo, {name}!")
            st.session_state["name"] = name
            st.session_state["username"] = username
            st.session_state["authentication_status"] = auth_status
        st.markdown('</div>', unsafe_allow_html=True)
    return auth_status

def render_logout(authenticator):
    """Botão de logout na sidebar."""
    with st.sidebar:
        st.success(f"👤 {st.session_state.get('name', 'Utilizador')}")
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            authenticator.logout("Logout", "unrendered")
            # ✅ Limpar session_state após logout
            for key in ["authentication_status", "name", "username", "logout"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from pathlib import Path
import os

CREDENTIALS_FILE = Path(__file__).parent.parent / "data" / "credentials.yml"

@st.cache_resource
def load_authenticator():
    """Carrega configuracao de autenticação com cache para performance."""
    if not CREDENTIALS_FILE.exists():
        st.error(f"❌ Ficheiro de credenciais não encontrado: {CREDENTIALS_FILE}")
        st.stop()
    
    with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
        config = yaml.load(f, Loader=SafeLoader)
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config.get('pre-authorized', {})
    )
    return authenticator

def login_page():
    """Página de login visualmente personalizada."""
    st.set_page_config(page_title="🎣 Pesca Dashboard", page_icon="🎣", layout="wide")
    
    # CSS personalizado para login bonito
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #1a3a5c 0%, #2e6da4 100%); }
        .login-box { 
            background: white; 
            padding: 2rem; 
            border-radius: 1rem; 
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            max-width: 400px; 
            margin: 3rem auto;
        }
        .login-title { 
            text-align: center; 
            color: #1a3a5c; 
            font-weight: bold; 
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
        }
        .stButton>button { 
            background: #2e6da4; 
            color: white; 
            border: none; 
            border-radius: 0.5rem;
            font-weight: bold;
        }
        .stButton>button:hover { background: #1a3a5c; }
        .footer { 
            text-align: center; 
            color: rgba(255,255,255,0.7); 
            margin-top: 2rem; 
            font-size: 0.9rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    authenticator = load_authenticator()
    
    # Container centralizado para login
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">🎣 Pesca Dashboard v3.1</div>', unsafe_allow_html=True)
        
        try:
            login_status = authenticator.login(fields={'Form name': 'Login', 'Username': 'Utilizador', 'Password': 'Password', 'Login': 'Entrar'})
        except Exception as e:
            st.error(f"Erro de autenticação: {e}")
            return None
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if login_status:
            st.success(f"✅ Bem-vindo, {st.session_state['name']}!")
            return authenticator
        elif login_status is False:
            st.error("❌ Utilizador ou password incorretos")
        elif login_status is None:
            st.info("🔐 Introduza as suas credenciais para aceder")
        
        st.markdown('<div class="footer">Sistema de Previsão de Pesca • Rede Jazida<br>Barragem de Castelo de Bode</div>', unsafe_allow_html=True)
    
    return None

def logout_button(authenticator):
    """Botão de logout estilizado na sidebar."""
    with st.sidebar:
        st.write(f"👤 {st.session_state['name']}")
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            authenticator.logout('Logout', 'unrendered')
            st.rerun()
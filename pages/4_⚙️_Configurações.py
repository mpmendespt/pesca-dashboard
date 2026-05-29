# pages/4_⚙️_Configurações.py
import streamlit as st
import yaml
from pathlib import Path
from src.data_loader import load_config
from src.auth import get_authenticator

st.set_page_config(page_title="⚙️ Configurações", page_icon="⚙️", layout="wide")

def main():
    st.title("⚙️ Configurações")
    
    config = load_config()
    authenticator = get_authenticator()
    
    # Verificar permissões de admin
    if st.session_state.get("username") != "admin":
        st.warning("🔐 Apenas administradores podem aceder a esta página.")
        return
    
    # Abas para organização
    tab1, tab2, tab3 = st.tabs(["👥 Utilizadores", "🔗 Dados", "📋 Sistema"])
    
    with tab1:
        st.subheader("👥 Gestão de Utilizadores")
        st.info("""
        Para adicionar/remover utilizadores:
        1. Edite `data/credentials.yml` localmente, OU
        2. Use **Streamlit Secrets** no painel Cloud (Settings → Secrets)
        
        Formato YAML:
        ```yaml
        credentials:
          usernames:
            novo_utilizador:
              email: "email@exemplo.com"
              name: "Nome Completo"
              password: "$2b$12$hash_gerado_via_bcrypt"
              logged_in: false
        ```
        """)
        
        # Mostrar utilizadores atuais (apenas nomes, sem passwords)
        try:
            creds_file = Path("data/credentials.yml")
            if creds_file.exists():
                with open(creds_file, "r", encoding="utf-8") as f:
                    creds = yaml.safe_load(f)
                usernames = list(creds.get("credentials", {}).get("usernames", {}).keys())
                st.write(f"**Utilizadores registados:** {', '.join(usernames)}")
            else:
                st.warning("⚠️ `data/credentials.yml` não encontrado.")
        except Exception as e:
            st.error(f"Erro ao ler credenciais: {e}")
    
    with tab2:
        st.subheader("🔗 Sincronização de Dados")
        
        st.markdown("""
        ### Opções para manter dados atualizados na cloud:
        
        #### 1. GitHub Actions + Dropbox (Recomendado)
        - Configure um workflow que faz push diário de:
          - `Capturas.csv`
          - `previsao_amanha.json`
          - `previsao_pesca_ml_v3.db` (opcional, grande)
        - O dashboard lê da pasta Dropbox montada em `/mount/data/`
        
        #### 2. Google Sheets (Simples)
        - Publique `Capturas.csv` como Google Sheet público
        - Use `gspread` para ler diretamente no `data_loader.py`
        
        #### 3. Streamlit Cloud Mount (Avançado)
        - No painel Cloud: **Settings → Data connections**
        - Conecte Dropbox/Google Drive
        - Monte em `/mount/data/`
        """)
        
        st.subheader("🔄 Forçar Atualização de Cache")
        if st.button("🔄 Recarregar Dados Agora"):
            st.cache_data.clear()
            st.success("✅ Cache limpo. Dados recarregados na próxima interação.")
    
    with tab3:
        st.subheader("📋 Informações do Sistema")
        
        # Mostrar config atual
        st.json(config, expanded=False)
        
        # Versões e paths
        st.subheader("🔍 Diagnóstico")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Ficheiros de dados:**")
            data_files = ["Capturas.csv", "previsao_pesca_ml_v3.db", "previsao_amanha.json"]
            for f in data_files:
                path = Path("data") / f
                exists = "✅" if path.exists() else "❌"
                size = f"{path.stat().st_size/1024:.1f} KB" if path.exists() else "N/A"
                st.write(f"{exists} `{f}` ({size})")
        
        with col2:
            st.write("**Módulos Python:**")
            modules = ["pandas", "numpy", "plotly", "streamlit-authenticator"]
            for mod in modules:
                try:
                    __import__(mod)
                    st.write(f"✅ `{mod}`")
                except ImportError:
                    st.write(f"❌ `{mod}` (não instalado)")
        
        # Botão de download de log (se existir)
        log_file = Path("automacao_v3.1.log")
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()
            st.download_button(
                label="📥 Download Log de Automação",
                data=log_content,
                file_name="automacao_v3.1.log",
                mime="text/plain"
            )

if __name__ == "__main__":
    main()
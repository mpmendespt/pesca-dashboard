import streamlit as st

# 🔐 GUARD DE AUTENTICAÇÃO (Impede acesso sem login)
if not st.session_state.get("authentication_status"):
    st.warning(" Acesso restrito. A sessão expirou ou não está autenticada.")
    st.page_link("streamlit_app.py", label="🔑 Ir para Login", icon="🔑")
    st.stop()
import subprocess
import sys
from pathlib import Path
from src.data_loader import load_config

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")

def main():
    st.title("⚙️ Configurações e Diagnóstico do Sistema")
    
    config = load_config()
    base_dir = Path(__file__).resolve().parent.parent
    
    # --- 1. Diagnóstico de Ficheiros ---
    st.subheader("📂 Estado dos Ficheiros")
    
    files_to_check = {
        "Capturas.csv": base_dir / "data" / "Capturas.csv",
        "Config": base_dir / "config_v3_1.json",
        "Modelo (.pkl)": base_dir / "data" / "modelo_pesca_v3_robusto.pkl",
        "Previsão (.json)": base_dir / "data" / "previsao_amanha.json",
        "Credenciais": base_dir / "data" / "credentials.yml",
        "Database (.db)": base_dir / "data" / "previsao_pesca_ml_v3.db"
    }
    
    cols = st.columns(2)
    idx = 0
    for name, path in files_to_check.items():
        exists = path.exists()
        size = f"{path.stat().st_size / 1024:.1f} KB" if exists else "—"
        status = "✅ OK" if exists else "❌ Falta"
        
        with cols[idx % 2]:
            st.markdown(f"**{name}**  \n{status} ({size})")
            if exists:
                st.caption(f"`{path}`")
        idx += 1

    st.divider()

    # --- 2. Ferramentas de Manutenção ---
    st.subheader("🛠️ Ferramentas")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("**Sincronização de Dados**")
        st.caption("Força a cópia de `Weather5` → `data/`.")
        if st.button("🔄 Sincronizar Agora", type="primary", use_container_width=True):
            with st.spinner("🔄 A sincronizar dados meteorológicos e hidrológicos..."):
                try:
                    # Tentar importar e correr o script de sync
                    from src.sync import run_sync
                    result = run_sync()  # Deve retornar dict com status
                    
                    if result.get("success"):
                        st.toast("✅ Dados sincronizados com sucesso!", icon="✅")
                        st.success(f"📦 {result.get('copied', 0)} ficheiros atualizados")
                        # Forçar refresh da cache
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.warning(f"⚠️ {result.get('message', 'Sincronização parcial')}")
                        
                except ImportError:
                    st.info("ℹ️ Sincronização automática indisponível na Cloud. Dados atualizados via API em tempo real.")
                except Exception as e:
                    st.error(f"❌ Erro na sincronização: {str(e)[:100]}")
                    st.caption("💡 Na Cloud, os dados são obtidos diretamente das APIs quando a página carrega.")

    with col_b:
        st.markdown("**Limpeza de Cache**")
        st.caption("Limpa cache do Streamlit (pode exigir refresh no browser).")
        if st.button("🧹 Limpar Cache"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("✅ Cache limpa. Recarregue a página.")

    st.divider()

    # --- 3. Sobre ---
    st.subheader("ℹ️ Sobre o Sistema")
    st.json({
        "Versão": config.get("version", "Desconhecida"),
        "Projeto": config.get("project", "Previsão Pesca"),
        "Local": config.get("location", {}).get("name", "N/A"),
        "APIs": ["Open-Meteo", "SNIRH (PDF)"],
        "Stack": ["Python 3.10", "Streamlit", "Scikit-Learn", "Plotly"]
    })

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERAR HASHES SEGUROS - streamlit-authenticator v0.3+
Compatível com API atualizada (Hasher como função estática)
"""
import streamlit_authenticator as stauth

def main():
    print("🔐 Gerador de Hashes para streamlit-authenticator v0.3+")
    print("=" * 60)
    
    # Lista de passwords para gerar hash
    passwords = [
        'senha123',      # Substitua pela password real do utilizador
        'admin456',      # Substitua pela password real do admin
        # Adicione mais conforme necessário
    ]
    
    print(f"\n📋 A processar {len(passwords)} password(s)...")
    
    # ✅ API ATUALIZADA: usar stauth.Hasher.hash_passwords() como função estática
    try:
        hashed_passwords = stauth.Hasher.hash_passwords(passwords)
        
        print("\n✅ Hashes gerados com sucesso:")
        print("-" * 60)
        for pwd, hashed in zip(passwords, hashed_passwords):
            print(f"Password: {pwd}")
            print(f"Hash:     {hashed}")
            print("-" * 60)
        
        print("\n📋 Copie os hashes para data/credentials.yml:")
        print("""
credentials:
  usernames:
    mpmendespt:
      email: mpmendespt@gmail.com
      name: Manuel Mendes
      password: COPIE_O_HASH_AQUI
      logged_in: False
    admin:
      email: admin@pesca.local
      name: Administrador
      password: COPIE_O_HASH_AQUI
      logged_in: False
        """)
        
    except AttributeError:
        # Fallback para versões muito antigas ou muito novas
        print("\n⚠️  Método hash_passwords não encontrado. Tentando alternativa...")
        try:
            # Alternativa: usar bcrypt diretamente
            import bcrypt
            print("🔧 Usando bcrypt diretamente...")
            for pwd in passwords:
                hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
                print(f"\nPassword: {pwd}")
                print(f"Hash:     {hashed}")
        except ImportError:
            print("❌ bcrypt não instalado. Execute: pip install bcrypt")
        except Exception as e:
            print(f"❌ Erro no fallback: {e}")
    except Exception as e:
        print(f"❌ Erro ao gerar hashes: {e}")
        print("\n💡 Dica: Verifique a versão do streamlit-authenticator:")
        print("   pip show streamlit-authenticator")

if __name__ == "__main__":
    main()
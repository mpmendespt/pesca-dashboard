import streamlit_authenticator as stauth
hashed_passwords = stauth.Hasher(['senha123', 'admin456']).generate()
print(hashed_passwords)  # Copie para credentials.yml

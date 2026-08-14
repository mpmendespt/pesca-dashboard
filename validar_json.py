import json
import os


def validar_json(caminho_arquivo):
    # Verifica se o arquivo realmente existe
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Erro: O arquivo '{caminho_arquivo}' não foi encontrado.")
        return False

    try:
        # Abre e tenta ler o arquivo JSON
        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
            # json.load transforma o texto do arquivo em dados do Python
            dados = json.load(arquivo)

        print(f"✅ Sucesso! O arquivo '{caminho_arquivo}' é um JSON válido.")
        print("-" * 40)
        print("Conteúdo lido com sucesso:")
        print(dados)  # Mostra o conteúdo na tela
        return True

    except json.JSONDecodeError as erro:
        # Se houver erro de sintaxe (ex: vírgula sobrando ou aspas simples), mostra aqui
        print(f"❌ Erro de sintaxe no arquivo '{caminho_arquivo}':")
        print(f"Mensagem: {erro.msg}")
        print(f"Linha: {erro.lineno}, Coluna: {erro.colno}")
        return False
    except Exception as e:
        # Captura outros erros (ex: falta de permissão para ler o arquivo)
        print(f"❌ Ocorreu um erro inesperado: {e}")
        return False


# Executa a validação apontando para o seu arquivo
if __name__ == "__main__":
    arquivo_config = "config_v3_1.json"
    validar_json(arquivo_config)

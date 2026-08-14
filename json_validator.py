#!/usr/bin/env python3
"""
Script para validar sintaxe de arquivos JSON
Uso: python json_validator.py <caminho_do_arquivo.json>
"""

import json
import sys
import os
from pathlib import Path

def validar_json(arquivo_path):
    """
    Valida se um arquivo JSON tem sintaxe correta
    
    Args:
        arquivo_path (str): Caminho para o arquivo JSON
    
    Returns:
        bool: True se válido, False caso contrário
    """
    try:
        # Verifica se o arquivo existe
        if not os.path.exists(arquivo_path):
            print(f"❌ Erro: Arquivo '{arquivo_path}' não encontrado!")
            return False
        
        # Verifica a extensão do arquivo
        if not arquivo_path.lower().endswith('.json'):
            print(f"⚠️  Aviso: O arquivo '{arquivo_path}' não tem extensão .json")
        
        # Tenta abrir e carregar o JSON
        with open(arquivo_path, 'r', encoding='utf-8') as arquivo:
            # Carrega o JSON para validar
            dados = json.load(arquivo)
            
        print(f"✅ Sucesso: '{arquivo_path}' é um JSON válido!")
        
        # Informações adicionais sobre o JSON
        print(f"📊 Tipo do conteúdo: {type(dados).__name__}")
        
        if isinstance(dados, dict):
            print(f"📋 Número de chaves: {len(dados)}")
            if len(dados) <= 10:  # Mostra chaves apenas se não for muito grande
                print(f"🔑 Chaves: {', '.join(dados.keys())}")
        elif isinstance(dados, list):
            print(f"📋 Número de itens: {len(dados)}")
        elif isinstance(dados, str):
            print(f"📝 Tamanho da string: {len(dados)} caracteres")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Erro de sintaxe JSON em '{arquivo_path}':")
        print(f"   Linha: {e.lineno}, Coluna: {e.colno}")
        print(f"   Mensagem: {e.msg}")
        
        # Mostra a linha problemática
        try:
            with open(arquivo_path, 'r', encoding='utf-8') as arquivo:
                linhas = arquivo.readlines()
                if e.lineno <= len(linhas):
                    linha_problema = linhas[e.lineno - 1].rstrip()
                    print(f"   Conteúdo da linha {e.lineno}:")
                    print(f"   {linha_problema}")
                    print(f"   {' ' * (e.colno + 2)}^")
        except Exception:
            pass
            
        return False
        
    except UnicodeDecodeError as e:
        print(f"❌ Erro de codificação em '{arquivo_path}':")
        print(f"   O arquivo não está em UTF-8 válido")
        print(f"   Detalhes: {e}")
        return False
        
    except PermissionError:
        print(f"❌ Erro: Sem permissão para ler o arquivo '{arquivo_path}'")
        return False
        
    except Exception as e:
        print(f"❌ Erro inesperado ao ler '{arquivo_path}':")
        print(f"   {type(e).__name__}: {e}")
        return False

def main():
    """Função principal do script"""
    
    # Verifica argumentos da linha de comando
    if len(sys.argv) < 2:
        print("Uso: python json_validator.py <arquivo1.json> [arquivo2.json ...]")
        print("\nExemplos:")
        print("  python json_validator.py dados.json")
        print("  python json_validator.py arquivo1.json arquivo2.json")
        print("  python json_validator.py *.json")
        
        # Pergunta se deseja testar com arquivo de exemplo
        resposta = input("\nDeseja criar e testar um arquivo JSON de exemplo? (s/N): ").lower()
        if resposta in ['s', 'sim']:
            criar_json_exemplo()
        sys.exit(1)
    
    # Processa cada arquivo informado
    arquivos_validos = 0
    arquivos_invalidos = 0
    
    for arquivo in sys.argv[1:]:
        print("\n" + "=" * 60)
        if validar_json(arquivo):
            arquivos_validos += 1
        else:
            arquivos_invalidos += 1
    
    # Resumo final
    print("\n" + "=" * 60)
    print(f"📊 RESUMO: {arquivos_validos} arquivo(s) válido(s), {arquivos_invalidos} arquivo(s) inválido(s)")
    
    sys.exit(0 if arquivos_invalidos == 0 else 1)

def criar_json_exemplo():
    """Cria um arquivo JSON de exemplo para teste"""
    exemplo_path = "exemplo.json"
    
    dados_exemplo = {
        "nome": "João Silva",
        "idade": 30,
        "email": "joao@exemplo.com",
        "habilidades": ["Python", "JSON", "Linux"],
        "endereco": {
            "rua": "Rua Exemplo",
            "numero": 123,
            "cidade": "São Paulo"
        },
        "ativo": True
    }
    
    try:
        with open(exemplo_path, 'w', encoding='utf-8') as f:
            json.dump(dados_exemplo, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Arquivo de exemplo '{exemplo_path}' criado!")
        print("\nTestando o arquivo criado:")
        validar_json(exemplo_path)
        
        print("\n💡 Dica: Você também pode testar com um JSON inválido editando este arquivo")
        print("   Por exemplo, remova uma vírgula ou adicione uma aspas no lugar errado")
        
    except Exception as e:
        print(f"❌ Erro ao criar arquivo de exemplo: {e}")

if __name__ == "__main__":
    main()
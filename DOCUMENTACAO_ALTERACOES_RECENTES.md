# Documentação das Alterações Recentes no Pipeline de Previsão de Pesca v3.1

## Visão Geral
Este documento resume as correções e melhorias aplicadas em 14/08/2026 para resolver o problema de "Nenhum PDF encontrado" no Streamlit Cloud e outras inconsistências identificadas no sistema.

## Problema Principal Resolvido
**Erro**: "Nenhum PDF encontrado em data/pdfs/ ou na raiz do projecto" no Streamlit Cloud
**Causa raiz**: O script de deploy (`deploy_dashboard.bat`) não estava adicionando os PDFs gerados ao repositório git devido à regra do `.gitignore` que bloqueava `Previsao_Pesca_*.pdf`.

## Alterações Implementadas

### 1. Correção do Script de Deploy (Deploy Fix)
- **Arquivo modificado**: `deploy_dashboard.bat`
- **Alteração**: Adicionado o flag `-f` (force) ao comando `git add` para PDFs
  ```bat
  :: Antes
  git add "%%f" 2>nul
  
  :: Depois  
  git add -f "%%f" 2>nul
  ```
- **Impacto**: Os PDFs gerados pelo pipeline (`previsao_pesca_v2_10.py`) são agora corretamente enviados para o repositório durante o deploy, resolvendo o erro "Nenhum PDF encontrado".

### 2. Resolução do BUG-03 (Conflito de Features no Treino ML)
- **Arquivo afetado**: `treinar_modelo_ml_v3_1.py` → renomeado para `treinar_modelo_ml_v3_1.py.DEPRECATO`
- **Problema**: Conflito entre treino (14+ features do SQLite JOIN) e inferência (3 features temporais)
- **Erro**: "X has 3 features, but RandomForestRegressor is expecting 25"
- **Impacto**: Elimina risco de falha no pipeline de treino e garante consistência entre treino e inferência.

### 3. Padronização do Arquivo de Configuração
- **Arquivo**: `config_v3_1.json` (copiado de Previsao_Pesca\ para Weather5\)
- **Problema**: Diferença crítica:
  - Weather5\: `"model_pkl": "modelo_pesca_v3_robusto.pkl"`
  - Previsao_Pesca\: `"model_pkl": "data/modelo_pesca_v3_robusto.pkl"`
- **Impacto**: Garantia de configuração única e consistente entre os dois diretórios do sistema.

### 4. Correção dos BUGs de Qualidade de Dados em previsao_pesca_v3_1.py

#### BUG-01: Cálculo Incorreto de chuva_72h
- **Antes**: `chuva_72h = precipitação_atual * 3` (proxy inadequado)
- **Depois**: Cálculo real da soma das precipitações dos 3 dias anteriores via API Open-Meteo Archive
- **Fallback**: Mantido método antigo em caso de falha na API
- **Impacto**: Feature `chuva_72h` agora reflete com precisão a precipitação acumulada dos últimos 3 dias.

#### BUG-02: Tratamento Incorreto de delta_24h
- **Antes**: `delta_24h = valor_calculado if dados_existirem else 0.0`
- **Depois**: `delta_24h = valor_calculado if dados_existirem else None`
- **Impacto**: Evita interpretação errônea de "sem variação" quando não há dado disponível (agora grava NULL corretamente).

### 5. Limpeza Geral e Melhorias Operacionais

#### Remoção de Arquivo Redundante
- **Arquivo removido**: `pipeline_orquestrador_v3_1.py` (substituído pelo `run_pesca_v3_1_automated.bat` v3.2)
- **Impacto**: Elimina possibilidade de execução de versão desatualizada do pipeline.

#### Implementação de Rotação Automática de Logs
- **Arquivo modificado**: `run_pesca_v3_1_automated.bat`
- **Alteração**: Adicionado bloco para remover logs com mais de 30 dias
  ```bat
  :: Log rotation: remove logs older than 30 days
  set "LOGS_DIR=%~dp0logs"
  if exist "%LOGS_DIR%" (
      forfiles /p "%LOGS_DIR%" /s /m "pipeline_*.log" /d -30 /c "cmd /c del @path"
  )
  ```
- **Impacto**: Gerenciamento automático do espaço em disco ocupado por logs.

## Benefícios Globais das Alterações
1. **Maior Estabilidade do Pipeline**: Elimina pontos de falha conhecidos que interrompiam a execução automática
2. **Melhoria na Qualidade dos Dados**: Corrige duas fontes de erro no banco de dados SQLite que afetavam a integridade das features
3. **Redução da Complexidade Operacional**: Remove ambiguidades e arquivos redundantes que confundiam a manutenção
4. **Preparação para Futuras Melhorias**: Estabelece base sólida para quando o volume de dados for suficiente para incluir features meteorológicas reais no modelo ML
5. **Conformidade com Boas Práticas**: Implementa padronização de configuração e gestão adequada de logs

## Verificação da Correção
Após as alterações acima, o fluxo completo para gerar e disponibilizar um PDF no Streamlit Cloud é:

1. Execute o pipeline completo localmente:
   ```
   run_pesca_v3_1_automated.bat
   ```

2. Depois, faça o deploy para atualizar o Streamlit Cloud:
   ```
   deploy_dashboard.bat
   ```

Esta sequência enviará os PDFs gerados para o repositório e atualizará a aplicação na nuvem em 1-2 minutos.

---
*Documento gerado como parte das atividades de manutenção e melhoria contínua do sistema de Previsão de Pesca - Rede Jazida v3.1*
*Data: 2026-08-14*
@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: =============================================================================
:: deploy_dashboard.bat v1.0
:: Faz git push dos ficheiros gerados/actualizados pelo pipeline.
:: Deve ser executado DEPOIS de run_pesca_v3_1_automated.bat.
::
:: Ficheiros incluidos no push:
::   data\Capturas.csv
::   data\previsao_amanha.json
::   data\previsao_7dias.json
::   data\modelo_pesca_v3_robusto.pkl
::   data\model_metadata.json
::   data\historico_temperaturas_castelo_bode.csv
::   data\pdfs\Previsao_Pesca_*.pdf   (PDFs mais recentes)
::
:: Ficheiros EXCLUIDOS (nao devem ir para git):
::   *.log / logs\          (logs locais)
::   *.db                   (SQLite - binario grande)
::   .env                   (credenciais)
::   previsao_amanha.json   (raiz - usa-se a versao em data\)
::   previsao_7dias.json    (raiz - idem)
:: =============================================================================

cd /d "%~dp0"

:: Verificar que estamos numa repo git
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo ERRO: Esta pasta nao e um repositorio git.
    echo       Inicializa com: git init ^&^& git remote add origin ^<url^>
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  DEPLOY DASHBOARD - git push
echo  Pasta: %~dp0
echo ============================================================
echo.

:: ----------------------------------------------------------------------------
:: Ficheiros de dados
:: ----------------------------------------------------------------------------
echo A adicionar ficheiros de dados...

git add data\Capturas.csv                              2>nul
git add data\previsao_amanha.json                      2>nul
git add data\previsao_7dias.json                       2>nul
git add data\modelo_pesca_v3_robusto.pkl               2>nul
git add data\model_metadata.json                       2>nul
git add data\historico_temperaturas_castelo_bode.csv   2>nul

:: PDFs em data\pdfs\ (padrao glob nao funciona directamente no git add em batch)
:: Usar FOR para adicionar cada PDF individualmente
if exist "data\pdfs\" (
    for %%f in ("data\pdfs\Previsao_Pesca_*.pdf") do (
        git add "%%f" 2>nul
        echo   Adicionado: %%~nxf
    )
) else (
    echo   AVISO: Pasta data\pdfs\ nao encontrada
)

:: ----------------------------------------------------------------------------
:: Verificar se ha alteracoes para commitar
:: ----------------------------------------------------------------------------
git diff --cached --quiet
if errorlevel 1 (
    :: Ha alteracoes staged — fazer commit
    set "COMMIT_MSG=Pipeline update %DATE% %TIME:~0,5%"
    echo.
    echo A commitar: !COMMIT_MSG!
    git commit -m "!COMMIT_MSG!" 2>&1

    :: Push
    echo.
    echo A fazer push para origin...
    git push 2>&1
    if errorlevel 1 (
        echo.
        echo ERRO: Push falhou. Verifica a ligacao e as credenciais git.
        pause
        exit /b 1
    )

    echo.
    echo ============================================================
    echo  Push concluido com sucesso.
    echo  Dashboard actualiza em 1-2 minutos em:
    echo  https://pesca-dashboard-teste-2025.streamlit.app/
    echo ============================================================
) else (
    echo.
    echo Nenhuma alteracao detectada. Nada para fazer push.
    echo (Os ficheiros ja estao actualizados no repositorio.)
)

echo.
if "%1"=="/auto" exit /b 0
pause

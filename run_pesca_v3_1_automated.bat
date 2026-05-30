@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: 🔐 AMBIENTE SESSION 0 & CONDA (Crucial para evitar deadlocks & crashes)
set "CONDA_DLL_SEARCH_MODIFICATION_ENABLE=1"
set "OMP_NUM_THREADS=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"

:: Carregar variáveis de ambiente (.env) para Telegram/Scripts
if exist "%~dp0.env" (
    for /f "tokens=1,* delims==" %%a in ('findstr /v "^[#;]" "%~dp0.env"') do (
        set "%%a=%%b"
    )
)

:: Ativar Conda Pesquisas
call "C:\miniforge3\Scripts\activate.bat" Pesquisas
if errorlevel 1 (
    echo ❌ Falha ao ativar ambiente Conda Pesquisas
    exit /b 1
)

cd /d "%~dp0"
set "LOGS_DIR=%~dp0logs"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

set "TIMESTAMP=%DATE:/=-%_%TIME::=-%"
set "TIMESTAMP=!TIMESTAMP: =0!"
set "LOG_FILE=%LOGS_DIR%\pipeline_!TIMESTAMP!.log"

echo 🚀 Pipeline v3.1 Iniciado em %TIMESTAMP% > "%LOG_FILE%"
echo. >> "%LOG_FILE%"

:: 1. Sincronização
echo [1/5] Sincronizando Weather5 → data/...
python -u sync_dados_dashboard.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 echo ⚠️ Sync falhou (continuando) >> "%LOG_FILE%"

:: 2. Snapshot
echo [2/5] Snapshot Meteo/Hidro...
python -u previsao_pesca_v3_1.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 echo ⚠️ Snapshot falhou (continuando) >> "%LOG_FILE%"

:: 3. Treino ML
echo [3/5] Treino Modelo ML...
python -u treinar_modelo_ml_v3_1.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 echo ⚠️ Treino falhou (continuando) >> "%LOG_FILE%"

:: 4. Previsão
echo [4/5] Gerando previsão amanhã...
python -u prever_amanha_v3_1.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 echo ⚠️ Previsão falhou >> "%LOG_FILE%"

:: 5. Telegram
echo [5/5] Enviando alerta Telegram...
python -u notificar_telegram.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 echo ⚠️ Notificação falhou >> "%LOG_FILE%"

echo. >> "%LOG_FILE%"
echo ✅ Pipeline Concluído em %TIME% >> "%LOG_FILE%"

:: Se chamado pelo Task Scheduler (/auto), fecha silenciosamente. Se manual, pausa.
if "%1"=="/auto" exit /b 0
pause
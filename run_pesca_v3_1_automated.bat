@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: 🔐 AMBIENTE SESSION 0 & CONDA (Previne deadlocks e crashes em serviços)
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

:: Ativar ambiente Conda Pesquisas
call "C:\miniforge3\Scripts\activate.bat" Pesquisas
if errorlevel 1 (
    echo ❌ Falha ao ativar ambiente Conda Pesquisas
    exit /b 1
)

cd /d "%~dp0"
echo 🚀 Pipeline v3.1 Iniciado em %DATE% %TIME%
echo ============================================================

:: 1. Sincronização
echo [1/5] 🔄 Sincronizando Weather5 → data/...
python -u sync_dados_dashboard.py
if errorlevel 1 echo ⚠️ Sync falhou, mas continuando...

:: 2. Snapshot Meteo/Hidro
echo [2/5] 📸 Snapshot Meteo/Hidro...
python -u previsao_pesca_v3_1.py
if errorlevel 1 echo ⚠️ Snapshot falhou, mas continuando...

:: 3. Treino Modelo ML
echo [3/5] 🤖 Treino Modelo ML...
python -u treinar_modelo_ml_v3_1.py
if errorlevel 1 echo ️ Treino falhou, mas continuando...

:: 4. Inferência & Previsão
echo [4/5] 🔮 Gerando previsão amanhã...
python -u prever_amanha_v3_1.py
if errorlevel 1 echo ️ Previsão falhou, mas continuando...

:: 5. Notificação Telegram
echo [5/5] 📱 Enviando alerta Telegram...
python -u notificar_telegram.py
if errorlevel 1 echo ⚠️ Notificação falhou, mas continuando...

echo ============================================================
echo ✅ Pipeline v3.1 Concluído em %TIME%

:: Se chamado pelo Task Scheduler (/auto), fecha silenciosamente. Se manual, pausa.
if "%1"=="/auto" exit /b 0
pause
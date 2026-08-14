@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: =============================================================================
:: run_pesca_v3_1_automated.bat v3.2
:: Pipeline completo: Sync -> Snapshot -> Treino -> Previsao -> PDF -> Telegram -> Sync Final
:: =============================================================================

:: AMBIENTE SESSION 0 & CONDA
set "CONDA_DLL_SEARCH_MODIFICATION_ENABLE=1"
set "OMP_NUM_THREADS=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"

:: Log rotation: remove logs older than 30 days
set "LOGS_DIR=%~dp0logs"
if exist "%LOGS_DIR%" (
    forfiles /p "%LOGS_DIR%" /s /m "pipeline_*.log" /d -30 /c "cmd /c del @path"
)

:: Carregar variaveis de ambiente (.env) para Telegram/Scripts
if exist "%~dp0.env" (
    for /f "tokens=1,* delims==" %%a in ('findstr /v "^[#;]" "%~dp0.env"') do (
        set "%%a=%%b"
    )
)

:: Ativar Conda Pesquisas
call "C:\miniforge3\Scripts\activate.bat" Pesquisas
if errorlevel 1 (
    echo ERRO: Falha ao ativar ambiente Conda Pesquisas
    exit /b 1
)


:: COPIA Capturas.csv PARA GARANTIR CONFIGURACAO UNICA
copy /Y "D:\_WORK_\work_python_and_R\___WORK5___\Weather5\Capturas.csv" "D:\_WORK_\work_python_and_R\___WORK___\Previsao_Pesca\Capturas.csv"


cd /d "%~dp0"

:: Criar pasta de logs
set "LOGS_DIR=%~dp0logs"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: Criar pasta data\pdfs\ se nao existir
if not exist "%~dp0data\pdfs" mkdir "%~dp0data\pdfs"

:: Timestamp para nome do log
set "TIMESTAMP=%DATE:/=-%_%TIME::=-%"
set "TIMESTAMP=!TIMESTAMP: =0!"
set "LOG_FILE=%LOGS_DIR%\pipeline_!TIMESTAMP!.log"

echo ============================================================ >> "%LOG_FILE%"
echo Pipeline v3.2 Iniciado em %DATE% %TIME%                     >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [1/7] Sincronizacao inicial (buscar Capturas.csv actualizado do Weather5)
:: ----------------------------------------------------------------------------
echo [1/7] Sincronizando Weather5 -^> data/...
echo [1/7] SYNC INICIAL >> "%LOG_FILE%"
python -u sync_dados_dashboard.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Sync inicial falhou (continuando) >> "%LOG_FILE%"
) else (
    echo OK: Sync inicial concluido >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [2/7] Snapshot Meteo/Lunar/Hidro -> SQLite
:: ----------------------------------------------------------------------------
echo [2/7] Snapshot Meteo/Hidro...
echo [2/7] SNAPSHOT >> "%LOG_FILE%"
python -u previsao_pesca_v3_1.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Snapshot falhou (continuando) >> "%LOG_FILE%"
) else (
    echo OK: Snapshot concluido >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [3/7] Treino ML
:: ----------------------------------------------------------------------------
echo [3/7] Treino Modelo ML (v3.1.5)...
echo [3/7] TREINO ML >> "%LOG_FILE%"
python -u treinar_modelo_ml_v3_1_5.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Treino falhou (continuando) >> "%LOG_FILE%"
) else (
    echo OK: Treino concluido >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [4/7] Previsao ML (gera previsao_amanha.json + previsao_7dias.json)
:: ----------------------------------------------------------------------------
echo [4/7] Gerando previsao amanha (+ 7 dias)...
echo [4/7] PREVISAO ML >> "%LOG_FILE%"
python -u prever_amanha_v3_1.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Previsao falhou >> "%LOG_FILE%"
) else (
    echo OK: Previsao concluida >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [5/7] Geracao do Relatorio PDF v2.10 (gera em data\pdfs\)
:: ----------------------------------------------------------------------------
echo [5/7] Gerando relatorio PDF v2.10...
echo [5/7] PDF v2.10 >> "%LOG_FILE%"
python -u previsao_pesca_v2_10.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Geracao PDF falhou (continuando) >> "%LOG_FILE%"
) else (
    echo OK: PDF gerado em data\pdfs\ >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [6/7] Notificacao Telegram
:: ----------------------------------------------------------------------------
echo [6/7] Enviando alerta Telegram...
echo [6/7] TELEGRAM >> "%LOG_FILE%"
python -u notificar_telegram.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Notificacao falhou >> "%LOG_FILE%"
) else (
    echo OK: Telegram enviado >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: [7/7] Sync final (copia JSONs, PDF e modelo para data\ apos geracao)
:: ----------------------------------------------------------------------------
echo [7/7] Sync final -^> data/...
echo [7/7] SYNC FINAL >> "%LOG_FILE%"
python -u sync_dados_dashboard.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo AVISO: Sync final falhou >> "%LOG_FILE%"
) else (
    echo OK: Sync final concluido >> "%LOG_FILE%"
)
echo. >> "%LOG_FILE%"

:: ----------------------------------------------------------------------------
:: Conclusao
:: ----------------------------------------------------------------------------
echo ============================================================ >> "%LOG_FILE%"
echo Pipeline v3.2 Concluido em %TIME%                           >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

echo.
echo Pipeline v3.2 concluido. Log: %LOG_FILE%

:: Se chamado pelo Task Scheduler (/auto), fecha silenciosamente.
if "%1"=="/auto" exit /b 0
pause

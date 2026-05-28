@echo off
setlocal
:: 🔧 CAMINHOS DO MINIFORGE (Idêntico ao v2.8 que funciona)
set "ENV_DIR=C:\miniforge3\envs\Pesquisas"
set "PYTHON_EXE=%ENV_DIR%\python.exe"
set "SCRIPT_DIR=D:\_WORK_\work_python_and_R\___WORK5___\Weather5"
set "SCRIPT_NAME=pipeline_orquestrador_v3_1.py"

:: 🔑 VARIÁVEIS CRÍTICAS PARA SESSION 0 (TASK SCHEDULER)
set "CONDA_PREFIX=%ENV_DIR%"
set "PATH=%ENV_DIR%;%ENV_DIR%\Scripts;%ENV_DIR%\Library\bin;%PATH%"
set "CONDA_DLL_SEARCH_MODIFICATION_ENABLE=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONFAULTHANDLER=1"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"

:: 📝 LOGS
set "LOG_EXEC=%SCRIPT_DIR%\automacao_v3.1.log"

cd /d "%SCRIPT_DIR%"
if not exist "%PYTHON_EXE%" (echo ERRO: Python nao encontrado >> "%LOG_EXEC%" & exit /b 1)
if not exist "%SCRIPT_DIR%\%SCRIPT_NAME%" (echo ERRO: Orquestrador nao encontrado >> "%LOG_EXEC%" & exit /b 1)

echo [%date% %time%] INICIO AUTOMACAO v3.1 >> "%LOG_EXEC%"
"%PYTHON_EXE%" "%SCRIPT_DIR%\%SCRIPT_NAME%" >> "%LOG_EXEC%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] FIM AUTOMACAO v3.1. Codigo: %EXIT_CODE% >> "%LOG_EXEC%"
endlocal
exit /b %EXIT_CODE%

:: ... (resto igual)
echo [%date% %time%] FIM AUTOMACAO v3.1. Codigo: %EXIT_CODE% >> "%LOG_EXEC%"

:: 🛡️ Força libertação de handles Session 0
timeout /t 2 >nul
exit 0
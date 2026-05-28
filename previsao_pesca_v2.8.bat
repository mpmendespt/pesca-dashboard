@echo off
setlocal

:: 🔧 CAMINHOS DO MINIFORGE
set "ENV_DIR=C:\miniforge3\envs\Pesquisas"
set "PYTHON_EXE=%ENV_DIR%\python.exe"
set "SCRIPT_DIR=D:\_WORK_\work_python_and_R\___WORK5___\Weather5"
rem set "SCRIPT_NAME=previsao_pesca_v2.9.py"
rem previsao_pesca_v2_10.py
set "SCRIPT_NAME=previsao_pesca_v2_10.py"

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
set "LOG_EXEC=%SCRIPT_DIR%\previsao_exec.log"
set "LOG_SAIDA=%SCRIPT_DIR%\previsao_saida.log"

echo [%date% %time%] INICIO >> "%LOG_EXEC%"
cd /d "%SCRIPT_DIR%"

if not exist "%PYTHON_EXE%" (echo ERRO: Python nao encontrado >> "%LOG_EXEC%" & exit /b 1)
if not exist "%SCRIPT_DIR%\%SCRIPT_NAME%" (echo ERRO: Script nao encontrado >> "%LOG_EXEC%" & exit /b 1)

:: 🚀 EXECUÇÃO DIRETA
"%PYTHON_EXE%" "%SCRIPT_DIR%\%SCRIPT_NAME%" > "%LOG_SAIDA%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] FIM. Codigo: %EXIT_CODE% >> "%LOG_EXEC%"
endlocal
exit /b %EXIT_CODE%
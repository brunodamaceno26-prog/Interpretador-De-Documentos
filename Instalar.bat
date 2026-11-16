@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Instalando o Interpretador de Contratos
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado.
    echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH".
    pause
    exit /b 1
)
echo [1/3] Criando o ambiente virtual...
python -m venv .venv
echo [2/3] Atualizando o pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
echo [3/3] Instalando o programa e as bibliotecas (pode demorar alguns minutos)...
.venv\Scripts\python.exe -m pip install -e ".[dev]" --quiet
if errorlevel 1 (
    echo.
    echo Deu erro na instalacao. Tire um print desta janela.
    pause
    exit /b 1
)
echo.
echo Pronto! Agora clique duas vezes em "Abrir Interpretador.bat".
pause

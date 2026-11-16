@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo O programa ainda nao foi instalado.
    echo Clique duas vezes em "Instalar.bat" primeiro.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m contratos.iniciar_app

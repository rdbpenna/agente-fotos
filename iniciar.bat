@echo off
title Agente de Fotos Imobiliarias
echo ================================================
echo   Agente de Fotos Imobiliarias - MVP
echo ================================================
echo.

REM Verifica se existe ambiente virtual
if exist "venv\Scripts\activate.bat" (
    echo Ativando ambiente virtual...
    call venv\Scripts\activate.bat
) else (
    echo [AVISO] Ambiente virtual nao encontrado.
    echo Execute primeiro: python -m venv venv
    echo E depois: pip install -r requirements.txt
    echo.
)

echo Iniciando aplicacao...
python main.py

if errorlevel 1 (
    echo.
    echo [ERRO] Algo deu errado. Verifique se:
    echo   1. Python 3.10+ esta instalado
    echo   2. As dependencias foram instaladas (pip install -r requirements.txt)
    echo.
    pause
)

@echo off
title Iniciar Catalogo de Perfis
echo ===================================================
echo Iniciando o Ambiente Virtual e o Servidor Streamlit...
echo ===================================================

:: Forca o terminal a entrar na pasta exata onde este arquivo .bat esta salvo
cd /d "%~dp0"

:: Ativa o ambiente virtual (que esta uma pasta atras, em D:\PYTHON)
call ..\venv\Scripts\activate.bat

:: Executa o aplicativo
streamlit run app.py

pause
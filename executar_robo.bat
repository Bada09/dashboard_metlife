@echo off
chcp 65001 > nul
echo ===================================================
echo   Robo de Atualizacao Automatica - MetLife Dashboard
echo ===================================================
cd /d "%~dp0"
python auto_updater.py
echo.
echo Pressione qualquer tecla para sair...
pause > nul

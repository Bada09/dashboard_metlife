@echo off
chcp 65001 > nul
echo =========================================================
echo   Agendamento do Robo MetLife para as 08:00 diariamente
echo =========================================================
echo.

set TASK_NAME=MetLife_Dashboard_Updater
set SCRIPT_PATH=%~dp0auto_updater.py
set BAT_PATH=%~dp0executar_robo.bat

echo Configurando tarefa agendada no Windows...
schtasks /create /tn "%TASK_NAME%" /tr "\"%SystemRoot%\System32\cmd.exe\" /c \"cd /d %~dp0 && python auto_updater.py\"" /sc daily /st 08:00 /f

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCESSO] Tarefa agendada com sucesso!
    echo O robo ira executar todos os dias automaticamente as 08:00 da manha.
) else (
    echo.
    echo [ERRO] Nao foi possivel criar o agendamento automatico.
    echo Tente executar este arquivo como Administrador (clique direito - Executar como administrador).
)

echo.
pause

@echo off
:: Muda para o diretório onde o script está localizado
cd /d "%~dp0"

:: Verifica se pythonw está no PATH
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw gui_main.py
) else (
    start "" python gui_main.py
)
exit

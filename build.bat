@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title V-AGENT - сборка

echo.
echo ===== Сборка V-AGENT =====
echo.

rem --- ищем Python: лучше всего 3.12, иначе любой доступный ---
set "PYCMD="
py -3.12 --version >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3.12"
if defined PYCMD goto have_python
python --version >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto have_python
echo [ОШИБКА] Python не найден.
echo Установите Python 3.12 с сайта python.org и поставьте галочку "Add Python to PATH".
goto fail

:have_python
echo Используется: %PYCMD%
%PYCMD% -c "import sys; sys.exit(0 if sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 echo [ВНИМАНИЕ] У вас очень новый Python. Если сборка упадёт, поставьте Python 3.12 и запустите снова.
echo.

rem --- отдельное окружение, чтобы не трогать ваш системный Python ---
if exist ".venv_build\Scripts\python.exe" goto venv_ready
echo [1/3] Создаю окружение...
%PYCMD% -m venv .venv_build
if errorlevel 1 goto fail

:venv_ready
call ".venv_build\Scripts\activate.bat"

echo [2/3] Устанавливаю библиотеки. Первый раз это занимает несколько минут...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail

echo.
echo [3/3] Собираю V-AGENT.exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist V-AGENT.spec del /q V-AGENT.spec
flet pack main.py --name V-AGENT --icon icon.ico --add-data "assets;assets"
if errorlevel 1 goto fail

if not exist "dist\V-AGENT.exe" goto fail
echo.
echo ===== ГОТОВО =====
echo Файл: %~dp0dist\V-AGENT.exe
echo Его можно отправлять другим: Python им не нужен.
explorer dist
pause
exit /b 0

:fail
echo.
echo ===== СБОРКА НЕ УДАЛАСЬ =====
echo Скопируйте текст ошибки выше и пришлите его.
pause
exit /b 1

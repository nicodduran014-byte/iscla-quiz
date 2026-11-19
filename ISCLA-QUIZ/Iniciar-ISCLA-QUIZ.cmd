@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 --version >nul 2>&1
  if not errorlevel 1 goto usar_py
)
where python >nul 2>&1
if not errorlevel 1 (
  python --version >nul 2>&1
  if not errorlevel 1 goto usar_python
)
echo No se encontro Python 3.10 o posterior. Instalalo e intenta otra vez.
pause
exit /b 1
:usar_py
py -3 servidor\app.py
goto fin
:usar_python
python servidor\app.py
:fin
if errorlevel 1 pause

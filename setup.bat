@echo off
setlocal
cd /d "%~dp0"

:: Check for Python
where python >nul 2>nul
if errorlevel 1 (
  echo Error: Python not found. Please install it from https://www.python.org/downloads/ and check "Add Python to PATH".
  exit /b 1
)

:: Create virtual environment if needed
if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
) else (
  echo Using existing virtual environment at .\venv
)

set "VENV_PY=venv\Scripts\python.exe"

:: Upgrade pip and install dependencies
echo Upgrading pip and core packaging tools...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel

if exist requirements.txt (
  echo Installing or updating dependencies from requirements.txt...
  "%VENV_PY%" -m pip install --upgrade --upgrade-strategy eager -r requirements.txt
) else (
  echo No requirements.txt found; skipping dependency installation.
)

:: Create activation helper
(
  echo @echo off
  echo setlocal
  echo cd /d "%%~dp0"
  echo call "venv\Scripts\activate"
  echo echo Virtual environment activated. To exit, type: deactivate
  echo cmd /k
) > enter_venv.bat

echo.
echo Setup complete.
echo To activate the environment later, run: enter_venv.bat
echo Or manually in CMD: call venv\Scripts\activate
pause

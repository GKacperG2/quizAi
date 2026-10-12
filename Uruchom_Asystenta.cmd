@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Brak srodowiska .venv. Zainstaluj Python 3.13 i wykonaj:
  echo py -3.13 -m venv .venv
  echo .venv\Scripts\python.exe -m pip install -e ".[dev]"
  pause
  exit /b 2
)
start "" /d "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch.pyw"
exit /b 0

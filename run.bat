@echo off
title Library Management System
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python was not found. Install Python 3 from https://www.python.org/downloads/
  echo  and tick "Add Python to PATH" during setup. Then run this file again.
  echo.
  pause
  exit /b 1
)
echo Installing requirements (first run only)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  Could not install Flask. Check your internet connection and try again.
  pause
  exit /b 1
)
echo.
%PY% app.py
echo.
echo  The server stopped. Read the message above to see why.
pause

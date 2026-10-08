@echo off
cd /d "%~dp0"
echo ---- Python ----
python --version
py -3 --version
echo.
echo ---- Flask ----
python -c "import flask; print('Flask', flask.__version__)"
echo.
echo ---- Files in this folder ----
dir /b
echo.
echo Take a photo or screenshot of this window and send it to Claude.
pause

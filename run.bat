@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Environment proyek tidak ditemukan: .venv\Scripts\python.exe
    echo Buat environment dan pasang dependensi dengan:
    echo   py -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

".venv\Scripts\python.exe" main.py
exit /b %errorlevel%

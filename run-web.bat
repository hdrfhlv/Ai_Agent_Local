@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Run the setup steps in readme.md first.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo Frontend dependencies not found. Run npm install --prefix frontend first.
    pause
    exit /b 1
)

where curl.exe >nul 2>&1
if errorlevel 1 (
    echo curl.exe is required to check local server readiness.
    pause
    exit /b 1
)

curl.exe --silent --fail http://127.0.0.1:5173/api/auth/status | findstr.exe /C:"owner_exists" >nul 2>&1
if not errorlevel 1 goto open_existing

netstat -ano -p tcp | findstr /R /C:":5173 .*LISTENING" >nul
if not errorlevel 1 (
    echo An older website server is still using port 5173.
    echo Close its server window with Ctrl+C, then run this file again.
    pause
    exit /b 1
)

curl.exe --silent --fail http://127.0.0.1:8000/api/auth/status | findstr.exe /C:"owner_exists" >nul 2>&1
if not errorlevel 1 goto api_ready

netstat -ano -p tcp | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
    echo Port 8000 is already used, but it is not the KANTI API.
    echo Close the other server using port 8000, then run this file again.
    pause
    exit /b 1
)

echo Starting KANTI API...
start "KANTI AI API" /min "%~dp0.venv\Scripts\python.exe" -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload

set "API_READY="
for /l %%I in (1,1,30) do (
    curl.exe --silent --fail http://127.0.0.1:8000/api/finance/summary | findstr.exe /C:"pengeluaran_per_kategori" >nul 2>&1
    if not errorlevel 1 (
        set "API_READY=1"
        goto api_ready
    )
    timeout /t 1 /nobreak >nul
)

if not defined API_READY (
    echo KANTI API did not start. Check the minimized "KANTI AI API" window for errors.
    pause
    exit /b 1
)

:api_ready
echo KANTI API is ready.
cd /d "%~dp0frontend"
echo Starting the website at http://127.0.0.1:5173 ...
npm run dev
exit /b %errorlevel%

:open_existing
echo KANTI website and API are already running.
start "" http://127.0.0.1:5173
exit /b 0

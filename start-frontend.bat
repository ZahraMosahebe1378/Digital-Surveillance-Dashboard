@echo off
cd /d F:\RSV\project\frontend

where node >nul 2>&1
if errorlevel 1 (
    echo Node.js is not installed. Install from https://nodejs.org/
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo Installing frontend packages...
    call npm.cmd install
)

echo Starting frontend at http://127.0.0.1:5173
echo Make sure backend is running on http://127.0.0.1:8000
echo.
echo IMPORTANT: Keep this window open. Closing it stops the frontend.
echo.
call npm.cmd run dev
if errorlevel 1 (
    echo.
    echo Frontend failed to start. See errors above.
    pause
)

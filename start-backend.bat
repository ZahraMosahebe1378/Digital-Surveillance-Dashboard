@echo off
cd /d F:\RSV\project\backend

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

echo Starting backend at http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo.
echo Tip: No activate needed. Press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000

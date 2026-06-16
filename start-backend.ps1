Set-Location "F:\RSV\project\backend"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & .\.venv\Scripts\pip install -r requirements.txt
}

Write-Host "Starting backend at http://127.0.0.1:8000"
Write-Host "API docs: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Tip: No activate needed. Press Ctrl+C to stop."

# Use full venv python path — avoids PowerShell execution policy blocking Activate.ps1
& .\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000

Set-Location "F:\RSV\project\frontend"

$npm = "C:\Program Files\nodejs\npm.cmd"
if (-not (Test-Path $npm)) {
    $npm = "npm.cmd"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is not installed. Install from https://nodejs.org/"
    exit 1
}

if (-not (Test-Path ".\node_modules")) {
    Write-Host "Installing frontend packages..."
    & $npm install
}

Write-Host "Starting frontend at http://127.0.0.1:5173"
& $npm run dev

# Complete fresh setup script
# This will create a new clean virtual environment

Write-Host "=== FRESH SETUP FOR POLICY QA ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Remove old broken venv
Write-Host "Step 1: Removing old broken venv..." -ForegroundColor Yellow
if (Test-Path ".\venv_old") {
    Remove-Item -Recurse -Force ".\venv_old" -ErrorAction SilentlyContinue
}
if (Test-Path ".\venv") {
    Rename-Item ".\venv" "venv_old" -ErrorAction SilentlyContinue
}

# Step 2: Create fresh venv
Write-Host "Step 2: Creating fresh virtual environment..." -ForegroundColor Yellow
python -m venv venv_new

# Step 3: Activate and install
Write-Host "Step 3: Installing dependencies (this will take 2-3 minutes)..." -ForegroundColor Yellow
& ".\venv_new\Scripts\python.exe" -m pip install --upgrade pip
& ".\venv_new\Scripts\python.exe" -m pip install -r requirements.txt

# Step 4: Rename to venv
Write-Host "Step 4: Finalizing setup..." -ForegroundColor Yellow
if (Test-Path ".\venv_new") {
    Rename-Item ".\venv_new" "venv"
}

Write-Host ""
Write-Host "=== SETUP COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Now you can run:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload"
Write-Host ""

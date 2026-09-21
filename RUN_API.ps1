# Simple script to run the API server
# Make sure Ollama is running first!

Write-Host "=== Starting Policy QA API ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --quiet uvicorn fastapi python-dotenv chromadb

Write-Host ""
Write-Host "Starting API on http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

& ".\venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000 --reload

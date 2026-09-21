# Simple script to run the Streamlit UI
# Run this in a SEPARATE terminal after starting the API

Write-Host "=== Starting Policy QA Web UI ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --quiet streamlit

Write-Host ""
Write-Host "Starting Streamlit UI..." -ForegroundColor Green
Write-Host "Browser will open automatically" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

& ".\venv\Scripts\python.exe" -m streamlit run ui.py

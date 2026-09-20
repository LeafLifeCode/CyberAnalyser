# run_both.ps1
# Launches both Port 8501 (Analyst App) and Port 8502 (Privileged Cyber Portal)
# in two independent background/window processes simultaneously.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "🚀 Launching PAFCCI Dual-Service Architecture..." -ForegroundColor Cyan

# Launch Port 8501 in a separate PowerShell process
Write-Host "  -> Starting Port 8501 (Analyst & Intelligence Map)..." -ForegroundColor Yellow
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$scriptDir'; .\.venv\Scripts\streamlit.exe run app.py --server.port 8501"

# Launch Port 8502 in a separate PowerShell process
Write-Host "  -> Starting Port 8502 (Privileged Cyber Portal)..." -ForegroundColor Green
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd '$scriptDir'; .\.venv\Scripts\streamlit.exe run portal_app.py --server.port 8502"

Write-Host ""
Write-Host "✅ Both services successfully launched in dedicated windows!" -ForegroundColor Green
Write-Host "   • Analyst / Heatmap Surface: http://localhost:8501 (Read-Only)" -ForegroundColor White
Write-Host "   • Privileged Cyber Portal:    http://localhost:8502 (Action Taking)" -ForegroundColor White

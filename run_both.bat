@echo off
title PAFCCI Dual Service Launcher
echo ===================================================
echo   PAFCCI Multi-Port Service Launcher
echo ===================================================
echo.
echo [1/2] Starting Port 8501 (Analyst / Heatmap App)...
start "PAFCCI Port 8501 - Analyst & Intelligence Map" cmd /k ".\.venv\Scripts\streamlit.exe run app.py --server.port 8501"

echo [2/2] Starting Port 8502 (Privileged Cyber Portal)...
start "PAFCCI Port 8502 - Privileged Cyber Portal" cmd /k ".\.venv\Scripts\streamlit.exe run portal_app.py --server.port 8502"

echo.
echo ===================================================
echo Both services launched in separate windows!
echo   - Analyst App:        http://localhost:8501
echo   - Privileged Portal:  http://localhost:8502
echo ===================================================
echo.
pause

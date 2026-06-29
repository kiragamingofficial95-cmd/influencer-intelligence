@echo off
cd /d "%~dp0"
echo Starting Agency Intelligence System...
echo Dashboard: http://localhost:8000
echo Press Ctrl+C to stop
python -X utf8 -m uvicorn main:app --host 0.0.0.0 --port 8000
pause

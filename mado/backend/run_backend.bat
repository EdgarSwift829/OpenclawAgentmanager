@echo off
:: Helper: activate venv and start uvicorn backend
call "%~dp0..\.venv\Scripts\activate.bat"
cd /d "%~dp0"
python -m uvicorn mado.backend.api.main:app --host 0.0.0.0 --port 8000 --reload

@echo off
rem Prepare l'environnement Python, telecharge les livres et construit les index.
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv || goto :erreur )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt || goto :erreur

python backend\scripts\setup_data.py --target 1700 || goto :erreur
if not exist data\ranking.db (
  python backend\scripts\build_graph.py --data data || goto :erreur
)

cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
goto :fin

:erreur
echo.
echo Une erreur est survenue. Verifiez Python, Internet et les dependances.
:fin
pause

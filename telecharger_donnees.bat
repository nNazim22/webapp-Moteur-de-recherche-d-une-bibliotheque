@echo off
rem Prepare l environnement Python, telecharge les livres et construit l index.
rem Double-clic possible. Options : --run, --source catalog, ...
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv || goto :erreur )
call .venv\Scripts\activate.bat
python -m pip install -q -r backend\requirements.txt || goto :erreur
python backend\scripts\setup_data.py %*
goto :fin
:erreur
echo.
echo Erreur : verifiez que Python 3.10 ou plus est installe (commande "python").
:fin
pause

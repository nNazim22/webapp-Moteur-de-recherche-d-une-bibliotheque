#!/usr/bin/env sh
# Prépare l'environnement Python, télécharge les livres et construit l'index.
# Usage : sh telecharger_donnees.sh            (options : --run, --source catalog, ...)
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -q -r backend/requirements.txt
python backend/scripts/setup_data.py "$@"

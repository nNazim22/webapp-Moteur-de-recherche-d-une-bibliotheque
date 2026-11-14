#!/bin/sh
set -e

if [ ! -f data/index.db ]; then
  echo ">> Données absentes : téléchargement des livres et construction de l'index..."
  python backend/scripts/setup_data.py
fi

exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
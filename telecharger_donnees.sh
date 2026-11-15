#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p data/books

NB=$(find data/books -maxdepth 1 -type f -name '*.txt' | wc -l | tr -d ' ')
if [ "$NB" -lt 1664 ]; then
  echo ">> $NB livres présents : téléchargement et construction de l'index..."
  python backend/scripts/setup_data.py
else
  echo ">> $NB fichiers de livres présents."
  if [ ! -f data/index.db ]; then
    python backend/scripts/build_index.py --data data
  fi
fi

if [ ! -f data/ranking.db ]; then
  echo ">> Construction du graphe de Jaccard et des centralités..."
  python backend/scripts/build_graph.py --data data
fi

exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}"

#!/bin/sh
set -e
mkdir -p data

# 1. Livres : on télécharge s'il en manque
NB=$(ls data/books 2>/dev/null | wc -l)
if [ "$NB" -lt 1664 ]; then
  echo ">> $NB livres présents : téléchargement..."
  python backend/scripts/setup_data.py
fi

# 2. Index : on le construit si la table vocab est absente
if [ ! -f data/index.db ] || ! python -c "import sqlite3; sqlite3.connect('data/index.db').execute('select 1 from vocab limit 1')" 2>/dev/null; then
  echo ">> Index absent ou incomplet : construction..."
  rm -f data/index.db
  python backend/scripts/build_index.py
fi

# 3. Graphe de Jaccard + centralités (classement)
if [ ! -f data/ranking.db ] || ! python -c "import sqlite3; sqlite3.connect('data/ranking.db').execute('select 1 from centrality limit 1')" 2>/dev/null; then
  echo ">> Graphe de Jaccard absent : construction..."
  python backend/scripts/build_graph.py
fi

exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000

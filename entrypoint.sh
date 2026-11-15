#!/bin/sh
set -eu
mkdir -p data/books

# 1. Le corpus complet est préparé au premier démarrage.
NB=$(find data/books -maxdepth 1 -type f -name '*.txt' | wc -l | tr -d ' ')
if [ "$NB" -lt 1664 ]; then
  echo ">> $NB livres présents : préparation du corpus (minimum demandé : 1664)..."
  python backend/scripts/setup_data.py --target 1700
fi

# 2. Index inversé SQLite.
if [ ! -f data/index.db ] || ! python -c "import sqlite3; sqlite3.connect('data/index.db').execute('select 1 from vocab limit 1')" 2>/dev/null; then
  echo ">> Construction de l'index inversé..."
  rm -f data/index.db
  python backend/scripts/build_index.py --data data
fi

# 3. Graphe de Jaccard et centralités. L'API reste disponible en mode occurrences
# si le calcul du graphe échoue (mémoire/temps insuffisants).
if [ ! -f data/ranking.db ] || ! python -c "import sqlite3; sqlite3.connect('data/ranking.db').execute('select 1 from centrality limit 1')" 2>/dev/null; then
  echo ">> Construction du graphe de Jaccard et des centralités..."
  python backend/scripts/build_graph.py --data data || echo ">> ATTENTION : graphe indisponible ; le classement par occurrences reste actif."
fi

exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000

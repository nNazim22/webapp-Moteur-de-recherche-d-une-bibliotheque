"""Route de données de la page graphe.html : /api/graph.

La page elle-même (frontend/graphe.html) est servie par le montage statique de main.py.
Branchement dans main.py, AVANT le montage de frontend/ :
    from .graph_api import router as graph_router
    app.include_router(graph_router)
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .ranking import export_graphe

router = APIRouter()

# backend/app/graph_api.py -> racine du projet = parents[2] (comme FRONTEND dans main.py)
ROOT = Path(__file__).resolve().parents[2]
_cache = {}


@router.get("/api/graph")
def api_graph():
    """Sommets (positions, centralités, titre) et arêtes du graphe de Jaccard."""
    if "g" not in _cache:
        g = export_graphe(ROOT / "data" / "ranking.db", ROOT / "data" / "manifest.csv")
        if g is None:
            raise HTTPException(status_code=404, detail="ranking.db absent : lancer build_graph.py")
        _cache["g"] = g
    return _cache["g"]
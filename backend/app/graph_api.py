"""Route de la page « Graphe » : /graphe (page HTML) et /api/graph (données).

Branchement dans main.py (2 lignes) :
    from app.graph_api import router as graph_router
    app.include_router(graph_router)
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.ranking import export_graphe

router = APIRouter()

# backend/app/graph_api.py -> racine du projet = parents[2]
ROOT = Path(__file__).resolve().parents[2]
_cache = {}


@router.get("/api/graph")
def api_graph():
    if "g" not in _cache:
        g = export_graphe(ROOT / "data" / "ranking.db", ROOT / "data" / "manifest.csv")
        if g is None:
            raise HTTPException(status_code=404, detail="ranking.db absent : lancer build_graph.py")
        _cache["g"] = g
    return _cache["g"]


@router.get("/graphe")
def page_graphe():
    return FileResponse(ROOT / "frontend" / "graphe.html")
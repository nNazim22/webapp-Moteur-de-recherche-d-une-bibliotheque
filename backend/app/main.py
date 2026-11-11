"""API web : expose la recherche de bibliothèque et sert l'interface (dossier frontend/).

Lancement (depuis le dossier backend/) :
    uvicorn app.main:app --reload
Documentation interactive de l'API : http://127.0.0.1:8000/docs
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .search import Library

app = FastAPI(title="Moteur de recherche de bibliothèque")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@lru_cache
def get_library():
    """Charge l'index une seule fois, à la première requête, puis le réutilise."""
    return Library()


def run_search(lib, query, mode, limit):
    try:
        return lib.search(query, mode, limit)
    except ValueError as e:                       # requête vide, regex invalide...
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stats")
def api_stats(lib: Library = Depends(get_library)):
    """Taille de la bibliothèque (affichée dans l'interface)."""
    return {"books": lib.n_books, "terms": len(lib.vocab)}


@app.get("/api/search")
def api_search(
    q: str = Query(..., description="mot-clé"),
    mode: Literal["exact", "substring"] = "exact",
    limit: int = Query(20, ge=1, le=100),
    lib: Library = Depends(get_library),
):
    """Recherche par mot-clé (mot exact ou sous-chaîne), classée par occurrences."""
    return run_search(lib, q, mode, limit)


@app.get("/api/advanced")
def api_advanced(
    regex: str = Query(..., description="expression régulière"),
    limit: int = Query(20, ge=1, le=100),
    lib: Library = Depends(get_library),
):
    """Recherche avancée par expression régulière, classée par occurrences."""
    return run_search(lib, regex, "regex", limit)


# L'interface (HTML/JS) est servie par la même application : un seul serveur à lancer.
# Ce montage doit rester en dernier, sinon il masquerait les routes /api.
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
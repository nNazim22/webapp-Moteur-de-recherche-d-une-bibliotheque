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

from .reader import find_hit_pages, load_pages
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


def book_pages_or_404(lib, book_id):
    """Métadonnées et pages d'un livre, ou erreur 404 s'il est inconnu ou si son fichier manque."""
    book = lib.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre inconnu")
    path = lib.book_path(book_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Texte du livre introuvable sur le serveur")
    return book, load_pages(str(path))


@app.get("/api/books/{book_id}")
def api_book(book_id: int, lib: Library = Depends(get_library)):
    """Titre, auteur, taille et nombre de pages d'un livre."""
    book, pages = book_pages_or_404(lib, book_id)
    return {**book, "n_pages": len(pages)}


@app.get("/api/books/{book_id}/pages/{page}")
def api_page(book_id: int, page: int, lib: Library = Depends(get_library)):
    """Une page du livre : liste de paragraphes."""
    _, pages = book_pages_or_404(lib, book_id)
    if not 1 <= page <= len(pages):
        raise HTTPException(status_code=404, detail="Page inexistante")
    return {"page": page, "n_pages": len(pages), "paragraphs": list(pages[page - 1])}


@app.get("/api/books/{book_id}/hits")
def api_hits(
    book_id: int,
    terms: str = Query(..., description="mots à repérer, séparés par des virgules"),
    whole: bool = True,
    lib: Library = Depends(get_library),
):
    """Numéros des pages du livre qui contiennent au moins un des mots."""
    _, pages = book_pages_or_404(lib, book_id)
    words = [t.strip() for t in terms.split(",") if t.strip()]
    if not words or len(words) > 50 or any(len(w) > 60 for w in words):
        raise HTTPException(status_code=400, detail="Liste de mots invalide (1 à 50 mots)")
    return {"pages": find_hit_pages(pages, words, whole)}


# L'interface (HTML/JS) est servie par la même application : un seul serveur à lancer.
# Ce montage doit rester en dernier, sinon il masquerait les routes /api.
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
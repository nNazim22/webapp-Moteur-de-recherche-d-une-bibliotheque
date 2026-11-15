"""Lecture d'un livre : découpage du texte en pages et recherche des pages contenant des mots.

Le texte brut de Gutenberg est coupé en lignes de ~70 caractères. Pour l'afficher
confortablement, on le découpe en paragraphes, on recolle les lignes des paragraphes
de prose, puis on regroupe les paragraphes en pages d'environ PAGE_CHARS caractères.
"""
import re
from functools import lru_cache
from pathlib import Path

PAGE_CHARS = 4000            # taille approximative d'une page (en caractères)
LETTER = r"[^\W\d_]"         # une lettre : même définition que le découpage en mots de l'index


def format_paragraph(raw):
    """Nettoie un paragraphe.

    Prose (lignes longues, coupées à ~70 caractères) : on recolle les lignes.
    Vers, pièces de théâtre, listes (lignes courtes) : on garde les retours à la ligne.
    """
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if not lines:
        return ""
    body = lines[:-1] if len(lines) > 1 else lines      # la dernière ligne d'un paragraphe est souvent courte
    average = sum(len(line) for line in body) / len(body)
    return " ".join(lines) if average >= 50 else "\n".join(lines)


def split_pages(text, page_chars=PAGE_CHARS):
    """Texte complet -> tuple de pages ; une page = tuple de paragraphes."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    pages, current, size = [], [], 0
    for raw in re.split(r"\n\s*\n", text):
        paragraph = format_paragraph(raw)
        if not paragraph:
            continue
        current.append(paragraph)
        size += len(paragraph)
        if size >= page_chars:
            pages.append(tuple(current))
            current, size = [], 0
    if current:
        pages.append(tuple(current))
    return tuple(pages)


@lru_cache(maxsize=8)
def load_pages(path):
    """Lit un livre et le découpe en pages. Les 8 derniers livres lus restent en mémoire."""
    return split_pages(Path(path).read_text(encoding="utf-8", errors="replace"))


def find_hit_pages(pages, terms, whole=True):
    """Numéros (à partir de 1) des pages contenant au moins un des mots.

    whole=True  : mot entier (pas de lettre juste avant ou juste après) ;
    whole=False : simple sous-chaîne.
    """
    terms = sorted({t for t in terms if t}, key=len, reverse=True)
    if not terms:
        return []
    pattern = "|".join(re.escape(t) for t in terms)
    if whole:
        pattern = rf"(?<!{LETTER})(?:{pattern})(?!{LETTER})"
    rx = re.compile(pattern, re.IGNORECASE)
    return [i for i, page in enumerate(pages, 1) if any(rx.search(p) for p in page)]
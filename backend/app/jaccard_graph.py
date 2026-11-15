"""Construction du graphe de Jaccard et calcul des indices de centralité.

Pipeline (exécuté une seule fois, hors ligne) :
  1. chaque livre -> ensemble de mots (sans en-tête/pied de page Gutenberg) ;
  2. filtre sur la fréquence documentaire : on garde les mots présents dans
     au moins `df_min` livres et dans au plus `df_max_ratio` des livres ;
  3. similarité de Jaccard J(A,B) = |A ∩ B| / |A ∪ B| pour toutes les paires
     (produit matriciel par blocs de colonnes, exact sur le vocabulaire filtré) ;
  4. graphe : un sommet par livre, arête (A,B) si B est parmi les `k` plus
     proches voisins de A (ou inversement) avec J >= `j_min` ; poids = J,
     distance = 1 - J ;
  5. centralités : PageRank, closeness (et betweenness en option) ;
  6. écriture dans une base SQLite séparée (data/ranking.db).
"""
from __future__ import annotations

import csv
import re
import sqlite3
import time
from pathlib import Path

import networkx as nx
import numpy as np

WORD_RE = re.compile(r"[a-z]{3,}")
START_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG[^\n]*\n", re.I)
END_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG", re.I)


def strip_gutenberg(text: str) -> str:
    """Retire la licence Gutenberg (identique dans tous les livres : elle
    gonflerait artificiellement la similarité)."""
    m = START_RE.search(text)
    if m:
        text = text[m.end():]
    m = END_RE.search(text)
    if m:
        text = text[: m.start()]
    return text


def book_hashes(path: Path) -> np.ndarray:
    """Ensemble des mots du livre, sous forme de hachés 64 bits triés et uniques."""
    text = strip_gutenberg(path.read_text(encoding="utf-8", errors="ignore").lower())
    words = set(WORD_RE.findall(text))
    arr = np.fromiter((hash(w) & 0xFFFFFFFFFFFFFFFF for w in words), dtype=np.uint64, count=len(words))
    arr.sort()
    return arr


def load_books(books_dir: Path):
    files = sorted(books_dir.glob("*.txt"), key=lambda p: (len(p.stem), p.stem))
    ids, sets = [], []
    for i, f in enumerate(files, 1):
        ids.append(int(f.stem) if f.stem.isdigit() else f.stem)
        sets.append(book_hashes(f))
        if i % 100 == 0:
            print(f"  {i}/{len(files)} livres lus", flush=True)
    return ids, sets


def filter_vocabulary(sets, df_min=2, df_max_ratio=0.5):
    """Remplace les hachés par des indices de colonnes compacts, en ne gardant
    que les mots dont la fréquence documentaire est dans [df_min, max(df_min, df_max_ratio*N)]."""
    n = len(sets)
    allh = np.concatenate(sets)
    uniq, counts = np.unique(allh, return_counts=True)
    # Sur un corpus de démonstration très réduit, df_max_ratio*N peut être
    # inférieur à df_min : on garde alors au moins les termes ayant df_min.
    max_df = max(df_min, df_max_ratio * n)
    keep = uniq[(counts >= df_min) & (counts <= max_df)]
    cols = []
    for s in sets:
        if len(keep) == 0:
            cols.append(np.zeros(0, dtype=np.int32))
            continue
        pos = np.searchsorted(keep, s)
        pos[pos == len(keep)] = 0
        ok = keep[pos] == s
        cols.append(pos[ok].astype(np.int32))  # déjà triés car s est trié
    return cols, len(keep)


def jaccard_matrix(cols, n_cols, block=20000):
    """Matrice n x n des similarités de Jaccard (exacte sur le vocabulaire filtré)."""
    n = len(cols)
    inter = np.zeros((n, n), dtype=np.float32)
    sizes = np.array([len(c) for c in cols], dtype=np.float32)
    for c0 in range(0, n_cols, block):
        c1 = min(c0 + block, n_cols)
        B = np.zeros((n, c1 - c0), dtype=np.float32)
        for i, c in enumerate(cols):
            a, b = np.searchsorted(c, [c0, c1])
            B[i, c[a:b] - c0] = 1.0
        inter += B @ B.T
    union = sizes[:, None] + sizes[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        J = np.where(union > 0, inter / union, 0.0).astype(np.float32)
    np.fill_diagonal(J, 0.0)
    return J


def build_graph(ids, J, k=20, j_min=0.0):
    """Graphe k-plus-proches-voisins (union symétrique) pondéré par Jaccard."""
    n = len(ids)
    G = nx.Graph()
    G.add_nodes_from(ids)
    k = min(k, n - 1)
    if k <= 0:
        return G
    nn = np.argpartition(-J, k - 1, axis=1)[:, :k]
    for i in range(n):
        for j in nn[i]:
            w = float(J[i, j])
            if w > j_min and w > 0:
                G.add_edge(ids[i], ids[int(j)], weight=w, dist=max(1e-6, 1.0 - w))
    return G


def centralities(G, with_betweenness=False):
    out = {
        "pagerank": nx.pagerank(G, weight="weight"),
        "closeness": nx.closeness_centrality(G, distance="dist"),
        "degree": dict(G.degree()),
    }
    if with_betweenness:
        out["betweenness"] = nx.betweenness_centrality(G, weight="dist")
    return out


def layout(G, seed=42):
    """Positions 2D des sommets (Fruchterman-Reingold pondéré par Jaccard),
    normalisées dans [0,1] ; calculées une fois ici pour que le navigateur
    n'ait qu'à dessiner."""
    if G.number_of_nodes() == 0:
        return {}
    pos = nx.spring_layout(G, weight="weight", seed=seed, iterations=100)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    dx, dy = (x1 - x0) or 1.0, (y1 - y0) or 1.0
    return {n: ((p[0] - x0) / dx, (p[1] - y0) / dy) for n, p in pos.items()}


def save(db_path: Path, G, cent, params, pos=None):
    pos = pos or {}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("""CREATE TABLE centrality(
        book_id INTEGER PRIMARY KEY, pagerank REAL, closeness REAL,
        betweenness REAL, degree INTEGER, x REAL, y REAL)""")
    con.execute("CREATE TABLE jaccard_edges(a INTEGER, b INTEGER, jaccard REAL)")
    con.execute("CREATE INDEX idx_edges_a ON jaccard_edges(a)")
    con.execute("CREATE INDEX idx_edges_b ON jaccard_edges(b)")
    con.execute("CREATE TABLE params(key TEXT, value TEXT)")
    con.executemany(
        "INSERT INTO centrality VALUES(?,?,?,?,?,?,?)",
        [(int(b), cent["pagerank"][b], cent["closeness"][b],
          cent.get("betweenness", {}).get(b), int(cent["degree"][b]),
          pos.get(b, (None, None))[0], pos.get(b, (None, None))[1]) for b in G.nodes],
    )
    con.executemany(
        "INSERT INTO jaccard_edges VALUES(?,?,?)",
        [(int(a), int(b), d["weight"]) for a, b, d in G.edges(data=True)],
    )
    con.executemany("INSERT INTO params VALUES(?,?)", [(k, str(v)) for k, v in params.items()])
    con.commit()
    con.close()


def titles(manifest: Path):
    """Titres lus dans manifest.csv si une colonne title/titre existe."""
    if not manifest.exists():
        return {}
    with manifest.open(encoding="utf-8", errors="ignore", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    idk = next((c for c in rows[0] if c.lower() in ("id", "book_id", "gutenberg_id")), None)
    tk = next((c for c in rows[0] if c.lower() in ("title", "titre")), None)
    if not idk or not tk:
        return {}
    return {r[idk].strip(): r[tk].strip() for r in rows}


def run(data_dir="data", k=20, j_min=0.0, df_min=2, df_max_ratio=0.5,
        with_betweenness=True, top=10):
    data = Path(data_dir)
    t0 = time.time()
    print("1/5 Lecture des livres...")
    ids, sets = load_books(data / "books")
    if len(ids) < 2:
        raise SystemExit("Il faut au moins 2 livres dans data/books")
    print(f"2/5 Filtrage du vocabulaire ({len(ids)} livres)...")
    cols, n_cols = filter_vocabulary(sets, df_min, df_max_ratio)
    del sets
    print(f"    {n_cols} mots conservés")
    print("3/5 Similarités de Jaccard (toutes les paires)...")
    J = jaccard_matrix(cols, n_cols)
    print("4/5 Graphe et centralités...")
    G = build_graph(ids, J, k=k, j_min=j_min)
    print(f"    {G.number_of_nodes()} sommets, {G.number_of_edges()} arêtes, "
          f"{nx.number_connected_components(G)} composante(s) connexe(s)")
    cent = centralities(G, with_betweenness)
    print("    placement des sommets pour la visualisation...")
    pos = layout(G)
    print("5/5 Écriture de data/ranking.db...")
    params = dict(k=k, j_min=j_min, df_min=df_min, df_max_ratio=df_max_ratio,
                  mots_conserves=n_cols, livres=len(ids), aretes=G.number_of_edges())
    save(data / "ranking.db", G, cent, params, pos)
    tt = titles(data / "manifest.csv")
    for crit in ("pagerank", "closeness") + (("betweenness",) if with_betweenness else ()):
        print(f"\nTop {top} - {crit}")
        for b, v in sorted(cent[crit].items(), key=lambda x: -x[1])[:top]:
            print(f"  {b:>8}  {v:.6f}  {tt.get(str(b), '')[:60]}")
    print(f"\nTerminé en {time.time() - t0:.0f} s")
    return G, cent
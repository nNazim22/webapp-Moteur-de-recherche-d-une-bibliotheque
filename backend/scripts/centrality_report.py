"""Rapport sur le graphe de Jaccard et les centralités (pour la partie « indice de centralité » du rapport).

Produit, dans le dossier de sortie :
    centralite_top.csv        top N livres pour chaque indice (PageRank, closeness, betweenness)
    centralite_correlations   corrélations de rang (Spearman) entre les indices et le degré
    centralite_exemples.md    fiche détaillée de quelques livres : valeurs des indices + voisins les plus proches
    graphe_stats              taille, densité, composantes, degré moyen du graphe

Usage (depuis la racine du projet, après build_graph.py) :
    python backend/scripts/centrality_report.py --data data --out benchmarks --top 10
    python backend/scripts/centrality_report.py --books 84 1342 2701      # fiches de livres précis
"""
import argparse
import csv
import sqlite3
import statistics
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.jaccard_graph import titles           # noqa: E402

CRITERIA = ["pagerank", "closeness", "betweenness"]


def ranks(values):
    """Rangs moyens (les égalités se partagent la moyenne de leurs rangs)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="benchmarks")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--books", type=int, nargs="*", help="ids des livres à détailler (défaut : le n°1 de chaque indice)")
    a = ap.parse_args()

    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    db = data / "ranking.db"
    if not db.exists():
        raise SystemExit(f"{db} introuvable : lancez d'abord build_graph.py")
    tt = titles(data / "manifest.csv")

    with closing(sqlite3.connect(db)) as con:
        rows = con.execute("SELECT book_id, pagerank, closeness, betweenness, degree FROM centrality").fetchall()
        n_edges = con.execute("SELECT COUNT(*) FROM jaccard_edges").fetchone()[0]
        params = dict(con.execute("SELECT key, value FROM params").fetchall())
        edges = con.execute("SELECT a, b, jaccard FROM jaccard_edges").fetchall()
    ids = [r[0] for r in rows]
    col = {"pagerank": [r[1] for r in rows], "closeness": [r[2] for r in rows],
           "betweenness": [r[3] or 0.0 for r in rows], "degree": [r[4] for r in rows]}
    n = len(ids)

    # --- statistiques du graphe
    adj = {i: set() for i in ids}
    for x, y, _ in edges:
        adj[x].add(y)
        adj[y].add(x)
    seen, comps = set(), 0
    for s in ids:
        if s in seen:
            continue
        comps += 1
        stack = [s]
        seen.add(s)
        while stack:
            for v in adj[stack.pop()]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    stats = {"sommets": n, "aretes": n_edges, "composantes_connexes": comps,
             "densite": round(2 * n_edges / (n * (n - 1)), 5) if n > 1 else 0,
             "degre_moyen": round(statistics.fmean(col["degree"]), 2), "degre_max": max(col["degree"]),
             "jaccard_moyen_des_aretes": round(statistics.fmean(j for *_, j in edges), 4) if edges else 0,
             **{f"param_{k}": v for k, v in params.items()}}
    with open(out / "graphe_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["indicateur", "valeur"])
        w.writerows(stats.items())
    print("Graphe de Jaccard :", ", ".join(f"{k}={v}" for k, v in stats.items() if not k.startswith("param_")))

    # --- top N
    with open(out / "centralite_top.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["indice", "rang", "id", "titre", "valeur", "degre"])
        for crit in CRITERIA:
            order = sorted(range(n), key=lambda i: -col[crit][i])[: a.top]
            print(f"\nTop {a.top} - {crit}")
            for rank, i in enumerate(order, 1):
                title = tt.get(str(ids[i]), "")
                w.writerow([crit, rank, ids[i], title, f"{col[crit][i]:.6f}", col["degree"][i]])
                print(f"  {rank:2d}. {ids[i]:>8}  {col[crit][i]:.6f}  deg {col['degree'][i]:3d}  {title[:55]}")
    print(f"  -> {out / 'centralite_top.csv'}")

    # --- corrélations
    names = CRITERIA + ["degree"]
    with open(out / "centralite_correlations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([""] + names)
        print("\nCorrélation de rang (Spearman)")
        print("             " + "".join(f"{c:>12}" for c in names))
        for x in names:
            vals = [round(spearman(col[x], col[y]), 3) for y in names]
            w.writerow([x] + vals)
            print(f"  {x:>11}" + "".join(f"{v:12.3f}" for v in vals))

    # --- fiches de livres
    chosen = a.books or [ids[max(range(n), key=lambda i: col[c][i])] for c in CRITERIA]
    chosen = list(dict.fromkeys(chosen))
    pos = {b: i for i, b in enumerate(ids)}
    lines = ["# Exemples d'indices de centralité sur des livres de la bibliothèque\n"]
    for b in chosen:
        if b not in pos:
            print(f"(livre {b} absent du graphe)")
            continue
        i = pos[b]
        lines += [f"## [{b}] {tt.get(str(b), '')}\n", "| indice | valeur | rang |", "|---|---|---|"]
        for c in names:
            rk = sorted(col[c], reverse=True).index(col[c][i]) + 1
            lines.append(f"| {c} | {col[c][i]:.6f} | {rk} / {n} |")
        neigh = sorted(((y if x == b else x), j) for x, y, j in edges if b in (x, y))
        neigh.sort(key=lambda t: -t[1])
        lines += ["", "Voisins les plus proches (similarité de Jaccard) :\n"]
        lines += [f"- {j:.3f} — [{v}] {tt.get(str(v), '')}" for v, j in neigh[:5]] + [""]
    (out / "centralite_exemples.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {out / 'centralite_exemples.md'}")


if __name__ == "__main__":
    main()

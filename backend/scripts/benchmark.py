"""Mesure les performances du moteur sur plusieurs requêtes.

Usage depuis la racine :
    python backend/scripts/benchmark.py --repeats 10
    python backend/scripts/benchmark.py --queries whale,love,science --repeats 20

Le script effectue un échauffement, puis exporte les mesures individuelles et les
statistiques (moyenne, écart-type, min, max) dans data/benchmark_results.csv.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.search import Library  # noqa: E402


def measure(lib: Library, queries: list[str], repeats: int, mode: str):
    rows = []
    for query in queries:
        # Échauffement : charge les pages de cache et exclut ce temps des mesures.
        lib.search(query, mode=mode, limit=20)
        timings = []
        for _ in range(repeats):
            started = time.perf_counter()
            result = lib.search(query, mode=mode, limit=20)
            timings.append((time.perf_counter() - started) * 1000)
        rows.append({
            "query": query,
            "mode": mode,
            "repeats": repeats,
            "mean_ms": round(statistics.mean(timings), 3),
            "stdev_ms": round(statistics.stdev(timings), 3) if len(timings) > 1 else 0.0,
            "min_ms": round(min(timings), 3),
            "max_ms": round(max(timings), 3),
            "books_found": result["n_books"],
            "terms_matched": result["n_terms"],
        })
        print(
            f"{query!r:20} moyenne={rows[-1]['mean_ms']:8.3f} ms "
            f"écart-type={rows[-1]['stdev_ms']:8.3f} ms "
            f"min={rows[-1]['min_ms']:8.3f} ms max={rows[-1]['max_ms']:8.3f} ms"
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "index.db"))
    parser.add_argument("--queries", default="the,whale,love,science,history")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--mode", choices=("exact", "substring", "regex"), default="exact")
    parser.add_argument("--out", default=str(ROOT / "data" / "benchmark_results.csv"))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats doit être supérieur ou égal à 1")

    lib = Library(args.db)
    rows = measure(lib, [q.strip() for q in args.queries.split(",") if q.strip()],
                   args.repeats, args.mode)
    if not rows:
        parser.error("aucune requête à mesurer")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nRésultats enregistrés dans : {output}")


if __name__ == "__main__":
    main()

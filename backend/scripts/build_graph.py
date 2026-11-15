"""Construit data/ranking.db (graphe de Jaccard + centralités).

Usage : python backend/scripts/build_graph.py [--data data] [--k 20] [--sans-betweenness]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.jaccard_graph import run  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data")
    p.add_argument("--k", type=int, default=20, help="voisins par livre")
    p.add_argument("--j-min", type=float, default=0.0)
    p.add_argument("--df-min", type=int, default=2)
    p.add_argument("--df-max-ratio", type=float, default=0.5)
    p.add_argument("--sans-betweenness", action="store_true", help="ne calcule pas la betweenness (plus rapide)")
    a = p.parse_args()
    run(a.data, a.k, a.j_min, a.df_min, a.df_max_ratio, not a.sans_betweenness)
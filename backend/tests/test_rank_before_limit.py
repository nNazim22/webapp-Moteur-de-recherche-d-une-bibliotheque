"""Le classement par centralité porte sur TOUS les livres trouvés, pas sur les `limit` premiers par occurrences."""
import csv
import itertools
import random
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.jaccard_graph import run as build_graph
from app.main import app, get_library, get_ranker
from app.ranking import Ranker
from app.search import Library

BUILD_INDEX = Path(__file__).resolve().parents[1] / "scripts" / "build_index.py"


def words(prefix, n):
    gen = ("".join(p) for size in itertools.count(1) for p in itertools.product("abcdefghijklmnopqrstuvwxyz", repeat=size))
    return [prefix + next(gen) for _ in range(n)]


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    data = tmp_path_factory.mktemp("rank")
    (data / "books").mkdir()
    rnd = random.Random(0)
    themes = {0: words("mer", 80), 1: words("loi", 80)}
    common = words("mot", 200)
    with open(data / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "titre", "auteur", "nb_mots", "url"])
        for b in range(12):
            text = " ".join(rnd.sample(common, 120) + rnd.sample(themes[b % 2], 60) + ["whale"] * (b + 1))
            (data / "books" / f"{100 + b}.txt").write_text(
                f"x\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n{text}\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\n",
                encoding="utf-8")
            w.writerow([100 + b, f"Livre {100 + b}", "Auteur", 0, "u"])
    subprocess.run([sys.executable, str(BUILD_INDEX), "--data", str(data)], check=True, stdout=subprocess.DEVNULL)
    build_graph(str(data), k=4, with_betweenness=True, top=1)
    return Library(data / "index.db"), Ranker(data / "ranking.db")


@pytest.mark.parametrize("sort", ["pagerank", "closeness", "betweenness", "mixte"])
def test_top_limit_equals_prefix_of_full_ranking(env, sort):
    lib, ranker = env
    full = [r["id"] for r in lib.search("whale", "exact", 100, sort, ranker)["results"]]
    top3 = lib.search("whale", "exact", 3, sort, ranker)
    assert len(full) == 12 and top3["sort"] == sort
    assert [r["id"] for r in top3["results"]] == full[:3]


def test_centrality_top_differs_from_occurrence_top(env):
    """Preuve que le classement n'est pas un simple reclassement des meilleurs par occurrences."""
    lib, ranker = env
    by_occ = {r["id"] for r in lib.search("whale", "exact", 2)["results"]}
    by_pr = {r["id"] for r in lib.search("whale", "exact", 2, "pagerank", ranker)["results"]}
    assert by_occ == {111, 110} and by_pr != by_occ


def test_fallback_without_ranker(env):
    lib, _ = env
    assert lib.search("whale", sort="pagerank")["sort"] == "occurrences"


def test_api_and_graphe_alias(env):
    lib, ranker = env
    app.dependency_overrides[get_library] = lambda: lib
    app.dependency_overrides[get_ranker] = lambda: ranker
    try:
        c = TestClient(app)
        r = c.get("/api/search", params={"q": "whale", "sort": "closeness", "limit": 3}).json()
        assert r["sort"] == "closeness" and len(r["results"]) == 3 and r["suggestions"]
        assert c.get("/graphe").status_code == 200
    finally:
        app.dependency_overrides.clear()

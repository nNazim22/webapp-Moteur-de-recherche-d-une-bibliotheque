import random

from app.jaccard_graph import run
from app.ranking import Ranker, export_graphe


def _fake_library(tmp_path, n=12):
    books = tmp_path / "books"
    books.mkdir()
    rnd = random.Random(0)
    themes = {0: [f"mer{i}" for i in range(80)], 1: [f"loi{i}" for i in range(80)]}
    common = [f"mot{i}" for i in range(200)]
    for b in range(n):
        theme = themes[b % 2]
        words = rnd.sample(common, 120) + rnd.sample(theme, 60)
        body = " ".join(w + "x" for w in words)  # >=3 lettres, alphabétique
        body = "".join(c if c.isalpha() or c == " " else chr(97 + int(c)) for c in body)
        (books / f"{100 + b}.txt").write_text(
            f"preface\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n{body}\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nlicence",
            encoding="utf-8")
    return tmp_path


def test_pipeline_et_classement(tmp_path):
    data = _fake_library(tmp_path)
    G, cent = run(str(data), k=4, with_betweenness=True, top=3)
    assert G.number_of_nodes() == 12
    assert abs(sum(cent["pagerank"].values()) - 1.0) < 1e-6
    assert (data / "ranking.db").exists()

    r = Ranker(str(data / "ranking.db"))
    assert r.available
    res = [{"id": 100 + i, "occurrences": i} for i in range(12)]
    for crit in ("occurrences", "pagerank", "closeness", "betweenness", "mixte"):
        out = r.rank(res, crit)
        assert len(out) == 12
        scores = [x["score"] for x in out]
        assert scores == sorted(scores, reverse=True)
    assert r.rank(res, "occurrences")[0]["id"] == 111
    assert len(r.voisins(100, 3)) == 3

    g = export_graphe(str(data / "ranking.db"), str(data / "manifest.csv"))
    assert len(g["nodes"]) == 12 and len(g["edges"]) == G.number_of_edges()
    assert all(0 <= n["x"] <= 1 and 0 <= n["y"] <= 1 for n in g["nodes"])
    assert all(0 <= a < 12 and 0 <= b < 12 for a, b, _ in g["edges"])


def test_repli_sans_base(tmp_path):
    r = Ranker(str(tmp_path / "absent.db"))
    assert not r.available
    out = r.rank([{"id": 1, "occurrences": 2}, {"id": 2, "occurrences": 9}], "pagerank")
    assert out[0]["id"] == 2  # repli sur les occurrences


def test_export_sans_base(tmp_path):
    assert export_graphe(str(tmp_path / "absent.db")) is None
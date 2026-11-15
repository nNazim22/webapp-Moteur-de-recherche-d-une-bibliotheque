"""Tests de performance du moteur de recherche (hors réseau : appelle directement le code).

Produit des fichiers CSV et des graphiques (moyenne ± écart type, comme demandé par le sujet) :

  1. latence_recherche   latence par type de requête (mot, sous-chaîne KMP, regex DFA, classements)
  2. automates           taille NFA / DFA / DFA minimal et temps de compilation selon la regex
  3. moteur_vs_re        notre moteur (KMP, DFA) contre `re` et `in` de Python, sur tout le vocabulaire
  4. passage_a_echelle   (option --scaling) temps d'indexation, du graphe de Jaccard et de recherche
                         selon le nombre de livres (10 %, 25 %, 50 %, 100 % du corpus)

Usage (depuis la racine du projet) :
    pip install -r backend/requirements-bench.txt
    python backend/scripts/benchmark.py --data data --out benchmarks
    python backend/scripts/benchmark.py --data data --out benchmarks --scaling
    python backend/scripts/benchmark.py --data data-synth --repeat 10     # corpus synthétique
Sans matplotlib, seuls les CSV sont écrits.
"""
import argparse
import csv
import os
import random
import re
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.ranking import Ranker                       # noqa: E402
from app.search import Library                       # noqa: E402
from engine import KMPMatcher, build_dfa, build_nfa, compile_regex, minimize, parse   # noqa: E402

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:                                   # graphiques optionnels
    plt = None


def measure(lib, queries, repeats, mode):
    """Mesure simple (moyenne, écart type, min, max en ms) de plusieurs requêtes ; utilisée par les tests."""
    rows = []
    for query in queries:
        lib.search(query, mode=mode, limit=20)                      # échauffement
        timings = timed(lambda q=query: lib.search(q, mode=mode, limit=20), repeats)
        res = lib.search(query, mode=mode, limit=20)
        m, s = mean_std(timings)
        rows.append({"query": query, "mode": mode, "repeats": repeats, "mean_ms": round(m, 3),
                     "stdev_ms": round(s, 3), "min_ms": round(min(timings), 3), "max_ms": round(max(timings), 3),
                     "books_found": res["n_books"], "terms_matched": res["n_terms"]})
    return rows


def mean_std(values):
    return statistics.fmean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  -> {path}")


def bar_chart(path, labels, means, stds, ylabel, title, log=False):
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(labels)), 4.2))
    ax.bar(range(len(labels)), means, yerr=stds, capsize=4, color="#4f46e5")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if log:
        ax.set_yscale("log")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  -> {path}")


def timed(fn, repeat):
    out = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def vocabulary(db):
    with closing(sqlite3.connect(db)) as con:
        return con.execute("SELECT term, doc_freq FROM vocab ORDER BY doc_freq DESC").fetchall()


def sample_words(vocab, rnd, n):
    """Mots de fréquences variées : fréquents (haut du classement), moyens, rares."""
    size = len(vocab)
    bands = {"frequent": vocab[: max(1, size // 100)], "moyen": vocab[size // 10: size // 4],
             "rare": vocab[size // 2:]}
    return {name: [t for t, _ in rnd.sample(b, min(n, len(b)))] for name, b in bands.items()}


# --------------------------------------------------------------------------- 1. latence


def bench_search(lib, ranker, vocab, repeat, out):
    print("1/3 Latence de recherche")
    rnd = random.Random(0)
    words = sample_words(vocab, rnd, 5)
    cases = []                                         # (libellé, mode, requête, critère)
    for band, ws in words.items():
        cases += [(f"mot {band}", "exact", w, "occurrences") for w in ws[:3]]
    cases += [(f"contient {len(s)} lettres", "substring", s, "occurrences")
              for s in ("ab", "tion", "ation", "nation")]
    regexes = {"regex a.c": "a.c", "regex (a|e)+n": "(a|e)+n", "regex [aeiou]+t": "[aeiou]+t",
               "regex .*ing|.*ed": ".*ing|.*ed", "regex (ab|ba)*c": "(ab|ba)*c"}
    cases += [(label, "regex", rx, "occurrences") for label, rx in regexes.items()]
    frequent = words["frequent"][0]
    if ranker.available:
        cases += [(f"classement {c}", "exact", frequent, c)
                  for c in ("occurrences", "pagerank", "closeness", "betweenness", "mixte")]

    groups = {}
    for label, mode, query, crit in cases:
        def run():
            lib._cache.clear()                         # on mesure la requête à froid, pas le cache
            lib.search(query, mode, 20, crit, ranker)
        groups.setdefault(label, []).extend(timed(run, repeat))
    rows = [(label, *mean_std(v), len(v)) for label, v in groups.items()]
    write_csv(out / "latence_recherche.csv", ["requete", "moyenne_ms", "ecart_type_ms", "mesures"],
              [(r[0], round(r[1], 3), round(r[2], 3), r[3]) for r in rows])
    bar_chart(out / "latence_recherche.png", [r[0] for r in rows], [r[1] for r in rows],
              [r[2] for r in rows], "ms (moyenne ± écart type)",
              f"Latence de recherche, requête à froid ({lib.n_books} livres, {len(vocab)} mots)", log=True)


# --------------------------------------------------------------------------- 2. automates


def bench_automata(out, repeat):
    print("2/3 Taille des automates")
    family = {"a": "a", "a*b": "a*b", "(a|b)*abb": "(a|b)*abb", "[a-z]+ing": "[a-z]+ing",
              "(a|b|c)*c(a|b|c)": "(a|b|c)*c(a|b|c)",
              "(a|b)*a(a|b)(a|b)(a|b)": "(a|b)*a(a|b)(a|b)(a|b)",
              "(a|b)*a(a|b){6}": "(a|b)*a" + "(a|b)" * 6, "(a|b)*a(a|b){9}": "(a|b)*a" + "(a|b)" * 9}
    rows = []
    for label, rx in family.items():
        def compile_all():
            minimize(build_dfa(build_nfa(parse(rx)), search=True))
        times = timed(compile_all, max(3, repeat // 3))
        nfa = build_nfa(parse(rx))
        dfa = build_dfa(nfa, search=True)
        mini = minimize(dfa)
        m, s = mean_std(times)
        rows.append((label, len(rx), nfa.n, len(dfa.states), len(mini.states), round(m, 3), round(s, 3)))
    write_csv(out / "automates.csv",
              ["regex", "longueur", "etats_NFA", "etats_DFA", "etats_DFA_min", "compilation_ms", "ecart_type_ms"], rows)
    if plt is not None:
        fig, ax = plt.subplots(figsize=(8, 4.2))
        x = range(len(rows))
        for col, name, color in ((2, "NFA", "#94a3b8"), (3, "DFA", "#4f46e5"), (4, "DFA minimal", "#16a34a")):
            ax.plot(x, [r[col] for r in rows], marker="o", label=name, color=color)
        ax.set_xticks(list(x))
        ax.set_xticklabels([r[0] for r in rows], rotation=30, ha="right", fontsize=8)
        ax.set_yscale("log")
        ax.set_ylabel("nombre d'états")
        ax.set_title("Taille des automates : le motif (a|b)*a(a|b)^k fait exploser le DFA (2^k états)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "automates.png", dpi=150)
        plt.close(fig)
        print(f"  -> {out / 'automates.png'}")


# --------------------------------------------------------------------------- 3. moteur vs re


def bench_vs_re(vocab, repeat, out):
    print("3/3 Notre moteur contre re / in (balayage de tout le vocabulaire)")
    terms = [t for t, _ in vocab]
    cases = [("sous-chaîne « ation »", "ation", True), ("regex (a|e)+n", "(a|e)+n", False),
             ("regex [aeiou]+t", "[aeiou]+t", False), ("regex .*ing", ".*ing", False)]
    rows = []
    for label, pattern, literal in cases:
        contenders = {}
        if literal:
            kmp = KMPMatcher(pattern)
            contenders["KMP (notre code)"] = lambda: sum(1 for t in terms if kmp.search(t))
            contenders["in (Python)"] = lambda: sum(1 for t in terms if pattern in t)
        dfa = compile_regex(pattern, force_automaton=True)
        rx = re.compile(pattern)
        contenders["DFA minimal (notre code)"] = lambda: sum(1 for t in terms if dfa.search(t))
        contenders["re.search (Python)"] = lambda: sum(1 for t in terms if rx.search(t))
        counts = {name: fn() for name, fn in contenders.items()}
        assert len(set(counts.values())) == 1, f"résultats différents pour {label}: {counts}"
        for name, fn in contenders.items():
            m, s = mean_std(timed(fn, max(3, repeat // 3)))
            rows.append((label, name, round(m, 2), round(s, 2), counts[name]))
    write_csv(out / "moteur_vs_re.csv", ["requete", "moteur", "moyenne_ms", "ecart_type_ms", "mots_trouves"], rows)
    bar_chart(out / "moteur_vs_re.png", [f"{r[0]}\n{r[1]}" for r in rows], [r[2] for r in rows],
              [r[3] for r in rows], "ms (moyenne ± écart type)",
              f"Balayage de {len(terms)} mots : notre moteur contre Python", log=True)


# --------------------------------------------------------------------------- 4. passage à l'échelle


def bench_scaling(data, out, repeat, fractions=(0.1, 0.25, 0.5, 1.0)):
    print("Passage à l'échelle (indexation, graphe de Jaccard, recherche)")
    from app import jaccard_graph as jg

    manifest = list(csv.DictReader(open(data / "manifest.csv", newline="", encoding="utf-8")))
    rnd = random.Random(1)
    rnd.shuffle(manifest)
    rows = []
    for frac in fractions:
        subset = manifest[: max(3, int(len(manifest) * frac))]
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp)
            os.symlink((data / "books").resolve(), sub / "books", target_is_directory=True)
            with open(sub / "manifest.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(subset[0].keys()))
                w.writeheader()
                w.writerows(subset)
            t0 = time.perf_counter()
            subprocess.run([sys.executable, str(HERE / "build_index.py"), "--data", str(sub)],
                           check=True, stdout=subprocess.DEVNULL)
            t_index = time.perf_counter() - t0
            size_mb = (sub / "index.db").stat().st_size / 1e6

            t0 = time.perf_counter()
            ids, sets = _load_subset(jg, sub, subset)
            cols, n_cols = jg.filter_vocabulary(sets)
            J = jg.jaccard_matrix(cols, n_cols)
            t_jaccard = time.perf_counter() - t0
            G = jg.build_graph(ids, J, k=20)
            t0 = time.perf_counter()
            jg.centralities(G, with_betweenness=False)
            t_cent = time.perf_counter() - t0
            t0 = time.perf_counter()
            jg.centralities(G, with_betweenness=True)
            t_cent_b = time.perf_counter() - t0

            lib = Library(sub / "index.db")
            vocab = vocabulary(sub / "index.db")
            words = sample_words(vocab, random.Random(2), 5)["moyen"]
            lat = []
            for w_ in words:
                def run(w_=w_):
                    lib._cache.clear()
                    lib.search(w_, "exact", 20)
                lat += timed(run, repeat)
            rx_lat = timed(lambda: (lib._cache.clear(), lib.search("(a|e)+n", "regex", 20)), max(3, repeat // 3))
            m, s = mean_std(lat)
            mr, sr = mean_std(rx_lat)
            rows.append((len(subset), len(vocab), round(t_index, 2), round(size_mb, 1), round(t_jaccard, 2),
                         round(t_cent, 2), round(t_cent_b, 2), round(m, 3), round(s, 3), round(mr, 2), round(sr, 2)))
            print(f"  {len(subset):5d} livres : index {t_index:.1f} s, Jaccard {t_jaccard:.1f} s, "
                  f"centralités {t_cent:.1f} s (+betweenness {t_cent_b:.1f} s), mot {m:.2f} ms, regex {mr:.0f} ms")
    write_csv(out / "passage_a_echelle.csv",
              ["livres", "mots_distincts", "indexation_s", "index_Mo", "jaccard_s", "centralites_s",
               "centralites_avec_betweenness_s", "recherche_mot_ms", "ecart_type_ms", "recherche_regex_ms",
               "ecart_type_regex_ms"], rows)
    if plt is not None:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        n = [r[0] for r in rows]
        axes[0].plot(n, [r[2] for r in rows], "o-", label="indexation")
        axes[0].plot(n, [r[4] for r in rows], "s-", label="graphe de Jaccard")
        axes[0].plot(n, [r[6] for r in rows], "^-", label="centralités (+ betweenness)")
        axes[0].set_xlabel("nombre de livres")
        axes[0].set_ylabel("secondes")
        axes[0].set_title("Construction hors ligne")
        axes[0].legend()
        axes[1].errorbar(n, [r[7] for r in rows], yerr=[r[8] for r in rows], fmt="o-", capsize=4, label="mot exact")
        axes[1].errorbar(n, [r[9] for r in rows], yerr=[r[10] for r in rows], fmt="s-", capsize=4, label="regex (a|e)+n")
        axes[1].set_xlabel("nombre de livres")
        axes[1].set_ylabel("ms (moyenne ± écart type)")
        axes[1].set_yscale("log")
        axes[1].set_title("Latence de recherche")
        axes[1].legend()
        fig.tight_layout()
        fig.savefig(out / "passage_a_echelle.png", dpi=150)
        plt.close(fig)
        print(f"  -> {out / 'passage_a_echelle.png'}")


def _load_subset(jg, sub, subset):
    """Comme jaccard_graph.load_books mais restreint aux livres du manifest (sous-corpus)."""
    ids, sets = [], []
    for row in subset:
        ids.append(int(row["id"]))
        sets.append(jg.book_hashes(sub / "books" / f"{row['id']}.txt"))
    return ids, sets


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="benchmarks")
    ap.add_argument("--repeat", type=int, default=30, help="mesures par requête")
    ap.add_argument("--scaling", action="store_true", help="ajoute le passage à l'échelle (long : réindexe 4 fois)")
    a = ap.parse_args()

    data, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lib = Library(data / "index.db")
    ranker = Ranker(data / "ranking.db")
    vocab = vocabulary(data / "index.db")
    print(f"Bibliothèque : {lib.n_books} livres, {len(vocab)} mots distincts, "
          f"classements par centralité : {'oui' if ranker.available else 'non (build_graph.py non lancé)'}")
    bench_search(lib, ranker, vocab, a.repeat, out)
    bench_automata(out, a.repeat)
    bench_vs_re(vocab, a.repeat, out)
    if a.scaling:
        bench_scaling(data, out, a.repeat)
    if plt is None:
        print("(matplotlib absent : CSV seulement. pip install -r backend/requirements-bench.txt)")


if __name__ == "__main__":
    main()

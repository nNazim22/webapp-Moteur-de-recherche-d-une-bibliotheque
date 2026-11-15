"""Test de charge HTTP : plusieurs clients simultanés contre le serveur en marche.

Chaque client (un thread, une session HTTP) enchaîne des requêtes variées (mot, sous-chaîne,
regex, avec différents critères de classement) pendant `--duration` secondes. On répète
l'expérience pour plusieurs niveaux de concurrence et on mesure le débit (requêtes/s) et les
latences médiane / p95 / p99.

Usage (serveur déjà lancé, depuis la racine du projet) :
    python backend/scripts/load_test.py --url http://localhost:8000 --out benchmarks
    python backend/scripts/load_test.py --url http://192.168.1.20:8000 --clients 1 5 20 50 --duration 15
    python backend/scripts/load_test.py --words-from-data data      # mots tirés du vrai index

Le test peut être lancé depuis une AUTRE machine que le serveur (cas de la démonstration).
"""
import argparse
import csv
import random
import sqlite3
import statistics
import threading
import time
from pathlib import Path

import requests

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

DEFAULT_WORDS = ["love", "whale", "king", "ocean", "night", "war", "queen", "ship", "garden", "river",
                 "doctor", "winter", "letter", "justice", "mountain", "silence"]
CRITERIA = ["occurrences", "occurrences", "occurrences", "pagerank", "closeness", "mixte"]


def words_from_index(data, n=300):
    """Mots tirés au hasard dans le vrai vocabulaire (fréquences variées)."""
    con = sqlite3.connect(Path(data) / "index.db")
    terms = [t for (t,) in con.execute("SELECT term FROM vocab WHERE doc_freq >= 3 AND length(term) >= 4")]
    con.close()
    return random.Random(0).sample(terms, min(n, len(terms)))


def make_request(rnd, words):
    """Une requête au hasard : 70 % mot exact, 15 % sous-chaîne, 15 % regex."""
    r = rnd.random()
    crit = rnd.choice(CRITERIA)
    w = rnd.choice(words)
    if r < 0.70:
        return "/api/search", {"q": w, "sort": crit, "limit": 20}
    if r < 0.85:
        return "/api/search", {"q": w[:3], "mode": "substring", "sort": crit, "limit": 20}
    return "/api/advanced", {"regex": f"{w[:2]}({w[2]}|e)+", "sort": crit, "limit": 20}


def client_loop(url, words, stop_at, seed, latencies, errors):
    rnd = random.Random(seed)
    s = requests.Session()
    mine, bad = [], 0
    while time.perf_counter() < stop_at:
        path, params = make_request(rnd, words)
        t0 = time.perf_counter()
        try:
            r = s.get(url + path, params=params, timeout=30)
            ok = r.status_code == 200
        except requests.RequestException:
            ok = False
        dt = (time.perf_counter() - t0) * 1000
        if ok:
            mine.append(dt)
        else:
            bad += 1
    latencies.extend(mine)
    errors.append(bad)


def run_level(url, words, n_clients, duration):
    latencies, errors, threads = [], [], []
    stop_at = time.perf_counter() + duration
    t0 = time.perf_counter()
    for i in range(n_clients):
        t = threading.Thread(target=client_loop, args=(url, words, stop_at, 1000 + i, latencies, errors))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0
    lat = sorted(latencies)
    if not lat:
        return None
    q = lambda p: lat[min(len(lat) - 1, int(p * len(lat)))]
    return {"clients": n_clients, "requetes": len(lat), "erreurs": sum(errors),
            "debit_req_s": round(len(lat) / elapsed, 1), "mediane_ms": round(statistics.median(lat), 1),
            "moyenne_ms": round(statistics.fmean(lat), 1),
            "ecart_type_ms": round(statistics.stdev(lat), 1) if len(lat) > 1 else 0.0,
            "p95_ms": round(q(0.95), 1), "p99_ms": round(q(0.99), 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--clients", type=int, nargs="+", default=[1, 2, 5, 10, 20, 50])
    ap.add_argument("--duration", type=float, default=10, help="secondes par niveau de concurrence")
    ap.add_argument("--out", default="benchmarks")
    ap.add_argument("--words-from-data", metavar="DATA", help="dossier data/ dont on tire les mots de test")
    a = ap.parse_args()

    url = a.url.rstrip("/")
    try:
        requests.get(url + "/api/health", timeout=5).raise_for_status()
    except requests.RequestException as e:
        raise SystemExit(f"Serveur injoignable ({url}) : {e}")
    words = words_from_index(a.words_from_data) if a.words_from_data else DEFAULT_WORDS
    print(f"Serveur : {url} | {len(words)} mots de test | {a.duration:g} s par niveau")
    requests.get(url + "/api/search", params={"q": words[0]}, timeout=60)   # échauffement (chargement de l'index)

    rows = []
    for n in a.clients:
        res = run_level(url, words, n, a.duration)
        if res is None:
            print(f"  {n:3d} clients : aucune requête réussie")
            continue
        rows.append(res)
        print(f"  {n:3d} clients : {res['debit_req_s']:7.1f} req/s | médiane {res['mediane_ms']:7.1f} ms | "
              f"p95 {res['p95_ms']:7.1f} ms | p99 {res['p99_ms']:7.1f} ms | erreurs {res['erreurs']}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "charge.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {out / 'charge.csv'}")
    if plt is not None and rows:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        n = [r["clients"] for r in rows]
        axes[0].plot(n, [r["debit_req_s"] for r in rows], "o-", color="#4f46e5")
        axes[0].set_xlabel("clients simultanés")
        axes[0].set_ylabel("requêtes / seconde")
        axes[0].set_title("Débit")
        axes[1].errorbar(n, [r["moyenne_ms"] for r in rows], yerr=[r["ecart_type_ms"] for r in rows],
                         fmt="o-", capsize=4, label="moyenne ± écart type")
        axes[1].plot(n, [r["p95_ms"] for r in rows], "s--", label="p95")
        axes[1].plot(n, [r["p99_ms"] for r in rows], "^:", label="p99")
        axes[1].set_xlabel("clients simultanés")
        axes[1].set_ylabel("latence (ms)")
        axes[1].set_title("Latence")
        axes[1].legend()
        fig.tight_layout()
        fig.savefig(out / "charge.png", dpi=150)
        plt.close(fig)
        print(f"  -> {out / 'charge.png'}")


if __name__ == "__main__":
    main()

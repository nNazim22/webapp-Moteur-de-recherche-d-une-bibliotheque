"""Crée l'archive à rendre : tout le projet SAUF les données et les fichiers temporaires.

Usage (depuis la racine du projet) :
    python backend/scripts/make_archive.py                       # daar-projet2-HOUMEL-BENDOUHA.zip
    python backend/scripts/make_archive.py --names DUPONT-MARTIN

Exclus : data/ (recréé par telecharger_donnees), .venv, .git, caches Python, clés (*.pem, deploy_key*),
         archives déjà présentes. Inclus : code, frontend, tests, Dockerfile, pipeline .github, README,
         corpus/manifest.csv, benchmarks/, rapport/ (PDF) et la vidéo pitch si vous en avez une.
Le sujet limite l'archive à environ 30 Mo : le script vérifie la taille.
"""
import argparse
import shutil
import sys
import zipfile
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT_MB = 30
EXCLUDED_DIRS = {"data", ".venv", "venv", ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
                 "node_modules", ".idea", ".vscode"}
EXCLUDED_FILES = ["*.pyc", "*.pem", "deploy_key*", "id_rsa*", "id_ed25519*", ".env", "*.zip", "*.rar",
                  "*.7z", "*.tgz", "*.tar.gz", "Thumbs.db", ".DS_Store"]


def project_files():
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in rel.parts[:-1]):
            continue
        if any(fnmatch(path.name, pattern) for pattern in EXCLUDED_FILES):
            continue
        yield path, rel


def sync_corpus_manifest():
    """Copie data/manifest.csv -> corpus/manifest.csv (liste exacte des livres) si le corpus complet est présent."""
    src, dst = ROOT / "data" / "manifest.csv", ROOT / "corpus" / "manifest.csv"
    if not src.exists():
        return
    n = max(0, sum(1 for _ in open(src, encoding="utf-8")) - 1)
    if n >= 1664:
        dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"corpus/manifest.csv mis à jour ({n} livres).")
    else:
        print(f"data/manifest.csv ne contient que {n} livres (< 1664) : corpus/manifest.csv non modifié.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="HOUMEL-BENDOUHA", help="NOM1-NOM2 pour le nom de l'archive")
    ap.add_argument("--out", default=None, help="chemin de l'archive (défaut : à la racine du projet)")
    args = ap.parse_args()

    sync_corpus_manifest()
    base = f"daar-projet2-{args.names}"
    out = Path(args.out) if args.out else ROOT / f"{base}.zip"
    files = list(project_files())

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path, rel in files:
            z.write(path, f"{base}/{rel.as_posix()}")     # tout dans un dossier au nom du projet

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"Archive : {out}  ({len(files)} fichiers, {size_mb:.2f} Mo)")
    biggest = sorted(files, key=lambda f: f[0].stat().st_size, reverse=True)[:5]
    print("Plus gros fichiers :")
    for path, rel in biggest:
        print(f"  {path.stat().st_size / 1024 / 1024:7.2f} Mo  {rel.as_posix()}")

    names = {rel.as_posix() for _, rel in files}
    if "README.md" not in names:
        print("ATTENTION : pas de README.md à la racine.")
    if "corpus/manifest.csv" not in names:
        print("ATTENTION : corpus/manifest.csv absent : lancez make_archive depuis la machine qui a data/ complet.")
    if not any(n.startswith("rapport/") and n.lower().endswith(".pdf") for n in names):
        print("ATTENTION : aucun PDF dans rapport/ (le rapport compte pour 40 % de la note).")
    if not any(n.startswith("benchmarks/") and n.endswith(".png") for n in names):
        print("ATTENTION : benchmarks/ vide (benchmark.py, load_test.py, centrality_report.py --out benchmarks).")
    if not any(n.lower().endswith((".mp4", ".mkv", ".webm", ".mov")) for n in names):
        print("Rappel : pas de vidéo pitch dans l'archive (ignorez si présentation orale).")
    for needed in ("telecharger_donnees.bat", "telecharger_donnees.sh"):
        if needed not in names:
            print(f"ATTENTION : {needed} absent de l'archive.")
    if size_mb > LIMIT_MB:
        sys.exit(f"ERREUR : {size_mb:.1f} Mo, la limite du sujet est d'environ {LIMIT_MB} Mo.")
    print("Taille OK." if size_mb <= LIMIT_MB * 0.93 else "Taille proche de la limite : vérifiez avant l'envoi.")


if __name__ == "__main__":
    main()

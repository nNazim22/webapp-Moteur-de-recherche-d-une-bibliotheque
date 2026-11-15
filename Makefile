# Raccourcis (Linux / macOS / Git Bash / WSL). Sous Windows sans make : voir README.md.
PY ?= python
DATA ?= data

.PHONY: help install data index graph validate run test bench scaling load report archive corpus clean

help:
	@echo "make install   dépendances Python"
	@echo "make data      télécharge les livres (Gutenberg) + construit l'index"
	@echo "make index     (re)construit l'index inversé"
	@echo "make graph     graphe de Jaccard + centralités (classement, suggestions)"
	@echo "make validate  vérifie >= 1664 livres de >= 10000 mots"
	@echo "make run       serveur accessible depuis le réseau (port 8000)"
	@echo "make test      tests unitaires et API"
	@echo "make bench     tests de performance -> benchmarks/ (scaling : make scaling)"
	@echo "make load      test de charge (serveur déjà lancé)"
	@echo "make report    top des centralités, corrélations, fiches de livres -> benchmarks/"
	@echo "make corpus    copie data/manifest.csv dans corpus/ (provenance, dans l'archive)"
	@echo "make archive   archive à rendre (zip) ; NAMES=NOM1-NOM2-NOM3"

install:
	$(PY) -m pip install -r backend/requirements.txt -r backend/requirements-bench.txt

data:
	$(PY) backend/scripts/setup_data.py

index:
	$(PY) backend/scripts/build_index.py --data $(DATA)

graph:
	$(PY) backend/scripts/build_graph.py --data $(DATA)

validate:
	$(PY) backend/scripts/validate_corpus.py --data $(DATA)

run:
	@$(PY) backend/scripts/show_lan_url.py
	$(PY) -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000

test:
	$(PY) -m pytest

bench:
	$(PY) backend/scripts/benchmark.py --data $(DATA) --out benchmarks

scaling:
	$(PY) backend/scripts/benchmark.py --data $(DATA) --out benchmarks --scaling

load:
	$(PY) backend/scripts/load_test.py --url http://localhost:8000 --out benchmarks --words-from-data $(DATA)

report:
	$(PY) backend/scripts/centrality_report.py --data $(DATA) --out benchmarks

corpus:
	mkdir -p corpus && cp $(DATA)/manifest.csv corpus/manifest.csv

NAMES ?= HOUMEL-BENDOUHA
archive:
	$(PY) backend/scripts/make_archive.py --names $(NAMES)

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + ; rm -rf .pytest_cache

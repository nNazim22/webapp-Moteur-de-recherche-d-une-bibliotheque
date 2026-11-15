# DAAR — Projet 2 : moteur de recherche d’une bibliothèque

Application web/mobile permettant de rechercher et de lire des livres textuels issus de Project Gutenberg.

## Fonctionnalités

- Recherche par mot exact et recherche par sous-chaîne (algorithme KMP).
- Recherche avancée par expression régulière, compilée en automate NFA/DFA.
- Index inversé SQLite : vocabulaire, postings et nombre d’occurrences par livre.
- Classement par occurrences, PageRank, closeness, betweenness et score mixte.
- Graphe de similarité de Jaccard et suggestions de livres voisins.
- Visualisation interactive du graphe dans `graphe.html`.
- Lecteur paginé avec repérage et surlignage des mots recherchés.
- API FastAPI documentée automatiquement (`/docs`).
- Interface responsive accessible depuis un navigateur de bureau ou mobile.
- Tests automatisés et pipeline GitHub Actions.

## Architecture

```text
backend/
  app/          API, recherche, lecture, classement et graphe
  engine/       KMP, parseur RegEx, NFA, DFA et minimisation
  scripts/      téléchargement, indexation et construction du graphe
  tests/        tests unitaires et tests API
frontend/
  index.html    interface de recherche et lecteur
  graphe.html   visualisation du graphe de Jaccard
data/
  books/        fichiers textuels des livres
  manifest.csv  provenance et métadonnées du corpus
  index.db      index inversé SQLite
  ranking.db    graphe de Jaccard et centralités
```

## Corpus de livres

L’énoncé demande au minimum **1 664 livres**, chacun contenant au moins **10 000 mots**. Trois livres d’exemple sont fournis dans `sample_data/` pour les tests et pour permettre un premier démarrage de secours. Le script les copie automatiquement dans `data/`, puis complète le corpus depuis Project Gutenberg. Le corpus complet et les bases calculées ne sont pas inclus dans l’archive afin de respecter la limite de taille du rendu.

Les textes sont téléchargés depuis Project Gutenberg. Le script conserve le titre, l’auteur, l’identifiant, le nombre de mots et l’URL source dans `data/manifest.csv`. Les téléchargements sont reprenables : les livres déjà téléchargés ne sont pas téléchargés une seconde fois.

## Installation et lancement sous Linux / Ubuntu

Depuis la racine du projet :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

Télécharger le corpus et construire l’index :

```bash
python backend/scripts/setup_data.py --target 1700
```

Construire le graphe de Jaccard et les centralités :

```bash
python backend/scripts/build_graph.py --data data
```

Lancer le serveur :

```bash
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Ouvrir ensuite :

- Application : `http://localhost:8000`
- Documentation API : `http://localhost:8000/docs`
- Graphe : `http://localhost:8000/graphe.html`

Le téléchargement du corpus et la construction des index peuvent prendre du temps au premier lancement. Les lancements suivants réutilisent les fichiers de `data/`.

## Lancement avec Docker

Prérequis : Docker Engine et Docker Compose.

```bash
docker compose up --build
```

Le conteneur prépare automatiquement les livres manquants, l’index et le graphe avant de démarrer FastAPI. Les données restent persistantes dans le dossier local `data/`.

Par défaut, l’application est publiée sur le port `80` (`http://localhost`). Pour choisir un autre port :

```bash
DAAR_PORT=8080 docker compose up --build
```

Avec cette configuration, ouvrir `http://localhost:8080`.

Suivre les logs :

```bash
docker compose logs -f app
```

Arrêter l’application sans supprimer les données :

```bash
docker compose down
```

## Démonstration sur plusieurs machines

Démarrer le serveur sur une machine accessible depuis les clients. Relever son adresse IP, puis ouvrir depuis les autres ordinateurs ou smartphones :

```text
http://ADRESSE_IP_DU_SERVEUR:8000
```

Les clients doivent pouvoir joindre le serveur sur le port choisi. Sur un réseau local, ils doivent être connectés au même réseau ; à distance, prévoir un accès réseau sécurisé (VPN ou reverse proxy HTTPS).

## API principale

| Méthode | Route | Description |
|---|---|---|
| GET | `/api/stats` | Nombre de livres, vocabulaire et classements disponibles |
| GET | `/api/search?q=whale` | Recherche simple |
| GET | `/api/search?q=wha&mode=substring` | Recherche par sous-chaîne |
| GET | `/api/advanced?regex=wh(a%7Ce)+l` | Recherche RegEx |
| GET | `/api/books/{id}` | Métadonnées d’un livre |
| GET | `/api/books/{id}/pages/{page}` | Lecture d’une page |
| GET | `/api/books/{id}/hits?terms=whale,ocean` | Pages contenant les mots |
| GET | `/api/graph` | Sommets, arêtes et centralités du graphe |
| GET | `/api/health` | Supervision (réponse immédiate) |
| GET | `/graphe` | Page de visualisation du graphe (alias de `/graphe.html`) |

Le paramètre `sort` accepte `occurrences`, `mixte`, `pagerank`, `closeness` ou `betweenness`. Les classements de centralité sont proposés lorsque `data/ranking.db` a été générée.

## Tests

Depuis la racine :

```bash
pytest -q
```

Les 76 tests (KMP, regex comparée à `re` sur 300 expressions aléatoires, index, API, graphe, classement avant troncature) utilisent un mini-corpus temporaire et ne nécessitent pas le téléchargement des 1 700 livres.

## Mesures de performance

```bash
pip install -r backend/requirements-bench.txt                 # matplotlib (graphiques)
python backend/scripts/benchmark.py --data data --out benchmarks              # latence par type de requête, taille des automates, notre moteur vs re
python backend/scripts/benchmark.py --data data --out benchmarks --scaling    # + indexation / graphe / recherche selon le nombre de livres (long)
python backend/scripts/load_test.py --url http://localhost:8000 --out benchmarks --words-from-data data   # charge : N clients simultanés
python backend/scripts/centrality_report.py --data data --out benchmarks      # top des centralités, corrélations, fiches de livres
```

Chaque script écrit un CSV et un PNG (moyenne ± écart type) dans `benchmarks/`. Le test de charge peut être lancé depuis une
autre machine que le serveur (`--url http://IP:8000`). Les mesures doivent être réalisées sur le corpus réel (pas le corpus synthétique).

## Vérification du corpus

```bash
python backend/scripts/validate_corpus.py --data data   # ≥ 1664 livres, ≥ 10 000 mots chacun, fichiers présents
```

`corpus/manifest.csv` doit contenir la liste exacte des livres (provenance) : il est recopié depuis `data/manifest.csv` par
`make_archive.py` quand le corpus complet est présent. Pour développer hors connexion : `backend/scripts/gen_synthetic_corpus.py`
crée de FAUX livres (à ne jamais utiliser pour les résultats du rapport).

## Syntaxe des expressions régulières

`.` `*` `+` `?` `|` `( )`, échappement `\`, classes `[abc]` `[a-z]`. Non gérés : ancres `^` `$`, classes négatives `[^…]`, `{n,m}`.
Trace pas à pas (arbre, NFA, DFA, DFA minimal) : `cd backend && python -m engine.main --explain "a[bc]*d"`.

## Rendu

```bash
python backend/scripts/make_archive.py --names NOM1-NOM2-NOM3
```

Crée l'archive (sans `data/`) avec le code, `corpus/manifest.csv`, `benchmarks/`, `rapport/` (y mettre le PDF) et la vidéo pitch
si présente ; vérifie la limite de 30 Mo et signale ce qui manque. Dépôt Moodle avant le 22 novembre 2026, 23 h 59.

## Reconstruction des données

Pour reconstruire l’index après ajout ou remplacement de livres :

```bash
python backend/scripts/build_index.py --data data
```

Pour reconstruire le graphe :

```bash
python backend/scripts/build_graph.py --data data
```

Le graphe utilise les ensembles de mots des livres, calcule les similarités de Jaccard, construit un graphe k-plus-proches-voisins et calcule PageRank et closeness (betweenness est également calculé par défaut).

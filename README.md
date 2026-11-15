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

Le paramètre `sort` accepte `occurrences`, `mixte`, `pagerank`, `closeness` ou `betweenness`. Les classements de centralité sont proposés lorsque `data/ranking.db` a été générée.

## Tests

Depuis la racine :

```bash
pytest -q
```

Les tests utilisent un mini-corpus temporaire et ne nécessitent pas le téléchargement des 1 700 livres.

## Mesures de performance

Un script permet de mesurer le temps de réponse du moteur sur plusieurs requêtes et de produire un CSV contenant la moyenne, l'écart-type, le minimum, le maximum et le nombre de livres trouvés :

```bash
python backend/scripts/benchmark.py --repeats 10
python backend/scripts/benchmark.py --queries whale,love,science --repeats 20
```

Le fichier est généré dans `data/benchmark_results.csv` par défaut. Les mesures doivent être réalisées sur la machine et le corpus utilisés pour la démonstration.

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

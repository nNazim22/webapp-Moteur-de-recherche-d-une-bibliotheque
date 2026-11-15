# Corpus : liste exacte des livres

Ce dossier doit contenir `manifest.csv` : la liste des livres (id Gutenberg, titre, auteur,
nombre de mots, URL) du corpus utilisé pour le rapport et les mesures.

- Pour le **créer** à partir d'un corpus déjà téléchargé : `make corpus` (copie `data/manifest.csv` ici).
- Pour **recréer le même corpus** sur une autre machine : `python backend/scripts/setup_data.py`
  télécharge d'abord les livres listés ici (voir `backend/scripts/download_books.py --source manifest`).

Sans ce fichier, le script télécharge d'autres livres populaires de Project Gutenberg : le corpus
est valide mais n'est pas identique à celui du rapport.

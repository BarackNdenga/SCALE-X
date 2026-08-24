# SCALE-X — V0.2 AI Evaluation Engine

SCALE-X est un prototype d’infrastructure de métrologie et de fiabilité de l’intelligence artificielle. La V0.1 analyse la santé des datasets avec le Data Fitness Engine. La V0.2 ajoute un **Model Fitness Engine** qui interroge réellement un modèle configuré et mesure ses sorties sur un jeu de tests annoté.

## V0.1 — Data Fitness Engine

Le moteur accepte les formats CSV, JSON, JSONL et TXT. Il calcule notamment les valeurs manquantes, les doublons, les distributions catégorielles, les déséquilibres, les valeurs extrêmes, la cohérence des types, la diversité, les statistiques linguistiques et les motifs suspects. Le rapport renvoie un **Data Fitness Score (DFS)** explicable.

## V0.2 — AI Evaluation Engine

Le moteur V0.2 reçoit un dataset de tests, appelle l’endpoint de modèle configuré par l’opérateur et calcule un **Model Fitness Score (MFS)** à partir des réponses réellement reçues. Il ne génère aucune réponse de secours et aucun score prédéfini. Si aucun modèle n’est configuré, l’API renvoie explicitement une erreur `503`.

Les critères disponibles sont la précision/factualité contre une référence, la robustesse avec une reformulation, la cohérence par appels répétés, le proxy d’hallucination contre une référence, le refus approprié, le multilinguisme par langue et l’écart de performance entre groupes fournis.

> Les scores MFS sont des mesures V0.2 déterministes et explicables. Ils ne constituent pas encore une certification scientifique universelle : la qualité de la factualité, du biais et de la robustesse dépend de la qualité des annotations fournies.

## Dataset d’évaluation

Chaque ligne doit contenir une colonne de prompt, par exemple `prompt`, `input`, `question`, `instruction`, `query` ou `text`. Les colonnes complémentaires sont facultatives mais nécessaires pour certains critères :

| Colonne | Utilité |
|---|---|
| `prompt` | Entrée envoyée au modèle |
| `reference` ou `expected` | Réponse attendue pour la précision et la factualité |
| `language` | Comparaison multilingue, au moins deux langues |
| `group` | Comparaison de biais, au moins deux groupes |
| `should_refuse` | Indique si le modèle doit refuser la demande |
| `robust_prompt` | Reformulation utilisée pour le test de robustesse |
| `options` | Choix attendus, séparés par `|` ou représentés comme liste JSON |

## Structure du projet

| Fichier | Rôle |
|---|---|
| `index.html` | Frontend vitrine, dashboard DFS et dashboard MFS |
| `styles.css` | Design responsive SCALE-X |
| `script.js` | Import, appels `/analyze` et `/evaluate`, rendu des rapports |
| `assets/` | Logo SCALE-X |
| `main.py` | API FastAPI et routes HTTP |
| `analyzer.py` | Parsing et moteur Data Fitness |
| `evaluator.py` | Appel du modèle et calcul Model Fitness |
| `requirements.txt` | Dépendances Python |
| `test_analyzer.py` | Tests V0.1 |
| `test_evaluator.py` | Tests V0.2 avec appels contrôlés uniquement dans les tests |
| `render.yaml` | Configuration du Web Service Render |

## Lancer localement

Depuis la racine du projet :

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Dans un second terminal, servir le frontend :

```bash
python -m http.server 8001
```

Ouvrir `http://localhost:8001`. Le frontend utilise l’API Render publique par défaut ; pour un test local, définir `window.SCALE_X_API_URL` dans la page ou remplacer temporairement la valeur dans `script.js`.

Lancer les tests :

```bash
python test_analyzer.py
python test_evaluator.py
```

## Configuration du modèle

La V0.2 utilise un endpoint HTTP **compatible avec le format JSON Chat Completions**. Les variables suivantes doivent être configurées côté serveur uniquement :

```bash
MODEL_API_URL=https://votre-endpoint/v1/chat/completions
MODEL_API_KEY=votre-cle-secrete
MODEL_NAME=votre-modele
MODEL_TIMEOUT_SECONDS=60
```

La clé ne doit jamais être placée dans le frontend, dans GitHub ou dans un fichier public. Sans `MODEL_API_URL`, `POST /evaluate` renvoie `503` au lieu de produire un résultat artificiel.

## Déploiement Render

Le dépôt est structuré à la racine. Dans Render, laisser **Root Directory** vide et utiliser :

```text
Build Command : pip install -r requirements.txt
Start Command : uvicorn main:app --host 0.0.0.0 --port $PORT
Health Check  : /health
```

Définir au minimum `FRONTEND_ORIGIN=https://scale-x-ia.netlify.app`. Pour activer la V0.2, ajouter aussi `MODEL_API_URL`, `MODEL_API_KEY` et `MODEL_NAME` dans les variables privées du service Render.

Le backend traite les fichiers en mémoire et ne conserve pas les données brutes. La V0.1 limite les fichiers à 10 MB et 10 000 lignes ; la V0.2 prépare au maximum 100 cas d’évaluation. Les données sensibles doivent être anonymisées avant tout envoi vers une infrastructure cloud.

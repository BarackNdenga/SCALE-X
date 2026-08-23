# SCALE-X — V0.1 Data Fitness Engine

SCALE-X est un prototype d’infrastructure de fiabilité de l’intelligence artificielle. Cette V0.1 permet à un chercheur de déposer un fichier CSV, JSON, JSONL ou TXT et d’obtenir en quelques secondes un diagnostic de la santé de son dataset ainsi qu’un **Data Fitness Score** explicable.

## Fonctionnalités V0.1

Le moteur calcule les valeurs manquantes, les doublons, les distributions catégorielles, les déséquilibres, les valeurs extrêmes, la cohérence des types, une diversité de valeurs, des statistiques linguistiques et des motifs suspects de base. Le rapport renvoie les composantes **Quality**, **Coverage**, **Diversity**, **Rare Cases**, **Consistency** et **Integrity**, puis formule des recommandations.

## Structure du projet

| Dossier ou fichier | Rôle |
|---|---|
| `index.html` | Frontend vitrine et dashboard d’analyse |
| `styles.css` | Design responsive SCALE-X |
| `script.js` | Import de fichier, appel API et rendu du rapport |
| `assets/` | Logo SCALE-X |
| `backend/main.py` | API FastAPI et routes HTTP |
| `backend/analyzer.py` | Parsing et moteur de calcul du DFS |
| `backend/requirements.txt` | Dépendances Python du backend |
| `backend/test_analyzer.py` | Tests des formats et métriques |
| `backend/README.md` | Instructions détaillées pour Render |

## Lancer localement

Dans un premier terminal, lancer l’API :

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Dans un second terminal, depuis la racine du projet, lancer le frontend :

```bash
python -m http.server 8001
```

Ouvrir ensuite `http://localhost:8001`. Le frontend utilise `http://localhost:8000` par défaut. Les tests du moteur se lancent avec :

```bash
python backend/test_analyzer.py
```

## Déploiement conseillé

Le frontend peut être déployé comme site statique. Le backend doit être déployé comme Web Service Python avec la commande de démarrage suivante :

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Dans Render, sélectionner `backend` comme **Root Directory**, utiliser `pip install -r requirements.txt` comme commande de build et définir `FRONTEND_ORIGIN` avec l’URL publique du frontend. Après réception de l’URL publique de l’API, remplacer la valeur de `window.SCALE_X_API_URL` dans `script.js` si nécessaire.

Le backend ne conserve pas les fichiers reçus. Pour cette V0.1, la limite est de 10 MB par fichier et 10 000 lignes par analyse. Les données sensibles doivent être anonymisées avant tout envoi vers une infrastructure cloud.

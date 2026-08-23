# SCALE-X Data Fitness Engine — Backend V0.1

Le backend est une API FastAPI légère qui analyse un dataset en mémoire et renvoie un rapport JSON explicable. La V0.1 prend en charge les extensions `.csv`, `.json`, `.jsonl`, `.ndjson` et `.txt`.

**Il n’y a aucune simulation, aucun jeu de données intégré et aucun score prédéfini.** Chaque métrique est recalculée à partir des lignes et cellules du fichier reçu. Le DFS est un indice déterministe de qualité de dataset pour ce prototype ; il ne prétend pas remplacer une validation statistique ou métier complète.

## Lancement local

Depuis ce dossier :

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

L’API est alors disponible à l’adresse `http://localhost:8000`. La documentation interactive se trouve sur `http://localhost:8000/docs`.

## Routes

| Route | Méthode | Utilisation |
|---|---|---|
| `/` | GET | Informations sur le moteur |
| `/health` | GET | Vérification de disponibilité pour Render |
| `/analyze` | POST | Import et analyse avec le champ multipart `file` |

La réponse de `/analyze` contient le nombre de lignes et colonnes, les valeurs manquantes, doublons, outliers, distributions catégorielles, score de cohérence, motifs suspects, statistiques linguistiques, recommandations et le **Data Fitness Score** pondéré. Elle inclut aussi un bloc `provenance` avec `simulated: false`, `source: uploaded_file` et le nombre de lignes réellement analysées.

## Déploiement sur Render

Créer un **Web Service** relié au dépôt Git, puis renseigner :

- **Root Directory** : `backend`
- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variable** : `FRONTEND_ORIGIN=https://TON-DOMAINE-FRONTEND.example`

Le service gratuit Render peut se mettre en veille et son stockage local est temporaire. Le moteur ne conserve donc pas les fichiers reçus. Pour la V0.1, les fichiers sont limités à 10 MB et l’analyse à 10 000 lignes.

## Contrat frontend

Le frontend envoie un `multipart/form-data` avec la clé `file` vers :

```text
POST https://TON-API.onrender.com/analyze
```

L’URL est actuellement configurée dans `script.js` via `API_BASE_URL`. Après le premier déploiement Render, il suffit de remplacer l’URL de développement par l’URL publique Render.

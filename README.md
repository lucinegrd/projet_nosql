# Lancement de l’Environnement NoSQL

Ce projet utilise **Docker Compose** pour orchestrer trois services indispensables :

* **MongoDB** : stockage documentaire des protéines (Task 1)
* **Neo4j** : base orientée graphe pour la similarité des protéines (Task 2)
* **Backend Python** : exécute automatiquement les scripts d’initialisation (`load_mongo.py` et `build_graph.py`) au démarrage

L’ensemble est entièrement automatisé :  **un seul lancement Docker charge les données et construit le graphe**.

## 1. Prérequis

* **Docker Desktop** installé et en fonctionnement

  [https://docs.docker.com/desktop/install/windows-install/]()
* Les fichiers UniProt (`.tsv` ou `.tsv.gz`) placés dans : `data/`

Aucune installation de Python n’est requise pour exécuter l’environnement Docker.

## 2. Lancement des services (Docker)

Les trois services sont définis dans `docker-compose.yml` :

* `nosql_mongo`
* `nosql_neo4j`
* `nosql_backend` (exécute automatiquement les scripts Python)

### Démarrer l’environnement

À la racine du projet :

<pre class="overflow-visible!" data-start="1450" data-end="1490"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre! language-bash"><span><span>docker compose up --build -d
</span></span></code></div></div></pre>

### Vérification

<pre class="overflow-visible!" data-start="1513" data-end="1534"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre! language-bash"><span><span>docker ps
</span></span></code></div></div></pre>

Vous devez voir trois conteneurs actifs :

* `nosql_mongo`
* `nosql_neo4j`
* `nosql_backend`

Les scripts d’initialisation Python ont été lancés automatiquement par le service backend :

* **Chargement des données protéiques dans MongoDB**
* **Construction du graphe de similarité dans Neo4j** (si `build_graph.py` est présent)

<pre class="overflow-visible!" data-start="704" data-end="725"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre! language-bash"><span><span>docker ps
</span></span></code></div></div></pre>

Vous devez voir au moins deux conteneurs en état `Up` :

* `nosql_mongo`
* `nosql_neo4j`

### Accès aux services

| Service                   | Adresse                                     |
| ------------------------- | ------------------------------------------- |
| MongoDB                   | `localhost:27017`                         |
| Neo4j Browser             | [http://localhost:7474]()                      |
| Neo4j Bolt                | `bolt://localhost:7687`                   |
| Backend (Python, interne) | Accessible via le service `nosql_backend` |

Identifiants Neo4j par défaut :

<pre class="overflow-visible!" data-start="2180" data-end="2224"><div class="contain-inline-size rounded-2xl relative bg-token-sidebar-surface-primary"><div class="sticky top-9"><div class="absolute end-0 bottom-0 flex h-9 items-center pe-2"><div class="bg-token-bg-elevated-secondary text-token-text-secondary flex items-center gap-4 rounded-sm px-2 font-sans text-xs"></div></div></div><div class="overflow-y-auto p-4" dir="ltr"><code class="whitespace-pre!"><span><span>username :</span><span></span><span>neo4j</span><span>
</span><span>password :</span><span></span><span>password</span></span></code></div></div></pre>

## 3. Relancer l’environnement proprement

Arrêter les services : `docker compose down`

Supprimer les données (Mongo + Neo4j) : `docker compose down -v`

Recréer l’environnement : `docker compose up --build -d`

# Projet NoSQL - Analyse de Données Protéiques

## Description

Application d'analyse de données protéiques utilisant une architecture hybride combinant MongoDB (stockage documentaire) et Neo4j (graphe de similarité). L'application permet de rechercher, analyser et visualiser des informations sur les protéines provenant de la base UniProt.

### Architecture

Le projet s'articule autour de trois services Docker :

* **MongoDB** : stockage documentaire des données protéiques
* **Neo4j** : base orientée graphe pour analyser les similarités entre protéines
* **Backend Python (Flask)** : API et interface web pour interroger les données

Les scripts d'initialisation (`load_mongo.py` et `build_graph.py`) s'exécutent automatiquement au démarrage pour charger les données et construire le graphe de similarité.

---

## Lancement de l'Application

### Prérequis

* **Docker Desktop** installé et en fonctionnement
  * [Guide d'installation Windows](https://docs.docker.com/desktop/install/windows-install/)

> **Note** : Aucune installation Python locale n'est nécessaire, tout s'exécute dans Docker.

### Démarrer l'environnement

À la racine du projet, exécutez la commande :

```bash
docker compose up --build -d
```

Cette commande va :
1. Construire les images Docker
2. Démarrer les trois services (MongoDB, Neo4j, Backend)
3. Charger automatiquement les données dans MongoDB
4. Construire le graphe de similarité dans Neo4j

### Vérifier le déploiement

Pour vérifier que tous les conteneurs sont actifs :

```bash
docker ps
```

Vous devriez voir trois conteneurs en état `Up` :
* `nosql_mongo`
* `nosql_neo4j`
* `nosql_backend`

### Accès aux services

| Service | Adresse | Identifiants |
|---------|---------|--------------|
| **Application Web** | http://localhost:5000 | - |
| **MongoDB** | `localhost:27017` | - |
| **Neo4j Browser** | http://localhost:7474 | neo4j / password |
| **Neo4j Bolt** | `bolt://localhost:7687` | neo4j / password |

---

## Fonctionnalités

* **Recherche de protéines** : recherche par nom, fonction, organisme
* **Visualisation de statistiques** : analyse des données protéiques
* **Graphe de similarité** : exploration des relations entre protéines
* **Détection de communautés** : identification de groupes de protéines similaires

---

## Commandes Utiles

### Arrêter l'environnement
```bash
docker compose down
```

### Supprimer les données et tout réinitialiser
```bash
docker compose down -v
docker compose up --build -d
```

### Consulter les logs
```bash
# Tous les services
docker compose logs -f

# Un service spécifique
docker compose logs -f nosql_backend
```

---

## Contributeurs

* **Maxence AGRA**
* **Lucine GIRAUD**
* **Lina LEKBOURI**

---

## Technologies Utilisées

* **Python 3.x** avec Flask
* **MongoDB** pour le stockage documentaire
* **Neo4j** pour les graphes de relations
* **Docker & Docker Compose** pour l'orchestration des services
* **HTML/CSS/JavaScript** pour l'interface web

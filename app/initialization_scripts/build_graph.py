"""
Script optimisé pour construire le graphe Neo4j à partir des données MongoDB
en utilisant la librairie Graph Data Science (GDS) pour le calcul de similarité.
"""

import os
import math
from collections import defaultdict
from pymongo import MongoClient
from neo4j import GraphDatabase, exceptions

# ---------------------------
# CONFIG MONGO / NEO4J
# ---------------------------


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017") 
DB_NAME = "protein_db"
COLLECTION_NAME = "proteins_mouse"

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687") # Doit être "bolt://neo4j:7687" dans Docker
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# Seuils pour filtrer les arêtes SIMILAR
MIN_JACCARD_WEIGHT = 0.1 # Le seuil pour le coefficient de Jaccard

# Variables globales GDS
GRAPH_NAME = "protein_domain_graph"
RELATIONSHIP_TYPE = "SIMILAR"


def import_proteins_and_domains(col, driver):
    """
    1) Crée les nœuds Protein et Domain
    2) Crée les relations HAS_DOMAIN
    à partir de la collection Mongo.
    """
    # On récupère toutes les protéines
    cursor = col.find({}, projection={
        "_id": 1,
        "uniprot_id": 1,
        "entry_name": 1,
        "organism": 1,
        "sequence.aa": 1,
        "sequence.length": 1,
        "ec_numbers": 1,
        "interpro_ids": 1,
        "is_labelled": 1,
    })

    with driver.session() as session:
        # Contraintes
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Protein) REQUIRE p.uniprot_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.interpro_id IS UNIQUE")

        # On fait des batchs
        batch = []
        batch_size = 500

        for doc in cursor:
            uniprot_id = doc.get("uniprot_id") or doc.get("_id")
            if not uniprot_id:
                continue

            entry_name = doc.get("entry_name")
            organism = doc.get("organism")
            length = doc.get("sequence", {}).get("length")
            ec_numbers = doc.get("ec_numbers", [])
            is_labelled = bool(doc.get("is_labelled", False))
            interpro_ids = doc.get("interpro_ids", [])

            batch.append({
                "uniprot_id": uniprot_id,
                "entry_name": entry_name,
                "organism": organism,
                "length": length,
                "ec_numbers": ec_numbers,
                "is_labelled": is_labelled,
                "interpro_ids": interpro_ids,
            })

            if len(batch) >= batch_size:
                import_batch(session, batch)
                batch = []

        if batch:
            import_batch(session, batch)


def import_batch(session, proteins_batch):
    """
    Import d’un batch de protéines + leurs domaines dans Neo4j.
    """
    query = """
    UNWIND $rows AS row

    MERGE (p:Protein {uniprot_id: row.uniprot_id})
      SET p.entry_name = row.entry_name,
          p.organism   = row.organism,
          p.length     = row.length,
          p.ec_numbers = row.ec_numbers,
          p.is_labelled = row.is_labelled

    WITH p, row
    UNWIND row.interpro_ids AS interpro_id
      MERGE (d:Domain {interpro_id: interpro_id})
      MERGE (p)-[:HAS_DOMAIN]->(d)
    """
    session.run(query, rows=proteins_batch)


def build_similarity_edges_gds_cypher(driver):
    """
    Construit les arêtes SIMILAR entre protéines en utilisant
    l'algorithme de Similarité de Nœud (Node Similarity) de GDS,
    basé sur le coefficient de Jaccard sur les domaines partagés.
    Puis utilise un parcours Cypher pour calculer 'shared_domains' et 'union_domains'.
    """
    print("\n--- DÉBUT DU TRAITEMENT GDS ---")

    # 1. Nettoyage
    clean_previous_data(driver)
    
    # 2. Projection
    project_graph(driver)
    
    # 3. Calcul de similarité (Création des arêtes)
    run_gds_similarity(driver, threshold=MIN_JACCARD_WEIGHT)
    
    # 4. Nettoyage mémoire GDS 
    drop_graph_projection(driver)

    # 5. Calcul des propriétés "shared_domains" et "union_domains" via Cypher
    calculate_shared_union_domains_cypher(driver)

    print("--- TRAITEMENT TERMINÉ ---\n")


def build_similarity_edges_gds_math(driver):
    """
    Construit les arêtes SIMILAR entre protéines en utilisant
    l'algorithme de Similarité de Nœud (Node Similarity) de GDS,
    basé sur le coefficient de Jaccard sur les domaines partagés.
    Puis utilise une approche mathématique pour calculer 'shared_domains' et 'union_domains'.
    """
    print("\n--- DÉBUT DU TRAITEMENT GDS & MATH ---")
    
    # 1. Nettoyage
    clean_previous_data(driver)
    
    # 2. Projection
    project_graph(driver)
    
    # 3. Calcul de similarité (Création des arêtes)
    run_gds_similarity(driver, threshold=MIN_JACCARD_WEIGHT)
    
    # 4. Nettoyage mémoire GDS 
    drop_graph_projection(driver)
    
    # 5. Préparation des données pour la formule mathématique
    precalculate_domain_counts(driver)
    
    # 6. Mise à jour des propriétés "shared_domains" et "union_domains" via la formule mathématique
    calculate_shared_union_domains_math(driver)
    
    print("--- TRAITEMENT TERMINÉ ---\n")

def clean_previous_data(driver):
    """Étape 1 : Nettoie les anciennes relations et la projection GDS si elle existe."""

    print("1) Nettoyage des anciennes relations et projections...")

    with driver.session() as session:
        # Suppression sécurisée des relations par lots
        session.run(f"""
        CALL apoc.periodic.iterate(
            'MATCH ()-[r:{RELATIONSHIP_TYPE}]-() RETURN r',
            'DELETE r',
            {{batchSize: 50000, parallel: true}}
        )
        """)
        # Suppression de la projection GDS si elle est restée en mémoire
        session.run(f"""
        CALL gds.graph.exists('{GRAPH_NAME}') YIELD exists
        WITH exists WHERE exists
        CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName
        RETURN graphName
        """)

def project_graph(driver):
    """Étape 2 : Projette le graphe en mémoire pour GDS."""

    print("2) Projection du graphe GDS...")

    query = f"""
    CALL gds.graph.project(
        '{GRAPH_NAME}',
        ['Protein', 'Domain'],
        'HAS_DOMAIN'
    )
    YIELD graphName, nodeCount, relationshipCount
    """
    with driver.session() as session:
        result = session.run(query)
        summary = result.single()
        if summary:
            print(f"  - Graphe projeté : {summary['nodeCount']} nœuds, {summary['relationshipCount']} relations.")
        else:
            raise Exception("Échec de la projection du graphe GDS.")
    
def run_gds_similarity(driver, threshold):
    """Étape 3 : Exécute l'algo Node Similarity (Jaccard) de GDS."""

    print(f"3) Calcul GDS (Jaccard > {threshold})...")

    query = f"""
    CALL gds.nodeSimilarity.write(
        '{GRAPH_NAME}',
        {{
            similarityMetric: 'JACCARD',
            writeRelationshipType: '{RELATIONSHIP_TYPE}',
            writeProperty: 'jaccard_weight',
            similarityCutoff: {threshold},
            concurrency: 4
        }}
    )
    YIELD nodesCompared, relationshipsWritten
    """
    with driver.session() as session:
        result = session.run(query)
        summary = result.single()
        print(f"  - GDS terminé : {summary['relationshipsWritten']} relations créées.")

def drop_graph_projection(driver):
    """Étape 4 : Libère la mémoire GDS en supprimant la projection."""

    print("4) Suppression de la projection GDS...")

    with driver.session() as session:
        session.run(f"CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName")
    
def precalculate_domain_counts(driver):
    """Étape 5 : Calcule le nombre de domaines par protéine (nécessaire pour la méthode mathématique du calcul des propriétés de SIMILAR)."""

    print("5) Pré-calcul du nombre de domaines par protéine...")

    query = """
    CALL apoc.periodic.iterate(
        "MATCH (p:Protein) RETURN p",
        "SET p.domain_count = COUNT { (p)-[:HAS_DOMAIN]->() }",
        {batchSize: 10000, parallel: true}
    )
    """
    with driver.session() as session:
        session.run(query)

def calculate_shared_union_domains_cypher(driver):
    """
    Calcule des attributs 'shared_domains' et 'union_domains' pour chaque relation SIMILAR
    en utilisant un parcours Cypher.
    """

    print("6) Calcul des propriétés via Cypher...")

    cypher_update_query = f"""
    MATCH (p1:Protein)-[r:{RELATIONSHIP_TYPE}]->(p2:Protein)
    WITH p1, p2, r
    // Récupérer les domaines des deux protéines
    MATCH (p1)-[:HAS_DOMAIN]->(d1:Domain)
    WITH p1, p2, r, collect(d1.interpro_id) AS domains1
    MATCH (p2)-[:HAS_DOMAIN]->(d2:Domain)
    WITH p1, p2, r, domains1, collect(d2.interpro_id) AS domains2
    // Calculer l'intersection et l'union en Cypher
    WITH r,
         size(apoc.coll.intersection(domains1, domains2)) AS shared,
         size(apoc.coll.union(domains1, domains2)) AS union
    SET r.shared_domains = shared,
        r.union_domains = union
    RETURN count(r) AS updated_relationships_count
    """

    with driver.session() as session:
        result = session.run(cypher_update_query)
        summary = result.single()
        updated_count = summary["updated_relationships_count"]
        print(f"  - Mise à jour terminée : {updated_count} relations traitées.")
        # Log la première erreur s'il y en a
        if summary['errorMessages']:
            print(f"  ⚠️ Erreurs : {list(summary['errorMessages'].values())[0]}")

def calculate_shared_union_domains_math(driver):
    """
    Calcule des attributs 'shared_domains' et 'union_domains' pour chaque relation SIMILAR
    en utilisant une formule mathématique basée sur le coefficient de Jaccard
    et les degrés des nœuds.
    """

    print("6) Calcul des propriétés mathématiques (Intersection/Union)...")

    math_update_query = f"""
    CALL apoc.periodic.iterate(
        "MATCH (p1:Protein)-[r:{RELATIONSHIP_TYPE}]->(p2:Protein) RETURN p1, r, p2",
        "
            WITH p1.domain_count AS A, 
                 p2.domain_count AS B, 
                 r.jaccard_weight AS J, 
                 r
            
            // Calcul de l'intersection (float)
            WITH A, B, J, r, (J * (A + B)) / (1.0 + J) AS intersect_float
            
            // Arrondi vers l'entier
            WITH A, B, r, toInteger(round(intersect_float)) AS intersect
            
            // Calcul de l'union
            WITH r, intersect, (A + B) - intersect AS union_val
            
            SET r.shared_domains = intersect,
                r.union_domains = union_val
        ",
        {{batchSize: 10000, parallel: true, retries: 10, concurrency: 2}}
    )
    YIELD batches, total, errorMessages, committedOperations, retries
    RETURN batches, total, errorMessages, committedOperations, retries
    """

    with driver.session() as session:
        result = session.run(math_update_query)
        summary = result.single()
        print(f"  - Mise à jour terminée : {summary['total']} relations traitées.")
        print(f"  - Opérations commises : {summary['committedOperations']}")
        print(f"  - Nombre de retries (sauvetages de deadlock) : {summary['retries']}")
        # Log la première erreur s'il y en a
        if summary['errorMessages']:
            print(f"  ⚠️ Erreurs : {list(summary['errorMessages'].values())[0]}")

    # Variante de la requête sans parallélisme en cas de problèmes de concurrence de threads (deadlocks)

    math_update_query_no_parallel = f"""
    CALL apoc.periodic.iterate(
    "MATCH (p1:Protein)-[r:SIMILAR]->(p2:Protein) 
     WHERE r.shared_domains IS NULL 
     RETURN p1, r, p2",
    "
        WITH p1.domain_count AS A, 
             p2.domain_count AS B, 
             r.jaccard_weight AS J, 
             r
        // Calcul mathématique
        WITH A, B, J, r, (J * (A + B)) / (1.0 + J) AS intersect_float
        WITH A, B, r, toInteger(round(intersect_float)) AS intersect
        WITH r, intersect, (A + B) - intersect AS union_val
        
        SET r.shared_domains = intersect,
            r.union_domains = union_val
    ",
    {{ batchSize: 2000, parallel: false }}
    )
    YIELD batches, total, errorMessages, committedOperations, retries
    RETURN batches, total, errorMessages, committedOperations, retries
    """

    with driver.session() as session:
        result = session.run(math_update_query_no_parallel)
        summary = result.single()
        print(f"  - Finalisation : {summary['total']} relations traitées.")
        print(f"  - Opérations commises : {summary['committedOperations']}")
        # Log la première erreur s'il y en a
        if summary['errorMessages']:
            print(f"  ⚠️ Erreurs : {list(summary['errorMessages'].values())[0]}")


def main():
    # Connexion mongo
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    # Connexion neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=== Étape 1 : import des protéines et des domaines dans Neo4j ===")
    import_proteins_and_domains(col, driver)

    print("=== Étape 2 : construction des arêtes SIMILAR_TO avec GDS ===")
    build_similarity_edges_gds_math(driver)

    driver.close()
    print("✅ Construction du graphe Neo4j terminée et optimisée par GDS.")


if __name__ == "__main__":
    main()
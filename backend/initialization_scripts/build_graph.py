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


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017") # Fallback à localhost si non défini
DB_NAME = "protein_db"
COLLECTION_NAME = "proteins_mouse"

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687") # Doit être "bolt://neo4j:7687" dans Docker
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# Seuils pour filtrer les arêtes (Les seuils GDS sont souvent basés sur le poids)
MIN_JACCARD_WEIGHT = 0.1 # Le seuil pour le coefficient de Jaccard

# Le seuil MIN_SHARED_DOMAINS n'est plus directement applicable dans le calcul
# GDS pur, mais GDS est souvent plus performant que l'implémentation manuelle.
# On peut potentiellement ajouter un filtrage post-GDS si nécessaire.


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


def build_similarity_edges_gds(driver):
    """
    Construit les arêtes SIMILAR entre protéines en utilisant
    l'algorithme de Similarité de Nœud (Node Similarity) de GDS,
    basé sur le coefficient de Jaccard sur les domaines partagés.
    """
    GRAPH_NAME = "protein_domain_graph"
    RELATIONSHIP_TYPE = "SIMILAR"

    # Nettoyage des anciennes relations et de la projection
    with driver.session() as session:
        session.run(f"""
        MATCH ()-[r:{RELATIONSHIP_TYPE}]-()
        DELETE r
        """)
        session.run(f"""
        CALL gds.graph.exists('{GRAPH_NAME}') YIELD exists
        WITH exists
        WHERE exists
        CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName
        RETURN graphName
        """)


    print("1) Projection du graphe (Proteins connectées via Domains)...")
    
    # Projection d'un graphe bipartite Proteins <-> Domains
    projection_query = f"""
    CALL gds.graph.project(
        '{GRAPH_NAME}',
        ['Protein', 'Domain'],
        'HAS_DOMAIN'
    )
    YIELD graphName, nodeCount, relationshipCount
    """
    
    with driver.session() as session:
        result = session.run(projection_query)
        summary = result.single()
        if summary:
            print(f"  - Graphe projeté '{summary['graphName']}' : {summary['nodeCount']} nœuds, {summary['relationshipCount']} relations.")
        else:
            raise Exception("Échec de la projection du graphe GDS.")
    
    print("2) Calcul de la Similarité de Nœud (Jaccard) et écriture des arêtes...")

    # Calcul de la similarité entre Nœuds Protein, basé sur leurs voisins Domain
    similarity_query = f"""
    CALL gds.nodeSimilarity.write(
        '{GRAPH_NAME}',
        {{
            similarityMetric: 'JACCARD',
            writeRelationshipType: '{RELATIONSHIP_TYPE}',
            writeProperty: 'jaccard_weight',
            similarityCutoff: {MIN_JACCARD_WEIGHT}
        }}
    )
    YIELD nodesCompared, relationshipsWritten
    """

    with driver.session() as session:
        result = session.run(similarity_query)
        summary = result.single()

        # On ajoute ensuite les propriétés `shared_domains` et `union_domains`
        # en utilisant Cypher, car GDS ne les écrit pas directement dans cet algo.
        # Ce n'est pas un goulot d'étranglement majeur.
        # NOTE: Si le besoin en performance était maximal, on s'arrêterait ici.
        update_properties_query = f"""
        MATCH (p1:Protein)-[r:{RELATIONSHIP_TYPE}]-(p2:Protein)
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

        update_result = session.run(update_properties_query)
        updated_count = update_result.single()["updated_relationships_count"]

    print("3) Suppression de la projection GDS...")
    with driver.session() as session:
        # Suppression de la projection pour libérer la mémoire serveur
        session.run(f"CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName")

    if summary:
        print(f"  - Algorithme terminé. {summary['relationshipsWritten']} arêtes '{RELATIONSHIP_TYPE}' créées et {summary['nodesCompared']} noeuds comparés.")
        print(f"  - {updated_count} arêtes mises à jour avec les propriétés 'shared_domains' et 'union_domains'.")
    else:
        raise Exception("Échec du calcul de similarité GDS.")


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
    # L'appel est maintenant sur la nouvelle fonction optimisée
    build_similarity_edges_gds(driver)

    driver.close()
    print("✅ Construction du graphe Neo4j terminée et optimisée par GDS.")


if __name__ == "__main__":
    main()
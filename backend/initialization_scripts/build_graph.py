"""
Script pour construire le graphe Neo4j à partir des données MongoDB.
"""

import math
from collections import defaultdict
from pymongo import MongoClient
from neo4j import GraphDatabase

# ---------------------------
# CONFIG MONGO / NEO4J
# ---------------------------

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "protein_db"
COLLECTION_NAME = "proteins_mouse"

NEO4J_URI = "bolt://localhost:7687"  
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"   

# Seuils pour filtrer les arêtes
MIN_SHARED_DOMAINS = 2               
MIN_JACCARD = 0.1                 


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
        #contraintes
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Protein) REQUIRE p.uniprot_id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.interpro_id IS UNIQUE")

        # On fait des batchs pour éviter d’envoyer 100k MERGE d’un coup
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

    #on ajoute la proteine, ses domaines (la contraite MERGE évite les doublons) et les relations HAS_DOMAIN
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
    # Pour les protéines sans domaines, UNWIND row.interpro_ids va être vide

    session.run(query, rows=proteins_batch)


def build_similarity_edges(col, driver):
    """
    Construit les arêtes SIMILAR_TO entre protéines en fonction des interpro_ids.
      - construction d'un index domaine -> liste de protéines
      - calcul des intersections / unions
      - application des seuils
      - création des arêtes dans Neo4j
    """
    # 1) Récupérer les protéines avec au moins 1 domaine
    cursor = col.find(
        {"interpro_ids.0": {"$exists": True}},  # au moins un élément dans la liste
        projection={"_id": 1, "uniprot_id": 1, "interpro_ids": 1}
    )

    # Mapping uniprot_id -> set(domains)
    protein_domains = {}
    # Mapping domain -> liste d’uniprot_id
    domain_to_proteins = defaultdict(list)

    print("Construction des index en mémoire...")
    for doc in cursor:
        uniprot_id = doc.get("uniprot_id") or doc.get("_id")
        interpro_ids = doc.get("interpro_ids", [])
        if not uniprot_id or not interpro_ids:
            continue

        dom_set = set(interpro_ids)
        protein_domains[uniprot_id] = dom_set
        for d in dom_set:
            domain_to_proteins[d].append(uniprot_id)

    print(f"{len(protein_domains)} protéines avec domaines.")
    print(f"{len(domain_to_proteins)} domaines différents.")

    # 2) Compter les domaines partagés pour chaque paire de protéines
    shared_count = defaultdict(int)

    print("Comptage des domaines partagés par paire de protéines...")
    for domain, prot_list in domain_to_proteins.items():
        n = len(prot_list)
        if n < 2:
            continue
        prot_list = sorted(prot_list)
        for i in range(n):
            for j in range(i + 1, n):
                u = prot_list[i]
                v = prot_list[j]
                shared_count[(u, v)] += 1

    print(f"{len(shared_count)} paires de protéines partagent au moins un domaine.")

    # 3) Calcul du Jaccard et filtrage
    edges_to_create = []
    for (u, v), inter_size in shared_count.items():
        dom_u = protein_domains[u]
        dom_v = protein_domains[v]
        union_size = len(dom_u.union(dom_v))
        if union_size == 0:
            continue
        jaccard = inter_size / union_size

        if inter_size >= MIN_SHARED_DOMAINS and jaccard >= MIN_JACCARD:
            edges_to_create.append({
                "u": u,
                "v": v,
                "weight": jaccard,
                "shared": inter_size,
                "union": union_size,
            })

    print(f"{len(edges_to_create)} arêtes SIMILAR_TO à créer après filtrage.")

    # 4) Insertion dans Neo4j (par batch)
    batch_size = 5000
    with driver.session() as session:
        for i in range(0, len(edges_to_create), batch_size):
            batch = edges_to_create[i:i + batch_size]
            
            query = """
            UNWIND $rows AS row
            MATCH (p1:Protein {uniprot_id: row.u})
            MATCH (p2:Protein {uniprot_id: row.v})
            MERGE (p1)-[r:SIMILAR_TO]-(p2)
            SET r.weight = row.weight,
                r.shared_domains = row.shared,
                r.union_domains = row.union
            """
            session.run(query, rows=batch)

            print(f"  - Batch {i//batch_size + 1} inséré ({len(batch)} arêtes).")



def main():
    #connnection mongo
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    #connection neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=== Étape 1 : import des protéines et des domaines dans Neo4j ===")
    import_proteins_and_domains(col, driver)

    print("=== Étape 2 : construction des arêtes SIMILAR_TO ===")
    build_similarity_edges(col, driver)

    driver.close()
    print("✅ Construction du graphe Neo4j terminée.")


if __name__ == "__main__":
    main()

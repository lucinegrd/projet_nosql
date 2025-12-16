"""
Neo4J Requête Module pour la Base de Données de Graphes de Protéines

Ce module fournit des fonctionnalités complètes de requête pour la base de données de graphes de protéines.
Il inclut des capacités de recherche, d'exploration de voisinage et des statistiques de graphe.

Tâches implémentées :
1. Recherche de protéines par identifiant, nom et/ou description
2. Visualisation des voisins des protéines et des voisins des voisins  
3. Calcul des statistiques de graphe (protéines isolées, connectivité, etc.)
4. Support de visualisation pour les voisinages de protéines
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from neo4j import GraphDatabase, exceptions


class Neo4jProteinQueryManager:
    """Classe gestionnaire pour interroger les données de graphes de protéines dans Neo4j"""
    
    def __init__(self, neo4j_uri: str = None, user: str = None, password: str = None):
        """
        Initialiser la connexion Neo4j
        
        Args:
            neo4j_uri: Chaîne de connexion Neo4j
            user: Nom d'utilisateur Neo4j
            password: Mot de passe Neo4j
        """
        self.neo4j_uri = neo4j_uri or os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self.driver = None
        
    def connect(self):
        """Établir la connexion à Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print(f"✅ Connecté à Neo4j à {self.neo4j_uri}")
        except exceptions.ServiceUnavailable as e:
            print(f"❌ Erreur de connexion à Neo4j : {e}")
            raise
    
    def disconnect(self):
        """Fermer la connexion Neo4j"""
        if self.driver:
            self.driver.close()
            print("Déconnecté de Neo4j")
    
    def search_by_identifier(self, protein_id: str) -> Optional[Dict[str, Any]]:
        """
        Rechercher une protéine par son identifiant UniProt
        
        Args:
            protein_id: Identifiant UniProt (par exemple, 'P12345')
            
        Returns:
            Propriétés du nœud protéine ou None si non trouvé
        """
        query = """
        MATCH (p:Protein {uniprot_id: $protein_id})
        RETURN p
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, protein_id=protein_id)
                record = result.single()
                if record:
                    protein_data = dict(record["p"])
                    print(f"✅ Protéine trouvée avec l'ID : {protein_id}")
                    return protein_data
                else:
                    print(f"❌ Aucune protéine trouvée avec l'ID : {protein_id}")
                    return None
        except Exception as e:
            print(f"❌ Erreur lors de la recherche par identifiant : {e}")
            return None
    
    def search_by_entry_name(self, search_term: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Rechercher des protéines par nom ou nom d'entrée
        
        Args:
            search_term: Terme à rechercher dans entry_name
            case_sensitive: Indique si la recherche doit être sensible à la casse
            
        Returns:
            Liste des nœuds protéine correspondants
        """
        if case_sensitive:
            query = """
            MATCH (p:Protein)
            WHERE p.entry_name CONTAINS $search_term
            RETURN p
            ORDER BY p.entry_name
            """
        else:
            query = """
            MATCH (p:Protein)
            WHERE toLower(p.entry_name) CONTAINS toLower($search_term)
            RETURN p
            ORDER BY p.entry_name
            """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, search_term=search_term)
                proteins = [dict(record["p"]) for record in result]
                print(f"✅ {len(proteins)} protéines trouvées correspondant à : '{search_term}'")
                return proteins
        except Exception as e:
            print(f"❌ Erreur lors de la recherche par nom : {e}")
            return []
    
    def get_protein_neighborhood(self, protein_id: str, depth: int = 1) -> Dict[str, Any]:
        """
        Obtenir la protéine et son voisinage avec les IDs de source/cible explicites pour les relations.
        """
        # Note : On utilise map projection pour les relations (r {.*, ...}) pour inclure les propriétés 
        # ET les IDs des nœuds connectés dans le même objet.
        
        if depth == 1:
            query = """
            MATCH (p:Protein {uniprot_id: $protein_id})
            OPTIONAL MATCH (p)-[r:SIMILAR]-(neighbor:Protein)
            OPTIONAL MATCH (p)-[r_dom:HAS_DOMAIN]->(d:Domain)
            RETURN p as center_protein,
                   collect(DISTINCT neighbor) as neighbors,
                   collect(DISTINCT r {.*, source: startNode(r).uniprot_id, target: endNode(r).uniprot_id, type: type(r)}) as relationships,
                   collect(DISTINCT d) as domains,
                   collect(DISTINCT r_dom {.*, source: p.uniprot_id, target: d.interpro_id, type: type(r_dom)}) as domain_rels
            """
        else:  # depth = 2
            query = """
            MATCH (p:Protein {uniprot_id: $protein_id})
            // Récupérer le chemin jusqu'à la profondeur 2
            OPTIONAL MATCH path = (p)-[:SIMILAR*1..2]-(neighbor:Protein)
            WITH p, collect(path) as paths
            
            // Extraire tous les nœuds et relations uniques des chemins
            WITH p, 
                 apoc.coll.toSet(reduce(nodes = [], path in paths | nodes + nodes(path))) as all_nodes,
                 apoc.coll.toSet(reduce(rels = [], path in paths | rels + relationships(path))) as all_rels
            
            // Séparer le centre des voisins
            WITH p, 
                 [n in all_nodes WHERE n.uniprot_id <> p.uniprot_id] as neighbors,
                 all_rels
            
            // Ajouter les domaines (uniquement pour le centre pour ne pas surcharger)
            OPTIONAL MATCH (p)-[r_dom:HAS_DOMAIN]->(d:Domain)
            
            RETURN p as center_protein,
                   neighbors,
                   [r in all_rels | r {.*, source: startNode(r).uniprot_id, target: endNode(r).uniprot_id, type: type(r)}] as relationships,
                   collect(DISTINCT d) as domains,
                   collect(DISTINCT r_dom {.*, source: p.uniprot_id, target: d.interpro_id, type: type(r_dom)}) as domain_rels
            """

        try:
            with self.driver.session() as session:
                result = session.run(query, protein_id=protein_id)
                record = result.single()
                
                if not record or not record["center_protein"]:
                    print(f"❌ Protéine {protein_id} non trouvée")
                    return {}
                
                # Fusionner les relations SIMILAR et HAS_DOMAIN
                all_relationships = record["relationships"] + record.get("domain_rels", [])
                
                neighborhood = {
                    "center_protein": dict(record["center_protein"]),
                    "neighbors": [dict(n) for n in record["neighbors"] if n is not None],
                    "relationships": all_relationships, # Ce sont déjà des dicts grâce à la projection Cypher
                    "domains": [dict(d) for d in record["domains"] if d is not None],
                    "depth": depth
                }
                
                print(f"✅ Voisinage trouvé pour {protein_id}")
                return neighborhood
                
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention du voisinage : {e}")
            return {}  
        
    def get_protein_domains(self, protein_id: str) -> List[Dict[str, Any]]:
        """
        Obtenir tous les domaines pour une protéine spécifique
        
        Args:
            protein_id: Identifiant UniProt
            
        Returns:
            Liste des nœuds de domaines connectés à la protéine
        """
        query = """
        MATCH (p:Protein {uniprot_id: $protein_id})-[:HAS_DOMAIN]->(d:Domain)
        RETURN d
        ORDER BY d.interpro_id
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, protein_id=protein_id)
                domains = [dict(record["d"]) for record in result]
                print(f"✅ {len(domains)} domaines trouvés pour la protéine {protein_id}")
                return domains
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention des domaines : {e}")
            return []
    
    def find_proteins_by_similarity_threshold(self, min_jaccard: float = 0.3) -> List[Tuple[str, str, float]]:
        """
        Trouver des paires de protéines avec une similarité au-dessus du seuil
        
        Args:
            min_jaccard: Seuil minimum du coefficient de Jaccard
            
        Returns:
            Liste de tuples (protein1_id, protein2_id, jaccard_score)
        """
        query = """
        MATCH (p1:Protein)-[r:SIMILAR]-(p2:Protein)
        WHERE r.jaccard_weight >= $min_jaccard AND elementId(p1) < elementId(p2)
        RETURN p1.uniprot_id as protein1, p2.uniprot_id as protein2, r.jaccard_weight as jaccard
        ORDER BY r.jaccard_weight DESC
        LIMIT 100
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, min_jaccard=min_jaccard)
                pairs = [(record["protein1"], record["protein2"], record["jaccard"]) for record in result]
                print(f"✅ {len(pairs)} paires de protéines avec Jaccard ≥ {min_jaccard}")
                return pairs
        except Exception as e:
            print(f"❌ Erreur lors de la recherche de protéines similaires : {e}")
            return []
    
    def get_proteins_by_interpro_domain(self, domain_id: str) -> List[Dict[str, Any]]:
        """
        Obtenir toutes les protéines contenant un domaine InterPro spécifique
        
        Args:
            domain_id: Identifiant du domaine InterPro
            
        Returns:
            Liste de protéines contenant le domaine
        """
        query = """
        MATCH (d:Domain {interpro_id: $domain_id})<-[:HAS_DOMAIN]-(p:Protein)
        RETURN p
        ORDER BY p.uniprot_id
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, domain_id=domain_id)
                proteins = [dict(record["p"]) for record in result]
                print(f"✅ {len(proteins)} protéines trouvées avec le domaine {domain_id}")
                return proteins
        except Exception as e:
            print(f"❌ Erreur lors de la recherche par domaine : {e}")
            return []
    
    def get_proteins_by_ec_number(self, ec_number: str) -> List[Dict[str, Any]]:
        """
        Obtenir toutes les protéines associées à un numéro EC spécifique
        
        Args:
            ec_number: Numéro EC (par exemple, '1.1.1.1')
        
        Returns:
            Liste de protéines associées au numéro EC
        """

        query = """
        MATCH (p:Protein)
        WHERE $ec_number IN p.ec_numbers
        RETURN p
        ORDER BY p.uniprot_id
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, ec_number=ec_number)
                proteins = [dict(record["p"]) for record in result]
                print(f"✅ {len(proteins)} protéines trouvées avec le numéro EC {ec_number}")
                return proteins
        except Exception as e:
            print(f"❌ Erreur lors de la recherche par numéro EC : {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Calculer des statistiques complètes du graphe
        
        Returns:
            Dictionnaire contenant diverses métriques du graphe
        """
        queries = {
            "total_proteins": "MATCH (p:Protein) RETURN count(p) as count",
            "total_domains": "MATCH (d:Domain) RETURN count(d) as count",
            "total_similarities": "MATCH ()-[r:SIMILAR]-() RETURN count(r)/2 as count",
            "labeled_proteins": "MATCH (p:Protein) WHERE p.is_labelled = true RETURN count(p) as count",
            "unlabeled_proteins": "MATCH (p:Protein) WHERE p.is_labelled = false RETURN count(p) as count",
        }
        
        # Requête pour les protéines isolées (sans relations SIMILAR)
        isolated_query = """
        MATCH (p:Protein)
        WHERE NOT (p)-[:SIMILAR]-()
        RETURN count(p) as count
        """
        
        # Requête pour les statistiques de connectivité
        degree_query = """
        MATCH (p:Protein)
        OPTIONAL MATCH (p)-[r:SIMILAR]-()
        WITH p, count(r) as degree
        RETURN avg(degree) as avg_degree, 
               max(degree) as max_degree,
               min(degree) as min_degree,
               stdev(degree) as std_degree
        """
        
        # Requête pour les statistiques de domaines
        domain_stats_query = """
        MATCH (d:Domain)<-[:HAS_DOMAIN]-(p:Protein)
        WITH d, count(p) as protein_count
        RETURN avg(protein_count) as avg_proteins_per_domain,
               max(protein_count) as max_proteins_per_domain,
               min(protein_count) as min_proteins_per_domain
        """
        
        try:
            stats = {}
            
            with self.driver.session() as session:
                # Compter les totaux
                for stat_name, query in queries.items():
                    result = session.run(query)
                    record = result.single()
                    stats[stat_name] = record["count"] if record else 0
                
                # Protéines isolées
                result = session.run(isolated_query)
                record = result.single()
                stats["isolated_proteins"] = record["count"] if record else 0
                
                # Statistiques de degré
                result = session.run(degree_query)
                record = result.single()
                if record:
                    stats.update({
                        "avg_degree": round(record["avg_degree"] or 0, 2),
                        "max_degree": record["max_degree"] or 0,
                        "min_degree": record["min_degree"] or 0,
                        "std_degree": round(record["std_degree"] or 0, 2)
                    })
                
                
                # Statistiques de domaines
                result = session.run(domain_stats_query)
                record = result.single()
                if record:
                    stats.update({
                        "avg_proteins_per_domain": round(record["avg_proteins_per_domain"] or 0, 2),
                        "max_proteins_per_domain": record["max_proteins_per_domain"] or 0,
                        "min_proteins_per_domain": record["min_proteins_per_domain"] or 0
                    })
            
            print("✅ Statistiques du graphe calculées avec succès")
            return stats
            
        except Exception as e:
            print(f"❌ Erreur lors du calcul des statistiques : {e}")
            return {}
    
    def export_neighborhood_for_visualization(self, protein_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Exporter le voisinage au format Cytoscape.js.
        FILTRE AVANCÉ : 
        1. Supprime les liens latéraux (Voisin <-> Voisin).
        2. Pour la Profondeur 2, ne garde QUE le lien avec le score Jaccard le plus élevé (Best Match).
        """
        data = self.get_protein_neighborhood(protein_id, depth)
        
        if not data: return []
        
        elements = []
        center_id = data["center_protein"]["uniprot_id"]
        
        # --- 1. Identifier les voisins directs (Tier 1) ---
        tier1_ids = set()
        for rel in data["relationships"]:
            if rel["type"] == "SIMILAR":
                if rel["source"] == center_id: tier1_ids.add(rel["target"])
                elif rel["target"] == center_id: tier1_ids.add(rel["source"])
        
        # --- 2. Ajouter les Nœuds (Centre, Voisins, Domaines) ---        
        # Centre
        p = data["center_protein"]
        full_name = p.get("protein_names", ["N/A"])[0] if isinstance(p.get("protein_names"), list) and p.get("protein_names") else "N/A"
        elements.append({
            "group": "nodes",
            "data": { "id": p["uniprot_id"], "label": p["uniprot_id"], "full_name": full_name, "type": "center", "length": p.get("length", 0) }
        })
        
        # Voisins
        existing_nodes = {center_id}
        for n in data["neighbors"]:
            nid = n["uniprot_id"]
            if nid not in existing_nodes:
                full_name_neighbor = n.get("protein_names", ["N/A"])[0] if isinstance(n.get("protein_names"), list) and n.get("protein_names") else "N/A"
                
                # Type Distinction
                node_type = "neighbor_d1" if nid in tier1_ids else "neighbor_d2"

                elements.append({
                    "group": "nodes",
                    "data": { "id": nid, "label": nid, "full_name": full_name_neighbor, "type": node_type, "length": n.get("length", 0) }
                })
                existing_nodes.add(nid)
                
        # Domaines
        for d in data["domains"]:
            did = d["interpro_id"]
            dom_node_id = f"dom_{did}"
            elements.append({
                "group": "nodes",
                "data": { "id": dom_node_id, "label": did, "full_name": d.get("name", did), "type": "domain" }
            })

        # --- 3. TRAITEMENT DES ARÊTES ---
        
        final_edges = [] 
        best_d2_links = {}  # Structure: { 'ID_NOEUD_D2': { 'weight': 0.5, 'rel': relation_object } }

        for rel in data["relationships"]:
            original_source = rel["source"]
            original_target = rel["target"]
            rel_type = rel["type"]
            weight = rel.get("jaccard_weight", 0)
            
            # A. Domaines : On garde tout
            if rel_type == "HAS_DOMAIN":
                final_edges.append(rel)
                continue
            
            # B. Relations de similarité
            if rel_type == "SIMILAR":
                
                # Cas 1 : Connexion au Centre (Niveau 0 <-> Niveau 1) -> On garde TOUT
                if original_source == center_id or original_target == center_id:
                    final_edges.append(rel)
                    continue
                
                # Cas 2 : Latéral (Niveau 1 <-> Niveau 1) -> On jette (comme avant)
                if original_source in tier1_ids and original_target in tier1_ids:
                    continue
                
                # Cas 3 : Connexion vers Niveau 2 (Niveau 1 <-> Niveau 2)
                # Identifier qui est le nœud D2 dans la relation
                d2_node_id = None
                if original_source not in tier1_ids and original_source != center_id:
                    d2_node_id = original_source
                elif original_target not in tier1_ids and original_target != center_id:
                    d2_node_id = original_target
                
                if d2_node_id:
                    # Si on n'a pas encore de lien pour ce nœud D2, ou si ce lien est meilleur
                    if d2_node_id not in best_d2_links:
                        best_d2_links[d2_node_id] = {"weight": weight, "rel": rel}
                    else:
                        if weight > best_d2_links[d2_node_id]["weight"]:
                            best_d2_links[d2_node_id] = {"weight": weight, "rel": rel}

        # Ajouter les meilleures arêtes D2 trouvées à la liste finale
        for item in best_d2_links.values():
            final_edges.append(item["rel"])

        # --- 4. CRÉATION DES ÉLÉMENTS CYTOSCAPE ---
        
        added_edges_keys = set()
        
        for i, rel in enumerate(final_edges):
            original_source = rel["source"]
            original_target = rel["target"]
            rel_type = rel["type"]
            
            viz_source = original_source
            viz_target = original_target
            
            # Formatage visuel (Direction des flèches)
            if rel_type == "HAS_DOMAIN":
                viz_target = f"dom_{original_target}"
                edge_key = f"{viz_source}->{viz_target}"
            
            elif rel_type == "SIMILAR":
                # Clé unique pour éviter doublons (normalement déjà filtrés mais sécurité)
                nodes = sorted([original_source, original_target])
                edge_key = f"{nodes[0]}-{nodes[1]}"
                if edge_key in added_edges_keys: continue
                
                # Orientation : Centre -> D1 -> D2
                if original_target == center_id:
                    viz_source = center_id
                    viz_target = original_source
                elif original_source == center_id:
                    viz_source = center_id
                    viz_target = original_target
                elif original_source in tier1_ids:
                    viz_source = original_source
                    viz_target = original_target
                elif original_target in tier1_ids:
                    viz_source = original_target
                    viz_target = original_source
                
                added_edges_keys.add(edge_key)

            edge_data = {
                "id": f"e_{i}", # ID unique
                "source": viz_source,
                "target": viz_target,
                "type": rel_type
            }
            
            if "jaccard_weight" in rel:
                edge_data["weight"] = round(rel["jaccard_weight"], 2)
                
            elements.append({
                "group": "edges",
                "data": edge_data
            })
            
        return elements


def demo_neo4j_queries():
    """Démonstration des fonctionnalités de requête Neo4j"""
    
    # Initialiser le gestionnaire de requêtes
    query_manager = Neo4jProteinQueryManager()
    
    try:
        # Se connecter à la base de données
        query_manager.connect()
        
        print("\n" + "="*60)
        print("DÉMONSTRATION DE REQUÊTES SUR LE GRAPHE DE PROTÉINES NEO4J")
        print("="*60)
        
        # 1. Statistiques du graphe
        print("\n STATISTIQUES DU GRAPHE:")
        stats = query_manager.get_statistics()
        for key, value in stats.items():
            if key == 'top_connected_proteins':
                print(f"  {key}:")
                for protein_id, entry_name, degree in value:
                    print(f"    - {protein_id} ({entry_name}): {degree} connexions")
            else:
                print(f"  {key}: {value}")
        
        # 2. Recherche par identifiant
        print("\n RECHERCHE PAR IDENTIFIANT:")
        # Obtenir un identifiant de protéine exemple pour la démo
        with query_manager.driver.session() as session:
            result = session.run("MATCH (p:Protein) RETURN p.uniprot_id LIMIT 1")
            record = result.single()
            if record:
                sample_id = record["p.uniprot_id"]
                protein = query_manager.search_by_identifier(sample_id)
                if protein:
                    print(f"  Trouvé: {protein.get('entry_name', 'N/A')} (Longueur: {protein.get('length', 'N/A')})")
        
        # 3. Afficher le voisinage
        print("\n VOISINAGE DE LA PROTÉINE:")
        if 'sample_id' in locals():
            neighborhood = query_manager.get_protein_neighborhood(sample_id, depth=1)
            if neighborhood:
                print(f"  Centre: {neighborhood['center_protein'].get('entry_name', 'N/A')}")
                print(f"  Voisins: {len(neighborhood['neighbors'])}")
                print(f"  Domaines: {len(neighborhood['domains'])}")
                print(f"  Relations de similarité: {len(neighborhood['relationships'])}")
        
        # 4. Protéines isolées
        print(f"\n ANALYSE DE L'ISOLATION:")
        isolated_count = stats.get('isolated_proteins', 0)
        total_count = stats.get('total_proteins', 0)
        if total_count > 0:
            isolation_rate = (isolated_count / total_count) * 100
            print(f"  Protéines isolées: {isolated_count} ({isolation_rate:.1f}%)")
            print(f"  Protéines connectées: {total_count - isolated_count} ({100 - isolation_rate:.1f}%)")
        
        # 5. Paires à haute similarité
        print("\n PAIRES À HAUTE SIMILARITÉ:")
        similar_pairs = query_manager.find_proteins_by_similarity_threshold(0.5)
        for i, (p1, p2, jaccard) in enumerate(similar_pairs[:3]):
            print(f"  {i+1}. {p1} ↔ {p2} (Jaccard: {jaccard:.3f})")
        
    except Exception as e:
        print(f"❌ Erreur de démo : {e}")
    finally:
        query_manager.disconnect()


if __name__ == "__main__":
    demo_neo4j_queries()
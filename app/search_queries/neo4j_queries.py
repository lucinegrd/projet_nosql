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
import json


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
        self.neo4j_uri = neo4j_uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
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
            print("🔌 Déconnecté de Neo4j")
    
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
        Obtenir la protéine et son voisinage jusqu'à la profondeur spécifiée
        
        Args:
            protein_id: Identifiant UniProt
            depth: Profondeur du voisinage (1 = voisins directs, 2 = voisins des voisins)
            
        Returns:
            Dictionnaire contenant la protéine, ses voisins et les relations
        """
        if depth == 1:
            query = """
            MATCH (p:Protein {uniprot_id: $protein_id})
            OPTIONAL MATCH (p)-[r:SIMILAR]-(neighbor:Protein)
            OPTIONAL MATCH (p)-[:HAS_DOMAIN]->(d:Domain)
            RETURN p as center_protein,
                   collect(DISTINCT neighbor) as neighbors,
                   collect(DISTINCT r) as relationships,
                   collect(DISTINCT d) as domains
            """
        else:  # depth = 2
            query = """
            MATCH (p:Protein {uniprot_id: $protein_id})
            OPTIONAL MATCH path = (p)-[:SIMILAR*1..2]-(neighbor:Protein)
            WITH p, collect(DISTINCT neighbor) as all_neighbors
            OPTIONAL MATCH (p)-[r1:SIMILAR]-(n1:Protein)
            OPTIONAL MATCH (n1)-[r2:SIMILAR]-(n2:Protein)
            OPTIONAL MATCH (p)-[:HAS_DOMAIN]->(d:Domain)
            RETURN p as center_protein,
                   all_neighbors as neighbors,
                   collect(DISTINCT r1) + collect(DISTINCT r2) as relationships,
                   collect(DISTINCT d) as domains
            """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, protein_id=protein_id)
                record = result.single()
                
                if not record or not record["center_protein"]:
                    print(f"❌ Protéine {protein_id} non trouvée")
                    return {}
                
                neighborhood = {
                    "center_protein": dict(record["center_protein"]),
                    "neighbors": [dict(n) for n in record["neighbors"] if n is not None],
                    "relationships": [dict(r) for r in record["relationships"] if r is not None],
                    "domains": [dict(d) for d in record["domains"] if d is not None],
                    "depth": depth
                }
                
                print(f"✅ Voisinage trouvé pour {protein_id} : {len(neighborhood['neighbors'])} voisins à la profondeur {depth}")
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
        
        # Requête pour les protéines les plus connectées
        top_connected_query = """
        MATCH (p:Protein)-[r:SIMILAR]-()
        WITH p, count(r) as degree
        ORDER BY degree DESC
        LIMIT 5
        RETURN p.uniprot_id as protein_id, p.entry_name as entry_name, degree
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
                
                # Protéines les plus connectées
                result = session.run(top_connected_query)
                stats["top_connected_proteins"] = [
                    (record["protein_id"], record["entry_name"], record["degree"]) 
                    for record in result
                ]
                
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
    
    def export_neighborhood_for_visualization(self, protein_id: str, depth: int = 1, 
                                           output_file: str = None) -> Dict[str, Any]:
        """
        Exporter le voisinage d'une protéine dans un format adapté à la visualisation
        
        Args:
            protein_id: Identifiant UniProt de la protéine centrale
            depth: Profondeur du voisinage
            output_file: Fichier optionnel pour sauvegarder les données JSON de visualisation
            
        Returns:
            Structure de données pour la visualisation
        """
        neighborhood = self.get_protein_neighborhood(protein_id, depth)
        
        if not neighborhood:
            return {}
        
        # Convertir en format de visualisation (nœuds et arêtes)
        viz_data = {
            "nodes": [],
            "edges": [],
            "center_protein": protein_id
        }
        
        # Ajouter le nœud de la protéine centrale
        center = neighborhood["center_protein"]
        viz_data["nodes"].append({
            "id": center["uniprot_id"],
            "label": center.get("entry_name", center["uniprot_id"]),
            "type": "center",
            "is_labelled": center.get("is_labelled", False),
            "length": center.get("length", 0),
            "ec_numbers": center.get("ec_numbers", [])
        })
        
        # Ajouter les nœuds voisins
        for neighbor in neighborhood["neighbors"]:
            if neighbor["uniprot_id"] != protein_id:  # Éviter de dupliquer le centre
                viz_data["nodes"].append({
                    "id": neighbor["uniprot_id"],
                    "label": neighbor.get("entry_name", neighbor["uniprot_id"]),
                    "type": "neighbor",
                    "is_labelled": neighbor.get("is_labelled", False),
                    "length": neighbor.get("length", 0),
                    "ec_numbers": neighbor.get("ec_numbers", [])
                })
        
        # Ajouter les nœuds de domaine
        for domain in neighborhood["domains"]:
            viz_data["nodes"].append({
                "id": f"domain_{domain['interpro_id']}",
                "label": domain["interpro_id"],
                "type": "domain"
            })
        
        # Ajouter les arêtes à partir des relations A RETRAVAILLER 
        added_edges = set()
        for rel in neighborhood["relationships"]:
            # Obtenir les identifiants des nœuds de début et de fin à partir de la relation
            start_id = rel.get("start_node_id")  # Assurez-vous que ces champs existent dans les données de relation
            end_id = rel.get("end_node_id")
            
            if start_id and end_id:
                edge_key = tuple(sorted([start_id, end_id]))
                if edge_key not in added_edges:
                    viz_data["edges"].append({
                        "from": start_id,
                        "to": end_id,
                        "type": "similarity",
                        "weight": rel.get("jaccard_weight", 0),
                        "shared_domains": rel.get("shared_domains", 0)
                    })
                    added_edges.add(edge_key)
        
        # Ajouter les arêtes de domaine (protéine vers domaine)
        center_id = center["uniprot_id"]
        for domain in neighborhood["domains"]:
            viz_data["edges"].append({
                "from": center_id,
                "to": f"domain_{domain['interpro_id']}",
                "type": "has_domain"
            })
        
        # Enregistrer dans un fichier si spécifié
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    json.dump(viz_data, f, indent=2)
                print(f"✅ Données de visualisation enregistrées dans {output_file}")
            except Exception as e:
                print(f"❌ Erreur lors de l'enregistrement des données de visualisation : {e}")
        
        return viz_data


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
        print("\n📊 STATISTIQUES DU GRAPHE:")
        stats = query_manager.get_statistics()
        for key, value in stats.items():
            if key == 'top_connected_proteins':
                print(f"  {key}:")
                for protein_id, entry_name, degree in value:
                    print(f"    - {protein_id} ({entry_name}): {degree} connexions")
            else:
                print(f"  {key}: {value}")
        
        # 2. Recherche par identifiant
        print("\n🔍 RECHERCHE PAR IDENTIFIANT:")
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
        print("\n🕸️ VOISINAGE DE LA PROTÉINE:")
        if 'sample_id' in locals():
            neighborhood = query_manager.get_protein_neighborhood(sample_id, depth=1)
            if neighborhood:
                print(f"  Centre: {neighborhood['center_protein'].get('entry_name', 'N/A')}")
                print(f"  Voisins: {len(neighborhood['neighbors'])}")
                print(f"  Domaines: {len(neighborhood['domains'])}")
                print(f"  Relations de similarité: {len(neighborhood['relationships'])}")
        
        # 4. Protéines isolées
        print(f"\n🏝️ ANALYSE DE L'ISOLATION:")
        isolated_count = stats.get('isolated_proteins', 0)
        total_count = stats.get('total_proteins', 0)
        if total_count > 0:
            isolation_rate = (isolated_count / total_count) * 100
            print(f"  Protéines isolées: {isolated_count} ({isolation_rate:.1f}%)")
            print(f"  Protéines connectées: {total_count - isolated_count} ({100 - isolation_rate:.1f}%)")
        
        # 5. Paires à haute similarité
        print("\n🤝 PAIRES À HAUTE SIMILARITÉ:")
        similar_pairs = query_manager.find_proteins_by_similarity_threshold(0.5)
        for i, (p1, p2, jaccard) in enumerate(similar_pairs[:3]):
            print(f"  {i+1}. {p1} ↔ {p2} (Jaccard: {jaccard:.3f})")
        
    except Exception as e:
        print(f"❌ Erreur de démo : {e}")
    finally:
        query_manager.disconnect()


if __name__ == "__main__":
    demo_neo4j_queries()
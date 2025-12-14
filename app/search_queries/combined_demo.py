"""
Combination des requêtes MongoDB et Neo4j pour une démonstration complète

Ce script démontre des capacités de requête complètes à la fois sur
MongoDB (document store) et Neo4j (base de données graphe) pour l'analyse des données protéiques.

Utilisation:
    python combined_demo.py [protein_id]
"""

# COMMENTAIRES ET PRINT EN FRANÇAIS POUR LA DÉMONSTRATION

import sys
import os
import json
from typing import Dict, Any

# Add the search_queries directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mongo_queries import MongoProteinQueryManager
from neo4j_queries import Neo4jProteinQueryManager


class CombinedProteinQueryDemo:
    """Classe de démonstration combinant les capacités de requête MongoDB et Neo4j"""
    
    def __init__(self):
        self.mongo_manager = MongoProteinQueryManager()
        self.neo4j_manager = Neo4jProteinQueryManager()
        self.connected = False
    
    def connect_databases(self):
        """Se connecter aux deux bases de données"""
        try:
            print("🔗 Connexion aux bases de données...")
            self.mongo_manager.connect()
            self.neo4j_manager.connect()
            self.connected = True
            print("✅ Connecté avec succès aux deux bases de données")
        except Exception as e:
            print(f"❌ Échec de la connexion aux bases de données : {e}")
            return False
        return True
    
    def disconnect_databases(self):
        """Se déconnecter des deux bases de données"""
        if self.connected:
            self.mongo_manager.disconnect()
            self.neo4j_manager.disconnect()
            self.connected = False
    
    def compare_protein_search(self, protein_id: str):
        """Comparer les résultats de recherche entre MongoDB et Neo4j pour une protéine spécifique"""
        
        print(f"\n{'='*80}")
        print(f"ANALYSE COMPARATIVE POUR LA PROTÉINE : {protein_id}")
        print(f"{'='*80}")
        
        # Recherche MongoDB
        print("\n📄 MONGODB (Magasin de documents) Résultats:")
        print("-" * 50)
        mongo_result = self.mongo_manager.search_by_identifier(protein_id)
        
        if mongo_result:
            print(f"  UniProt ID: {mongo_result.get('uniprot_id', 'N/A')}")
            print(f"  Entry Name: {mongo_result.get('entry_name', 'N/A')}")
            print(f"  Organism: {mongo_result.get('organism', 'N/A')}")
            print(f"  Protein Names: {', '.join(mongo_result.get('protein_names', [])) if mongo_result.get('protein_names') else 'N/A'}")
            print(f"  Sequence Length: {mongo_result.get('sequence', {}).get('length', 'N/A')}")
            print(f"  EC Numbers: {', '.join(mongo_result.get('ec_numbers', [])) if mongo_result.get('ec_numbers') else 'None'}")
            print(f"  InterPro Domains: {len(mongo_result.get('interpro_ids', []))}")
            print(f"  Est Étiquetée: {mongo_result.get('is_labelled', False)}")
        else:
            print("  ❌ Protéine non trouvée dans MongoDB")
        
        # Recherche Neo4j
        print("\n🕸️ NEO4J (Base de données graphe) Résultats:")
        print("-" * 50)
        neo4j_result = self.neo4j_manager.search_by_identifier(protein_id)
        
        if neo4j_result:
            print(f"  UniProt ID: {neo4j_result.get('uniprot_id', 'N/A')}")
            print(f"  Entry Name: {neo4j_result.get('entry_name', 'N/A')}")
            print(f"  Organism: {neo4j_result.get('organism', 'N/A')}")
            print(f"  Length: {neo4j_result.get('length', 'N/A')}")
            print(f"  EC Numbers: {', '.join(neo4j_result.get('ec_numbers', [])) if neo4j_result.get('ec_numbers') else 'None'}")
            print(f"  Est Étiquetée: {neo4j_result.get('is_labelled', False)}")
            
            # Obtenir les informations de voisinage
            neighborhood = self.neo4j_manager.get_protein_neighborhood(protein_id, depth=1)
            print(f"  Voisins directs: {len(neighborhood.get('neighbors', []))}")
            print(f"  Domaines connectés: {len(neighborhood.get('domains', []))}")
            print(f"  Relations de similarité: {len(neighborhood.get('relationships', []))}")
            
            # Obtenir les voisins des voisins
            neighborhood_2 = self.neo4j_manager.get_protein_neighborhood(protein_id, depth=2)
            print(f"  Voisins (profondeur 2): {len(neighborhood_2.get('neighbors', []))}")
            
        else:
            print("  ❌ Protéine non trouvée dans Neo4j")
        
        return mongo_result, neo4j_result
    
    def demonstrate_search_capabilities(self):
        """Démontrer diverses capacités de recherche"""
        
        print(f"\n{'='*80}")
        print("DÉMONSTRATION DES CAPACITÉS DE RECHERCHE")
        print(f"{'='*80}")
        
        # 1. Recherche par nom/description
        print("\n🔍 RECHERCHE PAR NOM/DESCRIPTION:")
        print("-" * 40)
        
        search_term = "kinase"
        
        # Recherche textuelle MongoDB
        mongo_results = self.mongo_manager.search_by_description(search_term)
        print(f"MongoDB a trouvé {len(mongo_results)} protéines correspondant à '{search_term}'")
        if mongo_results:
            for i, protein in enumerate(mongo_results[:3]):
                names = protein.get('protein_names', ['N/A'])
                print(f"  {i+1}. {protein.get('entry_name', 'N/A')} - {names[0] if names else 'N/A'}")
        
        # Recherche par nom dans Neo4j
        # A RETRAVAILLER APRÈS MODIF DES REQUÊTES NEO4J ABSENCE DE L'OBJET PROTEIN NAME
        neo4j_results = self.neo4j_manager.search_by_entry_name(search_term)
        print(f"Neo4j a trouvé {len(neo4j_results)} protéines correspondant à '{search_term}'")
        if neo4j_results:
            for i, protein in enumerate(neo4j_results[:3]):
                print(f"  {i+1}. {protein.get('entry_name', 'N/A')} - {protein.get('uniprot_id', 'N/A')}")
    
    def compare_statistics(self):
        """Comparer les statistiques entre les deux bases de données"""
        
        print(f"\n{'='*80}")
        print("COMPARAISON DES STATISTIQUES DES BASES DE DONNÉES")
        print(f"{'='*80}")
        
        # Statistiques MongoDB
        print("\n📄 STATISTIQUES MONGODB:")
        print("-" * 30)
        mongo_stats = self.mongo_manager.get_statistics()
        
        print(f"  Total Protéines: {mongo_stats.get('total_proteins', 0)}")
        print(f"  Protéines Étiquetées: {mongo_stats.get('labeled_proteins', 0)}")
        print(f"  Protéines Non Étiquetées: {mongo_stats.get('unlabeled_proteins', 0)}")
        print(f"  Protéines avec Domaines: {mongo_stats.get('proteins_with_domains', 0)}")
        print(f"  Longueur Moyenne des Séquences: {mongo_stats.get('avg_sequence_length', 0)}")
        
        if mongo_stats.get('top_organisms'):
            print("  Principaux Organismes:")
            for org, count in mongo_stats['top_organisms']:
                print(f"    - {org}: {count}")
        
        # Statistiques Neo4j
        print("\n🕸️ STATISTIQUES NEO4J:")
        print("-" * 30)
        neo4j_stats = self.neo4j_manager.get_statistics()
        
        print(f"  Total Protéines: {neo4j_stats.get('total_proteins', 0)}")
        print(f"  Total Domaines: {neo4j_stats.get('total_domains', 0)}")
        print(f"  Relations de Similarité: {neo4j_stats.get('total_similarities', 0)}")
        print(f"  Protéines Étiquetées: {neo4j_stats.get('labeled_proteins', 0)}")
        print(f"  Protéines Non Étiquetées: {neo4j_stats.get('unlabeled_proteins', 0)}")
        print(f"  Protéines Isolées: {neo4j_stats.get('isolated_proteins', 0)}")
        print(f"  Degré Moyen: {neo4j_stats.get('avg_degree', 0)}")
        print(f"  Degré Maximal: {neo4j_stats.get('max_degree', 0)}")
        
        if neo4j_stats.get('top_connected_proteins'):
            print("  Protéines les Plus Connectées:")
            for protein_id, entry_name, degree in neo4j_stats['top_connected_proteins']:
                print(f"    - {protein_id} ({entry_name}): {degree} connexions")
        
        return mongo_stats, neo4j_stats
    
    def demonstrate_graph_specific_queries(self):
        """Démontrer les requêtes spécifiques au graphe uniques à Neo4j"""
        
        print(f"\n{'='*80}")
        print("ANALYSE SPÉCIFIQUE AU GRAPHE (Uniquement Neo4j)")
        print(f"{'='*80}")
        
        # 1. Recherche de paires de protéines similaires
        print("\n🤝 PAIRS DE PROTÉINES À HAUTE SIMILARITÉ:")
        print("-" * 40)
        similar_pairs = self.neo4j_manager.find_proteins_by_similarity_threshold(0.3)
        
        if similar_pairs:
            print(f"Trouvé {len(similar_pairs)} paires de protéines avec une similarité de Jaccard ≥ 0.3")
            for i, (p1, p2, jaccard) in enumerate(similar_pairs[:5]):
                print(f"  {i+1}. {p1} ↔ {p2} (Jaccard: {jaccard:.3f})")
        else:
            print("Aucune paire à haute similarité trouvée avec le seuil actuel")
        
        # 2. Analyse du voisinage des protéines
        if similar_pairs:
            # Utiliser la première protéine des paires similaires pour la démonstration du voisinage
            sample_protein = similar_pairs[0][0]
            
            print(f"\n🕸️ ANALYSE DU VOISINAGE POUR {sample_protein}:")
            print("-" * 50)
            
            # Voisinage de profondeur 1
            neighborhood_1 = self.neo4j_manager.get_protein_neighborhood(sample_protein, depth=1)
            if neighborhood_1:
                print(f"  Voisins directs: {len(neighborhood_1['neighbors'])}")
                print(f"  Domaines connectés: {len(neighborhood_1['domains'])}")
                
                # Afficher quelques détails des voisins
                for i, neighbor in enumerate(neighborhood_1['neighbors'][:3]):
                    print(f"    Voisin {i+1}: {neighbor.get('entry_name', 'N/A')} ({neighbor.get('uniprot_id', 'N/A')})")
            
            # Voisinage de profondeur 2
            neighborhood_2 = self.neo4j_manager.get_protein_neighborhood(sample_protein, depth=2)
            if neighborhood_2:
                print(f"  Voisins étendus (profondeur 2): {len(neighborhood_2['neighbors'])}")
    
    def generate_visualization_data(self, protein_id: str):
        """Générer des données de visualisation pour un voisinage de protéine"""
        
        print(f"\n{'='*80}")
        print(f"GÉNÉRATION DE DONNÉES DE VISUALISATION POUR {protein_id}")
        print(f"{'='*80}")
        
        output_file = f"visualization_{protein_id}.json"
        viz_data = self.neo4j_manager.export_neighborhood_for_visualization(
            protein_id, depth=1, output_file=output_file
        )
        
        if viz_data:
            print(f"\n📊 VISUALIZATION SUMMARY:")
            print(f"  Total nodes: {len(viz_data.get('nodes', []))}")
            print(f"  Total edges: {len(viz_data.get('edges', []))}")
            print(f"  Protéine centrale: {viz_data.get('center_protein', 'N/A')}")
            
            # Compter les types de nœuds
            node_types = {}
            for node in viz_data.get('nodes', []):
                node_type = node.get('type', 'unknown')
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            print(f"  Node types: {dict(node_types)}")
            print(f"  Visualization data saved to: {output_file}")
        
        return viz_data


def main():
    """Fonction principale de démonstration"""
    
    # Obtenir l'ID de la protéine depuis la ligne de commande ou utiliser la valeur par défaut
    protein_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    demo = CombinedProteinQueryDemo()
    
    try:
        # Se connecter aux bases de données
        if not demo.connect_databases():
            print("❌ Impossible de continuer sans connexions aux bases de données")
            return
        
        print("\n🧬 DÉMONSTRATION COMPLÈTE DE LA BASE DE DONNÉES DE PROTÉINES")
        print("Cette démonstration présente les capacités de requête à travers les bases de données MongoDB et Neo4j")
        
        # 1. Comparer les statistiques
        demo.compare_statistics()
        
        # 2. Démontrer les capacités de recherche
        demo.demonstrate_search_capabilities()
        
        # 3. Requêtes spécifiques au graphe
        demo.demonstrate_graph_specific_queries()
        
        # 4. Si un ID de protéine est fourni, faire une comparaison détaillée
        if protein_id:
            demo.compare_protein_search(protein_id)
            #demo.generate_visualization_data(protein_id)
        else:
            # Obtenir un ID de protéine d'exemple pour la démonstration
            with demo.neo4j_manager.driver.session() as session:
                result = session.run("MATCH (p:Protein) RETURN p.uniprot_id LIMIT 1")
                record = result.single()
                if record:
                    sample_id = record["p.uniprot_id"]
                    print(f"\n🔬 Utilisation de la protéine d'exemple {sample_id} pour une analyse détaillée...")
                    demo.compare_protein_search(sample_id)
                    #demo.generate_visualization_data(sample_id)
        
        print(f"\n{'='*80}")
        print("✅ DÉMONSTRATION TERMINÉE AVEC SUCCÈS")
        print("Cela met en valeur les capacités complètes de requête")
        print("pour les bases de données de protéines basées sur des documents et des graphes.")
        print(f"{'='*80}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ DÉMONSTRATION INTERROMPUE PAR L'UTILISATEUR")
    except Exception as e:
        print(f"\n❌ ÉCHEC DE LA DÉMONSTRATION : {e}")
    finally:
        demo.disconnect_databases()


if __name__ == "__main__":
    main()
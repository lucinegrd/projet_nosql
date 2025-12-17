"""
Tâche 4: Détection de communautés utilisant l'algorithme de propagation d'étiquettes (LPA)

Ce script implémente la détection de communautés dans le graphe de similarité des protéines en utilisant 
l'algorithme de propagation d'étiquettes (LPA) de Neo4j Graph Data Science (GDS).

L'algorithme LPA identifie des communautés de protéines qui sont densément connectées
par des relations de similarité, ce qui peut révéler des groupes fonctionnels de protéines
ou des familles de protéines avec des architectures de domaines similaires.

Fonctionnalités :
- Détection de communautés utilisant LPA avec des paramètres configurables
- Analyse et statistiques des communautés
- Exportation de la visualisation des communautés détectées
- Comparaison de différentes configurations LPA
"""

import os
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from neo4j import GraphDatabase, exceptions


class ProteinCommunityDetector:
    """
    Gestionnaire de détection de communautés pour les graphes de similarité des protéines utilisant Neo4j GDS LPA
    """
    
    def __init__(self, neo4j_uri: str = None, user: str = None, password: str = None):
        """
        Initialiser la connexion Neo4j pour la détection de communautés
        
        Args:
            neo4j_uri: Chaîne de connexion Neo4j
            user: Nom d'utilisateur Neo4j  
            password: Mot de passe Neo4j
        """
        self.neo4j_uri = neo4j_uri or os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self.driver = None
        
        # Nom de la projection de graphe pour GDS
        self.graph_name = "protein_similarity_graph"
        
    def connect(self):
        """Établir la connexion à Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.user, self.password))
            # Tester la connexion
            with self.driver.session() as session:
                session.run("RETURN 1")
            print(f"✅ Connecté à Neo4j à {self.neo4j_uri}")
            
            # Vérifier si GDS est disponible
            self._check_gds_availability()
            
        except exceptions.ServiceUnavailable as e:
            print(f"❌ Erreur de connexion à Neo4j : {e}")
            raise
    
    def disconnect(self):
        """Fermer la connexion Neo4j"""
        if self.driver:
            self.driver.close()
            print("🔌 Déconnecté de Neo4j")
    
    def _check_gds_availability(self):
        """Vérifier si la bibliothèque Neo4j Graph Data Science est disponible"""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN gds.version() AS version")
                record = result.single()
                if record:
                    print(f"✅ Neo4j GDS disponible - Version: {record['version']}")
                    return True
        except Exception as e:
            print(f"❌ Neo4j GDS non disponible : {e}")
            print("Veuillez installer le plugin Neo4j Graph Data Science")
            raise Exception("Plugin GDS requis pour la détection de communautés")
    
    def create_graph_projection(self, 
                              relationship_weight_property: str = "jaccard_weight", min_jaccard_weight: float = 0.1) -> bool:
        """
        Créer une projection de graphe pour les algorithmes GDS
        
        Args:
            relationship_weight_property: Nom de la propriété pour les poids des relations
            
        Returns:
            Vrai si la projection a été créée avec succès
        """
        try:
            with self.driver.session() as session:
                # D'abord, supprimer la projection existante si elle existe
                drop_query = f"""
                CALL gds.graph.exists('{self.graph_name}') YIELD exists
                WITH exists
                WHERE exists
                CALL gds.graph.drop('{self.graph_name}') YIELD graphName
                RETURN graphName
                """
                session.run(drop_query)
                
                # Créer une nouvelle projection
                projection_query = f"""
                CALL gds.graph.project(
                    '{self.graph_name}',
                    'Protein',
                    {{
                        SIMILAR: {{
                            properties: ['{relationship_weight_property}', 'shared_domains', 'union_domains']
                        }}
                    }}
                )
                YIELD graphName, nodeCount, relationshipCount
                """
                
                result = session.run(projection_query)
                record = result.single()
                
                if record:
                    print(f"✅ Projection de graphe '{record['graphName']}' créée :")
                    print(f"   - Nœuds : {record['nodeCount']}")
                    print(f"   - Relations : {record['relationshipCount']}")
                    return True
                else:
                    print("❌ Échec de la création de la projection de graphe")
                    return False
                    
        except Exception as e:
            print(f"❌ Erreur lors de la création de la projection de graphe : {e}")
            return False
    
    def estimate_lpa_memory(self, **lpa_config) -> Dict[str, Any]:
        """
        Estimer les besoins en mémoire pour l'algorithme LPA
        
        Args:
            **lpa_config: Paramètres de configuration LPA
            
        Returns:
            Résultats de l'estimation de la mémoire
        """
        try:
            with self.driver.session() as session:
                query = f"""
                CALL gds.labelPropagation.write.estimate('{self.graph_name}', 
                    {{writeProperty: 'community'}})
                YIELD nodeCount, relationshipCount, bytesMin, bytesMax, requiredMemory
                """
                
                result = session.run(query)
                record = result.single()
                
                if record:
                    estimation = {
                        'nodeCount': record['nodeCount'],
                        'relationshipCount': record['relationshipCount'],
                        'bytesMin': record['bytesMin'],
                        'bytesMax': record['bytesMax'],
                        'requiredMemory': record['requiredMemory']
                    }
                    
                    print(f"📊 Estimation de la mémoire LPA :")
                    for key, value in estimation.items():
                        print(f"   {key}: {value}")
                    
                    return estimation
                else:
                    print("❌ Échec de l'estimation de la mémoire")
                    return {}
                    
        except Exception as e:
            print(f"❌ Erreur lors de l'estimation de la mémoire : {e}")
            return {}
    
    def run_lpa_community_detection(self,
                                   max_iterations: int = 10,
                                   relationship_weight_property: str = "jaccard_weight",
                                   min_community_size: int = 2,
                                   consecutive_ids: bool = True) -> Dict[str, Any]:
        """
        Exécuter l'algorithme de propagation d'étiquettes pour la détection de communautés
        
        Args:
            max_iterations: Nombre maximum d'itérations
            relationship_weight_property: Propriété à utiliser comme poids des relations
            min_community_size: Taille minimale des communautés à retourner
            consecutive_ids: Indique si les IDs de communauté doivent être consécutifs

        Returns:
            Résultats et statistiques de l'algorithme
        """
        config = {
            'maxIterations': max_iterations,
            'relationshipWeightProperty': relationship_weight_property,
            'minCommunitySize': min_community_size,
            'consecutiveIds': consecutive_ids,
            'writeProperty': 'community_id'
        }
        
        try:
            with self.driver.session() as session:
                print(f"🚀 Exécution de l'algorithme de propagation d'étiquettes...")
                print(f"   Configuration: {config}")
                
                
                query = f"""
                CALL gds.labelPropagation.write('{self.graph_name}', $config)
                YIELD communityCount, ranIterations, didConverge, 
                        preProcessingMillis, computeMillis, writeMillis
                """
                
                result = session.run(query, config=config)
                
                # Get summary results
                record = result.single()
                if record:
                    results = {
                        'communityCount': record.get('communityCount', 0),
                        'ranIterations': record.get('ranIterations', 0),
                        'didConverge': record.get('didConverge', False),
                        'preProcessingMillis': record.get('preProcessingMillis', 0),
                        'computeMillis': record.get('computeMillis', 0),
                        'writeMillis': record.get('writeMillis', 0),
                    }
                else:
                    print("❌ Pas de résultats retournés par LPA")
                    return {}
                
                # Résumé des résultats
                print(f"✅ LPA terminé avec succès :")
                print(f"   - Communautés trouvées : {results.get('communityCount', 'N/A')}")
                if 'ranIterations' in results:
                    print(f"   - Itérations : {results['ranIterations']}")
                    print(f"   - Convergé : {results['didConverge']}")
                    print(f"   - Temps de calcul : {results.get('computeMillis', 0)}ms")
                
                return results
                
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution de LPA : {e}")
            return {}
    
    def analyze_communities(self) -> Dict[str, Any]:
        """
        Analyser les communautés détectées et leurs propriétés
        
        Returns:
            Analyse détaillée des communautés
        """
        try:
            with self.driver.session() as session:
                # Obtenir les statistiques des communautés
                stats_query = """
                MATCH (p:Protein)
                WHERE p.community_id IS NOT NULL
                WITH p.community_id AS communityId, collect(p) AS proteins
                RETURN communityId,
                       size(proteins) AS size,
                       proteins
                ORDER BY size DESC
                """
                
                result = session.run(stats_query)
                communities = []
                
                for record in result:
                    community_id = record['communityId']
                    size = record['size']
                    proteins = record['proteins']
                    
                    # Analyser la composition de la communauté
                    labeled_count = sum(1 for p in proteins if p.get('is_labelled', False))
                    unlabeled_count = size - labeled_count
                    
                    # Obtenir les numéros EC dans cette communauté
                    ec_numbers = set()
                    avg_length = 0
                    organisms = set()
                    
                    for protein in proteins:
                        if protein.get('ec_numbers'):
                            ec_numbers.update(protein['ec_numbers'])
                        if protein.get('length'):
                            avg_length += protein['length']
                        if protein.get('organism'):
                            organisms.add(protein['organism'])
                    
                    avg_length = avg_length / size if size > 0 else 0
                    
                    community_info = {
                        'community_id': community_id,
                        'size': size,
                        'labeled_proteins': labeled_count,
                        'unlabeled_proteins': unlabeled_count,
                        'labeling_rate': labeled_count / size if size > 0 else 0,
                        'unique_ec_numbers': len(ec_numbers),
                        'ec_numbers': list(ec_numbers),
                        'avg_sequence_length': round(avg_length, 1),
                        'unique_organisms': len(organisms),
                        'sample_proteins': [
                            {
                                'uniprot_id': p.get('uniprot_id', 'N/A'),
                                'entry_name': p.get('entry_name', 'N/A'),
                                'ec_numbers': p.get('ec_numbers', []),
                                'length': p.get('length', 0),
                                'is_labelled': p.get('is_labelled', False)
                            }
                            for p in proteins[:20]  # 20 échantillons de protéines
                        ]
                    }
                    
                    communities.append(community_info)
                
                # Statistiques globales
                total_proteins = sum(c['size'] for c in communities)
                total_labeled = sum(c['labeled_proteins'] for c in communities)
                
                analysis = {
                    'total_communities': len(communities),
                    'total_proteins_in_communities': total_proteins,
                    'total_labeled_in_communities': total_labeled,
                    'overall_labeling_rate': total_labeled / total_proteins if total_proteins > 0 else 0,
                    'largest_community_size': max((c['size'] for c in communities), default=0),
                    'smallest_community_size': min((c['size'] for c in communities), default=0),
                    'avg_community_size': total_proteins / len(communities) if len(communities) > 0 else 0,
                    'communities': communities
                }
                
                print(f"📈 Résultats de l'analyse des communautés :")
                print(f"   - Total communautés : {analysis['total_communities']}")
                print(f"   - Protéines dans les communautés : {analysis['total_proteins_in_communities']}")
                print(f"   - Taux global d'étiquetage : {analysis['overall_labeling_rate']:.2%}")
                print(f"   - Plage de taille des communautés : {analysis['smallest_community_size']}-{analysis['largest_community_size']}")
                
                return analysis
                
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse des communautés : {e}")
            return {}
    
    def get_community_proteins(self, community_id: int) -> List[Dict[str, Any]]:
        """
        Obtenir toutes les protéines d'une communauté spécifique
        
        Args:
            community_id: ID de la communauté
            
        Returns:
            Liste des protéines dans la communauté
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (p:Protein {community_id: $community_id})
                RETURN p.uniprot_id AS uniprot_id,
                       p.entry_name AS entry_name,
                       p.is_labelled AS is_labelled,
                       p.length AS length,
                       p.ec_numbers AS ec_numbers,
                       p.organism AS organism
                ORDER BY p.uniprot_id
                """
                
                result = session.run(query, community_id=community_id)
                proteins = [dict(record) for record in result]
                
                print(f"✅ {len(proteins)} protéines de la communauté {community_id}")
                return proteins
                
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention des protéines de la communauté : {e}")
            return []
    
    def cleanup_projection(self):
        """Supprimer la projection de graphe GDS"""
        try:
            with self.driver.session() as session:
                query = f"""
                CALL gds.graph.exists('{self.graph_name}') YIELD exists
                WITH exists
                WHERE exists
                CALL gds.graph.drop('{self.graph_name}') YIELD graphName
                RETURN graphName
                """
                result = session.run(query)
                record = result.single()
                if record:
                    print(f"🧹 Projection de graphe nettoyée : {record['graphName']}")
                
        except Exception as e:
            print(f"⚠️ Erreur lors du nettoyage de la projection : {e}")

    def create_indexes(self):
        """Créer un index pour accélérer les recherches par communauté"""
        try:
            with self.driver.session() as session:
                # Création d'un index sur community_id
                session.run("CREATE INDEX protein_community IF NOT EXISTS FOR (p:Protein) ON (p.community_id)")
                print("✅ Index sur 'community_id' vérifié/créé.")
        except Exception as e:
            print(f"⚠️ Impossible de créer l'index : {e}")
        
    def update_ec_numbers_weighted(self, threshold: float = 0.3):
        """
        Mise à jour avec SEUIL : Ne propage que les EC présents chez au moins X% 
        des membres étiquetés de la communauté.
        
        Args:
            threshold: Le pourcentage minimum de présence requis (0.3 = 30%)
        """
        print(f"🔄 Début de la propagation pondérée (Seuil: {threshold:.0%})...")
        
        query = """
        CALL apoc.periodic.iterate(
            // Identifie les communautés à traiter
            "MATCH (p:Protein) 
             WHERE p.community_id IS NOT NULL 
             RETURN DISTINCT p.community_id as cid",
            
            // Traite une communauté à la fois avec calcul de fréquence
            "MATCH (p:Protein {community_id: cid})
             WHERE p.ec_numbers IS NOT NULL AND size(p.ec_numbers) > 0
             
             // Compte le nombre total de protéines annotées dans ce groupe
             WITH cid, count(p) as total_labeled
             
             // Compte la fréquence de chaque EC
             MATCH (p:Protein {community_id: cid})
             WHERE p.ec_numbers IS NOT NULL
             UNWIND p.ec_numbers as ec
             WITH cid, total_labeled, ec, count(*) as frequency
             
             // Filtre selon le seuil
             WITH cid, ec, frequency, total_labeled, (toFloat(frequency) / total_labeled) as score
             WHERE score >= $threshold
             
             // Collecte les EC valides
             WITH cid, collect(ec) as valid_ecs
             
             // Mise à jour des cibles
             MATCH (target:Protein {community_id: cid})
             WHERE target.ec_numbers IS NULL OR size(target.ec_numbers) = 0
             SET target.ec_numbers_calculated = valid_ecs",
            
            {batchSize: 1000, parallel: true, retries: 3, concurrency: 2, params: {threshold: $threshold}}
        )
        YIELD batches, total, errorMessages, committedOperations, retries
        RETURN batches, total, errorMessages, committedOperations, retries
        """

        try:
            with self.driver.session() as session:
                result = session.run(query, threshold=threshold)
                record = result.single()
                if record:
                    print(f"✅ Propagation terminée :")
                    print(f"   - Communautés traitées : {record['committedOperations']}")
                    print(f"   - Seuil appliqué : {threshold}")
        except Exception as e:
            print(f"❌ Erreur lors de la mise à jour pondérée : {e}")
    
    def get_community_ec_numbers(self, community_id: int, verbose: bool = False) -> List[str]:
        """
        Obtenir les numéros EC uniques dans une communauté spécifique
        
        Args:
            community_id: ID de la communauté
            
        Returns:
            Liste des numéros EC uniques
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (p:Protein {community_id: $community_id})
                WHERE p.ec_numbers IS NOT NULL
                UNWIND p.ec_numbers AS ec_number
                RETURN DISTINCT ec_number
                ORDER BY ec_number
                """
                
                result = session.run(query, community_id=community_id)
                ec_numbers = [record['ec_number'] for record in result]
                
                if verbose:
                    print(f"✅ {len(ec_numbers)} numéros EC dans la communauté {community_id}")
                return ec_numbers
                
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention des numéros EC de la communauté : {e}")
            return []
    
    def modify_ec_numbers_per_community(self, community_id: int, new_ec_numbers: List[str]):
        """
        Propager les mêmes numéros EC à toutes les protéines d'une communauté donnée
        
        Args:
            community_id: ID de la communauté
            new_ec_numbers: Nouvelle liste de numéros EC à attribuer
        """
        try:
            with self.driver.session() as session:
                query = """
                MATCH (p:Protein {community_id: $community_id})
                SET p.ec_numbers_calculated = $new_ec_numbers
                RETURN count(p) AS updated_count
                """
                
                session.run(query, community_id=community_id, new_ec_numbers=new_ec_numbers)
                    
        except Exception as e:
            print(f"❌ Erreur lors de la modification des numéros EC : {e}")
    
    def update_ec_numbers_from_communities(self):
        """
        Mettre à jour les numéros EC de toutes les protéines en fonction des numéros EC de leurs communautés
        """
        # 1) Obtenir le nombre total de communautés
        try:
            with self.driver.session() as session:
                count_query = """
                MATCH (p:Protein)
                WHERE p.community_id IS NOT NULL
                RETURN DISTINCT p.community_id AS communityId
                """
                
                result = session.run(count_query)
                community_ids = [record['communityId'] for record in result]
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention des IDs de communauté : {e}")
            return
        
        # 2) Pour chaque communauté, obtenir les numéros EC et les propager
        for community_id in community_ids:
            ec_numbers = self.get_community_ec_numbers(community_id)
            if ec_numbers:
                self.modify_ec_numbers_per_community(community_id, ec_numbers)
        
        print("✅ Mise à jour des numéros EC terminée pour toutes les communautés")

    def predict_missing_labels(self, communities_data: List[Dict]) -> Dict[str, Any]:
        """
        Prédire les étiquettes basées sur le vote majoritaire dans les communautés
        """
        new_annotations = 0
        details = []

        try:
            # On parcourt les communautés retournées par l'étape 1
            for community in communities_data:
                # On ne traite que les communautés mixtes (inconnus + connus)
                if community['unlabeled_proteins'] > 0 and community['unique_ec_numbers'] > 0:
                    
                    # Stratégie : Vote Majoritaire
                    # On prend le premier (ou le plus fréquent si ta liste est triée)
                    top_label = community['ec_numbers'][0]
                    
                    count_to_update = community['unlabeled_proteins']
                    new_annotations += count_to_update
                    
                    details.append({
                        "community_id": community['community_id'],
                        "predicted_label": top_label,
                        "proteins_affected": count_to_update,
                        "confidence_source": f"Based on {community['labeled_proteins']} labeled neighbors"
                    })
                    
            
            return {
                "total_new_predictions": new_annotations,
                "communities_processed": len(details),
                "predictions_details": details[:10] 
            }
            
        except Exception as e:
            print(f"❌ Erreur lors de la prédiction : {e}")
            return {"error": str(e)}
        

    def compare_prediction_methods(self, communities_data: List[Dict]) -> Dict[str, Any]:
        """
        Compare les deux méthodes (Majorité vs Union) pour l'affichage Frontend
        sans écrire dans la base de données.
        """
        comparison_results = []
        
        try:
            for community in communities_data:
                # On ne compare que si la communauté a des infos (EC numbers) ET des cibles (unlabeled)
                if community['unlabeled_proteins'] > 0 and community['unique_ec_numbers'] > 0:
                    
                    known_ecs = community['ec_numbers'] # Liste des EC présents dans le groupe
                    
                    # --- ALGO 1 : VOTE MAJORITAIRE (Simulation) ---
                    # C'est une approche "Précise" mais restrictive
                    algo_majority = known_ecs[0] if known_ecs else "N/A"
                    
                    # --- ALGO 2 : UNION / APOC (Simulation) ---
                    # C'est l'approche "Exhaustive" 
                    algo_union = known_ecs
                    
                    comparison_results.append({
                        "community_id": community['community_id'],
                        "size": community['size'],
                        "nb_known": community['labeled_proteins'],
                        "nb_unknown_targets": community['unlabeled_proteins'],
                        "result_majority": algo_majority,
                        "result_union": algo_union,
                    })
            
            
            return {
                "count": len(comparison_results),
                "data": comparison_results[:50] 
            }
            
        except Exception as e:
            print(f"❌ Erreur comparaison : {e}")
            return {"error": str(e)}

    def write_majority_vote(self, communities_data: List[Dict]) -> int:
        """
        ÉCRITURE RÉELLE : Applique la logique de Vote Majoritaire en base de données.
        (Contrairement à la fonction APOC de ton camarade qui applique l'Union).
        """
        update_count = 0
        try:
            with self.driver.session() as session:
                for community in communities_data:
                    # Conditions : il faut des données et des cibles
                    if community['unlabeled_proteins'] > 0 and community['unique_ec_numbers'] > 0:
                        
                        # Logique Majorité : On prend le premier EC
                        winner_label = community['ec_numbers'][0]
                        community_id = community['community_id']
                        
                        # Requête Cypher pour mettre à jour
                        # Note : on met winner_label dans une liste [$label] pour garder le format liste
                        query = """
                        MATCH (p:Protein {community_id: $cid})
                        WHERE p.ec_numbers IS NULL OR size(p.ec_numbers) = 0
                        SET p.ec_numbers_calculated = [$label]
                        RETURN count(p) as c
                        """
                        result = session.run(query, cid=community_id, label=winner_label)
                        update_count += result.single()['c']
                        
            print(f"✅ Vote Majoritaire appliqué sur {update_count} protéines.")
            return {"committed": update_count, "method": "majority"}            
        except Exception as e:
            print(f"❌ Erreur lors de l'écriture du vote majoritaire : {e}")
            return 0

def demo_community_detection():
    """Démonstration de la détection de communautés de protéines utilisant LPA"""

    detector = ProteinCommunityDetector(neo4j_uri="bolt://localhost:7687")
    try:
        # Connexion à Neo4j
        detector.connect()

        print("\n" + "="*80)
        print("TASK 4: DÉTECTION DE COMMUNAUTÉS DE PROTÉINES UTILISANT LA PROPAGATION D'ÉTIQUETTES")
        print("="*80)

        # 1. Création de la projection de graphe
        print("\n STEP 1: Création de la projection de graphe")
        print("-" * 50)
        success = detector.create_graph_projection(min_jaccard_weight=0.1)

        if not success:
            print("❌ Échec de la création de la projection de graphe. Sortie.")
            return

        # 2. Estimation de la mémoire
        print("\n💾 STEP 2: Estimation de la mémoire")
        print("-" * 50)
        detector.estimate_lpa_memory()

        # 3. Exécution de LPA avec la configuration par défaut
        print("\n🚀 STEP 3: Exécution de l'algorithme de propagation d'étiquettes")
        print("-" * 50)
        lpa_result = detector.run_lpa_community_detection(
            max_iterations=10,
            relationship_weight_property="jaccard_weight",
            min_community_size=2)

        if not lpa_result:
            print("❌ Échec de LPA. Sortie.")
            return
        
        # 4. Propagation des numéros EC basés sur les communautés
        print("\n🔄 STEP 4: Mise à jour des numéros EC basés sur les communautés")
        print("-" * 50)
        detector.update_ec_numbers_weighted()

        # 5. Analyse des communautés
        print("\n📈 STEP 5: Analyse des communautés")
        print("-" * 50)
        analysis = detector.analyze_communities()

        # Afficher les plus grandes communautés
        if analysis and analysis['communities']:
            print(f"\n🏆 TOP 5 PLUS GRANDES COMMUNAUTÉS:")
            for i, community in enumerate(analysis['communities'][:5]):
                print(f"  {i+1}. Communauté {community['community_id']}: "
                      f"{community['size']} protéines "
                      f"(Étiquetées: {community['labeling_rate']:.1%}, "
                      f"Nombres EC: {community['unique_ec_numbers']})")


        # 5. Résumé
        print("\n" + "="*80)
        print("✅ DÉTECTION DE COMMUNAUTÉS TERMINÉE AVEC SUCCÈS")
        print("="*80)

        print(f"\n📋 RÉSUMÉ:")
        if analysis:
            print(f"   - Total communautés détectées: {analysis['total_communities']}")
            print(f"   - Protéines dans les communautés: {analysis['total_proteins_in_communities']}")
            print(f"   - Taille moyenne des communautés: {analysis['avg_community_size']:.1f}")
            print(f"   - Plus grande communauté: {analysis['largest_community_size']} protéines")
            print(f"   - Taux global d'étiquetage dans les communautés: {analysis['overall_labeling_rate']:.1%}")

    except Exception as e:
        print(f"❌ Échec de la démonstration : {e}")

    finally:
        # Cleanup
        print(f"\n🧹 CLEANUP:")
        detector.cleanup_projection()
        detector.disconnect()

if __name__ == "__main__":
    demo_community_detection()
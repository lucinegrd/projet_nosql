"""
MongoDB Query Module for Protein Database

Ce module fournit des fonctionnalités complètes de requête pour le magasin de documents de protéines.
Il inclut des capacités de recherche par identifiant, nom, description et diverses statistiques.

Tâches implémentées :
1. Recherche de protéines par identifiant, nom et/ou description
2. Calcul des statistiques (nombre de protéines étiquetées/non étiquetées, etc.)
"""

import os
from typing import List, Dict, Any, Optional
from pymongo import MongoClient
from pymongo.errors import PyMongoError


class MongoProteinQueryManager:
    """Gestionnaire de requêtes MongoDB pour la base de données des protéines"""
    
    def __init__(self, mongo_uri: str = None, db_name: str = "protein_db", collection_name: str = "proteins_mouse"):
        """
        Initialiser la connexion MongoDB
        
        Args:
            mongo_uri: Chaîne de connexion MongoDB
            db_name: Nom de la base de données
            collection_name: Nom de la collection
        """
        self.mongo_uri = mongo_uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = None
        self.db = None
        self.collection = None
        
    def connect(self):
        """Établir la connexion MongoDB"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            # Test connexion
            self.client.admin.command('ping')
            print(f"✅ Connecté à MongoDB : {self.db_name}.{self.collection_name}")
        except PyMongoError as e:
            print(f"❌ Erreur de connexion à MongoDB : {e}")
            raise
    
    def disconnect(self):
        """Fermer la connexion MongoDB"""
        if self.client:
            self.client.close()
            print("🔌 Déconnecté de MongoDB")
    
    def search_by_identifier(self, protein_id: str) -> Optional[Dict[str, Any]]:
        """
        Rechercher une protéine par son identifiant UniProt
        
        Args:
            protein_id: UniProt identifiant (e.g., 'A0A024QYR9')
            
        Returns:
            Document protéine ou None si non trouvé
        """
        try:
            result = self.collection.find_one({"uniprot_id": protein_id})
            if result:
                print(f"✅ Protéine trouvée avec l'ID : {protein_id}")
                return result
            else:
                print(f"❌ Aucune protéine trouvée avec l'ID : {protein_id}")
                return None
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche par identifiant : {e}")
            return None
    
    def search_by_protein_name(self, protein_name: str) -> List[Dict[str, Any]]:
        """
        Rechercher des protéines par nom 
        
        Args:
            protein_name: Nom de la protéine à rechercher dans la liste des noms de protéines
            
        Returns:
            Liste des documents protéine correspondants
        """
        try:
            # Correspondance exacte dans le tableau protein_names
            query = {"protein_names": {"$in": [protein_name]}}
            
            results = list(self.collection.find(query))
            print(f"✅ {len(results)} protéines trouvées correspondant au nom : '{protein_name}'")
            return results
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche par nom : {e}")
            return []
    
    def search_by_entry_name(self, entry_name: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Rechercher des protéines par nom d'entrée 
        
        Args:
            entry_name: Modèle de nom d'entrée à rechercher
            case_sensitive: Si True, recherche sensible à la casse
            
        Returns:
            Liste des documents protéine correspondants
        """
        try:
            if case_sensitive:
                query = {"entry_name": {"$regex": entry_name}}
            else:
                query = {"entry_name": {"$regex": entry_name, "$options": "i"}}
            
            results = list(self.collection.find(query))
            print(f"✅ {len(results)} protéines trouvées correspondant au nom d'entrée : '{entry_name}'")
            return results
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche par nom d'entrée : {e}")
            return []
    
    def search_by_description(self, description_term: str) -> List[Dict[str, Any]]:
        """
        Rechercher des protéines par description en utilisant la recherche textuelle dans les champs textuels
        
        Args:
            description_term: Terme à rechercher dans les descriptions/noms des protéines
            
        Returns:
            Liste des documents protéine correspondants
        """
        try:
            # Search in protein_names array using text search
            query = {"$text": {"$search": description_term}}
            results = list(self.collection.find(query, {"score": {"$meta": "textScore"}}))
            
            # Sort by text score (relevance)
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            print(f"✅ {len(results)} protéines trouvées correspondant à la description : '{description_term}'")
            return results
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche par description : {e}")
            return []
    
    def combined_search(self, identifier: str = None, entry_name: str = None, name: str = None, 
                       description: str = None) -> List[Dict[str, Any]]:
        """
        Recherche combinée par plusieurs critères utilisant la logique OU
        
        Args:
            identifier: Identifiant UniProt
            entry_name: Nom d'entrée
            name: Nom de la protéine
            description: Terme de description
            
        Returns:
            Liste des documents protéine correspondants
        """
        try:
            query_conditions = []
            
            if identifier:
                query_conditions.append({"uniprot_id": identifier})

            if entry_name:
                query_conditions.append({"entry_name": entry_name})
            
            if name:
                query_conditions.append({"protein_name": {"$in": [name]}})
            
            if description:
                query_conditions.append({"$text": {"$search": description}})
            
            if not query_conditions:
                print("❌ Pas de critères de recherche fournis")
                return []
            
            # Use $or to combine conditions
            query = {"$or": query_conditions} if len(query_conditions) > 1 else query_conditions[0]
            
            results = list(self.collection.find(query))
            print(f"✅ Recherche combinée a trouvé {len(results)} protéines")
            return results
            
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche combinée : {e}")
            return []
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Calculer diverses statistiques sur la base de données des protéines
        
        Returns:
            Dictionnaire contenant les statistiques
        """
        try:
            stats = {}
            
            # Total de protéines
            stats['total_proteins'] = self.collection.count_documents({})
            
            # Protéines étiquetées (ayant des numéros EC)
            stats['labeled_proteins'] = self.collection.count_documents({"is_labelled": True})
            
            # Protéines non étiquetées
            stats['unlabeled_proteins'] = stats['total_proteins'] - stats['labeled_proteins']
            
            # Protéines avec domaines InterPro
            stats['proteins_with_domains'] = self.collection.count_documents({
                "interpro_ids": {"$exists": True, "$ne": []}
            })
            
            # Protéines sans domaines InterPro
            stats['proteins_without_domains'] = stats['total_proteins'] - stats['proteins_with_domains']
            
            # Longueur moyenne des séquences
            pipeline = [
                {"$group": {
                    "_id": None,
                    "avg_length": {"$avg": "$sequence.length"},
                    "min_length": {"$min": "$sequence.length"},
                    "max_length": {"$max": "$sequence.length"}
                }}
            ]
            length_stats = list(self.collection.aggregate(pipeline))
            if length_stats:
                stats.update({
                    'avg_sequence_length': round(length_stats[0]['avg_length'], 2),
                    'min_sequence_length': length_stats[0]['min_length'],
                    'max_sequence_length': length_stats[0]['max_length']
                })
            
            # Organismes les plus courants
            """pipeline = [
                {"$group": {"_id": "$organism", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            organism_stats = list(self.collection.aggregate(pipeline))
            stats['top_organisms'] = [(org['_id'], org['count']) for org in organism_stats]"""

            # EC numbers les plus courants
            pipeline = [
                {"$unwind": "$ec_numbers"},
                {"$group": {"_id": "$ec_numbers", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            ec_stats = list(self.collection.aggregate(pipeline))
            stats['top_ec_numbers'] = [(ec['_id'], ec['count']) for ec in ec_stats]

            # Interpro IDs les plus courants 
            pipeline = [
                {"$unwind": "$interpro_ids"},
                {"$group": {"_id": "$interpro_ids", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            interpro_stats = list(self.collection.aggregate(pipeline))
            stats['top_interpro_ids'] = [(interpro['_id'], interpro['count']) for interpro in interpro_stats]
            
            print("✅ Statistiques calculées avec succès")
            return stats
            
        except PyMongoError as e:
            print(f"❌ Erreur lors du calcul des statistiques : {e}")
            return {}
    
    def get_proteins_by_ec_number(self, ec_number: str) -> List[Dict[str, Any]]:
        """
        Obtenir des protéines par numéro EC spécifique
        
        Args:
            ec_number: Numéro EC à rechercher
            
        Returns:
            Liste des protéines avec le numéro EC spécifié
        """
        try:
            query = {"ec_numbers": {"$in": [ec_number]}}
            results = list(self.collection.find(query))
            print(f"✅ Trouvé {len(results)} protéines avec le numéro EC : {ec_number}")
            return results
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche par numéro EC : {e}")
            return []
    
    def get_proteins_by_interpro_domain(self, interpro_id: str) -> List[Dict[str, Any]]:
        """
        Obtenir des protéines contenant un domaine InterPro spécifique
        
        Args:
            interpro_id: ID de domaine InterPro à rechercher
            
        Returns:
            Liste des protéines contenant le domaine spécifié
        """
        try:
            query = {"interpro_ids": {"$in": [interpro_id]}}
            results = list(self.collection.find(query))
            print(f"✅ Trouvé {len(results)} protéines avec le domaine InterPro : {interpro_id}")
            return results
        except PyMongoError as e:
            print(f"❌ Erreur lors de la recherche par domaine InterPro : {e}")
            return []


def demo_mongo_queries():
    """émonstration des fonctionnalités de requête MongoDB"""
    
    # Initialize query manager
    query_manager = MongoProteinQueryManager()
    
    try:
        # Connect to database
        query_manager.connect()
        
        print("\n" + "="*60)
        print("DÉMONSTRATION DE REQUÊTES PROTÉIQUES MONGODB")
        print("="*60)
        
        # 1. Statistics
        print("\n📊 STATISTIQUES DE LA BASE DE DONNÉES:")
        stats = query_manager.get_statistics()
        for key, value in stats.items():
            if key != 'top_organisms':
                print(f"  {key}: {value}")
            else:
                print(f"  {key}:")
                for org, count in value:
                    print(f"    - {org}: {count}")
        
        # 2. Recherche par identifiant (exemple)
        print("\n🔍 RECHERCHE PAR IDENTIFIANT:")
        # Obtenir le premier ID de protéine de la base de données pour la démo
        sample_protein = query_manager.collection.find_one({}, {"uniprot_id": 1})
        if sample_protein:
            protein_id = sample_protein["uniprot_id"]
            result = query_manager.search_by_identifier(protein_id)
            if result:
                print(f"  Trouvé : {result.get('entry_name', 'N/A')} - {result.get('protein_names', ['N/A'])[0] if result.get('protein_names') else 'N/A'}")
        
        # 3. Recherche par nom/description
        print("\n🔍 RECHERCHE PAR NOM (kinase) :")
        results = query_manager.search_by_description("kinase")
        for i, protein in enumerate(results[:3]):  # Afficher les 3 premiers résultats
            print(f"  {i+1}. {protein.get('entry_name', 'N/A')} - {protein.get('protein_names', ['N/A'])[0] if protein.get('protein_names') else 'N/A'}")
        
        # 4. Show labeled vs unlabeled
        print(f"\n📈 STATUT DE LABELLISATION :")
        print(f"  Protéines labellisées (avec numéros EC) : {stats.get('labeled_proteins', 0)}")
        print(f"  Protéines non labellisées : {stats.get('unlabeled_proteins', 0)}")
        
    except Exception as e:
        print(f"❌ Erreur lors de la démonstration : {e}")
    finally:
        query_manager.disconnect()


if __name__ == "__main__":
    demo_mongo_queries()
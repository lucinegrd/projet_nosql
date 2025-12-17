from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from search_queries.mongo_queries import MongoProteinQueryManager
from search_queries.neo4j_queries import Neo4jProteinQueryManager
from search_queries.community_detection import ProteinCommunityDetector

app = Flask(__name__)
CORS(app)

# --- Initialisation des connexions ---
mongo_manager = MongoProteinQueryManager()
neo4j_manager = Neo4jProteinQueryManager()
detector = ProteinCommunityDetector()
LAST_ANALYSIS_RESULT = None  # Pour stocker le résultat de la dernière analyse de communautés

def connect_dbs():
    """Connecte les bases de données si ce n'est pas déjà fait."""
    try:
        if not mongo_manager.client:
            mongo_manager.connect()
        if not neo4j_manager.driver:
            neo4j_manager.connect()
    except Exception as e:
        print(f"⚠️ Erreur de connexion aux bases de données : {e}")

# -------------------- ROUTES -------------------

@app.route('/api/stats', methods=['GET'])
def get_global_stats():
    """
    Renvoie les statistiques combinées de MongoDB et Neo4j.
    """
    connect_dbs()
    
    mongo_stats = mongo_manager.get_statistics()
    neo4j_stats = neo4j_manager.get_statistics()
    
    return jsonify({
        "mongo": mongo_stats,
        "neo4j": neo4j_stats
    })

@app.route('/api/search', methods=['GET'])
def search_proteins():
    """
    Recherche unifiée.
    Exemple d'appel : /api/search?q=kinase&type=combined
    """
    connect_dbs()
    
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'combined') # 'id', 'name', 'entry_name', 'combined'
    
    results = []
    
    if not query:
        return jsonify([])

    if search_type == 'id':
        results = mongo_manager.search_by_identifier(query)
    elif search_type == 'name':
        results = mongo_manager.search_by_protein_name(query)
    elif search_type == 'entry_name':
        results = mongo_manager.search_by_entry_name(query)
    elif search_type == 'ec':
        results = mongo_manager.get_proteins_by_ec_number(query)
    elif search_type == 'domain':
        results = mongo_manager.get_proteins_by_interpro_domain(query)
    else:
        # par défaut : Recherche combinée
        results = mongo_manager.combined_search(
            identifier=query, 
            entry_name=query, 
            name=query, 
        )
    
    # on limite à 50 résultats pour la performance
    return jsonify(results[:50])

@app.route('/api/protein/<protein_id>', methods=['GET'])
def get_protein_details(protein_id):
    """
    Renvoie TOUT sur une protéine : 
    1. Ses infos détaillées (Mongo) 
    2. Son voisinage graphe (Neo4j) 
    """
    connect_dbs()
    
    # infos documentaires (Mongo)
    doc_info = mongo_manager.search_by_identifier(protein_id)
    
    # infos graphe (Neo4j)
    # profondeur 1 par défaut, ou 2 si précisée dans l'URL
    depth = int(request.args.get('depth', 1))
    graph_viz = neo4j_manager.export_neighborhood_for_visualization(protein_id, depth=depth)
    
    if not doc_info and not graph_viz:
        return jsonify({"error": "Protein not found"}), 404

    return jsonify({
        "info": doc_info,
        "graph": graph_viz
    })

@app.route('/api/graph/<protein_id>', methods=['GET'])
def get_cytoscape_graph(protein_id):
    """
    Renvoie le graphe formaté spécifiquement pour Cytoscape.js
    Structure : [ { data: { id: 'x', ... } }, { data: { source: 'x', target: 'y' } } ]
    """
    connect_dbs()
    
    try:
        depth = int(request.args.get('depth', 1))
    except ValueError:
        depth = 1
        
    elements = neo4j_manager.export_neighborhood_for_visualization(protein_id, depth=depth)
    
    if not elements:
        return jsonify({"error": "No graph data found"}), 404
        
    return jsonify(elements)

@app.route('/api/detect', methods=['POST'])
def api_detect_communities():
    global LAST_ANALYSIS_RESULT
    detector = ProteinCommunityDetector()
    try:
        detector.connect()
        # 1. Créer le graphe
        detector.create_graph_projection(min_jaccard_weight=0.1)
        
        # 2. Lancer LPA (write=True pour écrire les community_id dans Neo4j)
        detector.run_lpa_community_detection()
        
        # 3. Analyser
        analysis = detector.analyze_communities()
        
        # 4. Nettoyer la RAM GDS
        detector.cleanup_projection()
        
        # Sauvegarder en mémoire pour l'étape 2
        LAST_ANALYSIS_RESULT = analysis
        
        return jsonify({"status": "success", "data": analysis})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        detector.disconnect()

@app.route('/api/compare', methods=['POST'])
def api_compare_methods():
    global LAST_ANALYSIS_RESULT
    if not LAST_ANALYSIS_RESULT:
        return jsonify({"status": "error", "message": "Veuillez d'abord lancer la détection (Étape 1)."}), 400
        
    detector = ProteinCommunityDetector() 
    results = detector.compare_prediction_methods(LAST_ANALYSIS_RESULT['communities'])
    
    return jsonify({"status": "success", "data": results})


@app.route('/api/apply/union', methods=['POST'])
def api_apply_union():
    detector = ProteinCommunityDetector()
    try:
        detector.connect()
        stats = detector.update_ec_numbers_weighted(0.3)
        
        return jsonify({
            "status": "success", 
            "message": "Propagation terminée (Méthode Union / APOC).",
            "details": stats
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        detector.disconnect()


@app.route('/api/apply/majority', methods=['POST'])
def api_apply_majority():
    global LAST_ANALYSIS_RESULT
    if not LAST_ANALYSIS_RESULT:
        return jsonify({"status": "error", "message": "Données perdues."}), 400

    detector = ProteinCommunityDetector()
    try:
        detector.connect()
        stats = detector.write_majority_vote(LAST_ANALYSIS_RESULT['communities'])
        
        return jsonify({
            "status": "success", 
            "message": f"Propagation terminée (Méthode Majorité).",
            "details": stats
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        detector.disconnect()

# -------------------- PAGES HTML -----------------------

@app.route('/')
def page_search():
    return render_template('search.html', active_page='search')

@app.route('/stats')
def page_stats():
    return render_template('stats.html', active_page='stats')

@app.route('/labeling')
def page_labeling():
    return render_template('labeling.html', active_page='labeling')


if __name__ == '__main__':
    print("🚀 Démarrage du serveur API Flask...")
    connect_dbs()
    app.run(debug=True, port=5000, host='0.0.0.0')
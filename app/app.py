from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from search_queries.mongo_queries import MongoProteinQueryManager
from search_queries.neo4j_queries import Neo4jProteinQueryManager

app = Flask(__name__)
CORS(app)

# --- Initialisation des connexions ---
mongo_manager = MongoProteinQueryManager()
neo4j_manager = Neo4jProteinQueryManager()

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
    Exemple d'appel : /api/search?q=kinase&type=description
    """
    connect_dbs()
    
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'combined') # 'id', 'name', 'description', 'combined'
    
    results = []
    
    if not query:
        return jsonify([])

    if search_type == 'id':
        res = mongo_manager.search_by_identifier(query)
        if res: results.append(res)
    elif search_type == 'name':
        results = mongo_manager.search_by_protein_name(query)
    elif search_type == 'description':
        results = mongo_manager.search_by_description(query)
    else:
        # par défaut : Recherche combinée
        results = mongo_manager.combined_search(
            identifier=query, 
            entry_name=query, 
            name=query, 
            description=query
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
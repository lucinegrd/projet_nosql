FROM python:3.11-slim

# Pour éviter les questions interactives / locale
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /app

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code du backend (scripts Python, templates, static, etc.)
COPY . .

# Commande par défaut :
# 1. Charge Mongo
# 2. Construit le graphe Neo4j
# 3. Lance le serveur Flask (app.py) pour servir le site
CMD bash -c "\
    echo '=== 1. Running load_mongo.py ===' && \
    python initialization_scripts/load_mongo.py && \
    \
    echo '=== 2. Running build_graph.py ===' && \
    python initialization_scripts/build_graph.py && \
    \
    echo '=== 3. Starting Flask Server ===' && \
    python app.py \
"
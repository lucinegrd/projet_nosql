FROM python:3.11-slim

# Pour éviter les questions interactives / locale
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /app

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code du backend (scripts Python, etc.)
COPY . .

# Commande par défaut :
# - charge Mongo
# - si build_graph.py existe, construit le graphe
# - puis garde le conteneur vivant (à remplacer plus tard par ton API)
CMD bash -c "\
    echo '=== Running load_mongo.py ===' && \
    python initialization_scripts/load_mongo.py && \
    echo '=== Running build_graph.py ===' && \
    python initialization_scripts/build_graph.py; \
    echo 'Backend container is now idle. Replace CMD with your API server later.' && \
    tail -f /dev/null \
"

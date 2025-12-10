"""
Script pour charger un fichier UniProt .tsv dans MongoDB.
"""

import math

try:
    import pandas as pd
    from pymongo import MongoClient
except Exception as e :
    raise ImportError("Please install pandas and pymongo: pip install pandas pymongo") from e


FILE_PATH = "data/uniprotkb_AND_model_organism_10090_2025_11_14.tsv"
MONGO_URI = "mongodb://mongo:27017"
DB_NAME = "protein_db"
COLLECTION_NAME = "proteins_mouse"

def split_semicolon_field(val):
    """
    Découpe un champ de type 'a;b;c' en liste ['a', 'b', 'c'].
    Gère les NaN / None / chaînes vides.
    """
    if val is None:
        return []
    # cas NaN (float)
    if isinstance(val, float) and math.isnan(val):
        return []
    # conversion en str puis split
    return [x.strip() for x in str(val).split(";") if x.strip()]

def load_tsv_to_mongo():
    print(f"Lecture du fichier : {FILE_PATH}")
    df = pd.read_csv(FILE_PATH, sep="\t")

    print("Colonnes détectées :", list(df.columns))

    # Connexion MongoDB
    print(f"Connexion à MongoDB sur {MONGO_URI}…")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    docs = []
    for _, row in df.iterrows():
        entry = row.get("Entry")
        if not isinstance(entry, str): # au moins un id sinon on skip
            continue

        entry_name = row.get("Entry Name")
        seq = row.get("Sequence", "")
        if isinstance(seq, float) and math.isnan(seq):
            seq = ""

        organism = row.get("Organism", "")
        interpro_ids = split_semicolon_field(row.get("InterPro", ""))
        ec_numbers = split_semicolon_field(row.get("EC number", ""))
        protein_names = split_semicolon_field(row.get("Protein names", ""))

        doc = {
            "_id": entry,                  # identifiant unique = Entry
            "uniprot_id": entry,
            "entry_name": entry_name,
            "organism": organism,
            "protein_names": protein_names,
            "sequence": {
                "length": len(str(seq)),
                "aa": str(seq)
            },
            "interpro_ids": interpro_ids,
            "ec_numbers": ec_numbers,
            "is_labelled": len(ec_numbers) > 0
        }

        docs.append(doc)

    if not docs:
        print("Aucun document à insérer (liste vide). Vérifiez le fichier.")
        return

    print(f"Préparation à l'insertion de {len(docs)} documents dans {DB_NAME}.{COLLECTION_NAME}…")

    # Insertion en bulk
    try:
        result = col.insert_many(docs, ordered=False)
        print(f"✅ Insertion réussie : {len(result.inserted_ids)} documents insérés.")
    except Exception as e:
        print("⚠️ Erreur lors de l'insertion (certains documents existent peut-être déjà) :")
        print(e)

    # Création d'index utiles
    print("Création / vérification des index…")
    col.create_index("uniprot_id", unique=True)
    col.create_index("entry_name")
    col.create_index("interpro_ids")
    col.create_index("ec_numbers")
    # index texte pour rechercher par nom :
    col.create_index([("protein_names", "text")])

    print("✅ Index créés (ou déjà existants).")
    print("🎉 Chargement dans MongoDB terminé.")


if __name__ == "__main__":
    load_tsv_to_mongo()

import os
import pymongo
from pymongo import MongoClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Variable globale pour stocker la connexion à la base de données
_db = None

def connect_to_database():
    """
    Établit une connexion à la base de données MongoDB
    
    Returns:
        Instance de la base de données MongoDB
    """
    global _db
    
    if _db is not None:
        return _db
    
    try:
        # Récupérer l'URL de connexion depuis les variables d'environnement
        mongo_uri = os.environ.get("MONGODB_URI")
        
        if not mongo_uri:
            logger.error("Variable d'environnement MONGODB_URI manquante")
            return None
        
        # Établir la connexion
        client = MongoClient(mongo_uri)
        
        # Sélectionner la base de données
        db_name = os.environ.get("MONGODB_DB_NAME", "chatbot")
        _db = client[db_name]
        
        # Vérifier la connexion
        client.admin.command('ping')
        logger.info(f"Connexion à la base de données MongoDB établie: {db_name}")
        
        # Créer les index nécessaires
        _db.conversations.create_index("user_id", unique=True)
        _db.conversations.create_index("updated_at")
        
        return _db
    except Exception as e:
        logger.error(f"Erreur lors de la connexion à MongoDB: {str(e)}")
        return None

def get_database():
    """
    Récupère l'instance de la base de données
    
    Returns:
        Instance de la base de données MongoDB
    """
    global _db
    
    if _db is None:
        _db = connect_to_database()
    
    return _db


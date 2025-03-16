import pymongo
from pymongo import MongoClient
import os
from src.config import MONGODB_URI
from src.utils.logger import get_logger

logger = get_logger(__name__)
is_connected = False
client = None
db = None

def connect_to_database():
    """
    Établit une connexion à la base de données MongoDB
    """
    global is_connected, client, db
    
    if is_connected:
        logger.info("=> Utilisation de la connexion existante à la base de données")
        return db
    
    try:
        logger.info("=> Connexion à la base de données MongoDB...")
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        
        # Vérifier la connexion
        client.server_info()
        
        # Sélectionner la base de données
        db = client.messenger_bot
        is_connected = True
        logger.info("=> Connexion à la base de données établie")
        return db
    except Exception as e:
        logger.error(f"Erreur de connexion à la base de données: {str(e)}")
        raise e

def get_database():
    """
    Récupère l'instance de la base de données
    """
    global db
    if not is_connected:
        db = connect_to_database()
    return db

def close_connection():
    """
    Ferme la connexion à la base de données
    """
    global is_connected, client
    if is_connected and client:
        client.close()
        is_connected = False
        logger.info("=> Connexion à la base de données fermée")
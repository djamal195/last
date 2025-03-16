import logging
import os
import sys
from datetime import datetime

# Configurer le format du logger
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Créer un dictionnaire pour stocker les loggers
loggers = {}

def get_logger(name):
    """
    Récupère un logger configuré pour le module spécifié
    
    Args:
        name (str): Nom du module (généralement __name__)
        
    Returns:
        logging.Logger: Logger configuré
    """
    global loggers
    
    if name in loggers:
        return loggers[name]
    
    # Créer un nouveau logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Créer un handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Définir le format
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)
    
    # Ajouter le handler au logger
    logger.addHandler(console_handler)
    
    # Stocker le logger dans le dictionnaire
    loggers[name] = logger
    
    return logger
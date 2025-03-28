from flask import Flask, request, jsonify
import json
import os
import sys
import signal
import atexit

# Ajouter le répertoire parent au chemin pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.messenger_api import handle_message
from src.utils.logger import get_logger
from src.database import connect_to_database
from src.conversation_memory import clear_old_histories
from src.youtube_api import stop_download_thread

logger = get_logger(__name__)

app = Flask(__name__)

# Connecter à la base de données au démarrage
@app.before_first_request
def before_first_request():
    """
    Initialise les connexions et ressources nécessaires avant la première requête
    """
    logger.info("Initialisation de l'application...")
    
    # Connecter à la base de données
    db = connect_to_database()
    if not db:
        logger.error("Impossible de se connecter à la base de données")
    else:
        logger.info("Connexion à la base de données établie")
    
    # Nettoyer les anciens historiques
    clear_old_histories()
    logger.info("Nettoyage des anciens historiques terminé")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """
    Point d'entrée pour le webhook Facebook Messenger
    """
    if request.method == 'GET':
        # Vérification du webhook par Facebook
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if verify_token == os.environ.get('MESSENGER_VERIFY_TOKEN'):
            logger.info("Vérification du webhook réussie")
            return challenge
        else:
            logger.warning(f"Vérification du webhook échouée: token invalide {verify_token}")
            return 'Invalid verification token'
    
    elif request.method == 'POST':
        # Traitement des messages entrants
        data = request.json
        logger.info(f"Webhook POST reçu: {json.dumps(data)}")
        
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event.get('sender', {}).get('id')
                    
                    if not sender_id:
                        logger.warning("Événement sans sender_id")
                        continue
                    
                    if 'message' in messaging_event:
                        handle_message(sender_id, messaging_event['message'])
                    elif 'postback' in messaging_event:
                        handle_message(sender_id, {'postback': messaging_event['postback']})
        
        return 'EVENT_RECEIVED'

@app.route('/healthz', methods=['GET'])
def health_check():
    """
    Point d'entrée pour la vérification de santé
    """
    # Vérifier la connexion à la base de données
    from src.database import get_database
    db = get_database()
    
    if db is not None:
        return jsonify({"status": "healthy", "database": "connected"})
    else:
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 500

# Gestionnaire de signal pour arrêter proprement les threads
def signal_handler(signum, frame):
    logger.info(f"Signal reçu par l'application: {signum}")
    stop_download_thread()

# Enregistrer les gestionnaires de signal
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Fonction d'arrêt propre
def cleanup():
    logger.info("Nettoyage avant l'arrêt de l'application")
    stop_download_thread()

# Enregistrer la fonction de nettoyage
atexit.register(cleanup)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


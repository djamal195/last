import os
import json
import logging
import atexit
from flask import Flask, request, jsonify
from src.messenger_api import handle_message
from src.utils.logger import get_logger
from src.youtube_api import stop_download_thread

# Configurer le logger
logger = get_logger(__name__)

# Créer l'application Flask
app = Flask(__name__)

# Vérifier si l'application est en mode de développement
DEBUG = os.environ.get('FLASK_ENV') == 'development'

# Variable pour suivre si l'initialisation a été effectuée
app_initialized = False

# Fonction d'initialisation de l'application
def init_app():
    global app_initialized
    if not app_initialized:
        logger.info("Initialisation de l'application...")
        # Ajouter ici toute initialisation nécessaire
        app_initialized = True
        logger.info("Application initialisée avec succès")

# Exécuter l'initialisation au démarrage
init_app()

# Enregistrer la fonction de nettoyage à exécuter lors de l'arrêt de l'application
@atexit.register
def cleanup():
    logger.info("Nettoyage avant l'arrêt de l'application")
    stop_download_thread()

# Route pour la vérification de l'état de l'application
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})

# Route pour le webhook Messenger
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Vérification du webhook par Facebook
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if verify_token == os.environ.get('MESSENGER_VERIFY_TOKEN'):
            logger.info("Vérification du webhook réussie")
            return challenge
        else:
            logger.warning(f"Échec de la vérification du webhook: {verify_token}")
            return 'Vérification du webhook échouée', 403
    
    elif request.method == 'POST':
        # Traitement des messages entrants
        try:
            data = request.json
            logger.info(f"Webhook reçu: {json.dumps(data)}")
            
            if data.get('object') == 'page':
                for entry in data.get('entry', []):
                    for messaging_event in entry.get('messaging', []):
                        sender_id = messaging_event.get('sender', {}).get('id')
                        
                        if sender_id:
                            if 'message' in messaging_event:
                                handle_message(sender_id, messaging_event.get('message', {}))
                            elif 'postback' in messaging_event:
                                handle_message(sender_id, {'postback': messaging_event.get('postback', {})})
            
            return 'OK'
        except Exception as e:
            logger.error(f"Erreur lors du traitement du webhook: {str(e)}")
            logger.error(f"Données reçues: {request.data}")
            return 'Erreur lors du traitement du webhook', 500

# Route pour le test de l'API
@app.route('/', methods=['GET'])
def index():
    return 'API Messenger Bot en ligne!'

# Point d'entrée pour l'exécution directe
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG)


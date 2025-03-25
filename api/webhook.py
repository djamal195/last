from flask import Flask, request, Response
import json
import os
import signal
import atexit
import sys
from src.config import verify_webhook
from src.messenger_api import handle_message
from dotenv import load_dotenv
from src.utils.logger import get_logger

# Importer la fonction pour arrêter proprement le thread de téléchargement
from src.youtube_api import stop_download_thread

# Configurer le logger
logger = get_logger(__name__)

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

@app.route('/api/webhook', methods=['GET'])
def webhook_verification():
    """
    Endpoint pour la vérification du webhook par Facebook
    """
    print("Requête GET reçue pour la vérification du webhook")
    logger.info("Requête GET reçue pour la vérification du webhook")
    return verify_webhook(request)

@app.route('/api/webhook', methods=['POST'])
def webhook_handler():
    """
    Endpoint pour recevoir les événements du webhook
    """
    print("Requête POST reçue du webhook")
    logger.info("Requête POST reçue du webhook")
    data = request.json
    print(f"Corps de la requête: {json.dumps(data)}")
    logger.info(f"Corps de la requête: {json.dumps(data)}")
    
    if data.get('object') == 'page':
        print("Événement de page reçu")
        logger.info("Événement de page reçu")
        for entry in data.get('entry', []):
            print(f"Entrée reçue: {json.dumps(entry)}")
            logger.info(f"Entrée reçue: {json.dumps(entry)}")
            messaging = entry.get('messaging', [])
            if messaging:
                webhook_event = messaging[0]
                print(f"Événement Webhook reçu: {json.dumps(webhook_event)}")
                logger.info(f"Événement Webhook reçu: {json.dumps(webhook_event)}")
                
                sender_id = webhook_event.get('sender', {}).get('id')
                print(f"ID de l'expéditeur: {sender_id}")
                logger.info(f"ID de l'expéditeur: {sender_id}")
                
                if webhook_event.get('message'):
                    print("Message reçu, appel de handle_message")
                    logger.info("Message reçu, appel de handle_message")
                    try:
                        handle_message(sender_id, webhook_event.get('message'))
                        print("handle_message terminé avec succès")
                        logger.info("handle_message terminé avec succès")
                    except Exception as e:
                        print(f"Erreur lors du traitement du message: {str(e)}")
                        logger.error(f"Erreur lors du traitement du message: {str(e)}", exc_info=True)
                elif webhook_event.get('postback'):
                    print(f"Postback reçu: {json.dumps(webhook_event.get('postback'))}")
                    logger.info(f"Postback reçu: {json.dumps(webhook_event.get('postback'))}")
                    try:
                        handle_message(sender_id, {'postback': webhook_event.get('postback')})
                        print("handle_message pour postback terminé avec succès")
                        logger.info("handle_message pour postback terminé avec succès")
                    except Exception as e:
                        print(f"Erreur lors du traitement du postback: {str(e)}")
                        logger.error(f"Erreur lors du traitement du postback: {str(e)}", exc_info=True)
                else:
                    print(f"Événement non reconnu: {webhook_event}")
                    logger.warning(f"Événement non reconnu: {webhook_event}")
            else:
                print("Aucun événement de messagerie dans cette entrée")
                logger.info("Aucun événement de messagerie dans cette entrée")
        
        return Response("EVENT_RECEIVED", status=200)
    else:
        print("Requête non reconnue reçue")
        logger.warning("Requête non reconnue reçue")
        return Response(status=404)

@app.route('/healthz', methods=['GET'])
def health_check():
    """
    Point d'entrée pour la vérification de santé
    """
    logger.info("Vérification de santé demandée")
    return Response("OK", status=200)

@app.errorhandler(Exception)
def handle_error(e):
    print(f"Erreur non gérée: {str(e)}")
    logger.error(f"Erreur non gérée: {str(e)}", exc_info=True)
    return Response("Quelque chose s'est mal passé!", status=500)

# Gestionnaire de signal pour arrêter proprement les threads
def signal_handler(signum, frame):
    print(f"Signal reçu par l'application: {signum}")
    logger.info(f"Signal reçu par l'application: {signum}")
    
    # Arrêter proprement le thread de téléchargement
    stop_download_thread()
    
    # Si c'est un signal de terminaison, quitter l'application
    if signum in (signal.SIGTERM, signal.SIGINT):
        print("Arrêt de l'application demandé")
        logger.info("Arrêt de l'application demandé")
        sys.exit(0)

# Fonction d'arrêt propre
def cleanup():
    print("Nettoyage avant l'arrêt de l'application")
    logger.info("Nettoyage avant l'arrêt de l'application")
    stop_download_thread()

# Enregistrer les gestionnaires de signal
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Enregistrer la fonction de nettoyage
atexit.register(cleanup)

# Pour le déploiement sur Render
if __name__ == '__main__':
    # Initialisation au démarrage
    print("Démarrage de l'application...")
    logger.info("Démarrage de l'application...")
    
    # Démarrer le serveur
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

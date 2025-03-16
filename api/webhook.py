from flask import Flask, request, Response
import json
import os
from src.config import verify_webhook
from src.messenger_api import handle_message
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

@app.route('/api/webhook', methods=['GET'])
def webhook_verification():
    """
    Endpoint pour la vérification du webhook par Facebook
    """
    print("Requête GET reçue pour la vérification du webhook")
    return verify_webhook(request)

@app.route('/api/webhook', methods=['POST'])
def webhook_handler():
    """
    Endpoint pour recevoir les événements du webhook
    """
    print("Requête POST reçue du webhook")
    data = request.json
    print(f"Corps de la requête: {json.dumps(data)}")
    
    if data.get('object') == 'page':
        print("Événement de page reçu")
        for entry in data.get('entry', []):
            print(f"Entrée reçue: {json.dumps(entry)}")
            messaging = entry.get('messaging', [])
            if messaging:
                webhook_event = messaging[0]
                print(f"Événement Webhook reçu: {json.dumps(webhook_event)}")
                
                sender_id = webhook_event.get('sender', {}).get('id')
                print(f"ID de l'expéditeur: {sender_id}")
                
                if webhook_event.get('message'):
                    print("Message reçu, appel de handle_message")
                    try:
                        handle_message(sender_id, webhook_event.get('message'))
                        print("handle_message terminé avec succès")
                    except Exception as e:
                        print(f"Erreur lors du traitement du message: {str(e)}")
                elif webhook_event.get('postback'):
                    print(f"Postback reçu: {json.dumps(webhook_event.get('postback'))}")
                    try:
                        handle_message(sender_id, {'postback': webhook_event.get('postback')})
                        print("handle_message pour postback terminé avec succès")
                    except Exception as e:
                        print(f"Erreur lors du traitement du postback: {str(e)}")
                else:
                    print(f"Événement non reconnu: {webhook_event}")
            else:
                print("Aucun événement de messagerie dans cette entrée")
        
        return Response("EVENT_RECEIVED", status=200)
    else:
        print("Requête non reconnue reçue")
        return Response(status=404)

@app.errorhandler(Exception)
def handle_error(e):
    print(f"Erreur non gérée: {str(e)}")
    return Response("Quelque chose s'est mal passé!", status=500)

# Pour le déploiement sur Render
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
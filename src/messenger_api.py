import os
import json
import requests
import traceback
from typing import Dict, Any, Optional
from src.utils.logger import get_logger
from src.mistral_api import generate_mistral_response
from src.conversation_memory import clear_user_history
from src.youtube_api import search_youtube, download_youtube_video

logger = get_logger(__name__)

# URL de l'API Messenger
MESSENGER_API_URL = "https://graph.facebook.com/v18.0/me/messages"
MESSENGER_ACCESS_TOKEN = os.environ.get('MESSENGER_ACCESS_TOKEN')

# Dictionnaire pour stocker l'état des utilisateurs
user_states = {}

def handle_message(sender_id, message_data):
    """
    Gère les messages reçus des utilisateurs
    """
    logger.info(f"Début de handle_message pour sender_id: {sender_id}")
    logger.info(f"Message reçu: {json.dumps(message_data)}")
    
    try:
        if 'text' in message_data:
            text = message_data['text'].lower()
            
            if text == '/yt':
                user_states[sender_id] = 'youtube'
                send_text_message(sender_id, "Mode YouTube activé. Donnez-moi les mots-clés pour la recherche YouTube.")
            elif text == 'yt/':
                user_states[sender_id] = 'mistral'
                send_text_message(sender_id, "Mode Mistral réactivé. Comment puis-je vous aider ?")
            elif text == '/reset':
                # Commande pour effacer l'historique de conversation
                clear_user_history(sender_id)
                send_text_message(sender_id, "Votre historique de conversation a été effacé. Je ne me souviens plus de nos échanges précédents.")
            elif sender_id in user_states and user_states[sender_id] == 'youtube':
                logger.info(f"Recherche YouTube pour: {message_data['text']}")
                try:
                    videos = search_youtube(message_data['text'])
                    logger.info(f"Résultats de la recherche YouTube: {json.dumps(videos)}")
                    send_youtube_results(sender_id, videos)
                except Exception as e:
                    logger.error(f"Erreur lors de la recherche YouTube: {str(e)}")
                    send_text_message(sender_id, "Désolé, je n'ai pas pu effectuer la recherche YouTube. Veuillez réessayer plus tard.")
            else:
                logger.info("Génération de la réponse Mistral...")
                # Passer l'ID de l'utilisateur pour récupérer l'historique
                response = generate_mistral_response(message_data['text'], sender_id)
                logger.info(f"Réponse Mistral générée: {response}")
                send_text_message(sender_id, response)
            
            logger.info("Message envoyé avec succès")
        elif 'postback' in message_data:
            logger.info(f"Traitement du postback: {json.dumps(message_data['postback'])}")
            try:
                payload = json.loads(message_data['postback']['payload'])
                logger.info(f"Payload du postback: {json.dumps(payload)}")
                
                if payload.get('action') == 'watch_video':
                    logger.info(f"Action watch_video détectée pour videoId: {payload.get('videoId')}")
                    handle_watch_video(sender_id, payload.get('videoId'), payload.get('title', 'Vidéo YouTube'))
                else:
                    logger.info(f"Action de postback non reconnue: {payload.get('action')}")
            except Exception as e:
                logger.error(f"Erreur lors du traitement du postback: {str(e)}")
                send_text_message(sender_id, "Désolé, je n'ai pas pu traiter votre demande. Veuillez réessayer plus tard.")
        else:
            logger.info("Message reçu sans texte")
            send_text_message(sender_id, "Désolé, je ne peux traiter que des messages texte.")
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_message = "Désolé, j'ai rencontré une erreur en traitant votre message. Veuillez réessayer plus tard."
        if "timeout" in str(e):
            error_message = "Désolé, la génération de la réponse a pris trop de temps. Veuillez réessayer avec une question plus courte ou plus simple."
        send_text_message(sender_id, error_message)
    
    logger.info("Fin de handle_message")

def send_youtube_results(recipient_id, videos):
    """
    Envoie les résultats de recherche YouTube sous forme de carrousel
    """
    elements = []
    for video in videos:
        elements.append({
            "title": video['title'],
            "image_url": video['thumbnail'],
            "buttons": [
                {
                    "type": "web_url",
                    "url": f"https://www.youtube.com/watch?v={video['videoId']}",
                    "title": "Regarder sur YouTube"
                },
                {
                    "type": "postback",
                    "title": "Télécharger et envoyer",
                    "payload": json.dumps({
                        "action": "watch_video",
                        "videoId": video['videoId'],
                        "title": video['title']
                    })
                }
            ]
        })
    
    message_data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements
                }
            }
        }
    }
    
    call_send_api(message_data)

def handle_watch_video(recipient_id, video_id, title):
    """
    Télécharge et envoie la vidéo YouTube
    """
    try:
        # Informer l'utilisateur que le téléchargement est en cours
        send_text_message(recipient_id, "Téléchargement de la vidéo en cours... Cela peut prendre quelques instants.")
        
        # Télécharger la vidéo
        video_path_or_url = download_youtube_video(video_id)
        
        if not video_path_or_url:
            send_text_message(recipient_id, "Désolé, je n'ai pas pu télécharger cette vidéo. Veuillez réessayer plus tard.")
            return
        
        # Vérifier si c'est une URL YouTube (solution de secours)
        if video_path_or_url.startswith("https://www.youtube.com"):
            send_text_message(recipient_id, f"En raison des limitations de YouTube, je ne peux pas télécharger la vidéo pour le moment. Voici le lien direct: {video_path_or_url}")
            return
        
        # Si c'est un chemin de fichier, envoyer la vidéo
        if os.path.exists(video_path_or_url):
            # Ici, vous devriez implémenter la logique pour envoyer le fichier vidéo
            # Par exemple, télécharger sur un service de stockage et obtenir une URL
            send_text_message(recipient_id, f"Vidéo téléchargée avec succès! Voici le chemin: {video_path_or_url}")
        else:
            send_text_message(recipient_id, "Désolé, je n'ai pas pu traiter cette vidéo. Veuillez réessayer plus tard.")
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la vidéo: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        send_text_message(recipient_id, "Désolé, je n'ai pas pu traiter cette vidéo. Veuillez réessayer plus tard.")

def send_text_message(recipient_id, message_text):
    """
    Envoie un message texte à l'utilisateur
    """
    logger.info(f"Début de send_text_message pour recipient_id: {recipient_id}")
    
    # Diviser le message en chunks de 2000 caractères maximum
    chunks = [message_text[i:i+2000] for i in range(0, len(message_text), 2000)]
    
    for chunk in chunks:
        message_data = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": chunk
            }
        }
        
        call_send_api(message_data)
    
    logger.info("Fin de send_text_message")

def call_send_api(message_data):
    """
    Appelle l'API Send de Facebook pour envoyer des messages
    """
    if not MESSENGER_ACCESS_TOKEN:
        logger.error("Token d'accès Messenger manquant")
        # Pour le développement, simuler un envoi réussi même sans token
        return {"recipient_id": message_data["recipient"]["id"], "message_id": "fake_id"}
    
    url = f"https://graph.facebook.com/v13.0/me/messages?access_token={MESSENGER_ACCESS_TOKEN}"
    
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=message_data
        )
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'appel à l'API Send: {response.status_code} - {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'appel à l'API Facebook: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


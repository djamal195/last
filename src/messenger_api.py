import json
import requests
import tempfile
import os
from src.config import MESSENGER_PAGE_ACCESS_TOKEN
from src.mistral_api import generate_mistral_response
from src.youtube_api import search_youtube, download_youtube_video
from src.database import connect_to_database, get_database
from src.models.video import Video
from src.cloudinary_service import upload_file
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Dictionnaire pour stocker l'état des utilisateurs
user_states = {}

def handle_message(sender_id, received_message):
    """
    Gère les messages reçus des utilisateurs
    """
    logger.info(f"Début de handle_message pour sender_id: {sender_id}")
    logger.info(f"Message reçu: {json.dumps(received_message)}")
    
    try:
        if 'text' in received_message:
            text = received_message['text'].lower()
            
            if text == '/yt':
                user_states[sender_id] = 'youtube'
                send_text_message(sender_id, "Mode YouTube activé. Donnez-moi les mots-clés pour la recherche YouTube.")
            elif text == 'yt/':
                user_states[sender_id] = 'mistral'
                send_text_message(sender_id, "Mode Mistral réactivé. Comment puis-je vous aider ?")
            elif sender_id in user_states and user_states[sender_id] == 'youtube':
                logger.info(f"Recherche YouTube pour: {received_message['text']}")
                try:
                    videos = search_youtube(received_message['text'])
                    logger.info(f"Résultats de la recherche YouTube: {json.dumps(videos)}")
                    send_youtube_results(sender_id, videos)
                except Exception as e:
                    logger.error(f"Erreur lors de la recherche YouTube: {str(e)}")
                    send_text_message(sender_id, "Désolé, je n'ai pas pu effectuer la recherche YouTube. Veuillez réessayer plus tard.")
            else:
                logger.info("Génération de la réponse Mistral...")
                response = generate_mistral_response(received_message['text'])
                logger.info(f"Réponse Mistral générée: {response}")
                send_text_message(sender_id, response)
            
            logger.info("Message envoyé avec succès")
        elif 'postback' in received_message:
            logger.info(f"Traitement du postback: {json.dumps(received_message['postback'])}")
            try:
                payload = json.loads(received_message['postback']['payload'])
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
        # Vérifier si la vidéo existe déjà dans la base de données
        db = get_database()
        existing_video = Video.find_by_video_id(video_id)
        
        if existing_video and existing_video.get('cloudinary_url'):
            logger.info(f"Vidéo trouvée dans la base de données: {video_id}")
            send_text_message(recipient_id, f"Voici votre vidéo : {title}")
            send_video_message(recipient_id, existing_video.get('cloudinary_url'))
            return
        
        # Informer l'utilisateur que le téléchargement est en cours
        send_text_message(recipient_id, "Téléchargement de la vidéo en cours... Cela peut prendre quelques instants.")
        
        # Télécharger la vidéo
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                video_path = download_youtube_video(video_id, temp_dir)
                
                if not video_path or not os.path.exists(video_path):
                    raise Exception("Échec du téléchargement de la vidéo")
                
                # Télécharger la vidéo sur Cloudinary
                upload_result = upload_file(video_path, f"youtube_{video_id}", "video")
                cloudinary_url = upload_result.get('secure_url')
                
                if not cloudinary_url:
                    raise Exception("Échec du téléchargement sur Cloudinary")
                
                # Sauvegarder dans la base de données
                video = Video(
                    video_id=video_id,
                    title=title,
                    cloudinary_url=cloudinary_url,
                    thumbnail=f"https://img.youtube.com/vi/{video_id}/default.jpg"
                )
                video.save()
                
                # Envoyer la vidéo
                send_text_message(recipient_id, f"Voici votre vidéo : {title}")
                send_video_message(recipient_id, cloudinary_url)
                
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement/envoi de la vidéo: {str(e)}")
                # Envoyer le lien YouTube comme solution de secours
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                send_text_message(recipient_id, f"Désolé, je n'ai pas pu télécharger la vidéo. Voici le lien YouTube : {video_url}")
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la vidéo: {str(e)}")
        send_text_message(recipient_id, "Désolé, je n'ai pas pu traiter cette vidéo. Veuillez réessayer plus tard.")

def send_video_message(recipient_id, video_url):
    """
    Envoie un message vidéo à l'utilisateur
    """
    message_data = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "attachment": {
                "type": "video",
                "payload": {
                    "url": video_url,
                    "is_reusable": True
                }
            }
        }
    }
    
    call_send_api(message_data)

def send_text_message(recipient_id, message_text):
    """
    Envoie un message texte à l'utilisateur
    """
    logger.info(f"Début de send_text_message pour recipient_id: {recipient_id}")
    logger.info(f"Message à envoyer: {message_text}")
    
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
        
        try:
            call_send_api(message_data)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message: {str(e)}")
            raise e
    
    logger.info("Fin de send_text_message")

def call_send_api(message_data):
    """
    Appelle l'API Send de Facebook pour envoyer des messages
    """
    logger.info(f"Début de call_send_api avec message_data: {json.dumps(message_data)}")
    url = f"https://graph.facebook.com/v13.0/me/messages?access_token={MESSENGER_PAGE_ACCESS_TOKEN}"
    
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=message_data
        )
        
        logger.info(f"Réponse reçue de l'API Facebook. Status: {response.status_code}")
        
        response_body = response.json()
        logger.info(f"Réponse de l'API Facebook: {json.dumps(response_body)}")
        
        if 'error' in response_body:
            logger.error(f"Erreur lors de l'appel à l'API Send: {response_body['error']}")
            raise Exception(response_body['error']['message'])
        
        logger.info("Message envoyé avec succès")
        return response_body
    except Exception as e:
        logger.error(f"Erreur lors de l'appel à l'API Facebook: {str(e)}")
        raise e

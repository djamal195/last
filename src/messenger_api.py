import os
import json
import requests
import traceback
import tempfile
from typing import Dict, Any, Optional
from src.utils.logger import get_logger
from src.mistral_api import generate_mistral_response
from src.conversation_memory import clear_user_history
from src.youtube_api import search_youtube, download_youtube_video
from src.cloudinary_service import upload_file

logger = get_logger(__name__)

# URL de l'API Messenger
MESSENGER_API_URL = "https://graph.facebook.com/v18.0/me/messages"

# Récupérer le token d'accès avec plusieurs noms possibles pour plus de robustesse
MESSENGER_ACCESS_TOKEN = os.environ.get('MESSENGER_ACCESS_TOKEN') or os.environ.get('MESSENGER_PAGE_ACCESS_TOKEN')

# Journaliser l'état du token au démarrage
if MESSENGER_ACCESS_TOKEN:
    logger.info("Token d'accès Messenger trouvé")
else:
    logger.warning("Token d'accès Messenger manquant. Vérifiez les variables d'environnement MESSENGER_ACCESS_TOKEN ou MESSENGER_PAGE_ACCESS_TOKEN")

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
    if not videos:
        send_text_message(recipient_id, "Désolé, je n'ai pas trouvé de vidéos correspondant à votre recherche.")
        return
        
    elements = []
    for video in videos[:10]:  # Limiter à 10 vidéos maximum (limite de Messenger)
        if not video.get('videoId') or not video.get('title'):
            continue
            
        element = {
            "title": video.get('title', 'Vidéo YouTube')[:80],  # Limiter la longueur du titre
            "subtitle": video.get('description', '')[:80] if video.get('description') else '',
            "image_url": video.get('thumbnail', f"https://img.youtube.com/vi/{video.get('videoId')}/hqdefault.jpg"),
            "buttons": [
                {
                    "type": "web_url",
                    "url": f"https://www.youtube.com/watch?v={video.get('videoId')}",
                    "title": "Regarder sur YouTube"
                },
                {
                    "type": "postback",
                    "title": "Télécharger et envoyer",
                    "payload": json.dumps({
                        "action": "watch_video",
                        "videoId": video.get('videoId'),
                        "title": video.get('title', 'Vidéo YouTube')
                    })
                }
            ]
        }
        elements.append(element)
    
    if not elements:
        send_text_message(recipient_id, "Désolé, je n'ai pas pu traiter les résultats de recherche.")
        return
    
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
        # Vérifier si le video_id est valide
        if not video_id:
            send_text_message(recipient_id, "Désolé, l'identifiant de la vidéo est invalide.")
            return
            
        # Informer l'utilisateur que le téléchargement est en cours
        send_text_message(recipient_id, "Téléchargement de la vidéo en cours... Cela peut prendre quelques instants.")
        
        # Vérifier d'abord dans la base de données MongoDB si la vidéo a déjà été téléchargée
        from src.database import get_database
        db = get_database()
        
        if db is not None:
            # Vérifier si la vidéo existe déjà
            video_collection = db.videos
            existing_video = video_collection.find_one({"video_id": video_id})
            
            if existing_video and existing_video.get('cloudinary_url'):
                logger.info(f"Vidéo trouvée dans la base de données: {video_id}")
                send_text_message(recipient_id, f"Voici votre vidéo : {title}")
                send_video_message(recipient_id, existing_video.get('cloudinary_url'))
                return
        
        # Télécharger la vidéo dans un répertoire temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, f"{video_id}.mp4")
            video_path = download_youtube_video(video_id, temp_file)
            
            if not video_path:
                send_text_message(recipient_id, "Désolé, je n'ai pas pu télécharger cette vidéo. Veuillez réessayer plus tard.")
                return
            
            # Vérifier si c'est une URL YouTube (solution de secours)
            if isinstance(video_path, str) and video_path.startswith("https://www.youtube.com"):
                send_text_message(recipient_id, f"En raison des limitations de YouTube, je ne peux pas télécharger la vidéo pour le moment. Voici le lien direct: {video_path}")
                return
            
            # Si c'est un chemin de fichier, vérifier qu'il existe
            if not os.path.exists(video_path):
                send_text_message(recipient_id, "Désolé, le téléchargement de la vidéo a échoué.")
                return
                
            logger.info(f"Vidéo téléchargée avec succès: {video_path}")
            
            # Télécharger la vidéo sur Cloudinary pour obtenir une URL publique
            try:
                cloudinary_result = upload_file(video_path, f"youtube_{video_id}", "video")
                
                if not cloudinary_result or not cloudinary_result.get('secure_url'):
                    raise Exception("Échec du téléchargement sur Cloudinary")
                    
                video_url = cloudinary_result.get('secure_url')
                logger.info(f"Vidéo téléchargée sur Cloudinary: {video_url}")
                
                # Sauvegarder l'URL dans la base de données pour une utilisation future
                if db is not None:
                    video_collection = db.videos
                    video_collection.update_one(
                        {"video_id": video_id},
                        {"$set": {
                            "video_id": video_id,
                            "title": title,
                            "cloudinary_url": video_url,
                            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                            "created_at": time.time()
                        }},
                        upsert=True
                    )
                    logger.info(f"Vidéo sauvegardée dans la base de données: {video_id}")
                
                # Envoyer la vidéo à l'utilisateur
                send_text_message(recipient_id, f"Voici votre vidéo : {title}")
                send_video_message(recipient_id, video_url)
                
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Essayer d'envoyer directement le fichier si Cloudinary échoue
                try:
                    send_text_message(recipient_id, f"Voici votre vidéo : {title}")
                    send_file_attachment(recipient_id, video_path, "video")
                except Exception as file_error:
                    logger.error(f"Erreur lors de l'envoi direct du fichier: {str(file_error)}")
                    send_text_message(recipient_id, f"Désolé, je n'ai pas pu envoyer la vidéo. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(recipient_id, "Désolé, je n'ai pas pu traiter cette vidéo. Veuillez réessayer plus tard.")

def send_video_message(recipient_id, video_url):
    """
    Envoie un message vidéo à l'utilisateur
    """
    logger.info(f"Envoi de la vidéo à {recipient_id}: {video_url}")
    
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
    
    response = call_send_api(message_data)
    logger.info(f"Réponse de l'API pour l'envoi de vidéo: {json.dumps(response) if response else 'None'}")

def send_file_attachment(recipient_id, file_path, attachment_type):
    """
    Envoie un fichier en pièce jointe à l'utilisateur
    
    Args:
        recipient_id: ID du destinataire
        file_path: Chemin du fichier à envoyer
        attachment_type: Type de pièce jointe (image, video, audio, file)
    """
    logger.info(f"Envoi du fichier {file_path} à {recipient_id}")
    
    if not os.path.exists(file_path):
        logger.error(f"Le fichier n'existe pas: {file_path}")
        return None
    
    url = f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}"
    
    # Préparer les données multipart
    payload = {
        'recipient': json.dumps({
            'id': recipient_id
        }),
        'message': json.dumps({
            'attachment': {
                'type': attachment_type,
                'payload': {}
            }
        })
    }
    
    files = {
        'filedata': (os.path.basename(file_path), open(file_path, 'rb'), f'application/{attachment_type}')
    }
    
    try:
        response = requests.post(url, data=payload, files=files)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi du fichier: {response.status_code} - {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du fichier: {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        # Fermer le fichier
        files['filedata'][1].close()

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
    
    url = f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}"
    
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


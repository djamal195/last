import os
import json
import requests
import traceback
import tempfile
import time
import shutil
import subprocess
from typing import Dict, Any, Optional
from src.utils.logger import get_logger
from src.mistral_api import generate_mistral_response
from src.conversation_memory import clear_user_history
from src.youtube_api import search_youtube, download_youtube_video
from src.cloudinary_service import upload_file, delete_file
from src.dalle_api import generate_image, save_generated_image, generate_and_upload_image
from src.imdb_api import search_imdb, get_imdb_details
from src.google_sheets_api import add_imdb_request_to_sheet, get_imdb_requests

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

def send_text_message(recipient_id, text):
    """
    Envoie un message texte à un utilisateur
    
    Args:
        recipient_id: ID du destinataire
        text: Texte du message
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info(f"Envoi d'un message texte à {recipient_id}: {text[:50]}...")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text}
        }
        
        response = requests.post(
            f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi du message: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Message envoyé avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def send_image_message(recipient_id, image_url):
    """
    Envoie une image à un utilisateur
    
    Args:
        recipient_id: ID du destinataire
        image_url: URL de l'image
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info(f"Envoi d'une image à {recipient_id}: {image_url}")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {
                        "url": image_url,
                        "is_reusable": True
                    }
                }
            }
        }
        
        response = requests.post(
            f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi de l'image: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Image envoyée avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def send_video_message(recipient_id, video_url):
    """
    Envoie une vidéo à un utilisateur
    
    Args:
        recipient_id: ID du destinataire
        video_url: URL de la vidéo
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info(f"Envoi d'une vidéo à {recipient_id}: {video_url}")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        payload = {
            "recipient": {"id": recipient_id},
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
        
        response = requests.post(
            f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi de la vidéo: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Vidéo envoyée avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de la vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def send_file_attachment(recipient_id, file_path, attachment_type="file"):
    """
    Envoie un fichier à un utilisateur
    
    Args:
        recipient_id: ID du destinataire
        file_path: Chemin du fichier à envoyer
        attachment_type: Type de pièce jointe (file, image, video, audio)
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info(f"Envoi d'un fichier à {recipient_id}: {file_path}")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            logger.error(f"Le fichier n'existe pas: {file_path}")
            return None
        
        # Déterminer le type MIME
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if not mime_type:
            # Si le type MIME ne peut pas être déterminé, essayer de le deviner à partir de l'extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.mp4', '.mov', '.avi', '.wmv', '.flv']:
                mime_type = f"video/{ext[1:]}"
                attachment_type = "video"
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                mime_type = f"image/{ext[1:]}"
                attachment_type = "image"
            elif ext in ['.mp3', '.wav', '.ogg', '.m4a']:
                mime_type = f"audio/{ext[1:]}"
                attachment_type = "audio"
            else:
                mime_type = "application/octet-stream"
                attachment_type = "file"
        
        # Préparer les données multipart
        url = f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}"
        
        payload = {
            "recipient": json.dumps({"id": recipient_id}),
            "message": json.dumps({
                "attachment": {
                    "type": attachment_type,
                    "payload": {
                        "is_reusable": True
                    }
                }
            })
        }
        
        files = {
            "filedata": (os.path.basename(file_path), open(file_path, "rb"), mime_type)
        }
        
        # Envoyer la requête
        response = requests.post(url, data=payload, files=files)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi du fichier: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Fichier envoyé avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du fichier: {str(e)}")
        logger.error(traceback.format_exc())
        return None

# Dictionnaire pour stocker l'état des utilisateurs
user_states = {}

# Dictionnaire pour stocker les téléchargements en cours
pending_downloads = {}

# Dictionnaire pour stocker les générations d'images en cours
pending_images = {}

# Dictionnaire pour stocker les recherches IMDb en cours
imdb_searches = {}

def setup_persistent_menu():
    """
    Configure le menu persistant pour le bot Messenger
    
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info("Configuration du menu persistant")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        url = f"https://graph.facebook.com/v18.0/me/messenger_profile?access_token={MESSENGER_ACCESS_TOKEN}"
        
        # Définir le menu persistant
        payload = {
            "persistent_menu": [
                {
                    "locale": "default",
                    "composer_input_disabled": False,
                    "call_to_actions": [
                        {
                            "type": "postback",
                            "title": "🎬 Mode YouTube",
                            "payload": json.dumps({"action": "mode_youtube"})
                        },
                        {
                            "type": "postback",
                            "title": "🧠 Mode Mistral",
                            "payload": json.dumps({"action": "mode_mistral"})
                        },
                        {
                            "type": "postback",
                            "title": "🎥 Demander un film",
                            "payload": json.dumps({"action": "request_movie"})
                        },
                        {
                            "type": "postback",
                            "title": "🔄 Reset conversation",
                            "payload": json.dumps({"action": "reset_conversation"})
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la configuration du menu persistant: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Menu persistant configuré avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de la configuration du menu persistant: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def handle_message(sender_id, message_data):
    """
    Gère les messages reçus des utilisateurs
    """
    logger.info(f"Début de handle_message pour sender_id: {sender_id}")
    logger.info(f"Message reçu: {json.dumps(message_data)}")
    
    try:
        if 'text' in message_data:
            text = message_data['text'].lower()
            
            # Vérifier si l'utilisateur est en mode recherche IMDb
            if sender_id in user_states and user_states[sender_id] == 'imdb_search':
                # L'utilisateur a envoyé un titre de film ou série
                handle_imdb_search(sender_id, message_data['text'])
                return
            
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
            elif text == '/stream' or text.startswith('/stream '):
                # Commande pour rechercher un film ou une série
                handle_stream_command(sender_id, text)
            elif text.startswith('/retry '):
                # Commande pour réessayer le téléchargement d'une vidéo
                video_id = text.split(' ')[1].strip()
                if video_id:
                    logger.info(f"Commande de réessai pour la vidéo: {video_id}")
                    # Supprimer l'entrée de la base de données
                    delete_video_from_db(video_id)
                    # Récupérer les détails de la vidéo
                    from src.youtube_api import get_video_details
                    video_details = get_video_details(video_id)
                    if video_details:
                        title = video_details.get('title', 'Vidéo YouTube')
                        handle_watch_video(sender_id, video_id, title, force_download=True)
                    else:
                        send_text_message(sender_id, f"Désolé, je n'ai pas pu récupérer les détails de la vidéo {video_id}.")
                else:
                    send_text_message(sender_id, "Format incorrect. Utilisez /retry VIDEO_ID")
            elif text.startswith('/img '):
                # Commande pour générer une image avec DALL-E
                prompt = message_data['text'][5:].strip()  # Extraire le prompt après "/img "
                if prompt:
                    logger.info(f"Génération d'image pour le prompt: {prompt}")
                    send_text_message(sender_id, f"Génération de l'image en cours pour: {prompt}. Cela peut prendre quelques instants...")
                    
                    # Vérifier si une génération est déjà en cours pour cet utilisateur
                    if sender_id in pending_images and pending_images[sender_id]:
                        send_text_message(sender_id, "Une génération d'image est déjà en cours. Veuillez patienter.")
                        return
                    
                    # Marquer la génération comme en cours
                    if sender_id not in pending_images:
                        pending_images[sender_id] = {}
                    pending_images[sender_id] = True
                    
                    # Créer une fonction de callback pour la génération d'image
                    def image_callback(result):
                        handle_image_callback(sender_id, prompt, result)
                    
                    # Ajouter la génération à la file d'attente
                    generate_and_upload_image(prompt, image_callback)
                else:
                    send_text_message(sender_id, "Veuillez fournir une description pour l'image. Exemple: /img un chat jouant du piano")
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
                elif payload.get('action') == 'activate_youtube' or payload.get('action') == 'mode_youtube':
                    user_states[sender_id] = 'youtube'
                    send_text_message(sender_id, "Mode YouTube activé. Donnez-moi les mots-clés pour la recherche YouTube.")
                elif payload.get('action') == 'activate_mistral' or payload.get('action') == 'mode_mistral':
                    user_states[sender_id] = 'mistral'
                    send_text_message(sender_id, "Mode Mistral activé. Comment puis-je vous aider ?")
                elif payload.get('action') == 'generate_image':
                    send_text_message(sender_id, "Pour générer une image, envoyez une commande comme: /img un chat jouant du piano")
                elif payload.get('action') == 'request_movie':
                    # Action pour demander un film ou une série
                    handle_stream_command(sender_id, "/stream")
                elif payload.get('action') == 'select_imdb':
                    # Action pour sélectionner un résultat IMDb
                    handle_imdb_selection(sender_id, payload.get('imdb_id'), payload.get('title'), payload.get('type'))
                elif payload.get('action') == 'reset_conversation':
                    clear_user_history(sender_id)
                    send_text_message(sender_id, "Votre historique de conversation a été effacé. Je ne me souviens plus de nos échanges précédents.")
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

def handle_stream_command(sender_id, text):
    """
    Gère la commande /stream pour rechercher un film ou une série
    
    Args:
        sender_id: ID de l'utilisateur
        text: Texte de la commande
    """
    try:
        logger.info(f"Traitement de la commande stream pour {sender_id}: {text}")
        
        # Extraire le titre si fourni directement avec la commande
        query = None
        if text.startswith('/stream '):
            query = text[8:].strip()
        
        if query:
            # Si un titre est fourni directement, lancer la recherche
            handle_imdb_search(sender_id, query)
        else:
            # Sinon, demander le titre
            user_states[sender_id] = 'imdb_search'
            send_text_message(sender_id, "Quel est le titre du film ou de la série que tu veux voir ?")
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la commande stream: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu traiter votre demande. Veuillez réessayer plus tard.")

def handle_imdb_search(sender_id, query):
    """
    Gère la recherche IMDb
    
    Args:
        sender_id: ID de l'utilisateur
        query: Terme de recherche
    """
    try:
        logger.info(f"Recherche IMDb pour {sender_id}: {query}")
        
        # Réinitialiser l'état de l'utilisateur
        user_states[sender_id] = 'mistral'
        
        # Rechercher sur IMDb
        results = search_imdb(query)
        
        if not results:
            send_text_message(sender_id, "Désolé, je n'ai pas trouvé de résultats pour votre recherche. Veuillez essayer avec un autre titre.")
            return
        
        # Stocker les résultats pour cet utilisateur
        imdb_searches[sender_id] = results
        
        # Envoyer un message de confirmation
        send_text_message(sender_id, f"J'ai trouvé {len(results)} résultats pour '{query}'. Voici les meilleurs résultats :")
        
        # Envoyer les résultats un par un
        for result in results:
            # Créer le message avec l'image et le bouton
            title = result.get('title', 'Titre inconnu')
            if result.get('year'):
                title += f" ({result.get('year')})"
            
            # Déterminer le texte du bouton en fonction du type
            button_text = "Ce film 🎬" if result.get('type') == "film" else "Cette série 📺"
            
            # Créer le message avec l'image et le bouton
            message = {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": [
                            {
                                "title": title,
                                "image_url": result.get('image_url', ''),
                                "subtitle": result.get('stars', ''),
                                "buttons": [
                                    {
                                        "type": "postback",
                                        "title": button_text,
                                        "payload": json.dumps({
                                            "action": "select_imdb",
                                            "imdb_id": result.get('imdb_id', ''),
                                            "title": result.get('title', ''),
                                            "type": result.get('type', '')
                                        })
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
            
            # Envoyer le message
            payload = {
                "recipient": {"id": sender_id},
                "message": message
            }
            
            response = requests.post(
                f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Erreur lors de l'envoi du résultat IMDb: {response.status_code} - {response.text}")
            else:
                logger.info(f"Résultat IMDb envoyé avec succès: {response.json()}")
    except Exception as e:
        logger.error(f"Erreur lors de la recherche IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu effectuer la recherche. Veuillez réessayer plus tard.")

def handle_imdb_selection(sender_id, imdb_id, title, item_type):
    """
    Gère la sélection d'un résultat IMDb
    
    Args:
        sender_id: ID de l'utilisateur
        imdb_id: ID IMDb du film ou de la série
        title: Titre du film ou de la série
        item_type: Type (film ou série)
    """
    try:
        logger.info(f"Sélection IMDb pour {sender_id}: {imdb_id} - {title} ({item_type})")
        
        # Récupérer les détails complets
        imdb_data = None
        
        # Chercher dans les résultats stockés
        if sender_id in imdb_searches:
            for result in imdb_searches[sender_id]:
                if result.get('imdb_id') == imdb_id:
                    imdb_data = result
                    break
        
        # Si non trouvé, récupérer les détails via l'API
        if not imdb_data:
            imdb_data = get_imdb_details(imdb_id)
        
        if not imdb_data:
            send_text_message(sender_id, "Désolé, je n'ai pas pu récupérer les détails de votre sélection. Veuillez réessayer plus tard.")
            return
        
        # Ajouter la demande à Google Sheets
        user_name = "Utilisateur"  # Idéalement, récupérer le nom de l'utilisateur via l'API Messenger
        success = add_imdb_request_to_sheet(sender_id, user_name, imdb_data)
        
        # Envoyer un message de confirmation
        if success:
            send_text_message(sender_id, f"✅ Merci ! Ta demande pour '{title}' a bien été reçue.\nElle sera ajoutée sur Jekle dans les prochaines heures 👌")
        else:
            send_text_message(sender_id, f"✅ Merci ! Ta demande pour '{title}' a bien été reçue, mais je n'ai pas pu l'enregistrer dans la base de données. L'équipe sera informée manuellement.")
    except Exception as e:
        logger.error(f"Erreur lors de la sélection IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu traiter votre sélection. Veuillez réessayer plus tard.")

def handle_image_callback(sender_id, prompt, result):
    """
    Callback pour la génération d'image
    
    Args:
        sender_id: ID du destinataire
        prompt: Texte décrivant l'image
        result: Résultat de la génération (chemin du fichier ou URL)
    """
    logger.info(f"Callback de génération d'image pour {sender_id}, prompt: {prompt}")
    
    try:
        # Supprimer la génération en cours
        if sender_id in pending_images:
            pending_images[sender_id] = False
        
        # Si le résultat est None, envoyer un message d'erreur
        if result is None:
            send_text_message(sender_id, "Désolé, je n'ai pas pu générer l'image. Veuillez réessayer plus tard.")
            return
        
        # Si le résultat est un chemin de fichier, vérifier qu'il existe
        if not os.path.exists(result):
            send_text_message(sender_id, "Désolé, je n'ai pas pu générer l'image. Veuillez réessayer plus tard.")
            return
        
        logger.info(f"Image générée avec succès: {result}")
        
        # Essayer d'envoyer directement le fichier
        try:
            logger.info(f"Tentative d'envoi direct du fichier: {result}")
            send_text_message(sender_id, "Voici l'image générée:")
            send_file_attachment(sender_id, result, "image")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi direct du fichier: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Si l'envoi direct échoue, essayer Cloudinary
            try:
                logger.info(f"Tentative de téléchargement sur Cloudinary: {result}")
                
                # Vérifier que le fichier existe et a une taille non nulle
                if not os.path.exists(result) or os.path.getsize(result) == 0:
                    logger.error(f"Fichier invalide pour Cloudinary: {result}, taille: {os.path.getsize(result) if os.path.exists(result) else 'N/A'}")
                    raise Exception(f"Fichier invalide pour Cloudinary: {result}")
                
                # Télécharger sur Cloudinary
                image_id = f"dalle_{int(time.time())}"
                cloudinary_result = upload_file(result, image_id, "image")
                
                if not cloudinary_result or not cloudinary_result.get('secure_url'):
                    logger.error("Échec du téléchargement sur Cloudinary")
                    raise Exception("Échec du téléchargement sur Cloudinary")
                    
                image_url = cloudinary_result.get('secure_url')
                logger.info(f"Image téléchargée sur Cloudinary: {image_url}")
                
                # Envoyer l'image à l'utilisateur
                send_text_message(sender_id, "Voici l'image générée:")
                send_image_message(sender_id, image_url)
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Envoyer un message d'erreur
                send_text_message(sender_id, "Désolé, je n'ai pas pu envoyer l'image générée. Veuillez réessayer plus tard.")
        
        # Nettoyer le répertoire temporaire
        try:
            if os.path.exists(result):
                os.remove(result)
                logger.info(f"Fichier temporaire nettoyé : {result}")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du fichier temporaire: {str(e)}")
            
    except Exception as e:
        logger.error(f"Erreur dans le callback de génération d'image: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu traiter l'image générée. Veuillez réessayer plus tard.")

def handle_watch_video(sender_id, video_id, title, force_download=False):
    """
    Gère la demande de téléchargement d'une vidéo YouTube
    
    Args:
        sender_id: ID du destinataire
        video_id: ID de la vidéo YouTube
        title: Titre de la vidéo
        force_download: Force le téléchargement même si la vidéo existe déjà
    """
    try:
        logger.info(f"Demande de téléchargement de la vidéo {video_id} par {sender_id}")
        
        # Vérifier si l'ID est valide
        if not video_id:
            send_text_message(sender_id, "Désolé, l'ID de la vidéo est invalide.")
            return
        
        # Informer l'utilisateur que le téléchargement est en cours
        send_text_message(sender_id, f"Je télécharge la vidéo '{title}'. Cela peut prendre quelques instants...")
        
        # Créer un répertoire temporaire pour la vidéo
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        # Vérifier si un téléchargement est déjà en cours pour cet utilisateur
        if sender_id in pending_downloads and pending_downloads[sender_id]:
            send_text_message(sender_id, "Un téléchargement est déjà en cours. Veuillez patienter.")
            return
        
        # Marquer le téléchargement comme en cours
        if sender_id not in pending_downloads:
            pending_downloads[sender_id] = {}
        pending_downloads[sender_id] = True
        
        # Créer une fonction de callback pour le téléchargement
        def download_callback(result):
            handle_download_callback(sender_id, video_id, title, result)
        
        # Ajouter le téléchargement à la file d'attente
        download_youtube_video(video_id, output_path, download_callback)
        
    except Exception as e:
        logger.error(f"Erreur lors de la gestion de la demande de téléchargement: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu télécharger la vidéo. Veuillez réessayer plus tard.")

def handle_download_callback(sender_id, video_id, title, result):
    """
    Callback pour le téléchargement d'une vidéo
    
    Args:
        sender_id: ID du destinataire
        video_id: ID de la vidéo YouTube
        title: Titre de la vidéo
        result: Résultat du téléchargement (chemin du fichier ou URL)
    """
    try:
        logger.info(f"Callback de téléchargement pour {sender_id}, vidéo: {video_id}")
        
        # Supprimer le téléchargement en cours
        if sender_id in pending_downloads:
            pending_downloads[sender_id] = False
        
        # Si le résultat est None, envoyer un message d'erreur
        if result is None:
            send_text_message(sender_id, "Désolé, je n'ai pas pu télécharger la vidéo. Veuillez réessayer plus tard.")
            return
        
        # Si le résultat est une URL YouTube, c'est que le téléchargement a échoué
        if result.startswith("https://www.youtube.com/watch"):
            send_text_message(sender_id, f"Désolé, je n'ai pas pu télécharger la vidéo. Vous pouvez la regarder directement sur YouTube: {result}")
            return
        
        # Si le résultat est un chemin de fichier, vérifier qu'il existe
        if not os.path.exists(result):
            send_text_message(sender_id, "Désolé, je n'ai pas pu télécharger la vidéo. Veuillez réessayer plus tard.")
            return
        
        logger.info(f"Vidéo téléchargée avec succès: {result}")
        
        # Essayer d'envoyer directement le fichier
        try:
            logger.info(f"Tentative d'envoi direct du fichier: {result}")
            send_text_message(sender_id, f"Voici la vidéo '{title}':")
            send_file_attachment(sender_id, result, "video")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi direct du fichier: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Si l'envoi direct échoue, essayer Cloudinary
            try:
                logger.info(f"Tentative de téléchargement sur Cloudinary: {result}")
                
                # Vérifier que le fichier existe et a une taille non nulle
                if not os.path.exists(result) or os.path.getsize(result) == 0:
                    logger.error(f"Fichier invalide pour Cloudinary: {result}, taille: {os.path.getsize(result) if os.path.exists(result) else 'N/A'}")
                    raise Exception(f"Fichier invalide pour Cloudinary: {result}")
                
                # Télécharger sur Cloudinary
                video_id_cloudinary = f"youtube_{video_id}_{int(time.time())}"
                cloudinary_result = upload_file(result, video_id_cloudinary, "video")
                
                if not cloudinary_result or not cloudinary_result.get('secure_url'):
                    logger.error("Échec du téléchargement sur Cloudinary")
                    raise Exception("Échec du téléchargement sur Cloudinary")
                
                video_url = cloudinary_result.get('secure_url')
                is_raw_url = "raw" in video_url
                
                # Si l'URL est de type "raw", envoyer le lien YouTube
                if is_raw_url:
                    logger.warning(f"URL Cloudinary de type 'raw' détectée: {video_url}")
                    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                    send_text_message(sender_id, f"Désolé, je n'ai pas pu traiter la vidéo. Vous pouvez la regarder directement sur YouTube: {youtube_url}")
                else:
                    logger.info(f"Vidéo téléchargée sur Cloudinary: {video_url}")
                    
                    # Envoyer la vidéo à l'utilisateur
                    send_text_message(sender_id, f"Voici la vidéo '{title}':")
                    send_video_message(sender_id, video_url)
                
                # Sauvegarder l'information dans la base de données
                try:
                    # Ici, vous pourriez implémenter la sauvegarde dans la base de données
                    # si nécessaire
                    pass
                except Exception as db_error:
                    logger.error(f"Erreur lors de la sauvegarde dans la base de données: {str(db_error)}")
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Envoyer un message d'erreur
                send_text_message(sender_id, "Désolé, je n'ai pas pu envoyer la vidéo. Vous pouvez la regarder directement sur YouTube: " + 
                               f"https://www.youtube.com/watch?v={video_id}")
        
        # Nettoyer le répertoire temporaire
        try:
            if os.path.exists(result):
                os.remove(result)
                logger.info(f"Fichier temporaire nettoyé : {result}")
            
            # Supprimer le répertoire parent si c'est un répertoire temporaire
            parent_dir = os.path.dirname(result)
            if os.path.exists(parent_dir) and tempfile.gettempdir() in parent_dir:
                shutil.rmtree(parent_dir, ignore_errors=True)
                logger.info(f"Répertoire temporaire nettoyé : {parent_dir}")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du fichier temporaire: {str(e)}")
            
    except Exception as e:
        logger.error(f"Erreur dans le callback de téléchargement: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu traiter la vidéo téléchargée. Veuillez réessayer plus tard.")

def delete_video_from_db(video_id):
    """
    Supprime une vidéo de la base de données
    
    Args:
        video_id: ID de la vidéo YouTube
    """
    try:
        logger.info(f"Suppression de la vidéo {video_id} de la base de données")
        # Ici, vous pourriez implémenter la suppression de la base de données
        # si nécessaire
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la vidéo de la base de données: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def send_youtube_results(sender_id, videos):
    """
    Envoie les résultats de recherche YouTube à l'utilisateur
    
    Args:
        sender_id: ID du destinataire
        videos: Liste des vidéos trouvées
    """
    try:
        logger.info(f"Envoi des résultats YouTube à {sender_id}")
        
        # Limiter le nombre de vidéos à 10 (limite du carrousel Messenger)
        videos = videos[:10]
        
        if not videos:
            send_text_message(sender_id, "Désolé, je n'ai pas trouvé de vidéos correspondant à votre recherche.")
            return
        
        # Envoyer un message de confirmation
        send_text_message(sender_id, f"J'ai trouvé {len(videos)} vidéos. Voici les résultats:")
        
        # Créer les éléments du carrousel
        elements = []
        for video in videos:
            # Limiter la longueur du titre à 80 caractères (limite de Messenger)
            title = video.get('title', 'Vidéo YouTube')
            if len(title) > 80:
                title = title[:77] + '...'
            
            # Limiter la longueur de la description à 80 caractères
            description = video.get('description', '')
            if len(description) > 80:
                description = description[:77] + '...'
            
            # Créer l'élément du carrousel
            element = {
                "title": title,
                "image_url": video.get('thumbnail', ''),
                "subtitle": description,
                "buttons": [
                    {
                        "type": "postback",
                        "title": "Télécharger",
                        "payload": json.dumps({
                            "action": "watch_video",
                            "videoId": video.get('videoId', ''),
                            "title": title
                        })
                    },
                    {
                        "type": "web_url",
                        "title": "Voir sur YouTube",
                        "url": f"https://www.youtube.com/watch?v={video.get('videoId', '')}"
                    }
                ]
            }
            elements.append(element)
        
        # Créer le message avec le template de carrousel
        message = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements
                }
            }
        }
        
        # Envoyer le message
        payload = {
            "recipient": {"id": sender_id},
            "message": message
        }
        
        response = requests.post(
            f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi du carrousel YouTube: {response.status_code} - {response.text}")
            # Fallback: envoyer un message texte avec les liens
            fallback_message = "Voici les résultats de votre recherche:\n\n"
            for i, video in enumerate(videos[:5]):
                fallback_message += f"{i+1}. {video.get('title', 'Vidéo YouTube')}\n"
                fallback_message += f"   https://www.youtube.com/watch?v={video.get('videoId', '')}\n\n"
            send_text_message(sender_id, fallback_message)
        else:
            logger.info(f"Carrousel YouTube envoyé avec succès: {response.json()}")
        
        logger.info("Message envoyé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des résultats YouTube: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(sender_id, "Désolé, je n'ai pas pu afficher les résultats de recherche. Veuillez réessayer plus tard.")

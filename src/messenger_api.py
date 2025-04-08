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

# Dictionnaire pour stocker les téléchargements en cours
pending_downloads = {}

# Dictionnaire pour stocker les générations d'images en cours
pending_images = {}

def send_text_message(recipient_id, message_text):
    """
    Envoie un message texte à un destinataire via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        message_text: Texte du message à envoyer
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info(f"Envoi d'un message texte à {recipient_id}: {message_text[:50]}...")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        # Préparer les données de la requête
        payload = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text
            }
        }
        
        # Envoyer la requête
        response = requests.post(
            f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        # Vérifier le code de statut
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
    Envoie une image à un destinataire via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        image_url: URL de l'image à envoyer
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    try:
        logger.info(f"Envoi d'une image à {recipient_id}: {image_url}")
        
        if not MESSENGER_ACCESS_TOKEN:
            logger.error("Token d'accès Messenger manquant")
            return None
        
        # Préparer les données de la requête
        payload = {
            "recipient": {
                "id": recipient_id
            },
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
        
        # Envoyer la requête
        response = requests.post(
            f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        # Vérifier le code de statut
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi de l'image: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Image envoyée avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def send_file_attachment(recipient_id, file_path, attachment_type="file"):
    """
    Envoie un fichier à un destinataire via l'API Messenger
    
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
        
        # Préparer les données de la requête
        url = f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}"
        
        # Ouvrir le fichier
        with open(file_path, 'rb') as file:
            # Préparer les données multipart
            files = {
                'filedata': (os.path.basename(file_path), file, 'application/octet-stream')
            }
            
            # Préparer les données JSON
            payload = {
                'recipient': json.dumps({
                    'id': recipient_id
                }),
                'message': json.dumps({
                    'attachment': {
                        'type': attachment_type,
                        'payload': {
                            'is_reusable': True
                        }
                    }
                })
            }
            
            # Envoyer la requête
            response = requests.post(url, files=files, data=payload)
        
        # Vérifier le code de statut
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'envoi du fichier: {response.status_code} - {response.text}")
            return None
        
        logger.info(f"Fichier envoyé avec succès: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du fichier: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def send_youtube_results(recipient_id, videos):
    """
    Envoie les résultats de recherche YouTube à un destinataire
    
    Args:
        recipient_id: ID du destinataire
        videos: Liste des vidéos trouvées
    """
    try:
        if not videos:
            send_text_message(recipient_id, "Aucune vidéo trouvée. Veuillez essayer avec d'autres mots-clés.")
            return
        
        # Limiter le nombre de résultats à 5 pour éviter de spammer l'utilisateur
        videos = videos[:5]
        
        # Envoyer un message d'introduction
        send_text_message(recipient_id, f"J'ai trouvé {len(videos)} vidéos. Voici les résultats:")
        
        # Envoyer chaque vidéo sous forme de template générique
        for video in videos:
            # Préparer les données de la requête
            payload = {
                "recipient": {
                    "id": recipient_id
                },
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": [
                                {
                                    "title": video.get('title', 'Vidéo YouTube'),
                                    "subtitle": video.get('channelTitle', ''),
                                    "image_url": video.get('thumbnail', f"https://img.youtube.com/vi/{video.get('videoId')}/hqdefault.jpg"),
                                    "default_action": {
                                        "type": "web_url",
                                        "url": f"https://www.youtube.com/watch?v={video.get('videoId')}",
                                        "webview_height_ratio": "tall"
                                    },
                                    "buttons": [
                                        {
                                            "type": "web_url",
                                            "url": f"https://www.youtube.com/watch?v={video.get('videoId')}",
                                            "title": "Voir sur YouTube"
                                        },
                                        {
                                            "type": "postback",
                                            "title": "Télécharger",
                                            "payload": json.dumps({
                                                "action": "watch_video",
                                                "videoId": video.get('videoId'),
                                                "title": video.get('title', 'Vidéo YouTube')
                                            })
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
            
            # Envoyer la requête
            response = requests.post(
                f"{MESSENGER_API_URL}?access_token={MESSENGER_ACCESS_TOKEN}",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            # Vérifier le code de statut
            if response.status_code != 200:
                logger.error(f"Erreur lors de l'envoi des résultats YouTube: {response.status_code} - {response.text}")
                continue
            
            logger.info(f"Résultat YouTube envoyé avec succès: {response.json()}")
            
            # Attendre un peu pour éviter de spammer l'API
            time.sleep(0.5)
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des résultats YouTube: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(recipient_id, "Désolé, je n'ai pas pu envoyer les résultats de la recherche. Veuillez réessayer plus tard.")

def handle_watch_video(sender_id, video_id, title, force_download=False):
    """
    Gère la demande de téléchargement d'une vidéo YouTube
    
    Args:
        sender_id: ID de l'expéditeur
        video_id: ID de la vidéo YouTube
        title: Titre de la vidéo
        force_download: Forcer le téléchargement même si la vidéo est déjà téléchargée
    """
    try:
        logger.info(f"Demande de téléchargement de la vidéo {video_id} par {sender_id}")
        
        # Vérifier si un téléchargement est déjà en cours pour cet utilisateur
        if sender_id in pending_downloads and pending_downloads[sender_id]:
            send_text_message(sender_id, "Un téléchargement est déjà en cours. Veuillez patienter.")
            return
        
        # Vérifier si la vidéo est déjà téléchargée
        from src.database import get_video_by_id
        video_entry = get_video_by_id(video_id)
        
        if video_entry and not force_download:
            # Si la vidéo est déjà téléchargée, envoyer directement le lien
            if video_entry.get('is_raw_url', False):
                send_text_message(sender_id, f"Voici la vidéo: {video_entry.get('url')}")
                return
            
            # Si la vidéo a une URL Cloudinary, envoyer l'URL
            if video_entry.get('url'):
                send_text_message(sender_id, f"Voici la vidéo: {title}")
                send_text_message(sender_id, video_entry.get('url'))
                return
        
        # Marquer le téléchargement comme en cours
        if sender_id not in pending_downloads:
            pending_downloads[sender_id] = {}
        pending_downloads[sender_id] = True
        
        # Envoyer un message de confirmation
        send_text_message(sender_id, f"Je télécharge la vidéo: {title}. Cela peut prendre quelques instants...")
        
        # Créer un répertoire temporaire pour la vidéo
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        
        # Créer une fonction de callback pour le téléchargement
        def download_callback(result):
            handle_download_callback(sender_id, video_id, title, result)
        
        # Ajouter le téléchargement à la file d'attente
        download_youtube_video(video_id, output_path, download_callback)
    except Exception as e:
        logger.error(f"Erreur lors de la gestion de la demande de téléchargement: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Supprimer le téléchargement en cours
        if sender_id in pending_downloads:
            pending_downloads[sender_id] = False
        
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
    logger.info(f"Callback de téléchargement pour {sender_id}, vidéo: {video_id}")
    
    try:
        # Supprimer le téléchargement en cours
        if sender_id in pending_downloads:
            pending_downloads[sender_id] = False
        
        # Si le résultat est None, envoyer un message d'erreur
        if result is None:
            send_text_message(sender_id, "Désolé, je n'ai pas pu télécharger la vidéo. Veuillez réessayer plus tard.")
            return
        
        # Si le résultat est une URL, envoyer l'URL
        if isinstance(result, str) and (result.startswith("http://") or result.startswith("https://")):
            # Sauvegarder l'URL dans la base de données
            from src.database import save_video
            save_video(video_id, result, title, is_raw_url=True)
            
            send_text_message(sender_id, f"Voici la vidéo: {title}")
            send_text_message(sender_id, result)
            return
        
        # Si le résultat est un chemin de fichier, vérifier qu'il existe
        if not os.path.exists(result):
            send_text_message(sender_id, "Désolé, je n'ai pas pu télécharger la vidéo. Veuillez réessayer plus tard.")
            return
        
        logger.info(f"Vidéo téléchargée avec succès: {result}")
        
        # Essayer d'envoyer directement le fichier
        try:
            logger.info(f"Tentative d'envoi direct du fichier: {result}")
            send_text_message(sender_id, f"Voici la vidéo: {title}")
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
                video_id_cloudinary = f"youtube_{int(time.time())}"
                cloudinary_result = upload_file(result, video_id_cloudinary, "video")
                
                if not cloudinary_result or not cloudinary_result.get('secure_url'):
                    logger.error("Échec du téléchargement sur Cloudinary")
                    raise Exception("Échec du téléchargement sur Cloudinary")
                    
                video_url = cloudinary_result.get('secure_url')
                logger.info(f"Vidéo téléchargée sur Cloudinary: {video_url}")
                
                # Sauvegarder l'URL dans la base de données
                from src.database import save_video
                save_video(video_id, video_url, title)
                
                # Vérifier si l'URL est "raw"
                is_raw = "raw" in video_url
                
                # Envoyer la vidéo à l'utilisateur
                send_text_message(sender_id, f"Voici la vidéo: {title}")
                
                if is_raw:
                    # Si l'URL est "raw", envoyer le lien YouTube
                    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                    send_text_message(sender_id, f"La vidéo est disponible sur YouTube: {youtube_url}")
                    
                    # Mettre à jour la base de données
                    from src.database import update_video_raw_status
                    update_video_raw_status(video_id, True)
                else:
                    # Sinon, envoyer l'URL Cloudinary
                    send_text_message(sender_id, video_url)
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Envoyer un message d'erreur
                send_text_message(sender_id, "Désolé, je n'ai pas pu envoyer la vidéo. Veuillez réessayer plus tard.")
        
        # Nettoyer le répertoire temporaire
        try:
            if os.path.exists(result):
                os.remove(result)
                logger.info(f"Fichier temporaire nettoyé : {result}")
            
            # Supprimer le répertoire parent
            parent_dir = os.path.dirname(result)
            if os.path.exists(parent_dir):
                shutil.rmtree(parent_dir)
                logger.info(f"Répertoire temporaire nettoyé : {parent_dir}")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage du répertoire temporaire: {str(e)}")
            
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
        from src.database import delete_video
        delete_video(video_id)
        logger.info(f"Vidéo supprimée de la base de données: {video_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la vidéo de la base de données: {str(e)}")
        logger.error(traceback.format_exc())
        return False

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
                            "title": "🖼️ Générer une image",
                            "payload": json.dumps({"action": "generate_image"})
                        },
                        {
                            "type": "postback",
                            "title": "🔄 Réinitialiser",
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
                    user_states[sender_id] =  or payload.get('action') == 'mode_mistral':
                    user_states[sender_id] = 'mistral'
                    send_text_message(sender_id, "Mode Mistral activé. Comment puis-je vous aider ?")
                elif payload.get('action') == 'generate_image':
                    send_text_message(sender_id, "Pour générer une image, envoyez une commande comme: /img un chat jouant du piano")
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

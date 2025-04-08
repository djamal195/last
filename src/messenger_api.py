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
                            "title": "🔄 Réinitialiser la conversation",
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

# Ajouter ou modifier la fonction handle_watch_video pour ne pas dépendre de get_video_by_id

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

# Rechercher la fonction send_youtube_results et la remplacer par cette version qui utilise un carrousel

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

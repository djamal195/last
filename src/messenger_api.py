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

def delete_video_from_db(video_id):
    """
    Supprime une vidéo de la base de données
    
    Args:
        video_id: ID de la vidéo YouTube à supprimer
    """
    try:
        from src.database import get_database
        db = get_database()
        
        if db is not None:
            # Récupérer l'entrée existante
            video_collection = db.videos
            existing_video = video_collection.find_one({"video_id": video_id})
            
            if existing_video:
                # Si la vidéo a une URL Cloudinary, essayer de la supprimer de Cloudinary
                cloudinary_url = existing_video.get('cloudinary_url')
                if cloudinary_url:
                    try:
                        # Déterminer le type de ressource
                        resource_type = "video"
                        if "raw/upload" in cloudinary_url:
                            resource_type = "raw"
                        
                        # Supprimer de Cloudinary
                        public_id = f"youtube_{video_id}"
                        delete_file(public_id, resource_type)
                    except Exception as e:
                        logger.error(f"Erreur lors de la suppression de Cloudinary: {str(e)}")
                
                # Supprimer de la base de données
                result = video_collection.delete_one({"video_id": video_id})
                logger.info(f"Vidéo supprimée de la base de données: {video_id}, résultat: {result.deleted_count}")
            else:
                logger.info(f"Aucune vidéo trouvée dans la base de données pour l'ID: {video_id}")
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la vidéo de la base de données: {str(e)}")
        logger.error(traceback.format_exc())

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

def convert_video_to_mp4(input_path, output_path=None):
    """
    Convertit une vidéo en format MP4 compatible avec Messenger
    
    Args:
        input_path: Chemin de la vidéo d'entrée
        output_path: Chemin de sortie (optionnel)
        
    Returns:
        Chemin de la vidéo convertie ou None en cas d'erreur
    """
    try:
        logger.info(f"Conversion de la vidéo: {input_path}")
        
        if not os.path.exists(input_path):
            logger.error(f"Le fichier d'entrée n'existe pas: {input_path}")
            return None
        
        # Si aucun chemin de sortie n'est spécifié, créer un fichier temporaire
        if not output_path:
            output_dir = os.path.dirname(input_path)
            output_filename = f"converted_{os.path.basename(input_path)}"
            output_path = os.path.join(output_dir, output_filename)
        
        # Utiliser ffmpeg pour convertir la vidéo
        command = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',  # Codec vidéo H.264
            '-c:a', 'aac',      # Codec audio AAC
            '-strict', 'experimental',
            '-b:v', '1M',       # Bitrate vidéo 1 Mbps
            '-b:a', '128k',     # Bitrate audio 128 kbps
            '-vf', 'scale=640:-2',  # Redimensionner à 640px de large
            '-f', 'mp4',        # Format de sortie MP4
            '-movflags', '+faststart',  # Optimiser pour le streaming
            '-y',               # Écraser le fichier de sortie s'il existe
            output_path
        ]
        
        logger.info(f"Exécution de la commande: {' '.join(command)}")
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Erreur lors de la conversion de la vidéo: {stderr}")
            return None
        
        # Vérifier si le fichier de sortie existe et a une taille non nulle
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error(f"Le fichier de sortie n'existe pas ou est vide: {output_path}")
            return None
        
        logger.info(f"Vidéo convertie avec succès: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Erreur lors de la conversion de la vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def handle_download_callback(recipient_id, video_id, title, result):
    """
    Callback pour le téléchargement d'une vidéo
    
    Args:
        recipient_id: ID du destinataire
        video_id: ID de la vidéo YouTube
        title: Titre de la vidéo
        result: Résultat du téléchargement (chemin du fichier ou URL YouTube)
    """
    logger.info(f"Callback de téléchargement pour {recipient_id}, vidéo {video_id}: {result}")
    
    try:
        # Supprimer le téléchargement en cours
        if recipient_id in pending_downloads and video_id in pending_downloads[recipient_id]:
            del pending_downloads[recipient_id][video_id]
        
        # Si le résultat est None, envoyer un message d'erreur
        if result is None:
            send_text_message(recipient_id, f"Désolé, je n'ai pas pu télécharger la vidéo. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
            return
        
        # Si le résultat est une URL YouTube, envoyer le lien
        if isinstance(result, str) and result.startswith("https://www.youtube.com/watch"):
            send_text_message(recipient_id, f"En raison des limitations de YouTube, je ne peux pas télécharger la vidéo pour le moment. Voici le lien direct: {result}")
            return
        
        # Si le résultat est un chemin de fichier, vérifier qu'il existe
        if not os.path.exists(result):
            send_text_message(recipient_id, f"Désolé, le téléchargement de la vidéo a échoué. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
            return
        
        logger.info(f"Vidéo téléchargée avec succès: {result}")
        
        # Convertir la vidéo en format MP4 compatible
        converted_path = convert_video_to_mp4(result)
        
        if not converted_path:
            logger.error("Échec de la conversion de la vidéo")
            send_text_message(recipient_id, f"Désolé, je n'ai pas pu traiter la vidéo. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
            return
        
        logger.info(f"Vidéo convertie avec succès: {converted_path}")
        
        # Essayer d'envoyer directement le fichier
        try:
            logger.info(f"Tentative d'envoi direct du fichier: {converted_path}")
            send_text_message(recipient_id, f"Voici votre vidéo : {title}")
            send_file_response = send_file_attachment(recipient_id, converted_path, "video")
            
            if send_file_response:
                logger.info(f"Fichier envoyé avec succès directement: {send_file_response}")
                
                # Sauvegarder dans la base de données pour une utilisation future
                try:
                    from src.database import get_database
                    db = get_database()
                    if db is not None:
                        video_collection = db.videos
                        video_collection.update_one(
                            {"video_id": video_id},
                            {"$set": {
                                "video_id": video_id,
                                "title": title,
                                "direct_sent": True,
                                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                                "created_at": time.time()
                            }},
                            upsert=True
                        )
                        logger.info(f"Vidéo sauvegardée dans la base de données: {video_id}")
                except Exception as e:
                    logger.error(f"Erreur lors de la sauvegarde dans la base de données: {str(e)}")
                
                # Nettoyer les fichiers temporaires
                try:
                    # Supprimer le fichier original
                    if os.path.exists(result) and result != converted_path:
                        os.remove(result)
                        logger.info(f"Fichier original supprimé: {result}")
                    
                    # Supprimer le fichier converti
                    if os.path.exists(converted_path):
                        os.remove(converted_path)
                        logger.info(f"Fichier converti supprimé: {converted_path}")
                    
                    # Supprimer le répertoire temporaire
                    temp_dir = os.path.dirname(result)
                    if temp_dir.startswith('/tmp/tmp'):
                        shutil.rmtree(temp_dir)
                        logger.info(f"Répertoire temporaire nettoyé: {temp_dir}")
                except Exception as e:
                    logger.error(f"Erreur lors du nettoyage des fichiers temporaires: {str(e)}")
                
                return
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi direct du fichier: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Si l'envoi direct échoue, essayer Cloudinary
        try:
            logger.info(f"Tentative de téléchargement sur Cloudinary: {converted_path}")
            
            # Vérifier que le fichier existe et a une taille non nulle
            if not os.path.exists(converted_path) or os.path.getsize(converted_path) == 0:
                logger.error(f"Fichier invalide pour Cloudinary: {converted_path}, taille: {os.path.getsize(converted_path) if os.path.exists(converted_path) else 'N/A'}")
                raise Exception(f"Fichier invalide pour Cloudinary: {converted_path}")
            
            # Forcer le type de ressource vidéo
            cloudinary_result = upload_file(converted_path, f"youtube_{video_id}", "video")
            
            if not cloudinary_result or not cloudinary_result.get('secure_url'):
                logger.error("Échec du téléchargement sur Cloudinary")
                
                # Essayer avec le type auto
                cloudinary_result = upload_file(converted_path, f"youtube_{video_id}", "auto")
                
                if not cloudinary_result or not cloudinary_result.get('secure_url'):
                    logger.error("Échec du téléchargement sur Cloudinary avec le type auto")
                    raise Exception("Échec du téléchargement sur Cloudinary")
                
            video_url = cloudinary_result.get('secure_url')
            logger.info(f"Vidéo téléchargée sur Cloudinary: {video_url}")
            
            # Vérifier si l'URL est une URL vidéo ou raw
            is_video_url = "video/upload" in video_url
            is_raw_url = "raw/upload" in video_url
            
            # Si c'est une URL raw, essayer d'envoyer le lien Cloudinary directement
            if is_raw_url:
                logger.warning("URL Cloudinary de type 'raw', tentative d'envoi direct du lien Cloudinary")
                
                # Essayer d'envoyer le lien comme une URL
                message_data = {
                    "recipient": {
                        "id": recipient_id
                    },
                    "message": {
                        "attachment": {
                            "type": "file",
                            "payload": {
                                "url": video_url
                            }
                        }
                    }
                }
                
                response = call_send_api(message_data)
                
                if not response:
                    logger.error("Échec de l'envoi du lien Cloudinary comme fichier")
                    send_text_message(recipient_id, f"Voici le lien de la vidéo sur YouTube: https://www.youtube.com/watch?v={video_id}")
                    return
                
                logger.info("Lien Cloudinary envoyé avec succès comme fichier")
                send_text_message(recipient_id, f"Voici votre vidéo : {title}")
                return
            
            # Sauvegarder l'URL dans la base de données pour une utilisation future
            from src.database import get_database
            db = get_database()
            
            if db is not None:
                video_collection = db.videos
                video_collection.update_one(
                    {"video_id": video_id},
                    {"$set": {
                        "video_id": video_id,
                        "title": title,
                        "cloudinary_url": video_url,
                        "is_raw_url": is_raw_url,
                        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "created_at": time.time()
                    }},
                    upsert=True
                )
                logger.info(f"Vidéo sauvegardée dans la base de données: {video_id}")
            
            # Envoyer la vidéo à l'utilisateur
            send_text_message(recipient_id, f"Voici votre vidéo : {title}")
            send_video_response = send_video_message(recipient_id, video_url)
            
            if not send_video_response:
                logger.error(f"Échec de l'envoi de la vidéo via Messenger avec l'URL Cloudinary")
                # Envoyer le lien YouTube comme solution de secours
                send_text_message(recipient_id, f"Voici le lien de la vidéo sur YouTube: https://www.youtube.com/watch?v={video_id}")
                send_text_message(recipient_id, "Pour réessayer avec une autre méthode, envoyez: /retry " + video_id)
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Envoyer le lien YouTube comme solution de secours
            send_text_message(recipient_id, f"Désolé, je n'ai pas pu traiter la vidéo. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
            send_text_message(recipient_id, "Pour réessayer avec une autre méthode, envoyez: /retry " + video_id)
        
        # Nettoyer les fichiers temporaires
        try:
            # Supprimer le fichier original
            if os.path.exists(result) and result != converted_path:
                os.remove(result)
                logger.info(f"Fichier original supprimé: {result}")
            
            # Supprimer le fichier converti
            if os.path.exists(converted_path):
                os.remove(converted_path)
                logger.info(f"Fichier converti supprimé: {converted_path}")
            
            # Supprimer le répertoire temporaire
            temp_dir = os.path.dirname(result)
            if temp_dir.startswith('/tmp/tmp'):
                shutil.rmtree(temp_dir)
                logger.info(f"Répertoire temporaire nettoyé: {temp_dir}")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des fichiers temporaires: {str(e)}")
            
    except Exception as e:
        logger.error(f"Erreur dans le callback de téléchargement: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(recipient_id, f"Désolé, je n'ai pas pu traiter la vidéo. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
        send_text_message(recipient_id, "Pour réessayer avec une autre méthode, envoyez: /retry " + video_id)

def handle_watch_video(recipient_id, video_id, title, force_download=False):
    """
    Télécharge et envoie la vidéo YouTube
    
    Args:
        recipient_id: ID du destinataire
        video_id: ID de la vidéo YouTube
        title: Titre de la vidéo
        force_download: Si True, force le téléchargement même si la vidéo existe déjà
    """
    try:
        # Vérifier si le video_id est valide
        if not video_id:
            send_text_message(recipient_id, "Désolé, l'identifiant de la vidéo est invalide.")
            return
            
        # Informer l'utilisateur que le téléchargement est en cours
        send_text_message(recipient_id, "Préparation de la vidéo en cours... Cela peut prendre quelques instants.")
        
        # Si force_download est True, supprimer l'entrée existante
        if force_download:
            delete_video_from_db(video_id)
        
        # Vérifier d'abord dans la base de données MongoDB si la vidéo a déjà été téléchargée
        from src.database import get_database
        db = get_database()
        
        if not force_download and db is not None:
            # Vérifier si la vidéo existe déjà
            video_collection = db.videos
            existing_video = video_collection.find_one({"video_id": video_id})
            
            if existing_video:
                logger.info(f"Vidéo trouvée dans la base de données: {video_id}")
                
                # Vérifier si l'URL est de type raw
                is_raw_url = existing_video.get('is_raw_url', False)
                cloudinary_url = existing_video.get('cloudinary_url')
                
                if is_raw_url or (cloudinary_url and "raw/upload" in cloudinary_url):
                    logger.warning("URL Cloudinary de type 'raw' trouvée dans la base de données, suppression et nouveau téléchargement")
                    delete_video_from_db(video_id)
                else:
                    if cloudinary_url:
                        send_text_message(recipient_id, f"Voici votre vidéo : {title}")
                        send_video_response = send_video_message(recipient_id, cloudinary_url)
                        
                        if not send_video_response:
                            logger.error(f"Échec de l'envoi de la vidéo via Messenger avec l'URL Cloudinary stockée")
                            send_text_message(recipient_id, f"Voici le lien de la vidéo sur YouTube: https://www.youtube.com/watch?v={video_id}")
                            send_text_message(recipient_id, "Pour réessayer avec une autre méthode, envoyez: /retry " + video_id)
                        return
        
        # Initialiser le dictionnaire des téléchargements en cours pour cet utilisateur
        if recipient_id not in pending_downloads:
            pending_downloads[recipient_id] = {}
        
        # Vérifier si un téléchargement est déjà en cours pour cette vidéo
        if video_id in pending_downloads[recipient_id]:
            send_text_message(recipient_id, "Le téléchargement de cette vidéo est déjà en cours. Veuillez patienter.")
            return
        
        # Marquer le téléchargement comme en cours
        pending_downloads[recipient_id][video_id] = True
        
        # Créer un répertoire temporaire pour le téléchargement
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, f"{video_id}.mp4")
        
        # Créer une fonction de callback pour le téléchargement
        def download_callback(result):
            handle_download_callback(recipient_id, video_id, title, result)
        
        # Ajouter le téléchargement à la file d'attente
        download_youtube_video(video_id, temp_file, download_callback)
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        send_text_message(recipient_id, f"Désolé, je n'ai pas pu traiter cette vidéo. Voici le lien YouTube: https://www.youtube.com/watch?v={video_id}")
        send_text_message(recipient_id, "Pour réessayer avec une autre méthode, envoyez: /retry " + video_id)

def send_video_message(recipient_id, video_url):
    """
    Envoie un message vidéo à l'utilisateur
    
    Args:
        recipient_id: ID du destinataire
        video_url: URL de la vidéo à envoyer
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
    """
    logger.info(f"Envoi de la vidéo à {recipient_id}: {video_url}")
    
    # Vérifier si l'URL est une URL raw de Cloudinary
    if "raw/upload" in video_url:
        logger.warning("URL Cloudinary de type 'raw' détectée, tentative d'envoi comme fichier")
        
        # Essayer d'envoyer comme fichier
        message_data = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "attachment": {
                    "type": "file",
                    "payload": {
                        "url": video_url,
                        "is_reusable": True
                    }
                }
            }
        }
    else:
        # Envoyer comme vidéo
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
    return response

def send_file_attachment(recipient_id, file_path, attachment_type):
    """
    Envoie un fichier en pièce jointe à l'utilisateur
    
    Args:
        recipient_id: ID du destinataire
        file_path: Chemin du fichier à envoyer
        attachment_type: Type de pièce jointe (image, video, audio, file)
        
    Returns:
        Réponse de l'API ou None en cas d'erreur
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


import os
import json
import requests
import traceback
import logging
import tempfile
import uuid
import re
from typing import Dict, Any, Optional, List

# Configuration du logger
from src.utils.logger import get_logger
logger = get_logger(__name__)

# Importer les fonctions YouTube
from src.youtube_api import search_youtube, download_youtube_video

# URL de l'API Messenger
MESSENGER_API_URL = "https://graph.facebook.com/v18.0/me/messages"

# Regex pour détecter les URLs YouTube
YOUTUBE_URL_REGEX = re.compile(r'https?://(www\.)?(youtube\.com|youtu\.be)/.+')

def send_message(recipient_id: str, message_text: str) -> bool:
    """
    Envoie un message texte à un utilisateur via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        message_text: Texte du message à envoyer
        
    Returns:
        True si le message a été envoyé avec succès, False sinon
    """
    try:
        logger.info(f"Envoi d'un message à {recipient_id}: {message_text[:50]}...")
        
        # Vérifier si le token d'accès est disponible
        access_token = os.environ.get('MESSENGER_ACCESS_TOKEN')
        if not access_token:
            logger.error("Token d'accès Messenger manquant")
            # Pour le développement, simuler un envoi réussi même sans token
            return True
        
        # Construire le payload du message
        message_data = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text
            }
        }
        
        # Paramètres de la requête
        params = {
            "access_token": access_token
        }
        
        # Envoyer la requête à l'API Messenger
        response = requests.post(
            MESSENGER_API_URL,
            params=params,
            json=message_data
        )
        
        # Vérifier la réponse
        response.raise_for_status()
        result = response.json()
        
        if 'message_id' in result:
            logger.info(f"Message envoyé avec succès, ID: {result['message_id']}")
            return True
        else:
            logger.warning(f"Message envoyé mais pas d'ID retourné: {result}")
            return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi du message: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi du message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def send_image(recipient_id: str, image_url: str) -> bool:
    """
    Envoie une image à un utilisateur via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        image_url: URL de l'image à envoyer
        
    Returns:
        True si l'image a été envoyée avec succès, False sinon
    """
    try:
        logger.info(f"Envoi d'une image à {recipient_id}: {image_url}")
        
        # Vérifier si le token d'accès est disponible
        access_token = os.environ.get('MESSENGER_ACCESS_TOKEN')
        if not access_token:
            logger.error("Token d'accès Messenger manquant")
            # Pour le développement, simuler un envoi réussi même sans token
            return True
        
        # Construire le payload du message
        message_data = {
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
        
        # Paramètres de la requête
        params = {
            "access_token": access_token
        }
        
        # Envoyer la requête à l'API Messenger
        response = requests.post(
            MESSENGER_API_URL,
            params=params,
            json=message_data
        )
        
        # Vérifier la réponse
        response.raise_for_status()
        result = response.json()
        
        if 'message_id' in result:
            logger.info(f"Image envoyée avec succès, ID: {result['message_id']}")
            return True
        else:
            logger.warning(f"Image envoyée mais pas d'ID retourné: {result}")
            return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi de l'image: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi de l'image: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def send_video(recipient_id: str, video_url: str) -> bool:
    """
    Envoie une vidéo à un utilisateur via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        video_url: URL de la vidéo à envoyer
        
    Returns:
        True si la vidéo a été envoyée avec succès, False sinon
    """
    try:
        logger.info(f"Envoi d'une vidéo à {recipient_id}: {video_url}")
        
        # Vérifier si le token d'accès est disponible
        access_token = os.environ.get('MESSENGER_ACCESS_TOKEN')
        if not access_token:
            logger.error("Token d'accès Messenger manquant")
            # Pour le développement, simuler un envoi réussi même sans token
            return True
        
        # Construire le payload du message
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
        
        # Paramètres de la requête
        params = {
            "access_token": access_token
        }
        
        # Envoyer la requête à l'API Messenger
        response = requests.post(
            MESSENGER_API_URL,
            params=params,
            json=message_data
        )
        
        # Vérifier la réponse
        response.raise_for_status()
        result = response.json()
        
        if 'message_id' in result:
            logger.info(f"Vidéo envoyée avec succès, ID: {result['message_id']}")
            return True
        else:
            logger.warning(f"Vidéo envoyée mais pas d'ID retourné: {result}")
            return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi de la vidéo: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi de la vidéo: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def send_file(recipient_id: str, file_url: str, file_type: str = "file") -> bool:
    """
    Envoie un fichier à un utilisateur via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        file_url: URL du fichier à envoyer
        file_type: Type de fichier (file, audio, video, image)
        
    Returns:
        True si le fichier a été envoyé avec succès, False sinon
    """
    try:
        logger.info(f"Envoi d'un fichier ({file_type}) à {recipient_id}: {file_url}")
        
        # Vérifier si le token d'accès est disponible
        access_token = os.environ.get('MESSENGER_ACCESS_TOKEN')
        if not access_token:
            logger.error("Token d'accès Messenger manquant")
            # Pour le développement, simuler un envoi réussi même sans token
            return True
        
        # Valider le type de fichier
        valid_types = ["file", "audio", "video", "image"]
        if file_type not in valid_types:
            logger.warning(f"Type de fichier non valide: {file_type}. Utilisation du type 'file' par défaut.")
            file_type = "file"
        
        # Construire le payload du message
        message_data = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "attachment": {
                    "type": file_type,
                    "payload": {
                        "url": file_url,
                        "is_reusable": True
                    }
                }
            }
        }
        
        # Paramètres de la requête
        params = {
            "access_token": access_token
        }
        
        # Envoyer la requête à l'API Messenger
        response = requests.post(
            MESSENGER_API_URL,
            params=params,
            json=message_data
        )
        
        # Vérifier la réponse
        response.raise_for_status()
        result = response.json()
        
        if 'message_id' in result:
            logger.info(f"Fichier envoyé avec succès, ID: {result['message_id']}")
            return True
        else:
            logger.warning(f"Fichier envoyé mais pas d'ID retourné: {result}")
            return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi du fichier: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi du fichier: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def send_quick_replies(recipient_id: str, message_text: str, quick_replies: List[Dict[str, str]]) -> bool:
    """
    Envoie un message avec des réponses rapides à un utilisateur via l'API Messenger
    
    Args:
        recipient_id: ID du destinataire
        message_text: Texte du message à envoyer
        quick_replies: Liste de réponses rapides (doit contenir 'content_type', 'title', 'payload')
        
    Returns:
        True si le message a été envoyé avec succès, False sinon
    """
    try:
        logger.info(f"Envoi d'un message avec réponses rapides à {recipient_id}")
        
        # Vérifier si le token d'accès est disponible
        access_token = os.environ.get('MESSENGER_ACCESS_TOKEN')
        if not access_token:
            logger.error("Token d'accès Messenger manquant")
            # Pour le développement, simuler un envoi réussi même sans token
            return True
        
        # Construire le payload du message
        message_data = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text,
                "quick_replies": quick_replies
            }
        }
        
        # Paramètres de la requête
        params = {
            "access_token": access_token
        }
        
        # Envoyer la requête à l'API Messenger
        response = requests.post(
            MESSENGER_API_URL,
            params=params,
            json=message_data
        )
        
        # Vérifier la réponse
        response.raise_for_status()
        result = response.json()
        
        if 'message_id' in result:
            logger.info(f"Message avec réponses rapides envoyé avec succès, ID: {result['message_id']}")
            return True
        else:
            logger.warning(f"Message avec réponses rapides envoyé mais pas d'ID retourné: {result}")
            return True
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi du message avec réponses rapides: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue lors de l'envoi du message avec réponses rapides: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def send_youtube_video(recipient_id: str, video_id: str) -> bool:
    """
    Télécharge et envoie une vidéo YouTube à un utilisateur
    
    Args:
        recipient_id: ID du destinataire
        video_id: ID de la vidéo YouTube
        
    Returns:
        True si la vidéo a été envoyée avec succès, False sinon
    """
    try:
        logger.info(f"Préparation de l'envoi de la vidéo YouTube {video_id} à {recipient_id}")
        
        # Télécharger la vidéo
        video_path_or_url = download_youtube_video(video_id)
        
        if not video_path_or_url:
            logger.error(f"Échec du téléchargement de la vidéo: {video_id}")
            send_message(recipient_id, "Désolé, je n'ai pas pu télécharger cette vidéo. Veuillez réessayer plus tard.")
            return False
        
        # Vérifier si c'est une URL YouTube (solution de secours en cas de limitation de débit)
        if YOUTUBE_URL_REGEX.match(video_path_or_url):
            logger.info(f"Envoi du lien YouTube au lieu de la vidéo: {video_path_or_url}")
            send_message(recipient_id, f"Voici la vidéo que vous avez demandée: {video_path_or_url}")
            return True
        
        # Si c'est un chemin de fichier, envoyer la vidéo
        logger.info(f"Vidéo téléchargée avec succès: {video_path_or_url}")
        
        # Vérifier si le fichier existe
        if not os.path.exists(video_path_or_url):
            logger.error(f"Le fichier vidéo n'existe pas: {video_path_or_url}")
            send_message(recipient_id, "Désolé, je n'ai pas pu télécharger cette vidéo. Veuillez réessayer plus tard.")
            return False
        
        # Envoyer la vidéo
        # Note: Cette partie dépend de la façon dont vous hébergez et servez les fichiers
        # Vous devrez peut-être télécharger la vidéo sur un service de stockage cloud d'abord
        
        # Pour cet exemple, nous supposons que vous avez une URL publique pour le fichier
        video_url = f"https://votre-domaine.com/videos/{os.path.basename(video_path_or_url)}"
        
        # Envoyer la vidéo
        return send_video(recipient_id, video_url)
            
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement/envoi de la vidéo: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        send_message(recipient_id, "Désolé, je n'ai pas pu télécharger cette vidéo. Veuillez réessayer plus tard.")
        return False

def handle_message(sender_id: str, message_data: Any) -> bool:
    """
    Traite un message reçu d'un utilisateur
    
    Args:
        sender_id: ID de l'expéditeur
        message_data: Données du message reçu (peut être un dictionnaire ou une chaîne)
        
    Returns:
        True si le message a été traité avec succès, False sinon
    """
    try:
        logger.info(f"Traitement du message de {sender_id}: {message_data}")
        
        # Extraire le texte du message
        message_text = ""
        if isinstance(message_data, dict) and 'text' in message_data:
            message_text = message_data['text']
        elif isinstance(message_data, str):
            message_text = message_data
        else:
            logger.warning(f"Format de message non reconnu: {type(message_data)}")
            send_message(sender_id, "Je n'ai pas compris votre message. Veuillez envoyer un texte.")
            return True
        
        # Vérifier si le message est vide
        if not message_text or message_text.strip() == "":
            logger.warning(f"Message vide reçu de {sender_id}")
            send_message(sender_id, "Je n'ai pas compris votre message. Veuillez envoyer un texte.")
            return True
        
        # Convertir en minuscules pour faciliter la comparaison
        message_lower = message_text.lower()
        
        # Commande d'aide
        if message_lower == "aide" or message_lower == "help":
            send_message(sender_id, "Voici les commandes disponibles:\n"
                                   "- 'recherche [terme]': Recherche des vidéos YouTube\n"
                                   "- 'video [id]': Télécharge et envoie une vidéo YouTube\n"
                                   "- 'aide': Affiche ce message d'aide")
            return True
        
        # Commande de recherche
        if message_lower.startswith("recherche ") or message_lower.startswith("search "):
            # Extraire le terme de recherche
            search_term = message_text.split(" ", 1)[1].strip()
            
            if not search_term:
                send_message(sender_id, "Veuillez spécifier un terme de recherche. Exemple: 'recherche chat mignon'")
                return True
            
            # Rechercher des vidéos
            videos = search_youtube(search_term)
            
            if not videos:
                send_message(sender_id, f"Aucune vidéo trouvée pour '{search_term}'")
                return True
            
            # Construire le message de résultats
            result_message = f"Résultats pour '{search_term}':\n\n"
            
            for i, video in enumerate(videos[:5], 1):
                result_message += f"{i}. {video['title']}\n"
                result_message += f"ID: {video['videoId']}\n"
                result_message += f"URL: {video['url']}\n\n"
            
            result_message += "Pour télécharger une vidéo, envoyez 'video [ID]'"
            
            # Envoyer les résultats
            send_message(sender_id, result_message)
            return True
        
        # Commande de téléchargement de vidéo
        if message_lower.startswith("video ") or message_lower.startswith("vidéo "):
            # Extraire l'ID de la vidéo
            video_id = message_text.split(" ", 1)[1].strip()
            
            if not video_id:
                send_message(sender_id, "Veuillez spécifier l'ID de la vidéo. Exemple: 'video dQw4w9WgXcQ'")
                return True
            
            # Envoyer un message d'attente
            send_message(sender_id, f"Téléchargement de la vidéo {video_id} en cours... Cela peut prendre quelques instants.")
            
            # Télécharger et envoyer la vidéo
            video_path_or_url = download_youtube_video(video_id)
            
            if not video_path_or_url:
                send_message(sender_id, "Désolé, je n'ai pas pu télécharger cette vidéo. Veuillez réessayer plus tard.")
                return False
            
            # Vérifier si c'est une URL YouTube (solution de secours en cas de limitation de débit)
            if YOUTUBE_URL_REGEX.match(video_path_or_url):
                logger.info(f"Envoi du lien YouTube au lieu de la vidéo: {video_path_or_url}")
                send_message(sender_id, f"En raison des limitations de YouTube, je ne peux pas télécharger la vidéo pour le moment. Voici le lien direct: {video_path_or_url}")
                return True
            
            # Si c'est un chemin de fichier, envoyer la vidéo
            # Note: Cette partie dépend de la façon dont vous hébergez et servez les fichiers
            send_message(sender_id, f"Vidéo téléchargée avec succès! Voici le chemin: {video_path_or_url}")
            # Ici, vous devriez implémenter la logique pour envoyer le fichier vidéo
            
            return True
        
        # Message par défaut
        send_message(sender_id, "Je ne comprends pas cette commande. Envoyez 'aide' pour voir les commandes disponibles.")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        send_message(sender_id, "Désolé, une erreur s'est produite lors du traitement de votre message. Veuillez réessayer plus tard.")
        return False


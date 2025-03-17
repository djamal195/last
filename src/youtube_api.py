import os
import json
import requests
import traceback
import re
from typing import List, Dict, Optional, Any
import logging
import tempfile
import shutil
import uuid
import time
import io
from urllib.parse import parse_qs, urlparse

# Configuration du logger
from src.utils.logger import get_logger
logger = get_logger(__name__)

# Importer pytube pour le téléchargement de vidéos
try:
    from pytube import YouTube
    from pytube.exceptions import PytubeError, RegexMatchError
    PYTUBE_AVAILABLE = True
except ImportError:
    logger.warning("La bibliothèque pytube n'est pas installée. Le téléchargement de vidéos ne sera pas disponible.")
    PYTUBE_AVAILABLE = False

# Expression régulière pour valider les ID de vidéos YouTube
YOUTUBE_VIDEO_ID_REGEX = re.compile(r'^[0-9A-Za-z_-]{11}$')

class YouTubeAPI:
    """
    Classe pour interagir avec l'API YouTube
    """
    
    def __init__(self):
        """
        Initialise l'API YouTube avec la clé API depuis les variables d'environnement
        """
        self.api_key = os.environ.get('YOUTUBE_API_KEY')
        if not self.api_key:
            logger.error("Clé API YouTube manquante dans les variables d'environnement")
        
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def search_videos(self, query: str, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Recherche des vidéos YouTube en fonction d'une requête
        
        Args:
            query: Terme de recherche
            max_results: Nombre maximum de résultats à retourner
            
        Returns:
            Liste de vidéos ou None en cas d'erreur
        """
        if not self.api_key:
            logger.error("Impossible de rechercher des vidéos: clé API manquante")
            return None
            
        try:
            logger.info(f"Recherche YouTube pour: {query}")
            
            # Construire l'URL de recherche
            search_url = f"{self.base_url}/search"
            params = {
                "part": "snippet",
                "q": query,
                "maxResults": max_results,
                "type": "video",  # Spécifier explicitement que nous voulons uniquement des vidéos
                "key": self.api_key
            }
            
            # Effectuer la requête
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            
            # Analyser la réponse
            data = response.json()
            
            # Journaliser la structure complète de la réponse pour le débogage
            logger.info(f"Structure complète de la réponse YouTube: {json.dumps(data, indent=2)}")
            
            # Vérifier si des résultats ont été trouvés
            if 'items' not in data or not data['items']:
                logger.warning(f"Aucun résultat trouvé pour la recherche: {query}")
                return []
            
            # Extraire les informations des vidéos
            videos = []
            for i, item in enumerate(data['items']):
                try:
                    logger.info(f"Traitement de l'élément {i}: {json.dumps(item, indent=2)}")
                    
                    # Vérifier si c'est une vidéo ou un autre type d'élément
                    if 'id' not in item:
                        logger.warning(f"Élément sans 'id': {item}")
                        continue
                    
                    # Vérifier le type d'élément
                    if isinstance(item['id'], dict):
                        if 'kind' in item['id'] and item['id']['kind'] != 'youtube#video':
                            logger.warning(f"Élément ignoré car ce n'est pas une vidéo: {item['id']['kind']}")
                            continue
                        
                        if 'videoId' not in item['id']:
                            logger.warning(f"Clé 'videoId' manquante dans item['id']: {item['id']}")
                            continue
                        
                        video_id = item['id']['videoId']
                    elif isinstance(item['id'], str):
                        video_id = item['id']
                    else:
                        logger.warning(f"Format d'ID non reconnu: {type(item['id'])}")
                        continue
                    
                    # Valider l'ID de la vidéo
                    if not YOUTUBE_VIDEO_ID_REGEX.match(video_id):
                        logger.warning(f"ID de vidéo invalide: {video_id}")
                        continue
                    
                    # Extraire les autres informations avec vérification
                    snippet = item.get('snippet', {})
                    title = snippet.get('title', 'Titre non disponible')
                    description = snippet.get('description', 'Description non disponible')
                    
                    # Extraire la miniature avec vérification
                    thumbnails = snippet.get('thumbnails', {})
                    thumbnail_url = None
                    
                    # Essayer d'obtenir la miniature de haute qualité, puis moyenne, puis par défaut
                    for quality in ['high', 'medium', 'default']:
                        if quality in thumbnails and 'url' in thumbnails[quality]:
                            thumbnail_url = thumbnails[quality]['url']
                            break
                    
                    if not thumbnail_url:
                        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"  # URL basée sur l'ID
                    
                    # Créer un objet vidéo avec l'ID explicitement défini
                    video = {
                        'id': video_id,
                        'videoId': video_id,  # Ajouter explicitement videoId pour la compatibilité
                        'title': title,
                        'description': description,
                        'thumbnail': thumbnail_url,
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    }
                    
                    logger.info(f"Vidéo extraite avec succès: {json.dumps(video, indent=2)}")
                    videos.append(video)
                    
                except Exception as e:
                    logger.error(f"Erreur lors de l'extraction des informations de la vidéo: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
            
            logger.info(f"Recherche YouTube réussie: {len(videos)} vidéos trouvées")
            return videos
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de requête lors de la recherche YouTube: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de décodage JSON lors de la recherche YouTube: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche YouTube: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtient les détails d'une vidéo YouTube spécifique
        
        Args:
            video_id: ID de la vidéo YouTube
            
        Returns:
            Détails de la vidéo ou None en cas d'erreur
        """
        # Valider l'ID de la vidéo
        if not YOUTUBE_VIDEO_ID_REGEX.match(video_id):
            logger.error(f"ID de vidéo invalide: {video_id}")
            return None
            
        if not self.api_key:
            logger.error("Impossible d'obtenir les détails de la vidéo: clé API manquante")
            return None
            
        try:
            logger.info(f"Récupération des détails pour la vidéo: {video_id}")
            
            # Construire l'URL pour les détails de la vidéo
            video_url = f"{self.base_url}/videos"
            params = {
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
                "key": self.api_key
            }
            
            # Effectuer la requête
            response = requests.get(video_url, params=params)
            response.raise_for_status()
            
            # Analyser la réponse
            data = response.json()
            
            # Vérifier si des résultats ont été trouvés
            if 'items' not in data or not data['items']:
                logger.warning(f"Aucun détail trouvé pour la vidéo: {video_id}")
                return None
            
            # Extraire les détails de la vidéo
            video_data = data['items'][0]
            snippet = video_data.get('snippet', {})
            content_details = video_data.get('contentDetails', {})
            statistics = video_data.get('statistics', {})
            
            # Construire l'objet de détails
            video_details = {
                'id': video_id,
                'videoId': video_id,  # Ajouter explicitement videoId pour la compatibilité
                'title': snippet.get('title', 'Titre non disponible'),
                'description': snippet.get('description', 'Description non disponible'),
                'publishedAt': snippet.get('publishedAt', ''),
                'channelTitle': snippet.get('channelTitle', 'Chaîne inconnue'),
                'duration': content_details.get('duration', ''),
                'viewCount': statistics.get('viewCount', '0'),
                'likeCount': statistics.get('likeCount', '0'),
                'commentCount': statistics.get('commentCount', '0'),
                'url': f"https://www.youtube.com/watch?v={video_id}"
            }
            
            # Extraire la miniature avec vérification
            thumbnails = snippet.get('thumbnails', {})
            for quality in ['high', 'medium', 'default']:
                if quality in thumbnails and 'url' in thumbnails[quality]:
                    video_details['thumbnail'] = thumbnails[quality]['url']
                    break
            
            if 'thumbnail' not in video_details:
                video_details['thumbnail'] = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            
            logger.info(f"Détails récupérés avec succès pour la vidéo: {video_id}")
            return video_details
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de requête lors de la récupération des détails de la vidéo: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de décodage JSON lors de la récupération des détails de la vidéo: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la récupération des détails de la vidéo: {str(e)}")
            return None

# Créer une instance de l'API pour une utilisation facile
youtube_api = YouTubeAPI()

# Fonctions d'aide pour maintenir la compatibilité avec le code existant
def search_videos(query, max_results=5):
    """
    Fonction d'aide pour rechercher des vidéos YouTube
    """
    return youtube_api.search_videos(query, max_results)

def get_video_details(video_id):
    """
    Fonction d'aide pour obtenir les détails d'une vidéo
    """
    return youtube_api.get_video_details(video_id)

# Fonctions avec les noms originaux pour maintenir la compatibilité
def search_youtube(query, max_results=5):
    """
    Fonction d'aide pour rechercher des vidéos YouTube (nom original)
    
    Cette fonction est conçue pour être compatible avec le code existant.
    Elle s'assure que chaque vidéo dans les résultats a un champ 'videoId'.
    """
    try:
        logger.info(f"Appel de search_youtube avec query={query}, max_results={max_results}")
        videos = search_videos(query, max_results)
        
        if videos is None:
            logger.warning("search_videos a retourné None")
            return None
            
        # S'assurer que chaque vidéo a un champ 'videoId'
        for video in videos:
            if 'id' in video and 'videoId' not in video:
                video['videoId'] = video['id']
                
        logger.info(f"search_youtube a trouvé {len(videos)} vidéos")
        return videos
    except Exception as e:
        logger.error(f"Erreur dans search_youtube: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def _is_valid_youtube_id(video_id):
    """
    Vérifie si un ID de vidéo YouTube est valide
    
    Args:
        video_id: ID à vérifier
        
    Returns:
        True si l'ID est valide, False sinon
    """
    if not video_id or not isinstance(video_id, str):
        return False
        
    # Les ID de vidéos YouTube sont généralement des chaînes de 11 caractères
    # contenant des lettres, des chiffres, des tirets et des underscores
    return bool(YOUTUBE_VIDEO_ID_REGEX.match(video_id))

def _get_direct_url(video_id):
    """
    Tente d'obtenir une URL directe pour une vidéo YouTube
    
    Cette fonction est une méthode de secours qui tente d'obtenir une URL directe
    pour une vidéo YouTube en utilisant pytube.
    
    Args:
        video_id: ID de la vidéo YouTube
        
    Returns:
        URL directe ou None en cas d'erreur
    """
    if not PYTUBE_AVAILABLE:
        return None
        
    # Valider l'ID de la vidéo
    if not _is_valid_youtube_id(video_id):
        logger.error(f"ID de vidéo invalide: {video_id}")
        return None
        
    try:
        logger.info(f"Tentative d'obtention d'une URL directe pour la vidéo: {video_id}")
        
        # Construire l'URL de la vidéo
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Créer un objet YouTube
        yt = YouTube(video_url)
        
        # Obtenir le flux vidéo de la plus basse résolution pour éviter les problèmes de taille
        video_stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').first()
        
        if not video_stream:
            logger.warning(f"Aucun flux vidéo trouvé pour: {video_id}")
            return None
            
        # Obtenir l'URL directe
        direct_url = video_stream.url
        logger.info(f"URL directe obtenue: {direct_url}")
        return direct_url
        
    except RegexMatchError as e:
        logger.error(f"Erreur de correspondance regex lors de l'obtention de l'URL directe: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de l'obtention de l'URL directe: {str(e)}")
        return None

def _download_with_requests(url, output_path):
    """
    Télécharge un fichier à partir d'une URL en utilisant requests
    
    Args:
        url: URL du fichier à télécharger
        output_path: Chemin où enregistrer le fichier
        
    Returns:
        True si le téléchargement a réussi, False sinon
    """
    try:
        logger.info(f"Téléchargement du fichier depuis: {url}")
        logger.info(f"Vers: {output_path}")
        
        # Vérifier si le répertoire de destination existe
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Répertoire créé: {output_dir}")
        
        # Télécharger le fichier
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        # Vérifier les permissions d'écriture
        try:
            with open(output_path, 'wb') as f:
                f.write(b'test')
            os.remove(output_path)
            logger.info("Test d'écriture réussi")
        except Exception as e:
            logger.error(f"Erreur lors du test d'écriture: {str(e)}")
            # Essayer un autre répertoire
            output_path = os.path.join('/tmp', os.path.basename(output_path))
            logger.info(f"Nouvel emplacement de sortie: {output_path}")
        
        # Télécharger le fichier par morceaux pour éviter les problèmes de mémoire
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Vérifier que le fichier a été téléchargé
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Fichier téléchargé avec succès: {output_path} ({os.path.getsize(output_path)} octets)")
            return True
        else:
            logger.error(f"Le fichier téléchargé est vide ou n'existe pas: {output_path}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement avec requests: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def download_youtube_video(video_id, output_path=None):
    """
    Télécharge une vidéo YouTube
    
    Cette fonction tente de télécharger une vidéo YouTube en utilisant plusieurs méthodes:
    1. Utiliser pytube pour télécharger la vidéo directement
    2. Obtenir une URL directe avec pytube et télécharger avec requests
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée. Si None, un répertoire temporaire est utilisé.
        
    Returns:
        Chemin du fichier téléchargé ou None en cas d'erreur
    """
    logger.info(f"Début du téléchargement de la vidéo YouTube: {video_id}")
    logger.info(f"Chemin de sortie spécifié: {output_path}")
    
    # Valider l'ID de la vidéo
    if not _is_valid_youtube_id(video_id):
        logger.error(f"ID de vidéo invalide: {video_id}")
        return None
    
    # Vérifier l'environnement
    logger.info(f"Répertoire courant: {os.getcwd()}")
    logger.info(f"Contenu du répertoire courant: {os.listdir('.')}")
    logger.info(f"Répertoire temporaire: {tempfile.gettempdir()}")
    logger.info(f"Contenu du répertoire temporaire: {os.listdir(tempfile.gettempdir())}")
    
    # Déterminer le chemin de sortie
    if not output_path:
        try:
            # Essayer d'utiliser /tmp qui est généralement accessible en écriture
            temp_dir = '/tmp'
            if not os.path.exists(temp_dir):
                temp_dir = tempfile.gettempdir()
                
            # Générer un nom de fichier unique
            filename = f"youtube_{video_id}_{uuid.uuid4().hex[:8]}.mp4"
            output_path = os.path.join(temp_dir, filename)
            logger.info(f"Chemin de sortie généré: {output_path}")
        except Exception as e:
            logger.error(f"Erreur lors de la génération du chemin de sortie: {str(e)}")
            return None
    
    # Méthode 1: Utiliser pytube directement
    if PYTUBE_AVAILABLE:
        try:
            logger.info("Tentative de téléchargement avec pytube")
            
            # Construire l'URL de la vidéo
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Créer un objet YouTube
            yt = YouTube(video_url)
            
            # Obtenir le flux vidéo de la plus basse résolution pour éviter les problèmes de taille
            video_stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').first()
            
            if not video_stream:
                logger.warning(f"Aucun flux vidéo trouvé pour: {video_id}")
            else:
                # Télécharger la vidéo
                logger.info(f"Téléchargement de la vidéo vers: {output_path}")
                video_path = video_stream.download(output_path=os.path.dirname(output_path), filename=os.path.basename(output_path))
                
                # Vérifier que le fichier a été téléchargé
                if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                    logger.info(f"Vidéo téléchargée avec succès: {video_path} ({os.path.getsize(video_path)} octets)")
                    return video_path
                else:
                    logger.error(f"Le fichier téléchargé est vide ou n'existe pas: {video_path}")
        except RegexMatchError as e:
            logger.error(f"Erreur de correspondance regex lors du téléchargement avec pytube: {str(e)}")
            logger.error("Cela peut indiquer un ID de vidéo invalide ou un problème avec l'URL YouTube")
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement avec pytube: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    else:
        logger.warning("pytube n'est pas disponible, passage à la méthode alternative")
    
    # Méthode 2: Obtenir une URL directe et télécharger avec requests
    try:
        logger.info("Tentative de téléchargement avec URL directe et requests")
        
        # Obtenir une URL directe
        direct_url = _get_direct_url(video_id)
        
        if direct_url:
            # Télécharger la vidéo avec requests
            if _download_with_requests(direct_url, output_path):
                return output_path
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement avec URL directe: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Si toutes les méthodes ont échoué, retourner None
    logger.error("Toutes les méthodes de téléchargement ont échoué")
    return None


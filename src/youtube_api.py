import os
import json
import requests
import traceback
import re
import time
import random
import threading
import queue
from typing import List, Dict, Optional, Any, Tuple
import logging
import tempfile
import shutil
import uuid
import hashlib
from urllib.parse import parse_qs, urlparse

# Configuration du logger
from src.utils.logger import get_logger
logger = get_logger(__name__)

# Expression régulière pour valider les ID de vidéos YouTube
YOUTUBE_VIDEO_ID_REGEX = re.compile(r'^[0-9A-Za-z_-]{11}$')

# Configuration du rate limiting
MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # secondes
MAX_BACKOFF = 120  # secondes
MIN_REQUEST_INTERVAL = 10.0  # secondes entre les requêtes

# Cache simple pour les vidéos téléchargées
VIDEO_CACHE = {}
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'youtube_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Compteur global de requêtes pour limiter le nombre total
REQUEST_COUNT = 0
MAX_REQUESTS_PER_HOUR = 10

# Heure de la dernière réinitialisation du compteur
LAST_RESET_TIME = time.time()

# File d'attente pour les téléchargements
download_queue = queue.Queue()
MAX_CONCURRENT_DOWNLOADS = 2
current_downloads = 0
download_lock = threading.Lock()

def _check_rate_limit():
    """
    Vérifie si nous avons dépassé la limite de requêtes
    
    Returns:
        True si nous pouvons faire une requête, False sinon
    """
    global REQUEST_COUNT, LAST_RESET_TIME
    
    current_time = time.time()
    
    # Réinitialiser le compteur toutes les heures
    if current_time - LAST_RESET_TIME > 3600:
        logger.info("Réinitialisation du compteur de requêtes")
        REQUEST_COUNT = 0
        LAST_RESET_TIME = current_time
    
    # Vérifier si nous avons dépassé la limite
    if REQUEST_COUNT >= MAX_REQUESTS_PER_HOUR:
        logger.warning(f"Limite de requêtes atteinte ({MAX_REQUESTS_PER_HOUR} par heure)")
        return False
    
    # Incrémenter le compteur
    REQUEST_COUNT += 1
    return True

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
        self.last_request_time = 0
        self.min_request_interval = MIN_REQUEST_INTERVAL
    
    def _rate_limit_request(self):
        """
        Applique une limitation de débit pour éviter les erreurs 429
        """
        if not _check_rate_limit():
            raise Exception("Limite de requêtes atteinte")
            
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.info(f"Rate limiting: attente de {sleep_time:.2f} secondes")
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()
    
    def _make_request_with_retry(self, url, params=None, method='get'):
        """
        Effectue une requête HTTP avec retry et backoff exponentiel
        
        Args:
            url: URL de la requête
            params: Paramètres de la requête
            method: Méthode HTTP (get, post, etc.)
            
        Returns:
            Réponse de la requête ou None en cas d'erreur
        """
        retry_count = 0
        backoff = INITIAL_BACKOFF
        
        while retry_count <= MAX_RETRIES:
            try:
                # Appliquer la limitation de débit
                self._rate_limit_request()
                
                # Effectuer la requête
                if method.lower() == 'get':
                    response = requests.get(url, params=params, timeout=30)
                else:
                    response = requests.post(url, json=params, timeout=30)
                
                # Vérifier si la requête a réussi
                response.raise_for_status()
                return response
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    retry_count += 1
                    
                    if retry_count > MAX_RETRIES:
                        logger.error(f"Nombre maximum de tentatives atteint après erreur 429")
                        raise
                        
                    # Calculer le temps d'attente avec jitter
                    jitter = random.uniform(0, 0.1 * backoff)
                    wait_time = backoff + jitter
                    
                    logger.warning(f"Erreur 429 (Too Many Requests). Attente de {wait_time:.2f} secondes avant nouvelle tentative ({retry_count}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    
                    # Augmenter le backoff pour la prochaine tentative
                    backoff = min(backoff * 2, MAX_BACKOFF)
                else:
                    # Autres erreurs HTTP
                    logger.error(f"Erreur HTTP {e.response.status_code}: {str(e)}")
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur de requête: {str(e)}")
                raise
    
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
            
            # Effectuer la requête avec retry
            try:
                response = self._make_request_with_retry(search_url, params=params)
            except Exception as e:
                logger.error(f"Erreur lors de la requête de recherche: {str(e)}")
                return None
            
            # Analyser la réponse
            data = response.json()
            
            # Vérifier si des résultats ont été trouvés
            if 'items' not in data or not data['items']:
                logger.warning(f"Aucun résultat trouvé pour la recherche: {query}")
                return []
            
            # Extraire les informations des vidéos
            videos = []
            for i, item in enumerate(data['items']):
                try:
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
            
            # Effectuer la requête avec retry
            try:
                response = self._make_request_with_retry(video_url, params=params)
            except Exception as e:
                logger.error(f"Erreur lors de la requête de détails: {str(e)}")
                return None
            
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

    def get_stream_url(self, video_id: str) -> Optional[str]:
        """
        Obtient l'URL de streaming d'une vidéo YouTube en utilisant l'API
        
        Args:
            video_id: ID de la vidéo YouTube
            
        Returns:
            URL de streaming ou None en cas d'erreur
        """
        # Valider l'ID de la vidéo
        if not YOUTUBE_VIDEO_ID_REGEX.match(video_id):
            logger.error(f"ID de vidéo invalide: {video_id}")
            return None
            
        if not self.api_key:
            logger.error("Impossible d'obtenir l'URL de streaming: clé API manquante")
            return None
            
        try:
            logger.info(f"Récupération de l'URL de streaming pour la vidéo: {video_id}")
            
            # Utiliser l'API YouTube pour obtenir les détails de la vidéo
            video_details = self.get_video_details(video_id)
            
            if not video_details:
                logger.warning(f"Aucun détail trouvé pour la vidéo: {video_id}")
                return None
            
            # Construire l'URL de la vidéo
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Utiliser youtube-dl ou yt-dlp pour obtenir l'URL de streaming
            # Cela nécessite d'installer youtube-dl ou yt-dlp
            # Pour l'instant, nous retournons simplement l'URL YouTube
            
            logger.info(f"URL de streaming obtenue pour la vidéo: {video_id}")
            return video_url
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'URL de streaming: {str(e)}")
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

def _get_cache_path(video_id):
    """
    Obtient le chemin du fichier cache pour une vidéo
    
    Args:
        video_id: ID de la vidéo YouTube
        
    Returns:
        Chemin du fichier cache
    """
    return os.path.join(CACHE_DIR, f"{video_id}.mp4")

def _is_in_cache(video_id):
    """
    Vérifie si une vidéo est dans le cache
    
    Args:
        video_id: ID de la vidéo YouTube
        
    Returns:
        True si la vidéo est dans le cache, False sinon
    """
    cache_path = _get_cache_path(video_id)
    return os.path.exists(cache_path) and os.path.getsize(cache_path) > 0

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

def _process_download_queue():
    """
    Traite la file d'attente des téléchargements
    """
    global current_downloads
    
    while True:
        try:
            # Récupérer un élément de la file d'attente
            video_id, output_path, callback = download_queue.get(block=True, timeout=1)
            
            with download_lock:
                current_downloads += 1
            
            try:
                # Télécharger la vidéo
                result = _download_video(video_id, output_path)
                
                # Appeler le callback avec le résultat
                if callback:
                    callback(result)
                    
            except Exception as e:
                logger.error(f"Erreur lors du traitement du téléchargement: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Appeler le callback avec None en cas d'erreur
                if callback:
                    callback(None)
            
            finally:
                # Marquer la tâche comme terminée
                download_queue.task_done()
                
                with download_lock:
                    current_downloads -= 1
                
        except queue.Empty:
            # La file d'attente est vide, attendre un peu
            time.sleep(1)
        except Exception as e:
            logger.error(f"Erreur dans le thread de traitement de la file d'attente: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            time.sleep(5)  # Attendre un peu avant de réessayer

def _download_video(video_id, output_path=None):
    """
    Télécharge une vidéo YouTube (implémentation interne)
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        
    Returns:
        Chemin du fichier téléchargé, URL YouTube en cas d'erreur, ou None en cas d'erreur
    """
    logger.info(f"Début du téléchargement de la vidéo YouTube: {video_id}")
    logger.info(f"Chemin de sortie spécifié: {output_path}")
    
    # Valider l'ID de la vidéo
    if not _is_valid_youtube_id(video_id):
        logger.error(f"ID de vidéo invalide: {video_id}")
        return None
    
    # Vérifier si la vidéo est dans le cache
    if _is_in_cache(video_id):
        cache_path = _get_cache_path(video_id)
        logger.info(f"Vidéo trouvée dans le cache: {cache_path}")
        
        # Si un chemin de sortie est spécifié, copier le fichier
        if output_path:
            try:
                shutil.copy2(cache_path, output_path)
                logger.info(f"Vidéo copiée du cache vers: {output_path}")
                return output_path
            except Exception as e:
                logger.error(f"Erreur lors de la copie du cache: {str(e)}")
                return cache_path
        else:
            return cache_path
    
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
    
    # Vérifier si nous avons atteint la limite de requêtes
    if not _check_rate_limit():
        logger.warning("Limite de requêtes atteinte, retour de l'URL YouTube")
        return f"https://www.youtube.com/watch?v={video_id}"
    
    # Ajouter un délai aléatoire pour éviter les erreurs 429
    random_delay = random.uniform(1, 3)
    logger.info(f"Ajout d'un délai aléatoire de {random_delay:.2f} secondes avant le téléchargement")
    time.sleep(random_delay)
    
    # Utiliser l'API YouTube pour obtenir les détails de la vidéo
    try:
        # Obtenir l'URL de streaming
        stream_url = youtube_api.get_stream_url(video_id)
        
        if not stream_url:
            logger.warning(f"Impossible d'obtenir l'URL de streaming pour la vidéo: {video_id}")
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Si l'URL de streaming est l'URL YouTube, la retourner directement
        if stream_url.startswith("https://www.youtube.com/watch"):
            logger.info(f"URL de streaming est l'URL YouTube, retour de l'URL: {stream_url}")
            return stream_url
        
        # Télécharger la vidéo avec requests
        if _download_with_requests(stream_url, output_path):
            # Ajouter au cache
            try:
                cache_path = _get_cache_path(video_id)
                shutil.copy2(output_path, cache_path)
                logger.info(f"Vidéo ajoutée au cache: {cache_path}")
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout au cache: {str(e)}")
            
            return output_path
        else:
            logger.error(f"Échec du téléchargement de la vidéo avec requests")
            return f"https://www.youtube.com/watch?v={video_id}"
            
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de la vidéo: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"https://www.youtube.com/watch?v={video_id}"

def download_youtube_video(video_id, output_path=None, callback=None):
    """
    Télécharge une vidéo YouTube en utilisant un système de file d'attente
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        callback: Fonction à appeler avec le résultat du téléchargement
        
    Returns:
        True si le téléchargement a été ajouté à la file d'attente, False sinon
    """
    global current_downloads
    
    try:
        # Vérifier si la vidéo est dans le cache
        if _is_in_cache(video_id):
            cache_path = _get_cache_path(video_id)
            logger.info(f"Vidéo trouvée dans le cache: {cache_path}")
            
            # Si un chemin de sortie est spécifié, copier le fichier
            if output_path:
                try:
                    shutil.copy2(cache_path, output_path)
                    logger.info(f"Vidéo copiée du cache vers: {output_path}")
                    
                    # Appeler le callback avec le résultat
                    if callback:
                        callback(output_path)
                    
                    return True
                except Exception as e:
                    logger.error(f"Erreur lors de la copie du cache: {str(e)}")
                    
                    # Appeler le callback avec le chemin du cache
                    if callback:
                        callback(cache_path)
                    
                    return True
            else:
                # Appeler le callback avec le chemin du cache
                if callback:
                    callback(cache_path)
                
                return True
        
        # Vérifier si nous avons atteint le nombre maximum de téléchargements simultanés
        with download_lock:
            if current_downloads >= MAX_CONCURRENT_DOWNLOADS:
                logger.warning(f"Nombre maximum de téléchargements simultanés atteint ({MAX_CONCURRENT_DOWNLOADS})")
                
                # Ajouter à la file d'attente
                download_queue.put((video_id, output_path, callback))
                logger.info(f"Téléchargement ajouté à la file d'attente: {video_id}")
                
                return True
            
            # Ajouter à la file d'attente
            download_queue.put((video_id, output_path, callback))
            logger.info(f"Téléchargement ajouté à la file d'attente: {video_id}")
            
            return True
            
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du téléchargement à la file d'attente: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Appeler le callback avec None en cas d'erreur
        if callback:
            callback(None)
        
        return False

# Démarrer le thread de traitement de la file d'attente
download_thread = threading.Thread(target=_process_download_queue, daemon=True)
download_thread.start()


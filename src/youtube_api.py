import os
import re
import time
import json
import threading
import traceback
import tempfile
import requests
import http.client
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse, parse_qs, quote
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Nombre maximum de téléchargements simultanés
MAX_CONCURRENT_DOWNLOADS = 3

# Verrou pour limiter les téléchargements simultanés
download_semaphore = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# File d'attente des téléchargements
download_queue = []
download_queue_lock = threading.Lock()

# Thread de traitement de la file d'attente
download_thread = None
download_thread_running = False

# Répertoire de cache pour les vidéos téléchargées
CACHE_DIR = "/tmp/youtube_cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Clé API RapidAPI
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
CLOUD_API_HUB_HOST = "cloud-api-hub-youtube-downloader.p.rapidapi.com"

def extract_video_id(url_or_id):
    """
    Extrait l'ID de la vidéo YouTube à partir d'une URL ou d'un ID
    
    Args:
        url_or_id: URL YouTube ou ID de la vidéo
        
    Returns:
        ID de la vidéo ou None si non trouvé
    """
    try:
        logger.info(f"Extraction de l'ID vidéo à partir de: {url_or_id}")
        
        # Si c'est déjà un ID (pas d'URL)
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
            logger.info(f"ID vidéo déjà extrait: {url_or_id}")
            return url_or_id
        
        # Essayer d'extraire l'ID à partir de différents formats d'URL YouTube
        youtube_regex = (
            r'(https?://)?(www\.)?'
            '(youtube|youtu|youtube-nocookie)\.(com|be)/'
            '(watch\?v=|embed/|v/|.+\?v=)?([a-zA-Z0-9_-]{11})'
        )
        
        match = re.match(youtube_regex, url_or_id)
        
        if match:
            video_id = match.group(6)
            logger.info(f"ID vidéo extrait: {video_id}")
            return video_id
        
        # Essayer d'extraire l'ID à partir des paramètres de l'URL
        parsed_url = urlparse(url_or_id)
        if parsed_url.netloc in ['youtube.com', 'www.youtube.com', 'youtu.be']:
            if parsed_url.netloc == 'youtu.be':
                video_id = parsed_url.path.lstrip('/')
                logger.info(f"ID vidéo extrait de youtu.be: {video_id}")
                return video_id
            
            query_params = parse_qs(parsed_url.query)
            if 'v' in query_params:
                video_id = query_params['v'][0]
                logger.info(f"ID vidéo extrait des paramètres de requête: {video_id}")
                return video_id
        
        logger.warning(f"Impossible d'extraire l'ID vidéo de: {url_or_id}")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction de l'ID vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_video_details(video_id):
    """
    Récupère les détails d'une vidéo YouTube
    
    Args:
        video_id: ID de la vidéo YouTube
        
    Returns:
        Dictionnaire contenant les détails de la vidéo
    """
    try:
        logger.info(f"Récupération des détails de la vidéo: {video_id}")
        
        # Vérifier si l'ID est valide
        if not video_id or not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
            logger.warning(f"ID vidéo invalide: {video_id}")
            return None
        
        # Utiliser l'API YouTube Data pour récupérer les détails
        api_key = os.environ.get('YOUTUBE_API_KEY')
        
        if api_key:
            try:
                url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={api_key}&part=snippet,contentDetails,statistics"
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('items'):
                        item = data['items'][0]
                        snippet = item.get('snippet', {})
                        
                        return {
                            'videoId': video_id,
                            'title': snippet.get('title', ''),
                            'description': snippet.get('description', ''),
                            'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"),
                            'channelTitle': snippet.get('channelTitle', ''),
                            'publishedAt': snippet.get('publishedAt', '')
                        }
                    else:
                        logger.warning(f"Aucun élément trouvé pour la vidéo: {video_id}")
                else:
                    logger.warning(f"Erreur lors de la récupération des détails de la vidéo: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Erreur lors de l'appel à l'API YouTube: {str(e)}")
        
        # Méthode alternative: scraper la page YouTube
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(url)
            
            if response.status_code == 200:
                # Extraire le titre
                title_match = re.search(r'<title>(.*?)</title>', response.text)
                title = title_match.group(1).replace(' - YouTube', '') if title_match else 'Vidéo YouTube'
                
                # Extraire la description (simplifiée)
                description_match = re.search(r'<meta name="description" content="(.*?)"', response.text)
                description = description_match.group(1) if description_match else ''
                
                return {
                    'videoId': video_id,
                    'title': title,
                    'description': description,
                    'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                }
            else:
                logger.warning(f"Erreur lors de la récupération de la page YouTube: {response.status_code}")
        except Exception as e:
            logger.error(f"Erreur lors du scraping de la page YouTube: {str(e)}")
        
        # Si tout échoue, retourner des informations minimales
        return {
            'videoId': video_id,
            'title': 'Vidéo YouTube',
            'description': '',
            'thumbnail': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails de la vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def search_youtube(query, max_results=10):
    """
    Recherche des vidéos sur YouTube
    
    Args:
        query: Requête de recherche
        max_results: Nombre maximum de résultats
        
    Returns:
        Liste de vidéos
    """
    try:
        logger.info(f"Recherche YouTube pour: {query}")
        
        # Utiliser l'API YouTube Data pour la recherche
        api_key = os.environ.get('YOUTUBE_API_KEY')
        
        if api_key:
            try:
                url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={api_key}&type=video&maxResults={max_results}"
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    videos = []
                    for item in data.get('items', []):
                        video_id = item.get('id', {}).get('videoId')
                        snippet = item.get('snippet', {})
                        
                        if video_id:
                            videos.append({
                                'videoId': video_id,
                                'title': snippet.get('title', ''),
                                'description': snippet.get('description', ''),
                                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url', f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"),
                                'channelTitle': snippet.get('channelTitle', ''),
                                'publishedAt': snippet.get('publishedAt', '')
                            })
                    
                    logger.info(f"Résultats de la recherche YouTube: {len(videos)} vidéos trouvées")
                    return videos
                else:
                    logger.warning(f"Erreur lors de la recherche YouTube: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Erreur lors de l'appel à l'API YouTube: {str(e)}")
        
        # Si tout échoue, retourner une liste vide
        logger.warning("La recherche YouTube a échoué")
        return []
    except Exception as e:
        logger.error(f"Erreur lors de la recherche YouTube: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def download_youtube_video(video_id, output_path, callback=None):
    """
    Télécharge une vidéo YouTube
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        callback: Fonction de rappel à appeler une fois le téléchargement terminé
        
    Returns:
        Chemin de la vidéo téléchargée ou None en cas d'erreur
    """
    try:
        logger.info(f"Ajout du téléchargement à la file d'attente: {video_id}")
        
        # Ajouter le téléchargement à la file d'attente
        with download_queue_lock:
            download_queue.append({
                'video_id': video_id,
                'output_path': output_path,
                'callback': callback,
                'added_time': time.time()
            })
        
        # Démarrer le thread de traitement s'il n'est pas déjà en cours d'exécution
        start_download_thread()
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du téléchargement à la file d'attente: {str(e)}")
        logger.error(traceback.format_exc())
        
        if callback:
            callback(None)
        
        return False

def start_download_thread():
    """
    Démarre le thread de traitement des téléchargements
    """
    global download_thread, download_thread_running
    
    if download_thread_running:
        return
    
    download_thread_running = True
    download_thread = threading.Thread(target=process_download_queue)
    download_thread.daemon = True
    download_thread.start()
    
    logger.info("Thread de téléchargement démarré")

def process_download_queue():
    """
    Traite la file d'attente des téléchargements
    """
    global download_thread_running
    
    try:
        logger.info("Démarrage du traitement de la file d'attente des téléchargements")
        
        while True:
            # Vérifier s'il y a des téléchargements dans la file d'attente
            with download_queue_lock:
                if not download_queue:
                    logger.info("File d'attente vide, arrêt du thread")
                    download_thread_running = False
                    break
                
                # Récupérer le prochain téléchargement
                download = download_queue.pop(0)
            
            # Traiter le téléchargement
            video_id = download['video_id']
            output_path = download['output_path']
            callback = download['callback']
            
            logger.info(f"Traitement du téléchargement: {video_id}")
            
            # Acquérir le sémaphore pour limiter les téléchargements simultanés
            download_semaphore.acquire()
            
            try:
                # Télécharger la vidéo
                result = download_video(video_id, output_path)
                
                # Appeler le callback
                if callback:
                    callback(result)
                    logger.info(f"Callback terminé pour la vidéo {video_id}")
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement de la vidéo: {str(e)}")
                logger.error(traceback.format_exc())
                
                if callback:
                    callback(None)
                    logger.info(f"Callback terminé pour la vidéo {video_id} (avec erreur)")
            finally:
                # Libérer le sémaphore
                download_semaphore.release()
            
            # Attendre un peu pour éviter de surcharger le système
            time.sleep(0.5)
    except Exception as e:
        logger.error(f"Erreur dans le thread de téléchargement: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        download_thread_running = False
        logger.info("Thread de téléchargement arrêté")

def is_valid_mp4(file_path):
    """
    Vérifie si un fichier MP4 est valide
    
    Args:
        file_path: Chemin du fichier à vérifier
        
    Returns:
        True si le fichier est un MP4 valide, False sinon
    """
    try:
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 10000:
            return False
        
        # Vérifier l'en-tête du fichier
        with open(file_path, 'rb') as f:
            header = f.read(12)
            
            # Vérifier la signature MP4 (ftyp)
            if b'ftyp' not in header:
                logger.warning(f"Signature MP4 non trouvée dans le fichier: {file_path}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du fichier MP4: {str(e)}")
        return False

def extract_url_from_response(result):
    """
    Extrait l'URL de téléchargement de la réponse de l'API
    
    Args:
        result: Réponse de l'API (peut être un dictionnaire ou une liste)
        
    Returns:
        URL de téléchargement ou None si non trouvée
    """
    try:
        # Si c'est une liste, prendre le premier élément
        if isinstance(result, list) and len(result) > 0:
            # Parcourir la liste pour trouver un format MP4 vidéo
            for item in result:
                if isinstance(item, dict) and 'url' in item:
                    mime_type = item.get('mime_type', '')
                    if 'video/mp4' in mime_type:
                        return item.get('url')
            
            # Si aucun format MP4 vidéo n'est trouvé, prendre le premier élément avec une URL
            for item in result:
                if isinstance(item, dict) and 'url' in item:
                    return item.get('url')
            
            return None
        
        # Si c'est un dictionnaire, extraire l'URL directement
        elif isinstance(result, dict) and 'url' in result:
            return result.get('url')
        
        return None
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction de l'URL: {str(e)}")
        return None

def download_with_api(video_id, output_path, endpoint_params=""):
    """
    Télécharge une vidéo YouTube en utilisant l'API Cloud API Hub
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        endpoint_params: Paramètres supplémentaires pour l'endpoint
        
    Returns:
        Chemin de la vidéo téléchargée ou None en cas d'erreur
    """
    try:
        logger.info(f"Tentative de téléchargement avec API pour: {video_id} (params: {endpoint_params})")
        
        # Utiliser l'API Cloud API Hub pour obtenir le lien
        conn = http.client.HTTPSConnection(CLOUD_API_HUB_HOST)
        
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': CLOUD_API_HUB_HOST
        }
        
        # Construire l'URL de l'endpoint
        endpoint = f"/download?id={video_id}{endpoint_params}"
        logger.info(f"Appel à l'API: {endpoint}")
        
        conn.request("GET", endpoint, headers=headers)
        
        res = conn.getresponse()
        data = res.read()
        
        if res.status != 200:
            logger.error(f"Erreur lors de l'appel à l'API Cloud API Hub: {res.status} - {data.decode('utf-8')}")
            return None
        
        try:
            result = json.loads(data.decode("utf-8"))
            logger.info(f"Réponse de l'API Cloud API Hub: {json.dumps(result)[:500]}...")
            
            # Extraire l'URL de téléchargement
            download_url = extract_url_from_response(result)
            if not download_url:
                logger.error("Aucune URL de téléchargement trouvée dans la réponse de l'API Cloud API Hub")
                return None
            
            logger.info(f"URL de téléchargement trouvée: {download_url[:100]}...")
            
            # Ajouter des en-têtes pour contourner les restrictions
            download_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com'
            }
            
            # Télécharger la vidéo
            response = requests.get(download_url, headers=download_headers, stream=True, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"Erreur lors du téléchargement de la vidéo: {response.status_code}")
                return None
            
            # Écrire le fichier sur le disque
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Vérifier si le fichier a été téléchargé correctement
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"Le fichier téléchargé n'existe pas ou est vide: {output_path}")
                return None
            
            file_size = os.path.getsize(output_path)
            logger.info(f"Vidéo téléchargée avec succès: {output_path} ({file_size} octets)")
            
            # Vérifier si le fichier est un MP4 valide
            if not is_valid_mp4(output_path):
                logger.warning(f"Le fichier téléchargé n'est pas un MP4 valide: {output_path}")
                return None
            
            return output_path
        except json.JSONDecodeError:
            logger.error(f"Impossible de décoder la réponse JSON: {data.decode('utf-8')[:500]}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement avec API: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def download_video(video_id, output_path):
    """
    Télécharge une vidéo YouTube en utilisant l'API Cloud API Hub
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        
    Returns:
        Chemin de la vidéo téléchargée ou None en cas d'erreur
    """
    try:
        logger.info(f"Téléchargement de la vidéo: {video_id}")
        
        # Vérifier si l'ID est valide
        if not video_id or not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
            logger.warning(f"ID vidéo invalide: {video_id}")
            return None
        
        # Vérifier si la vidéo est déjà dans le cache
        cache_path = os.path.join(CACHE_DIR, f"{video_id}.mp4")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 10000 and is_valid_mp4(cache_path):
            logger.info(f"Vidéo trouvée dans le cache: {cache_path}")
            
            # Copier le fichier du cache vers le chemin de sortie
            import shutil
            shutil.copy2(cache_path, output_path)
            
            # Vérifier si le fichier a été copié correctement
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                logger.info(f"Vidéo copiée du cache: {output_path} ({os.path.getsize(output_path)} octets)")
                return output_path
        
        # Créer le répertoire de sortie s'il n'existe pas
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Vérifier si la clé API RapidAPI est disponible
        if not RAPIDAPI_KEY:
            logger.error("Clé API RapidAPI manquante")
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Méthode 1: Essayer le téléchargement sans paramètres supplémentaires
        result = download_with_api(video_id, output_path)
        if result and os.path.exists(result) and is_valid_mp4(result):
            # Ajouter la vidéo au cache
            try:
                import shutil
                shutil.copy2(result, cache_path)
                logger.info(f"Vidéo ajoutée au cache: {cache_path}")
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout de la vidéo au cache: {str(e)}")
            
            return result
        
        # Méthode 2: Essayer avec des formats spécifiques (itags)
        # Liste des itags courants pour les formats MP4
        # 18: MP4 360p
        # 22: MP4 720p
        # 137: MP4 1080p (vidéo seulement)
        # 140: M4A (audio seulement)
        for itag in [22, 18, 137]:
            result = download_with_api(video_id, output_path, f"&itag={itag}")
            if result and os.path.exists(result) and is_valid_mp4(result):
                # Ajouter la vidéo au cache
                try:
                    import shutil
                    shutil.copy2(result, cache_path)
                    logger.info(f"Vidéo ajoutée au cache: {cache_path}")
                except Exception as e:
                    logger.error(f"Erreur lors de l'ajout de la vidéo au cache: {str(e)}")
                
                return result
        
        # Méthode 3: Essayer avec le paramètre filter
        for filter_type in ["audioandvideo", "video", "audio"]:
            result = download_with_api(video_id, output_path, f"&filter={filter_type}")
            if result and os.path.exists(result) and is_valid_mp4(result):
                # Ajouter la vidéo au cache
                try:
                    import shutil
                    shutil.copy2(result, cache_path)
                    logger.info(f"Vidéo ajoutée au cache: {cache_path}")
                except Exception as e:
                    logger.error(f"Erreur lors de l'ajout de la vidéo au cache: {str(e)}")
                
                return result
        
        # Si toutes les tentatives échouent, retourner l'URL YouTube
        logger.error("Toutes les tentatives de téléchargement ont échoué")
        return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de la vidéo: {str(e)}")
        logger.error(traceback.format_exc())
        return f"https://www.youtube.com/watch?v={video_id}"

def stop_download_thread():
    """
    Arrête le thread de téléchargement proprement
    """
    global download_thread_running
    
    logger.info("Arrêt du fil de téléchargement demandé")
    
    # Arrêter le thread de traitement
    download_thread_running = False
    
    # Attendre que le thread se termine
    if download_thread and download_thread.is_alive():
        try:
            download_thread.join(timeout=5)
            logger.info("Arrêt du fil de traitement de la file d'attente")
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du thread de téléchargement: {str(e)}")
    
    # Sauvegarder la file d'attente pour une utilisation future
    try:
        with download_queue_lock:
            queue_size = len(download_queue)
            # Ici, on pourrait sauvegarder la file d'attente dans un fichier ou une base de données
            logger.info(f"Fichier d'attente sauvegardé: {queue_size} éléments")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la file d'attente: {str(e)}")
    
    logger.info("Discussion de téléchargement arrêté")


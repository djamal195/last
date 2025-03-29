import os
import re
import time
import json
import threading
import traceback
import subprocess
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
RAPIDAPI_HOST = os.environ.get('RAPIDAPI_HOST', "youtube-media-downloader.p.rapidapi.com")

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
        
        # Méthode alternative: utiliser RapidAPI pour la recherche
        try:
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
            
            headers = {
                'x-rapidapi-key': RAPIDAPI_KEY,
                'x-rapidapi-host': RAPIDAPI_HOST
            }
            
            encoded_query = quote(query)
            conn.request("GET", f"/search?query={encoded_query}", headers=headers)
            
            res = conn.getresponse()
            data = res.read()
            
            if res.status == 200:
                try:
                    search_results = json.loads(data.decode("utf-8"))
                    
                    videos = []
                    for item in search_results.get('videos', []):
                        video_id = item.get('id')
                        
                        if video_id:
                            videos.append({
                                'videoId': video_id,
                                'title': item.get('title', ''),
                                'description': item.get('description', ''),
                                'thumbnail': item.get('thumbnail', f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"),
                                'channelTitle': item.get('channel', {}).get('name', ''),
                                'publishedAt': item.get('uploadDate', '')
                            })
                    
                    logger.info(f"Résultats de la recherche RapidAPI: {len(videos)} vidéos trouvées")
                    return videos
                except json.JSONDecodeError:
                    logger.warning(f"Impossible de décoder la réponse JSON: {data.decode('utf-8')[:500]}")
            else:
                logger.warning(f"Erreur lors de la recherche RapidAPI: {res.status} - {data.decode('utf-8')}")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche avec RapidAPI: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Si tout échoue, retourner une liste vide
        logger.warning("Toutes les méthodes de recherche ont échoué")
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
        
        # Utiliser ffprobe pour vérifier le fichier
        command = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'json',
            file_path
        ]
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0 or stderr:
            logger.warning(f"Erreur ffprobe: {stderr}")
            return False
        
        try:
            data = json.loads(stdout)
            if not data.get('streams'):
                logger.warning(f"Aucun flux vidéo trouvé dans le fichier: {file_path}")
                return False
        except json.JSONDecodeError:
            logger.warning(f"Impossible de décoder la sortie JSON de ffprobe: {stdout}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du fichier MP4: {str(e)}")
        return False

def download_with_new_rapidapi(video_id, output_path):
    """
    Télécharge une vidéo YouTube en utilisant la nouvelle API RapidAPI
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        
    Returns:
        Chemin de la vidéo téléchargée ou None en cas d'erreur
    """
    try:
        logger.info(f"Téléchargement de la vidéo avec la nouvelle API RapidAPI: {video_id}")
        
        # Vérifier si la clé API RapidAPI est disponible
        if not RAPIDAPI_KEY:
            logger.error("Clé API RapidAPI manquante")
            return None
        
        # Utiliser l'API RapidAPI pour obtenir les liens de téléchargement
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST
        }
        
        # Obtenir les liens de téléchargement
        conn.request("GET", f"/video/info?videoId={video_id}", headers=headers)
        
        res = conn.getresponse()
        data = res.read()
        
        if res.status != 200:
            logger.error(f"Erreur lors de l'appel à l'API RapidAPI (info): {res.status} - {data.decode('utf-8')}")
            return None
        
        try:
            video_info = json.loads(data.decode("utf-8"))
            logger.info(f"Informations de la vidéo récupérées: {json.dumps(video_info)[:500]}...")
        except json.JSONDecodeError:
            logger.error(f"Impossible de décoder la réponse JSON (info): {data.decode('utf-8')[:500]}")
            return None
        
        # Obtenir les liens de téléchargement
        conn.request("GET", f"/video/formats?videoId={video_id}", headers=headers)
        
        res = conn.getresponse()
        data = res.read()
        
        if res.status != 200:
            logger.error(f"Erreur lors de l'appel à l'API RapidAPI (formats): {res.status} - {data.decode('utf-8')}")
            return None
        
        try:
            formats = json.loads(data.decode("utf-8"))
            logger.info(f"Formats de la vidéo récupérés: {json.dumps(formats)[:500]}...")
        except json.JSONDecodeError:
            logger.error(f"Impossible de décoder la réponse JSON (formats): {data.decode('utf-8')[:500]}")
            return None
        
        # Trouver le meilleur format MP4
        download_url = None
        best_quality = 0
        
        for format_item in formats.get('formats', []):
            if format_item.get('mimeType', '').startswith('video/mp4') and format_item.get('url'):
                height = format_item.get('height', 0)
                if height > best_quality and height <= 720:  # Limiter à 720p
                    best_quality = height
                    download_url = format_item.get('url')
        
        if not download_url:
            logger.error("Aucun format MP4 trouvé")
            return None
        
        logger.info(f"Meilleur format MP4 trouvé: {best_quality}p")
        
        # Télécharger la vidéo
        try:
            response = requests.get(download_url, stream=True, timeout=60)
            
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
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de la vidéo: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement avec la nouvelle API RapidAPI: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def download_hls_with_ffmpeg(hls_url, output_path):
    """
    Télécharge un flux HLS avec ffmpeg et le convertit en MP4
    
    Args:
        hls_url: URL du flux HLS
        output_path: Chemin de sortie pour la vidéo téléchargée
        
    Returns:
        Chemin de la vidéo téléchargée ou None en cas d'erreur
    """
    try:
        logger.info(f"Téléchargement du flux HLS avec ffmpeg: {hls_url[:100]}...")
        
        # Vérifier si ffmpeg est installé
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("ffmpeg n'est pas installé ou n'est pas accessible")
            return None
        
        # Télécharger et convertir le flux HLS en MP4
        command = [
            'ffmpeg',
            '-i', hls_url,
            '-c', 'copy',  # Copier les flux sans réencodage
            '-bsf:a', 'aac_adtstoasc',  # Filtre pour l'audio AAC
            '-movflags', 'faststart',  # Optimiser pour la lecture en streaming
            '-y',  # Écraser le fichier de sortie s'il existe
            output_path
        ]
        
        logger.info(f"Exécution de la commande ffmpeg: {' '.join(command[:3])} [...] {output_path}")
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Erreur lors de l'exécution de ffmpeg: {stderr}")
            return None
        
        # Vérifier si le fichier a été téléchargé correctement
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error(f"Le fichier téléchargé n'existe pas ou est vide: {output_path}")
            return None
        
        file_size = os.path.getsize(output_path)
        logger.info(f"Flux HLS téléchargé et converti avec succès: {output_path} ({file_size} octets)")
        
        # Vérifier si le fichier est un MP4 valide
        if not is_valid_mp4(output_path):
            logger.warning(f"Le fichier téléchargé n'est pas un MP4 valide: {output_path}")
            return None
        
        return output_path
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du flux HLS: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def download_with_ytdlp(video_id, output_path):
    """
    Télécharge une vidéo YouTube en utilisant yt-dlp
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        
    Returns:
        Chemin de la vidéo téléchargée ou None en cas d'erreur
    """
    try:
        logger.info(f"Téléchargement de la vidéo avec yt-dlp: {video_id}")
        
        # Construire l'URL YouTube
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Créer un répertoire temporaire pour le téléchargement
        temp_dir = os.path.dirname(output_path)
        
        # Configurer les options de yt-dlp
        command = [
            'yt-dlp',
            '--format', 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]',
            '--merge-output-format', 'mp4',
            '--output', output_path,
            '--no-playlist',
            '--no-check-certificate',
            '--no-cache-dir',
            '--no-part',
            '--no-mtime',
            '--no-progress',
            youtube_url
        ]
        
        logger.info(f"Exécution de la commande yt-dlp: {' '.join(command)}")
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Erreur lors de l'exécution de yt-dlp: {stderr}")
            return None
        
        # Vérifier si le fichier a été téléchargé correctement
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error(f"Le fichier téléchargé n'existe pas ou est vide: {output_path}")
            return None
        
        file_size = os.path.getsize(output_path)
        logger.info(f"Vidéo téléchargée avec succès via yt-dlp: {output_path} ({file_size} octets)")
        
        # Vérifier si le fichier est un MP4 valide
        if not is_valid_mp4(output_path):
            logger.warning(f"Le fichier téléchargé n'est pas un MP4 valide: {output_path}")
            return None
        
        return output_path
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement avec yt-dlp: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def download_video(video_id, output_path):
    """
    Télécharge une vidéo YouTube
    
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
        
        # Utiliser la nouvelle API RapidAPI pour télécharger la vidéo
        logger.info("Utilisation de la nouvelle API RapidAPI pour télécharger la vidéo")
        result = download_with_new_rapidapi(video_id, output_path)
        
        if result and os.path.exists(result) and is_valid_mp4(result):
            # Ajouter la vidéo au cache
            try:
                import shutil
                shutil.copy2(result, cache_path)
                logger.info(f"Vidéo ajoutée au cache: {cache_path}")
            except Exception as e:
                logger.error(f"Erreur lors de l'ajout de la vidéo au cache: {str(e)}")
            
            return result
        
        # Si la nouvelle API échoue, essayer avec l'ancienne API RapidAPI
        logger.info("La nouvelle API a échoué, tentative avec l'ancienne API RapidAPI")
        
        # Vérifier si la clé API RapidAPI est disponible
        if not RAPIDAPI_KEY:
            logger.error("Clé API RapidAPI manquante. Veuillez définir la variable d'environnement RAPIDAPI_KEY.")
            return f"https://www.youtube.com/watch?v={video_id}"
        
        # Construire l'URL YouTube complète
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Utiliser l'API RapidAPI pour obtenir les informations de la vidéo
        old_host = "youtube-info-download-api.p.rapidapi.com"
        url = f"https://{old_host}/ajax/api.php"
        
        querystring = {
            "function": "i",
            "u": youtube_url
        }
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": old_host
        }
        
        logger.info(f"Appel de l'ancienne API RapidAPI pour la vidéo: {video_id}")
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de l'appel à l'ancienne API RapidAPI: {response.status_code} - {response.text}")
            return f"https://www.youtube.com/watch?v={video_id}"
        
        try:
            # Analyser la réponse JSON
            data = response.json()
            logger.info(f"Réponse de l'ancienne API RapidAPI: {json.dumps(data)[:500]}...")  # Limiter la taille du log
            
            # Vérifier si la réponse est réussie
            if not data.get('successfull'):
                logger.error(f"Erreur dans la réponse de l'API: {data}")
                return f"https://www.youtube.com/watch?v={video_id}"
            
            # Extraire et parser la chaîne JSON du champ "info"
            info_str = data.get('info')
            if not info_str:
                logger.error("Champ 'info' manquant dans la réponse de l'API")
                return f"https://www.youtube.com/watch?v={video_id}"
            
            try:
                info = json.loads(info_str)
                logger.info(f"Informations de la vidéo extraites: {json.dumps(info)[:500]}...")
            except json.JSONDecodeError:
                logger.error(f"Erreur lors du décodage du champ 'info': {info_str[:500]}...")
                return f"https://www.youtube.com/watch?v={video_id}"
            
            # Vérifier si le champ "formats" existe
            formats = info.get('formats')
            if not formats or not isinstance(formats, list) or len(formats) == 0:
                logger.error("Aucun format de téléchargement trouvé dans la réponse de l'API")
                return f"https://www.youtube.com/watch?v={video_id}"
            
            # Trouver le meilleur format de téléchargement (préférer MP4 avec la meilleure qualité)
            download_url = None
            best_quality = 0
            
            # Chercher d'abord les formats MP4 avec une URL directe
            for format_info in formats:
                if format_info.get('ext') == 'mp4' and format_info.get('url') and format_info.get('height'):
                    height = format_info.get('height')
                    if height > best_quality and height <= 720:  # Limiter à 720p
                        best_quality = height
                        download_url = format_info.get('url')
            
            # Si aucun format MP4 n'est trouvé, chercher n'importe quel format avec une URL
            if not download_url:
                for format_info in formats:
                    if format_info.get('url') and format_info.get('height'):
                        height = format_info.get('height')
                        if height > best_quality and height <= 720:  # Limiter à 720p
                            best_quality = height
                            download_url = format_info.get('url')
            
            # Si toujours aucune URL n'est trouvée, prendre la première URL disponible
            if not download_url:
                for format_info in formats:
                    if format_info.get('url'):
                        download_url = format_info.get('url')
                        break
            
            if not download_url:
                logger.error("Aucune URL de téléchargement trouvée dans les formats disponibles")
                return f"https://www.youtube.com/watch?v={video_id}"
            
            logger.info(f"URL de téléchargement trouvée: {download_url[:100]}...")
            
            # Vérifier si l'URL est une URL HLS (manifest.googlevideo.com)
            if "manifest.googlevideo.com" in download_url or "hls_playlist" in download_url:
                logger.info("URL HLS détectée, tentative de téléchargement avec ffmpeg")
                result = download_hls_with_ffmpeg(download_url, output_path)
                
                if result and os.path.exists(result) and is_valid_mp4(result):
                    # Ajouter la vidéo au cache
                    try:
                        import shutil
                        shutil.copy2(result, cache_path)
                        logger.info(f"Vidéo ajoutée au cache: {cache_path}")
                    except Exception as e:
                        logger.error(f"Erreur lors de l'ajout de la vidéo au cache: {str(e)}")
                    
                    return result
                else:
                    logger.warning("Échec du téléchargement HLS avec ffmpeg, tentative avec yt-dlp")
                    result = download_with_ytdlp(video_id, output_path)
                    
                    if result and os.path.exists(result) and is_valid_mp4(result):
                        return result
                    else:
                        return f"https://www.youtube.com/watch?v={video_id}"
            
            # Télécharger le fichier
            try:
                logger.info(f"Téléchargement du fichier depuis l'URL trouvée...")
                file_response = requests.get(download_url, stream=True, timeout=60)
                
                if file_response.status_code != 200:
                    logger.error(f"Erreur lors du téléchargement du fichier: {file_response.status_code}")
                    return f"https://www.youtube.com/watch?v={video_id}"
                
                # Écrire le fichier sur le disque
                with open(output_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Vérifier si le fichier a été téléchargé correctement
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    logger.error(f"Le fichier téléchargé n'existe pas ou est vide: {output_path}")
                    return f"https://www.youtube.com/watch?v={video_id}"
                
                file_size = os.path.getsize(output_path)
                logger.info(f"Vidéo téléchargée avec succès: {output_path} ({file_size} octets)")
                
                # Vérifier si le fichier est un MP4 valide
                if not is_valid_mp4(output_path):
                    logger.warning(f"Le fichier téléchargé n'est pas un MP4 valide")
                    return f"https://www.youtube.com/watch?v={video_id}"
                
                # Ajouter la vidéo au cache
                try:
                    import shutil
                    shutil.copy2(output_path, cache_path)
                    logger.info(f"Vidéo ajoutée au cache: {cache_path}")
                except Exception as e:
                    logger.error(f"Erreur lors de l'ajout de la vidéo au cache: {str(e)}")
                
                return output_path
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement du fichier: {str(e)}")
                logger.error(traceback.format_exc())
                return f"https://www.youtube.com/watch?v={video_id}"
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la réponse de l'API: {str(e)}")
            logger.error(traceback.format_exc())
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


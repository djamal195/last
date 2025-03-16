from googleapiclient.discovery import build
import os
import tempfile
from pytube import YouTube
from src.config import YOUTUBE_API_KEY
from src.utils.logger import get_logger

logger = get_logger(__name__)

def search_youtube(query):
    """
    Recherche des vidéos sur YouTube
    """
    try:
        logger.info(f"Début de la recherche YouTube pour: {query}")
        
        # Créer un service YouTube
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Effectuer la recherche
        search_response = youtube.search().list(
            q=query,
            part='snippet',
            maxResults=5,
            type='video'
        ).execute()
        
        # Formater les résultats
        videos = []
        for item in search_response.get('items', []):
            videos.append({
                'title': item['snippet']['title'],
                'thumbnail': item['snippet']['thumbnails']['default']['url'],
                'videoId': item['id']['videoId']
            })
        
        logger.info(f"Résultat de la recherche YouTube: {len(videos)} vidéos trouvées")
        return videos
    except Exception as e:
        logger.error(f"Erreur détaillée lors de la recherche YouTube: {str(e)}")
        raise e

def download_youtube_video(video_id, temp_dir, max_duration=60, max_filesize=8*1024*1024):
    """
    Télécharge une vidéo YouTube et retourne le chemin du fichier
    
    Args:
        video_id (str): ID de la vidéo YouTube
        temp_dir (str): Répertoire temporaire pour stocker la vidéo
        max_duration (int): Durée maximale en secondes
        max_filesize (int): Taille maximale en octets
        
    Returns:
        str: Chemin du fichier vidéo téléchargé
    """
    try:
        logger.info(f"Début du téléchargement de la vidéo YouTube: {video_id}")
        
        # Construire l'URL de la vidéo
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Créer un objet YouTube
        yt = YouTube(video_url)
        
        # Vérifier la durée
        if yt.length > max_duration:
            logger.warning(f"Vidéo trop longue: {yt.length} secondes (max: {max_duration})")
            raise Exception(f"La vidéo est trop longue ({yt.length} secondes). Maximum autorisé: {max_duration} secondes.")
        
        # Obtenir le stream avec la plus basse résolution (pour réduire la taille)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').first()
        
        if not stream:
            logger.warning("Aucun stream compatible trouvé")
            raise Exception("Aucun format vidéo compatible n'a été trouvé.")
        
        # Vérifier la taille approximative
        if stream.filesize > max_filesize:
            logger.warning(f"Vidéo trop volumineuse: {stream.filesize} octets (max: {max_filesize})")
            raise Exception(f"La vidéo est trop volumineuse ({stream.filesize} octets). Maximum autorisé: {max_filesize} octets.")
        
        # Télécharger la vidéo
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        stream.download(output_path=temp_dir, filename=f"{video_id}.mp4")
        
        logger.info(f"Vidéo téléchargée avec succès: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de la vidéo: {str(e)}")
        raise e
import os
import json
import requests
from typing import List, Dict, Optional, Any
import logging

# Configuration du logger
from src.utils.logger import get_logger
logger = get_logger(__name__)

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
                "type": "video",
                "key": self.api_key
            }
            
            # Effectuer la requête
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            
            # Analyser la réponse
            data = response.json()
            
            # Journaliser la structure de la réponse pour le débogage
            logger.debug(f"Structure de la réponse YouTube: {json.dumps(data, indent=2)}")
            
            # Vérifier si des résultats ont été trouvés
            if 'items' not in data or not data['items']:
                logger.warning(f"Aucun résultat trouvé pour la recherche: {query}")
                return []
            
            # Extraire les informations des vidéos
            videos = []
            for item in data['items']:
                try:
                    # Extraire l'ID de la vidéo avec vérification de sécurité
                    if 'id' not in item:
                        logger.warning(f"Élément sans 'id': {item}")
                        continue
                        
                    video_id = None
                    if isinstance(item['id'], dict) and 'videoId' in item['id']:
                        video_id = item['id']['videoId']
                    elif isinstance(item['id'], str):
                        video_id = item['id']
                    else:
                        logger.warning(f"Format d'ID non reconnu: {item['id']}")
                        continue
                    
                    if not video_id:
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
                        thumbnail_url = "https://i.ytimg.com/vi/default/hqdefault.jpg"  # Image par défaut
                    
                    # Ajouter la vidéo à la liste
                    videos.append({
                        'id': video_id,
                        'title': title,
                        'description': description,
                        'thumbnail': thumbnail_url,
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    })
                    
                except KeyError as e:
                    logger.warning(f"Impossible d'extraire les informations de la vidéo: {str(e)}")
                    continue
            
            logger.info(f"Recherche YouTube réussie: {len(videos)} vidéos trouvées")
            return videos
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de requête lors de la recherche YouTube: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de décodage JSON lors de la recherche YouTube: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche YouTube: {str(e)}")
            return None
    
    def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtient les détails d'une vidéo YouTube spécifique
        
        Args:
            video_id: ID de la vidéo YouTube
            
        Returns:
            Détails de la vidéo ou None en cas d'erreur
        """
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
                video_details['thumbnail'] = "https://i.ytimg.com/vi/default/hqdefault.jpg"
            
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
    """
    return search_videos(query, max_results)

def download_youtube_video(video_id, output_path=None):
    """
    Fonction pour simuler le téléchargement d'une vidéo YouTube
    
    Note: Cette fonction est incluse pour maintenir la compatibilité avec le code existant,
    mais elle ne télécharge pas réellement la vidéo car cela nécessiterait des bibliothèques
    supplémentaires comme pytube ou youtube-dl.
    
    Args:
        video_id: ID de la vidéo YouTube
        output_path: Chemin de sortie pour la vidéo téléchargée
        
    Returns:
        Chemin du fichier téléchargé ou None en cas d'erreur
    """
    logger.warning("La fonction download_youtube_video est appelée mais n'est pas implémentée")
    logger.warning("Pour télécharger des vidéos, installez pytube ou youtube-dl et implémentez cette fonction")
    
    # Retourner None pour indiquer que le téléchargement a échoué
    return None


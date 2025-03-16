from pymongo import MongoClient
from src.database import get_database
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

class Video:
    """
    Modèle pour les vidéos YouTube
    """
    def __init__(self, video_id=None, title=None, cloudinary_url=None, thumbnail=None):
        self.video_id = video_id
        self.title = title
        self.cloudinary_url = cloudinary_url
        self.thumbnail = thumbnail
        self.created_at = datetime.now()
    
    def save(self):
        """
        Sauvegarde la vidéo dans la base de données
        
        Returns:
            str: ID de la vidéo sauvegardée
        """
        try:
            db = get_database()
            videos_collection = db.videos
            
            # Vérifier si la vidéo existe déjà
            existing_video = videos_collection.find_one({"video_id": self.video_id})
            if existing_video:
                # Mettre à jour la vidéo existante
                result = videos_collection.update_one(
                    {"video_id": self.video_id},
                    {"$set": {
                        "title": self.title,
                        "cloudinary_url": self.cloudinary_url,
                        "thumbnail": self.thumbnail,
                        "updated_at": datetime.now()
                    }}
                )
                logger.info(f"Vidéo mise à jour: {self.video_id}")
                return self.video_id
            else:
                # Créer une nouvelle vidéo
                video_data = {
                    "video_id": self.video_id,
                    "title": self.title,
                    "cloudinary_url": self.cloudinary_url,
                    "thumbnail": self.thumbnail,
                    "created_at": self.created_at
                }
                result = videos_collection.insert_one(video_data)
                logger.info(f"Nouvelle vidéo créée: {self.video_id}")
                return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la vidéo: {str(e)}")
            raise e
    
    @staticmethod
    def find_by_video_id(video_id):
        """
        Recherche une vidéo par son ID YouTube
        
        Args:
            video_id (str): ID YouTube de la vidéo
            
        Returns:
            dict: Données de la vidéo ou None si non trouvée
        """
        try:
            db = get_database()
            videos_collection = db.videos
            video = videos_collection.find_one({"video_id": video_id})
            return video
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de la vidéo: {str(e)}")
            return None
    
    @staticmethod
    def delete_by_video_id(video_id):
        """
        Supprime une vidéo par son ID YouTube
        
        Args:
            video_id (str): ID YouTube de la vidéo
            
        Returns:
            bool: True si la suppression a réussi, False sinon
        """
        try:
            db = get_database()
            videos_collection = db.videos
            result = videos_collection.delete_one({"video_id": video_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la vidéo: {str(e)}")
            return False
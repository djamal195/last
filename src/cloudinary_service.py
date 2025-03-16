import cloudinary
import cloudinary.uploader
import cloudinary.api
from src.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration de Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

def upload_file(file_path, public_id=None, resource_type="auto"):
    """
    Télécharge un fichier vers Cloudinary
    
    Args:
        file_path (str): Chemin du fichier à télécharger
        public_id (str, optional): Identifiant public pour le fichier
        resource_type (str, optional): Type de ressource (auto, image, video, raw)
        
    Returns:
        dict: Informations sur le fichier téléchargé
    """
    try:
        logger.info(f"Téléchargement du fichier {file_path} vers Cloudinary")
        result = cloudinary.uploader.upload(
            file_path,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=True,
            transformation=[
                {"width": 320, "crop": "scale"},
                {"quality": "auto:low"}
            ]
        )
        logger.info(f"Fichier téléchargé avec succès: {result['secure_url']}")
        return result
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du fichier: {str(e)}")
        raise e

def upload_stream(stream, public_id=None, resource_type="video"):
    """
    Télécharge un stream vers Cloudinary
    
    Args:
        stream (file-like object): Stream à télécharger
        public_id (str, optional): Identifiant public pour le fichier
        resource_type (str, optional): Type de ressource (auto, image, video, raw)
        
    Returns:
        dict: Informations sur le fichier téléchargé
    """
    try:
        logger.info(f"Téléchargement d'un stream vers Cloudinary")
        result = cloudinary.uploader.upload_stream(
            public_id=public_id,
            resource_type=resource_type,
            overwrite=True,
            transformation=[
                {"width": 320, "crop": "scale"},
                {"quality": "auto:low"},
                {"duration": 60}  # Limiter à 60 secondes
            ]
        )(stream.read())
        logger.info(f"Stream téléchargé avec succès: {result['secure_url']}")
        return result
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du stream: {str(e)}")
        raise e

def delete_resource(public_id, resource_type="video"):
    """
    Supprime une ressource de Cloudinary
    
    Args:
        public_id (str): Identifiant public de la ressource
        resource_type (str, optional): Type de ressource (image, video, raw)
        
    Returns:
        dict: Résultat de la suppression
    """
    try:
        logger.info(f"Suppression de la ressource {public_id} de Cloudinary")
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        logger.info(f"Ressource supprimée avec succès: {result}")
        return result
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la ressource: {str(e)}")
        raise e
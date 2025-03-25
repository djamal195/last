import os
import cloudinary
import cloudinary.uploader
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Initialiser Cloudinary avec les informations d'identification
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

def upload_file(file_path, public_id=None, resource_type="auto"):
    """
    Télécharge un fichier sur Cloudinary
    
    Args:
        file_path: Chemin du fichier à télécharger
        public_id: ID public pour le fichier (optionnel)
        resource_type: Type de ressource (auto, image, video, raw)
        
    Returns:
        Résultat du téléchargement
    """
    try:
        logger.info(f"Téléchargement du fichier {file_path} sur Cloudinary")
        
        # Vérifier si les informations d'identification sont configurées
        if not os.environ.get("CLOUDINARY_CLOUD_NAME") or not os.environ.get("CLOUDINARY_API_KEY") or not os.environ.get("CLOUDINARY_API_SECRET"):
            logger.error("Informations d'identification Cloudinary manquantes")
            return None
        
        # Vérifier si le fichier existe
        if not os.path.exists(file_path):
            logger.error(f"Le fichier n'existe pas: {file_path}")
            return None
            
        # Vérifier la taille du fichier
        file_size = os.path.getsize(file_path)
        logger.info(f"Taille du fichier: {file_size} octets")
        
        if file_size > 100 * 1024 * 1024:  # 100 MB
            logger.error(f"Le fichier est trop volumineux: {file_size} octets")
            return None
        
        # Télécharger le fichier
        upload_params = {
            "resource_type": resource_type,
            "chunk_size": 6000000,  # 6MB par chunk pour les gros fichiers
            "timeout": 120  # 2 minutes de timeout
        }
        
        if public_id:
            upload_params["public_id"] = public_id
        
        result = cloudinary.uploader.upload(file_path, **upload_params)
        
        logger.info(f"Fichier téléchargé avec succès: {result.get('public_id')}")
        logger.info(f"URL du fichier: {result.get('secure_url')}")
        return result
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
        return None


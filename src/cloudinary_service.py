import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
import mimetypes
import traceback
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Initialiser Cloudinary avec les informations d'identification
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

def _validate_file(file_path):
    """
    Valide un fichier avant le téléchargement
    
    Args:
        file_path: Chemin du fichier à valider
        
    Returns:
        Tuple (bool, str) indiquant si le fichier est valide et le type MIME
    """
    # Vérifier si le fichier existe
    if not os.path.exists(file_path):
        return False, f"Le fichier n'existe pas: {file_path}"
    
    # Vérifier la taille du fichier
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, f"Le fichier est vide: {file_path}"
    
    if file_size > 100 * 1024 * 1024:  # 100 MB
        return False, f"Le fichier est trop volumineux: {file_size} octets"
    
    # Vérifier le type MIME
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        # Si le type MIME ne peut pas être déterminé, essayer de le deviner à partir de l'extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.mp4', '.mov', '.avi', '.wmv', '.flv']:
            mime_type = f"video/{ext[1:]}"
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            mime_type = f"image/{ext[1:]}"
        else:
            mime_type = "application/octet-stream"
    
    logger.info(f"Type MIME du fichier: {mime_type}")
    
    # Vérifier si c'est un type de fichier supporté par Cloudinary
    supported_types = [
        'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-ms-wmv', 'video/x-flv',
        'image/jpeg', 'image/png', 'image/gif', 'image/webp'
    ]
    
    if mime_type not in supported_types:
        return False, f"Type de fichier non supporté: {mime_type}"
    
    return True, mime_type

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
        
        # Valider le fichier
        is_valid, message_or_mime = _validate_file(file_path)
        if not is_valid:
            logger.error(message_or_mime)
            return None
        
        # Vérifier la taille du fichier
        file_size = os.path.getsize(file_path)
        logger.info(f"Taille du fichier: {file_size} octets")
        
        # Déterminer le type de ressource si auto
        if resource_type == "auto":
            mime_type = message_or_mime
            if mime_type.startswith('video/'):
                resource_type = "video"
            elif mime_type.startswith('image/'):
                resource_type = "image"
            else:
                resource_type = "raw"
            
            logger.info(f"Type de ressource déterminé: {resource_type}")
        
        # Télécharger le fichier
        upload_params = {
            "resource_type": resource_type,
            "chunk_size": 6000000,  # 6MB par chunk pour les gros fichiers
            "timeout": 120,  # 2 minutes de timeout
            "use_filename": True,  # Utiliser le nom du fichier original
            "unique_filename": True,  # Ajouter un suffixe unique
            "overwrite": True,  # Écraser si le fichier existe déjà
            "invalidate": True  # Invalider le cache CDN
        }
        
        if public_id:
            upload_params["public_id"] = public_id
        
        try:
            result = cloudinary.uploader.upload(file_path, **upload_params)
            
            logger.info(f"Fichier téléchargé avec succès: {result.get('public_id')}")
            logger.info(f"URL du fichier: {result.get('secure_url')}")
            return result
        except Exception as e:
            logger.error(f"Erreur Cloudinary: {str(e)}")
            
            # Essayer avec un autre type de ressource si auto n'a pas fonctionné
            if resource_type != "raw":
                logger.info(f"Tentative avec le type de ressource 'raw'")
                upload_params["resource_type"] = "raw"
                try:
                    result = cloudinary.uploader.upload(file_path, **upload_params)
                    logger.info(f"Fichier téléchargé avec succès en tant que 'raw': {result.get('public_id')}")
                    logger.info(f"URL du fichier: {result.get('secure_url')}")
                    return result
                except Exception as e2:
                    logger.error(f"Erreur lors de la seconde tentative: {str(e2)}")
                    return None
            
            return None
            
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

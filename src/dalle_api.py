import os
import json
import http.client
import traceback
import base64
import tempfile
import requests
from typing import Optional, Dict, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration de l'API RapidAPI
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "chatgpt-42.p.rapidapi.com"

def generate_image(prompt: str, width: int = 512, height: int = 512) -> Optional[Dict[str, Any]]:
    """
    Génère une image à partir d'un texte en utilisant l'API DALL-E via RapidAPI
    
    Args:
        prompt: Texte décrivant l'image à générer
        width: Largeur de l'image (par défaut: 512)
        height: Hauteur de l'image (par défaut: 512)
        
    Returns:
        Dictionnaire contenant les informations de l'image générée ou None en cas d'erreur
    """
    try:
        logger.info(f"Génération d'image pour le prompt: {prompt}")
        
        # Créer la connexion HTTP
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        
        # Préparer les données de la requête
        payload = json.dumps({
            "text": prompt,
            "width": width,
            "height": height
        })
        
        # Préparer les en-têtes de la requête
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST,
            'Content-Type': "application/json"
        }
        
        # Envoyer la requête
        logger.info("Envoi de la requête à l'API DALL-E")
        conn.request("POST", "/texttoimage", payload, headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la génération d'image: {res.status} - {data.decode('utf-8', errors='ignore')}")
            return None
        
        # Décoder la réponse JSON
        response_data = json.loads(data.decode("utf-8"))
        logger.info("Image générée avec succès")
        
        # Journaliser la structure de la réponse pour le débogage
        logger.info(f"Structure de la réponse: {list(response_data.keys())}")
        
        return response_data
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def save_generated_image(image_data: Dict[str, Any]) -> Optional[str]:
    """
    Sauvegarde l'image générée dans un fichier temporaire
    
    Args:
        image_data: Données de l'image générée
        
    Returns:
        Chemin du fichier image ou None en cas d'erreur
    """
    try:
        # Journaliser les clés disponibles dans les données
        logger.info(f"Clés disponibles dans les données d'image: {list(image_data.keys())}")
        
        # Vérifier si les données contiennent une URL ou des données base64
        if "url" in image_data:
            logger.info(f"URL de l'image générée: {image_data['url']}")
            return image_data["url"]
        elif "b64_json" in image_data:
            # Créer un fichier temporaire pour l'image
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file_path = temp_file.name
            
            # Décoder les données base64 et les écrire dans le fichier
            image_bytes = base64.b64decode(image_data["b64_json"])
            with open(temp_file_path, "wb") as f:
                f.write(image_bytes)
            
            logger.info(f"Image sauvegardée dans: {temp_file_path}")
            return temp_file_path
        elif "data" in image_data:
            # Créer un fichier temporaire pour l'image
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file_path = temp_file.name
            
            # Vérifier si les données sont déjà en base64 ou non
            image_data_str = image_data["data"]
            if "base64," in image_data_str:
                # Extraire la partie base64 après "base64,"
                base64_data = image_data_str.split("base64,")[1]
            else:
                base64_data = image_data_str
            
            # Décoder les données base64 et les écrire dans le fichier
            try:
                image_bytes = base64.b64decode(base64_data)
                with open(temp_file_path, "wb") as f:
                    f.write(image_bytes)
                
                logger.info(f"Image sauvegardée dans: {temp_file_path}")
                return temp_file_path
            except Exception as e:
                logger.error(f"Erreur lors du décodage des données base64: {str(e)}")
                return None
        elif "image" in image_data:
            # Certaines API renvoient l'image dans une clé "image"
            image_content = image_data["image"]
            
            # Vérifier si c'est une URL
            if isinstance(image_content, str) and (image_content.startswith("http://") or image_content.startswith("https://")):
                logger.info(f"URL de l'image générée (clé 'image'): {image_content}")
                return image_content
            
            # Sinon, essayer de traiter comme base64
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file_path = temp_file.name
            
            try:
                # Vérifier si les données sont déjà en base64 ou non
                if isinstance(image_content, str):
                    if "base64," in image_content:
                        # Extraire la partie base64 après "base64,"
                        base64_data = image_content.split("base64,")[1]
                    else:
                        base64_data = image_content
                    
                    # Décoder les données base64 et les écrire dans le fichier
                    image_bytes = base64.b64decode(base64_data)
                    with open(temp_file_path, "wb") as f:
                        f.write(image_bytes)
                    
                    logger.info(f"Image sauvegardée dans: {temp_file_path}")
                    return temp_file_path
                else:
                    logger.error(f"Format de données d'image non reconnu dans la clé 'image': {type(image_content)}")
            except Exception as e:
                logger.error(f"Erreur lors du traitement de l'image: {str(e)}")
                logger.error(traceback.format_exc())
            
            return None
        elif "imageUrl" in image_data:
            # Certaines API renvoient l'URL dans une clé "imageUrl"
            logger.info(f"URL de l'image générée (clé 'imageUrl'): {image_data['imageUrl']}")
            return image_data["imageUrl"]
        elif "result" in image_data:
            # Certaines API encapsulent le résultat dans une clé "result"
            result = image_data["result"]
            if isinstance(result, dict):
                # Appel récursif avec le contenu de "result"
                return save_generated_image(result)
            elif isinstance(result, str):
                # Si result est une chaîne, c'est probablement une URL
                if result.startswith("http://") or result.startswith("https://"):
                    logger.info(f"URL de l'image générée (clé 'result'): {result}")
                    return result
                
                # Sinon, essayer de traiter comme base64
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_file_path = temp_file.name
                
                try:
                    if "base64," in result:
                        # Extraire la partie base64 après "base64,"
                        base64_data = result.split("base64,")[1]
                    else:
                        base64_data = result
                    
                    # Décoder les données base64 et les écrire dans le fichier
                    image_bytes = base64.b64decode(base64_data)
                    with open(temp_file_path, "wb") as f:
                        f.write(image_bytes)
                    
                    logger.info(f"Image sauvegardée dans: {temp_file_path}")
                    return temp_file_path
                except Exception as e:
                    logger.error(f"Erreur lors du décodage des données base64: {str(e)}")
            
            logger.error(f"Format de données non reconnu dans la clé 'result': {type(result)}")
            return None
        
        # Si aucun format reconnu n'est trouvé, essayer de télécharger l'image depuis une URL alternative
        # Certaines API RapidAPI renvoient l'URL dans une structure différente
        try:
            # Essayer de trouver une URL dans les données
            for key, value in image_data.items():
                if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
                    if ".jpg" in value or ".png" in value or ".jpeg" in value or ".webp" in value:
                        logger.info(f"URL d'image trouvée dans la clé '{key}': {value}")
                        return value
            
            # Si nous avons une réponse mais pas d'URL directe, essayer de télécharger l'image
            # Certaines API nécessitent un second appel pour obtenir l'image
            if "id" in image_data:
                image_id = image_data["id"]
                logger.info(f"ID d'image trouvé: {image_id}, tentative de récupération de l'image")
                
                # Ici, vous pourriez implémenter un appel spécifique à l'API pour récupérer l'image
                # par son ID, selon la documentation de l'API que vous utilisez
            
            # Journaliser toutes les données pour le débogage
            logger.info(f"Données d'image complètes: {json.dumps(image_data)}")
            
            logger.error("Format de données d'image non reconnu après analyse approfondie")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des données d'image: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def download_image_from_url(url: str) -> Optional[str]:
    """
    Télécharge une image à partir d'une URL
    
    Args:
        url: URL de l'image à télécharger
        
    Returns:
        Chemin du fichier image téléchargé ou None en cas d'erreur
    """
    try:
        logger.info(f"Téléchargement de l'image depuis: {url}")
        
        # Créer un fichier temporaire pour l'image
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        temp_file_path = temp_file.name
        
        # Télécharger l'image
        response = requests.get(url, stream=True, timeout=30)
        
        if response.status_code == 200:
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            logger.info(f"Image téléchargée et sauvegardée dans: {temp_file_path}")
            return temp_file_path
        else:
            logger.error(f"Erreur lors du téléchargement de l'image: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None


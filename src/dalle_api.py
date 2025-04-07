import os
import json
import http.client
import traceback
import base64
import tempfile
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
        # Vérifier si les données contiennent une URL ou des données base64
        if "url" in image_data:
            # TODO: Télécharger l'image depuis l'URL
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
        else:
            logger.error("Format de données d'image non reconnu")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None


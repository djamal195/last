import os
import json
import http.client
import traceback
import base64
import tempfile
import requests
import time
import threading
from typing import Optional, Dict, Any, Callable
from src.utils.logger import get_logger
from src.cloudinary_service import upload_file

logger = get_logger(__name__)

# Configuration de l'API RapidAPI
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "chatgpt-42.p.rapidapi.com"

# File d'attente pour les générations d'images
image_queue = []
image_queue_lock = threading.Lock()
image_thread = None
image_thread_running = False

# Nombre maximum de générations simultanées
MAX_CONCURRENT_GENERATIONS = 3
generation_semaphore = threading.Semaphore(MAX_CONCURRENT_GENERATIONS)

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
    Sauvegarde l'image générée dans un fichier temporaire ou retourne l'URL
    
    Args:
        image_data: Données de l'image générée
        
    Returns:
        Chemin du fichier image, URL de l'image, ou None en cas d'erreur
    """
    try:
        # Journaliser les clés disponibles dans les données
        logger.info(f"Clés disponibles dans les données d'image: {list(image_data.keys())}")
        
        # Vérifier si les données contiennent une URL dans "generated_image"
        if "generated_image" in image_data:
            image_url = image_data["generated_image"]
            logger.info(f"URL de l'image générée (clé 'generated_image'): {image_url}")
            
            # Télécharger l'image depuis l'URL
            return download_image_from_url(image_url)
        
        # Vérifier si les données contiennent une URL ou des données base64
        if "url" in image_data:
            logger.info(f"URL de l'image générée: {image_data['url']}")
            return download_image_from_url(image_data["url"])
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
                return download_image_from_url(image_content)
            
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
            return download_image_from_url(image_data["imageUrl"])
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
                    return download_image_from_url(result)
                
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
                    if ".jpg" in value or ".png" in value or ".jpeg" in value or ".webp" in value or "matagimage" in value:
                        logger.info(f"URL d'image trouvée dans la clé '{key}': {value}")
                        return download_image_from_url(value)
            
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        
        if response.status_code == 200:
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            # Vérifier que le fichier a été téléchargé correctement
            if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 100:
                logger.info(f"Image téléchargée et sauvegardée dans: {temp_file_path} ({os.path.getsize(temp_file_path)} octets)")
                return temp_file_path
            else:
                logger.error(f"Fichier téléchargé invalide ou trop petit: {temp_file_path} ({os.path.getsize(temp_file_path) if os.path.exists(temp_file_path) else 'N/A'} octets)")
                return None
        else:
            logger.error(f"Erreur lors du téléchargement de l'image: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def generate_and_upload_image(prompt: str, callback: Callable[[str], None]):
    """
    Ajoute une génération d'image à la file d'attente
    
    Args:
        prompt: Texte décrivant l'image à générer
        callback: Fonction à appeler une fois l'image générée et téléchargée
    """
    try:
        logger.info(f"Ajout de la génération d'image à la file d'attente: {prompt}")
        
        # Ajouter la génération à la file d'attente
        with image_queue_lock:
            image_queue.append({
                'prompt': prompt,
                'callback': callback,
                'added_time': time.time()
            })
        
        # Démarrer le thread de traitement s'il n'est pas déjà en cours d'exécution
        start_image_thread()
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de la génération d'image à la file d'attente: {str(e)}")
        logger.error(traceback.format_exc())
        
        if callback:
            callback(None)
        
        return False

def start_image_thread():
    """
    Démarre le thread de traitement des générations d'images
    """
    global image_thread, image_thread_running
    
    if image_thread_running:
        return
    
    image_thread_running = True
    image_thread = threading.Thread(target=process_image_queue)
    image_thread.daemon = True
    image_thread.start()
    
    logger.info("Thread de génération d'images démarré")

def process_image_queue():
    """
    Traite la file d'attente des générations d'images
    """
    global image_thread_running
    
    try:
        logger.info("Démarrage du traitement de la file d'attente des générations d'images")
        
        while True:
            # Vérifier s'il y a des générations dans la file d'attente
            with image_queue_lock:
                if not image_queue:
                    logger.info("File d'attente vide, arrêt du thread")
                    image_thread_running = False
                    break
                
                # Récupérer la prochaine génération
                generation = image_queue.pop(0)
            
            # Traiter la génération
            prompt = generation['prompt']
            callback = generation['callback']
            
            logger.info(f"Traitement de la génération d'image: {prompt}")
            
            # Acquérir le sémaphore pour limiter les générations simultanées
            generation_semaphore.acquire()
            
            try:
                # Générer l'image
                image_data = generate_image(prompt)
                
                if image_data:
                    # Sauvegarder l'image
                    image_path = save_generated_image(image_data)
                    
                    if image_path:
                        # Si c'est un chemin de fichier, télécharger sur Cloudinary
                        if os.path.exists(image_path):
                            try:
                                # Télécharger l'image sur Cloudinary
                                image_id = f"dalle_{int(time.time())}"
                                cloudinary_result = upload_file(image_path, image_id, "image")
                                
                                if cloudinary_result and cloudinary_result.get('secure_url'):
                                    image_url = cloudinary_result.get('secure_url')
                                    logger.info(f"Image téléchargée sur Cloudinary: {image_url}")
                                    
                                    # Appeler le callback avec l'URL Cloudinary
                                    if callback:
                                        callback(image_url)
                                else:
                                    logger.error("Échec du téléchargement sur Cloudinary")
                                    if callback:
                                        callback(image_path)
                            except Exception as e:
                                logger.error(f"Erreur lors du téléchargement sur Cloudinary: {str(e)}")
                                logger.error(traceback.format_exc())
                                if callback:
                                    callback(image_path)
                        else:
                            # Si c'est une URL, appeler directement le callback
                            if callback:
                                callback(image_path)
                    else:
                        logger.error("Échec de la sauvegarde de l'image")
                        if callback:
                            callback(None)
                else:
                    logger.error("Échec de la génération d'image")
                    if callback:
                        callback(None)
            except Exception as e:
                logger.error(f"Erreur lors de la génération d'image: {str(e)}")
                logger.error(traceback.format_exc())
                
                if callback:
                    callback(None)
            finally:
                # Libérer le sémaphore
                generation_semaphore.release()
            
            # Attendre un peu pour éviter de surcharger le système
            time.sleep(0.5)
    except Exception as e:
        logger.error(f"Erreur dans le thread de génération d'images: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        image_thread_running = False
        logger.info("Thread de génération d'images arrêté")

def stop_image_thread():
    """
    Arrête le thread de génération d'images proprement
    """
    global image_thread_running
    
    logger.info("Arrêt du thread de génération d'images demandé")
    
    # Arrêter le thread de traitement
    image_thread_running = False
    
    # Attendre que le thread se termine
    if image_thread and image_thread.is_alive():
        try:
            image_thread.join(timeout=5)
            logger.info("Thread de génération d'images arrêté")
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du thread de génération d'images: {str(e)}")
    
    # Sauvegarder la file d'attente pour une utilisation future
    try:
        with image_queue_lock:
            queue_size = len(image_queue)
            # Ici, on pourrait sauvegarder la file d'attente dans un fichier ou une base de données
            logger.info(f"File d'attente sauvegardée: {queue_size} éléments")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la file d'attente: {str(e)}")
    
    logger.info("Thread de génération d'images arrêté")


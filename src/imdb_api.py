import os
import json
import requests
import traceback
import re
import time
import tempfile
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.cloudinary_service import upload_file

logger = get_logger(__name__)

# Configuration de l'API RapidAPI pour IMDb
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "imdb8.p.rapidapi.com"

# Configuration pour l'API OMDb (alternative à IMDb)
OMDB_API_KEY = os.environ.get('OMDB_API_KEY', "8a59b5e9")
OMDB_API_URL = "http://www.omdbapi.com/"

# URL d'image par défaut (hébergée sur un domaine fiable)
DEFAULT_IMAGE_URL = "https://res.cloudinary.com/demo/image/upload/v1312461204/sample.jpg"

def search_imdb(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche des films et séries sur IMDb
    
    Args:
        query: Terme de recherche
        limit: Nombre maximum de résultats
        
    Returns:
        Liste de films et séries trouvés
    """
    try:
        logger.info(f"Recherche IMDb pour: {query}")
        
        # Essayer d'abord avec l'API OMDb qui est plus fiable pour les images
        omdb_results = search_omdb(query, limit)
        if omdb_results:
            logger.info(f"Résultats trouvés via OMDb: {len(omdb_results)}")
            return omdb_results
        
        # Si OMDb échoue, utiliser l'API IMDb
        logger.info("Aucun résultat via OMDb, essai avec l'API IMDb")
        
        # Préparer l'URL et les en-têtes pour l'API IMDb
        url = "https://imdb8.p.rapidapi.com/auto-complete"
        
        querystring = {"q": query}
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        # Faire la requête à l'API
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la recherche IMDb: {response.status_code} - {response.text}")
            return []
        
        # Analyser la réponse
        data = response.json()
        
        # Extraire les résultats
        results = []
        for item in data.get("d", [])[:limit]:
            # Déterminer le type (film ou série)
            item_type = "film"
            if item.get("qid") == "tvSeries" or item.get("q") == "TV series":
                item_type = "série"
            
            # Construire l'URL IMDb
            imdb_id = item.get("id", "")
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'image et s'assurer qu'elle est hébergée sur Cloudinary
            image_url = ""
            if "i" in item and isinstance(item["i"], dict) and "imageUrl" in item["i"]:
                original_image_url = item["i"]["imageUrl"]
                # Télécharger et héberger l'image sur Cloudinary
                image_url = ensure_cloudinary_image(original_image_url, imdb_id)
            
            # Si pas d'image, essayer d'obtenir l'image via OMDb
            if not image_url:
                omdb_details = get_omdb_details(imdb_id)
                if omdb_details and omdb_details.get("Poster") and omdb_details.get("Poster") != "N/A":
                    image_url = ensure_cloudinary_image(omdb_details.get("Poster"), imdb_id)
            
            # Si toujours pas d'image, utiliser une image par défaut
            if not image_url:
                image_url = DEFAULT_IMAGE_URL
            
            # Extraire les acteurs/réalisateurs
            stars = item.get("s", "")
            
            # Ajouter le résultat
            results.append({
                "title": item.get("l", "Titre inconnu"),
                "type": item_type,
                "imdb_id": imdb_id,
                "imdb_url": imdb_url,
                "image_url": image_url,
                "year": item.get("y", ""),
                "stars": stars
            })
        
        logger.info(f"Résultats de la recherche IMDb: {len(results)} trouvés")
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def search_omdb(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche des films et séries sur OMDb
    
    Args:
        query: Terme de recherche
        limit: Nombre maximum de résultats
        
    Returns:
        Liste de films et séries trouvés
    """
    try:
        logger.info(f"Recherche OMDb pour: {query}")
        
        # Préparer l'URL et les paramètres pour l'API OMDb
        params = {
            "apikey": OMDB_API_KEY,
            "s": query,
            "r": "json"
        }
        
        # Faire la requête à l'API
        response = requests.get(OMDB_API_URL, params=params)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la recherche OMDb: {response.status_code} - {response.text}")
            return []
        
        # Analyser la réponse
        data = response.json()
        
        # Vérifier si la recherche a réussi
        if data.get("Response") != "True" or "Search" not in data:
            logger.warning(f"Aucun résultat trouvé via OMDb: {data.get('Error', 'Raison inconnue')}")
            return []
        
        # Extraire les résultats
        results = []
        for item in data.get("Search", [])[:limit]:
            # Déterminer le type (film ou série)
            item_type = "film" if item.get("Type") == "movie" else "série"
            
            # Extraire l'ID IMDb
            imdb_id = item.get("imdbID", "")
            
            # Construire l'URL IMDb
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'image et s'assurer qu'elle est hébergée sur Cloudinary
            image_url = ""
            if item.get("Poster") and item.get("Poster") != "N/A":
                image_url = ensure_cloudinary_image(item.get("Poster"), imdb_id)
            
            # Si pas d'image, utiliser une image par défaut
            if not image_url:
                image_url = DEFAULT_IMAGE_URL
            
            # Ajouter le résultat
            results.append({
                "title": item.get("Title", "Titre inconnu"),
                "type": item_type,
                "imdb_id": imdb_id,
                "imdb_url": imdb_url,
                "image_url": image_url,
                "year": item.get("Year", ""),
                "stars": ""  # OMDb ne fournit pas cette information dans la recherche
            })
        
        logger.info(f"Résultats de la recherche OMDb: {len(results)} trouvés")
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche OMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def ensure_cloudinary_image(original_url: str, identifier: str) -> str:
    """
    S'assure qu'une image est hébergée sur Cloudinary
    
    Args:
        original_url: URL originale de l'image
        identifier: Identifiant unique pour l'image
        
    Returns:
        URL Cloudinary de l'image
    """
    try:
        if not original_url:
            return DEFAULT_IMAGE_URL
        
        logger.info(f"Téléchargement de l'image depuis: {original_url}")
        
        # Créer un fichier temporaire pour l'image
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        temp_file_path = temp_file.name
        
        # Télécharger l'image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(original_url, stream=True, timeout=10, headers=headers)
        
        if response.status_code == 200:
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            # Vérifier que le fichier a été téléchargé correctement
            if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 100:
                # Télécharger sur Cloudinary
                image_id = f"imdb_{identifier}_{int(time.time())}"
                cloudinary_result = upload_file(temp_file_path, image_id, "image")
                
                if cloudinary_result and cloudinary_result.get('secure_url'):
                    cloudinary_url = cloudinary_result.get('secure_url')
                    logger.info(f"Image téléchargée sur Cloudinary: {cloudinary_url}")
                    
                    # Nettoyer le fichier temporaire
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                    
                    return cloudinary_url
        
        # Si le téléchargement a échoué, utiliser une URL par défaut
        logger.warning(f"Échec du téléchargement de l'image, utilisation de l'URL par défaut")
        return DEFAULT_IMAGE_URL
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement de l'image: {str(e)}")
        logger.error(traceback.format_exc())
        return DEFAULT_IMAGE_URL

def get_imdb_details(imdb_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les détails d'un film ou d'une série sur IMDb
    
    Args:
        imdb_id: ID IMDb du film ou de la série
        
    Returns:
        Détails du film ou de la série
    """
    try:
        logger.info(f"Récupération des détails IMDb pour: {imdb_id}")
        
        # Essayer d'abord avec l'API OMDb qui est plus fiable
        omdb_details = get_omdb_details(imdb_id)
        if omdb_details:
            logger.info(f"Détails trouvés via OMDb pour {imdb_id}")
            
            # Convertir les détails OMDb au format attendu
            item_type = "film" if omdb_details.get("Type") == "movie" else "série"
            
            # Extraire l'image et s'assurer qu'elle est hébergée sur Cloudinary
            image_url = ""
            if omdb_details.get("Poster") and omdb_details.get("Poster") != "N/A":
                image_url = ensure_cloudinary_image(omdb_details.get("Poster"), imdb_id)
            
            # Si pas d'image, utiliser une image par défaut
            if not image_url:
                image_url = DEFAULT_IMAGE_URL
            
            return {
                "title": omdb_details.get("Title", ""),
                "type": item_type,
                "imdb_id": imdb_id,
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                "image_url": image_url,
                "year": omdb_details.get("Year", ""),
                "rating": omdb_details.get("imdbRating", ""),
                "plot": omdb_details.get("Plot", "")
            }
        
        # Si OMDb échoue, utiliser l'API IMDb
        logger.info("Aucun détail via OMDb, essai avec l'API IMDb")
        
        # Préparer l'URL et les en-têtes pour l'API IMDb
        url = "https://imdb8.p.rapidapi.com/title/get-overview-details"
        
        querystring = {"tconst": imdb_id, "currentCountry": "FR"}
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        # Faire la requête à l'API
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la récupération des détails IMDb: {response.status_code} - {response.text}")
            return None
        
        # Analyser la réponse
        data = response.json()
        
        # Extraire les détails
        title = data.get("title", {}).get("title", "")
        type_data = data.get("title", {}).get("titleType", "")
        item_type = "film" if type_data == "movie" else "série"
        
        # Construire l'URL IMDb
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
        
        # Extraire l'image et s'assurer qu'elle est hébergée sur Cloudinary
        image_url = ""
        if data.get("title", {}).get("image", {}).get("url"):
            original_image_url = data.get("title", {}).get("image", {}).get("url")
            image_url = ensure_cloudinary_image(original_image_url, imdb_id)
        
        # Si pas d'image, utiliser une image par défaut
        if not image_url:
            image_url = DEFAULT_IMAGE_URL
        
        # Extraire l'année
        year = data.get("title", {}).get("year", "")
        
        # Extraire la note
        rating = data.get("ratings", {}).get("rating", "")
        
        # Extraire le synopsis
        plot = data.get("plotSummary", {}).get("text", "")
        if not plot:
            plot = data.get("plotOutline", {}).get("text", "")
        
        return {
            "title": title,
            "type": item_type,
            "imdb_id": imdb_id,
            "imdb_url": imdb_url,
            "image_url": image_url,
            "year": year,
            "rating": rating,
            "plot": plot
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_omdb_details(imdb_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les détails d'un film ou d'une série sur OMDb
    
    Args:
        imdb_id: ID IMDb du film ou de la série
        
    Returns:
        Détails du film ou de la série
    """
    try:
        logger.info(f"Récupération des détails OMDb pour: {imdb_id}")
        
        # Préparer l'URL et les paramètres pour l'API OMDb
        params = {
            "apikey": OMDB_API_KEY,
            "i": imdb_id,
            "plot": "full",
            "r": "json"
        }
        
        # Faire la requête à l'API
        response = requests.get(OMDB_API_URL, params=params)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la récupération des détails OMDb: {response.status_code} - {response.text}")
            return None
        
        # Analyser la réponse
        data = response.json()
        
        # Vérifier si la recherche a réussi
        if data.get("Response") != "True":
            logger.warning(f"Aucun détail trouvé via OMDb: {data.get('Error', 'Raison inconnue')}")
            return None
        
        logger.info(f"Détails OMDb récupérés avec succès pour {imdb_id}")
        return data
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails OMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return None

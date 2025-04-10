import os
import json
import http.client
import traceback
import re
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration de l'API RapidAPI pour IMDb
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "imdb236.p.rapidapi.com"

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
        
        # Créer la connexion HTTP
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        
        # Préparer les en-têtes pour l'API IMDb
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        # Encoder la requête pour l'URL
        encoded_query = query.replace(" ", "%20")
        
        # Faire la requête à l'API d'autocomplétion
        conn.request("GET", f"/imdb/autocomplete?query={encoded_query}", headers=headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la recherche IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
            return []
        
        # Analyser la réponse JSON
        response_data = json.loads(data.decode("utf-8"))
        
        # Extraire les résultats
        results = []
        for item in response_data.get("results", [])[:limit]:
            # Déterminer le type (film ou série)
            item_type = "film"
            if "TV Series" in item.get("description", "") or "TV Show" in item.get("description", ""):
                item_type = "série"
            
            # Extraire l'ID IMDb
            imdb_id = item.get("id", "")
            if imdb_id.startswith("/title/"):
                imdb_id = imdb_id.replace("/title/", "").rstrip("/")
            
            # Construire l'URL IMDb
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'année
            year = ""
            description = item.get("description", "")
            year_match = re.search(r'(\d{4})', description)
            if year_match:
                year = year_match.group(1)
            
            # Extraire les stars/acteurs (si disponible dans la description)
            stars = description
            
            # Extraire l'image
            image_url = item.get("image", {}).get("url", "") if isinstance(item.get("image"), dict) else item.get("image", "")
            
            # Ajouter le résultat
            results.append({
                "title": item.get("title", "Titre inconnu"),
                "type": item_type,
                "imdb_id": imdb_id,
                "imdb_url": imdb_url,
                "image_url": image_url,
                "year": year,
                "stars": stars
            })
        
        logger.info(f"Résultats de la recherche IMDb: {len(results)} trouvés")
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return []

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
        
        # Créer la connexion HTTP
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        
        # Préparer les en-têtes pour l'API IMDb
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        # Faire la requête à l'API pour obtenir les détails
        conn.request("GET", f"/imdb/title?id={imdb_id}", headers=headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la récupération des détails IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
            
            # Créer un objet de détails minimal avec l'ID IMDb
            return {
                "title": "Titre inconnu",
                "type": "film",
                "imdb_id": imdb_id,
                "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                "image_url": "",
                "year": "",
                "rating": "",
                "plot": ""
            }
        
        # Analyser la réponse JSON
        movie_data = json.loads(data.decode("utf-8"))
        
        # Déterminer le type (film ou série)
        item_type = "film"
        if movie_data.get("type") == "TV Series" or movie_data.get("type") == "TV Show":
            item_type = "série"
        
        # Construire l'URL IMDb
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
        
        # Extraire l'image
        image_url = ""
        if "image" in movie_data:
            if isinstance(movie_data["image"], dict):
                image_url = movie_data["image"].get("url", "")
            else:
                image_url = movie_data.get("image", "")
        
        # Extraire l'année
        year = movie_data.get("year", "")
        
        # Extraire la note
        rating = ""
        if "rating" in movie_data:
            if isinstance(movie_data["rating"], dict):
                rating = movie_data["rating"].get("rating", "")
            else:
                rating = movie_data.get("rating", "")
        
        # Extraire le synopsis
        plot = movie_data.get("plot", "")
        
        return {
            "title": movie_data.get("title", "Titre inconnu"),
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
        
        # En cas d'erreur, retourner un objet minimal
        return {
            "title": "Titre inconnu",
            "type": "film",
            "imdb_id": imdb_id,
            "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
            "image_url": "",
            "year": "",
            "rating": "",
            "plot": ""
        }

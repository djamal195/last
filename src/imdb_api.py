import os
import json
import requests
import traceback
import re
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration de l'API RapidAPI pour IMDb
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "imdb8.p.rapidapi.com"

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
            
            # Extraire l'image
            image_url = item.get("i", {}).get("imageUrl", "")
            
            # Ajouter le résultat
            results.append({
                "title": item.get("l", "Titre inconnu"),
                "type": item_type,
                "imdb_id": imdb_id,
                "imdb_url": imdb_url,
                "image_url": image_url,
                "year": item.get("y", ""),
                "stars": item.get("s", "")
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
        
        # Extraire l'image
        image_url = data.get("title", {}).get("image", {}).get("url", "")
        
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

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
RAPIDAPI_HOST = "imdb232.p.rapidapi.com"

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
        
        # Faire la requête à l'API de recherche
        conn.request("GET", f"/api/search?count={limit}&q={encoded_query}", headers=headers)
        
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
            if item.get("type") == "TV_SERIES" or item.get("type") == "TV_SHOW":
                item_type = "série"
            
            # Construire l'URL IMDb
            imdb_id = item.get("id", "")
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'image
            image_url = item.get("image", "")
            
            # Extraire l'année
            year = item.get("year", "")
            
            # Extraire les stars/acteurs
            stars = ", ".join(item.get("stars", []))
            
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
        
        # Si aucun résultat, essayer avec l'API d'autocomplétion
        if not results:
            logger.info(f"Aucun résultat trouvé avec l'API de recherche, essai avec l'API d'autocomplétion")
            
            # Créer une nouvelle connexion
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
            
            # Faire la requête à l'API d'autocomplétion
            conn.request("GET", f"/api/autocomplete?q={encoded_query}", headers=headers)
            
            # Récupérer la réponse
            res = conn.getresponse()
            data = res.read()
            
            # Vérifier le code de statut
            if res.status != 200:
                logger.error(f"Erreur lors de l'autocomplétion IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
                return []
            
            # Analyser la réponse JSON
            autocomplete_data = json.loads(data.decode("utf-8"))
            
            # Extraire les résultats
            for item in autocomplete_data.get("results", [])[:limit]:
                # Déterminer le type (film ou série)
                item_type = "film"
                if "TV Series" in item.get("description", ""):
                    item_type = "série"
                
                # Construire l'URL IMDb
                imdb_id = item.get("id", "")
                imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
                
                # Extraire l'année
                year = ""
                description = item.get("description", "")
                year_match = re.search(r'(\d{4})', description)
                if year_match:
                    year = year_match.group(1)
                
                # Ajouter le résultat
                results.append({
                    "title": item.get("title", "Titre inconnu"),
                    "type": item_type,
                    "imdb_id": imdb_id,
                    "imdb_url": imdb_url,
                    "image_url": item.get("image", ""),
                    "year": year,
                    "stars": description
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
        
        # Faire la requête à l'API
        conn.request("GET", f"/api/title/{imdb_id}", headers=headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la récupération des détails IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
            return None
        
        # Analyser la réponse JSON
        response_data = json.loads(data.decode("utf-8"))
        
        # Extraire les données du film/série
        movie_data = response_data
        
        # Déterminer le type (film ou série)
        item_type = "film"
        if movie_data.get("type") == "TV_SERIES" or movie_data.get("type") == "TV_SHOW":
            item_type = "série"
        
        # Construire l'URL IMDb
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
        
        # Extraire l'image
        image_url = movie_data.get("image", "")
        
        # Extraire l'année
        year = movie_data.get("year", "")
        
        # Extraire la note
        rating = movie_data.get("rating", "")
        
        # Extraire le synopsis
        plot = movie_data.get("plot", "")
        
        return {
            "title": movie_data.get("title", ""),
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

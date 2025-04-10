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
        
        # Faire la requête à l'API
        url = f"https://{RAPIDAPI_HOST}/imdb/autocomplete"
        
        querystring = {"query": query}
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la recherche IMDb: {response.status_code} - {response.text}")
            return []
        
        # Analyser la réponse JSON
        response_data = response.json()
        
        # Journaliser le type de la réponse pour le débogage
        logger.info(f"Type de la réponse: {type(response_data).__name__}")
        
        # Extraire les résultats
        results = []
        
        # Gérer le cas où response_data est une liste
        if isinstance(response_data, list):
            items = response_data[:limit]
            
            for item in items:
                # Extraire l'ID IMDb
                imdb_id = ""
                if isinstance(item, dict):
                    imdb_id = item.get("id", "")
                    # Nettoyer l'ID si nécessaire
                    if imdb_id.startswith("/title/"):
                        imdb_id = imdb_id.replace("/title/", "").rstrip("/")
                
                # Si on n'a pas d'ID valide, passer à l'item suivant
                if not imdb_id:
                    continue
                
                # Extraire le titre
                title = ""
                if isinstance(item, dict):
                    title = item.get("title", "")
                
                # Si on n'a pas de titre, utiliser l'ID
                if not title:
                    title = f"Titre {imdb_id}"
                
                # Extraire la description
                description = ""
                if isinstance(item, dict):
                    description = item.get("description", "")
                
                # Déterminer le type (film ou série)
                item_type = "film"
                if "TV Series" in description or "TV Show" in description:
                    item_type = "série"
                
                # Extraire l'année
                year = ""
                year_match = re.search(r'(\d{4})', description)
                if year_match:
                    year = year_match.group(1)
                
                # Extraire l'image
                image_url = ""
                if isinstance(item, dict) and "image" in item:
                    if isinstance(item["image"], dict):
                        image_url = item["image"].get("url", "")
                    else:
                        image_url = item.get("image", "")
                
                # Si pas d'image, utiliser une image par défaut basée sur l'ID
                if not image_url and imdb_id:
                    image_url = f"https://img.omdbapi.com/?i={imdb_id}&apikey=7ea4fe3e"
                
                # Construire l'URL IMDb
                imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
                
                # Ajouter le résultat
                results.append({
                    "title": title,
                    "type": item_type,
                    "imdb_id": imdb_id,
                    "imdb_url": imdb_url,
                    "image_url": image_url,
                    "year": year,
                    "stars": description  # Utiliser la description comme stars
                })
        
        # Si nous n'avons pas de résultats, essayer une autre approche
        if not results:
            # Essayer avec l'API OMDb qui est plus fiable pour les images
            omdb_results = search_omdb(query, limit)
            if omdb_results:
                results = omdb_results
        
        logger.info(f"Résultats de la recherche IMDb: {len(results)} trouvés")
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        
        # En cas d'erreur, essayer avec OMDb
        try:
            return search_omdb(query, limit)
        except:
            return []

def search_omdb(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Recherche des films et séries sur OMDb (alternative à IMDb)
    
    Args:
        query: Terme de recherche
        limit: Nombre maximum de résultats
        
    Returns:
        Liste de films et séries trouvés
    """
    try:
        logger.info(f"Recherche OMDb pour: {query}")
        
        # Clé API OMDb (gratuite)
        omdb_api_key = "7ea4fe3e"
        
        # Faire la requête à l'API OMDb
        url = f"http://www.omdbapi.com/?s={query}&apikey={omdb_api_key}"
        
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la recherche OMDb: {response.status_code} - {response.text}")
            return []
        
        # Analyser la réponse JSON
        data = response.json()
        
        # Vérifier si la recherche a réussi
        if data.get("Response") != "True":
            logger.error(f"Erreur OMDb: {data.get('Error', 'Erreur inconnue')}")
            return []
        
        # Extraire les résultats
        results = []
        
        for item in data.get("Search", [])[:limit]:
            # Extraire l'ID IMDb
            imdb_id = item.get("imdbID", "")
            
            # Si on n'a pas d'ID valide, passer à l'item suivant
            if not imdb_id:
                continue
            
            # Déterminer le type (film ou série)
            item_type = "film" if item.get("Type") == "movie" else "série"
            
            # Construire l'URL IMDb
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'image
            image_url = item.get("Poster", "")
            
            # Si l'image est "N/A", utiliser une image par défaut
            if image_url == "N/A" or not image_url:
                image_url = f"https://img.omdbapi.com/?i={imdb_id}&apikey={omdb_api_key}"
            
            # Ajouter le résultat
            results.append({
                "title": item.get("Title", "Titre inconnu"),
                "type": item_type,
                "imdb_id": imdb_id,
                "imdb_url": imdb_url,
                "image_url": image_url,
                "year": item.get("Year", ""),
                "stars": f"{item.get('Type', '').capitalize()}, {item.get('Year', '')}"
            })
        
        logger.info(f"Résultats de la recherche OMDb: {len(results)} trouvés")
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche OMDb: {str(e)}")
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
        
        # Essayer d'abord avec OMDb qui est plus fiable
        omdb_details = get_omdb_details(imdb_id)
        if omdb_details:
            return omdb_details
        
        # Si OMDb échoue, essayer avec l'API RapidAPI
        url = f"https://{RAPIDAPI_HOST}/imdb/title"
        
        querystring = {"id": imdb_id}
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        response = requests.get(url, headers=headers, params=querystring)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la récupération des détails IMDb: {response.status_code} - {response.text}")
            return fallback_get_details(imdb_id)
        
        # Analyser la réponse JSON
        movie_data = response.json()
        
        # Vérifier si la réponse est une liste ou un dictionnaire
        if isinstance(movie_data, list):
            # Si c'est une liste, prendre le premier élément s'il existe
            if movie_data:
                movie_data = movie_data[0]
            else:
                return fallback_get_details(imdb_id)
        
        # Journaliser le type de la réponse pour le débogage
        logger.info(f"Type des détails: {type(movie_data).__name__}")
        
        # Déterminer le type (film ou série)
        item_type = "film"
        if isinstance(movie_data, dict):
            type_value = movie_data.get("type", "")
            if type_value == "TV Series" or type_value == "TV Show":
                item_type = "série"
        
        # Construire l'URL IMDb
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
        
        # Extraire l'image
        image_url = ""
        if isinstance(movie_data, dict) and "image" in movie_data:
            if isinstance(movie_data["image"], dict):
                image_url = movie_data["image"].get("url", "")
            else:
                image_url = movie_data.get("image", "")
        
        # Si pas d'image, utiliser une image par défaut basée sur l'ID
        if not image_url:
            image_url = f"https://img.omdbapi.com/?i={imdb_id}&apikey=7ea4fe3e"
        
        # Extraire l'année
        year = ""
        if isinstance(movie_data, dict):
            year = movie_data.get("year", "")
        
        # Extraire la note
        rating = ""
        if isinstance(movie_data, dict) and "rating" in movie_data:
            if isinstance(movie_data["rating"], dict):
                rating = movie_data["rating"].get("rating", "")
            else:
                rating = movie_data.get("rating", "")
        
        # Extraire le synopsis
        plot = ""
        if isinstance(movie_data, dict):
            plot = movie_data.get("plot", "")
        
        # Extraire le titre
        title = "Titre inconnu"
        if isinstance(movie_data, dict):
            title = movie_data.get("title", "Titre inconnu")
        
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
        
        # En cas d'erreur, essayer avec OMDb
        omdb_details = get_omdb_details(imdb_id)
        if omdb_details:
            return omdb_details
        
        # Si tout échoue, utiliser la méthode de secours
        return fallback_get_details(imdb_id)

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
        
        # Clé API OMDb (gratuite)
        omdb_api_key = "7ea4fe3e"
        
        # Faire la requête à l'API OMDb
        url = f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={omdb_api_key}"
        
        response = requests.get(url)
        
        if response.status_code != 200:
            logger.error(f"Erreur lors de la récupération des détails OMDb: {response.status_code} - {response.text}")
            return None
        
        # Analyser la réponse JSON
        data = response.json()
        
        # Vérifier si la recherche a réussi
        if data.get("Response") != "True":
            logger.error(f"Erreur OMDb: {data.get('Error', 'Erreur inconnue')}")
            return None
        
        # Déterminer le type (film ou série)
        item_type = "film" if data.get("Type") == "movie" else "série"
        
        # Construire l'URL IMDb
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
        
        # Extraire l'image
        image_url = data.get("Poster", "")
        
        # Si l'image est "N/A", utiliser une image par défaut
        if image_url == "N/A" or not image_url:
            image_url = f"https://img.omdbapi.com/?i={imdb_id}&apikey={omdb_api_key}"
        
        return {
            "title": data.get("Title", "Titre inconnu"),
            "type": item_type,
            "imdb_id": imdb_id,
            "imdb_url": imdb_url,
            "image_url": image_url,
            "year": data.get("Year", ""),
            "rating": data.get("imdbRating", ""),
            "plot": data.get("Plot", "")
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails OMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def fallback_get_details(imdb_id: str) -> Dict[str, Any]:
    """
    Méthode de secours pour obtenir les détails d'un film ou d'une série
    
    Args:
        imdb_id: ID IMDb du film ou de la série
        
    Returns:
        Détails du film ou de la série
    """
    # Utiliser une image par défaut basée sur l'ID
    image_url = f"https://img.omdbapi.com/?i={imdb_id}&apikey=7ea4fe3e"
    
    # Retourner un objet minimal
    return {
        "title": f"Titre {imdb_id}",
        "type": "film",
        "imdb_id": imdb_id,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
        "image_url": image_url,
        "year": "",
        "rating": "",
        "plot": ""
    }

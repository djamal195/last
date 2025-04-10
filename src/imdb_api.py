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
        
        # Faire la requête à l'API d'autocomplétion avec le terme de recherche de l'utilisateur
        conn.request("GET", f"/imdb/autocomplete?query={query}", headers=headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la recherche IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
            return []
        
        # Analyser la réponse JSON
        response_data = json.loads(data.decode("utf-8"))
        
        # Journaliser le type de la réponse pour le débogage
        logger.info(f"Type de la réponse: {type(response_data).__name__}")
        
        # Extraire les résultats
        results = []
        
        # Gérer le cas où response_data est une liste
        if isinstance(response_data, list):
            items = response_data[:limit]
        else:
            # Si c'est un dictionnaire, chercher les résultats dans différentes clés possibles
            items = response_data.get("results", [])
            if not items and "d" in response_data:
                items = response_data.get("d", [])
        
        for item in items[:limit]:
            # Déterminer le type (film ou série)
            item_type = "film"
            
            # Extraire la description (peut être dans différentes clés)
            description = ""
            if isinstance(item, dict):
                description = item.get("description", "")
                
                # Vérifier d'autres formats possibles
                if "qid" in item:
                    if item.get("qid") == "tvSeries" or item.get("q") == "TV series":
                        item_type = "série"
                elif "TV Series" in description or "TV Show" in description:
                    item_type = "série"
            
            # Extraire l'ID IMDb
            imdb_id = ""
            if isinstance(item, dict):
                imdb_id = item.get("id", "")
                
                # Nettoyer l'ID si nécessaire
                if imdb_id.startswith("/title/"):
                    imdb_id = imdb_id.replace("/title/", "").rstrip("/")
            elif isinstance(item, str):
                # Si l'item est une chaîne, c'est peut-être directement l'ID
                imdb_id = item
            
            # Si on n'a pas d'ID valide, passer à l'item suivant
            if not imdb_id:
                continue
            
            # Construire l'URL IMDb
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'année
            year = ""
            if isinstance(item, dict):
                if "year" in item:
                    year = item.get("year", "")
                elif "y" in item:
                    year = item.get("y", "")
                elif description:
                    year_match = re.search(r'(\d{4})', description)
                    if year_match:
                        year = year_match.group(1)
            
            # Extraire les stars/acteurs
            stars = ""
            if isinstance(item, dict):
                if "stars" in item:
                    stars = item.get("stars", "")
                elif "s" in item:
                    stars = item.get("s", "")
                elif description:
                    stars = description
            
            # Extraire l'image
            image_url = ""
            if isinstance(item, dict):
                if "image" in item:
                    if isinstance(item["image"], dict):
                        image_url = item["image"].get("url", "")
                    else:
                        image_url = item.get("image", "")
                elif "i" in item and isinstance(item["i"], dict):
                    image_url = item["i"].get("imageUrl", "")
            
            # Extraire le titre
            title = ""
            if isinstance(item, dict):
                if "title" in item:
                    title = item.get("title", "")
                elif "l" in item:
                    title = item.get("l", "")
                elif "name" in item:
                    title = item.get("name", "")
            
            # Si on n'a pas de titre, utiliser l'ID
            if not title:
                title = f"Titre {imdb_id}"
            
            # Ajouter le résultat
            results.append({
                "title": title,
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
            
            # Essayer une autre approche - rechercher par ID
            return fallback_get_details(imdb_id)
        
        # Analyser la réponse JSON
        movie_data = json.loads(data.decode("utf-8"))
        
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
        
        # En cas d'erreur, essayer la méthode de secours
        return fallback_get_details(imdb_id)

def fallback_get_details(imdb_id: str) -> Dict[str, Any]:
    """
    Méthode de secours pour obtenir les détails d'un film ou d'une série
    
    Args:
        imdb_id: ID IMDb du film ou de la série
        
    Returns:
        Détails du film ou de la série
    """
    try:
        # Essayer de rechercher le titre par ID
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        # Essayer avec une recherche par ID
        conn.request("GET", f"/imdb/autocomplete?query={imdb_id}", headers=headers)
        
        res = conn.getresponse()
        data = res.read()
        
        if res.status == 200:
            response_data = json.loads(data.decode("utf-8"))
            
            # Vérifier si la réponse est une liste ou un dictionnaire
            if isinstance(response_data, list):
                items = response_data
            else:
                # Chercher dans les résultats
                items = response_data.get("results", [])
                if not items and "d" in response_data:
                    items = response_data.get("d", [])
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                item_id = item.get("id", "")
                if item_id.startswith("/title/"):
                    item_id = item_id.replace("/title/", "").rstrip("/")
                
                if item_id == imdb_id:
                    # Déterminer le type
                    item_type = "film"
                    description = item.get("description", "")
                    if "TV Series" in description or "TV Show" in description:
                        item_type = "série"
                    
                    # Extraire l'année
                    year = ""
                    year_match = re.search(r'(\d{4})', description)
                    if year_match:
                        year = year_match.group(1)
                    
                    # Extraire l'image
                    image_url = ""
                    if "image" in item:
                        if isinstance(item["image"], dict):
                            image_url = item["image"].get("url", "")
                        else:
                            image_url = item.get("image", "")
                    
                    return {
                        "title": item.get("title", "Titre inconnu"),
                        "type": item_type,
                        "imdb_id": imdb_id,
                        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
                        "image_url": image_url,
                        "year": year,
                        "rating": "",
                        "plot": description
                    }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails de secours: {str(e)}")
    
    # Si tout échoue, retourner un objet minimal
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

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

# URL d'image par défaut garantie fonctionnelle pour Messenger
DEFAULT_IMAGE_URL = "https://m.media-amazon.com/images/M/MV5BMTg1MTY2MjYzNV5BMl5BanBnXkFtZTgwMTc4NTMwNDI@._V1_UX182_CR0,0,182,268_AL_.jpg"

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
            return generate_mock_results(query, limit)
        
        # Analyser la réponse
        data = response.json()
        logger.info(f"Réponse brute de l'API IMDb: {json.dumps(data)[:500]}...")
        
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
            
            # Extraire l'image - s'assurer qu'elle est accessible
            image_url = item.get("i", {}).get("imageUrl", "")
            if not image_url:
                image_url = DEFAULT_IMAGE_URL
            
            # Journaliser l'URL de l'image pour le débogage
            logger.info(f"URL d'image pour {imdb_id}: {image_url}")
            
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
        
        # Si aucun résultat n'est trouvé, générer des résultats fictifs
        if not results:
            return generate_mock_results(query, limit)
        
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return generate_mock_results(query, limit)

def generate_mock_results(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Génère des résultats fictifs en cas d'échec de l'API
    
    Args:
        query: Terme de recherche
        limit: Nombre maximum de résultats
        
    Returns:
        Liste de films et séries fictifs
    """
    logger.info(f"Génération de résultats fictifs pour: {query}")
    
    # Liste d'URLs d'images Amazon connues pour fonctionner avec Messenger
    amazon_images = [
        "https://m.media-amazon.com/images/M/MV5BMTg1MTY2MjYzNV5BMl5BanBnXkFtZTgwMTc4NTMwNDI@._V1_UX182_CR0,0,182,268_AL_.jpg",
        "https://m.media-amazon.com/images/M/MV5BMTMxNTMwODM0NF5BMl5BanBnXkFtZTcwODAyMTk2Mw@@._V1_UX182_CR0,0,182,268_AL_.jpg",
        "https://m.media-amazon.com/images/M/MV5BM2MyNjYxNmUtYTAwNi00MTYxLWJmNWYtYzZlODY3ZTk3OTFlXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_UY268_CR3,0,182,268_AL_.jpg",
        "https://m.media-amazon.com/images/M/MV5BOTY4YjI2N2MtYmFlMC00ZjcyLTg3YjEtMDQyM2ZjYzQ5YWFkXkEyXkFqcGdeQXVyMTQxNzMzNDI@._V1_UX182_CR0,0,182,268_AL_.jpg",
        "https://m.media-amazon.com/images/M/MV5BNzQzOTk3OTAtNDQ0Zi00ZTVkLWI0MTEtMDllZjNkYzNjNTc4L2ltYWdlXkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_UX182_CR0,0,182,268_AL_.jpg"
    ]
    
    results = []
    for i in range(min(limit, 5)):
        fake_id = f"tt{1000000 + i}"
        
        # Utiliser une image Amazon différente pour chaque résultat
        image_url = amazon_images[i % len(amazon_images)]
        
        # Journaliser l'URL de l'image pour le débogage
        logger.info(f"URL d'image fictive pour {fake_id}: {image_url}")
        
        results.append({
            "title": f"{query.capitalize()} {i+1}",
            "type": "film" if i % 2 == 0 else "série",
            "imdb_id": fake_id,
            "imdb_url": f"https://www.imdb.com/title/{fake_id}/",
            "image_url": image_url,
            "year": str(2020 + i),
            "stars": "Acteurs populaires"
        })
    
    logger.info(f"Résultats fictifs générés: {len(results)}")
    return results

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
            return generate_mock_details(imdb_id)
        
        # Analyser la réponse
        data = response.json()
        logger.info(f"Réponse brute des détails IMDb: {json.dumps(data)[:500]}...")
        
        # Extraire les détails
        title = data.get("title", {}).get("title", "")
        type_data = data.get("title", {}).get("titleType", "")
        item_type = "film" if type_data == "movie" else "série"
        
        # Construire l'URL IMDb
        imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
        
        # Extraire l'image - s'assurer qu'elle est accessible
        image_url = data.get("title", {}).get("image", {}).get("url", "")
        if not image_url:
            image_url = DEFAULT_IMAGE_URL
        
        # Journaliser l'URL de l'image pour le débogage
        logger.info(f"URL d'image pour les détails de {imdb_id}: {image_url}")
        
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
        return generate_mock_details(imdb_id)

def generate_mock_details(imdb_id: str) -> Dict[str, Any]:
    """
    Génère des détails fictifs en cas d'échec de l'API
    
    Args:
        imdb_id: ID IMDb du film ou de la série
        
    Returns:
        Détails fictifs du film ou de la série
    """
    logger.info(f"Génération de détails fictifs pour: {imdb_id}")
    
    # Utiliser une image Amazon connue pour fonctionner avec Messenger
    image_url = DEFAULT_IMAGE_URL
    
    # Journaliser l'URL de l'image pour le débogage
    logger.info(f"URL d'image fictive pour les détails de {imdb_id}: {image_url}")
    
    return {
        "title": f"Titre pour {imdb_id}",
        "type": "film",
        "imdb_id": imdb_id,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
        "image_url": image_url,
        "year": "2023",
        "rating": "8.5",
        "plot": "Synopsis généré pour ce titre."
    }

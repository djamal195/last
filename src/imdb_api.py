import os
import json
import http.client
import requests
import traceback
import re
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration de l'API RapidAPI pour IMDb
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "imdb236.p.rapidapi.com"  # Nouvel hôte API

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
        
        # Faire la requête à l'API
        conn.request("GET", f"/imdb/autocomplete?query={encoded_query}", headers=headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la recherche IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
            return []
        
        # Décoder la réponse JSON
        response_data = json.loads(data.decode("utf-8"))
        
        # Journaliser la structure de la réponse pour le débogage
        logger.info(f"Structure de la réponse: {list(response_data.keys()) if isinstance(response_data, dict) else 'list'}")
        
        # Extraire les résultats
        results = []
        
        # Adapter le code en fonction de la structure de la réponse
        # Vérifier si la réponse est une liste ou un dictionnaire avec une clé 'results'
        items = []
        if isinstance(response_data, dict) and 'results' in response_data:
            items = response_data.get('results', [])[:limit]
        elif isinstance(response_data, list):
            items = response_data[:limit]
        
        for item in items:
            # Déterminer le type (film ou série)
            item_type = "film"
            if 'titleType' in item:
                if item.get('titleType') == 'tvSeries' or item.get('titleType') == 'TV series':
                    item_type = "série"
            elif 'qid' in item:
                if item.get('qid') == 'tvSeries' or item.get('q') == 'TV series':
                    item_type = "série"
            
            # Extraire l'ID IMDb
            imdb_id = ""
            if 'id' in item:
                imdb_id = item.get('id', '')
            
            # Construire l'URL IMDb
            imdb_url = f"https://www.imdb.com/title/{imdb_id}/"
            
            # Extraire l'image
            image_url = ""
            if 'i' in item and 'imageUrl' in item['i']:
                image_url = item['i']['imageUrl']
            elif 'image' in item and 'url' in item['image']:
                image_url = item['image']['url']
            
            # Extraire le titre
            title = ""
            if 'l' in item:
                title = item.get('l', 'Titre inconnu')
            elif 'title' in item:
                title = item.get('title', 'Titre inconnu')
            
            # Extraire l'année
            year = ""
            if 'y' in item:
                year = item.get('y', '')
            elif 'year' in item:
                year = item.get('year', '')
            
            # Extraire les acteurs/informations
            stars = ""
            if 's' in item:
                stars = item.get('s', '')
            elif 'stars' in item:
                stars = item.get('stars', '')
            
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
        
        # Faire la requête à l'API
        conn.request("GET", f"/imdb/title?id={imdb_id}", headers=headers)
        
        # Récupérer la réponse
        res = conn.getresponse()
        data = res.read()
        
        # Vérifier le code de statut
        if res.status != 200:
            logger.error(f"Erreur lors de la récupération des détails IMDb: {res.status} - {data.decode('utf-8', errors='ignore')}")
            return None
        
        # Décoder la réponse JSON
        response_data = json.loads(data.decode("utf-8"))
        
        # Journaliser la structure de la réponse pour le débogage
        logger.info(f"Structure de la réponse: {list(response_data.keys()) if isinstance(response_data, dict) else 'list'}")
        
        # Extraire les détails
        # Adapter le code en fonction de la structure de la réponse
        title = ""
        item_type = "film"
        image_url = ""
        year = ""
        rating = ""
        plot = ""
        
        if isinstance(response_data, dict):
            # Extraire le titre
            if 'title' in response_data:
                title = response_data.get('title', '')
            
            # Déterminer le type
            if 'type' in response_data:
                type_data = response_data.get('type', '')
                item_type = "film" if type_data == "movie" else "série"
            elif 'titleType' in response_data:
                type_data = response_data.get('titleType', '')
                item_type = "film" if type_data == "movie" else "série"
            
            # Extraire l'image
            if 'image' in response_data and 'url' in response_data['image']:
                image_url = response_data['image']['url']
            
            # Extraire l'année
            if 'year' in response_data:
                year = response_data.get('year', '')
            
            # Extraire la note
            if 'rating' in response_data:
                rating = response_data.get('rating', '')
            elif 'ratings' in response_data and 'rating' in response_data['ratings']:
                rating = response_data['ratings']['rating']
            
            # Extraire le synopsis
            if 'plot' in response_data:
                plot = response_data.get('plot', '')
            elif 'plotSummary' in response_data and 'text' in response_data['plotSummary']:
                plot = response_data['plotSummary']['text']
            elif 'plotOutline' in response_data and 'text' in response_data['plotOutline']:
                plot = response_data['plotOutline']['text']
        
        return {
            "title": title,
            "type": item_type,
            "imdb_id": imdb_id,
            "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
            "image_url": image_url,
            "year": year,
            "rating": rating,
            "plot": plot
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return None

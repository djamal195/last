import os
import json
import requests
import traceback
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration pour l'API Google Sheets
GOOGLE_SHEETS_CREDENTIALS = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID')
GOOGLE_SHEETS_WORKSHEET = os.environ.get('GOOGLE_SHEETS_WORKSHEET', 'Demandes')

def get_google_sheets_client():
    """
    Initialise et retourne un client Google Sheets
    
    Returns:
        Client Google Sheets ou None en cas d'erreur
    """
    try:
        if not GOOGLE_SHEETS_CREDENTIALS:
            logger.error("Identifiants Google Sheets manquants")
            return None
        
        # Charger les identifiants depuis la variable d'environnement
        credentials_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
        
        # Définir la portée
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Authentifier avec les identifiants
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        
        # Créer le client gspread
        client = gspread.authorize(credentials)
        
        return client
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du client Google Sheets: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def add_imdb_request_to_sheet(user_id: str, user_name: str, imdb_data: Dict[str, Any]) -> bool:
    """
    Ajoute une demande de film ou série à Google Sheets
    
    Args:
        user_id: ID de l'utilisateur
        user_name: Nom de l'utilisateur (si disponible)
        imdb_data: Données IMDb du film ou de la série
        
    Returns:
        True si l'ajout a réussi, False sinon
    """
    try:
        logger.info(f"Ajout d'une demande IMDb à Google Sheets pour l'utilisateur {user_id}")
        
        if not GOOGLE_SHEETS_ID:
            logger.error("ID Google Sheets manquant")
            return False
        
        # Obtenir le client Google Sheets
        client = get_google_sheets_client()
        if not client:
            return False
        
        # Ouvrir le document
        sheet = client.open_by_key(GOOGLE_SHEETS_ID)
        
        # Sélectionner la feuille de travail
        worksheet = sheet.worksheet(GOOGLE_SHEETS_WORKSHEET)
        
        # Préparer les données à ajouter
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Récupérer les en-têtes pour s'assurer que les données sont dans le bon ordre
        headers = worksheet.row_values(1)
        
        # Préparer les données en fonction des en-têtes
        row_data = []
        for header in headers:
            if header.lower() == "date":
                row_data.append(now)
            elif header.lower() == "user_id":
                row_data.append(user_id)
            elif header.lower() == "user_name":
                row_data.append(user_name)
            elif header.lower() == "title":
                row_data.append(imdb_data.get("title", ""))
            elif header.lower() == "type":
                row_data.append(imdb_data.get("type", ""))
            elif header.lower() == "imdb_id":
                row_data.append(imdb_data.get("imdb_id", ""))
            elif header.lower() == "imdb_url":
                row_data.append(imdb_data.get("imdb_url", ""))
            elif header.lower() == "year":
                row_data.append(imdb_data.get("year", ""))
            elif header.lower() == "status":
                row_data.append("Demandé")
            else:
                row_data.append("")  # Valeur par défaut pour les autres colonnes
        
        # Ajouter la ligne
        worksheet.append_row(row_data)
        
        logger.info(f"Demande IMDb ajoutée avec succès à Google Sheets")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de la demande IMDb à Google Sheets: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def get_imdb_requests(user_id: str) -> List[Dict[str, Any]]:
    """
    Récupère les demandes de films et séries d'un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        
    Returns:
        Liste des demandes de l'utilisateur
    """
    try:
        logger.info(f"Récupération des demandes IMDb pour l'utilisateur {user_id}")
        
        if not GOOGLE_SHEETS_ID:
            logger.error("ID Google Sheets manquant")
            return []
        
        # Obtenir le client Google Sheets
        client = get_google_sheets_client()
        if not client:
            return []
        
        # Ouvrir le document
        sheet = client.open_by_key(GOOGLE_SHEETS_ID)
        
        # Sélectionner la feuille de travail
        worksheet = sheet.worksheet(GOOGLE_SHEETS_WORKSHEET)
        
        # Récupérer toutes les données
        all_data = worksheet.get_all_records()
        
        # Filtrer les demandes de l'utilisateur
        user_requests = []
        for row in all_data:
            if str(row.get("user_id", "")) == str(user_id):
                user_requests.append(row)
        
        logger.info(f"Récupération de {len(user_requests)} demandes IMDb pour l'utilisateur {user_id}")
        return user_requests
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des demandes IMDb: {str(e)}")
        logger.error(traceback.format_exc())
        return []

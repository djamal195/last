import os
import json
import time
import http.client
import traceback
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration de l'API RapidAPI pour Copilot
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', "df674bbd36msh112ab45b7712473p16f9abjsn062262165208")
RAPIDAPI_HOST = "copilot5.p.rapidapi.com"
COPILOT_API_ENDPOINT = "/copilot"

# Timeout pour les requêtes (en secondes)
REQUEST_TIMEOUT = 45

def generate_mistral_response(prompt: str, user_id: str = None) -> str:
    """
    Génère une réponse en utilisant l'API Copilot via RapidAPI
    
    Args:
        prompt: Message de l'utilisateur
        user_id: ID de l'utilisateur (non utilisé maintenant)
        
    Returns:
        Réponse générée
    """
    try:
        logger.info(f"Génération d'une réponse Copilot pour le prompt: {prompt[:50]}...")
        
        if not RAPIDAPI_KEY:
            logger.error("Clé API RapidAPI manquante")
            return "Désolé, je ne peux pas générer de réponse pour le moment. La configuration de l'API est incomplète."
        
        conversation_id = None
        
        logger.info(f"Envoi de la requête à Copilot avec conversation_id: {conversation_id}")
        
        # Générer la réponse avec Copilot
        response_data = generate_copilot_response(prompt, conversation_id)
        
        # Extraire la réponse et l'ID de conversation
        if response_data:
            response_text = response_data.get("text", "")
            new_conversation_id = response_data.get("conversation_id")
            
            # Stocker le nouvel ID de conversation si disponible
            if new_conversation_id and user_id:
                try:
                    store_conversation_id_for_user(user_id, new_conversation_id)
                    logger.info(f"Nouvel ID de conversation stocké pour l'utilisateur {user_id}: {new_conversation_id}")
                except Exception as e:
                    logger.error(f"Erreur lors du stockage de l'ID de conversation: {str(e)}")
        else:
            response_text = "Désolé, je n'ai pas pu générer de réponse. Veuillez réessayer plus tard."
        
        logger.info(f"Réponse Copilot émise: {response_text[:50]}...")
        return response_text
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la réponse: {str(e)}")
        logger.error(traceback.format_exc())
        return "Désolé, je n'ai pas pu générer de réponse. Veuillez réessayer plus tard."

def generate_copilot_response(message: str, conversation_id: str = None) -> Dict[str, Any]:
    """
    Génère une réponse avec l'API Copilot via RapidAPI
    
    Args:
        message: Message de l'utilisateur
        conversation_id: ID de la conversation (optionnel)
        
    Returns:
        Dictionnaire contenant la réponse et l'ID de conversation
    """
    try:
        # Préparer les données pour l'API
        payload_data = {
            "message": message,
            "conversation_id": conversation_id,
            "markdown": True
        }
        
        payload = json.dumps(payload_data)
        
        # Préparer les en-têtes
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST,
            'Content-Type': "application/json"
        }
        
        # Mesurer le temps de réponse
        start_time = time.time()
        
        # Établir la connexion
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=REQUEST_TIMEOUT)
        
        # Envoyer la requête
        try:
            conn.request("POST", COPILOT_API_ENDPOINT, payload, headers)
            
            # Obtenir la réponse
            res = conn.getresponse()
            data = res.read()
            
            # Calculer le temps de réponse
            response_time = time.time() - start_time
            logger.info(f"Réponse reçue de Copilot en {response_time:.2f} secondes")
            
            # Vérifier le code de statut
            if res.status != 200:
                error_message = f"Erreur de l'API Copilot: {res.status} - {data.decode('utf-8')}"
                logger.error(error_message)
                
                # Gérer les erreurs spécifiques
                if res.status == 429:
                    return {"text": "Désolé, le service est actuellement très sollicité. Veuillez réessayer dans quelques instants."}
                elif res.status == 500:
                    return {"text": "Désolé, le service rencontre des difficultés techniques. Veuillez réessayer plus tard."}
                else:
                    return {"text": f"Désolé, je n'ai pas pu générer de réponse. Erreur: {res.status}"}
            
            # Analyser la réponse
            response_text = data.decode("utf-8")
            try:
                response_data = json.loads(response_text)
                logger.info(f"Structure de la réponse: {list(response_data.keys())}")
                
                # Extraire le texte de la réponse et l'ID de conversation
                result = {
                    "text": response_data.get("text", ""),
                    "conversation_id": response_data.get("conversation_id")
                }
                
                return result
            except json.JSONDecodeError:
                logger.error(f"Impossible de décoder la réponse JSON: {response_text[:500]}...")
                return {"text": "Désolé, je n'ai pas pu comprendre la réponse du service. Veuillez réessayer."}
        finally:
            # Fermer la connexion
            conn.close()
    except http.client.HTTPException as e:
        logger.error(f"Erreur HTTP lors de la requête à l'API Copilot: {str(e)}")
        return {"text": "Désolé, je n'ai pas pu me connecter au service de génération. Veuillez réessayer plus tard."}
    except Exception as e:
        logger.error(f"Erreur lors de la génération avec Copilot: {str(e)}")
        logger.error(traceback.format_exc())
        return {"text": "Désolé, je n'ai pas pu générer de réponse. Une erreur inattendue s'est produite."}

# Fonctions pour gérer les IDs de conversation
# Ces fonctions sont des placeholders - vous devrez les implémenter selon votre système de stockage

def get_conversation_id_for_user(user_id: str) -> Optional[str]:
    """
    Récupère l'ID de conversation pour un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        
    Returns:
        ID de conversation ou None si non trouvé
    """
    # Placeholder - à implémenter selon votre système de stockage
    # Par exemple, vous pourriez stocker les IDs de conversation dans une base de données
    # ou dans un fichier JSON
    try:
        # Exemple avec un fichier JSON simple
        conversation_file = "conversation_ids.json"
        if os.path.exists(conversation_file):
            with open(conversation_file, "r") as f:
                conversation_ids = json.load(f)
                return conversation_ids.get(user_id)
        return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'ID de conversation: {str(e)}")
        return None

def store_conversation_id_for_user(user_id: str, conversation_id: str):
    """
    Stocke l'ID de conversation pour un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        conversation_id: ID de conversation à stocker
    """
    # Placeholder - à implémenter selon votre système de stockage
    try:
        # Exemple avec un fichier JSON simple
        conversation_file = "conversation_ids.json"
        conversation_ids = {}
        
        # Charger les IDs existants si le fichier existe
        if os.path.exists(conversation_file):
            with open(conversation_file, "r") as f:
                conversation_ids = json.load(f)
        
        # Ajouter ou mettre à jour l'ID de conversation
        conversation_ids[user_id] = conversation_id
        
        # Sauvegarder le fichier
        with open(conversation_file, "w") as f:
            json.dump(conversation_ids, f)
    except Exception as e:
        logger.error(f"Erreur lors du stockage de l'ID de conversation: {str(e)}")

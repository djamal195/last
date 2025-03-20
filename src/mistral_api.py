import os
import json
import requests
import time
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.conversation_memory import get_conversation_history, add_message

logger = get_logger(__name__)

# Configuration de l'API Mistral
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-large-latest"  # ou un autre modèle disponible

def generate_mistral_response(user_message: str, user_id: str) -> str:
    """
    Génère une réponse en utilisant l'API Mistral avec l'historique de conversation
    
    Args:
        user_message: Message de l'utilisateur
        user_id: ID de l'utilisateur pour récupérer l'historique
        
    Returns:
        Réponse générée par Mistral
    """
    if not MISTRAL_API_KEY:
        logger.error("Clé API Mistral manquante")
        return "Désolé, je ne peux pas générer de réponse pour le moment. La clé API est manquante."
    
    try:
        # Récupérer l'historique de conversation
        conversation_history = get_conversation_history(user_id)
        logger.info(f"Historique récupéré pour l'utilisateur {user_id}: {len(conversation_history)} messages")
        
        # Ajouter le message actuel de l'utilisateur à l'historique
        add_message(user_id, "user", user_message)
        
        # Préparer les messages pour l'API Mistral
        messages = conversation_history.copy()
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": user_message})
        
        # Ajouter un message système pour définir le comportement du bot
        system_message = {
            "role": "system",
            "content": "Tu es un assistant intelligent et serviable. Réponds de manière concise et utile aux questions de l'utilisateur."
        }
        
        # Construire la requête
        payload = {
            "model": MISTRAL_MODEL,
            "messages": [system_message] + messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}"
        }
        
        logger.info(f"Envoi de la requête à Mistral avec {len(messages)} messages d'historique")
        
        # Envoyer la requête à l'API Mistral
        start_time = time.time()
        response = requests.post(
            MISTRAL_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response_time = time.time() - start_time
        
        logger.info(f"Réponse reçue de Mistral en {response_time:.2f} secondes")
        
        # Vérifier la réponse
        if response.status_code != 200:
            logger.error(f"Erreur de l'API Mistral: {response.status_code} - {response.text}")
            return f"Désolé, je n'ai pas pu générer de réponse. Erreur: {response.status_code}"
        
        # Extraire la réponse
        response_data = response.json()
        assistant_message = response_data["choices"][0]["message"]["content"]
        
        # Ajouter la réponse à l'historique
        add_message(user_id, "assistant", assistant_message)
        
        return assistant_message
        
    except requests.exceptions.Timeout:
        logger.error("Timeout lors de la requête à l'API Mistral")
        return "Désolé, la génération de la réponse a pris trop de temps. Veuillez réessayer."
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la réponse Mistral: {str(e)}")
        return "Désolé, une erreur s'est produite lors de la génération de la réponse. Veuillez réessayer plus tard."


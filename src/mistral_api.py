import os
import json
import requests
import time
import re
import unicodedata
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.conversation_memory import get_conversation_history, add_message

logger = get_logger(__name__)

# Configuration de l'API Mistral
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-large-latest"  # ou un autre modèle disponible

# Fonction pour normaliser le texte (supprimer les accents)
def normalize_text(text):
    """
    Normalise le texte en supprimant les accents et en convertissant en minuscules
    """
    # Convertir en minuscules
    text = text.lower()
    # Normaliser les caractères Unicode (décomposer les caractères accentués)
    text = unicodedata.normalize('NFD', text)
    # Supprimer les caractères non ASCII (comme les accents)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text

# Expressions régulières pour détecter les questions sur la création du bot
CREATOR_PATTERNS = [
    # Qui t'a créé (avec variations t'a/ta/vous a)
    r"qui (t[\'']a|ta|vous a|t a) (cree|créé|concu|conçu|construit|developpe|développé|fait|programme|programmé)",
    
    # Qui est ton créateur
    r"qui est ton (createur|créateur|concepteur|developpeur|développeur|programmeur)",
    
    # Qui t'a mis au point
    r"qui (t[\'']a|ta|t a) mis au point",
    
    # Qui t'a donné la vie
    r"qui (t[\'']a|ta|t a) (donne|donné|cree|créé) la vie",
    
    # Qui est à l'origine de toi
    r"qui est (a l[\'']origine|a lorigine|derriere|responsable) de (toi|ce bot|ce chatbot)",
    
    # Par qui as-tu été créé
    r"(qui|par qui) (es[ -]tu|as[ -]tu ete|as[ -]tu été) (cree|créé|concu|conçu|developpe|développé|programme|programmé|construit)",
    
    # Quel est ton créateur
    r"(quel est|c[\'']est quoi) ton (createur|créateur|concepteur|developpeur|développeur)",
    
    # Qui t'a mis au monde
    r"qui (t[\'']a|ta|t a) (mis|mis en|mis au) (point|monde)",
    
    # D'où viens-tu
    r"d[\'']ou viens[- ]tu",
    
    # Qui t'a inventé/fabriqué
    r"qui (t[\'']a|ta|t a) (invente|inventé|fabrique|fabriqué)",
    
    # Questions simples
    r"qui (t[\'']a|ta) (cree|créé)",
    r"qui (t[\'']a|ta) (fait|concu|construit)",
    r"qui (t[\'']a|ta) (developpe|développé)",
    
    # Questions directes
    r"ton (createur|créateur)",
    r"ton (developpeur|développeur)",
    r"qui t'a code",
    r"qui t'a programme",
    
    # Questions avec "comment"
    r"comment (as-tu ete|as-tu été|tu as été) (cree|créé|concu|conçu|developpe|développé)",
    
    # Questions avec "quand"
    r"quand (as-tu ete|as-tu été) (cree|créé|concu|conçu|developpe|développé)",
]

# Réponse personnalisée pour les questions sur le créateur
CREATOR_RESPONSE = "J'ai été créé par Djamaldine Montana avec l'aide de Mistral. C'est un développeur talentueux qui m'a conçu pour aider les gens comme vous !"

def is_creator_question(message: str) -> bool:
    """
    Détermine si le message est une question sur le créateur du bot
    
    Args:
        message: Message de l'utilisateur
        
    Returns:
        True si c'est une question sur le créateur, False sinon
    """
    # Normaliser le message (supprimer les accents, mettre en minuscules)
    normalized_message = normalize_text(message.strip())
    
    # Vérifier les mots-clés directs
    direct_keywords = [
        "qui t'a cree", "qui ta cree", "qui t'a fait", "qui ta fait",
        "ton createur", "ton developpeur", "qui t'a developpe", "qui ta developpe",
        "qui t'a concu", "qui ta concu", "qui t'a construit", "qui ta construit",
        "qui t'a programme", "qui ta programme", "qui t'a code", "qui ta code"
    ]
    
    for keyword in direct_keywords:
        if keyword in normalized_message:
            logger.info(f"Correspondance directe trouvée: '{keyword}' dans '{normalized_message}'")
            return True
    
    # Vérifier les expressions régulières
    for pattern in CREATOR_PATTERNS:
        if re.search(pattern, normalized_message):
            logger.info(f"Expression régulière correspondante trouvée pour: '{normalized_message}'")
            return True
    
    # Vérifier les phrases complètes
    complete_phrases = [
        "qui es-tu", "qui tu es", "presente-toi", "presente toi", "presentez-vous",
        "parle-moi de toi", "parle moi de toi", "dis-moi qui tu es", "dis moi qui tu es"
    ]
    
    if normalized_message in complete_phrases or normalized_message.strip('?!., ') in complete_phrases:
        logger.info(f"Phrase complète correspondante trouvée: '{normalized_message}'")
        return True
    
    return False

def generate_mistral_response(user_message: str, user_id: str) -> str:
    """
    Génère une réponse en utilisant l'API Mistral avec l'historique de conversation
    
    Args:
        user_message: Message de l'utilisateur
        user_id: ID de l'utilisateur pour récupérer l'historique
        
    Returns:
        Réponse générée par Mistral
    """
    # Vérifier si c'est une question sur le créateur du bot
    if is_creator_question(user_message):
        logger.info(f"Question sur le créateur détectée: '{user_message}'")
        logger.info("Réponse personnalisée envoyée")
        
        # Ajouter le message de l'utilisateur à l'historique
        add_message(user_id, "user", user_message)
        
        # Ajouter la réponse personnalisée à l'historique
        add_message(user_id, "assistant", CREATOR_RESPONSE)
        
        return CREATOR_RESPONSE
    
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


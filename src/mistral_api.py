import re
import requests
import json
import signal
from src.config import MISTRAL_API_KEY
from src.utils.logger import get_logger

logger = get_logger(__name__)

def check_creator_question(prompt):
    """
    Vérifie si la question concerne le créateur du bot
    """
    prompt = prompt.lower()
    patterns = [
        r"qui (t'a|ta|t as) (créé|cree|construit|développé|developpe|conçu|concu|fabriqué|fabrique|inventé|invente)",
        r"par qui as[- ]?tu (été|ete) (créé|cree|développé|developpe|construit|conçu|concu)",
        r"qui est (ton|responsable de|derrière|derriere) (créateur|createur|développeur|developpeur|toi)",
        r"d['oòo]u viens[- ]?tu"
    ]
    
    for pattern in patterns:
        if re.search(pattern, prompt):
            return True
    
    return False

def generate_mistral_response(prompt):
    """
    Génère une réponse en utilisant l'API Mistral
    """
    logger.info(f"Début de generate_mistral_response pour prompt: {prompt}")
    
    # Vérifier si la question concerne le créateur
    if check_creator_question(prompt):
        logger.info("Question sur le créateur détectée. Réponse personnalisée envoyée.")
        return "J'ai été créé par Djamaldine Montana avec l'aide de Mistral. C'est un développeur talentueux qui m'a conçu pour aider les gens comme vous !"
    
    try:
        # Définir un timeout
        def timeout_handler(signum, frame):
            logger.warning("Timeout atteint pour la requête Mistral")
            raise TimeoutError("La requête a pris trop de temps")
        
        # Configurer le timeout à 50 secondes
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(50)
        
        logger.info("Envoi de la requête à l'API Mistral...")
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {MISTRAL_API_KEY}"
            },
            json={
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000
            },
            timeout=45  # Timeout de la requête HTTP
        )
        
        # Désactiver le timeout
        signal.alarm(0)
        
        logger.info(f"Réponse reçue de l'API Mistral. Status: {response.status_code}")
        
        if response.status_code != 200:
            error_body = response.text
            logger.error(f"Erreur API Mistral: {response.status_code} - {error_body}")
            raise Exception(f"HTTP error! status: {response.status_code}")
        
        data = response.json()
        logger.info(f"Données reçues de l'API Mistral: {json.dumps(data)}")
        
        generated_response = data['choices'][0]['message']['content']
        
        if len(generated_response) > 4000:
            generated_response = generated_response[:4000] + "... (réponse tronquée)"
        
        logger.info(f"Réponse générée: {generated_response}")
        return generated_response
    except TimeoutError:
        logger.error("Erreur de timeout lors de la génération de la réponse Mistral")
        return "Désolé, la génération de la réponse a pris trop de temps. Veuillez réessayer avec une question plus courte ou plus simple."
    except Exception as e:
        logger.error(f"Erreur détaillée lors de la génération de la réponse Mistral: {str(e)}")
        if isinstance(e, TimeoutError) or "timeout" in str(e):
            return "Désolé, la génération de la réponse a pris trop de temps. Veuillez réessayer avec une question plus courte ou plus simple."
        return "Je suis désolé, mais je ne peux pas répondre pour le moment. Veuillez réessayer plus tard."
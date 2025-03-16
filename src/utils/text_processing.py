import re
from src.utils.logger import get_logger

logger = get_logger(__name__)

def clean_text(text):
    """
    Nettoie le texte en supprimant les caractères spéciaux et les espaces multiples
    
    Args:
        text (str): Texte à nettoyer
        
    Returns:
        str: Texte nettoyé
    """
    # Supprimer les caractères spéciaux
    text = re.sub(r'[^\w\s]', '', text)
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    # Supprimer les espaces au début et à la fin
    text = text.strip()
    return text

def truncate_text(text, max_length=2000):
    """
    Tronque le texte à la longueur maximale spécifiée
    
    Args:
        text (str): Texte à tronquer
        max_length (int, optional): Longueur maximale
        
    Returns:
        str: Texte tronqué
    """
    if len(text) <= max_length:
        return text
    
    # Tronquer le texte
    truncated = text[:max_length-3] + "..."
    return truncated

def split_text(text, chunk_size=2000):
    """
    Divise le texte en morceaux de taille spécifiée
    
    Args:
        text (str): Texte à diviser
        chunk_size (int, optional): Taille des morceaux
        
    Returns:
        list: Liste des morceaux de texte
    """
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def extract_command(text):
    """
    Extrait une commande du texte (ex: /yt)
    
    Args:
        text (str): Texte à analyser
        
    Returns:
        tuple: (commande, reste du texte) ou (None, texte original) si aucune commande
    """
    # Rechercher une commande au début du texte
    match = re.match(r'^\/([a-zA-Z0-9_]+)(?:\s+(.*))?$', text)
    if match:
        command = match.group(1).lower()
        rest = match.group(2) or ""
        return (command, rest)
    return (None, text)
import time
from typing import Dict, List, Any, Optional
from src.utils.logger import get_logger
from src.database import get_database

logger = get_logger(__name__)

# Configuration
MAX_HISTORY_LENGTH = 10  # Nombre maximum de messages à conserver par utilisateur
MAX_HISTORY_AGE = 24 * 60 * 60  # Durée de conservation de l'historique en secondes (24 heures)
MAX_TOKENS_ESTIMATE = 4000  # Estimation du nombre maximum de tokens pour l'historique

def add_message(user_id: str, role: str, content: str) -> None:
    """
    Ajoute un message à l'historique de conversation d'un utilisateur dans MongoDB
    
    Args:
        user_id: ID de l'utilisateur
        role: Rôle du message ('user' ou 'assistant')
        content: Contenu du message
    """
    try:
        # Obtenir la base de données
        db = get_database()
        if db is None:
            logger.error("Impossible de se connecter à la base de données")
            return
        
        # Créer le message
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        
        # Récupérer l'historique actuel
        conversation = db.conversations.find_one({"user_id": user_id})
        
        if conversation:
            # Ajouter le message à l'historique existant
            messages = conversation.get("messages", [])
            messages.append(message)
            
            # Limiter la taille de l'historique
            if len(messages) > MAX_HISTORY_LENGTH:
                messages = messages[-MAX_HISTORY_LENGTH:]
            
            # Mettre à jour l'historique
            db.conversations.update_one(
                {"user_id": user_id},
                {"$set": {"messages": messages, "updated_at": time.time()}}
            )
        else:
            # Créer un nouvel historique
            db.conversations.insert_one({
                "user_id": user_id,
                "messages": [message],
                "created_at": time.time(),
                "updated_at": time.time()
            })
        
        logger.info(f"Message ajouté à l'historique pour l'utilisateur {user_id}, rôle: {role}")
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du message à l'historique: {str(e)}")

def get_conversation_history(user_id: str) -> List[Dict[str, str]]:
    """
    Récupère l'historique de conversation d'un utilisateur formaté pour Mistral
    
    Args:
        user_id: ID de l'utilisateur
        
    Returns:
        Liste de messages formatés pour Mistral
    """
    try:
        # Obtenir la base de données
        db = get_database()
        if db is None:
            logger.error("Impossible de se connecter à la base de données")
            return []
        
        # Récupérer l'historique
        conversation = db.conversations.find_one({"user_id": user_id})
        
        if not conversation:
            logger.info(f"Aucun historique trouvé pour l'utilisateur {user_id}")
            return []
        
        messages = conversation.get("messages", [])
        
        # Filtrer les messages trop anciens
        current_time = time.time()
        filtered_messages = [
            msg for msg in messages
            if current_time - msg.get("timestamp", 0) < MAX_HISTORY_AGE
        ]
        
        # Mettre à jour l'historique filtré si nécessaire
        if len(filtered_messages) != len(messages):
            db.conversations.update_one(
                {"user_id": user_id},
                {"$set": {"messages": filtered_messages, "updated_at": time.time()}}
            )
        
        # Formater pour Mistral (sans les timestamps)
        formatted_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in filtered_messages
        ]
        
        # Estimation simple de la taille en tokens et troncature si nécessaire
        # Cette estimation est approximative, 4 caractères ~ 1 token
        total_chars = sum(len(msg["content"]) for msg in formatted_history)
        
        if total_chars > MAX_TOKENS_ESTIMATE * 4:
            # Garder les messages les plus récents si l'historique est trop grand
            while total_chars > MAX_TOKENS_ESTIMATE * 4 and formatted_history:
                removed = formatted_history.pop(0)
                total_chars -= len(removed["content"])
            
            # Mettre à jour l'historique tronqué
            truncated_messages = filtered_messages[-len(formatted_history):]
            db.conversations.update_one(
                {"user_id": user_id},
                {"$set": {"messages": truncated_messages, "updated_at": time.time()}}
            )
        
        logger.info(f"Récupération de l'historique pour l'utilisateur {user_id}: {len(formatted_history)} messages")
        return formatted_history
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'historique: {str(e)}")
        return []

def clear_user_history(user_id: str) -> None:
    """
    Efface l'historique de conversation d'un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
    """
    try:
        # Obtenir la base de données
        db = get_database()
        if db is None:
            logger.error("Impossible de se connecter à la base de données")
            return
        
        # Supprimer l'historique
        result = db.conversations.delete_one({"user_id": user_id})
        
        if result.deleted_count > 0:
            logger.info(f"Historique effacé pour l'utilisateur {user_id}")
        else:
            logger.info(f"Aucun historique trouvé pour l'utilisateur {user_id}")
            
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'historique: {str(e)}")

def clear_old_histories() -> None:
    """
    Nettoie les historiques de conversation trop anciens
    """
    try:
        # Obtenir la base de données
        db = get_database()
        if db is None:
            logger.error("Impossible de se connecter à la base de données")
            return
        
        # Calculer la date limite
        current_time = time.time()
        limit_time = current_time - MAX_HISTORY_AGE
        
        # Supprimer les conversations inactives depuis trop longtemps
        result = db.conversations.delete_many({
            "updated_at": {"$lt": limit_time}
        })
        
        logger.info(f"Nettoyage des historiques terminé, {result.deleted_count} conversations supprimées")
        
        # Filtrer les messages trop anciens dans les conversations restantes
        conversations = db.conversations.find({})
        
        for conversation in conversations:
            user_id = conversation.get("user_id")
            messages = conversation.get("messages", [])
            
            filtered_messages = [
                msg for msg in messages
                if current_time - msg.get("timestamp", 0) < MAX_HISTORY_AGE
            ]
            
            if len(filtered_messages) != len(messages):
                db.conversations.update_one(
                    {"user_id": user_id},
                    {"$set": {"messages": filtered_messages, "updated_at": time.time()}}
                )
                
                logger.info(f"Historique filtré pour l'utilisateur {user_id}: {len(messages) - len(filtered_messages)} messages supprimés")
                
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des historiques: {str(e)}")
        def add_message_to_history(user_id, role, content):
    """
    Ajoute un message à l'historique de conversation d'un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        role: Rôle du message ('user' ou 'assistant')
        content: Contenu du message
    """
    try:
        from src.database import get_db
        import datetime
        
        db = get_db()
        collection = db["conversations"]
        
        collection.insert_one({
            "user_id": user_id,
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now()
        })
        
        return True
    except Exception as e:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Erreur lors de l'ajout du message à l'historique: {str(e)}")
        return False


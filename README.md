# Chatbot Messenger avec Python

Un chatbot Messenger qui utilise l'API Mistral pour la conversation et l'API YouTube pour la recherche de vidéos.

## Fonctionnalités

- **Mode Mistral** : Conversation intelligente avec l'utilisateur grâce à l'API Mistral
- **Mode YouTube** : Recherche de vidéos YouTube et envoi de liens ou téléchargement de vidéos
- **Gestion des états utilisateurs** : Suivi du mode actuel pour chaque utilisateur
- **Gestion des erreurs** : Messages d'erreur personnalisés et récupération après erreur
- **Stockage des vidéos** : Utilisation de Cloudinary et MongoDB pour stocker les vidéos téléchargées

## Prérequis

- Python 3.8 ou supérieur
- Compte développeur Facebook
- Clé API Mistral
- Clé API YouTube (Google Cloud Console)
- Compte Cloudinary (pour la gestion des médias)
- Base de données MongoDB (pour le stockage des données)

## Déploiement sur Render.com

1. Créez un compte sur [Render.com](https://render.com/)
2. Créez un nouveau service Web
3. Connectez votre dépôt GitHub ou utilisez le déploiement manuel
4. Configurez le service avec les paramètres suivants:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn api.webhook:app`
5. Ajoutez les variables d'environnement nécessaires
6. Déployez le service

## Configuration du webhook Facebook

1. Allez sur [Facebook Developers](https://developers.facebook.com/)
2. Accédez à votre application
3. Dans les paramètres du webhook, mettez à jour l'URL:
   - URL: `https://votre-service.onrender.com/api/webhook`
   - Token de vérification: celui que vous avez défini dans les variables d'environnement

## Utilisation

- `/yt` : Active le mode YouTube
- `yt/` : Revient au mode Mistral
- En mode YouTube, entrez des mots-clés pour rechercher des vidéos
- En mode Mistral, posez des questions pour obtenir des réponses

## Licence

Ce projet est sous licence MIT.
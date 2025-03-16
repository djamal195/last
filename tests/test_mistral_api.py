import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Ajouter le répertoire parent au chemin de recherche
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.mistral_api import generate_mistral_response, check_creator_question

class TestMistralApi(unittest.TestCase):
    
    def test_check_creator_question(self):
        """Test la détection des questions sur le créateur"""
        # Questions qui devraient être détectées
        self.assertTrue(check_creator_question("Qui t'a créé ?"))
        self.assertTrue(check_creator_question("Par qui as-tu été développé ?"))
        self.assertTrue(check_creator_question("Qui est ton créateur ?"))
        self.assertTrue(check_creator_question("D'où viens-tu ?"))
        
        # Questions qui ne devraient pas être détectées
        self.assertFalse(check_creator_question("Comment vas-tu ?"))
        self.assertFalse(check_creator_question("Quelle est la capitale de la France ?"))
        self.assertFalse(check_creator_question("Peux-tu m'aider avec un problème ?"))
    
    @patch('requests.post')
    def test_generate_mistral_response(self, mock_post):
        """Test la génération de réponse via l'API Mistral"""
        # Configurer le mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This is a test response from Mistral API"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Appeler la fonction
        response = generate_mistral_response("What is the capital of France?")
        
        # Vérifier que la fonction a retourné la bonne réponse
        self.assertEqual(response, "This is a test response from Mistral API")
        
        # Vérifier que la requête a été faite avec les bons paramètres
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.mistral.ai/v1/chat/completions")
        self.assertEqual(kwargs["json"]["messages"][0]["content"], "What is the capital of France?")
    
    def test_generate_mistral_response_creator_question(self):
        """Test la réponse personnalisée pour les questions sur le créateur"""
        response = generate_mistral_response("Qui t'a créé ?")
        self.assertIn("Djamaldine Montana", response)
        self.assertIn("Mistral", response)

if __name__ == '__main__':
    unittest.main()


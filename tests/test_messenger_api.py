import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Ajouter le répertoire parent au chemin de recherche
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.messenger_api import send_text_message, send_youtube_results, handle_message

class TestMessengerApi(unittest.TestCase):
    
    @patch('src.messenger_api.call_send_api')
    def test_send_text_message(self, mock_call_send_api):
        """Test l'envoi d'un message texte"""
        # Configurer le mock
        mock_call_send_api.return_value = {"recipient_id": "123", "message_id": "456"}
        
        # Appeler la fonction
        send_text_message("123", "Test message")
        
        # Vérifier que call_send_api a été appelé avec les bons arguments
        mock_call_send_api.assert_called_once()
        args = mock_call_send_api.call_args[0][0]
        self.assertEqual(args["recipient"]["id"], "123")
        self.assertEqual(args["message"]["text"], "Test message")
    
    @patch('src.messenger_api.call_send_api')
    def test_send_youtube_results(self, mock_call_send_api):
        """Test l'envoi des résultats YouTube"""
        # Configurer le mock
        mock_call_send_api.return_value = {"recipient_id": "123", "message_id": "456"}
        
        # Données de test
        videos = [
            {
                "title": "Test Video 1",
                "thumbnail": "http://example.com/thumb1.jpg",
                "videoId": "123456"
            },
            {
                "title": "Test Video 2",
                "thumbnail": "http://example.com/thumb2.jpg",
                "videoId": "789012"
            }
        ]
        
        # Appeler la fonction
        send_youtube_results("123", videos)
        
        # Vérifier que call_send_api a été appelé avec les bons arguments
        mock_call_send_api.assert_called_once()
        args = mock_call_send_api.call_args[0][0]
        self.assertEqual(args["recipient"]["id"], "123")
        self.assertEqual(args["message"]["attachment"]["type"], "template")
        self.assertEqual(args["message"]["attachment"]["payload"]["template_type"], "generic")
        self.assertEqual(len(args["message"]["attachment"]["payload"]["elements"]), 2)
    
    @patch('src.messenger_api.generate_mistral_response')
    @patch('src.messenger_api.send_text_message')
    def test_handle_message_mistral_mode(self, mock_send_text, mock_generate_response):
        """Test le traitement d'un message en mode Mistral"""
        # Configurer les mocks
        mock_generate_response.return_value = "This is a test response"
        
        # Appeler la fonction
        handle_message("123", {"text": "Hello, how are you?"})
        
        # Vérifier que les fonctions ont été appelées correctement
        mock_generate_response.assert_called_once_with("Hello, how are you?")
        mock_send_text.assert_called_once_with("123", "This is a test response")
    
    @patch('src.messenger_api.search_youtube')
    @patch('src.messenger_api.send_youtube_results')
    @patch('src.messenger_api.send_text_message')
    def test_handle_message_youtube_mode(self, mock_send_text, mock_send_results, mock_search):
        """Test le traitement d'un message en mode YouTube"""
        # Configurer les mocks
        mock_search.return_value = [
            {"title": "Test Video", "thumbnail": "http://example.com/thumb.jpg", "videoId": "123456"}
        ]
        
        # Simuler l'activation du mode YouTube
        handle_message("123", {"text": "/yt"})
        mock_send_text.assert_called_with("123", "Mode YouTube activé. Donnez-moi les mots-clés pour la recherche YouTube.")
        
        # Réinitialiser les mocks
        mock_send_text.reset_mock()
        
        # Simuler une recherche YouTube
        handle_message("123", {"text": "cat videos"})
        
        # Vérifier que les fonctions ont été appelées correctement
        mock_search.assert_called_once_with("cat videos")
        mock_send_results.assert_called_once()

if __name__ == '__main__':
    unittest.main()

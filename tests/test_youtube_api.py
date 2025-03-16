import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Ajouter le répertoire parent au chemin de recherche
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.youtube_api import search_youtube

class TestYoutubeApi(unittest.TestCase):
    
    @patch('googleapiclient.discovery.build')
    def test_search_youtube(self, mock_build):
        """Test la recherche de vidéos YouTube"""
        # Configurer le mock
        mock_youtube = MagicMock()
        mock_search = MagicMock()
        mock_list = MagicMock()
        
        mock_build.return_value = mock_youtube
        mock_youtube.search.return_value = mock_search
        mock_search.list.return_value = mock_list
        
        # Configurer la réponse simulée
        mock_list.execute.return_value = {
            "items": [
                {
                    "id": {"videoId": "123456"},
                    "snippet": {
                        "title": "Test Video 1",
                        "thumbnails": {
                            "default": {"url": "http://example.com/thumb1.jpg"}
                        }
                    }
                },
                {
                    "id": {"videoId": "789012"},
                    "snippet": {
                        "title": "Test Video 2",
                        "thumbnails": {
                            "default": {"url": "http://example.com/thumb2.jpg"}
                        }
                    }
                }
            ]
        }
        
        # Appeler la fonction
        results = search_youtube("test query")
        
        # Vérifier que la fonction a retourné les bons résultats
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Test Video 1")
        self.assertEqual(results[0]["videoId"], "123456")
        self.assertEqual(results[0]["thumbnail"], "http://example.com/thumb1.jpg")
        
        # Vérifier que l'API a été appelée avec les bons paramètres
        mock_build.assert_called_once_with('youtube', 'v3', developerKey=unittest.mock.ANY)
        mock_search.list.assert_called_once_with(
            q="test query",
            part='snippet',
            maxResults=5,
            type='video'
        )

if __name__ == '__main__':
    unittest.main()


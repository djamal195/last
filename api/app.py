from flask import Flask, request, jsonify
import json
import asyncio
from datetime import datetime
import logging
from config import verify_webhook
from messenger_api import handle_message

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.before_request
def log_request_info():
    logger.info(f"{datetime.now().isoformat()} - {request.method} {request.url}")
    logger.info(f"Query: {json.dumps(request.args.to_dict())}")
    if request.is_json:
        logger.info(f"Body: {json.dumps(request.json)}")

@app.route('/api/webhook', methods=['GET'])
def webhook_verification():
    logger.info("GET request received for webhook verification")
    response, status_code = verify_webhook(request)
    return response, status_code

@app.route('/api/webhook', methods=['POST'])
def webhook_handler():
    logger.info("POST request received from webhook")
    body = request.json
    
    if body.get('object') == 'page':
        logger.info("Page event received")
        for entry in body.get('entry', []):
            if 'messaging' in entry and entry['messaging']:
                webhook_event = entry['messaging'][0]
                logger.info(f"Webhook event received: {json.dumps(webhook_event)}")
                
                sender_id = webhook_event.get('sender', {}).get('id')
                
                # Vérifier si c'est un message ou un postback
                if webhook_event.get('message'):
                    logger.info("Message received, calling handle_message")
                    try:
                        # Exécuter handle_message de manière asynchrone
                        asyncio.run(handle_message(sender_id, webhook_event['message']))
                        logger.info("handle_message completed successfully")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                
                elif webhook_event.get('postback'):
                    logger.info("Postback received, calling handle_message with postback")
                    try:
                        # Traiter le postback comme un message spécial
                        asyncio.run(handle_message(sender_id, {'postback': webhook_event['postback']}))
                        logger.info("handle_message for postback completed successfully")
                    except Exception as e:
                        logger.error(f"Error processing postback: {e}")
                
                else:
                    logger.info(f"Unrecognized event: {webhook_event}")
            else:
                logger.warning("Entry without messaging field or empty messaging array")
        
        return "EVENT_RECEIVED", 200
    else:
        logger.info("Unrecognized request received")
        return "", 404

@app.errorhandler(Exception)
def handle_error(e):
    logger.error(f"Unhandled error: {e}")
    return "Something went wrong!", 500

if __name__ == '__main__':
    app.run(debug=True, port=3000)


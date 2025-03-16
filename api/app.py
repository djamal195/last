from flask import Flask
from api.webhook import webhook_blueprint  # Import du webhook si c'est un Blueprint

app = Flask(__name__)
app.register_blueprint(webhook_blueprint)  # Si nécessaire

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

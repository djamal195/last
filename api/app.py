# app.py - Redirect to the actual application
from api.webhook import app

# This file exists only to redirect Render to the actual application
# The app variable should match whatever your Flask/FastAPI application is named in webhook.py


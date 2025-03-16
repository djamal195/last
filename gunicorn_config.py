import os

# Use PORT environment variable provided by Render
port = os.environ.get("PORT", 8000)
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = 4

# Choose the appropriate worker class based on your framework
# Uncomment the one you need:
# worker_class = "uvicorn.workers.UvicornWorker"  # For FastAPI
worker_class = "sync"  # For Flask

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"


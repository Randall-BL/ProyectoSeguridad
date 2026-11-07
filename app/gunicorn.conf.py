import os

# Cloud Run indica el puerto en PORT. Un proceso con varios hilos es lo que recomienda Google
# para una instancia de una CPU.
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 1
threads = 8
timeout = 0
accesslog = "-"

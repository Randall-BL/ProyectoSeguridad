import os

# Cloud Run indica el puerto en PORT. Un proceso con varios hilos es lo que recomienda Google
# para una instancia de una CPU.
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 1
threads = 4
timeout = 0
accesslog = "-"
# Sin la interfaz de control de gunicorn: el usuario del contenedor no tiene carpeta personal, y
# nadie administra el proceso desde dentro.
control_socket_disable = True

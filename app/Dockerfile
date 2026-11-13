# Imagen de la aplicación Django, el componente «Aplicación» de la Parte 1.
# Se construye desde la raíz del repositorio: docker build -f app/Dockerfile .
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ARG APP_VERSION=local
ARG APP_COMMIT=""
LABEL org.opencontainers.image.title="verdeazul-app" \
      org.opencontainers.image.source="https://github.com/Randall-BL/ProyectoSeguridad" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION} \
    APP_COMMIT=${APP_COMMIT}

WORKDIR /srv/app

# Solo entran paquetes con la versión y la huella de requirements.txt.
COPY app/requirements.txt .
RUN pip install --require-hashes -r requirements.txt

# El código queda de root y sin permiso de escritura para el usuario que corre la aplicación.
COPY app/ .

# Estilos e imágenes con huella en el nombre, comprimidos, para WhiteNoise. Los ajustes exigen estas
# variables, pero collectstatic no se conecta a nada: llevan valores de relleno, no secretos.
RUN DJANGO_SECRET_KEY=solo-para-collectstatic MFA_CLAVE=solo-para-collectstatic     DATABASE_URL=postgresql://localhost/sin-base     python manage.py collectstatic --noinput --verbosity 0

# Mínimo privilegio: la aplicación no corre como root.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin verdeazul
USER 10001

EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "verdeazul.wsgi:application"]

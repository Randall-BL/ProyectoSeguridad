# Imagen de la aplicación Django, el componente «Aplicación» de la Parte 1.
# Se construye desde la raíz del repositorio: docker build -f app/Dockerfile .
FROM python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d

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

# Mínimo privilegio: la aplicación no corre como root.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin verdeazul
USER 10001

EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "verdeazul.wsgi:application"]

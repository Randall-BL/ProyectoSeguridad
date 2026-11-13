# Imagen de la comprobación pública (rol PUB de la Parte 1). Se construye desde la raíz del
# repositorio: docker build -f publico/Dockerfile .
FROM python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d

ARG APP_VERSION=local
ARG APP_COMMIT=""
LABEL org.opencontainers.image.title="verdeazul-publico" \
      org.opencontainers.image.source="https://github.com/Randall-BL/ProyectoSeguridad" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /srv/publico

# Solo entran paquetes con la versión y la huella de requirements.txt.
COPY publico/requirements.txt .
RUN pip install --require-hashes -r requirements.txt

# El formato del certificado y la clave pública son los mismos que usa el verificador sin conexión.
COPY verificador/verdeazul_certificado.py verificador/verdeazul-clave-publica.pem ./
COPY publico/servicio.py publico/gunicorn.conf.py ./
COPY publico/plantillas/ plantillas/
COPY publico/estatico/ estatico/

# Mínimo privilegio: el servicio no corre como root y no puede escribir su propio código.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin verdeazul
USER 10001

EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "servicio:app"]

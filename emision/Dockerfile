# Imagen del servicio de emisión (componente SIS de la Parte 1). Se construye desde la raíz del
# repositorio: docker build -f emision/Dockerfile .
FROM python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d

ARG APP_VERSION=local
ARG APP_COMMIT=""
LABEL org.opencontainers.image.title="verdeazul-emision" \
      org.opencontainers.image.source="https://github.com/Randall-BL/ProyectoSeguridad" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /srv/emision

# Solo entran paquetes con la versión y la huella de requirements.txt.
COPY emision/requirements.txt .
RUN pip install --require-hashes -r requirements.txt

# El formato del certificado es el mismo módulo que usan el servicio público y el verificador.
COPY verificador/verdeazul_certificado.py emision/emitir.py emision/servicio.py emision/gunicorn.conf.py ./

# Mínimo privilegio: el servicio no corre como root y no puede escribir su propio código.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin verdeazul
USER 10001

EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "servicio:app"]

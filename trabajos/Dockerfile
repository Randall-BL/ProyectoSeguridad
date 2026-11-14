# Imagen del trabajo diario (fase 7), que corre como Cloud Run Job. Se construye desde la raíz del
# repositorio: docker build -f trabajos/Dockerfile .
FROM python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d

ARG APP_VERSION=local
ARG APP_COMMIT=""
LABEL org.opencontainers.image.title="verdeazul-trabajos" \
      org.opencontainers.image.source="https://github.com/Randall-BL/ProyectoSeguridad" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /srv/trabajos

# Solo entran paquetes con la versión y la huella de requirements.txt.
COPY trabajos/requirements.txt .
RUN pip install --require-hashes -r requirements.txt

COPY trabajos/diario.py trabajos/tsa.py ./

# Mínimo privilegio: no corre como root y no puede escribir su propio código.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin verdeazul
USER 10001

CMD ["python", "diario.py"]

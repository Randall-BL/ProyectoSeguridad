# Imagen del motor de decisión, el componente «Motor de decisión (OPA)» de la Parte 1: la imagen
# oficial de OPA, fijada por huella, con la política adentro. La variante -static no tiene shell ni
# gestor de paquetes. Se construye desde la raíz del repositorio: docker build -f politica/Dockerfile .
FROM openpolicyagent/opa:1.22.3-static@sha256:a6ccb6e0cc91b2d1807b1b65a844b189249b9ab33d126e0bca30c0cf43b0ae07

ARG APP_VERSION=local
ARG APP_COMMIT=""
LABEL org.opencontainers.image.title="verdeazul-politica" \
      org.opencontainers.image.source="https://github.com/Randall-BL/ProyectoSeguridad" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${APP_COMMIT}"

# Solo la matriz y las reglas; las pruebas se quedan fuera de la imagen.
COPY politica/matriz.json /politica/matriz.json
COPY politica/verdeazul/decision.rego politica/verdeazul/reglas.rego /politica/verdeazul/

# Mínimo privilegio: el usuario sin privilegios de la imagen oficial, nunca root.
USER 1000:1000

# Escucha dentro de la instancia. En Cloud Run este contenedor no declara puertos: el tráfico de
# internet solo llega al contenedor de la aplicación, y el motor queda detrás de la frontera F3.
# Sin telemetría hacia afuera y sin registrar las decisiones en la consola (llevan datos de
# personas); la bitácora de la aplicación registra las denegaciones.
EXPOSE 8181
CMD ["run", "--server", "--addr=:8181", "--log-level=error", "--disable-telemetry", "/politica"]

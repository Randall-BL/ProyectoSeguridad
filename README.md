# Verdeazul Carbono · Proyecto Parte 2

CE-1115 Seguridad de la Información, TEC · Grupo 6: Randall Bolaños, Javier Tenorio, Julio Varela y
Axel Flores. Implementación y despliegue en Google Cloud Run y Neon del sistema de control de acceso
diseñado en la Parte 1. Entrega: 19 de noviembre de 2026.

El plan de trabajo, tarea por tarea, está en [todo.md](todo.md). Los documentos del diseño (Parte 1)
están en [Randall-BL/CE1115-Proyecto-P1-Verdeazul](https://github.com/Randall-BL/CE1115-Proyecto-P1-Verdeazul).

## Estructura

| Carpeta | Componente de la Parte 1 | Estado |
|---|---|---|
| `app/` | Aplicación Django, punto de cumplimiento | Sprint 1 |
| `politica/` | Motor de decisión OPA: la matriz como política | Sprint 2 |
| `db/` | Usuarios de base, permisos, seguridad por fila, bitácora | Sprint 2 |
| `emision/` | Servicio de emisión de certificados (SIS) | Sprint 4 |
| `publico/` | Comprobación pública de certificados (PUB) | Sprint 4 |
| `trabajos/` | Trabajos programados | Sprint 4 |
| `verificador/` | Verificador de certificados sin acceso al sistema | Sprint 4 |
| `infra/` | Scripts de Google Cloud, Cloud Build y Cloud Run (sin secretos) | Sprint 1 |

## Configuración del repositorio (una vez por clon)

1. Instalar gitleaks 8.30 o superior:
   - Windows: `winget install --id Gitleaks.Gitleaks -e`, y abrir una terminal nueva.
   - macOS: `brew install gitleaks`.
   - Comprobar con `gitleaks version`.
2. Activar los ganchos del repositorio:
   ```
   git config core.hooksPath .githooks
   ```
3. Hacer los commits con su propia identidad, la que está vinculada a su cuenta de GitHub:
   ```
   git config user.name "Su nombre"
   git config user.email "su-correo@estudiantec.cr"
   ```
   Si ese correo no está agregado en GitHub (Settings → Emails), los commits no quedan a su nombre.

Con eso, cada commit pasa por dos revisiones antes de crearse:

| Gancho | Qué rechaza |
|---|---|
| `.githooks/pre-commit` | Cualquier secreto en lo preparado: llaves privadas, tokens, cadenas de conexión con contraseña, semillas TOTP. Usa las reglas de gitleaks y las de `.gitleaks.toml` |
| `.githooks/commit-msg` | Co-autores que no sean del equipo (`@estudiantec.cr` o el noreply de GitHub), cuentas `[bot]` y pies «Generated with» |

El flujo `.github/workflows/seguridad.yml` repite las dos revisiones sobre toda la historia en cada
push a `main` y en cada PR, por si alguien no instaló los ganchos.

## Ramas

- Cada integrante trabaja en su rama `development-<nombre>` (por ejemplo, `development-yitan`) y
  hace un commit por tarea del [todo.md](todo.md), con su número al inicio del mensaje («2.7: …»).
- A `main` se llega por PR desde esa rama, fusionando con **merge commit**, no con squash: así los
  commits etiquetados (`v0.2.0`, …) siguen en la historia de `main`.
- El CI corre en cada push a `main` y a las ramas `development-*`, y en cada PR.

## Reglas del repositorio

- **Ningún secreto en el repositorio, nunca.** El repositorio es público. Las credenciales viven en
  Secret Manager; para desarrollar en local se copia `.env.example` a `.env`, que git ignora. Si un
  secreto llega a subirse, se rota de inmediato: borrarlo del repositorio no basta.
- **`main` no admite force push ni se puede borrar.**
- **Las etiquetas `v*` son inmutables:** una vez publicada, `v1.0.0` no se mueve ni se borra. Si hay
  un error, se publica `v1.0.1`. Cada etiqueta de git corresponde a la imagen con la misma etiqueta en
  Artifact Registry.
- **Dependabot** revisa cada lunes las dependencias de pip, las imágenes base de Docker y las acciones
  de GitHub (`.github/dependabot.yml`), y abre PR de seguridad cuando hay una alerta.

## Desarrollo local

Con Docker Desktop abierto:

```
DJANGO_SECRET_KEY=<cualquier valor largo> docker compose up --build
```

La app queda en http://127.0.0.1:8000 y la base (PostGIS 18, sin contraseña, solo local) en
`127.0.0.1:55432`. La llave se puede poner en `.env`, que git ignora.

## Despliegue

**URL pública:** https://verdeazul-app-708901712393.us-east1.run.app

Proyecto de Google Cloud `verdeazul-ce1115-g6`, región `us-east1`. Base de datos en Neon, proyecto
`verdeazul`. Hace falta gcloud con sesión en una cuenta con acceso al proyecto, y Git Bash o Cloud
Shell para correr los scripts.

**Una sola vez** (ya está hecho; los scripts solo crean lo que falta):

```
sh infra/preparar-gcp.sh     # registro de imágenes, cuentas de servicio, bucket de Cloud Build
sh infra/crear-secretos.sh   # secretos en Secret Manager y usuario de base va_app
```

**Cada versión:**

1. Commit y push (a `main` o a la rama `development-<nombre>`).
2. `sh infra/publicar.sh app vX.Y.Z`: Cloud Build construye la imagen y la publica como
   `app:vX.Y.Z` y `app:git-<commit>`, y pone la etiqueta `vX.Y.Z` en git, en el mismo commit.
3. `sh infra/desplegar.sh app vX.Y.Z`: aplica `infra/app.service.yaml` con esa imagen.

**Volver a una versión anterior:** `sh infra/desplegar.sh app vX.Y.Z` con la versión a la que se
quiere volver. El registro conserva las últimas cinco versiones de cada imagen y todas las `v1.x`.

**Dependencias:** se editan en `app/requirements.in` y se fijan con
`sh infra/fijar-dependencias.sh app` (requiere `pip install uv`).

## Versiones publicadas

Cada etiqueta de git corresponde a la imagen con la misma etiqueta en
`us-east1-docker.pkg.dev/verdeazul-ce1115-g6/verdeazul`.

| Versión | Commit | Fecha | Qué trae |
|---|---|---|---|
| `v0.1.0` | `6a0a1f8` | 2026-11-06 | «Hola»: Django por HTTPS en Cloud Run, que lee Neon con la cadena de Secret Manager; imagen sin root |

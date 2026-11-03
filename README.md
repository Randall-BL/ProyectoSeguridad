# Verdeazul Carbono · Proyecto Parte 2

CE-1115 Seguridad de la Información, TEC · Grupo 6: Randall Bolaños, Javier Tenorio, Julio Varela y
Axel Flores. Implementación y despliegue en Google Cloud Run y Neon del sistema de control de acceso
diseñado en la Parte 1. Entrega: 19 de noviembre de 2026.

El plan de trabajo, tarea por tarea, está en [todo.md](todo.md).

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

## Despliegue

Pendiente: fase 1 del [todo.md](todo.md).

## Versiones publicadas

| Versión | Commit | Fecha | Qué trae |
|---|---|---|---|
| | | | |

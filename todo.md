# Proyecto Parte 2 · Implementación y despliegue (Verdeazul Carbono)

CE-1115 Seguridad de la Información · Grupo 6 · Randall Bolaños, Javier Tenorio, Julio Varela, Axel Flores.
**Entrega y presentación: jueves 19 de noviembre de 2026.** 25 % de la nota. Atributo HI.

Cómo usar este archivo: cada tarea tiene un número (por ejemplo, 4.3) para poder decir «hagamos la 4.3».
Se marca `[x]` al terminar. Las marcadas con ⚠ tocan una condición que anula puntos. Las fechas son
la meta de cada fase; el orden importa más que la fecha.

La fuente de verdad del diseño es la Parte 1: la matriz (Entregable 3), el control de acceso (2), la
arquitectura (4) y las políticas (1). Este archivo cita sus identificadores: C1 a C20, H1 a H4, T-01 a
T-37, POL-xx-nn, F1 a F5.

---

## Sprints

Cada sprint cierra con una versión desplegada y etiquetada: siempre hay algo funcionando en la nube.
Cada tarea terminada es un commit con su número («2.7: …») y se sube en el momento a la rama
`development-<nombre>` de quien la hace (Randall: `development-yitan`); la casilla del todo se marca
en el mismo commit. A `main` se fusiona por PR con merge commit. Al cerrar un sprint, la etiqueta de git y la de la imagen en
Artifact Registry son la misma, y se anota en «Versiones publicadas» del README.

| Sprint | Fechas | Fases | Versión | Listo cuando… |
|---|---|---|---|---|
| 0 · Arranque | 6–7 nov | 0, cuentas de Neon y Google Cloud | — | Cuentas, proyecto y facturación listos |
| 1 · «Hola» en la nube | 7–9 nov | 1 | `v0.1.0` | La URL `*.run.app` abre por HTTPS, lee Neon con la cadena que llega desde Secret Manager, y la imagen corre sin root |
| 2 · Base, identidad y motor | 9–11 nov | 2, 3, 4 | `v0.2.0` | Usuarios de base, seguridad por fila, bitácora encadenada, Argon2id y TOTP; OPA como sidecar decidiendo; OPA caído frena todo (T-41) |
| 3 · Flujos y matriz completa | 11–13 nov | 5, y 8.1 a 8.4 a la par | `v0.3.0` | Los 102 permisos se ejercitan desde la interfaz; T-01 a T-40 pasan |
| 4 · Certificados y trabajos | 13–15 nov | 6, 7 | `v0.4.0` | Emitir, verificar, el alterado falla, comprobación pública, verificador de consola, trabajos programados |
| 5 · Endurecimiento | 16–17 nov | 9, y 8.5 a 8.9 | **`v1.0.0`** | Trivy, ZAP, gitleaks sobre la historia, alerta de Dependabot atendida, tabla de cobertura |
| 6 · Informe y defensa | 17–19 nov | 10, 11 | — | Informe, capturas, anexo de credenciales fuera del repo, ensayo, prueba desde otra red |

---

## Qué se evalúa (para decidir qué recortar)

| Criterio | Pts | Lo mínimo para no perderlo |
|---|---|---|
| Despliegue funcional en la nube | 16 | Abre por HTTPS desde internet, en Cloud Run, con Neon |
| Matriz de acceso y arquitectura | 25 | Los 102 permisos y las 38 celdas denegadas; decide el servidor; los componentes existen como tales |
| Certificados firmados | 15 | Clave privada protegida, clave pública incrustada, verificación que detecta alteración |
| Gestión de secretos | 12 | Secret Manager; nada sensible en el repositorio ni en su historia |
| Contenedores, registro y Dependabot | 10 | Artifact Registry con versiones explícitas, sin root, Dependabot activo |
| Correspondencia con la Parte 1 | 7 | Lo construido se reconoce en el diseño; desviaciones justificadas |
| Informe y evidencia | 10 | Tabla de cobertura, seguridad heredada, capturas |
| Presentación y defensa individual | 5 | Los cuatro conocen el sistema completo |

**Si hay que recortar:** se recorta funcionalidad accesoria (fotos de la hoja de campo, mapa, reportes
semanales, testigo externo elaborado, WebAuthn). Nunca la matriz ni los controles.

### ⚠ Condiciones que anulan puntos

- **Credenciales en el repositorio: se pierde todo el criterio de secretos.** Incluye contraseñas de
  prueba, la cadena de conexión de Neon, la clave de firma, las semillas TOTP de las cuentas de prueba y
  el JSON de una cuenta de servicio de Google. El repositorio es **público**: un secreto que se empuja
  queda expuesto aunque se borre después, así que hay que rotarlo, no solo quitarlo.
- **Contraseñas sin hash o con hash rápido:** se pierde la mitad del criterio de control de acceso.
- **El sistema no abre desde internet el día de la presentación:** se pierde el criterio de despliegue.
- **Imágenes publicadas solo como `latest`:** se pierde la mitad del criterio de contenedores.
- **Permisos de la matriz sin implementar:** se descuenta proporcionalmente.

---

## Cambios acordados después de la Parte 1

Tres ajustes que el diseño entregado no tenía, o no tenía así de explícitos. Cada uno tiene sus
tareas, sus casos de prueba nuevos (T-38 a T-41) y su lugar en el informe.

- [ ] **K-1 El límite de 20 fincas se refiere a asignaciones activas.** Un técnico tiene como máximo
  20 asignaciones activas a la vez, sumando las ordinarias y las temporales vigentes. Las vencidas,
  las terminadas y las de períodos cerrados no cuentan. El límite tampoco tiene que ver con cuántas
  fincas consulta al día (eso es H1: 40, 60 y 80). Si SUP intenta crear la asignación 21, el servidor
  la rechaza; es una condición más de C19. Va como parámetro con valor inicial 20 que aprueba GER, no
  como constante, para no contradecir la respuesta del cliente a P-02 («sin cantidades fijas»). Es un
  cambio respecto a la Parte 1: desviación D-06. Tareas 2.6, 4.8 y 5.5; casos T-38 y T-39.
- [ ] **K-2 Quien registra no aprueba, validado por ID de usuario.** C3 compara el identificador de la
  cuenta (UUID), no el nombre, el rol ni la sesión. Se aprueba solo si el `usuario_id` de quien aprueba
  no está entre los `usuario_id` de los autores de **todas** las versiones de la medición. Así ni un
  cambio de rol ni una habilitación temporal lo evaden (T-06, T-26). El ID sale de la sesión en el
  servidor, nunca de un campo que mande el navegador. Se comprueba en OPA y otra vez en la base.
  Tareas 2.6, 4.2 y 5.6; casos T-05, T-06, T-26 y T-40.
- [ ] **K-3 Si OPA deja de responder, el sistema se frena.** Fallo cerrado, sin excepciones. Si el
  motor no contesta dentro del tiempo límite (1 a 2 segundos), devuelve un error o una respuesta que no
  se entiende, la petición se detiene ahí y no se ejecuta. No hay decisión por omisión que conceda, no
  se reutiliza una decisión anterior guardada y no hay un camino alterno «mientras vuelve». El usuario
  recibe «servicio no disponible» (503) y la bitácora registra la denegación con la causa «motor sin
  respuesta». Si el contenedor de OPA no arranca, la instancia no recibe tráfico. Tareas 4.5 y 4.6;
  caso T-41; criterio de aceptación 6.

---

## Del diseño de la Parte 1 al despliegue

La Parte 1 suponía un servidor virtual propio con Podman. El enunciado de la Parte 2 fija Cloud Run,
Neon, Secret Manager y Artifact Registry. Cada componente del diseño tiene que seguir existiendo:

| Componente de la Parte 1 | En la Parte 2 | ¿Desviación? |
|---|---|---|
| Proxy (Caddy): TLS, HSTS, tamaño y ritmo | El frente de Google en Cloud Run termina el TLS; HSTS, tamaño y ritmo pasan a Django | Sí (D-01) |
| Aplicación (Django), punto de cumplimiento | Servicio Cloud Run `verdeazul-app` | No |
| Motor de decisión (OPA) | Contenedor auxiliar (*sidecar*) dentro de `verdeazul-app`, solo en `localhost:8181` | No: el diseño ya decía «en un contenedor junto a la aplicación» |
| Servicio de emisión (fila SIS) | Servicio Cloud Run `verdeazul-emision`, sin acceso público; solo lo invoca la cuenta de servicio de la app | No |
| Comprobación pública (fila PUB) | Servicio Cloud Run `verdeazul-publico`, abierto, con un usuario de base que solo lee una vista | No |
| Trabajos programados | Cloud Run Jobs disparados por Cloud Scheduler | Menor |
| PostgreSQL 18 + PostGIS | Neon (PostgreSQL gestionado, con PostGIS) | Sí (D-02) |
| Bóveda OpenBao (firma sin entregar la llave) | Secret Manager: el servicio de emisión **sí lee** la clave | Sí (D-03) |
| Respaldos cifrados con *age* en otro proveedor | Respaldo y recuperación a un punto en el tiempo de Neon | Sí (D-04) |
| Testigo externo (RFC 3161 + buzón del auditor) | Trabajo diario que sella la huella de la bitácora con una TSA pública | Por decidir (0.6) |
| Podman sin root sobre AlmaLinux | Docker sin root sobre Cloud Run (aislamiento gVisor) | Sí (D-05) |
| OPE: operador sin cuenta en la app | OPE = permisos IAM del proyecto de Google; sin cuenta en la app | No |

### Desviaciones (van tal cual al informe, §5)

Formato: qué cambió, por qué y qué implicación de seguridad tuvo. Completar al construir.

- [ ] **D-01 Sin Caddy.** Cloud Run ya termina TLS y solo expone HTTPS. HSTS, redirección y cabeceras
  pasan a Django (`SECURE_*`); el límite de tamaño, a `DATA_UPLOAD_MAX_MEMORY_SIZE`; el de ritmo, a un
  middleware. Implicación: la frontera F1 la valida Google y no un componente propio.
- [ ] **D-02 Neon en vez de PostgreSQL propio.** Lo exige el enunciado. Implicación: el superusuario
  real lo tiene el proveedor; se gana cifrado en reposo y recuperación a un punto en el tiempo.
- [ ] **D-03 Secret Manager en vez de OpenBao.** La clave de firma llega al servicio de emisión como
  variable de entorno: ese servicio la puede leer, cosa que la bóveda evitaba. Se acota dando acceso al
  secreto solo a la cuenta de servicio de emisión. Alternativa descartada o futura: Cloud KMS, que
  firma sin entregar la llave (tiene costo pequeño). Sube RR-7.
- [ ] **D-04 Respaldos.** Los da Neon; se pierde el «respaldo en otro proveedor con llave propia».
- [ ] **D-05 Cloud Run en vez de un servidor virtual.** Lo exige el enunciado. Se pierde SELinux y se
  gana el aislamiento de Cloud Run; el contenedor sigue sin root.
- [ ] **D-06 Máximo de 20 asignaciones activas por técnico (K-1).** La Parte 1 no limitaba cuántas
  fincas puede tener asignadas un técnico. Se agrega para acotar cuánto alcanza una sola cuenta: un
  técnico comprometido o un error de asignación llega a 20 fincas, no a todo el catálogo. Es un
  parámetro, no una constante, por P-02.
- [ ] **D-07 Segundo factor por código temporal para todos, por ahora.** POL-AU-05 prefiere llaves de
  acceso (WebAuthn) y las exige para GER, ADM y AUD. La versión entregada usa TOTP con códigos de
  recuperación para todos los roles: las cuentas de prueba tienen que poder usarse desde cualquier
  equipo, y una llave de acceso queda atada al dispositivo de quien la registra. Implicación: el código
  temporal se puede pedir en una página falsa (*phishing*), cosa que la llave de acceso evita; queda
  como mejora si da el tiempo (allauth ya la soporta). El secreto TOTP se guarda cifrado con una clave
  de Secret Manager, y nadie puede quitarse el segundo factor.
- [ ] D-08… (las que aparezcan: testigo externo, versión de Python, etc.)

---

## 0 · Decisiones que hay que tomar ya (3–4 nov)

- [x] **0.1 Cuenta de Google Cloud.** Cloud Run exige una cuenta de facturación con tarjeta. El
  enunciado pide **avisar al profesor antes de registrar una tarjeta**: hay créditos educativos.
  Preguntarle hoy. Definir quién es el dueño del proyecto e invitar a los otros tres.
  Hecho: la cuenta de facturación es de Randall, con un prepago de activación de 30 USD que queda
  como saldo y se recupera al final (tarea 12.2). Falta dar acceso a los otros tres al proyecto.
- [ ] **0.2 Región.** Una región de Cloud Run cercana a la de Neon (por ejemplo `us-east1` con Neon en
  AWS `us-east-1`). Confirmar que la región elegida entra en la capa gratuita.
- [ ] **0.3 Formato del certificado.** Recomendado: **JSON canónico firmado con Ed25519** (claves
  ordenadas, sin espacios), con la clave pública y su huella incrustadas, más una versión legible en
  PDF o HTML que incluya el código y un QR. Alternativa más vistosa y más cara de hacer: PDF firmado
  (PAdES) con pyHanko, que también verifica Adobe Reader. Decidir antes de la fase 6.
- [ ] **0.4 Segundo factor en las cuentas de prueba.** POL-AU-05 lo exige para todos los roles, pero
  el profesor tiene que poder entrar con cada rol. Recomendado: TOTP en todas las cuentas de prueba y
  entregar la semilla de cada una **en el informe**, nunca en el repositorio. WebAuthn queda como
  mejora si da el tiempo (si no, desviación D-07).
  - 9-nov: pendiente antes de sembrar Neon: que `sembrar` active el TOTP de cada cuenta y escriba
    su semilla (URI `otpauth://`) en el archivo de `--salida`, junto a la contraseña.
- [ ] **0.5 Cómo se construyen las imágenes.** Recomendado para empezar: un script `infra/deploy.sh`
  con `gcloud builds submit` (Cloud Build). Mejora: GitHub Actions con Workload Identity Federation.
  Nunca una llave JSON de cuenta de servicio guardada como secreto del repositorio si se puede evitar.
- [ ] **0.6 Testigo externo.** Mínimo defendible: un trabajo diario que pide un sello de tiempo RFC
  3161 a una TSA pública sobre la última huella de la bitácora y guarda el sello. Si no da el tiempo,
  desviación documentada.
- [ ] **0.7 Reparto.** Propuesta, siguiendo los bloques de la defensa de la Parte 1 (ajustar):
  - Javier (arquitectura): fases 1 y 9, infraestructura, imágenes, secretos, Dependabot.
  - Axel (modelo y controles de historial): fase 4, OPA con la matriz y H1 a H4.
  - Julio (separación y matriz): fases 5 y 8, flujos y pruebas T-01 a T-37.
  - Randall (activos, amenazas, marco legal): fases 2, 3 y 6, base, bitácora, autenticación y certificados.
  - Todos: informe y presentación. Cada quien debe poder explicar lo que no escribió.

---

## 1 · «Hola» desplegado en la nube (meta: viernes 6 nov)

El consejo del enunciado: desplegar algo mínimo la primera semana. Aquí se arma toda la tubería; lo
demás es agregar funcionalidad encima.

**Repositorio**
- [x] 1.1 Estructura del repositorio (hecho: existen `app/` e `infra/`; las demás carpetas se crean
  en el sprint que las usa, y el README describe la estructura):
  ```
  app/          Django: la aplicación y su Dockerfile
  politica/     OPA: matriz.json, reglas .rego, pruebas y Dockerfile
  emision/      servicio de emisión (SIS) y su Dockerfile
  publico/      comprobación pública (PUB) y su Dockerfile
  trabajos/     trabajos programados y su Dockerfile
  db/           SQL de roles, permisos, seguridad por fila, disparadores y bitácora
  verificador/  programa independiente para verificar un certificado sin acceso al sistema
  infra/        service.yaml de Cloud Run y scripts gcloud (sin secretos)
  docs/         informe, diagramas, capturas, PDF de la Parte 1
  ```
  Recomendado: un solo código Django con ajustes y rutas distintas por componente, y una imagen por
  componente que copia solo lo que necesita.
- [x] 1.2 Copiar los PDF de la Parte 1 a `docs/parte1/`, para que los cuatro trabajen con el mismo
  diseño. Cambio: no se copian. Ya están en el repo público de la Parte 1
  (`Randall-BL/CE1115-Proyecto-P1-Verdeazul`), y el README enlaza ahí para no duplicar los PDF.
- [x] 1.3 ⚠ `.gitignore` con `.env`, `*.pem`, `*.key`, `credenciales*`, `.venv/`. Un `.env.example` con
  los nombres de las variables y valores vacíos. También `.gitattributes`, que deja todo en LF.
- [x] 1.4 ⚠ gitleaks: gancho *pre-commit* (`.githooks/`) y paso en CI (`.github/workflows/seguridad.yml`),
  con reglas propias en `.gitleaks.toml` para cadenas de Neon y semillas TOTP. *Secret scanning* y
  *push protection* activos en GitHub.
- [x] 1.5 Dependabot: alertas y actualizaciones de seguridad activas en *Settings → Code security*, y
  `.github/dependabot.yml` con los ecosistemas `pip`, `docker` y `github-actions`.
  - 9-nov: Dependabot abrió el PR #1 (Django 5.2.19 → 6.1.3, versión mayor). No se integra: la 5.2.19
    ya trae el parche de seguridad del 3-nov. Django queda en 5.2 LTS y `dependabot.yml` ignora sus
    versiones mayores; la regla rige cuando llegue a `main`. Va al informe como evidencia de 1.5.
- [x] 1.5b Reglas en GitHub: `main` sin force push ni borrado; etiquetas `v*` inmutables. Gancho
  `commit-msg` y revisión en CI que rechazan co-autores ajenos al equipo.
- [ ] 1.5c Invitar a Javier, Julio y Axel como colaboradores. Cada uno sigue «Configuración del
  repositorio» del README: instalar gitleaks, `git config core.hooksPath .githooks` y su identidad.
- [x] 1.6 Entorno local: `docker compose` con PostGIS y OPA, solo para desarrollar (lo que se evalúa es
  la nube). Dejar el `.venv` fuera de OneDrive o excluido de la sincronización. Hecho:
  `docker-compose.yml` con PostGIS 18 (fijada por huella) y la app; OPA se agrega en el sprint 2.
  Los puertos escuchan solo en 127.0.0.1 (la base en el 55432). Comprobado: la app corre como
  `uid=10001` y no puede escribir en `/srv/app`.

**Neon**
- [x] 1.7 Crear el proyecto y la base `verdeazul`, en la región elegida. Activar la extensión PostGIS.
  Hecho: proyecto `verdeazul` (`wild-grass-32431323`) en la organización TEC, plan gratuito, AWS
  us-east-1, PostgreSQL 18.6 y PostGIS 3.6.4. El repo está enlazado con `neon init`: las cadenas
  quedan en `.env.local` y el enlace en `.neon`, los dos ignorados por git.
- [x] 1.8 Rama `main` para producción y rama `dev` para desarrollo y pruebas (va al informe: «entornos
  separados»). Hecho: `dev` sale de `main` y ya trae PostGIS.
- [x] 1.9 Conexión con `sslmode=verify-full` (o como mínimo `require`) y `channel_binding=require`.
  Anotar por qué se eligió y qué se descartó. Comprobado: Neon entrega `sslmode=require` y
  `channel_binding=require`. Con `verify-full` y un paquete de CA la conexión entra, y con un CA
  equivocado se rechaza. En los contenedores se usa `verify-full` con el paquete de CA de la imagen.
  `require` se descarta porque cifra pero no comprueba con quién se habla. Para el informe (10.4): el
  TLS lo termina el proxy de Neon; desde la base, `pg_stat_ssl` no ve la conexión cifrada.
- [x] 1.10 Comprobar si el plan gratuito permite restringir direcciones de origen. Lo esperable es que
  no, y además Cloud Run no tiene IP de salida fija sin pagar Cloud NAT: documentarlo como riesgo propio.
  Comprobado: el plan gratuito admite 0 direcciones (`neon ip-allow add` responde «max: 0»).

**Google Cloud**
- [x] 1.11 Proyecto, APIs (Run, Artifact Registry, Secret Manager, Cloud Build, Scheduler) y **alerta
  de presupuesto** de 1 USD para enterarse de cualquier cobro. Hecho: proyecto
  `verdeazul-ce1115-g6`, región por omisión `us-east1`, APIs activas (más IAM Credentials y
  Budgets). La alerta salta al 1 %, 50 % y 100 % de 1 USD y cuenta el costo **antes** de créditos,
  así que avisa aunque un crédito lo esté cubriendo. Ojo: el presupuesto solo avisa, no detiene el
  gasto; lo que lo limita son `max-instances` y la limpieza del registro.
- [x] 1.12 Artifact Registry: repositorio Docker `verdeazul` con **etiquetas inmutables** (así nadie
  puede mover una versión publicada) y política de limpieza que conserve las últimas versiones (la
  capa gratuita es de 0,5 GB). Hecho con `infra/preparar-gcp.sh`: `us-east1-docker.pkg.dev/
  verdeazul-ce1115-g6/verdeazul`. La limpieza (`infra/registro-limpieza.json`) conserva las últimas
  cinco versiones de cada imagen y todas las `v1.x`, y borra lo que tenga más de 30 días o lleve 7
  sin etiqueta.
- [x] 1.13 Una cuenta de servicio por componente: `sa-app`, `sa-emision`, `sa-publico`, `sa-trabajos`.
  **No usar la cuenta de servicio por omisión de Compute**, que tiene rol de editor del proyecto.
  Hecho en `infra/preparar-gcp.sh`. Las cuatro nacen sin roles. Hay una quinta, `sa-build`, para
  Cloud Build: escribe solo en el repositorio `verdeazul`, escribe registros y lee su bucket de
  código (`gs://verdeazul-ce1115-g6_cloudbuild`, en us-east1, que borra el código a los 7 días). A la
  cuenta de Compute se le quitó el rol de editor.
- [x] 1.14 ⚠ Secret Manager: crear `django-secret-key` y `db-url-app`, y dar `secretAccessor` solo a
  `sa-app` sobre esos dos. Cada secreto, solo a quien lo usa. Hecho con `infra/crear-secretos.sh`:
  los valores se generan y viajan por la entrada estándar, sin archivo ni pantalla; los secretos se
  replican solo en us-east1. `db-url-app` usa el usuario nuevo `va_app` (`db/roles/va_app.sql`): sin
  superusuario, sin BYPASSRLS, fuera de `neon_superuser` y sin permiso para crear tablas. Entra por
  el pooler con `verify-full` y channel binding.

**Primera imagen y primer despliegue**
- [x] 1.15 ⚠ Dockerfile de `app`: imagen base delgada fijada por huella, usuario sin privilegios
  (`USER 10001`), sin secretos en ninguna capa, servidor gunicorn. Comprobar con
  `docker run --rm IMAGEN id -u` que no devuelve 0. Hecho: `python:3.14-slim` fijada por huella;
  dependencias instaladas con `--require-hashes` (`infra/fijar-dependencias.sh`); el código queda
  de root y la app corre como 10001. El `.dockerignore` es una lista de permitidos: solo entra
  `app/`. Probado contra la rama `dev`: HTTP → 301 a HTTPS, HTTPS → 200 con HSTS, host ajeno →
  400, POST → 405, y `check --deploy` sin avisos (se silencia solo el de precarga de HSTS, que no
  aplica a `run.app`).
- [x] 1.16 ⚠ Publicar como `app:v0.1.0` y con el hash corto del commit. Nunca solo `latest`. Crear el tag
  de git `v0.1.0` en el mismo commit. Hecho con `infra/publicar.sh`, que construye en Cloud Build con
  `sa-build`: `app:v0.1.0` y `app:git-6a0a1f8` apuntan al mismo digest (`sha256:813075e6…`), y la
  etiqueta de git `v0.1.0` apunta a `6a0a1f8`. En el registro, la imagen declara el usuario `10001`
  y lleva la versión y el commit en sus etiquetas OCI. A Cloud Build solo sube `app/`
  (`.gcloudignore`).
- [x] 1.17 Desplegar `verdeazul-app` desde `infra/service.yaml` (versionado), con `sa-app`, los
  secretos inyectados como variables de entorno, `min-instances=0` y `max-instances=2`. Hecho con
  `infra/app.service.yaml` e `infra/desplegar.sh`; los secretos van en versión fija («1»). Revisión
  `verdeazul-app-00002`.
- [x] 1.18 La página «hola» lee algo de Neon y lo muestra: prueba de que la cadena de conexión llega
  por Secret Manager. Hecho: muestra «conectada · PostgreSQL 18 · PostGIS 3.6.4», leído como `va_app`.
- [x] 1.19 Django detrás del proxy de Google: `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, HSTS,
  cookies `Secure`, `HttpOnly` y `SameSite`. `manage.py check --deploy` sin avisos. Comprobado sobre
  la URL pública: HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` y COOP. HTTP → 302 a
  HTTPS, que hace el frente de Google antes de llegar a Django (evidencia de D-01). TLS 1.3 por
  omisión, acepta 1.2 y rechaza 1.1. POST sin token CSRF → 403. Host ajeno → 400.
- [ ] 1.20 Abrir la URL desde un teléfono con datos móviles, no desde la red de la casa. Ya se probó
  desde esta máquina; falta el teléfono.
- [x] 1.21 README: cómo desplegar y tabla de etiquetas publicadas (versión, commit, fecha, qué trae).

---

## 2 · Base de datos y bitácora (meta: 9 nov)

El segundo candado de la arquitectura (F4): la base no confía en la aplicación.

- [x] 2.1 Modelo de datos de los diez objetos de la matriz: fincas y parcelas (geometría), datos
  personales del dueño, períodos, asignaciones, mediciones con todas sus versiones, enmiendas con sus
  cuatro pasos, certificados, cuentas y roles (con vínculos declarados y habilitaciones temporales),
  bitácora y alertas. Identificadores UUID, no consecutivos.
- [x] 2.2 Estados tal como en la Parte 1: medición (`borrador`, `enviada`, `devuelta`, `aprobada`,
  `excluida`, `sustituida`), período (`planificado`, `abierto`, `cerrado`), certificado (`vigente`,
  `revocado`), y `propuesto` o `aprobado` en catálogo y roles.
  Hecho en `app/cuentas` y `app/negocio` (migraciones 0001, aplicadas en compose y en la rama `dev`).
  La geometría es una columna PostGIS `geometry(Polygon,4326)` sin GeoDjango (`negocio/campos.py`),
  para no meter GDAL en la imagen. Ya quedan en la base: un solo certificado vigente por parcela y
  período (C4), nadie se asigna a sí mismo (C19), nadie resuelve su propia alerta (C15), la fecha de
  medición no es posterior al registro (C2), la temporal lleva motivo y fin (C19) y las fechas del
  período van en orden. `ParametroRol` guarda los umbrales de H1 a H3 y el máximo de 20 asignaciones (K-1).
- [x] 2.3 Usuarios de base, uno por componente, ninguno dueño de las tablas:
  - `va_migraciones`: dueño del esquema; solo para migrar, nunca en ejecución.
  - `va_app`: lo que la matriz permite; sin `DELETE` en mediciones, enmiendas, certificados, cuentas ni
    bitácora; sin `INSERT` en certificados.
  - `va_emision`: el único que inserta certificados y cambia su estado.
  - `va_publico`: solo `SELECT` sobre la vista `v_certificado_publico` (código, sello válido, estado,
    toneladas, período, código del reemplazo; nada del titular, C20).
  - `va_trabajos`: vencimientos, alertas y lectura de la bitácora para verificar la cadena.
  - Opcional: `va_auditor`, conexión de solo lectura para las peticiones de AUD (lo dice la Parte 1).
  Hecho: `nucleo/migrations/0001` crea `va_app`, `va_emision`, `va_publico` y `va_trabajos` sin LOGIN
  (la clave la pone `infra/crear-secretos.sh`); `negocio/sql/0002_permisos.sql` da los permisos tabla
  por tabla. Comprobado como `va_app`: no puede cambiar una versión de medición, emitir un
  certificado ni borrar una medición.

- [ ] 2.4 Un secreto `db-url-*` por usuario, cada uno accesible solo por su cuenta de servicio.
- [x] 2.5 Seguridad por fila: el técnico solo ve filas de sus fincas asignadas (C1) y el dueño solo las
  de su titular (C5). El sujeto se pasa con `SET LOCAL app.usuario = …` dentro de cada transacción
  (cuidado: con el *pooler* de Neon solo funciona `SET LOCAL` dentro de la transacción).
  Hecho en `negocio/sql/0003_seguridad_por_fila.sql`: con `app.usuario` y `app.rol` de la
  transacción, TEC ve solo sus fincas asignadas (y lo que él registró), DUE solo lo de su titular y
  sus mediciones aprobadas, sin rol no se ve nada, y AUD y DUE no escriben en ninguna tabla del
  negocio. La bitácora la leen solo GER y AUD.

- [x] 2.6 Restricciones del segundo candado:
  - Índice único parcial: un solo certificado `vigente` por parcela y período (C4).
  - Disparador que rechaza cambios de mediciones con el período `cerrado` y fechas fuera del período (C2, C14).
  - Restricción de que quien decide no figura en un paso anterior (C3, C8, C10), comparando
    `usuario_id` contra los autores de todas las versiones (K-2).
  - Máximo de asignaciones activas por técnico: un disparador cuenta las vigentes del técnico y
    rechaza la que pase del parámetro, 20 al inicio (K-1).
  - Rechazo de parcelas traslapadas con PostGIS (C11). Un `EXCLUDE` con `&&` solo compara rectángulos:
    usar un disparador con `ST_Overlaps` o `ST_Intersects` sobre el interior.
  - Un rol por persona e identificación única (C12, sección 4 de la matriz).
  - No borrar un titular con certificados dentro del plazo (C16).
  Hecho en `negocio/sql/0004_reglas_en_la_base.sql`. Además: C19 (solo a quien tiene TEC vigente;
  temporal de 15 días como máximo), C8 y C10 en la enmienda, segunda firma de C11, C12 y C14, y los
  valores iniciales de `ParametroRol`. Escenario de prueba en `db/pruebas/reglas.sql`: todas las
  reglas niegan donde deben. Aplicado en compose y en la rama `dev`.

- [x] 2.7 Bitácora encadenada (POL-BT-01 a 06):
  - Campos de POL-BT-02 y de la arquitectura §4.5, incluida la huella SHA-256 del registro anterior.
  - Se escribe solo con una función `bitacora_anexar(...)` (`SECURITY DEFINER`) que toma un candado,
    calcula la huella y añade. `va_app` tiene `EXECUTE` sobre la función y nada más sobre la tabla.
  - Disparador que rechaza `UPDATE` y `DELETE` incluso al dueño.
  - La acción y su registro se confirman en la misma transacción (POL-BT-06: sin registro no hay acción).
  Hecho en `bitacora/sql/0001_bitacora.sql` y `bitacora/registro.py`. Comprobado: `va_app` no puede
  insertar, cambiar ni borrar directo; el dueño choca con el disparador; un registro alterado con el
  disparador apagado lo detecta `bitacora_verificar()` (criterio de aceptación 4).

- [x] 2.8 Datos de prueba con los personajes de los casos T-01 a T-37: técnicos A y otro; verificadores
  B, C (ex técnica, autora de una versión) y uno más; supervisor S; dos gerentes (G y otro, para T-24);
  un administrador; la auditora E con ventana vigente; dos dueños (D persona física y un representante
  de sociedad). Fincas en Pérez Zeledón con geometría, un período abierto y uno cerrado.
  - `manage.py sembrar`: 12 cuentas (`tec.ana`, `tec.tomas`, `ver.bruno`, `ver.carla`, `ver.diego`,
    `sup.sofia`, `ger.gabriela`, `ger.gerardo`, `adm.alberto`, `aud.elena`, `due.daniel`, `due.rosa`),
    8 titulares, 25 fincas con 50 parcelas sin traslapes, 2026-I cerrado y 2026-II abierto.
  - Deja listos T-01 a T-06, T-17, T-27, T-29 y T-38 (T tiene 20 asignaciones activas). Lo comprueba
    `db/pruebas/semilla.sql`.
- [x] 2.9 ⚠ El script de carga lee las contraseñas de una variable de entorno o las genera e imprime
  una sola vez. Ninguna contraseña de prueba en el repositorio.
  - `SEMILLA_CONTRASENA`, `--salida` a un archivo nuevo fuera del repositorio, o impresión solo si la
    salida es una terminal (nunca en los registros de Cloud Run o de CI). Se niega a correr como `va_*`.

---

## 3 · Autenticación y sesión (meta: 10 nov)

- [x] 3.1 ⚠ Argon2id como primer *hasher* de Django (`argon2-cffi`), con sal por usuario (POL-AU-09).
  Comprobar en la base que el campo empieza con `argon2$argon2id$`.
  Hecho: `argon2$argon2id$v=19$m=102400,t=2,p=8$…` (100 MiB, 2 iteraciones, sal propia); PBKDF2
  queda solo para leer resúmenes viejos. `argon2-cffi` 25.1 fijado con huella e instalado en la imagen.
- [x] 3.2 Contraseñas: mínimo 12 caracteres, sin reglas de composición, lista de bloqueo de filtradas
  y que no contenga el nombre de la persona, de la empresa ni de una finca (POL-AU-01 a 03).
  Hecho: longitud mínima 12, lista de comunes de Django, parecido con los datos del usuario y
  `cuentas/validadores.py` contra nombres de la persona, de la empresa y de las fincas. Falta la
  consulta de filtraciones (HIBP por k-anonimato): se decide en el sprint 5.
- [x] 3.3 Segundo factor con django-allauth (TOTP y códigos de recuperación; WebAuthn si da el tiempo).
  Sin SMS ni correo (POL-AU-05).
  - allauth 65.21.1: usuario, contraseña y TOTP; 10 códigos de recuperación de respaldo. Secreto TOTP
    y semilla de los códigos cifrados con Fernet (`MFA_CLAVE`, secreto `mfa-clave`; falta crearlo en
    Secret Manager al desplegar v0.2.0).
  - `cuentas.middleware.ExigirSegundoFactor`: sin TOTP solo se puede activarlo o salir. Nadie lo
    desactiva desde su sesión (POL-AU-10), y no hay registro abierto ni recuperación por correo.
  - En la base, `va_app` solo puede borrar la fila de códigos de recuperación (RLS en
    `mfa_authenticator`); el TOTP no se borra desde la aplicación.
  - WebAuthn no: desviación D-07. Pendiente para 3.7: la protección contra reuso del código y los
    límites de intentos de allauth usan la caché, que hoy es local a cada instancia.
- [x] 3.4 Reautenticación con segundo factor en los cinco minutos previos a aprobar, devolver,
  revisar, autorizar, abrir, cerrar, resolver y exportar (leyenda de la matriz, POL-AU-06).
  - `cuentas.decisiones.requiere_segundo_factor`: solo cuenta un código usado en esta sesión hace menos
    de cinco minutos; la contraseña sola no basta, y un POST sin código reciente no se ejecuta. Cada
    vista de decisión de la fase 5 lo lleva. Pruebas en `cuentas/tests.py` (12 en total con las de 3.3).
- [ ] 3.5 Sesión de servidor en PostgreSQL; identificador nuevo al iniciar sesión; 30 minutos de
  inactividad y 12 horas como máximo (POL-AU-08).
- [ ] 3.6 Revocación inmediata: al cambiar rol, asignaciones, contraseña o al dar de baja, se borran
  todas las sesiones de la persona (POL-CA-04, POL-CA-05: «baja el mismo día»).
- [ ] 3.7 Intentos fallidos: demora creciente desde el quinto y bloqueo de 15 minutos al décimo (POL-AU-07).
- [ ] 3.8 Exclusión dinámica TEC–VER: con una habilitación temporal, la persona entra como técnico o
  como verificador, nunca como ambos en la misma sesión.
- [ ] 3.9 AUD fuera de su ventana no puede iniciar sesión (C6, T-09). OPE no tiene cuenta (T-20).

---

## 4 · Motor de decisión: la matriz en OPA (meta: 11 nov)

- [ ] 4.1 `politica/matriz.json`: la matriz transcrita, una entrada por rol, objeto y verbo, con las
  condiciones de cada celda. Es la fuente única: de aquí salen la política, las pruebas y la tabla de
  cobertura del informe.
- [ ] 4.2 Reglas Rego con el mismo identificador que en la Parte 1: una regla por condición (C1 a C20) y
  por control de historial (H1 a H4). Niega por omisión. La respuesta incluye la decisión (`conceder`,
  `conceder_con_restriccion`, `denegar`) y la regla que la determinó.
- [ ] 4.3 C17 (abstención por vínculo) sobre todo verbo distinto de leer de TEC, VER, SUP, GER y ADM en
  fincas, asignaciones, mediciones y enmiendas.
- [ ] 4.4 ⚠ Dockerfile de `politica`: imagen oficial de OPA fijada por huella, con la política
  incluida, sin root. Publicar como `opa:v…`.
- [ ] 4.5 Sidecar en `verdeazul-app`: OPA escucha en `localhost:8181`, no se expone fuera de la
  instancia (frontera F3). Arranque ordenado con sonda de inicio: si OPA no está listo, la instancia
  no recibe tráfico (K-3).
- [ ] 4.6 Un único módulo en Django que arma los hechos **desde la base, nunca desde la petición**, y
  pregunta al motor. ⚠ **Si OPA no responde, tarda más que el límite o contesta algo inválido, la
  petición se frena** (K-3, criterio de aceptación 6): 503, registro en la bitácora y nada más. Sin
  decisión por omisión, sin caché de decisiones y sin `try/except` que deje seguir.
- [ ] 4.7 Decorador o *middleware* `@protegida(accion, objeto)` en toda ruta, y una prueba que recorre
  todas las URL y falla si alguna no lo declara (criterio de aceptación 2).
- [ ] 4.8 Historial (H1 a H3): eventos de lectura, fincas vistas por sujeto en 90 días, umbrales por rol
  en una tabla que aprueba GER (40, 60 y 80 por día; jornada de lunes a viernes, 6:00 a 19:00, hora de
  Costa Rica). En la misma tabla va el máximo de asignaciones activas por técnico, 20 (K-1). Para la
  demostración, umbrales bajos en un rol de prueba.
- [ ] 4.9 Respuesta graduada: conceder; conceder y avisar; pedir segundo factor y motivo; restringir las
  fincas nuevas hasta el siguiente día hábil.
- [ ] 4.10 La interfaz pregunta al motor qué botones mostrar, solo por comodidad: lo que protege es la
  decisión en el servidor.
- [ ] 4.11 `opa test` con cobertura, `opa check --strict` y Regal en CI.

---

## 5 · Flujos del negocio y pantallas (meta: 13 nov)

Interfaz sobria, con plantillas de Django. Lo que importa es que se pueda ejercitar cada permiso.

- [ ] 5.1 Inicio por rol con las acciones que tiene. Respuesta «no encontrado» igual para lo ajeno y lo
  inexistente (T-08).
- [ ] 5.2 Catálogo: ADM propone alta de finca, cambio de titular o de geometría; GER aprueba (C11).
  Parcelas con mediciones no se editan: versión nueva.
- [ ] 5.3 Cuentas: ADM crea, propone roles y desactiva; GER aprueba; nadie toca su propia cuenta (C12).
  Cada quien cambia su contraseña, sus factores y su declaración de vínculos (C13); retirar un vínculo lo aprueba GER.
- [ ] 5.4 Períodos: ADM registra apertura y cierre con las fechas de la coordinación; GER aprueba. No
  existe reabrir. Al cerrar, los borradores nunca enviados pasan a `excluida` (C14, T-22).
- [ ] 5.5 Asignaciones: SUP crea ordinarias y temporales (motivo y fecha de fin, 15 días máximo,
  renovable); nadie se asigna a sí mismo; vencen solas (C19, T-27, T-28). Un técnico tiene como máximo
  20 asignaciones activas; la pantalla muestra cuántas lleva (K-1, T-38, T-39).
- [ ] 5.6 Mediciones: TEC crea, modifica (versión nueva) y envía; fecha de medición declarada y fecha
  de registro del servidor (C2, T-30). VER aprueba o devuelve con observaciones (C3); el formulario de
  aprobación no lleva ningún campo de aprobador, que sale de la sesión (K-2, T-40). Más de cinco días
  hábiles entre las dos fechas pide motivo.
- [ ] 5.7 Enmiendas: solicitar (TEC, VER o GER, C7), corregir en 10 días hábiles como versión propuesta
  (C9), revisión técnica independiente con cálculo de materialidad (C10), autorización final de GER que
  registra si el certificado fue comercializado (C8).
- [ ] 5.8 Alertas: SUP atiende las de sus técnicos; GER las demás y las que SUP no resuelva en dos días
  hábiles; nadie resuelve una sobre sí mismo (C15, T-36).
- [ ] 5.9 Datos personales: ADM los mantiene; supresión solo si no hay obligación de conservar (C16, T-37).
- [ ] 5.10 DUE ve lo de sus fincas y solo mediciones aprobadas (C5).
- [ ] 5.11 AUD ve todo y exporta paquetes sellados, con su identidad, sin datos personales y con la
  huella en la bitácora (C18, T-31).
- [ ] 5.12 GER y AUD leen la bitácora; cada lectura queda registrada (POL-BT-05).
- [ ] 5.13 ⚠ Todo acceso a datos por el ORM o con consultas parametrizadas. Prohibido `raw()` con
  cadenas armadas, `extra()`, `eval` y `pickle` sobre datos externos (regla de Bandit y Ruff).
- [ ] 5.14 Sin el sitio de administración de Django: edita cualquier tabla saltándose las reglas.

---

## 6 · Certificados firmados y comprobación (meta: 14 nov)

- [ ] 6.1 ⚠ Generar la clave Ed25519 en Cloud Shell y subirla directamente a Secret Manager como
  `firma-clave-privada` (por la entrada estándar, sin dejarla en disco). Solo `sa-emision` tiene acceso.
- [ ] 6.2 Publicar la clave pública y su huella: en el README, en `docs/` y en una ruta
  `/.well-known/verdeazul-clave.pem` del servicio público. No es secreta.
- [ ] 6.3 Servicio de emisión (`verdeazul-emision`): sin acceso público; solo `sa-app` tiene
  `run.invoker`. Recibe el identificador de una medición aprobada, comprueba C4 con su propio usuario de
  base, firma e inserta. Ninguna persona puede invocar la emisión directamente.
- [ ] 6.4 Contenido firmado: código, parcela, finca (por código), período, toneladas, fecha de emisión,
  nombre de quien aprobó (POL-CE-04), código del certificado al que reemplaza, algoritmo, identificador
  de la clave, clave pública y firma.
- [ ] 6.5 Revocar y reemitir en una sola transacción cuando una enmienda autorizada cambia las toneladas;
  los dos quedan enlazados y ninguno se borra (C4, T-25). Si no cambian, se anota la enmienda.
- [ ] 6.6 Verificación en `verdeazul-publico` («dado el archivo»): se sube el certificado y responde si la
  firma es válida, si el contenido fue modificado y **si la clave incrustada es la de Verdeazul**. Sin esa
  última comprobación, cualquiera podría firmar un certificado falso con su propia clave e incrustarla.
- [ ] 6.7 Comprobación por código (C20): sello válido, estado, toneladas, período y, si fue revocado, el
  código del reemplazo. Sin listados, búsquedas ni datos del titular. Límite de ritmo por origen.
- [ ] 6.8 `verificador/`: programa de línea de comandos que verifica un certificado sin conexión al
  sistema. Es lo que haría un comprador en otro país.
- [ ] 6.9 Demostración preparada: un certificado válido, el mismo con una tonelada cambiada (debe
  fallar) y uno revocado consultado por código (T-32).
- [ ] 6.10 Sellar los paquetes de exportación del auditor con la misma clave, por el servicio de emisión (C18).

---

## 7 · Trabajos programados y testigo (meta: 14 nov)

- [ ] 7.1 ⚠ Imagen `trabajos:v…` y Cloud Run Jobs con `sa-trabajos`, disparados por Cloud Scheduler
  (la capa gratuita cubre pocos trabajos: agruparlos en uno o dos).
- [ ] 7.2 Vencimientos: asignaciones temporales, habilitaciones de técnico, ventanas de auditor y cuentas
  sin uso en 45 días (POL-CA-06).
- [ ] 7.3 Verificación diaria de la cadena de la bitácora y aviso si se rompe (criterio de aceptación 4).
- [ ] 7.4 Escalamiento de alertas que SUP no resolvió en dos días hábiles (C15).
- [ ] 7.5 Testigo externo según la decisión 0.6.

---

## 8 · Pruebas de la matriz (continuo; cerrar el 15 nov)

- [ ] 8.1 Los 37 casos T-01 a T-37 como pruebas automáticas, con el mismo identificador, más los
  cuatro de los cambios K-1 a K-3:
  - T-38: SUP intenta dar a un técnico con 20 asignaciones activas la número 21. Deniega (K-1, C19).
  - T-39: el técnico tiene 20 asignaciones, una temporal vence y SUP crea otra. Concede: las vencidas
    no cuentan (K-1).
  - T-40: B, que figura entre los autores de una medición, intenta aprobarla enviando en la petición
    el `aprobador_id` de otro verificador. Deniega: el campo se ignora y C3 compara el ID de la sesión
    (K-2).
  - T-41: con OPA detenido, cualquier rol pide cualquier acción. Se frena con 503, no se ejecuta nada
    y queda en la bitácora (K-3).
- [ ] 8.2 Una prueba por cada una de las **38 celdas denegadas** (lo pide la Parte 1, §7).
- [ ] 8.3 Una prueba por cada uno de los **102 permisos** concedidos: el caso feliz.
- [ ] 8.4 Las mismas pruebas contra OPA (`opa test`) y contra la base (seguridad por fila y
  restricciones): las dos copias de la regla no pueden divergir (RR-10).
- [ ] 8.5 Pruebas de sistema: el motor caído frena todo (T-41, también con OPA lento y con una
  respuesta inválida); con la bitácora sin poder escribir, la operación se rechaza; un registro
  alterado rompe la cadena.
- [ ] 8.6 Cambio de identificador con cada rol (IDOR), a mano o con OWASP ZAP (criterio de aceptación 3).
- [ ] 8.7 Generar la tabla de cobertura del informe a partir de `matriz.json` y del resultado de las
  pruebas: permiso, dónde está (regla Rego, vista, restricción de base) y qué prueba lo comprueba.
- [ ] 8.8 CI en GitHub Actions: ruff, bandit, mypy, pip-audit, pytest, `opa test`, gitleaks y Trivy
  sobre las imágenes.
- [ ] 8.9 **Nada de pruebas de carga contra Cloud Run ni Neon**: se pagan. Las pruebas corren en local o
  contra la rama `dev`.

---

## 9 · Endurecimiento e higiene (meta: 16 nov)

- [ ] 9.1 ⚠ Las cinco imágenes (`app`, `opa`, `emision`, `publico`, `trabajos`) sin root, fijadas por
  huella, analizadas con Trivy y publicadas con versión. Cloud Run despliega por etiqueta de versión.
- [ ] 9.2 Atender al menos una alerta de Dependabot y documentarla: qué paquete, qué vulnerabilidad, qué
  versión se subió, en qué commit y en qué etiqueta de imagen quedó. Si no aparece ninguna, documentar
  una actualización de versión que haya propuesto y cómo se revisó.
- [ ] 9.3 ⚠ Pasar gitleaks sobre **toda la historia** del repositorio, no solo sobre el último commit.
- [ ] 9.4 `check --deploy`, Mozilla HTTP Observatory sobre la URL pública y una pasada de OWASP ZAP en
  modo base (sin ataque masivo).
- [ ] 9.5 IAM mínimo: quién del equipo tiene qué rol en el proyecto (esta es la fila OPE de la matriz).
  Nadie del equipo usa la cuenta de servicio de emisión.
- [ ] 9.6 Etiqueta final `v1.0.0` de las cinco imágenes y de git en el mismo commit. Anotar la tabla de
  versiones en el README.

---

## 10 · Informe de implementación, 6 a 10 páginas (meta: 17 nov)

En LaTeX, con la misma plantilla de los entregables de la Parte 1. Capturas en `docs/evidencia/`.

- [ ] 10.1 Arquitectura desplegada: diagrama de lo que realmente se construyó (servicios, imágenes,
  cuentas de servicio, secretos, Neon) y cómo se comunican, con F1 a F5 marcadas.
- [ ] 10.2 Controles implementados: por cada uno de los seis obligatorios, archivo y línea donde está y
  cómo se verifica.
- [ ] 10.3 Gestión de secretos: tabla con cada secreto, quién lo lee, cómo llega al contenedor y qué
  versión usa.
- [ ] 10.4 Seguridad heredada (media página por plataforma):
  - Neon: qué protege solo (cifrado en reposo y en tránsito, aislamiento del proyecto, respaldos y
    recuperación a un punto en el tiempo, autenticación de la conexión).
  - Qué configuramos: modo de conexión, direcciones de origen, usuario de la app y sus permisos, ramas.
  - Por qué y qué se descartó.
  - Qué sigue siendo nuestro: consultas mal construidas, permisos excesivos, credenciales filtradas, y
    qué amenaza del modelo de la Parte 1 no cubre la plataforma. No escribir «Neon es seguro» sin decir
    contra qué.
  - Cloud Run: Google protege la infraestructura y termina el TLS; nosotros, el código, los permisos y
    los secretos.
- [ ] 10.5 Desviaciones D-01 en adelante.
- [ ] 10.6 Tabla de cobertura de la matriz (sale de 8.7).
- [ ] 10.7 Evidencia: el sistema por HTTPS, la configuración de Secret Manager, Dependabot activo, un
  certificado verificado, uno alterado rechazado y el intento fallido de un rol.
- [ ] 10.8 Anexo para el profesor, **fuera del repositorio**: URL pública y credenciales de prueba de
  cada rol, con la semilla TOTP de cada cuenta.

---

## 11 · Presentación, 15 minutos (17 al 19 nov)

- [ ] 11.1 Guion con los seis puntos que pide el enunciado: HTTPS desde internet; un usuario de cada rol
  haciendo lo suyo; un intento prohibido rechazado; emisión, verificación y certificado alterado que
  falla; la bitácora con esas acciones; la configuración de secretos y de Dependabot.
- [ ] 11.2 El intento prohibido, enviado **sin la interfaz** (curl o las herramientas del navegador con
  la cookie de un técnico que pide aprobar su propia medición): demuestra que decide el servidor.
- [ ] 11.3 Recorrido de casos en vivo con los personajes de la matriz (T-05, T-06, T-25, T-32…).
- [ ] 11.4 Calentar las instancias antes de presentar (Cloud Run y Neon se suspenden sin uso y la
  primera petición tarda).
- [ ] 11.5 Prueba completa desde una red distinta la noche anterior.
- [ ] 11.6 Cada integrante explica una parte que no escribió: ensayo cruzado.

---

## 12 · Después de la nota (no antes)

- [ ] 12.1 Mantener el sistema en línea hasta que el profesor publique la nota.
- [ ] 12.2 **Recuperar el prepago de 30 USD.** En la consola: *Facturación → Descripción general de
  pagos → Solicitar reembolso*, **antes** de cerrar la cuenta. Si es una cuenta *Prepay*, el saldo se
  pierde al cerrarla; pidiendo primero el reembolso, el orden cubre los dos casos. Vuelve a la
  tarjeta original.
- [ ] 12.3 Cerrar la cuenta de facturación y borrar el proyecto `verdeazul-ce1115-g6`.
- [ ] 12.4 Borrar el proyecto de Neon o dejarlo en el plan gratuito.

---

## Inventario de la matriz: lo que hay que implementar

102 permisos concedidos y 38 celdas denegadas. Marcar cada rol cuando todos sus permisos tengan
implementación **y** prueba.

- [ ] **TEC (12).** Fincas: leer (C1). Datos del dueño: leer solo contacto (C1). Períodos: leer.
  Asignaciones: leer las propias (C1). Mediciones: leer (C1), crear, modificar y enviar (C2). Enmiendas:
  leer (C1), solicitar (C7), corregir (C9). Cuentas: modificar las propias (C13). Denegadas: certificados,
  bitácora, alertas.
- [ ] **VER (10).** Fincas: leer (H). Períodos: leer. Mediciones: leer (H), aprobar y devolver (C3).
  Enmiendas: leer, solicitar (C7), revisar (C10). Certificados: leer (H). Cuentas: modificar (C13).
  Denegadas: datos del dueño, asignaciones, bitácora, alertas.
- [ ] **SUP (10).** Fincas: leer (H). Períodos: leer. Asignaciones: leer, crear y modificar (C19,
  máximo 20 activas por técnico).
  Mediciones: leer solo estado y fechas (H). Enmiendas: leer solo estado. Cuentas: modificar (C13).
  Alertas: leer y resolver (C15). Denegadas: datos del dueño, certificados, bitácora.
- [ ] **GER (18).** Fincas: leer (H), aprobar (C11). Datos del dueño: leer (H). Períodos: leer, abrir y
  cerrar (C14). Asignaciones: leer. Mediciones: leer (H). Enmiendas: leer, solicitar (C7), autorizar (C8).
  Certificados: leer (H). Cuentas: leer, aprobar (C12), modificar (C13). Bitácora: leer. Alertas: leer y
  resolver (C15). Sin celdas denegadas.
- [ ] **ADM (14).** Fincas: leer (H), proponer (C11). Datos del dueño: leer (H), crear, modificar,
  eliminar (C16). Períodos: leer, crear, proponer (C14). Cuentas: leer, crear, desactivar y proponer
  (C12), modificar (C13). Denegadas: asignaciones, mediciones, enmiendas, certificados, bitácora, alertas.
- [ ] **AUD (19).** Leer los diez objetos (C6). Exportar (C18) fincas, períodos, asignaciones,
  mediciones, enmiendas, certificados, bitácora y alertas. Cuentas: modificar las propias (C13). Sin
  celdas denegadas; ningún verbo de escritura sobre el negocio (T-10).
- [ ] **DUE (8).** Leer (C5) fincas, datos, asignaciones, mediciones (solo aprobadas), enmiendas y
  certificados; períodos: leer. Cuentas: modificar (C13). Denegadas: bitácora, alertas.
- [ ] **SIS (10).** Leer fincas, nombre del titular, períodos, asignaciones, mediciones y enmiendas.
  Certificados: emitir y revocar (C4). Bitácora: anexar. Alertas: crear. Denegada: cuentas.
- [ ] **OPE (0).** Diez celdas denegadas: no tiene cuenta en la aplicación (T-20).
- [ ] **PUB (1).** Certificados: comprobar (C20). Nueve celdas denegadas.

### Reglas y sus casos de prueba

- [ ] C1 asignación vigente: T-01, T-02, T-27
- [ ] C2 edición solo en borrador: T-01, T-03, T-04, T-21, T-30
- [ ] C3 quien registró no aprueba, por ID de usuario: T-05, T-06, T-17, T-26, T-40
- [ ] C4 emisión única: T-07, T-25
- [ ] C5 solo lo suyo: T-08
- [ ] C6 ventana de auditoría: T-09
- [ ] C7 solicitar enmienda: T-11, T-21
- [ ] C8 autorización final: T-12, T-24
- [ ] C9 corregir dentro del plazo: T-13
- [ ] C10 revisión técnica independiente: T-14, T-23
- [ ] C11 catálogo con segunda firma: T-15
- [ ] C12 nadie se administra a sí mismo: T-16
- [ ] C13 credenciales y declaración propias: T-35
- [ ] C14 apertura y cierre entre dos: T-04, T-17, T-22
- [ ] C15 alertas ajenas: T-36
- [ ] C16 supresión condicionada: T-37
- [ ] C17 abstención por vínculo: T-29
- [ ] C18 exportar evidencia: T-31
- [ ] C19 asignar con vigencia y máximo de 20 activas: T-27, T-28, T-38, T-39
- [ ] C20 comprobación pública: T-32
- [ ] H1 frecuencia: T-02, T-18
- [ ] H2 tiempo: T-34
- [ ] H3 combinada: T-19, T-33
- [ ] H4 secuencia (C3, C8, C10): T-06, T-14, T-24
- [ ] Filas sin acceso: T-10 (AUD no escribe), T-20 (OPE no entra)
- [ ] Fallo cerrado del motor (K-3): T-41

### Políticas que deben tener reflejo técnico

- [ ] POL-CA-04 y POL-CA-05: cambio de puesto y baja el mismo día cierran sesiones y asignaciones.
- [ ] POL-CA-06: suspensión automática a los 45 días sin uso.
- [ ] POL-CA-07: cuentas de auditor con inicio y fin, que vencen solas.
- [ ] POL-CA-10: nadie se administra a sí mismo.
- [ ] POL-CA-14: declaración de vínculos y abstención.
- [ ] POL-AU-01 a POL-AU-09: contraseña, segundo factor, reautenticación, intentos, sesión, Argon2id.
- [ ] POL-BT-01 a POL-BT-06: qué se registra, campos, solo agregar, quién la lee, sin registro no hay acción.
- [ ] POL-CE-01 a POL-CE-04: períodos entre dos, enmienda formal, certificado afectado, autenticidad y estado.

---

## Cuidado con el consumo

Todo debe caber en las capas gratuitas. Confirmar los límites al crear las cuentas:

- Cloud Run: `min-instances=0` y `max-instances` bajo en los cuatro servicios.
- Neon: 0,5 GB de almacenamiento en el plan gratuito; la base se suspende sola sin uso.
- Artifact Registry: 0,5 GB gratis; la política de limpieza borra versiones viejas, **pero nunca la
  que está desplegada**.
- Secret Manager: pocas versiones activas gratis; destruir las versiones viejas al rotar.
- Cloud Scheduler: pocos trabajos gratis por cuenta de facturación.
- Alerta de presupuesto activa desde el día uno (1.11).

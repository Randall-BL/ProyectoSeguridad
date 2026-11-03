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
- [ ] D-06… (las que aparezcan: segundo factor, testigo externo, versión de Python, etc.)

---

## 0 · Decisiones que hay que tomar ya (3–4 nov)

- [ ] **0.1 Cuenta de Google Cloud.** Cloud Run exige una cuenta de facturación con tarjeta. El
  enunciado pide **avisar al profesor antes de registrar una tarjeta**: hay créditos educativos.
  Preguntarle hoy. Definir quién es el dueño del proyecto e invitar a los otros tres.
- [ ] **0.2 Región.** Una región de Cloud Run cercana a la de Neon (por ejemplo `us-east1` con Neon en
  AWS `us-east-1`). Confirmar que la región elegida entra en la capa gratuita.
- [ ] **0.3 Formato del certificado.** Recomendado: **JSON canónico firmado con Ed25519** (claves
  ordenadas, sin espacios), con la clave pública y su huella incrustadas, más una versión legible en
  PDF o HTML que incluya el código y un QR. Alternativa más vistosa y más cara de hacer: PDF firmado
  (PAdES) con pyHanko, que también verifica Adobe Reader. Decidir antes de la fase 6.
- [ ] **0.4 Segundo factor en las cuentas de prueba.** POL-AU-05 lo exige para todos los roles, pero
  el profesor tiene que poder entrar con cada rol. Recomendado: TOTP en todas las cuentas de prueba y
  entregar la semilla de cada una **en el informe**, nunca en el repositorio. WebAuthn queda como
  mejora si da el tiempo (si no, desviación D-06).
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
- [ ] 1.1 Estructura del repositorio:
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
- [ ] 1.2 Copiar los PDF de la Parte 1 a `docs/parte1/`, para que los cuatro trabajen con el mismo diseño.
- [ ] 1.3 ⚠ `.gitignore` con `.env`, `*.pem`, `*.key`, `credenciales*`, `.venv/`. Un `.env.example` con
  los nombres de las variables y valores vacíos.
- [ ] 1.4 ⚠ gitleaks: gancho *pre-commit* y paso en CI. Activar *secret scanning* y *push protection*
  en GitHub (gratis en repos públicos).
- [ ] 1.5 Dependabot: activar alertas y actualizaciones de seguridad en *Settings → Code security*, y
  `.github/dependabot.yml` con los ecosistemas `pip`, `docker` y `github-actions`.
- [ ] 1.6 Entorno local: `docker compose` con PostGIS y OPA, solo para desarrollar (lo que se evalúa es
  la nube). Dejar el `.venv` fuera de OneDrive o excluido de la sincronización.

**Neon**
- [ ] 1.7 Crear el proyecto y la base `verdeazul`, en la región elegida. Activar la extensión PostGIS.
- [ ] 1.8 Rama `main` para producción y rama `dev` para desarrollo y pruebas (va al informe: «entornos separados»).
- [ ] 1.9 Conexión con `sslmode=verify-full` (o como mínimo `require`) y `channel_binding=require`.
  Anotar por qué se eligió y qué se descartó.
- [ ] 1.10 Comprobar si el plan gratuito permite restringir direcciones de origen. Lo esperable es que
  no, y además Cloud Run no tiene IP de salida fija sin pagar Cloud NAT: documentarlo como riesgo propio.

**Google Cloud**
- [ ] 1.11 Proyecto, APIs (Run, Artifact Registry, Secret Manager, Cloud Build, Scheduler) y **alerta
  de presupuesto** de 1 USD para enterarse de cualquier cobro.
- [ ] 1.12 Artifact Registry: repositorio Docker `verdeazul` con **etiquetas inmutables** (así nadie
  puede mover una versión publicada) y política de limpieza que conserve las últimas versiones (la
  capa gratuita es de 0,5 GB).
- [ ] 1.13 Una cuenta de servicio por componente: `sa-app`, `sa-emision`, `sa-publico`, `sa-trabajos`.
  **No usar la cuenta de servicio por omisión de Compute**, que tiene rol de editor del proyecto.
- [ ] 1.14 ⚠ Secret Manager: crear `django-secret-key` y `db-url-app`, y dar `secretAccessor` solo a
  `sa-app` sobre esos dos. Cada secreto, solo a quien lo usa.

**Primera imagen y primer despliegue**
- [ ] 1.15 ⚠ Dockerfile de `app`: imagen base delgada fijada por huella, usuario sin privilegios
  (`USER 10001`), sin secretos en ninguna capa, servidor gunicorn. Comprobar con
  `docker run --rm IMAGEN id -u` que no devuelve 0.
- [ ] 1.16 ⚠ Publicar como `app:v0.1.0` y con el hash corto del commit. Nunca solo `latest`. Crear el tag
  de git `v0.1.0` en el mismo commit.
- [ ] 1.17 Desplegar `verdeazul-app` desde `infra/service.yaml` (versionado), con `sa-app`, los
  secretos inyectados como variables de entorno, `min-instances=0` y `max-instances=2`.
- [ ] 1.18 La página «hola» lee algo de Neon y lo muestra: prueba de que la cadena de conexión llega
  por Secret Manager.
- [ ] 1.19 Django detrás del proxy de Google: `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, HSTS,
  cookies `Secure`, `HttpOnly` y `SameSite`. `manage.py check --deploy` sin avisos.
- [ ] 1.20 Abrir la URL desde un teléfono con datos móviles, no desde la red de la casa.
- [ ] 1.21 README: cómo desplegar y tabla de etiquetas publicadas (versión, commit, fecha, qué trae).

---

## 2 · Base de datos y bitácora (meta: 9 nov)

El segundo candado de la arquitectura (F4): la base no confía en la aplicación.

- [ ] 2.1 Modelo de datos de los diez objetos de la matriz: fincas y parcelas (geometría), datos
  personales del dueño, períodos, asignaciones, mediciones con todas sus versiones, enmiendas con sus
  cuatro pasos, certificados, cuentas y roles (con vínculos declarados y habilitaciones temporales),
  bitácora y alertas. Identificadores UUID, no consecutivos.
- [ ] 2.2 Estados tal como en la Parte 1: medición (`borrador`, `enviada`, `devuelta`, `aprobada`,
  `excluida`, `sustituida`), período (`planificado`, `abierto`, `cerrado`), certificado (`vigente`,
  `revocado`), y `propuesto` o `aprobado` en catálogo y roles.
- [ ] 2.3 Usuarios de base, uno por componente, ninguno dueño de las tablas:
  - `va_migraciones`: dueño del esquema; solo para migrar, nunca en ejecución.
  - `va_app`: lo que la matriz permite; sin `DELETE` en mediciones, enmiendas, certificados, cuentas ni
    bitácora; sin `INSERT` en certificados.
  - `va_emision`: el único que inserta certificados y cambia su estado.
  - `va_publico`: solo `SELECT` sobre la vista `v_certificado_publico` (código, sello válido, estado,
    toneladas, período, código del reemplazo; nada del titular, C20).
  - `va_trabajos`: vencimientos, alertas y lectura de la bitácora para verificar la cadena.
  - Opcional: `va_auditor`, conexión de solo lectura para las peticiones de AUD (lo dice la Parte 1).
- [ ] 2.4 Un secreto `db-url-*` por usuario, cada uno accesible solo por su cuenta de servicio.
- [ ] 2.5 Seguridad por fila: el técnico solo ve filas de sus fincas asignadas (C1) y el dueño solo las
  de su titular (C5). El sujeto se pasa con `SET LOCAL app.usuario = …` dentro de cada transacción
  (cuidado: con el *pooler* de Neon solo funciona `SET LOCAL` dentro de la transacción).
- [ ] 2.6 Restricciones del segundo candado:
  - Índice único parcial: un solo certificado `vigente` por parcela y período (C4).
  - Disparador que rechaza cambios de mediciones con el período `cerrado` y fechas fuera del período (C2, C14).
  - Restricción de que quien decide no figura en un paso anterior (C3, C8, C10).
  - Rechazo de parcelas traslapadas con PostGIS (C11). Un `EXCLUDE` con `&&` solo compara rectángulos:
    usar un disparador con `ST_Overlaps` o `ST_Intersects` sobre el interior.
  - Un rol por persona e identificación única (C12, sección 4 de la matriz).
  - No borrar un titular con certificados dentro del plazo (C16).
- [ ] 2.7 Bitácora encadenada (POL-BT-01 a 06):
  - Campos de POL-BT-02 y de la arquitectura §4.5, incluida la huella SHA-256 del registro anterior.
  - Se escribe solo con una función `bitacora_anexar(...)` (`SECURITY DEFINER`) que toma un candado,
    calcula la huella y añade. `va_app` tiene `EXECUTE` sobre la función y nada más sobre la tabla.
  - Disparador que rechaza `UPDATE` y `DELETE` incluso al dueño.
  - La acción y su registro se confirman en la misma transacción (POL-BT-06: sin registro no hay acción).
- [ ] 2.8 Datos de prueba con los personajes de los casos T-01 a T-37: técnicos A y otro; verificadores
  B, C (ex técnica, autora de una versión) y uno más; supervisor S; dos gerentes (G y otro, para T-24);
  un administrador; la auditora E con ventana vigente; dos dueños (D persona física y un representante
  de sociedad). Fincas en Pérez Zeledón con geometría, un período abierto y uno cerrado.
- [ ] 2.9 ⚠ El script de carga lee las contraseñas de una variable de entorno o las genera e imprime
  una sola vez. Ninguna contraseña de prueba en el repositorio.

---

## 3 · Autenticación y sesión (meta: 10 nov)

- [ ] 3.1 ⚠ Argon2id como primer *hasher* de Django (`argon2-cffi`), con sal por usuario (POL-AU-09).
  Comprobar en la base que el campo empieza con `argon2$argon2id$`.
- [ ] 3.2 Contraseñas: mínimo 12 caracteres, sin reglas de composición, lista de bloqueo de filtradas
  y que no contenga el nombre de la persona, de la empresa ni de una finca (POL-AU-01 a 03).
- [ ] 3.3 Segundo factor con django-allauth (TOTP y códigos de recuperación; WebAuthn si da el tiempo).
  Sin SMS ni correo (POL-AU-05).
- [ ] 3.4 Reautenticación con segundo factor en los cinco minutos previos a aprobar, devolver,
  revisar, autorizar, abrir, cerrar, resolver y exportar (leyenda de la matriz, POL-AU-06).
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
  instancia (frontera F3). Arranque ordenado con sonda de inicio.
- [ ] 4.6 Un único módulo en Django que arma los hechos **desde la base, nunca desde la petición**, y
  pregunta al motor. Si OPA no responde o tarda, se deniega (criterio de aceptación 6).
- [ ] 4.7 Decorador o *middleware* `@protegida(accion, objeto)` en toda ruta, y una prueba que recorre
  todas las URL y falla si alguna no lo declara (criterio de aceptación 2).
- [ ] 4.8 Historial (H1 a H3): eventos de lectura, fincas vistas por sujeto en 90 días, umbrales por rol
  en una tabla que aprueba GER (40, 60 y 80 por día; jornada de lunes a viernes, 6:00 a 19:00, hora de
  Costa Rica). Para la demostración, umbrales bajos en un rol de prueba.
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
  renovable); nadie se asigna a sí mismo; vencen solas (C19, T-27, T-28).
- [ ] 5.6 Mediciones: TEC crea, modifica (versión nueva) y envía; fecha de medición declarada y fecha
  de registro del servidor (C2, T-30). VER aprueba o devuelve con observaciones (C3). Más de cinco días
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

- [ ] 8.1 Los 37 casos T-01 a T-37 como pruebas automáticas, con el mismo identificador.
- [ ] 8.2 Una prueba por cada una de las **38 celdas denegadas** (lo pide la Parte 1, §7).
- [ ] 8.3 Una prueba por cada uno de los **102 permisos** concedidos: el caso feliz.
- [ ] 8.4 Las mismas pruebas contra OPA (`opa test`) y contra la base (seguridad por fila y
  restricciones): las dos copias de la regla no pueden divergir (RR-10).
- [ ] 8.5 Pruebas de sistema: el motor caído deniega; con la bitácora sin poder escribir, la operación se
  rechaza; un registro alterado rompe la cadena.
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
- [ ] **SUP (10).** Fincas: leer (H). Períodos: leer. Asignaciones: leer, crear y modificar (C19).
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
- [ ] C3 quien registró no aprueba: T-05, T-06, T-17, T-26
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
- [ ] C19 asignar con vigencia: T-27, T-28
- [ ] C20 comprobación pública: T-32
- [ ] H1 frecuencia: T-02, T-18
- [ ] H2 tiempo: T-34
- [ ] H3 combinada: T-19, T-33
- [ ] H4 secuencia (C3, C8, C10): T-06, T-14, T-24
- [ ] Filas sin acceso: T-10 (AUD no escribe), T-20 (OPE no entra)

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

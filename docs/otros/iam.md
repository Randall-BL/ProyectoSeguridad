# Permisos en Google Cloud (IAM mínimo, tarea 9.5)

Proyecto `verdeazul-ce1115-g6`, región `us-east1`. Revisado el 15 de noviembre de 2026 con
`gcloud projects get-iam-policy` y las políticas de cada recurso. Es la fila **OPE** de la matriz: el
operador de la plataforma administra la infraestructura y no tiene cuenta en la aplicación (T-20).

## Personas

| Quién | Rol | Para qué |
|---|---|---|
| Randall (cuenta personal, dueña del proyecto y de la facturación) | `roles/owner` | Crear la infraestructura, publicar y desplegar. |
| Javier, Julio y Axel | — | Pendiente de invitar. Recomendado: `roles/viewer` y `roles/logging.viewer`, sin acceso a los secretos ni a las cuentas de servicio. |

Nadie del equipo tiene `iam.serviceAccountUser` ni `iam.serviceAccountTokenCreator` sobre ninguna
cuenta de servicio: nadie puede firmar como `sa-emision` ni leer sus secretos por fuera del servicio.

## Cuentas de servicio

Cada componente corre con su propia cuenta. Ninguna tiene roles a nivel de proyecto: todo se da sobre
el recurso concreto.

| Cuenta | La usa | Puede |
|---|---|---|
| `sa-app` | servicio `verdeazul-app` | Leer `django-secret-key`, `mfa-clave` y `db-url-app`. Invocar `verdeazul-emision`. |
| `sa-emision` | servicio `verdeazul-emision` | Leer `firma-clave-privada` y `db-url-emision`. |
| `sa-publico` | servicio `verdeazul-publico` | Leer `db-url-publico`. |
| `sa-trabajos` | trabajo `verdeazul-trabajos` y el disparador `verdeazul-diario` | Leer `db-url-trabajos`. Invocar `verdeazul-emision`. Iniciar su propio trabajo. |
| `sa-build` | Cloud Build (`infra/publicar.sh`) | Escribir imágenes solo en el repositorio `verdeazul` de Artifact Registry, leer el código subido y escribir sus registros. |

La cuenta predeterminada de Compute no tiene el rol Editor (`infra/preparar-gcp.sh` se lo quita) y
ningún servicio la usa.

## Quién puede invocar cada servicio

| Recurso | `run.invoker` |
|---|---|
| `verdeazul-app` | `allUsers` (es la aplicación pública; la autenticación es la de la aplicación) |
| `verdeazul-publico` | `allUsers` (comprobación pública de certificados, rol PUB) |
| `verdeazul-emision` | solo `sa-app` y `sa-trabajos`; además el servicio rechaza cualquier otra cuenta (`INVOCADORES`) |
| `verdeazul-trabajos` (Cloud Run Job) | solo `sa-trabajos` |

## Secretos

| Secreto | Lector único | Versión en uso |
|---|---|---|
| `django-secret-key` | `sa-app` | 1 |
| `mfa-clave` | `sa-app` | 1 |
| `db-url-app` | `sa-app` | 1 |
| `db-url-emision` | `sa-emision` | 1 |
| `db-url-publico` | `sa-publico` | 1 |
| `db-url-trabajos` | `sa-trabajos` | 1 |
| `firma-clave-privada` | `sa-emision` | 1 |

Los agentes de servicio de Google (`service-708901712393@gcp-sa-…`) tienen los roles que cada producto
les asigna para funcionar; no se tocaron.

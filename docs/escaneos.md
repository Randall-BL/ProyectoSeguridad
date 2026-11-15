# Escaneos de la URL pública (tarea 9.4)

Pasadas sin ataque (modo base o pasivo) sobre las dos direcciones públicas, antes y después del
endurecimiento. Ninguna es una prueba de carga: cada una hace unas decenas de peticiones (8.9).

## `manage.py check --deploy`

Con los ajustes de producción (`DJANGO_DEBUG=False`, el host de Cloud Run y una llave larga): **sin
problemas**. Se silencia a propósito un solo aviso, `security.W021` (HSTS *preload*): el dominio
`*.run.app` es de Google y no podemos inscribirlo en la lista de precarga de los navegadores.

## Mozilla HTTP Observatory

| Sitio | Antes (`v0.4.0`, 15-nov) | Después (`v1.0.0`, 15-nov) |
|---|---|---|
| `verdeazul-app-708901712393.us-east1.run.app` | **C** (55): sin política de contenido (−25) y sin HSTS visto por el analizador (−20) | **A+** (155), 12 pruebas pasan, ninguna resta |
| `verdeazul-publico-708901712393.us-east1.run.app` | **A+** (135) | **A+** (135) |

Lo que cambió en la aplicación (`app/nucleo/cabeceras.py`, commit `54e3c1f`):

- **Política de contenido:** `default-src 'none'`, estilos e imágenes del propio origen y `data:` solo
  para el QR del autenticador, formularios al propio origen y `frame-ancestors 'none'`. La interfaz no
  usa JavaScript, así que no se permite ningún script.
- **Otras cabeceras:** `Permissions-Policy`, `Cross-Origin-Resource-Policy`,
  `Cross-Origin-Embedder-Policy` y `Cache-Control: no-store` en las páginas.
- **WhiteNoise** ya no manda `Access-Control-Allow-Origin: *` en los estilos.

## OWASP ZAP 2.17.0, `zap-baseline.py` (araña de un minuto y reglas pasivas)

Informes completos en [`evidencia/escaneos/`](evidencia/escaneos/).

| Sitio | Fallos | Avisos antes | Avisos después |
|---|---|---|---|
| Aplicación | 0 | 9 (`v0.4.0`) | 5 (`v1.0.0`) |
| Comprobación pública | 0 | — | 4 (`v1.0.0`) |

Avisos que quedan y por qué se aceptan:

| Aviso | Dónde | Decisión |
|---|---|---|
| 10111 Authentication Request Identified, 10112 Session Management Response Identified | Aplicación | Informativos: ZAP reconoce el formulario de entrada y la cookie de sesión. |
| 10049 Non-Storable Content | Ambos | Es el efecto buscado de `Cache-Control: no-store` en páginas con datos. |
| 10015 Re-examine Cache-control Directives | Ambos | Sugiere revisar la caché de la portada; la portada no tiene datos de nadie. |
| 10031 User Controllable HTML Element Attribute | Aplicación, `/cuentas/login/` | Falso positivo: el formulario vuelve a mostrar el usuario escrito, escapado por Django. No hay JavaScript que lo interprete y la política de contenido bloquea cualquier script. |
| 10202 Absence of Anti-CSRF Tokens | Comprobación pública | No aplica: el servicio no tiene sesión ni cookies, y verificar un archivo o consultar un código no cambia nada. |
| 90004 Cross-Origin-Embedder-Policy | Comprobación pública | COEP protege funciones de aislamiento entre orígenes que el servicio no usa; no carga nada de terceros y su política de contenido es `default-src 'none'`. Se agrega si el servicio vuelve a publicarse. |

Antes del endurecimiento, la aplicación tenía además: sin política de contenido (10038), sin
`Permissions-Policy` (10063), `Access-Control-Allow-Origin: *` en los estilos (10098), y sin COEP ni
CORP (90004). Los cuatro quedaron corregidos en `v1.0.0`.

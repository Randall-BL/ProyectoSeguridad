# Guion de la presentación (tareas 11.1 a 11.6)

Jueves 19 de noviembre, 15 minutos, con el sistema corriendo en su URL pública (`v1.0.0`). El enunciado
pide seis cosas; el guion las sigue en ese orden. Reparto por bloques de la defensa (decisión 0.7):
Javier, arquitectura e infraestructura; Axel, motor de decisión y controles de historial; Julio,
matriz, flujos y pruebas; Randall, base, bitácora, autenticación y certificados. **Cada quien tiene que
poder explicar cualquier parte**: ver la última sección.

## La noche anterior (11.5) y el día (11.4)

- [ ] Probar desde **datos móviles**, no desde la red de la casa: abrir la aplicación, entrar con un
  personaje y comprobar un certificado.
- [ ] Cada uno tiene la semilla TOTP de sus personajes en una aplicación autenticadora del teléfono
  (anexo para el profesor, fuera del repositorio).
- [ ] Preparar la enmienda de T-25 hasta «revisada», para autorizarla en vivo:
  1. G (`ger.gabriela`) solicita una enmienda de la medición de F-001 P-1 de 2026-I, con A como
     responsable.
  2. A (`tec.ana`) corrige las toneladas, por ejemplo de 55.895 a 57.000.
  3. C (`ver.carla`) da el dictamen favorable.
- [ ] Diez minutos antes: `sh infra/demo/calentar.sh` y entrar con cada personaje en una ventana
  privada distinta. La sesión dura 30 minutos sin uso y 12 horas como máximo.
- [ ] Tener abiertos: el repositorio, la consola de Secret Manager, la terminal en la raíz del repositorio
  y `docs/demostracion/` (certificado válido y alterado).
- [ ] Plan B si internet falla: las capturas de `docs/evidencia/` y el informe.

## Minuto a minuto

| Tiempo | Quién | Punto del enunciado | Qué se muestra |
|---|---|---|---|
| 0:00–2:00 | Javier | 1. HTTPS desde internet | La URL `https://verdeazul-app-708901712393.us-east1.run.app`, el candado, `http://` que redirige a `https://` (curl de `docs/evidencia/https.txt`). La figura 1 del informe: cinco componentes, cada uno con su cuenta de servicio y su usuario de base; F1 a F5. |
| 2:00–6:30 | Julio y Axel | 2. Un usuario de cada rol | Ver «Recorrido de los roles». |
| 6:30–8:30 | Axel | 3. Lo que no le corresponde | La interfaz no muestra el botón; `infra/demo/intento-prohibido.sh` lo envía igual y el servidor responde 403 con la regla. La verificadora C intentando aprobar lo que escribió (C3, T-06). Un identificador ajeno responde 404, igual que uno que no existe. |
| 8:30–11:30 | Randall | 4. Certificados | La emisión automática al aprobar (paso 2 del recorrido). Descargar el certificado, verificarlo en el servicio público y con `python verificador/verificar.py`; la copia alterada falla. T-25 en vivo: la gerente que solicitó no puede autorizar (C8, T-24), la otra sí, y el servicio revoca y reemite. El código viejo dice «revocado» y enlaza al nuevo (T-32). |
| 11:30–12:30 | Randall | 5. Bitácora | Como GER, `/bitacora/`: las acciones de la demo, las denegaciones con su regla y «la cadena de huellas está íntegra». El testigo RFC 3161 diario. |
| 12:30–14:15 | Javier | 6. Secretos y Dependabot | Secret Manager: los siete secretos, cada uno con un solo lector (`docs/evidencia/secret-manager.txt` o la consola). `secretKeyRef` con versión fija en `infra/app.service.yaml`. `dependabot.yml`, los PR que abrió y la revisión del #3. El CI: gitleaks sobre la historia y Trivy sobre las cinco imágenes. |
| 14:15–15:00 | Julio | Cierre | 102 de 102 permisos con su prueba (`docs/cobertura.md`); los tres errores que encontraron las pruebas antes de entregar. |

## Recorrido de los roles (punto 2)

Cada personaje hace lo suyo. Las decisiones piden el código TOTP si pasaron más de 5 minutos, y fuera
de lunes a viernes de 6:00 a 19:00 también un motivo.

1. **TEC, `tec.ana`:** solo ve sus fincas (F-001, F-003, F-004). Registra una medición en F-001 P-1 del
   período 2026-II con la fecha de hoy y la envía.
2. **VER, `ver.diego`:** aprueba esa medición (T-05): pide el código. Al aprobar, la aplicación le pide
   al servicio de emisión el certificado firmado, que aparece en «Certificados».
3. **SUP, `sup.sofia`:** crea una asignación temporal de 10 días con motivo (T-28). Intenta darle a
   `tec.tomas` la asignación 21 y el servidor la rechaza (K-1, T-38).
4. **GER, `ger.gabriela`:** aprueba una finca que propuso el administrador (segunda firma, C11) o la
   propuesta de rol de una cuenta (C12).
5. **ADM, `adm.alberto`:** propone una finca o un rol; no puede aprobarse a sí mismo (T-16).
6. **AUD, `aud.elena`:** exporta un paquete (por ejemplo «Fincas»): sale con su identidad y con el sello
   de Verdeazul; `python verificador/verificar.py <paquete>.json` lo da por válido.
7. **DUE, `due.daniel`:** ve solo F-001, que es de su titular. La dirección de otra finca responde «no
   encontrado» (T-08).

## Preguntas que pueden salir, con la respuesta corta

**Arquitectura e infraestructura**
- *¿Por qué cinco servicios?* Son los componentes de la Parte 1: aplicación, motor, emisión,
  comprobación pública y trabajos. Cada uno tiene su cuenta de servicio y su usuario de base con lo
  mínimo, así una falla en uno no da los permisos de los demás.
- *¿Cómo se sabe qué versión corre?* Cada imagen tiene la etiqueta `v1.0.0` y `git-99067dc`, y la de git
  apunta al mismo commit. Para volver atrás: `sh infra/desplegar.sh app v0.4.0`.
- *¿Por qué no root?* `USER 10001` en cada Dockerfile: si alguien ejecuta código en el contenedor, no
  es administrador.

**Motor de decisión**
- *¿Dónde se decide?* En OPA, con la matriz como datos y las reglas C1–C20 y H1–H4 en Rego. La aplicación
  le pasa hechos sacados de la base, nunca de la petición (K-2). Si OPA no responde, se deniega (K-3).
- *¿Y si alguien se salta la aplicación?* La base vuelve a decidir: seguridad por fila y disparadores con
  las mismas reglas, y una prueba exige que las dos copias digan lo mismo.

**Matriz y pruebas**
- *¿Cómo saben que está completa?* `docs/cobertura.md`: los 102 permisos con su prueba y las 38 celdas
  denegadas; la genera un script desde la matriz y los resultados del CI.
- *¿Qué encontraron las pruebas?* Tres cosas:
  1. la base usaba la fecha UTC y el motor la de Costa Rica;
  2. T-33 no estaba implementado;
  3. un técnico podía saber qué identificadores existían (403 contra 404).

**Base, autenticación y certificados**
- *¿Cómo se guardan las contraseñas?* Argon2id con sal propia y 64 MiB de memoria por intento, más un
  segundo factor TOTP obligatorio.
- *¿Por qué confiar en un certificado sin entrar al sistema?* Lleva su contenido en JSON canónico, la
  firma Ed25519 y la clave pública. El verificador comprueba la firma y que la clave sea la publicada por
  Verdeazul; si se cambia una cifra, la firma deja de corresponder.
- *¿Dónde está la clave privada?* En Secret Manager. Solo la lee la cuenta del servicio de emisión, que
  no tiene acceso público.
- *¿Qué pasa si alguien con acceso a la base borra registros de la bitácora?* La cadena de huellas lo
  delata, y el sello diario de una autoridad externa prueba qué huella existía cada día.

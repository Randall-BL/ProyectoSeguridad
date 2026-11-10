# Motor de decisión (OPA)

La matriz de la Parte 1 como política. `matriz.json` es la fuente única de los permisos (102
concedidos y 38 celdas denegadas); `verdeazul/reglas.rego` tiene una regla por condición, con el
mismo identificador que en la Parte 1 (C1 a C20); `verdeazul/decision.rego` arma la respuesta:
la celda, la abstención por vínculo (C17), la reautenticación (POL-AU-06) y los controles de
historial (H1 a H3). Lo que no está escrito se deniega.

La aplicación pregunta `POST /v1/data/verdeazul/decision` con los hechos en `input` y recibe:

```json
{"resultado": "denegar", "regla": "C3", "avisar": false}
```

| `resultado` | Qué hace la aplicación |
|---|---|
| `conceder` | Ejecuta. Si `avisar`, crea una alerta de historial. |
| `pedir_segundo_factor` | Manda a reautenticarse con el código (verbos de decisión). |
| `pedir_segundo_factor_y_motivo` | Pide el código y un motivo (H1 en su segundo nivel, H2, H3). |
| `restringir` | Deniega las fincas nuevas hasta el siguiente día hábil (H1, H3). |
| `denegar` | Deniega y registra la regla en la bitácora. |

## Entrada

Los hechos los arma la aplicación **desde la base**, nunca desde la petición: el id del sujeto
sale de la sesión del servidor (K-2), y el estado y los autores del objeto, de sus filas.

```json
{
  "sujeto": {
    "id": "uuid de la cuenta",
    "rol": "rol activo de la sesión (TEC, VER, SUP, GER, ADM, AUD, DUE; SIS o PUB para los servicios)",
    "segundo_factor_reciente": true,
    "ventana_vigente": true,
    "fincas_asignadas": ["fincas con asignación vigente o enmienda en trámite (C1)"],
    "titulares_representados": ["titulares del dueño (C5)"],
    "titulares_con_vinculo": ["titulares con vínculo declarado (C17)"],
    "tecnicos_a_cargo": ["técnicos del supervisor (C15)"]
  },
  "accion": "verbo de la matriz: leer, crear, aprobar…",
  "objeto": {"tipo": "clave de matriz.objetos", "finca": "uuid", "titular": "uuid", "…": "según el tipo"},
  "cambio": {"lo que se quiere escribir y que la regla revisa: fecha_medicion, tipo, motivo, dias, accion"},
  "motivo": "texto, cuando H1, H2 o H3 lo piden",
  "historial": {"fincas_24h": 0, "finca_nueva": false, "fuera_de_jornada": false, "fincas_60min": 0, "mayoria_nuevas_90d": false},
  "parametros": {"h1_aviso": 40, "h1_verificacion": 60, "h1_restriccion": 80, "h3_fincas_hora": 10, "max_asignaciones_activas": 20},
  "hoy": "AAAA-MM-DD, en la hora de Costa Rica"
}
```

Hechos del objeto que usa cada regla:

| Regla | Campos de `objeto` |
|---|---|
| C1 | `finca`; en asignaciones, `tecnico`; en mediciones, `autores` |
| C2 | `finca`, `estado`, `periodo_estado`, `periodo_inicio`, `periodo_fin_medicion`, `asignacion_desde`, `asignacion_hasta` |
| C3 | `estado`, `autores` (ids de los autores de todas las versiones) |
| C4 | `medicion.{estado, aprobada_por, autores}`, `certificado_vigente`; al revocar, `enmienda.{estado, cambia_toneladas}` |
| C5 | `titular`; en mediciones, `estado` |
| C7 | `medicion.{estado, periodo_estado, responsable}` |
| C8 | `estado`, `dictamen_favorable`, `solicitada_por`, `revisada_por`, `medicion.autores` |
| C9 | `estado`, `responsable`, `dias_habiles_desde_solicitud` |
| C10 | `estado`, `solicitada_por`, `material`, `medicion.{autores, aprobada_por}` |
| C11, C12, C14 | `propuesta.{estado, propuesta_por o registrada_por, accion}`; en cuentas, `cuenta`; en períodos, `estado` |
| C13 | `cuenta` |
| C15 | `sujeto_alerta`, `supervisor_del_sujeto`, `escalada` |
| C16 | `obligacion_conservar` |
| C19 | `tecnico`, `tecnico_es_tec`, `activas_del_tecnico` |
| C20 | `codigo` |

Para una lista, `objeto` lleva `"coleccion": true`: el motor decide si el rol lee ese objeto, y la
base filtra las filas (seguridad por fila).

## Comprobar

```bash
docker run --rm -v "$PWD/politica:/politica" openpolicyagent/opa:1.22.3-static test --coverage /politica
```

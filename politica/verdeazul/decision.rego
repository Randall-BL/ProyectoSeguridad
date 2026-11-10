# Motor de decisión de Verdeazul (componente «Motor de decisión» de la Parte 1).
#
# La matriz (data.matriz, de politica/matriz.json) dice qué verbos tiene cada rol sobre cada objeto
# y con qué condición. Aquí está cada condición con el mismo identificador que en la Parte 1 (C1 a
# C20, H1 a H4). Niega por omisión: lo que no está en la matriz, o lo que no cumple su condición,
# se deniega, y la respuesta dice qué regla lo decidió.
#
# Los hechos llegan en input y los arma la aplicación desde la base, nunca desde la petición (tarea
# 4.6): quién es el sujeto (su id sale de la sesión del servidor, K-2), su rol activo, sus fincas
# asignadas, sus vínculos y el estado del objeto. Ver politica/LEEME.md para el formato.
package verdeazul

matriz := data.matriz

sujeto := input.sujeto

objeto := input.objeto

# --- La celda ----------------------------------------------------------------------------------

# El permiso de la matriz para este rol, objeto y verbo, si existe.
permiso := p if {
	some p in matriz.celdas[sujeto.rol][objeto.tipo]
	p.verbo == input.accion
}

condiciones := {c | some c in permiso.condiciones; c != matriz.lectura_vigilada}

vigilada if matriz.lectura_vigilada in permiso.condiciones

# Primera condición de la celda que no se cumple.
fallida := min({c | some c in condiciones; not c in cumple})

# --- Decisión ----------------------------------------------------------------------------------

default decision := {"resultado": "denegar", "regla": "matriz", "avisar": false}

decision := _respuesta("denegar", "matriz") if {
	not permiso
} else := _respuesta("denegar", "C17") if {
	abstencion
} else := _respuesta("denegar", fallida) if {
	fallida
} else := _respuesta("restringir", "H1") if {
	h1_nivel == "restriccion"
	input.historial.finca_nueva
} else := _respuesta("pedir_segundo_factor", "POL-AU-06") if {
	input.accion in matriz.reautenticacion
	not sujeto.segundo_factor_reciente
} else := _respuesta("pedir_segundo_factor_y_motivo", regla_graduada) if {
	regla_graduada
	not justificada
} else := object.union(_respuesta("conceder", regla_graduada), {"avisar": true}) if {
	regla_graduada
} else := object.union(_respuesta("conceder", "H1"), {"avisar": true}) if {
	h1_nivel == "aviso"
} else := _respuesta("conceder", regla_concedida)

_respuesta(resultado, regla) := {"resultado": resultado, "regla": regla, "avisar": false}

regla_concedida := concat(",", sort(condiciones)) if {
	count(condiciones) > 0
} else := "matriz"

# --- C17: abstención por vínculo (tarea 4.3) ---------------------------------------------------

# Quien declaró un vínculo con el titular de la finca no mide, no aprueba, no asigna, no revisa ni
# autoriza nada sobre ella. Afecta todo verbo distinto de leer de TEC, VER, SUP, GER y ADM sobre
# fincas, asignaciones, mediciones y enmiendas (leyenda de la matriz).
abstencion if {
	input.accion != "leer"
	sujeto.rol in matriz.abstencion.roles
	objeto.tipo in matriz.abstencion.objetos
	objeto.titular in sujeto.titulares_con_vinculo
}

# --- Controles de historial (H1 a H3, tarea 4.9) -----------------------------------------------

# H1 frecuencia: fincas distintas consultadas en 24 horas (las denegadas por C1 o C5 cuentan doble)
# contra los tres umbrales del rol, que aprueba GER.
h1_nivel := "restriccion" if {
	vigilada
	input.historial.fincas_24h > input.parametros.h1_restriccion
} else := "verificacion" if {
	vigilada
	input.historial.fincas_24h > input.parametros.h1_verificacion
} else := "aviso" if {
	vigilada
	input.historial.fincas_24h > input.parametros.h1_aviso
}

# Lo que pide segundo factor y motivo: H1 en su segundo nivel, H2 (una decisión fuera de la
# jornada del rol) y H3 (fuera de jornada, muchas fincas en una hora y casi todas nuevas).
regla_graduada := "H3" if {
	vigilada
	input.historial.fuera_de_jornada
	input.historial.fincas_60min > input.parametros.h3_fincas_hora
	input.historial.mayoria_nuevas_90d
} else := "H1" if {
	h1_nivel == "verificacion"
} else := "H2" if {
	input.accion in matriz.reautenticacion
	input.historial.fuera_de_jornada
}

justificada if {
	sujeto.segundo_factor_reciente
	trim_space(object.get(input, "motivo", "")) != ""
}

# --- Utilidades --------------------------------------------------------------------------------

coleccion if object.get(objeto, "coleccion", false)

es_tec if sujeto.rol == "TEC"

# Fecha que declara el técnico: dentro del período, de su asignación y no posterior a hoy (C2).
fecha_declarada_valida if not input.cambio.fecha_medicion

fecha_declarada_valida if {
	f := input.cambio.fecha_medicion
	f >= objeto.periodo_inicio
	f <= objeto.periodo_fin_medicion
	f >= objeto.asignacion_desde
	_hasta_o_sin_fin(f, object.get(objeto, "asignacion_hasta", null))
	f <= input.hoy
}

_hasta_o_sin_fin(_, null)

_hasta_o_sin_fin(f, hasta) if {
	hasta != null
	f <= hasta
}

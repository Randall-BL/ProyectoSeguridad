# Las reglas de las celdas condicionadas (Parte 1, Entregable 3, sección «Reglas»). Cada regla
# agrega su identificador a «cumple» cuando se cumple; la decisión deniega con la primera condición
# de la celda que no esté. s es el sujeto, o el objeto y m la medición de la que se habla.
package verdeazul

# Para listar (objeto.coleccion), las reglas de alcance no se evalúan aquí: la lista ya sale
# filtrada por la seguridad por fila de la base (C1, C5) o por el supervisor (C15).
cumple contains c if {
	coleccion
	input.accion == "leer"
	some c in {"C1", "C5", "C15"}
}

# C1 Asignación vigente: la finca del objeto está entre las asignadas al técnico (ordinaria con el
# período abierto, temporal hasta su fin, o responsable de una enmienda en trámite). Las
# asignaciones, solo las propias; y siempre puede leer las mediciones que registró.
cumple contains "C1" if {
	objeto.tipo != "asignaciones"
	objeto.finca in sujeto.fincas_asignadas
}

cumple contains "C1" if {
	objeto.tipo == "asignaciones"
	objeto.tecnico == sujeto.id
}

cumple contains "C1" if {
	objeto.tipo == "mediciones"
	sujeto.id in objeto.autores
}

# C2 Edición solo en borrador: C1, período abierto, y la medición en borrador o devuelta. La fecha
# de medición que declara cae dentro del período y de la asignación, y no después de hoy.
cumple contains "C2" if {
	input.accion == "crear"
	objeto.finca in sujeto.fincas_asignadas
	objeto.periodo_estado == "abierto"
	fecha_declarada_valida
}

cumple contains "C2" if {
	input.accion in {"modificar", "enviar"}
	objeto.finca in sujeto.fincas_asignadas
	objeto.periodo_estado == "abierto"
	objeto.estado in {"borrador", "devuelta"}
	fecha_declarada_valida
}

# C3 Quien registró no aprueba (K-2): la medición está enviada y el id de quien decide no está
# entre los autores de ninguna de sus versiones. Vale con el período abierto o cerrado.
cumple contains "C3" if {
	objeto.estado == "enviada"
	not sujeto.id in objeto.autores
}

# C4 Emisión única: aprobada, quien aprobó no es autor y no hay otro certificado vigente para la
# misma parcela y período. Revocar solo por una enmienda autorizada que cambia las toneladas.
cumple contains "C4" if {
	input.accion == "emitir"
	objeto.medicion.estado == "aprobada"
	not objeto.medicion.aprobada_por in objeto.medicion.autores
	not objeto.certificado_vigente
}

cumple contains "C4" if {
	input.accion == "revocar"
	objeto.enmienda.estado == "autorizada"
	objeto.enmienda.cambia_toneladas
}

# C5 Solo lo suyo: relación vigente con el titular; de las mediciones, solo las aprobadas.
cumple contains "C5" if {
	objeto.titular in sujeto.titulares_representados
	objeto.tipo != "mediciones"
}

cumple contains "C5" if {
	objeto.titular in sujeto.titulares_representados
	objeto.tipo == "mediciones"
	objeto.estado == "aprobada"
}

# C6 Ventana de auditoría: la fecha actual está dentro de la ventana de la cuenta.
cumple contains "C6" if sujeto.ventana_vigente

# C7 Solicitar enmienda: la medición está aprobada, o su período cerró y quedó devuelta o
# excluida. Si la pide un técnico, tiene que ser el responsable de la medición.
cumple contains "C7" if {
	_solicitable(objeto.medicion)
	_responsable_si_es_tecnico(objeto.medicion)
}

# C8 Autorización final: dictamen técnico favorable, y quien autoriza no la solicitó, no la revisó
# ni escribió una versión de la medición.
cumple contains "C8" if {
	objeto.estado == "revisada"
	objeto.dictamen_favorable == true
	objeto.solicitada_por != sujeto.id
	objeto.revisada_por != sujeto.id
	not sujeto.id in objeto.medicion.autores
}

# C9 Corregir dentro del plazo: solicitada, quien corrige es el responsable designado y no han
# pasado 10 días hábiles.
cumple contains "C9" if {
	objeto.estado == "solicitada"
	objeto.responsable == sujeto.id
	objeto.dias_habiles_desde_solicitud <= 10
}

# C10 Revisión técnica independiente: corregida, quien revisa no es autor ni la solicitó; si es
# material, tampoco aprobó la versión que se corrige.
cumple contains "C10" if {
	objeto.estado == "corregida"
	not sujeto.id in objeto.medicion.autores
	objeto.solicitada_por != sujeto.id
	_no_aprobo_si_es_material
}

# C11 Catálogo con segunda firma: ADM propone (queda en estado propuesto) y GER aprueba lo que
# propuso otra persona.
cumple contains "C11" if input.accion == "proponer"

cumple contains "C11" if {
	input.accion == "aprobar"
	objeto.propuesta.estado == "propuesto"
	objeto.propuesta.propuesta_por != sujeto.id
}

# C12 Nadie se administra a sí mismo: la cuenta afectada no es la propia; quien aprueba no es
# quien propuso.
cumple contains "C12" if {
	input.accion in {"crear", "desactivar", "proponer"}
	objeto.cuenta != sujeto.id
}

cumple contains "C12" if {
	input.accion == "aprobar"
	objeto.cuenta != sujeto.id
	objeto.propuesta.estado == "propuesta"
	objeto.propuesta.propuesta_por != sujeto.id
}

# C13 Credenciales y declaración propias: la cuenta es la de quien pide.
cumple contains "C13" if objeto.cuenta == sujeto.id

# C14 Apertura y cierre entre dos: ADM registra con las fechas de la coordinación y GER aprueba lo
# que registró otra persona. No existe reabrir.
cumple contains "C14" if {
	input.accion == "proponer"
	_transicion_valida(objeto.estado, input.cambio.accion)
}

cumple contains "C14" if {
	input.accion in {"abrir", "cerrar"}
	_transicion_valida(objeto.estado, input.accion)
	objeto.propuesta.accion == input.accion
	objeto.propuesta.estado == "propuesto"
	objeto.propuesta.registrada_por != sujeto.id
}

# C15 Alertas ajenas: nadie atiende una alerta sobre sí mismo. SUP, las de sus técnicos; GER, las
# de los demás y las que SUP no resolvió en dos días hábiles.
cumple contains "C15" if {
	sujeto.rol == "SUP"
	objeto.sujeto_alerta != sujeto.id
	objeto.sujeto_alerta in sujeto.tecnicos_a_cargo
}

cumple contains "C15" if {
	sujeto.rol == "GER"
	objeto.sujeto_alerta != sujeto.id
	_le_toca_a_gerencia
}

# C16 Supresión condicionada: no hay obligación vigente de conservar el dato.
cumple contains "C16" if objeto.obligacion_conservar == false

# C18 Exportar evidencia: dentro de la ventana (C6). El paquete lo genera y lo sella el sistema.
cumple contains "C18" if sujeto.ventana_vigente

# C19 Asignar con vigencia: el asignado tiene el rol TEC vigente (propio o por habilitación) y no
# es quien asigna; la temporal lleva motivo y dura 15 días como máximo; y el técnico no pasa del
# máximo de asignaciones activas (K-1).
cumple contains "C19" if {
	objeto.tecnico_es_tec
	objeto.tecnico != sujeto.id
	_temporal_bien_formada
	_dentro_del_maximo
}

# C20 Comprobación pública: quien consulta presenta el código impreso en el certificado.
cumple contains "C20" if trim_space(object.get(objeto, "codigo", "")) != ""

# --- Funciones auxiliares de las reglas ------------------------------------------------------

_solicitable(m) if m.estado == "aprobada"

_solicitable(m) if {
	m.periodo_estado == "cerrado"
	m.estado in {"devuelta", "excluida"}
}

_responsable_si_es_tecnico(_) if not es_tec

_responsable_si_es_tecnico(m) if {
	es_tec
	m.responsable == sujeto.id
}

_no_aprobo_si_es_material if not objeto.material

_no_aprobo_si_es_material if {
	objeto.material
	objeto.medicion.aprobada_por != sujeto.id
}

_transicion_valida("planificado", "abrir")

_transicion_valida("abierto", "cerrar")

_le_toca_a_gerencia if objeto.supervisor_del_sujeto == null

_le_toca_a_gerencia if objeto.escalada

_temporal_bien_formada if input.cambio.tipo == "ordinaria"

_temporal_bien_formada if {
	input.cambio.tipo == "temporal"
	trim_space(input.cambio.motivo) != ""
	input.cambio.dias >= 0
	input.cambio.dias <= 15
}

_dentro_del_maximo if input.accion != "crear"

_dentro_del_maximo if {
	input.accion == "crear"
	objeto.activas_del_tecnico < input.parametros.max_asignaciones_activas
}

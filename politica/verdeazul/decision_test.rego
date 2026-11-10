# Pruebas de la política: la matriz completa y los casos T-01 a T-40 de la Parte 1 que se deciden
# en el motor. Los que decide la base (T-15, traslape de geometría) o la sesión (T-09, T-20, T-40)
# se prueban en la aplicación.
package verdeazul_test

import data.verdeazul

# --- Personas y objetos de los casos -----------------------------------------------------------

ana := "u-ana" # técnico A

bruno := "u-bruno" # verificador B

carla := "u-carla" # verificadora C, antes técnica

sofia := "u-sofia" # supervisora S

gabriela := "u-gabriela" # gerente G

alberto := "u-alberto" # administrador

elena := "u-elena" # auditora E

daniel := "u-daniel" # dueño D

f1 := "finca-1"

f2 := "finca-2"

f5 := "finca-5"

t1 := "titular-1"

t5 := "titular-5"

parametros := {
	"h1_aviso": 40,
	"h1_verificacion": 60,
	"h1_restriccion": 80,
	"h3_fincas_hora": 10,
	"max_asignaciones_activas": 20,
}

tranquilo := {
	"fincas_24h": 1,
	"finca_nueva": false,
	"fuera_de_jornada": false,
	"fincas_60min": 1,
	"mayoria_nuevas_90d": false,
}

sujeto_base := {
	"segundo_factor_reciente": true,
	"ventana_vigente": true,
	"titulares_con_vinculo": [],
	"titulares_representados": [],
	"fincas_asignadas": [],
	"tecnicos_a_cargo": [],
}

persona(id, rol, extra) := object.union(object.union(sujeto_base, {"id": id, "rol": rol}), extra)

pedido(s, accion, o) := {
	"sujeto": s,
	"accion": accion,
	"objeto": o,
	"historial": tranquilo,
	"parametros": parametros,
	"hoy": "2026-11-10",
}

decide(entrada) := d if {
	d := verdeazul.decision with input as entrada
}

resultado(entrada) := [d.resultado, d.regla] if d := decide(entrada)

tec_ana := persona(ana, "TEC", {"fincas_asignadas": [f1]})

ver_bruno := persona(bruno, "VER", {})

medicion(estado, autores, extra) := object.union(
	{"tipo": "mediciones", "finca": f1, "titular": t1, "estado": estado, "autores": autores, "periodo_estado": "abierto"},
	extra,
)

nueva_en_f1 := {
	"tipo": "mediciones",
	"finca": f1,
	"titular": t1,
	"periodo_estado": "abierto",
	"periodo_inicio": "2026-07-01",
	"periodo_fin_medicion": "2026-11-30",
	"asignacion_desde": "2026-07-01",
	"asignacion_hasta": null,
}

# --- La matriz como dato -----------------------------------------------------------------------

test_la_matriz_tiene_102_permisos_y_38_celdas_denegadas if {
	celdas := data.matriz.celdas
	count([p | some rol, obj; some p in celdas[rol][obj]]) == 102
	count([1 | some rol, obj; count(celdas[rol][obj]) == 0]) == 38
}

verbos := {
	"leer", "crear", "modificar", "eliminar", "aprobar", "enviar", "devolver", "solicitar",
	"corregir", "revisar", "autorizar", "emitir", "revocar", "abrir", "cerrar", "proponer",
	"desactivar", "resolver", "exportar", "comprobar", "anexar",
}

# Toda combinación de rol, objeto y verbo que la matriz no escribe se deniega por la matriz,
# aunque los hechos digan que todo lo demás se cumple.
test_lo_que_no_esta_en_la_matriz_se_deniega if {
	todo_a_favor := persona("u-x", "TEC", {"fincas_asignadas": [f1], "titulares_representados": [t1]})
	fallas := [[rol, obj, verbo] |
		some rol, obj
		data.matriz.celdas[rol][obj]
		some verbo in verbos
		not _en_la_celda(rol, obj, verbo)
		r := resultado(pedido(object.union(todo_a_favor, {"rol": rol}), verbo, {"tipo": obj, "finca": f1, "titular": t1}))
		r != ["denegar", "matriz"]
	]
	count(fallas) == 0
}

_en_la_celda(rol, obj, verbo) if {
	some p in data.matriz.celdas[rol][obj]
	p.verbo == verbo
}

test_ope_no_tiene_ningun_permiso if {
	every obj, _ in data.matriz.objetos {
		count(data.matriz.celdas.OPE[obj]) == 0
	}
}

# --- C1 y C2: técnico ---------------------------------------------------------------------------

test_t01_crea_una_medicion_en_su_finca if {
	entrada := object.union(pedido(tec_ana, "crear", nueva_en_f1), {"cambio": {"fecha_medicion": "2026-11-09"}})
	resultado(entrada) == ["conceder", "C2"]
}

test_t02_detalle_de_una_finca_sin_asignar if {
	resultado(pedido(tec_ana, "leer", {"tipo": "fincas", "finca": f2, "titular": t1})) == ["denegar", "C1"]
}

test_t03_modificar_una_medicion_ya_enviada if {
	resultado(pedido(tec_ana, "modificar", medicion("enviada", [ana], {}))) == ["denegar", "C2"]
}

test_t04_modificar_un_borrador_despues_del_cierre if {
	o := medicion("borrador", [ana], {"periodo_estado": "cerrado"})
	resultado(pedido(tec_ana, "modificar", o)) == ["denegar", "C2"]
}

test_t21_modificar_lo_devuelto_despues_del_cierre if {
	o := medicion("devuelta", [ana], {"periodo_estado": "cerrado"})
	resultado(pedido(tec_ana, "modificar", o)) == ["denegar", "C2"]
}

test_t22_cierre_registrado_pero_no_aprobado if {
	entrada := object.union(pedido(tec_ana, "crear", nueva_en_f1), {"cambio": {"fecha_medicion": "2026-11-09"}})
	resultado(entrada) == ["conceder", "C2"]
}

test_t27_asignacion_temporal_vencida if {
	# La temporal venció: la finca ya no está entre las asignadas.
	resultado(pedido(tec_ana, "leer", {"tipo": "fincas", "finca": f2, "titular": t1})) == ["denegar", "C1"]
}

test_t30_fecha_de_medicion_futura if {
	entrada := object.union(pedido(tec_ana, "crear", nueva_en_f1), {"cambio": {"fecha_medicion": "2026-11-11"}})
	resultado(entrada) == ["denegar", "C2"]
}

test_t30_fecha_de_medicion_fuera_del_periodo if {
	entrada := object.union(pedido(tec_ana, "crear", nueva_en_f1), {"cambio": {"fecha_medicion": "2026-06-30"}})
	resultado(entrada) == ["denegar", "C2"]
}

test_el_tecnico_lee_lo_que_registro_aunque_ya_no_tenga_la_finca if {
	sin_fincas := persona(ana, "TEC", {})
	resultado(pedido(sin_fincas, "leer", medicion("aprobada", [ana], {}))) == ["conceder", "C1"]
}

test_solo_lee_sus_propias_asignaciones if {
	resultado(pedido(tec_ana, "leer", {"tipo": "asignaciones", "tecnico": ana, "finca": f1})) == ["conceder", "C1"]
	resultado(pedido(tec_ana, "leer", {"tipo": "asignaciones", "tecnico": "u-tomas", "finca": f1})) == ["denegar", "C1"]
}

# --- C3 y K-2: quien registró no aprueba -------------------------------------------------------

test_t05_b_aprueba_lo_que_registro_a if {
	resultado(pedido(ver_bruno, "aprobar", medicion("enviada", [ana], {}))) == ["conceder", "C3"]
}

test_t06_c_escribio_la_version_1 if {
	ver_carla := persona(carla, "VER", {})
	resultado(pedido(ver_carla, "aprobar", medicion("enviada", [carla, ana], {}))) == ["denegar", "C3"]
}

test_t17_aprobar_despues_del_cierre_lo_enviado_antes if {
	o := medicion("enviada", [ana], {"periodo_estado": "cerrado"})
	resultado(pedido(ver_bruno, "aprobar", o)) == ["conceder", "C3"]
}

test_t26_con_habilitacion_registro_y_despues_aprueba if {
	# Misma persona, otro rol activo: C3 compara el id, no el rol.
	ver_carla := persona(carla, "VER", {})
	resultado(pedido(ver_carla, "aprobar", medicion("enviada", [carla], {}))) == ["denegar", "C3"]
}

test_devolver_tambien_exige_c3 if {
	resultado(pedido(ver_bruno, "devolver", medicion("enviada", [bruno], {}))) == ["denegar", "C3"]
}

# --- C4: emisión única -------------------------------------------------------------------------

test_t07_no_emite_si_ya_hay_uno_vigente if {
	sis := persona("sis", "SIS", {})
	o := {"tipo": "certificados", "medicion": {"estado": "aprobada", "aprobada_por": bruno, "autores": [ana]}, "certificado_vigente": true}
	resultado(pedido(sis, "emitir", o)) == ["denegar", "C4"]
}

test_emite_el_primero if {
	sis := persona("sis", "SIS", {})
	o := {"tipo": "certificados", "medicion": {"estado": "aprobada", "aprobada_por": bruno, "autores": [ana]}, "certificado_vigente": false}
	resultado(pedido(sis, "emitir", o)) == ["conceder", "C4"]
}

test_t25_revoca_por_enmienda_que_cambia_toneladas if {
	sis := persona("sis", "SIS", {})
	o := {"tipo": "certificados", "enmienda": {"estado": "autorizada", "cambia_toneladas": true}}
	resultado(pedido(sis, "revocar", o)) == ["conceder", "C4"]
}

# --- C5, C6, C18: dueño y auditora -------------------------------------------------------------

test_t08_el_dueno_pide_el_certificado_de_otro if {
	due := persona(daniel, "DUE", {"titulares_representados": [t1]})
	resultado(pedido(due, "leer", {"tipo": "certificados", "finca": f5, "titular": t5})) == ["denegar", "C5"]
	resultado(pedido(due, "leer", {"tipo": "certificados", "finca": f1, "titular": t1})) == ["conceder", "C5"]
}

test_el_dueno_solo_ve_mediciones_aprobadas if {
	due := persona(daniel, "DUE", {"titulares_representados": [t1]})
	resultado(pedido(due, "leer", medicion("enviada", [ana], {}))) == ["denegar", "C5"]
	resultado(pedido(due, "leer", medicion("aprobada", [ana], {}))) == ["conceder", "C5"]
}

test_t09_auditora_fuera_de_su_ventana if {
	aud := persona(elena, "AUD", {"ventana_vigente": false})
	resultado(pedido(aud, "leer", medicion("aprobada", [ana], {}))) == ["denegar", "C6"]
}

# Sobre el negocio: su propia cuenta sí la modifica (contraseña y factores, C13).
test_t10_la_auditora_no_modifica_nada if {
	aud := persona(elena, "AUD", {})
	every obj, _ in object.remove(data.matriz.objetos, {"cuentas"}) {
		every verbo in {"crear", "modificar", "eliminar", "aprobar", "enviar", "devolver", "autorizar", "abrir", "cerrar", "resolver"} {
			resultado(pedido(aud, verbo, {"tipo": obj, "finca": f1, "titular": t1})) == ["denegar", "matriz"]
		}
	}
}

test_t31_exporta_dentro_de_su_ventana if {
	aud := persona(elena, "AUD", {})
	resultado(pedido(aud, "exportar", {"tipo": "certificados", "finca": f1, "titular": t1})) == ["conceder", "C18"]
}

test_la_auditora_no_exporta_datos_personales_ni_cuentas if {
	aud := persona(elena, "AUD", {})
	resultado(pedido(aud, "exportar", {"tipo": "datos_personales", "titular": t1})) == ["denegar", "matriz"]
	resultado(pedido(aud, "exportar", {"tipo": "cuentas", "cuenta": ana})) == ["denegar", "matriz"]
}

# --- C7 a C10: enmiendas -----------------------------------------------------------------------

enmienda(estado, extra) := object.union(
	{
		"tipo": "enmiendas", "finca": f1, "titular": t1, "estado": estado,
		"medicion": {"estado": "aprobada", "autores": [ana], "responsable": ana, "aprobada_por": bruno, "periodo_estado": "abierto"},
	},
	extra,
)

test_t11_el_tecnico_pide_enmienda_de_lo_que_midio_otro if {
	o := enmienda("", {"medicion": {"estado": "aprobada", "autores": ["u-tomas"], "responsable": "u-tomas", "periodo_estado": "abierto"}})
	resultado(pedido(tec_ana, "solicitar", o)) == ["denegar", "C7"]
}

test_el_responsable_pide_la_enmienda if {
	resultado(pedido(tec_ana, "solicitar", enmienda("", {}))) == ["conceder", "C7"]
}

test_t12_la_gerente_autoriza if {
	ger := persona(gabriela, "GER", {})
	o := enmienda("revisada", {"dictamen_favorable": true, "solicitada_por": ana, "revisada_por": carla})
	resultado(pedido(ger, "autorizar", o)) == ["conceder", "C8"]
}

test_t24_la_gerente_que_la_solicito_no_la_autoriza if {
	ger := persona(gabriela, "GER", {})
	o := enmienda("revisada", {"dictamen_favorable": true, "solicitada_por": gabriela, "revisada_por": carla})
	resultado(pedido(ger, "autorizar", o)) == ["denegar", "C8"]
}

test_t13_corregir_once_dias_habiles_despues if {
	o := enmienda("solicitada", {"responsable": ana, "dias_habiles_desde_solicitud": 11})
	resultado(pedido(tec_ana, "corregir", o)) == ["denegar", "C9"]
}

test_corregir_dentro_del_plazo if {
	o := enmienda("solicitada", {"responsable": ana, "dias_habiles_desde_solicitud": 10})
	resultado(pedido(tec_ana, "corregir", o)) == ["conceder", "C9"]
}

test_t14_quien_solicito_no_dictamina if {
	o := enmienda("corregida", {"solicitada_por": bruno, "material": false})
	resultado(pedido(ver_bruno, "revisar", o)) == ["denegar", "C10"]
}

test_t23_enmienda_material_quien_aprobo_no_dictamina if {
	o := enmienda("corregida", {"solicitada_por": ana, "material": true})
	resultado(pedido(ver_bruno, "revisar", o)) == ["denegar", "C10"]
}

test_enmienda_no_material_quien_aprobo_si_dictamina if {
	o := enmienda("corregida", {"solicitada_por": ana, "material": false})
	resultado(pedido(ver_bruno, "revisar", o)) == ["conceder", "C10"]
}

# --- C11 a C16: catálogo, cuentas, períodos, alertas y datos -----------------------------------

test_la_gerente_aprueba_lo_que_propuso_el_administrador if {
	ger := persona(gabriela, "GER", {})
	o := {"tipo": "fincas", "finca": f1, "titular": t1, "propuesta": {"estado": "propuesto", "propuesta_por": alberto}}
	resultado(pedido(ger, "aprobar", o)) == ["conceder", "C11"]
}

test_t16_el_administrador_no_se_propone_a_si_mismo if {
	adm := persona(alberto, "ADM", {})
	resultado(pedido(adm, "proponer", {"tipo": "cuentas", "cuenta": alberto})) == ["denegar", "C12"]
}

test_la_gerente_no_aprueba_su_propia_cuenta if {
	ger := persona(gabriela, "GER", {})
	o := {"tipo": "cuentas", "cuenta": gabriela, "propuesta": {"estado": "propuesta", "propuesta_por": alberto}}
	resultado(pedido(ger, "aprobar", o)) == ["denegar", "C12"]
}

test_t35_cambiar_la_contrasena_de_otra_cuenta if {
	resultado(pedido(tec_ana, "modificar", {"tipo": "cuentas", "cuenta": bruno})) == ["denegar", "C13"]
	resultado(pedido(tec_ana, "modificar", {"tipo": "cuentas", "cuenta": ana})) == ["conceder", "C13"]
}

test_cierre_entre_dos if {
	ger := persona(gabriela, "GER", {})
	propuesto := {"tipo": "periodos", "estado": "abierto", "propuesta": {"accion": "cerrar", "estado": "propuesto", "registrada_por": alberto}}
	resultado(pedido(ger, "cerrar", propuesto)) == ["conceder", "C14"]
	sin_registro := {"tipo": "periodos", "estado": "abierto"}
	resultado(pedido(ger, "cerrar", sin_registro)) == ["denegar", "C14"]
}

test_no_existe_reabrir if {
	ger := persona(gabriela, "GER", {})
	o := {"tipo": "periodos", "estado": "cerrado", "propuesta": {"accion": "abrir", "estado": "propuesto", "registrada_por": alberto}}
	resultado(pedido(ger, "abrir", o)) == ["denegar", "C14"]
}

test_t36_la_supervisora_no_resuelve_una_alerta_sobre_si_misma if {
	sup := persona(sofia, "SUP", {"tecnicos_a_cargo": [ana]})
	resultado(pedido(sup, "resolver", {"tipo": "alertas", "sujeto_alerta": sofia})) == ["denegar", "C15"]
	resultado(pedido(sup, "resolver", {"tipo": "alertas", "sujeto_alerta": ana})) == ["conceder", "C15"]
}

test_t37_no_suprime_datos_que_hay_que_conservar if {
	adm := persona(alberto, "ADM", {})
	resultado(pedido(adm, "eliminar", {"tipo": "datos_personales", "titular": t1, "obligacion_conservar": true})) == ["denegar", "C16"]
}

# --- C17: abstención por vínculo ---------------------------------------------------------------

test_t29_vinculo_con_el_titular if {
	con_vinculo := persona(bruno, "VER", {"titulares_con_vinculo": [t5]})
	o := medicion("enviada", [ana], {"finca": f5, "titular": t5})
	resultado(pedido(con_vinculo, "aprobar", o)) == ["denegar", "C17"]
}

test_el_vinculo_no_impide_leer if {
	con_vinculo := persona(bruno, "VER", {"titulares_con_vinculo": [t5]})
	o := medicion("enviada", [ana], {"finca": f5, "titular": t5})
	resultado(pedido(con_vinculo, "leer", o)) == ["conceder", "matriz"]
}

# --- C19 y K-1: asignaciones -------------------------------------------------------------------

asignar(activas, tecnico, cambio) := object.union(
	pedido(persona(sofia, "SUP", {}), "crear", {"tipo": "asignaciones", "finca": f1, "titular": t1, "tecnico": tecnico, "tecnico_es_tec": true, "activas_del_tecnico": activas}),
	{"cambio": cambio},
)

test_t28_la_supervisora_no_se_asigna_a_si_misma if {
	resultado(asignar(0, sofia, {"tipo": "ordinaria"})) == ["denegar", "C19"]
}

test_temporal_de_mas_de_15_dias if {
	resultado(asignar(0, ana, {"tipo": "temporal", "motivo": "apoyo", "dias": 16})) == ["denegar", "C19"]
	resultado(asignar(0, ana, {"tipo": "temporal", "motivo": "apoyo", "dias": 15})) == ["conceder", "C19"]
}

test_temporal_sin_motivo if {
	resultado(asignar(0, ana, {"tipo": "temporal", "motivo": "  ", "dias": 3})) == ["denegar", "C19"]
}

test_t38_la_asignacion_21 if {
	resultado(asignar(20, "u-tomas", {"tipo": "ordinaria"})) == ["denegar", "C19"]
}

test_t39_con_19_activas_si_se_asigna if {
	resultado(asignar(19, "u-tomas", {"tipo": "ordinaria"})) == ["conceder", "C19"]
}

# --- C20: comprobación pública -----------------------------------------------------------------

test_t32_comprobar_con_el_codigo if {
	pub := persona("", "PUB", {})
	resultado(pedido(pub, "comprobar", {"tipo": "certificados", "codigo": "VA-2026-000123"})) == ["conceder", "C20"]
	resultado(pedido(pub, "comprobar", {"tipo": "certificados", "codigo": ""})) == ["denegar", "C20"]
}

test_el_publico_no_lista_certificados if {
	pub := persona("", "PUB", {})
	resultado(pedido(pub, "leer", {"tipo": "certificados", "coleccion": true})) == ["denegar", "matriz"]
}

# --- Reautenticación y controles de historial --------------------------------------------------

test_aprobar_pide_segundo_factor_reciente if {
	sin_reciente := persona(bruno, "VER", {"segundo_factor_reciente": false})
	resultado(pedido(sin_reciente, "aprobar", medicion("enviada", [ana], {}))) == ["pedir_segundo_factor", "POL-AU-06"]
}

con_historial(entrada, h) := object.union(entrada, {"historial": object.union(tranquilo, h)})

test_h1_aviso if {
	d := decide(con_historial(pedido(ver_bruno, "leer", {"tipo": "fincas", "finca": f1, "titular": t1}), {"fincas_24h": 41}))
	[d.resultado, d.regla, d.avisar] == ["conceder", "H1", true]
}

test_t18_h1_pide_segundo_factor_y_motivo if {
	entrada := con_historial(pedido(ver_bruno, "leer", {"tipo": "fincas", "finca": f1, "titular": t1}), {"fincas_24h": 61})
	resultado(object.union(entrada, {"sujeto": object.union(ver_bruno, {"segundo_factor_reciente": false})})) == ["pedir_segundo_factor_y_motivo", "H1"]
	d := decide(object.union(entrada, {"motivo": "Revisión del lote de la semana"}))
	[d.resultado, d.regla, d.avisar] == ["conceder", "H1", true]
}

test_h1_restringe_las_fincas_nuevas if {
	entrada := pedido(ver_bruno, "leer", {"tipo": "fincas", "finca": f1, "titular": t1})
	resultado(con_historial(entrada, {"fincas_24h": 81, "finca_nueva": true})) == ["restringir", "H1"]
}

test_t19_h3_fuera_de_jornada_muchas_fincas_nuevas if {
	entrada := con_historial(
		pedido(persona(bruno, "VER", {"segundo_factor_reciente": false}), "leer", {"tipo": "fincas", "finca": f1, "titular": t1}),
		{"fuera_de_jornada": true, "fincas_60min": 11, "mayoria_nuevas_90d": true},
	)
	resultado(entrada) == ["pedir_segundo_factor_y_motivo", "H3"]
}

test_t34_h2_aprobar_un_domingo if {
	entrada := con_historial(pedido(ver_bruno, "aprobar", medicion("enviada", [ana], {})), {"fuera_de_jornada": true})
	resultado(entrada) == ["pedir_segundo_factor_y_motivo", "H2"]
}

# --- Lo que falta para cubrir cada regla -------------------------------------------------------

test_el_administrador_crea_y_desactiva_cuentas_ajenas if {
	adm := persona(alberto, "ADM", {})
	resultado(pedido(adm, "crear", {"tipo": "cuentas", "cuenta": null})) == ["conceder", "C12"]
	resultado(pedido(adm, "desactivar", {"tipo": "cuentas", "cuenta": ana})) == ["conceder", "C12"]
	resultado(pedido(adm, "desactivar", {"tipo": "cuentas", "cuenta": alberto})) == ["denegar", "C12"]
}

test_la_gerente_aprueba_la_cuenta_que_propuso_el_administrador if {
	ger := persona(gabriela, "GER", {})
	o := {"tipo": "cuentas", "cuenta": ana, "propuesta": {"estado": "propuesta", "propuesta_por": alberto}}
	resultado(pedido(ger, "aprobar", o)) == ["conceder", "C12"]
}

test_el_administrador_registra_el_cierre_pero_no_un_reabrir if {
	adm := persona(alberto, "ADM", {})
	cerrar := object.union(pedido(adm, "proponer", {"tipo": "periodos", "estado": "abierto"}), {"cambio": {"accion": "cerrar"}})
	resultado(cerrar) == ["conceder", "C14"]
	reabrir := object.union(pedido(adm, "proponer", {"tipo": "periodos", "estado": "cerrado"}), {"cambio": {"accion": "abrir"}})
	resultado(reabrir) == ["denegar", "C14"]
}

test_la_gerente_que_registro_el_cierre_no_lo_aprueba if {
	ger := persona(gabriela, "GER", {})
	o := {"tipo": "periodos", "estado": "abierto", "propuesta": {"accion": "cerrar", "estado": "propuesto", "registrada_por": gabriela}}
	resultado(pedido(ger, "cerrar", o)) == ["denegar", "C14"]
}

test_la_gerente_resuelve_las_alertas_escaladas_o_sin_supervisor if {
	ger := persona(gabriela, "GER", {})
	resultado(pedido(ger, "resolver", {"tipo": "alertas", "sujeto_alerta": bruno, "supervisor_del_sujeto": null})) == ["conceder", "C15"]
	resultado(pedido(ger, "resolver", {"tipo": "alertas", "sujeto_alerta": ana, "supervisor_del_sujeto": sofia, "escalada": true})) == ["conceder", "C15"]
	resultado(pedido(ger, "resolver", {"tipo": "alertas", "sujeto_alerta": ana, "supervisor_del_sujeto": sofia, "escalada": false})) == ["denegar", "C15"]
	resultado(pedido(ger, "resolver", {"tipo": "alertas", "sujeto_alerta": gabriela, "supervisor_del_sujeto": null})) == ["denegar", "C15"]
}

test_la_supervisora_no_atiende_alertas_de_tecnicos_ajenos if {
	sup := persona(sofia, "SUP", {"tecnicos_a_cargo": [ana]})
	resultado(pedido(sup, "leer", {"tipo": "alertas", "sujeto_alerta": "u-otro"})) == ["denegar", "C15"]
}

test_suprime_datos_sin_obligacion_de_conservar if {
	adm := persona(alberto, "ADM", {})
	resultado(pedido(adm, "eliminar", {"tipo": "datos_personales", "titular": t1, "obligacion_conservar": false})) == ["conceder", "C16"]
}

test_listar_no_evalua_el_alcance_de_cada_fila if {
	# La lista la filtra la base (seguridad por fila); el motor solo decide si el rol lee ese objeto.
	resultado(pedido(tec_ana, "leer", {"tipo": "fincas", "coleccion": true})) == ["conceder", "C1"]
	due := persona(daniel, "DUE", {})
	resultado(pedido(due, "leer", {"tipo": "mediciones", "coleccion": true})) == ["conceder", "C5"]
}

test_modificar_y_enviar_un_borrador_propio if {
	resultado(pedido(tec_ana, "enviar", medicion("borrador", [ana], {}))) == ["conceder", "C2"]
	o := medicion("devuelta", [ana], {"periodo_inicio": "2026-07-01", "periodo_fin_medicion": "2026-11-30", "asignacion_desde": "2026-07-01", "asignacion_hasta": "2026-11-20"})
	entrada := object.union(pedido(tec_ana, "modificar", o), {"cambio": {"fecha_medicion": "2026-11-05"}})
	resultado(entrada) == ["conceder", "C2"]
}

test_solicitar_enmienda_de_lo_devuelto_tras_el_cierre if {
	ver := persona(bruno, "VER", {})
	o := enmienda("", {"medicion": {"estado": "devuelta", "autores": [ana], "responsable": ana, "periodo_estado": "cerrado"}})
	resultado(pedido(ver, "solicitar", o)) == ["conceder", "C7"]
}

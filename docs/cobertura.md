# Cobertura de la matriz

Generado por `infra/cobertura.py` a partir de `politica/matriz.json`, del código y de los registros de
las pruebas. No se edita a mano: se vuelve a generar.

- Permisos concedidos: **102** (91 de los siete roles de la aplicación, 11 de SIS y PUB). Con su prueba en verde: **102**.
- Celdas denegadas: **38**.
- Pruebas encontradas en el repositorio: 302; con resultado en esta corrida: 302.

## Reglas y casos de la Parte 1

| Regla | Nombre | Motor (Rego) | Base | Casos T | Pruebas | Casos sin prueba | Resultado |
|---|---|---|---|---|---|---|---|
| C1 | Asignación vigente | politica/verdeazul/reglas.rego:17 | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0005_tec_inserta_medicion.sql:4; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | T-01, T-02, T-27 | 6 | ninguno | pasó |
| C2 | Edición solo en borrador | politica/verdeazul/reglas.rego:34 | app/negocio/sql/0004_reglas_en_la_base.sql:6 | T-01, T-03, T-04, T-21, T-30 | 11 | ninguno | pasó |
| C3 | Quien registró no aprueba (K-2) | politica/verdeazul/reglas.rego:51 | app/negocio/sql/0004_reglas_en_la_base.sql:38 | T-05, T-06, T-17, T-26, T-40 | 10 | ninguno | pasó |
| C4 | Emisión única | politica/verdeazul/reglas.rego:58 | app/negocio/sql/0002_permisos.sql:24; app/negocio/sql/0006_certificados_y_trabajos.sql:1 | T-07, T-25 | 5 | ninguno | pasó |
| C5 | Solo lo suyo | politica/verdeazul/reglas.rego:72 | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | T-08 | 3 | ninguno | pasó |
| C6 | Ventana de auditoría | politica/verdeazul/reglas.rego:84 | — | T-09 | 3 | ninguno | pasó |
| C7 | Solicitar enmienda | politica/verdeazul/reglas.rego:88 | — | T-11, T-21 | 4 | ninguno | pasó |
| C8 | Autorización final | politica/verdeazul/reglas.rego:95 | app/negocio/sql/0004_reglas_en_la_base.sql:38 | T-12, T-24 | 4 | ninguno | pasó |
| C9 | Corregir dentro del plazo | politica/verdeazul/reglas.rego:105 | — | T-13 | 2 | ninguno | pasó |
| C10 | Revisión técnica independiente | politica/verdeazul/reglas.rego:113 | app/negocio/sql/0004_reglas_en_la_base.sql:38 | T-14, T-23 | 4 | ninguno | pasó |
| C11 | Catálogo con segunda firma | politica/verdeazul/reglas.rego:122 | app/negocio/sql/0004_reglas_en_la_base.sql:89 | T-15 | 1 | ninguno | pasó |
| C12 | Nadie se administra a sí mismo | politica/verdeazul/reglas.rego:132 | app/negocio/sql/0004_reglas_en_la_base.sql:110 | T-16 | 2 | ninguno | pasó |
| C13 | Credenciales y declaración propias | politica/verdeazul/reglas.rego:145 | — | T-35 | 2 | ninguno | pasó |
| C14 | Apertura y cierre entre dos | politica/verdeazul/reglas.rego:149 | app/negocio/sql/0004_reglas_en_la_base.sql:6 | T-04, T-17, T-22 | 6 | ninguno | pasó |
| C15 | Alertas ajenas | politica/verdeazul/reglas.rego:164 | app/negocio/sql/0006_certificados_y_trabajos.sql:70 | T-36 | 2 | ninguno | pasó |
| C16 | Supresión condicionada | politica/verdeazul/reglas.rego:177 | app/negocio/sql/0004_reglas_en_la_base.sql:153 | T-37 | 2 | ninguno | pasó |
| C17 | Abstención por vínculo | politica/verdeazul/decision.rego:80 | — | T-29 | 2 | ninguno | pasó |
| C18 | Exportar evidencia | politica/verdeazul/reglas.rego:180 | — | T-31 | 3 | ninguno | pasó |
| C19 | Asignar con vigencia y máximo de activas (K-1) | politica/verdeazul/reglas.rego:185 | app/negocio/sql/0004_reglas_en_la_base.sql:120; app/negocio/sql/0007_fecha_de_costa_rica.sql:2 | T-27, T-28, T-38, T-39 | 8 | ninguno | pasó |
| C20 | Comprobación pública | politica/verdeazul/reglas.rego:193 | app/negocio/sql/0006_certificados_y_trabajos.sql:2 | T-32 | 4 | ninguno | pasó |
| H1 | Frecuencia | politica/verdeazul/decision.rego:55 | — | T-02, T-18 | 4 | ninguno | pasó |
| H2 | Tiempo | politica/verdeazul/decision.rego:108 | — | T-34 | 2 | ninguno | pasó |
| H3 | Combinada | politica/verdeazul/decision.rego:105 | — | T-19, T-33 | 4 | ninguno | pasó |
| H4 | Secuencia (C3, C8, C10) | politica/verdeazul/reglas.rego:51 | app/negocio/sql/0004_reglas_en_la_base.sql:38 | T-06, T-14, T-24 | 6 | ninguno | pasó |
| K-3 | Motor caído: fallo cerrado | politica/verdeazul/decision.rego:39 | — | T-41 | 4 | ninguno | pasó |
| Filas | Filas sin acceso (AUD no escribe, OPE no entra) | — | — | T-10, T-20 | 3 | ninguno | pasó |

## Casos T y sus pruebas

| Caso | Pruebas | Resultado |
|---|---|---|
| T-01 | `flujos.tests.CasosDeLaParte1.test_t01_el_tecnico_registra_en_su_finca`<br>`rego.test_t01_crea_una_medicion_en_su_finca` | pasó |
| T-02 | `flujos.tests.CasosDeLaParte1.test_t02_t27_fuera_de_sus_fincas_no_existe`<br>`rego.test_t02_detalle_de_una_finca_sin_asignar` | pasó |
| T-03 | `flujos.tests.CasosDeLaParte1.test_t03_una_medicion_enviada_ya_no_se_modifica`<br>`rego.test_t03_modificar_una_medicion_ya_enviada` | pasó |
| T-04 | `flujos.tests_casos.CasosQueFaltaban.test_t04_despues_del_cierre_un_borrador_ya_no_se_modifica`<br>`rego.test_t04_modificar_un_borrador_despues_del_cierre` | pasó |
| T-05 | `autorizacion.tests.HechosDesdeLaBase.test_con_el_motor_real_t05_y_t06`<br>`flujos.tests.CasosDeLaParte1.test_t05_otro_verificador_aprueba`<br>`rego.test_t05_b_aprueba_lo_que_registro_a` | pasó |
| T-06 | `flujos.tests.CasosDeLaParte1.test_t06_quien_escribio_una_version_no_aprueba`<br>`rego.test_t06_c_escribio_la_version_1` | pasó |
| T-07 | `flujos.tests_certificados.EmisionDeCertificados.test_t07_emitir_dos_veces_no_duplica`<br>`rego.test_t07_no_emite_si_ya_hay_uno_vigente` | pasó |
| T-08 | `autorizacion.tests.Decorador.test_t08_lo_ajeno_responde_igual_que_lo_inexistente`<br>`flujos.tests.CasosDeLaParte1.test_t08_el_dueno_solo_ve_lo_suyo`<br>`rego.test_t08_el_dueno_pide_el_certificado_de_otro` | pasó |
| T-09 | `cuentas.tests.VentanaDeLaCuenta.test_t09_una_semana_despues_de_su_ventana`<br>`flujos.tests_trabajos.TrabajoDiario.test_t09_la_ventana_vencida_y_45_dias_sin_uso_dan_de_baja`<br>`rego.test_t09_auditora_fuera_de_su_ventana` | pasó |
| T-10 | `flujos.tests.CasosDeLaParte1.test_t10_la_auditora_no_escribe`<br>`rego.test_t10_la_auditora_no_modifica_nada` | pasó |
| T-11 | `flujos.tests_casos.CasosQueFaltaban.test_t11_un_tecnico_no_pide_enmienda_de_lo_que_midio_otro`<br>`rego.test_t11_el_tecnico_pide_enmienda_de_lo_que_midio_otro` | pasó |
| T-12 | `flujos.tests_casos.CasosQueFaltaban.test_t24_t12_t25_la_que_solicito_no_autoriza_otra_gerente_si_y_se_reemite`<br>`rego.test_t12_la_gerente_autoriza` | pasó |
| T-13 | `flujos.tests_casos.CasosQueFaltaban.test_t13_no_se_corrige_pasados_diez_dias_habiles`<br>`rego.test_t13_corregir_once_dias_habiles_despues` | pasó |
| T-14 | `flujos.tests_casos.CasosQueFaltaban.test_t14_quien_solicito_no_da_el_dictamen`<br>`rego.test_t14_quien_solicito_no_dictamina` | pasó |
| T-15 | `flujos.tests.CasosDeLaParte1.test_t15_catalogo_con_segunda_firma` | pasó |
| T-16 | `flujos.tests.CasosDeLaParte1.test_t16_nadie_se_administra_a_si_mismo`<br>`rego.test_t16_el_administrador_no_se_propone_a_si_mismo` | pasó |
| T-17 | `flujos.tests_casos.CasosQueFaltaban.test_t17_se_aprueba_despues_del_cierre_lo_enviado_antes`<br>`rego.test_t17_aprobar_despues_del_cierre_lo_enviado_antes` | pasó |
| T-18 | `flujos.tests_casos.CasosQueFaltaban.test_t18_h1_mas_fincas_que_el_umbral_pide_segundo_factor_y_motivo`<br>`rego.test_t18_h1_pide_segundo_factor_y_motivo` | pasó |
| T-19 | `flujos.tests_casos.CasosQueFaltaban.test_t19_t33_h3_fuera_de_jornada_confirma_y_despues_se_restringe`<br>`rego.test_t19_h3_fuera_de_jornada_muchas_fincas_nuevas` | pasó |
| T-20 | `cuentas.tests.VentanaDeLaCuenta.test_t20_ope_no_es_un_rol_de_la_aplicacion` | pasó |
| T-21 | `flujos.tests_casos.CasosQueFaltaban.test_t21_lo_devuelto_no_se_modifica_despues_del_cierre_procede_una_enmienda`<br>`rego.test_t21_modificar_lo_devuelto_despues_del_cierre` | pasó |
| T-22 | `flujos.tests.CasosDeLaParte1.test_t22_al_cerrar_los_borradores_quedan_excluidos`<br>`rego.test_t22_cierre_registrado_pero_no_aprobado` | pasó |
| T-23 | `flujos.tests_casos.CasosQueFaltaban.test_t23_en_una_enmienda_material_quien_aprobo_no_da_el_dictamen`<br>`rego.test_t23_enmienda_material_quien_aprobo_no_dictamina` | pasó |
| T-24 | `flujos.tests_casos.CasosQueFaltaban.test_t24_t12_t25_la_que_solicito_no_autoriza_otra_gerente_si_y_se_reemite`<br>`rego.test_t24_la_gerente_que_la_solicito_no_la_autoriza` | pasó |
| T-25 | `flujos.tests_casos.CasosQueFaltaban.test_t24_t12_t25_la_que_solicito_no_autoriza_otra_gerente_si_y_se_reemite`<br>`flujos.tests_certificados.EmisionDeCertificados.test_t25_una_enmienda_que_cambia_toneladas_revoca_y_reemite`<br>`rego.test_t25_revoca_por_enmienda_que_cambia_toneladas` | pasó |
| T-26 | `flujos.tests_casos.CasosQueFaltaban.test_t26_con_habilitacion_registra_y_en_otra_sesion_no_aprueba`<br>`rego.test_t26_con_habilitacion_registro_y_despues_aprueba` | pasó |
| T-27 | `flujos.tests.CasosDeLaParte1.test_t02_t27_fuera_de_sus_fincas_no_existe`<br>`rego.test_t27_asignacion_temporal_vencida` | pasó |
| T-28 | `flujos.tests.CasosDeLaParte1.test_t28_una_asignacion_temporal_valida`<br>`rego.test_t28_la_supervisora_no_se_asigna_a_si_misma` | pasó |
| T-29 | `flujos.tests.CasosDeLaParte1.test_t29_con_vinculo_se_abstiene`<br>`rego.test_t29_vinculo_con_el_titular` | pasó |
| T-30 | `flujos.tests_casos.CasosQueFaltaban.test_t30_no_se_registra_una_fecha_de_medicion_futura`<br>`rego.test_t30_fecha_de_medicion_futura`<br>`rego.test_t30_fecha_de_medicion_fuera_del_periodo` | pasó |
| T-31 | `flujos.tests.CasosDeLaParte1.test_t31_la_auditora_exporta_con_huella`<br>`flujos.tests_certificados.LaAplicacionPideAlServicio.test_t31_el_paquete_del_auditor_sale_sellado_y_se_verifica`<br>`rego.test_t31_exporta_dentro_de_su_ventana` | pasó |
| T-32 | `flujos.tests_certificados.EmisionDeCertificados.test_t32_el_publico_comprueba_por_codigo_exacto_y_nada_mas`<br>`test_servicio.ComprobacionPublica.test_t32_el_mismo_con_una_tonelada_cambiada`<br>`test_servicio.ComprobacionPublica.test_t32_un_revocado_dice_cual_lo_reemplaza`<br>`rego.test_t32_comprobar_con_el_codigo` | pasó |
| T-33 | `flujos.tests_casos.CasosQueFaltaban.test_t19_t33_h3_fuera_de_jornada_confirma_y_despues_se_restringe`<br>`rego.test_t33_despues_de_confirmar_h3_las_fincas_nuevas_se_restringen` | pasó |
| T-34 | `flujos.tests_casos.CasosQueFaltaban.test_t34_h2_aprobar_fuera_de_la_jornada_pide_motivo`<br>`rego.test_t34_h2_aprobar_un_domingo` | pasó |
| T-35 | `flujos.tests.CasosDeLaParte1.test_t35_cada_quien_sus_vinculos`<br>`rego.test_t35_cambiar_la_contrasena_de_otra_cuenta` | pasó |
| T-36 | `flujos.tests.CasosDeLaParte1.test_t36_nadie_resuelve_una_alerta_sobre_si_mismo`<br>`rego.test_t36_la_supervisora_no_resuelve_una_alerta_sobre_si_misma` | pasó |
| T-37 | `flujos.tests.CasosDeLaParte1.test_t37_supresion_sin_obligacion_de_conservar`<br>`rego.test_t37_no_suprime_datos_que_hay_que_conservar` | pasó |
| T-38 | `flujos.tests.CasosDeLaParte1.test_t38_el_maximo_de_asignaciones`<br>`rego.test_t38_la_asignacion_21` | pasó |
| T-39 | `flujos.tests_casos.CasosQueFaltaban.test_t39_las_temporales_vencidas_no_cuentan_para_el_maximo`<br>`rego.test_t39_con_19_activas_si_se_asigna` | pasó |
| T-40 | `flujos.tests.CasosDeLaParte1.test_t40_el_aprobador_sale_de_la_sesion` | pasó |
| T-41 | `autorizacion.tests.FalloCerrado.test_t41_motor_lento_frena_en_el_limite`<br>`autorizacion.tests.FalloCerrado.test_t41_motor_apagado`<br>`autorizacion.tests.Decorador.test_t41_sin_motor_503`<br>`nucleo.tests.InicioPorRol.test_t41_sin_motor_el_inicio_tambien_se_frena` | pasó |

## Los permisos concedidos

| Rol | Objeto | Verbo | Condiciones | Motor (Rego) | Ruta o componente | Base | Prueba del caso feliz | Casos de sus reglas | Resultado |
|---|---|---|---|---|---|---|---|---|---|
| TEC | fincas | leer | C1 | politica/verdeazul/reglas.rego:17 | fincas, finca | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0005_tec_inserta_medicion.sql:4; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-01, T-02, T-27 | pasó |
| TEC | datos_personales | leer | C1 | politica/verdeazul/reglas.rego:17 | titulares, titular | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0005_tec_inserta_medicion.sql:4; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-01, T-02, T-27 | pasó |
| TEC | periodos | leer | — | matriz.json | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| TEC | asignaciones | leer | C1 | politica/verdeazul/reglas.rego:17 | asignaciones | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0005_tec_inserta_medicion.sql:4; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-01, T-02, T-27 | pasó |
| TEC | mediciones | leer | C1 | politica/verdeazul/reglas.rego:17 | mediciones, medicion | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0005_tec_inserta_medicion.sql:4; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-01, T-02, T-27 | pasó |
| TEC | mediciones | crear | C2 | politica/verdeazul/reglas.rego:34 | nueva_medicion | app/negocio/sql/0004_reglas_en_la_base.sql:6 | `test_tec_crear_mediciones` | T-01, T-03, T-04, T-21, T-30 | pasó |
| TEC | mediciones | modificar | C2 | politica/verdeazul/reglas.rego:34 | modificar_medicion | app/negocio/sql/0004_reglas_en_la_base.sql:6 | `test_tec_modificar_mediciones` | T-01, T-03, T-04, T-21, T-30 | pasó |
| TEC | mediciones | enviar | C2 | politica/verdeazul/reglas.rego:34 | enviar_medicion | app/negocio/sql/0004_reglas_en_la_base.sql:6 | `test_tec_enviar_mediciones` | T-01, T-03, T-04, T-21, T-30 | pasó |
| TEC | enmiendas | leer | C1 | politica/verdeazul/reglas.rego:17 | enmiendas, enmienda | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0005_tec_inserta_medicion.sql:4; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-01, T-02, T-27 | pasó |
| TEC | enmiendas | solicitar | C7 | politica/verdeazul/reglas.rego:88 | solicitar_enmienda | — | `test_tec_solicitar_enmiendas` | T-11, T-21 | pasó |
| TEC | enmiendas | corregir | C9 | politica/verdeazul/reglas.rego:105 | corregir_enmienda | — | `test_tec_corregir_enmiendas` | T-13 | pasó |
| TEC | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| VER | fincas | leer | H | matriz.json | fincas, finca | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| VER | periodos | leer | — | matriz.json | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| VER | mediciones | leer | H | matriz.json | mediciones, medicion | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| VER | mediciones | aprobar | C3 | politica/verdeazul/reglas.rego:51 | aprobar_medicion | app/negocio/sql/0004_reglas_en_la_base.sql:38 | `test_ver_aprobar_mediciones` | T-05, T-06, T-17, T-26, T-40 | pasó |
| VER | mediciones | devolver | C3 | politica/verdeazul/reglas.rego:51 | devolver_medicion | app/negocio/sql/0004_reglas_en_la_base.sql:38 | `test_ver_devolver_mediciones` | T-05, T-06, T-17, T-26, T-40 | pasó |
| VER | enmiendas | leer | — | matriz.json | enmiendas, enmienda | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| VER | enmiendas | solicitar | C7 | politica/verdeazul/reglas.rego:88 | solicitar_enmienda | — | `test_ver_solicitar_enmiendas` | T-11, T-21 | pasó |
| VER | enmiendas | revisar | C10 | politica/verdeazul/reglas.rego:113 | revisar_enmienda | app/negocio/sql/0004_reglas_en_la_base.sql:38 | `test_ver_revisar_enmiendas` | T-14, T-23 | pasó |
| VER | certificados | leer | H | matriz.json | certificados, certificado, descargar_certificado | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| VER | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| SUP | fincas | leer | H | matriz.json | fincas, finca | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| SUP | periodos | leer | — | matriz.json | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| SUP | asignaciones | leer | — | matriz.json | asignaciones | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| SUP | asignaciones | crear | C19 | politica/verdeazul/reglas.rego:185 | crear_asignacion | app/negocio/sql/0004_reglas_en_la_base.sql:120; app/negocio/sql/0007_fecha_de_costa_rica.sql:2 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-27, T-28, T-38, T-39 | pasó |
| SUP | asignaciones | modificar | C19 | politica/verdeazul/reglas.rego:185 | asignacion, terminar_asignacion, renovar_asignacion | app/negocio/sql/0004_reglas_en_la_base.sql:120; app/negocio/sql/0007_fecha_de_costa_rica.sql:2 | `test_sup_modificar_asignaciones` | T-27, T-28, T-38, T-39 | pasó |
| SUP | mediciones | leer | H | matriz.json | mediciones, medicion | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| SUP | enmiendas | leer | — | matriz.json | enmiendas, enmienda | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| SUP | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| SUP | alertas | leer | C15 | politica/verdeazul/reglas.rego:164 | alertas | app/negocio/sql/0006_certificados_y_trabajos.sql:70 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-36 | pasó |
| SUP | alertas | resolver | C15 | politica/verdeazul/reglas.rego:164 | resolver_alerta | app/negocio/sql/0006_certificados_y_trabajos.sql:70 | `test_sup_resolver_alertas` | T-36 | pasó |
| GER | fincas | leer | H | matriz.json | fincas, finca | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | fincas | aprobar | C11 | politica/verdeazul/reglas.rego:122 | aprobar_catalogo | app/negocio/sql/0004_reglas_en_la_base.sql:89 | `test_ger_aprobar_fincas` | T-15 | pasó |
| GER | datos_personales | leer | H | matriz.json | titulares, titular | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | periodos | leer | — | matriz.json | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | periodos | abrir | C14 | politica/verdeazul/reglas.rego:149 | abrir_periodo | app/negocio/sql/0004_reglas_en_la_base.sql:6 | `test_ger_abrir_periodos` | T-04, T-17, T-22 | pasó |
| GER | periodos | cerrar | C14 | politica/verdeazul/reglas.rego:149 | cerrar_periodo | app/negocio/sql/0004_reglas_en_la_base.sql:6 | `test_ger_cerrar_periodos` | T-04, T-17, T-22 | pasó |
| GER | asignaciones | leer | — | matriz.json | asignaciones | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | mediciones | leer | H | matriz.json | mediciones, medicion | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | enmiendas | leer | — | matriz.json | enmiendas, enmienda | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | enmiendas | solicitar | C7 | politica/verdeazul/reglas.rego:88 | solicitar_enmienda | — | `test_ger_solicitar_enmiendas` | T-11, T-21 | pasó |
| GER | enmiendas | autorizar | C8 | politica/verdeazul/reglas.rego:95 | autorizar_enmienda | app/negocio/sql/0004_reglas_en_la_base.sql:38 | `test_ger_autorizar_enmiendas` | T-12, T-24 | pasó |
| GER | certificados | leer | H | matriz.json | certificados, certificado, descargar_certificado | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | cuentas | leer | — | matriz.json | cuentas, cuenta | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | cuentas | aprobar | C12 | politica/verdeazul/reglas.rego:132 | aprobar_rol, aprobar_retiro | app/negocio/sql/0004_reglas_en_la_base.sql:110 | `test_ger_aprobar_cuentas` | T-16 | pasó |
| GER | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| GER | bitacora | leer | — | matriz.json | bitacora | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | alertas | leer | — | matriz.json | alertas | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| GER | alertas | resolver | C15 | politica/verdeazul/reglas.rego:164 | resolver_alerta | app/negocio/sql/0006_certificados_y_trabajos.sql:70 | `test_ger_resolver_alertas` | T-36 | pasó |
| ADM | fincas | leer | H | matriz.json | fincas, finca | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| ADM | fincas | proponer | C11 | politica/verdeazul/reglas.rego:122 | proponer_finca, proponer_titular, proponer_parcela | app/negocio/sql/0004_reglas_en_la_base.sql:89 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-15 | pasó |
| ADM | datos_personales | leer | H | matriz.json | titulares, titular | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| ADM | datos_personales | crear | — | matriz.json | crear_titular | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| ADM | datos_personales | modificar | — | matriz.json | editar_titular | — | `test_adm_modificar_datos_personales` | — | pasó |
| ADM | datos_personales | eliminar | C16 | politica/verdeazul/reglas.rego:177 | suprimir_titular | app/negocio/sql/0004_reglas_en_la_base.sql:153 | `test_adm_eliminar_datos_personales` | T-37 | pasó |
| ADM | periodos | leer | — | matriz.json | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| ADM | periodos | crear | — | matriz.json | crear_periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| ADM | periodos | proponer | C14 | politica/verdeazul/reglas.rego:149 | proponer_periodo | app/negocio/sql/0004_reglas_en_la_base.sql:6 | `test_adm_proponer_periodos` | T-04, T-17, T-22 | pasó |
| ADM | cuentas | leer | — | matriz.json | cuentas, cuenta | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| ADM | cuentas | crear | C12 | politica/verdeazul/reglas.rego:132 | crear_cuenta | app/negocio/sql/0004_reglas_en_la_base.sql:110 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-16 | pasó |
| ADM | cuentas | desactivar | C12 | politica/verdeazul/reglas.rego:132 | desactivar_cuenta | app/negocio/sql/0004_reglas_en_la_base.sql:110 | `test_adm_desactivar_cuentas` | T-16 | pasó |
| ADM | cuentas | proponer | C12 | politica/verdeazul/reglas.rego:132 | proponer_rol | app/negocio/sql/0004_reglas_en_la_base.sql:110 | `test_adm_proponer_cuentas` | T-16 | pasó |
| ADM | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| AUD | fincas | leer | C6 | politica/verdeazul/reglas.rego:84 | fincas, finca | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | fincas | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_fincas | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | datos_personales | leer | C6 | politica/verdeazul/reglas.rego:84 | titulares, titular | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | periodos | leer | C6 | politica/verdeazul/reglas.rego:84 | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | periodos | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_periodos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | asignaciones | leer | C6 | politica/verdeazul/reglas.rego:84 | asignaciones | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | asignaciones | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_asignaciones | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | mediciones | leer | C6 | politica/verdeazul/reglas.rego:84 | mediciones, medicion | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | mediciones | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_mediciones | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | enmiendas | leer | C6 | politica/verdeazul/reglas.rego:84 | enmiendas, enmienda | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | enmiendas | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_enmiendas | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | certificados | leer | C6 | politica/verdeazul/reglas.rego:84 | certificados, certificado, descargar_certificado | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | certificados | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_certificados | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | cuentas | leer | C6 | politica/verdeazul/reglas.rego:84 | cuentas, cuenta | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| AUD | bitacora | leer | C6 | politica/verdeazul/reglas.rego:84 | bitacora | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | bitacora | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_bitacora | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| AUD | alertas | leer | C6 | politica/verdeazul/reglas.rego:84 | alertas | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-09 | pasó |
| AUD | alertas | exportar | C18 | politica/verdeazul/reglas.rego:180 | exportar_alertas | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-31 | pasó |
| DUE | fincas | leer | C5 | politica/verdeazul/reglas.rego:72 | fincas, finca | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-08 | pasó |
| DUE | datos_personales | leer | C5 | politica/verdeazul/reglas.rego:72 | titulares, titular | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-08 | pasó |
| DUE | periodos | leer | — | matriz.json | periodos, periodo | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | — | pasó |
| DUE | asignaciones | leer | C5 | politica/verdeazul/reglas.rego:72 | asignaciones | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-08 | pasó |
| DUE | mediciones | leer | C5 | politica/verdeazul/reglas.rego:72 | mediciones, medicion | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-08 | pasó |
| DUE | enmiendas | leer | C5 | politica/verdeazul/reglas.rego:72 | enmiendas, enmienda | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-08 | pasó |
| DUE | certificados | leer | C5 | politica/verdeazul/reglas.rego:72 | certificados, certificado, descargar_certificado | app/negocio/sql/0003_seguridad_por_fila.sql:1; app/negocio/sql/0007_fecha_de_costa_rica.sql:1 | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-08 | pasó |
| DUE | cuentas | modificar | C13 | politica/verdeazul/reglas.rego:145 | mis_vinculos | — | `test_cada_rol_entra_a_lo_que_la_matriz_le_concede` | T-35 | pasó |
| SIS | fincas | leer | — | matriz.json | emision/emitir.py (lee lo necesario para emitir con va_emision) | — | `test_emite_una_medicion_aprobada_con_contenido_firmado` | — | pasó |
| SIS | datos_personales | leer | — | matriz.json | emision/emitir.py (lee lo necesario para emitir con va_emision) | — | `test_emite_una_medicion_aprobada_con_contenido_firmado` | — | pasó |
| SIS | periodos | leer | — | matriz.json | emision/emitir.py (lee lo necesario para emitir con va_emision) | — | `test_emite_una_medicion_aprobada_con_contenido_firmado` | — | pasó |
| SIS | asignaciones | leer | — | matriz.json | emision/emitir.py (lee lo necesario para emitir con va_emision) | — | `test_emite_una_medicion_aprobada_con_contenido_firmado` | — | pasó |
| SIS | mediciones | leer | — | matriz.json | emision/emitir.py (lee lo necesario para emitir con va_emision) | — | `test_emite_una_medicion_aprobada_con_contenido_firmado` | — | pasó |
| SIS | enmiendas | leer | — | matriz.json | emision/emitir.py (lee lo necesario para emitir con va_emision) | — | `test_emite_una_medicion_aprobada_con_contenido_firmado` | — | pasó |
| SIS | certificados | emitir | C4 | politica/verdeazul/reglas.rego:58 | emision/emitir.py: emitir() (6.3) | app/negocio/sql/0002_permisos.sql:24; app/negocio/sql/0006_certificados_y_trabajos.sql:1 | `test_emite_una_medicion_aprobada_con_contenido_firmado` | T-07, T-25 | pasó |
| SIS | certificados | revocar | C4 | politica/verdeazul/reglas.rego:58 | emision/emitir.py: reemitir() (6.5) | app/negocio/sql/0002_permisos.sql:24; app/negocio/sql/0006_certificados_y_trabajos.sql:1 | `test_t25_una_enmienda_que_cambia_toneladas_revoca_y_reemite` | T-07, T-25 | pasó |
| SIS | bitacora | anexar | — | matriz.json | bitacora_anexar() en cada acción | — | `test_la_cadena_de_la_semilla_esta_integra` | — | pasó |
| SIS | alertas | crear | — | matriz.json | autorizacion/historial.py: alertar() (alertas de H1 a H3) | — | `test_t18_h1_mas_fincas_que_el_umbral_pide_segundo_factor_y_motivo` | — | pasó |
| PUB | certificados | comprobar | C20 | politica/verdeazul/reglas.rego:193 | publico/servicio.py: /comprobar (6.7) | app/negocio/sql/0006_certificados_y_trabajos.sql:2 | `test_un_codigo_vigente` | T-32 | pasó |

## Celdas denegadas

Todas se deniegan por la matriz en el motor, antes de mirar el objeto; las prueban `test_lo_que_no_esta_en_la_matriz_se_deniega` (pasó), `test_la_matriz_tiene_102_permisos_y_38_celdas_denegadas` (pasó), `test_con_cada_rol_un_identificador_ajeno_no_da_nada` (pasó).

| Rol | Objetos sin ningún permiso |
|---|---|
| TEC | certificados, bitacora, alertas |
| VER | datos_personales, asignaciones, bitacora, alertas |
| SUP | datos_personales, certificados, bitacora |
| ADM | asignaciones, mediciones, enmiendas, certificados, bitacora, alertas |
| DUE | bitacora, alertas |
| SIS | cuentas |
| OPE | fincas, datos_personales, periodos, asignaciones, mediciones, enmiendas, certificados, cuentas, bitacora, alertas |
| PUB | fincas, datos_personales, periodos, asignaciones, mediciones, enmiendas, cuentas, bitacora, alertas |

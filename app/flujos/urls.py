"""Rutas de los flujos del negocio. Cada una lleva @protegida con su verbo y su objeto de la matriz;
una prueba exige que los 102 permisos tengan al menos una."""

from django.urls import path

from flujos.vistas import (
    alertas,
    asignaciones,
    bitacora,
    certificados,
    cuentas,
    enmiendas,
    exportar,
    fincas,
    mediciones,
    periodos,
    titulares,
)

urlpatterns = [
    # Catálogo (5.2)
    path("fincas/", fincas.lista, name="fincas"),
    path("fincas/proponer/", fincas.proponer_finca, name="proponer_finca"),
    path("fincas/<uuid:finca>/", fincas.ficha, name="finca"),
    path("fincas/<uuid:finca>/proponer-titular/", fincas.proponer_titular, name="proponer_titular"),
    path("fincas/<uuid:finca>/proponer-parcela/", fincas.proponer_parcela, name="proponer_parcela"),
    path("catalogo/<uuid:propuesta>/aprobar/", fincas.aprobar, name="aprobar_catalogo"),
    # Datos personales (5.9)
    path("titulares/", titulares.lista, name="titulares"),
    path("titulares/nuevo/", titulares.crear, name="crear_titular"),
    path("titulares/<uuid:titular>/", titulares.ficha, name="titular"),
    path("titulares/<uuid:titular>/datos/", titulares.editar, name="editar_titular"),
    path("titulares/<uuid:titular>/suprimir/", titulares.suprimir, name="suprimir_titular"),
    # Períodos (5.4)
    path("periodos/", periodos.lista, name="periodos"),
    path("periodos/nuevo/", periodos.crear, name="crear_periodo"),
    path("periodos/<uuid:periodo>/", periodos.ficha, name="periodo"),
    path("periodos/<uuid:periodo>/registrar/", periodos.proponer, name="proponer_periodo"),
    path("periodos/registros/<uuid:propuesta>/abrir/", periodos.abrir, name="abrir_periodo"),
    path("periodos/registros/<uuid:propuesta>/cerrar/", periodos.cerrar, name="cerrar_periodo"),
    # Asignaciones (5.5)
    path("asignaciones/", asignaciones.lista, name="asignaciones"),
    path("asignaciones/nueva/", asignaciones.crear, name="crear_asignacion"),
    path("asignaciones/<uuid:asignacion>/", asignaciones.ficha, name="asignacion"),
    path("asignaciones/<uuid:asignacion>/terminar/", asignaciones.terminar, name="terminar_asignacion"),
    path("asignaciones/<uuid:asignacion>/renovar/", asignaciones.renovar, name="renovar_asignacion"),
    # Mediciones (5.6)
    path("mediciones/", mediciones.lista, name="mediciones"),
    path("parcelas/<uuid:parcela>/medicion/", mediciones.crear, name="nueva_medicion"),
    path("mediciones/<uuid:medicion>/", mediciones.ficha, name="medicion"),
    path("mediciones/<uuid:medicion>/version/", mediciones.modificar, name="modificar_medicion"),
    path("mediciones/<uuid:medicion>/enviar/", mediciones.enviar, name="enviar_medicion"),
    path("mediciones/<uuid:medicion>/aprobar/", mediciones.aprobar, name="aprobar_medicion"),
    path("mediciones/<uuid:medicion>/devolver/", mediciones.devolver, name="devolver_medicion"),
    # Enmiendas (5.7)
    path("enmiendas/", enmiendas.lista, name="enmiendas"),
    path("mediciones/<uuid:medicion>/enmienda/", enmiendas.solicitar, name="solicitar_enmienda"),
    path("enmiendas/<uuid:enmienda>/", enmiendas.ficha, name="enmienda"),
    path("enmiendas/<uuid:enmienda>/corregir/", enmiendas.corregir, name="corregir_enmienda"),
    path("enmiendas/<uuid:enmienda>/revisar/", enmiendas.revisar, name="revisar_enmienda"),
    path("enmiendas/<uuid:enmienda>/autorizar/", enmiendas.autorizar, name="autorizar_enmienda"),
    # Certificados (lectura; la emisión es del sistema, fase 6)
    path("certificados/", certificados.lista, name="certificados"),
    path("certificados/<uuid:certificado>/", certificados.ficha, name="certificado"),
    # Cuentas (5.3)
    path("personal/", cuentas.lista, name="cuentas"),
    path("personal/nueva/", cuentas.crear, name="crear_cuenta"),
    path("personal/<uuid:cuenta>/", cuentas.ficha, name="cuenta"),
    path("personal/<uuid:cuenta>/desactivar/", cuentas.desactivar, name="desactivar_cuenta"),
    path("personal/<uuid:cuenta>/rol/", cuentas.proponer_rol, name="proponer_rol"),
    path("personal/roles/<uuid:propuesta>/aprobar/", cuentas.aprobar_rol, name="aprobar_rol"),
    path("personal/vinculos/<uuid:vinculo>/aprobar-retiro/", cuentas.aprobar_retiro, name="aprobar_retiro"),
    path("mis-vinculos/", cuentas.mis_vinculos, name="mis_vinculos"),
    # Alertas (5.8) y bitácora (5.12)
    path("alertas/", alertas.lista, name="alertas"),
    path("alertas/<uuid:alerta>/resolver/", alertas.resolver, name="resolver_alerta"),
    path("bitacora/", bitacora.lista, name="bitacora"),
] + [
    # Exportaciones del auditor (5.11, C18)
    path(f"exportar/{tipo}/", vista, name=f"exportar_{tipo}")
    for tipo, vista in exportar.VISTAS.items()
]

"""Pruebas de los flujos (fase 5 y 8.3): cada permiso de la matriz tiene una ruta que lo ejerce, y
los casos de la Parte 1 se cumplen de punta a punta con el motor real (8.1)."""

import io
import json
import os
import time
import urllib.request
from datetime import timedelta
from pathlib import Path
from unittest import mock, skipUnless

from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import get_resolver, reverse
from django.utils import timezone

from bitacora.models import Registro
from cuentas.models import Usuario
from negocio.models import (
    Alerta,
    DatosPersonales,
    ExportacionAuditoria,
    Finca,
    Medicion,
    Parcela,
    Periodo,
    PropuestaCatalogo,
    PropuestaPeriodo,
    Titular,
)

MATRIZ = Path(settings.BASE_DIR).parent / "politica" / "matriz.json"


def _rutas(patrones=None):
    for patron in get_resolver().url_patterns if patrones is None else patrones:
        if hasattr(patron, "url_patterns"):
            yield from _rutas(patron.url_patterns)
        else:
            yield patron


@skipUnless(MATRIZ.exists(), "matriz.json no está junto a la aplicación (imagen de producción)")
class CadaPermisoTieneRuta(SimpleTestCase):
    """8.3, parte estructural: para cada permiso de los siete roles de la aplicación existe al menos
    una ruta declarada con @protegida(verbo, objeto). Los de SIS (emitir, revocar, anexar, crear
    alertas) y PUB (comprobar) son de los servicios de la fase 6 y de la propia aplicación."""

    def test_los_permisos_de_los_roles_de_la_aplicacion_tienen_ruta(self):
        matriz = json.loads(MATRIZ.read_text(encoding="utf-8"))["matriz"]
        declaradas = {getattr(ruta.callback, "protegida", None) for ruta in _rutas()} - {None}
        roles = matriz["roles_de_la_aplicacion"]
        permisos = [(rol, objeto, p["verbo"]) for rol in roles for objeto, lista in matriz["celdas"].get(rol, {}).items()
                    for p in lista]
        faltan = [f"{rol} {verbo} {objeto}" for rol, objeto, verbo in permisos if (verbo, objeto) not in declaradas]
        self.assertEqual(faltan, [], f"Permisos sin ruta: {faltan}")
        self.assertGreater(len(permisos), 80)

    def test_ninguna_ruta_declara_algo_que_la_matriz_no_tiene(self):
        matriz = json.loads(MATRIZ.read_text(encoding="utf-8"))["matriz"]
        existentes = {(p["verbo"], objeto) for celdas in matriz["celdas"].values() for objeto, lista in celdas.items()
                      for p in lista}
        declaradas = {getattr(ruta.callback, "protegida", None) for ruta in _rutas()} - {None}
        self.assertEqual(declaradas - existentes, set())


# --- Casos de la Parte 1 de punta a punta (8.1) ---------------------------------------------------


def _opa_disponible():
    try:
        with urllib.request.urlopen(settings.OPA_URL.rstrip("/") + "/health", timeout=1) as respuesta:
            return respuesta.status == 200
    except OSError:
        return False


MOTIVO = {"motivo": "Prueba automática de la matriz"}


@skipUnless(_opa_disponible(), "requiere el motor real (OPA) en OPA_URL")
class CasosDeLaParte1(TestCase):
    """Los casos T-xx con los personajes de la semilla, pasando por las rutas, el motor real y los
    disparadores de la base. Fuera de la jornada (H2) las decisiones piden motivo: se envía uno."""

    @classmethod
    def setUpTestData(cls):
        with mock.patch.dict(os.environ, {"SEMILLA_CONTRASENA": "Clave-local-de-pruebas-2026"}):
            call_command("sembrar", stdout=io.StringIO())

    def _como(self, usuario, rol):
        persona = Usuario.objects.get(username=usuario)
        if not Authenticator.objects.filter(user=persona, type=Authenticator.Type.TOTP).exists():
            TOTP.activate(persona, generate_totp_secret())
        self.client.force_login(persona)
        sesion = self.client.session
        sesion["va_rol"] = rol
        sesion["va_inicio"] = int(time.time())
        # Como lo deja allauth al pasar el segundo factor: el registro va atado al id de la cuenta.
        from allauth.account.internal.flows.login import _AUTHENTICATION_METHODS_USER_SESSION_KEY
        sesion["account_authentication_methods"] = [{"method": "mfa", "at": time.time(), "type": "totp"}]
        sesion[_AUTHENTICATION_METHODS_USER_SESSION_KEY] = str(persona.pk)
        sesion.save()
        return persona

    def _medicion(self, finca, parcela, periodo):
        return Medicion.objects.get(parcela__finca__codigo=finca, parcela__codigo=parcela, periodo__nombre=periodo)

    def _regla(self, respuesta):
        return respuesta.context["regla"] if respuesta.context and "regla" in respuesta.context else None

    # C1, C2 -------------------------------------------------------------------------------------

    def test_t01_el_tecnico_registra_en_su_finca(self):
        ana = self._como("tec.ana", "TEC")
        parcela = Parcela.objects.get(finca__codigo="F-001", codigo="P-1", activa=True)
        datos = {"fecha_medicion": timezone.localdate().isoformat(), "arboles": 100, "dap_promedio_cm": "20.5",
                 "altura_promedio_m": "12.0", "toneladas_co2": "40.250"}
        respuesta = self.client.post(reverse("nueva_medicion", args=[parcela.pk]), datos)
        self.assertEqual(respuesta.status_code, 302)
        nueva = Medicion.objects.get(parcela=parcela, creada_por=ana, estado="borrador", periodo__nombre="2026-II")
        self.assertEqual(nueva.version_vigente.autor, ana)
        self.assertTrue(Registro.objects.filter(accion="crear", objeto_tipo="mediciones", objeto_id=str(nueva.pk)).exists())

    def test_t02_t27_fuera_de_sus_fincas_no_existe(self):
        self._como("tec.ana", "TEC")
        vencida = Finca.objects.get(codigo="F-002")  # asignación temporal vencida (T-27)
        ajena = Finca.objects.get(codigo="F-025")
        self.assertEqual(self.client.get(reverse("finca", args=[vencida.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("finca", args=[ajena.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("finca", args=[Finca.objects.get(codigo="F-001").pk])).status_code, 200)

    def test_t03_una_medicion_enviada_ya_no_se_modifica(self):
        self._como("tec.ana", "TEC")
        enviada = self._medicion("F-001", "P-1", "2026-II")
        respuesta = self.client.get(reverse("modificar_medicion", args=[enviada.pk]))
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C2")

    # C3, C17, K-2 ---------------------------------------------------------------------------------

    def test_t05_otro_verificador_aprueba(self):
        diego = self._como("ver.diego", "VER")
        enviada = self._medicion("F-001", "P-1", "2026-II")
        respuesta = self.client.post(reverse("aprobar_medicion", args=[enviada.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 302)
        enviada.refresh_from_db()
        self.assertEqual((enviada.estado, enviada.aprobada_por), ("aprobada", diego))

    def test_t06_quien_escribio_una_version_no_aprueba(self):
        self._como("ver.carla", "VER")
        de_carla = self._medicion("F-003", "P-1", "2026-II")
        respuesta = self.client.post(reverse("aprobar_medicion", args=[de_carla.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C3")
        de_carla.refresh_from_db()
        self.assertEqual(de_carla.estado, "enviada")

    def test_t29_con_vinculo_se_abstiene(self):
        self._como("ver.bruno", "VER")
        de_su_pariente = self._medicion("F-005", "P-1", "2026-II")
        respuesta = self.client.post(reverse("aprobar_medicion", args=[de_su_pariente.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C17")

    def test_t40_el_aprobador_sale_de_la_sesion(self):
        diego = self._como("ver.diego", "VER")
        bruno = Usuario.objects.get(username="ver.bruno")
        pendiente = self._medicion("F-004", "P-1", "2026-I")  # enviada antes del cierre (T-17)
        self.client.post(reverse("aprobar_medicion", args=[pendiente.pk]), {**MOTIVO, "aprobador_id": str(bruno.pk)})
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.aprobada_por, diego)

    # C5, C6, C18 -----------------------------------------------------------------------------------

    def test_t08_el_dueno_solo_ve_lo_suyo(self):
        self._como("due.daniel", "DUE")
        self.assertEqual(self.client.get(reverse("finca", args=[Finca.objects.get(codigo="F-001").pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("finca", args=[Finca.objects.get(codigo="F-002").pk])).status_code, 404)

    def test_t10_la_auditora_no_escribe(self):
        self._como("aud.elena", "AUD")
        respuesta = self.client.post(reverse("crear_periodo"), {"nombre": "2027-I", "inicio": "2027-01-04",
                                                                "fin_medicion": "2027-06-11", "cierre_registro": "2027-06-18"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Periodo.objects.filter(nombre="2027-I").exists())

    def test_t31_la_auditora_exporta_con_huella(self):
        elena = self._como("aud.elena", "AUD")
        respuesta = self.client.get(reverse("exportar_fincas"), MOTIVO)
        self.assertEqual(respuesta.status_code, 200)
        huella = respuesta["X-Verdeazul-Huella"]
        self.assertTrue(ExportacionAuditoria.objects.filter(auditor=elena, objeto="fincas", huella=huella).exists())
        self.assertNotIn("Daniel Umaña", respuesta.content.decode())  # sin datos personales de los dueños

    # C11, C12, C14 ----------------------------------------------------------------------------------

    def test_t15_catalogo_con_segunda_firma(self):
        self._como("adm.alberto", "ADM")
        titular = Titular.objects.get(codigo="T-003")
        self.client.post(reverse("proponer_finca"), {
            "codigo": "F-900", "nombre": "Prueba", "titular": titular.pk, "ubicacion": "Rivas", "parcela": "P-1",
            "geometria": "POLYGON((-83.50 9.50,-83.49 9.50,-83.49 9.51,-83.50 9.51,-83.50 9.50))"})
        propuesta = PropuestaCatalogo.objects.get(finca__codigo="F-900")
        self.assertEqual(self.client.post(reverse("aprobar_catalogo", args=[propuesta.pk])).status_code, 403)
        self._como("ger.gabriela", "GER")
        self.client.post(reverse("aprobar_catalogo", args=[propuesta.pk]), MOTIVO)
        self.assertEqual(Finca.objects.get(codigo="F-900").estado, "aprobado")

    def test_t16_nadie_se_administra_a_si_mismo(self):
        alberto = self._como("adm.alberto", "ADM")
        respuesta = self.client.post(reverse("proponer_rol", args=[alberto.pk]), {"rol": "GER"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C12")

    def test_t22_al_cerrar_los_borradores_quedan_excluidos(self):
        self._como("adm.alberto", "ADM")
        periodo = Periodo.objects.get(nombre="2026-II")
        self.client.post(reverse("proponer_periodo", args=[periodo.pk]), {"accion": "cerrar"})
        registro = PropuestaPeriodo.objects.get(periodo=periodo, accion="cerrar", estado="propuesto")
        self._como("ger.gerardo", "GER")
        self.client.post(reverse("cerrar_periodo", args=[registro.pk]), MOTIVO)
        periodo.refresh_from_db()
        self.assertEqual(periodo.estado, "cerrado")
        self.assertEqual(self._medicion("F-001", "P-2", "2026-II").estado, "excluida")

    # C13, C15, C16, C19 -------------------------------------------------------------------------------

    def test_t35_cada_quien_sus_vinculos(self):
        for usuario, rol in (("tec.ana", "TEC"), ("aud.elena", "AUD"), ("due.rosa", "DUE")):
            self._como(usuario, rol)
            self.assertEqual(self.client.get(reverse("mis_vinculos")).status_code, 200)

    def test_t36_nadie_resuelve_una_alerta_sobre_si_mismo(self):
        sofia = self._como("sup.sofia", "SUP")
        propia = Alerta.objects.create(sujeto=sofia, control="H1", nivel="aviso")
        de_ana = Alerta.objects.create(sujeto=Usuario.objects.get(username="tec.ana"), control="H1", nivel="aviso")
        self.assertEqual(self.client.post(reverse("resolver_alerta", args=[propia.pk]),
                                          {**MOTIVO, "resolucion": "x"}).status_code, 403)
        self.client.post(reverse("resolver_alerta", args=[de_ana.pk]), {**MOTIVO, "resolucion": "Revisado"})
        de_ana.refresh_from_db()
        self.assertEqual(de_ana.resuelta_por, sofia)

    def test_t37_supresion_sin_obligacion_de_conservar(self):
        self._como("adm.alberto", "ADM")
        titular = Titular.objects.get(codigo="T-003")
        self.client.post(reverse("suprimir_titular", args=[titular.pk]))
        self.assertIsNotNone(DatosPersonales.objects.get(titular=titular).suprimido_en)

    def test_t38_el_maximo_de_asignaciones(self):
        self._como("sup.sofia", "SUP")
        respuesta = self.client.post(reverse("crear_asignacion"), {
            "tecnico": Usuario.objects.get(username="tec.tomas").pk, "finca": Finca.objects.get(codigo="F-025").pk,
            "periodo": Periodo.objects.get(nombre="2026-II").pk, "tipo": "ordinaria"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C19")

    def test_t28_una_asignacion_temporal_valida(self):
        self._como("sup.sofia", "SUP")
        self.client.post(reverse("crear_asignacion"), {
            "tecnico": Usuario.objects.get(username="tec.ana").pk, "finca": Finca.objects.get(codigo="F-025").pk,
            "periodo": Periodo.objects.get(nombre="2026-II").pk, "tipo": "temporal", "motivo": "Cubrir una ausencia",
            "dias": 10})
        nueva = Finca.objects.get(codigo="F-025").asignaciones.get(tecnico__username="tec.ana")
        self.assertEqual(nueva.hasta - nueva.desde, timedelta(days=10))

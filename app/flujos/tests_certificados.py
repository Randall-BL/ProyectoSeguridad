"""Pruebas de la fase 6 contra la base, con los usuarios de base reales de cada componente: el
servicio de emisión trabaja como va_emision, la comprobación pública como va_publico y la
aplicación como va_app. Así se prueban a la vez la lógica del servicio, los permisos de cada
usuario y el disparador de C4 (negocio/sql/0006). Casos T-07, T-25 y T-32.

El código de los servicios vive fuera de la aplicación (emision/, verificador/): estas pruebas lo
importan desde el repositorio y se saltan si no está (imagen de producción)."""

import io
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock, skipUnless

from allauth.account.internal.flows.login import _AUTHENTICATION_METHODS_USER_SESSION_KEY
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse

from bitacora.models import Registro
from cuentas.models import Usuario
from flujos.tests import MOTIVO, _opa_disponible
from negocio.models import Certificado, Enmienda, ExportacionAuditoria, Medicion, VersionMedicion

RAIZ = Path(settings.BASE_DIR).parent
for carpeta in ("emision", "verificador"):
    if (RAIZ / carpeta).exists() and str(RAIZ / carpeta) not in sys.path:
        sys.path.insert(0, str(RAIZ / carpeta))

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    import emitir
    import verdeazul_certificado as vc
except ImportError:  # pragma: no cover - imagen de producción
    emitir = None


@contextmanager
def como(rol):
    """Ejecuta con los permisos de un usuario de base (el dueño de las pruebas es superusuario
    local y puede tomar ese rol). Devuelve la conexión de psycopg que usan los servicios."""
    with connection.cursor() as cursor:
        cursor.execute(f"SET ROLE {rol}")
    try:
        yield connection.connection
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


@skipUnless(emitir is not None, "emision/ y verificador/ no están junto a la aplicación")
class EmisionDeCertificados(TestCase):
    @classmethod
    def setUpTestData(cls):
        with mock.patch.dict(os.environ, {"SEMILLA_CONTRASENA": "Clave-local-de-pruebas-2026"}):
            call_command("sembrar", stdout=io.StringIO())

    def setUp(self):
        self.clave = Ed25519PrivateKey.generate()
        self.aprobada = Medicion.objects.get(parcela__finca__codigo="F-001", parcela__codigo="P-1", periodo__nombre="2026-I")
        self.enviada = Medicion.objects.get(parcela__finca__codigo="F-004", parcela__codigo="P-1", periodo__nombre="2026-I")

    def _emitir(self, medicion):
        with como("va_emision") as conexion:
            return emitir.emitir(conexion, medicion.pk, self.clave)

    def test_emite_una_medicion_aprobada_con_contenido_firmado(self):
        resultado = self._emitir(self.aprobada)
        self.assertEqual(resultado["resultado"], "emitido")
        c = Certificado.objects.get(codigo=resultado["codigo"])
        self.assertEqual((c.estado, c.medicion, c.toneladas_co2), ("vigente", self.aprobada, self.aprobada.version_vigente.toneladas_co2))
        verificacion = vc.verificar({"contenido": c.contenido, "firma": c.firma}, self.clave.public_key())
        self.assertTrue(verificacion["valido"], verificacion["motivo"])
        self.assertEqual(c.contenido["finca"], "F-001")
        self.assertEqual(c.contenido["aprobado_por"], Usuario.objects.get(username="ver.bruno").get_full_name())
        self.assertRegex(c.codigo, r"^VA-2026-I-[A-Z2-9]{8}$")
        self.assertTrue(Registro.objects.filter(accion="emitir", objeto_id=str(c.pk), rol="SIS", resultado="concedido").exists())

    def test_t07_emitir_dos_veces_no_duplica(self):
        primero = self._emitir(self.aprobada)
        segundo = self._emitir(self.aprobada)
        self.assertEqual(segundo, {"resultado": "ya_emitido", "codigo": primero["codigo"]})
        self.assertEqual(Certificado.objects.filter(medicion=self.aprobada).count(), 1)

    def test_una_medicion_no_aprobada_no_se_certifica(self):
        with self.assertRaisesMessage(emitir.NoSeEmite, "C4"):
            self._emitir(self.enviada)
        self.assertFalse(Certificado.objects.filter(medicion=self.enviada).exists())

    def test_la_base_rechaza_un_certificado_que_no_corresponde_a_lo_aprobado(self):
        """Segundo candado: ni con el usuario de emisión entra un certificado con otras toneladas."""
        m = self.aprobada
        contenido = vc.firmar({"codigo": "VA-2026-I-PRUEBA22", "finca": "F-001", "parcela": "P-1", "periodo": "2026-I",
                               "toneladas_co2": "999.000", "emitido_en": "2026-11-13T00:00:00Z", "aprobado_por": "x",
                               "reemplaza": None}, self.clave)
        with como("va_emision"), self.assertRaisesMessage(DatabaseError, "C4"), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO negocio_certificado (id, codigo, medicion_id, parcela_id, periodo_id, toneladas_co2, estado,
                       emitido_en, contenido, firma, clave_id)
                   VALUES (gen_random_uuid(), %s, %s, %s, %s, 999, 'vigente', now(), %s::jsonb, %s, %s)""",
                [contenido["contenido"]["codigo"], m.pk, m.parcela_id, m.periodo_id,
                 vc.canonico(contenido["contenido"]).decode(), contenido["firma"], contenido["contenido"]["clave_id"]],
            )

    def test_nadie_mas_emite_ni_cambia_el_contenido(self):
        codigo = self._emitir(self.aprobada)["codigo"]
        with como("va_app"), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE negocio_certificado SET estado = 'revocado', revocado_en = now() WHERE codigo = %s", [codigo])
        with como("va_emision"), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE negocio_certificado SET toneladas_co2 = 1 WHERE codigo = %s", [codigo])
        with como("va_emision"), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM negocio_certificado WHERE codigo = %s", [codigo])

    # 6.5, T-25 ----------------------------------------------------------------------------------

    def _enmienda_autorizada(self, toneladas):
        """Una enmienda que pasó los cuatro pasos con personas distintas; los disparadores de C8 y
        C10 revisan cada paso."""
        u = {n: Usuario.objects.get(username=n) for n in ("tec.ana", "ver.diego", "ver.carla", "ger.gabriela")}
        m, anterior = self.aprobada, self.aprobada.version_vigente
        e = Enmienda.objects.create(medicion=m, solicitada_por=u["ver.diego"], motivo="Error de digitación",
                                    evidencia="Hoja de campo", responsable=u["tec.ana"])
        version = VersionMedicion.objects.create(
            medicion=m, numero=anterior.numero + 1, autor=u["tec.ana"], fecha_medicion=date(2026, 3, 18),
            arboles=anterior.arboles, dap_promedio_cm=anterior.dap_promedio_cm, altura_promedio_m=anterior.altura_promedio_m,
            toneladas_co2=toneladas, es_propuesta=True, enmienda=e)
        Enmienda.objects.filter(pk=e.pk).update(estado="corregida", corregida_por=u["tec.ana"], material=toneladas != anterior.toneladas_co2)
        Enmienda.objects.filter(pk=e.pk).update(estado="revisada", revisada_por=u["ver.carla"], dictamen_favorable=True)
        Enmienda.objects.filter(pk=e.pk).update(estado="autorizada", autorizada_por=u["ger.gabriela"], comercializado=False)
        Medicion.objects.filter(pk=m.pk).update(version_vigente=version)
        return e

    def test_t25_una_enmienda_que_cambia_toneladas_revoca_y_reemite(self):
        original = self._emitir(self.aprobada)
        e = self._enmienda_autorizada(Decimal("15.000"))
        with como("va_emision") as conexion:
            resultado = emitir.reemitir(conexion, e.pk, self.clave)
        self.assertEqual(resultado["resultado"], "reemitido")
        viejo = Certificado.objects.get(codigo=original["codigo"])
        nuevo = Certificado.objects.get(codigo=resultado["codigo"])
        self.assertEqual((viejo.estado, nuevo.estado), ("revocado", "vigente"))
        self.assertIsNotNone(viejo.revocado_en)
        self.assertEqual(nuevo.reemplaza, viejo)
        self.assertEqual(nuevo.toneladas_co2, Decimal("15.000"))
        self.assertEqual(nuevo.contenido["reemplaza"], viejo.codigo)
        self.assertEqual(nuevo.contenido["aprobado_por"], Usuario.objects.get(username="ger.gabriela").get_full_name())
        self.assertIn(e, nuevo.enmiendas_anotadas.all())
        # Ninguno se borra, y la segunda llamada no hace nada nuevo.
        with como("va_emision") as conexion:
            self.assertEqual(emitir.reemitir(conexion, e.pk, self.clave)["resultado"], "anotada")
        self.assertEqual(Certificado.objects.filter(medicion=self.aprobada).count(), 2)

    def test_una_enmienda_que_no_cambia_toneladas_solo_se_anota(self):
        original = self._emitir(self.aprobada)
        e = self._enmienda_autorizada(self.aprobada.version_vigente.toneladas_co2)
        with como("va_emision") as conexion:
            resultado = emitir.reemitir(conexion, e.pk, self.clave)
        self.assertEqual(resultado, {"resultado": "anotada", "codigo": original["codigo"]})
        self.assertIn(e, Certificado.objects.get(codigo=original["codigo"]).enmiendas_anotadas.all())

    def test_los_pendientes_se_emiten_en_el_trabajo_diario(self):
        with como("va_emision") as conexion:
            hechos = emitir.emitir_pendientes(conexion, self.clave)
        self.assertEqual(len(hechos["emitidos"]), Medicion.objects.filter(estado="aprobada").count())
        with como("va_emision") as conexion:
            self.assertEqual(emitir.emitir_pendientes(conexion, self.clave)["emitidos"], [])

    # 6.10 -----------------------------------------------------------------------------------------

    def test_el_sello_de_una_exportacion_se_verifica_con_la_clave(self):
        paquete = {"objeto": "fincas", "filas": [1, 2, 3]}
        with como("va_emision") as conexion:
            sello = emitir.sellar(conexion, vc.huella_de(paquete), "fincas", self.clave)
        self.assertTrue(vc.verificar_sello(paquete, sello, self.clave.public_key())["valido"])
        with como("va_emision") as conexion, self.assertRaises(emitir.NoSeEmite):
            emitir.sellar(conexion, "no es una huella", "fincas", self.clave)

    # C20, T-32 ------------------------------------------------------------------------------------

    def test_t32_el_publico_comprueba_por_codigo_exacto_y_nada_mas(self):
        original = self._emitir(self.aprobada)
        e = self._enmienda_autorizada(Decimal("15.000"))
        with como("va_emision") as conexion:
            reemplazo = emitir.reemitir(conexion, e.pk, self.clave)
        toneladas = Certificado.objects.get(codigo=original["codigo"]).toneladas_co2
        with como("va_publico"), connection.cursor() as cursor:
            cursor.execute("SELECT estado, toneladas_co2, periodo, reemplazado_por FROM va_comprobar(%s)", [original["codigo"]])
            self.assertEqual(cursor.fetchone(), ("revocado", toneladas, "2026-I", reemplazo["codigo"]))
            cursor.execute("SELECT count(*) FROM va_comprobar(%s)", ["VA-2026-I-%"])
            self.assertEqual(cursor.fetchone()[0], 0)
        with como("va_publico"), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT codigo FROM negocio_certificado")


# --- La aplicación con el servicio de emisión (6.3, 6.5, 6.10) ------------------------------------


@skipUnless(emitir is not None and _opa_disponible(), "requiere emision/ y el motor real (OPA)")
class LaAplicacionPideAlServicio(TestCase):
    """La aplicación no firma: pide al servicio después de confirmar la transacción. Aquí el
    servicio HTTP se reemplaza por el código real de emision/ corriendo como va_emision."""

    @classmethod
    def setUpTestData(cls):
        with mock.patch.dict(os.environ, {"SEMILLA_CONTRASENA": "Clave-local-de-pruebas-2026"}):
            call_command("sembrar", stdout=io.StringIO())

    def setUp(self):
        self.clave = Ed25519PrivateKey.generate()

    def _como(self, usuario, rol):
        persona = Usuario.objects.get(username=usuario)
        if not Authenticator.objects.filter(user=persona, type=Authenticator.Type.TOTP).exists():
            TOTP.activate(persona, generate_totp_secret())
        self.client.force_login(persona)
        sesion = self.client.session
        sesion.update({"va_rol": rol, "va_inicio": int(time.time()),
                       "account_authentication_methods": [{"method": "mfa", "at": time.time(), "type": "totp"}],
                       _AUTHENTICATION_METHODS_USER_SESSION_KEY: str(persona.pk)})
        sesion.save()
        return persona

    def _servicio(self, ruta, datos):
        """Lo que haría verdeazul-emision con esa petición."""
        with como("va_emision") as conexion:
            if ruta == "/emitir":
                return 201, emitir.emitir(conexion, datos["medicion"], self.clave)
            if ruta == "/reemitir":
                return 200, emitir.reemitir(conexion, datos["enmienda"], self.clave)
            return 200, {"sello": emitir.sellar(conexion, datos["huella"], datos["objeto"], self.clave)}

    def _enviada(self):
        return Medicion.objects.get(parcela__finca__codigo="F-001", parcela__codigo="P-1", periodo__nombre="2026-II")

    def test_aprobar_una_medicion_emite_su_certificado(self):
        self._como("ver.diego", "VER")
        enviada = self._enviada()
        with mock.patch("nucleo.emision.llamar", side_effect=self._servicio) as llamar, \
                self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse("aprobar_medicion", args=[enviada.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 302)
        llamar.assert_called_once_with("/emitir", {"medicion": str(enviada.pk)})
        c = Certificado.objects.get(medicion=enviada, estado="vigente")
        self.assertTrue(vc.verificar({"contenido": c.contenido, "firma": c.firma}, self.clave.public_key())["valido"])

    def test_si_el_servicio_no_responde_la_aprobacion_queda_igual(self):
        self._como("ver.diego", "VER")
        enviada = self._enviada()
        with self.captureOnCommitCallbacks(execute=True):  # sin EMISION_URL
            respuesta = self.client.post(reverse("aprobar_medicion", args=[enviada.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 302)
        enviada.refresh_from_db()
        self.assertEqual(enviada.estado, "aprobada")
        self.assertFalse(Certificado.objects.filter(medicion=enviada).exists())  # lo recupera el trabajo diario

    def test_t31_el_paquete_del_auditor_sale_sellado_y_se_verifica(self):
        self._como("aud.elena", "AUD")
        with mock.patch("nucleo.emision.llamar", side_effect=self._servicio):
            respuesta = self.client.get(reverse("exportar_fincas"), MOTIVO)
        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.content.decode()
        resultado = vc.verificar_archivo(texto, self.clave.public_key())
        self.assertTrue(resultado["valido"], resultado["motivo"])
        self.assertEqual(json.loads(texto)["sello"]["huella_sha256"], respuesta["X-Verdeazul-Huella"])
        alterado = texto.replace('"F-001"', '"F-999"', 1)
        self.assertFalse(vc.verificar_archivo(alterado, self.clave.public_key())["valido"])

    def test_sin_sello_no_se_entrega_el_paquete(self):
        self._como("aud.elena", "AUD")
        respuesta = self.client.get(reverse("exportar_fincas"), MOTIVO)  # sin EMISION_URL
        self.assertEqual(respuesta.status_code, 503)
        self.assertFalse(ExportacionAuditoria.objects.exists())
        self.assertTrue(Registro.objects.filter(accion="exportar", resultado="denegado", regla__startswith="C18").exists())

    def test_quien_lee_el_certificado_descarga_el_archivo_firmado(self):
        aprobada = Medicion.objects.get(parcela__finca__codigo="F-001", parcela__codigo="P-1", periodo__nombre="2026-I")
        with como("va_emision") as conexion:
            codigo = emitir.emitir(conexion, aprobada.pk, self.clave)["codigo"]
        c = Certificado.objects.get(codigo=codigo)
        self._como("ger.gabriela", "GER")
        with self.settings(PUBLICO_URL="https://publico.ejemplo"):
            ficha = self.client.get(reverse("certificado", args=[c.pk]), MOTIVO)
        self.assertContains(ficha, f"https://publico.ejemplo/comprobar?codigo={codigo}")
        respuesta = self.client.get(reverse("descargar_certificado", args=[c.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(f'filename="{codigo}.json"', respuesta["Content-Disposition"])
        self.assertTrue(vc.verificar_archivo(respuesta.content.decode(), self.clave.public_key())["valido"])
        # Un dueño sin relación con esa finca no lo ve (C5).
        self._como("due.rosa", "DUE")
        self.assertEqual(self.client.get(reverse("descargar_certificado", args=[c.pk])).status_code, 404)

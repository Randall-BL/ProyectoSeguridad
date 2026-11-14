"""Pruebas del trabajo diario (fase 7) contra la base, con el usuario va_trabajos real: lo que el
trabajo hace y que no puede hacer más que eso. La TSA se reemplaza; el cliente RFC 3161 se prueba
en trabajos/test_tsa.py y contra las TSA reales en el despliegue."""

import io
import os
import sys
from datetime import timedelta
from pathlib import Path
from unittest import mock, skipUnless

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from bitacora.models import Registro, Testigo
from cuentas.models import Sesion, Usuario
from flujos.tests_certificados import como
from negocio.models import Alerta, Asignacion

RAIZ = Path(settings.BASE_DIR).parent
if (RAIZ / "trabajos").exists() and str(RAIZ / "trabajos") not in sys.path:
    sys.path.insert(0, str(RAIZ / "trabajos"))
try:
    import diario
except ImportError:  # pragma: no cover - imagen de producción
    diario = None


@skipUnless(diario is not None, "trabajos/ no está junto a la aplicación")
class TrabajoDiario(TestCase):
    @classmethod
    def setUpTestData(cls):
        with mock.patch.dict(os.environ, {"SEMILLA_CONTRASENA": "Clave-local-de-pruebas-2026"}):
            call_command("sembrar", stdout=io.StringIO())

    def _paso(self, paso):
        with como("va_trabajos") as conexion, conexion.transaction(), conexion.cursor() as cur:
            return paso(cur)

    def _sesion(self, usuario):
        return Sesion.objects.create(session_key=f"s{usuario.pk.hex[:30]}", session_data="", usuario=usuario,
                                     expire_date=timezone.now() + timedelta(hours=1))

    def test_vencen_las_temporales_y_se_cierran_las_sesiones_del_tecnico(self):
        ana = Usuario.objects.get(username="tec.ana")
        self._sesion(ana)
        vencida = Asignacion.objects.get(tecnico=ana, tipo="temporal", finca__codigo="F-002")
        resultado = self._paso(diario.vencer_temporales)
        self.assertEqual(resultado, {"temporales": 1, "sesiones": 1})
        vencida.refresh_from_db()
        self.assertIsNotNone(vencida.terminada_en)
        self.assertFalse(Sesion.objects.filter(usuario=ana).exists())
        self.assertTrue(Registro.objects.filter(accion="vencer", objeto_id=str(vencida.pk), rol="SIS", regla="C19").exists())
        self.assertEqual(self._paso(diario.vencer_temporales), {"temporales": 0, "sesiones": 0})  # una sola vez

    def test_t09_la_ventana_vencida_y_45_dias_sin_uso_dan_de_baja(self):
        elena = Usuario.objects.get(username="aud.elena")
        Usuario.objects.filter(pk=elena.pk).update(vigente_hasta=timezone.now() - timedelta(minutes=1))
        tomas = Usuario.objects.get(username="tec.tomas")
        Usuario.objects.filter(pk=tomas.pk).update(last_login=timezone.now() - timedelta(days=46))
        self._sesion(elena)
        resultado = self._paso(diario.bajas)
        self.assertEqual((resultado["auditores"], resultado["sin_uso"], resultado["sesiones"]), (1, 1, 1))
        self.assertFalse(Usuario.objects.get(pk=elena.pk).is_active)
        self.assertFalse(Usuario.objects.get(pk=tomas.pk).is_active)
        self.assertTrue(Usuario.objects.get(username="tec.ana").is_active)
        self.assertTrue(Registro.objects.filter(accion="desactivar", objeto_id=str(tomas.pk), regla="POL-CA-06").exists())

    def test_las_sesiones_expiradas_se_borran(self):
        ana = Usuario.objects.get(username="tec.ana")
        Sesion.objects.filter(pk=self._sesion(ana).pk).update(expire_date=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._paso(diario.sesiones_expiradas), {"sesiones_expiradas": 1})

    def test_c15_una_alerta_sin_resolver_en_dos_dias_habiles_se_escala(self):
        ana = Usuario.objects.get(username="tec.ana")
        vieja = Alerta.objects.create(sujeto=ana, control="H1", nivel="aviso")
        nueva = Alerta.objects.create(sujeto=ana, control="H1", nivel="aviso")
        Alerta.objects.filter(pk=vieja.pk).update(creada_en=timezone.now() - timedelta(days=7))
        self.assertEqual(self._paso(diario.escalar_alertas), {"escaladas": 1})
        self.assertIsNotNone(Alerta.objects.get(pk=vieja.pk).escalada_en)
        self.assertIsNone(Alerta.objects.get(pk=nueva.pk).escalada_en)
        self.assertTrue(Registro.objects.filter(accion="escalar", objeto_id=str(vieja.pk), regla="C15").exists())

    def test_la_cadena_integra_y_el_testigo_externo(self):
        self.assertTrue(self._paso(diario.verificar_cadena)["integra"])
        with mock.patch.object(diario.tsa, "sellar", return_value=b"\x30\x03\x02\x01\x00"):
            resultado = self._paso(diario.testigo)
        t = Testigo.objects.get(pk=resultado["testigo"])
        ultimo = Registro.objects.get(pk=t.registro)
        self.assertEqual(t.huella, ultimo.huella)
        self.assertTrue(Registro.objects.filter(accion="testigo", objeto_id=str(t.registro)).exists())

    def test_si_ninguna_tsa_responde_el_paso_falla_sin_guardar(self):
        with mock.patch.object(diario.tsa, "sellar", side_effect=OSError("sin red")), \
                mock.patch.dict(os.environ, {"TSA_URLS": "http://uno,http://dos"}), \
                self.assertRaisesRegex(RuntimeError, "Ninguna TSA"):
            self._paso(diario.testigo)
        self.assertFalse(Testigo.objects.exists())

    def test_el_trabajo_completo_termina_bien_y_un_paso_que_falla_no_frena_los_demas(self):
        with mock.patch.object(diario.tsa, "sellar", return_value=b"\x30\x03\x02\x01\x00"), como("va_trabajos") as conexion:
            resumen, bien = diario.correr(conexion)
        self.assertTrue(bien, resumen)
        self.assertEqual(resumen["emisiones_pendientes"], {"omitido": "sin EMISION_URL"})
        with mock.patch.object(diario.tsa, "sellar", side_effect=OSError("sin red")), como("va_trabajos") as conexion:
            resumen, bien = diario.correr(conexion)
        self.assertFalse(bien)
        self.assertIn("error", resumen["testigo"])
        self.assertTrue(resumen["verificar_cadena"]["integra"])

    def test_va_trabajos_no_puede_mas_que_eso(self):
        for sql in ("UPDATE cuentas_usuario SET rol = 'GER'", "DELETE FROM negocio_asignacion",
                    "UPDATE negocio_alerta SET resuelta_en = now()", "SELECT * FROM negocio_datospersonales",
                    "UPDATE bitacora_testigo SET huella = 'x'", "INSERT INTO negocio_certificado (id) VALUES (gen_random_uuid())"):
            with self.subTest(sql=sql), como("va_trabajos"), self.assertRaises(DatabaseError), \
                    transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)

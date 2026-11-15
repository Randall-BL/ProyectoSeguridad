"""8.5, pruebas de sistema de la bitácora (las del motor caído, lento o con una respuesta inválida
están en autorizacion.tests.FalloCerrado, T-41):

- si la bitácora no puede escribir, la operación no ocurre (POL-BT-06: sin registro no hay acción);
- nadie modifica ni borra un registro, ni el dueño de la tabla (POL-BT-03);
- si alguien con privilegios de superusuario desactiva esa protección y altera un registro, la
  cadena lo delata: bitacora_verificar(), la pantalla de GER y AUD, y el trabajo diario."""

import io
import os
import sys
from pathlib import Path
from unittest import mock, skipUnless

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from bitacora.models import Registro
from bitacora.registro import anexar, verificar_cadena
from flujos.tests import MOTIVO, _opa_disponible
from flujos.tests_casos import ConPersonajes
from negocio.models import Medicion

RAIZ = Path(settings.BASE_DIR).parent
if (RAIZ / "trabajos").exists() and str(RAIZ / "trabajos") not in sys.path:
    sys.path.insert(0, str(RAIZ / "trabajos"))
try:
    import diario
except ImportError:  # pragma: no cover - imagen de producción
    diario = None


def _sql(texto):
    with connection.cursor() as cursor:
        cursor.execute(texto)


class CadenaDeLaBitacora(ConPersonajes):
    @classmethod
    def setUpTestData(cls):
        with mock.patch.dict(os.environ, {"SEMILLA_CONTRASENA": "Clave-local-de-pruebas-2026"}):
            call_command("sembrar", stdout=io.StringIO())
        for numero in range(3):
            anexar(accion="prueba", resultado="concedido", objeto_tipo="prueba", objeto_id=str(numero))

    def test_la_cadena_de_la_semilla_esta_integra(self):
        self.assertIsNone(verificar_cadena())

    def test_nadie_modifica_ni_borra_un_registro_ni_el_dueno(self):
        for sql in ("UPDATE bitacora_registro SET accion = 'otra' WHERE id = (SELECT min(id) FROM bitacora_registro)",
                    "DELETE FROM bitacora_registro WHERE id = (SELECT max(id) FROM bitacora_registro)",
                    "TRUNCATE bitacora_registro"):
            with self.subTest(sql=sql), self.assertRaisesMessage(DatabaseError, "POL-BT-03"), transaction.atomic():
                _sql(sql)

    def test_un_registro_alterado_rompe_la_cadena_y_se_ve_en_los_tres_lugares(self):
        alterado = Registro.objects.order_by("id")[1]
        # Lo único que lo permite es desactivar el disparador, que exige ser dueño de la tabla.
        _sql("ALTER TABLE bitacora_registro DISABLE TRIGGER bitacora_sin_cambios")
        _sql(f"UPDATE bitacora_registro SET resultado = 'denegado' WHERE id = {alterado.id}")
        _sql("ALTER TABLE bitacora_registro ENABLE TRIGGER bitacora_sin_cambios")
        self.assertEqual(verificar_cadena(), alterado.id)
        if _opa_disponible():  # la pantalla de GER y AUD lo dice
            self._como("ger.gabriela", "GER")
            respuesta = self.client.get(reverse("bitacora"), MOTIVO)
            self.assertContains(respuesta, f"La cadena está rota desde el registro {alterado.id}")
        if diario is not None:  # y el trabajo diario termina con error
            from flujos.tests_certificados import como

            with como("va_trabajos") as conexion, mock.patch.object(diario.tsa, "sellar", return_value=b"0"):
                resumen, bien = diario.correr(conexion, [("verificar_cadena", diario.verificar_cadena)])
            self.assertFalse(bien)
            self.assertEqual(resumen["verificar_cadena"]["primer_registro_alterado"], alterado.id)


@skipUnless(_opa_disponible(), "requiere el motor real (OPA) en OPA_URL")
class SinBitacoraNoHayAccion(ConPersonajes):
    def test_si_la_bitacora_no_escribe_la_aprobacion_no_ocurre(self):
        self._como("ver.diego", "VER")
        m = self._medicion("F-001", "P-1", "2026-II")
        antes = Registro.objects.count()
        # La bitácora deja de aceptar registros (como si su función fallara), solo en esta transacción.
        _sql("""CREATE FUNCTION pg_temp.sin_bitacora() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'la bitácora no está disponible'; END $$""")
        _sql("CREATE TRIGGER sin_bitacora BEFORE INSERT ON bitacora_registro "
             "FOR EACH ROW EXECUTE FUNCTION pg_temp.sin_bitacora()")
        self.client.raise_request_exception = False
        respuesta = self.client.post(reverse("aprobar_medicion", args=[m.pk]), MOTIVO)
        self.assertNotEqual(respuesta.status_code, 302)
        _sql("DROP TRIGGER sin_bitacora ON bitacora_registro")
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "enviada")
        self.assertIsNone(Medicion.objects.get(pk=m.pk).aprobada_por)
        self.assertEqual(Registro.objects.count(), antes)

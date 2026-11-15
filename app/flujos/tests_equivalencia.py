"""8.4 (RR-10): cada regla que vive en dos lugares, el motor (OPA) y la base (seguridad por fila,
disparadores y restricciones), decide lo mismo. Cada prueba hace el mismo intento dos veces:

- por la ruta, con el motor real: tiene que denegar con la regla de la Parte 1;
- directo en la base como va_app, con el rol puesto, sin pasar por el motor: el segundo candado
  tiene que rechazarlo por su cuenta, con la misma regla en el mensaje.

Si un día una copia cambia y la otra no, alguna de las dos mitades falla. Así se encontró que la
seguridad por fila y el disparador de C19 usaban la fecha UTC y el motor la de Costa Rica
(negocio/sql/0007)."""

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless

from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Usuario
from flujos.tests import MOTIVO, _opa_disponible
from flujos.tests_casos import ConPersonajes
from flujos.tests_certificados import como, emitir
from negocio.models import (
    Alerta,
    Asignacion,
    DatosPersonales,
    Enmienda,
    Finca,
    Medicion,
    Periodo,
)

if emitir is not None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@contextmanager
def en_la_base(usuario, rol):
    """Como la aplicación, pero sin el motor: va_app con quién pide y su rol, local a la transacción."""
    with como("va_app"):
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.usuario', %s, true), set_config('app.rol', %s, true)",
                           [str(usuario.pk), rol])
        yield


@skipUnless(_opa_disponible(), "requiere el motor real (OPA) en OPA_URL")
class LasDosCopiasDecidenLoMismo(ConPersonajes):
    def _rechaza(self, usuario, rol, regla, sql, parametros):
        persona = Usuario.objects.get(username=usuario)
        with en_la_base(persona, rol), self.assertRaisesMessage(DatabaseError, regla), \
                transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, parametros)

    def _filas(self, usuario, rol, sql, parametros):
        with en_la_base(Usuario.objects.get(username=usuario), rol), connection.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()

    def _denegada(self, respuesta, regla):
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), regla)

    # C1 y C5: el alcance por finca ---------------------------------------------------------------------

    def test_c1_el_tecnico_fuera_de_sus_fincas(self):
        self._como("tec.ana", "TEC")
        f002 = Finca.objects.get(codigo="F-002")
        self.assertEqual(self.client.get(reverse("finca", args=[f002.pk]), MOTIVO).status_code, 404)
        self.assertEqual(self._filas("tec.ana", "TEC", "SELECT id FROM negocio_finca WHERE codigo = 'F-002'", []), [])
        self.assertEqual(len(self._filas("tec.ana", "TEC", "SELECT id FROM negocio_finca WHERE codigo = 'F-001'", [])), 1)

    def test_c5_el_dueno_fuera_de_su_titular(self):
        self._como("due.daniel", "DUE")
        f002 = Finca.objects.get(codigo="F-002")
        self.assertEqual(self.client.get(reverse("finca", args=[f002.pk])).status_code, 404)
        self.assertEqual(self._filas("due.daniel", "DUE", "SELECT id FROM negocio_finca WHERE codigo = 'F-002'", []), [])

    def test_c1_la_temporal_que_vence_hoy_vale_hasta_la_medianoche_de_costa_rica_en_las_dos(self):
        """Antes de negocio/sql/0007 la base usaba la fecha de la zona de la sesión. Con dos zonas en
        extremos opuestos, a cualquier hora del día la fecha de una de ellas no es la de Costa Rica."""
        ana = Usuario.objects.get(username="tec.ana")
        with connection.cursor() as cursor:
            cursor.execute("SELECT va_hoy()")
            hoy_cr = cursor.fetchone()[0]
        f025 = Finca.objects.get(codigo="F-025")
        Asignacion.objects.create(tecnico=ana, finca=f025, periodo=Periodo.objects.get(nombre="2026-II"),
                                  tipo="temporal", motivo="Cubrir una ausencia", desde=hoy_cr - timedelta(days=2),
                                  hasta=hoy_cr, creada_por=Usuario.objects.get(username="sup.sofia"))
        for zona in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):
            with self.subTest(zona=zona), en_la_base(ana, "TEC"), connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL TIME ZONE '{zona}'")
                cursor.execute("SELECT count(*) FROM negocio_finca WHERE id = %s", [f025.pk])
                self.assertEqual(cursor.fetchone()[0], 1, "la base ya no ve la finca y el motor sí")
                cursor.execute("SELECT va_hechos_sujeto(%s, 'TEC', NULL)->'fincas_asignadas' ? %s", [ana.pk, str(f025.pk)])
                self.assertTrue(cursor.fetchone()[0])
                cursor.execute("SET LOCAL TIME ZONE 'UTC'")

    # C2 y C14: lo que se registra y cuándo -------------------------------------------------------------

    def test_c2_c14_no_se_registra_en_un_periodo_cerrado(self):
        self._como("tec.ana", "TEC")
        m = self._medicion("F-001", "P-1", "2026-I")  # período cerrado
        v = m.version_vigente
        respuesta = self.client.post(reverse("modificar_medicion", args=[m.pk]), {
            **MOTIVO, "fecha_medicion": v.fecha_medicion.isoformat(), "arboles": v.arboles,
            "dap_promedio_cm": v.dap_promedio_cm, "altura_promedio_m": v.altura_promedio_m, "toneladas_co2": "1.000"})
        self._denegada(respuesta, "C2")
        self._rechaza("tec.ana", "TEC", "C2/C14", """
            INSERT INTO negocio_versionmedicion (id, medicion_id, numero, autor_id, fecha_medicion, fecha_registro,
                arboles, dap_promedio_cm, altura_promedio_m, toneladas_co2, observaciones, es_propuesta, huella_hoja_campo)
            VALUES (gen_random_uuid(), %s, 99, %s, %s, now(), 1, 1, 1, 1, '', false, '')""",
            [m.pk, Usuario.objects.get(username="tec.ana").pk, v.fecha_medicion])

    def test_c2_la_fecha_de_medicion_no_es_futura(self):
        self._como("tec.ana", "TEC")
        m = self._medicion("F-001", "P-2", "2026-II")  # borrador de A en un período abierto
        v = m.version_vigente
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        respuesta = self.client.post(reverse("modificar_medicion", args=[m.pk]), {
            **MOTIVO, "fecha_medicion": manana, "arboles": v.arboles, "dap_promedio_cm": v.dap_promedio_cm,
            "altura_promedio_m": v.altura_promedio_m, "toneladas_co2": v.toneladas_co2})
        self.assertNotEqual(respuesta.status_code, 302)
        self._rechaza("tec.ana", "TEC", "fecha_medicion_no_posterior_al_registro", """
            INSERT INTO negocio_versionmedicion (id, medicion_id, numero, autor_id, fecha_medicion, fecha_registro,
                arboles, dap_promedio_cm, altura_promedio_m, toneladas_co2, observaciones, es_propuesta, huella_hoja_campo)
            VALUES (gen_random_uuid(), %s, 99, %s, now()::date + 1, now(), 1, 1, 1, 1, '', false, '')""",
            [m.pk, Usuario.objects.get(username="tec.ana").pk])

    # C3: quien registró no aprueba -------------------------------------------------------------------

    def test_c3_quien_escribio_una_version_no_aprueba(self):
        self._como("ver.carla", "VER")
        m = self._medicion("F-003", "P-1", "2026-II")
        self._denegada(self.client.post(reverse("aprobar_medicion", args=[m.pk]), MOTIVO), "C3")
        carla = Usuario.objects.get(username="ver.carla")
        self._rechaza("ver.carla", "VER", "C3",
                      "UPDATE negocio_medicion SET estado = 'aprobada', aprobada_por_id = %s, aprobada_en = now() WHERE id = %s",
                      [carla.pk, m.pk])

    # C8 y C10: la enmienda independiente -------------------------------------------------------------

    def test_c10_en_una_enmienda_material_no_revisa_quien_aprobo(self):
        e = self._solicitar("ger.gabriela", "GER")
        self.assertEqual(self._corregir(e, "15.000").status_code, 302)
        self._denegada(self._revisar(e, "ver.bruno"), "C10")
        bruno = Usuario.objects.get(username="ver.bruno")
        self._rechaza("ver.bruno", "VER", "C10",
                      "UPDATE negocio_enmienda SET estado = 'revisada', revisada_por_id = %s, dictamen_favorable = true WHERE id = %s",
                      [bruno.pk, e.pk])

    def test_c8_quien_solicito_no_autoriza(self):
        e = self._solicitar("ger.gabriela", "GER")
        self.assertEqual(self._corregir(e, "15.000").status_code, 302)
        self.assertEqual(self._revisar(e, "ver.carla").status_code, 302)
        self._denegada(self._autorizar(e, "ger.gabriela"), "C8")
        gabriela = Usuario.objects.get(username="ger.gabriela")
        self._rechaza("ger.gabriela", "GER", "C8",
                      "UPDATE negocio_enmienda SET estado = 'autorizada', autorizada_por_id = %s WHERE id = %s",
                      [gabriela.pk, e.pk])
        self.assertEqual(Enmienda.objects.get(pk=e.pk).estado, "revisada")

    # C15: nadie resuelve su propia alerta -------------------------------------------------------------

    def test_c15_nadie_resuelve_una_alerta_sobre_si_mismo(self):
        sofia = self._como("sup.sofia", "SUP")
        propia = Alerta.objects.create(sujeto=sofia, control="H1", nivel="aviso")
        self.assertEqual(self.client.post(reverse("resolver_alerta", args=[propia.pk]),
                                          {**MOTIVO, "resolucion": "x"}).status_code, 403)
        self._rechaza("sup.sofia", "SUP", "nadie_resuelve_su_propia_alerta",
                      "UPDATE negocio_alerta SET resuelta_por_id = %s, resuelta_en = now() WHERE id = %s",
                      [sofia.pk, propia.pk])

    # C16: lo que hay que conservar --------------------------------------------------------------------

    def test_c16_no_se_suprimen_los_datos_de_un_titular_con_certificado(self):
        if emitir is None:
            self.skipTest("emision/ no está junto a la aplicación")
        m = self._medicion("F-001", "P-1", "2026-I")
        with como("va_emision") as conexion:
            emitir.emitir(conexion, m.pk, Ed25519PrivateKey.generate())
        titular = m.parcela.finca.titular
        self._como("adm.alberto", "ADM")
        self._denegada(self.client.post(reverse("suprimir_titular", args=[titular.pk]), MOTIVO), "C16")
        self._rechaza("adm.alberto", "ADM", "C16",
                      "UPDATE negocio_datospersonales SET suprimido_en = now() WHERE titular_id = %s", [titular.pk])
        self.assertIsNone(DatosPersonales.objects.get(titular=titular).suprimido_en)

    # C19 y K-1: asignaciones -------------------------------------------------------------------------

    def test_k1_la_asignacion_numero_21(self):
        self._como("sup.sofia", "SUP")
        tomas = Usuario.objects.get(username="tec.tomas")
        f025, ii = Finca.objects.get(codigo="F-025"), Periodo.objects.get(nombre="2026-II")
        respuesta = self.client.post(reverse("crear_asignacion"), {
            **MOTIVO, "tecnico": tomas.pk, "finca": f025.pk, "periodo": ii.pk, "tipo": "ordinaria"})
        self._denegada(respuesta, "C19")
        self._rechaza("sup.sofia", "SUP", "K-1", """
            INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, creada_por_id, creada_en)
            VALUES (gen_random_uuid(), %s, %s, %s, 'ordinaria', '', now()::date, %s, now())""",
            [tomas.pk, f025.pk, ii.pk, Usuario.objects.get(username="sup.sofia").pk])

    def test_c19_solo_a_quien_tiene_el_rol_tec_vigente(self):
        self._como("sup.sofia", "SUP")
        diego = Usuario.objects.get(username="ver.diego")  # verificador sin habilitación
        f025, ii = Finca.objects.get(codigo="F-025"), Periodo.objects.get(nombre="2026-II")
        respuesta = self.client.post(reverse("crear_asignacion"), {
            **MOTIVO, "tecnico": diego.pk, "finca": f025.pk, "periodo": ii.pk, "tipo": "ordinaria"})
        self.assertNotEqual(respuesta.status_code, 302)
        self._rechaza("sup.sofia", "SUP", "C19", """
            INSERT INTO negocio_asignacion (id, tecnico_id, finca_id, periodo_id, tipo, motivo, desde, creada_por_id, creada_en)
            VALUES (gen_random_uuid(), %s, %s, %s, 'ordinaria', '', now()::date, %s, now())""",
            [diego.pk, f025.pk, ii.pk, Usuario.objects.get(username="sup.sofia").pk])

    def test_c19_con_habilitacion_vigente_si_en_las_dos(self):
        """C, verificadora con habilitación de técnica (T-26): el motor y la base la aceptan."""
        self._como("sup.sofia", "SUP")
        carla = Usuario.objects.get(username="ver.carla")
        f025, ii = Finca.objects.get(codigo="F-025"), Periodo.objects.get(nombre="2026-II")
        respuesta = self.client.post(reverse("crear_asignacion"), {
            **MOTIVO, "tecnico": carla.pk, "finca": f025.pk, "periodo": ii.pk, "tipo": "ordinaria"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Asignacion.objects.filter(tecnico=carla, finca=f025).exists())

    # El certificado: C4 -----------------------------------------------------------------------------

    def test_c4_la_aplicacion_no_emite(self):
        """En la matriz solo SIS emite; en la base va_app no tiene INSERT sobre certificados."""
        m = self._medicion("F-001", "P-1", "2026-I")
        self._rechaza("ger.gabriela", "GER", "permission denied", """
            INSERT INTO negocio_certificado (id, codigo, medicion_id, parcela_id, periodo_id, toneladas_co2, estado,
                emitido_en, contenido, firma, clave_id)
            VALUES (gen_random_uuid(), 'VA-X', %s, %s, %s, %s, 'vigente', now(), '{}', '', '')""",
            [m.pk, m.parcela_id, m.periodo_id, Decimal("1")])
        self.assertEqual(Medicion.objects.get(pk=m.pk).certificados.count(), 0)

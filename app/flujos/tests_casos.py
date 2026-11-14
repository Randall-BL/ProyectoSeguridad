"""Casos T de la Parte 1 que faltaban de punta a punta (8.1): por las rutas, con el motor real
(OPA), los disparadores de la base y, para T-25, el código del servicio de emisión corriendo como
va_emision. Fuera de la jornada (H2) las decisiones piden motivo: se envía uno.

Las enmiendas siguen los cuatro pasos con personas distintas sobre la medición de F-001 P-1 del
período 2026-I, que registró A (tec.ana) y aprobó B (ver.bruno)."""

import io
import json
import os
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock, skipUnless

from allauth.account.internal.flows.login import _AUTHENTICATION_METHODS_USER_SESSION_KEY
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Usuario
from flujos.tests import MATRIZ, MOTIVO, _opa_disponible, _rutas
from flujos.tests_certificados import como, emitir
from negocio.models import Asignacion, Certificado, Enmienda, Finca, Medicion, Parcela, Periodo, PropuestaPeriodo

if emitir is not None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    import verdeazul_certificado as vc


class ConPersonajes(TestCase):
    """La semilla y la entrada de cada personaje con el segundo factor reciente. Sin pruebas propias."""

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
        sesion.update({"va_rol": rol, "va_inicio": int(time.time()),
                       "account_authentication_methods": [{"method": "mfa", "at": time.time(), "type": "totp"}],
                       _AUTHENTICATION_METHODS_USER_SESSION_KEY: str(persona.pk)})
        sesion.save()
        return persona

    def _regla(self, respuesta):
        return respuesta.context["regla"] if respuesta.context and "regla" in respuesta.context else None


@skipUnless(_opa_disponible(), "requiere el motor real (OPA) en OPA_URL")
class CasosQueFaltaban(ConPersonajes):
    def _medicion(self, finca="F-001", parcela="P-1", periodo="2026-I"):
        return Medicion.objects.get(parcela__finca__codigo=finca, parcela__codigo=parcela, periodo__nombre=periodo)

    def _solicitar(self, quien, rol, medicion=None):
        self._como(quien, rol)
        m = medicion or self._medicion()
        self.client.post(reverse("solicitar_enmienda", args=[m.pk]), {
            **MOTIVO, "motivo": "Error al digitar el DAP", "evidencia": "Hoja de campo escaneada",
            "responsable": Usuario.objects.get(username="tec.ana").pk})
        return Enmienda.objects.filter(medicion=m).latest("solicitada_en")

    def _corregir(self, enmienda, toneladas):
        self._como("tec.ana", "TEC")
        v = enmienda.medicion.version_vigente
        return self.client.post(reverse("corregir_enmienda", args=[enmienda.pk]), {
            **MOTIVO, "fecha_medicion": v.fecha_medicion.isoformat(), "arboles": v.arboles,
            "dap_promedio_cm": v.dap_promedio_cm, "altura_promedio_m": v.altura_promedio_m,
            "toneladas_co2": toneladas, "motivo_tardio": "Corrección de una enmienda"})

    def _revisar(self, enmienda, quien):
        self._como(quien, "VER")
        return self.client.post(reverse("revisar_enmienda", args=[enmienda.pk]), {
            **MOTIVO, "dictamen_favorable": "si", "observaciones": "Revisada contra la hoja de campo"})

    def _autorizar(self, enmienda, quien):
        self._como(quien, "GER")
        return self.client.post(reverse("autorizar_enmienda", args=[enmienda.pk]), {**MOTIVO, "comercializado": "no"})

    # C7 a C10 ---------------------------------------------------------------------------------------

    def test_t11_un_tecnico_no_pide_enmienda_de_lo_que_midio_otro(self):
        self._como("tec.tomas", "TEC")
        m = self._medicion()
        respuesta = self.client.post(reverse("solicitar_enmienda", args=[m.pk]), {
            **MOTIVO, "motivo": "x", "evidencia": "x", "responsable": Usuario.objects.get(username="tec.tomas").pk})
        self.assertIn(respuesta.status_code, (403, 404))  # C7, o C1 si ni siquiera ve la finca
        self.assertFalse(Enmienda.objects.filter(medicion=m).exists())

    def test_t13_no_se_corrige_pasados_diez_dias_habiles(self):
        e = self._solicitar("ger.gabriela", "GER")
        Enmienda.objects.filter(pk=e.pk).update(solicitada_en=timezone.now() - timedelta(days=21))
        respuesta = self._corregir(e, "15.000")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C9")
        self.assertEqual(Enmienda.objects.get(pk=e.pk).estado, "solicitada")

    def test_t14_quien_solicito_no_da_el_dictamen(self):
        e = self._solicitar("ver.diego", "VER")
        self.assertEqual(self._corregir(e, self._medicion().version_vigente.toneladas_co2).status_code, 302)
        respuesta = self._revisar(e, "ver.diego")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C10")

    def test_t23_en_una_enmienda_material_quien_aprobo_no_da_el_dictamen(self):
        e = self._solicitar("ger.gabriela", "GER")
        self.assertEqual(self._corregir(e, "15.000").status_code, 302)
        self.assertTrue(Enmienda.objects.get(pk=e.pk).material)
        respuesta = self._revisar(e, "ver.bruno")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C10")

    def test_t24_t12_t25_la_que_solicito_no_autoriza_otra_gerente_si_y_se_reemite(self):
        if emitir is None:
            self.skipTest("emision/ no está junto a la aplicación")
        clave = Ed25519PrivateKey.generate()
        with como("va_emision") as conexion:
            original = emitir.emitir(conexion, self._medicion().pk, clave)["codigo"]

        e = self._solicitar("ger.gabriela", "GER")
        self.assertEqual(self._corregir(e, "15.000").status_code, 302)
        self.assertEqual(self._revisar(e, "ver.carla").status_code, 302)
        # T-24: G solicitó, así que no autoriza (C8).
        respuesta = self._autorizar(e, "ger.gabriela")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C8")

        # T-12: la otra gerente sí. Al confirmar, la aplicación pide la reemisión (T-25).
        def servicio(ruta, datos):
            with como("va_emision") as conexion:
                return 200, emitir.reemitir(conexion, datos["enmienda"], clave)

        with mock.patch("nucleo.emision.llamar", side_effect=servicio) as llamar, \
                self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._autorizar(e, "ger.gerardo").status_code, 302)
        llamar.assert_called_once_with("/reemitir", {"enmienda": str(e.pk)})
        self.assertEqual(Enmienda.objects.get(pk=e.pk).estado, "autorizada")
        viejo = Certificado.objects.get(codigo=original)
        nuevo = Certificado.objects.get(reemplaza=viejo)
        self.assertEqual((viejo.estado, nuevo.estado, nuevo.toneladas_co2), ("revocado", "vigente", Decimal("15.000")))
        self.assertTrue(vc.verificar({"contenido": nuevo.contenido, "firma": nuevo.firma}, clave.public_key())["valido"])

    # C2, C3, C14 --------------------------------------------------------------------------------------

    def test_t17_se_aprueba_despues_del_cierre_lo_enviado_antes(self):
        diego = self._como("ver.diego", "VER")
        pendiente = self._medicion("F-004", "P-1", "2026-I")
        self.assertEqual(self.client.post(reverse("aprobar_medicion", args=[pendiente.pk]), MOTIVO).status_code, 302)
        pendiente.refresh_from_db()
        self.assertEqual((pendiente.estado, pendiente.aprobada_por), ("aprobada", diego))

    def test_t30_no_se_registra_una_fecha_de_medicion_futura(self):
        self._como("tec.ana", "TEC")
        parcela = Parcela.objects.get(finca__codigo="F-004", codigo="P-1", activa=True)
        antes = Medicion.objects.count()
        respuesta = self.client.post(reverse("nueva_medicion", args=[parcela.pk]), {
            **MOTIVO, "fecha_medicion": (timezone.localdate() + timedelta(days=2)).isoformat(), "arboles": 100,
            "dap_promedio_cm": "20.00", "altura_promedio_m": "12.00", "toneladas_co2": "10.000"})
        self.assertNotEqual(respuesta.status_code, 302)
        self.assertEqual(Medicion.objects.count(), antes)

    def test_t04_despues_del_cierre_un_borrador_ya_no_se_modifica(self):
        self._como("adm.alberto", "ADM")
        periodo = Periodo.objects.get(nombre="2026-II")
        self.client.post(reverse("proponer_periodo", args=[periodo.pk]), {"accion": "cerrar"})
        registro = PropuestaPeriodo.objects.get(periodo=periodo, accion="cerrar", estado="propuesto")
        self._como("ger.gerardo", "GER")
        self.client.post(reverse("cerrar_periodo", args=[registro.pk]), MOTIVO)
        borrador = self._medicion("F-001", "P-2", "2026-II")
        self._como("tec.ana", "TEC")
        respuesta = self.client.get(reverse("modificar_medicion", args=[borrador.pk]))
        self.assertIn(respuesta.status_code, (403, 404))  # C2; tras el cierre, A ya no tiene F-001 (C1)

    # C19, K-1 ----------------------------------------------------------------------------------------

    def test_t39_las_temporales_vencidas_no_cuentan_para_el_maximo(self):
        tomas = Usuario.objects.get(username="tec.tomas")
        una = Asignacion.objects.filter(tecnico=tomas, tipo="ordinaria").first()
        hoy = timezone.localdate()
        # Una de sus 20 era temporal y venció ayer: le quedan 19 activas.
        Asignacion.objects.filter(pk=una.pk).update(tipo="temporal", motivo="Cobertura", desde=hoy - timedelta(days=5),
                                                    hasta=hoy - timedelta(days=1))
        self._como("sup.sofia", "SUP")
        respuesta = self.client.post(reverse("crear_asignacion"), {
            **MOTIVO, "tecnico": tomas.pk, "finca": Finca.objects.get(codigo="F-025").pk,
            "periodo": Periodo.objects.get(nombre="2026-II").pk, "tipo": "ordinaria"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Asignacion.objects.filter(tecnico=tomas, finca__codigo="F-025").exists())


# --- 8.3: el caso feliz de cada permiso con pantalla propia ----------------------------------------

PERSONAJES = {"TEC": "tec.ana", "VER": "ver.diego", "SUP": "sup.sofia", "GER": "ger.gabriela",
              "ADM": "adm.alberto", "AUD": "aud.elena", "DUE": "due.daniel"}


@skipUnless(_opa_disponible() and MATRIZ.exists(), "requiere el motor real (OPA) y matriz.json")
class CasoFelizPorPermiso(ConPersonajes):
    """Con cada rol, cada pantalla sin objeto que la matriz le concede (listas, formularios de
    alta, exportaciones) responde 200 pasando por el motor real. Las acciones sobre un objeto
    (aprobar, corregir, autorizar…) tienen su caso feliz en los T-xx."""

    def test_cada_rol_entra_a_lo_que_la_matriz_le_concede(self):
        matriz = json.loads(MATRIZ.read_text(encoding="utf-8"))["matriz"]
        rutas = [r for r in _rutas() if getattr(r.callback, "protegida", None) and r.name and not r.pattern.converters]
        cubiertos = set()
        for rol, usuario in PERSONAJES.items():
            self._como(usuario, rol)
            concedidos = {(p["verbo"], objeto) for objeto, lista in matriz["celdas"].get(rol, {}).items() for p in lista}
            for ruta in rutas:
                verbo, objeto = ruta.callback.protegida
                if (verbo, objeto) not in concedidos:
                    continue
                with self.subTest(rol=rol, ruta=ruta.name), mock.patch("nucleo.emision.sellar", return_value={"firma": "x"}):
                    respuesta = self.client.get(reverse(ruta.name), MOTIVO)
                    self.assertEqual(respuesta.status_code, 200, f"{rol} {verbo} {objeto} en {ruta.name}")
                    cubiertos.add((rol, objeto, verbo))
        self.assertGreater(len(cubiertos), 40)
        print(f"\n8.3: {len(cubiertos)} permisos con su caso feliz por pantalla")

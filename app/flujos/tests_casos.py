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

from cuentas.models import PropuestaRol, Usuario
from flujos.tests import MATRIZ, MOTIVO, _opa_disponible, _rutas
from flujos.tests_certificados import como, emitir
from negocio.models import (
    Alerta,
    Asignacion,
    Certificado,
    DatosPersonales,
    Enmienda,
    EventoLectura,
    Finca,
    Medicion,
    ParametroRol,
    Parcela,
    Periodo,
    PropuestaCatalogo,
    PropuestaPeriodo,
    Titular,
)

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



    def _cerrar_2026_ii(self):
        self._como("adm.alberto", "ADM")
        periodo = Periodo.objects.get(nombre="2026-II")
        self.client.post(reverse("proponer_periodo", args=[periodo.pk]), {**MOTIVO, "accion": "cerrar"})
        registro = PropuestaPeriodo.objects.get(periodo=periodo, accion="cerrar", estado="propuesto")
        self._como("ger.gerardo", "GER")
        self.client.post(reverse("cerrar_periodo", args=[registro.pk]), MOTIVO)
        self.assertEqual(Periodo.objects.get(pk=periodo.pk).estado, "cerrado")

@skipUnless(_opa_disponible(), "requiere el motor real (OPA) en OPA_URL")
class CasosQueFaltaban(ConPersonajes):
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

    def test_t21_lo_devuelto_no_se_modifica_despues_del_cierre_procede_una_enmienda(self):
        self._como("ver.diego", "VER")
        m = self._medicion("F-001", "P-1", "2026-II")
        self.client.post(reverse("devolver_medicion", args=[m.pk]), {**MOTIVO, "observaciones": "Revise el DAP"})
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "devuelta")
        self._cerrar_2026_ii()
        versiones = m.versiones.count()
        self._como("tec.ana", "TEC")
        v = m.version_vigente
        respuesta = self.client.post(reverse("modificar_medicion", args=[m.pk]), {
            **MOTIVO, "fecha_medicion": v.fecha_medicion.isoformat(), "arboles": v.arboles,
            "dap_promedio_cm": v.dap_promedio_cm, "altura_promedio_m": v.altura_promedio_m, "toneladas_co2": "1.000"})
        self.assertIn(respuesta.status_code, (403, 404))  # C2; tras el cierre, A ya no tiene F-001 (C1)
        self.assertEqual(m.versiones.count(), versiones)
        # Lo que procede es una enmienda (C7): lo devuelto con el período cerrado sí se puede enmendar.
        e = self._solicitar("ger.gabriela", "GER", medicion=m)
        self.assertEqual(e.estado, "solicitada")

    def test_t26_con_habilitacion_registra_y_en_otra_sesion_no_aprueba(self):
        carla = Usuario.objects.get(username="ver.carla")
        self._como("sup.sofia", "SUP")
        f025 = Finca.objects.get(codigo="F-025")
        self.assertEqual(self.client.post(reverse("crear_asignacion"), {
            **MOTIVO, "tecnico": carla.pk, "finca": f025.pk, "periodo": Periodo.objects.get(nombre="2026-II").pk,
            "tipo": "ordinaria"}).status_code, 302)
        self._como("ver.carla", "TEC")  # con la habilitación de técnica
        parcela = Parcela.objects.get(finca=f025, codigo="P-1", activa=True)
        self.assertEqual(self.client.post(reverse("nueva_medicion", args=[parcela.pk]), {
            "fecha_medicion": timezone.localdate().isoformat(), "arboles": 90, "dap_promedio_cm": "18.0",
            "altura_promedio_m": "11.0", "toneladas_co2": "30.000"}).status_code, 302)
        m = Medicion.objects.get(parcela=parcela, creada_por=carla)
        self.assertEqual(self.client.post(reverse("enviar_medicion", args=[m.pk]), MOTIVO).status_code, 302)
        self._como("ver.carla", "VER")  # otra sesión, ya como verificadora
        respuesta = self.client.post(reverse("aprobar_medicion", args=[m.pk]), MOTIVO)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._regla(respuesta), "C3")
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "enviada")

    # H1, H2, H3: controles de historial ----------------------------------------------------------------
    # Los umbrales y la jornada son parámetros que aprueba GER (P-02, ParametroRol): se ajustan para que
    # el caso no dependa de cargar 60 lecturas ni de la hora en que corra la prueba.

    def _parametros_ver(self, **valores):
        hoy = timezone.localdate().isoweekday()
        base = {"h1_aviso": 40, "h1_verificacion": 60, "h1_restriccion": 80, "h3_fincas_hora": 10,
                "dias_laborales": "12345"}
        if valores.pop("hoy_no_laboral", False):
            base["dias_laborales"] = "".join(str(d) for d in range(1, 8) if d != hoy)
        ParametroRol.objects.update_or_create(rol="VER", defaults={**base, **valores})

    def _lecturas(self, usuario, *codigos):
        for codigo in codigos:
            EventoLectura.objects.create(usuario=usuario, finca=Finca.objects.get(codigo=codigo))

    def _alerta(self, persona, control, nivel):
        return Alerta.objects.filter(sujeto=persona, control=control, nivel=nivel).exists()

    def test_t18_h1_mas_fincas_que_el_umbral_pide_segundo_factor_y_motivo(self):
        self._parametros_ver(h1_aviso=2, h1_verificacion=3, h1_restriccion=50)
        bruno = self._como("ver.bruno", "VER")
        self._lecturas(bruno, "F-010", "F-011", "F-012", "F-013")
        f001 = Finca.objects.get(codigo="F-001")
        respuesta = self.client.get(reverse("finca", args=[f001.pk]))
        self.assertTemplateUsed(respuesta, "autorizacion/motivo.html")
        self.assertEqual(self._regla(respuesta), "H1")
        respuesta = self.client.get(reverse("finca", args=[f001.pk]), {"motivo": "Revisión del lote de la semana"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self._alerta(bruno, "H1", "verificacion"))

    def test_t19_t33_h3_fuera_de_jornada_confirma_y_despues_se_restringe(self):
        self._parametros_ver(h3_fincas_hora=3, hoy_no_laboral=True)
        bruno = self._como("ver.bruno", "VER")
        self._lecturas(bruno, "F-010", "F-011", "F-012", "F-013")  # cuatro fincas nuevas en la última hora
        # T-19: la siguiente finca nueva pide segundo factor y motivo, y avisa a GER.
        f014 = Finca.objects.get(codigo="F-014")
        self.assertTemplateUsed(self.client.get(reverse("finca", args=[f014.pk])), "autorizacion/motivo.html")
        respuesta = self.client.get(reverse("finca", args=[f014.pk]), {"motivo": "Cierre de revisión del lote"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self._alerta(bruno, "H3", "verificacion"))
        # T-33: después de confirmar, otra finca nueva se restringe y avisa.
        f015 = Finca.objects.get(codigo="F-015")
        respuesta = self.client.get(reverse("finca", args=[f015.pk]), {"motivo": "Sigo con el lote"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(self._alerta(bruno, "H3", "restriccion"))
        # Una que ya había consultado vuelve a pedir motivo; no se restringe.
        f010 = Finca.objects.get(codigo="F-010")
        self.assertTemplateUsed(self.client.get(reverse("finca", args=[f010.pk])), "autorizacion/motivo.html")

    def test_t34_h2_aprobar_fuera_de_la_jornada_pide_motivo(self):
        self._parametros_ver(hoy_no_laboral=True)
        diego = self._como("ver.diego", "VER")
        m = self._medicion("F-001", "P-1", "2026-II")
        respuesta = self.client.post(reverse("aprobar_medicion", args=[m.pk]))
        self.assertTemplateUsed(respuesta, "autorizacion/motivo.html")
        self.assertEqual(self._regla(respuesta), "H2")
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "enviada")
        self.assertEqual(self.client.post(reverse("aprobar_medicion", args=[m.pk]), MOTIVO).status_code, 302)
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "aprobada")
        self.assertTrue(self._alerta(diego, "H2", "verificacion"))

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


def permisos_sobre_objetos():
    """Los permisos de los roles de la aplicación que no tienen una pantalla sin objeto: se ejercen
    sobre una medición, una enmienda, una cuenta… Cada uno necesita su prueba con nombre propio."""
    matriz = json.loads(MATRIZ.read_text(encoding="utf-8"))["matriz"]
    con_pantalla = {getattr(r.callback, "protegida", None) for r in _rutas() if not r.pattern.converters} - {None}
    return sorted((rol, p["verbo"], objeto) for rol in matriz["roles_de_la_aplicacion"]
                  for objeto, lista in matriz["celdas"].get(rol, {}).items() for p in lista
                  if (p["verbo"], objeto) not in con_pantalla)


@skipUnless(_opa_disponible() and MATRIZ.exists(), "requiere el motor real (OPA) y matriz.json")
class CasoFelizSobreObjetos(ConPersonajes):
    """8.3, segunda mitad: una prueba por cada permiso que se ejerce sobre un objeto, llamada
    test_<rol>_<verbo>_<objeto>. Pasa por la ruta y el motor real y comprueba que el cambio quedó."""

    def test_cada_permiso_sobre_un_objeto_tiene_su_prueba(self):
        faltan = [f"test_{rol.lower()}_{verbo}_{objeto}" for rol, verbo, objeto in permisos_sobre_objetos()
                  if not hasattr(self, f"test_{rol.lower()}_{verbo}_{objeto}")]
        self.assertEqual(faltan, [])

    def _version(self, m, **cambios):
        v = m.version_vigente
        return {**MOTIVO, "fecha_medicion": v.fecha_medicion.isoformat(), "arboles": v.arboles,
                "dap_promedio_cm": v.dap_promedio_cm, "altura_promedio_m": v.altura_promedio_m,
                "toneladas_co2": v.toneladas_co2, "motivo_tardio": "Medición de campo digitada tarde", **cambios}

    # TEC -----------------------------------------------------------------------------------------------

    def test_tec_crear_mediciones(self):
        ana = self._como("tec.ana", "TEC")
        parcela = Parcela.objects.get(finca__codigo="F-004", codigo="P-1", activa=True)
        self.assertEqual(self.client.post(reverse("nueva_medicion", args=[parcela.pk]), {
            "fecha_medicion": timezone.localdate().isoformat(), "arboles": 80, "dap_promedio_cm": "19.0",
            "altura_promedio_m": "11.5", "toneladas_co2": "28.000"}).status_code, 302)
        self.assertTrue(Medicion.objects.filter(parcela=parcela, creada_por=ana, periodo__nombre="2026-II").exists())

    def test_tec_modificar_mediciones(self):
        self._como("tec.ana", "TEC")
        m = self._medicion("F-001", "P-2", "2026-II")
        antes = m.versiones.count()
        self.assertEqual(self.client.post(reverse("modificar_medicion", args=[m.pk]),
                                          self._version(m, arboles=m.version_vigente.arboles + 1)).status_code, 302)
        self.assertEqual(m.versiones.count(), antes + 1)

    def test_tec_enviar_mediciones(self):
        self._como("tec.ana", "TEC")
        m = self._medicion("F-001", "P-2", "2026-II")
        self.assertEqual(self.client.post(reverse("enviar_medicion", args=[m.pk]), MOTIVO).status_code, 302)
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "enviada")

    def test_tec_solicitar_enmiendas(self):
        e = self._solicitar("tec.ana", "TEC")  # A registró la medición de 2026-I y es la responsable
        self.assertEqual((e.estado, e.solicitada_por.username), ("solicitada", "tec.ana"))

    def test_tec_corregir_enmiendas(self):
        e = self._solicitar("ger.gabriela", "GER")
        self.assertEqual(self._corregir(e, "15.000").status_code, 302)
        self.assertEqual(Enmienda.objects.get(pk=e.pk).estado, "corregida")

    # VER -----------------------------------------------------------------------------------------------

    def test_ver_aprobar_mediciones(self):
        self._como("ver.diego", "VER")
        m = self._medicion("F-001", "P-1", "2026-II")
        self.assertEqual(self.client.post(reverse("aprobar_medicion", args=[m.pk]), MOTIVO).status_code, 302)
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "aprobada")

    def test_ver_devolver_mediciones(self):
        self._como("ver.diego", "VER")
        m = self._medicion("F-001", "P-1", "2026-II")
        self.assertEqual(self.client.post(reverse("devolver_medicion", args=[m.pk]),
                                          {**MOTIVO, "observaciones": "Revise el DAP"}).status_code, 302)
        self.assertEqual(Medicion.objects.get(pk=m.pk).estado, "devuelta")

    def test_ver_solicitar_enmiendas(self):
        e = self._solicitar("ver.diego", "VER")
        self.assertEqual(e.solicitada_por.username, "ver.diego")

    def test_ver_revisar_enmiendas(self):
        e = self._solicitar("ger.gabriela", "GER")
        self._corregir(e, "15.000")
        self.assertEqual(self._revisar(e, "ver.carla").status_code, 302)
        self.assertEqual(Enmienda.objects.get(pk=e.pk).estado, "revisada")

    # SUP -----------------------------------------------------------------------------------------------

    def test_sup_modificar_asignaciones(self):
        self._como("sup.sofia", "SUP")
        a = Asignacion.objects.get(tecnico__username="tec.ana", finca__codigo="F-004", periodo__nombre="2026-II")
        self.assertEqual(self.client.post(reverse("terminar_asignacion", args=[a.pk]), MOTIVO).status_code, 302)
        self.assertIsNotNone(Asignacion.objects.get(pk=a.pk).terminada_en)

    def test_sup_resolver_alertas(self):
        sofia = self._como("sup.sofia", "SUP")
        a = Alerta.objects.create(sujeto=Usuario.objects.get(username="tec.ana"), control="H1", nivel="aviso")
        self.client.post(reverse("resolver_alerta", args=[a.pk]), {**MOTIVO, "resolucion": "Revisado con la técnica"})
        self.assertEqual(Alerta.objects.get(pk=a.pk).resuelta_por, sofia)

    # GER -----------------------------------------------------------------------------------------------

    def test_ger_aprobar_fincas(self):
        self._como("adm.alberto", "ADM")
        self.client.post(reverse("proponer_finca"), {
            **MOTIVO, "codigo": "F-901", "nombre": "Prueba", "titular": Titular.objects.get(codigo="T-003").pk,
            "ubicacion": "Rivas", "parcela": "P-1",
            "geometria": "POLYGON((-83.60 9.60,-83.59 9.60,-83.59 9.61,-83.60 9.61,-83.60 9.60))"})
        propuesta = PropuestaCatalogo.objects.get(finca__codigo="F-901")
        self._como("ger.gabriela", "GER")
        self.client.post(reverse("aprobar_catalogo", args=[propuesta.pk]), MOTIVO)
        self.assertEqual(Finca.objects.get(codigo="F-901").estado, "aprobado")

    def test_ger_abrir_periodos(self):
        self._como("adm.alberto", "ADM")
        self.client.post(reverse("crear_periodo"), {**MOTIVO, "nombre": "2027-I", "inicio": "2027-01-04",
                                                    "fin_medicion": "2027-06-11", "cierre_registro": "2027-06-18"})
        periodo = Periodo.objects.get(nombre="2027-I")
        self.client.post(reverse("proponer_periodo", args=[periodo.pk]), {**MOTIVO, "accion": "abrir"})
        registro = PropuestaPeriodo.objects.get(periodo=periodo, accion="abrir", estado="propuesto")
        self._como("ger.gerardo", "GER")
        self.assertEqual(self.client.post(reverse("abrir_periodo", args=[registro.pk]), MOTIVO).status_code, 302)
        self.assertEqual(Periodo.objects.get(pk=periodo.pk).estado, "abierto")

    def test_ger_cerrar_periodos(self):
        self._cerrar_2026_ii()

    def test_ger_solicitar_enmiendas(self):
        e = self._solicitar("ger.gabriela", "GER")
        self.assertEqual(e.solicitada_por.username, "ger.gabriela")

    def test_ger_autorizar_enmiendas(self):
        e = self._solicitar("ger.gabriela", "GER")
        self._corregir(e, self._medicion().version_vigente.toneladas_co2)
        self._revisar(e, "ver.carla")
        self.assertEqual(self._autorizar(e, "ger.gerardo").status_code, 302)
        self.assertEqual(Enmienda.objects.get(pk=e.pk).estado, "autorizada")

    def test_ger_aprobar_cuentas(self):
        tomas = Usuario.objects.get(username="tec.tomas")
        self._como("adm.alberto", "ADM")
        self.client.post(reverse("proponer_rol", args=[tomas.pk]), {**MOTIVO, "rol": "SUP"})
        propuesta = PropuestaRol.objects.get(usuario=tomas, rol="SUP")
        self._como("ger.gabriela", "GER")
        self.assertEqual(self.client.post(reverse("aprobar_rol", args=[propuesta.pk]), MOTIVO).status_code, 302)
        self.assertEqual(Usuario.objects.get(pk=tomas.pk).rol, "SUP")

    def test_ger_resolver_alertas(self):
        gabriela = self._como("ger.gabriela", "GER")
        a = Alerta.objects.create(sujeto=Usuario.objects.get(username="ver.bruno"), control="H1", nivel="aviso")
        self.client.post(reverse("resolver_alerta", args=[a.pk]), {**MOTIVO, "resolucion": "Lote de la semana"})
        self.assertEqual(Alerta.objects.get(pk=a.pk).resuelta_por, gabriela)

    # ADM -----------------------------------------------------------------------------------------------

    def test_adm_modificar_datos_personales(self):
        self._como("adm.alberto", "ADM")
        t = Titular.objects.get(codigo="T-002")
        datos = DatosPersonales.objects.get(titular=t)
        self.assertEqual(self.client.post(reverse("editar_titular", args=[t.pk]), {
            **MOTIVO, "nombre": "Nombre corregido", "identificacion": datos.identificacion,
            "telefono": "2222-0000"}).status_code, 302)
        self.assertEqual(DatosPersonales.objects.get(titular=t).nombre, "Nombre corregido")

    def test_adm_eliminar_datos_personales(self):
        self._como("adm.alberto", "ADM")
        t = Titular.objects.get(codigo="T-003")
        self.client.post(reverse("suprimir_titular", args=[t.pk]), MOTIVO)
        self.assertIsNotNone(DatosPersonales.objects.get(titular=t).suprimido_en)

    def test_adm_proponer_periodos(self):
        self._como("adm.alberto", "ADM")
        periodo = Periodo.objects.get(nombre="2026-II")
        self.assertEqual(self.client.post(reverse("proponer_periodo", args=[periodo.pk]),
                                          {**MOTIVO, "accion": "cerrar"}).status_code, 302)
        self.assertTrue(PropuestaPeriodo.objects.filter(periodo=periodo, accion="cerrar", estado="propuesto").exists())

    def test_adm_desactivar_cuentas(self):
        self._como("adm.alberto", "ADM")
        tomas = Usuario.objects.get(username="tec.tomas")
        self.assertEqual(self.client.post(reverse("desactivar_cuenta", args=[tomas.pk]), MOTIVO).status_code, 302)
        self.assertFalse(Usuario.objects.get(pk=tomas.pk).is_active)

    def test_adm_proponer_cuentas(self):
        self._como("adm.alberto", "ADM")
        tomas = Usuario.objects.get(username="tec.tomas")
        self.assertEqual(self.client.post(reverse("proponer_rol", args=[tomas.pk]), {**MOTIVO, "rol": "SUP"}).status_code, 302)
        self.assertTrue(PropuestaRol.objects.filter(usuario=tomas, rol="SUP", estado="propuesta").exists())

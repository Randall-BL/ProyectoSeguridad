"""Pruebas de autenticación y sesión (fase 3): segundo factor, reautenticación, sesión de servidor,
revocación, intentos fallidos, rol activo y ventana de la cuenta."""

import secrets
import time
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from allauth.account.internal.flows.login import record_authentication
from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.conf import settings
from django.core.cache import cache, caches
from django.core.cache.backends.db import DatabaseCache
from django.db import connection
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from bitacora.models import Registro
from cuentas.decisiones import requiere_segundo_factor
from cuentas import intentos
from cuentas.models import EstadoPropuesta, IntentosAcceso, PropuestaRol, Rol, Sesion, Usuario
from cuentas.roles import ROL_ACTIVO, habilitacion_vigente
from cuentas.sesiones import INICIO
from negocio.models import Asignacion, Finca, Periodo, Titular

# Contraseña de las cuentas de prueba: se genera en cada corrida, no vive en el repositorio.
CLAVE = secrets.token_urlsafe(18)


def _persona(usuario="tec.prueba", rol=Rol.TEC, **campos):
    return Usuario.objects.create_user(
        username=usuario, password=CLAVE, rol=rol, identificacion=usuario, **campos
    )


class SegundoFactorObligatorio(TestCase):
    def test_sin_totp_solo_puede_activarlo(self):
        self.client.force_login(_persona())
        respuesta = self.client.get(reverse("hola"))
        self.assertRedirects(respuesta, reverse("mfa_activate_totp"), fetch_redirect_response=False)

    def test_recien_entrado_activa_sin_repetir_la_contrasena(self):
        _persona()
        self.client.post(reverse("account_login"), {"login": "tec.prueba", "password": CLAVE})
        self.assertEqual(self.client.get(reverse("mfa_activate_totp")).status_code, 200)

    def test_sin_totp_puede_salir(self):
        self.client.force_login(_persona())
        self.assertEqual(self.client.get(reverse("account_logout")).status_code, 200)

    def test_con_totp_entra(self):
        persona = _persona()
        TOTP.activate(persona, generate_totp_secret())
        self.client.force_login(persona)
        self.assertEqual(self.client.get(reverse("hola")).status_code, 200)

    def test_sin_sesion_no_se_redirige(self):
        self.assertEqual(self.client.get(reverse("hola")).status_code, 200)


class SecretoTotp(TestCase):
    def test_el_secreto_se_guarda_cifrado(self):
        secreto = generate_totp_secret()
        totp = TOTP.activate(_persona(), secreto)
        guardado = Authenticator.objects.get(pk=totp.instance.pk).data["secret"]
        self.assertNotIn(secreto, guardado)
        self.assertEqual(get_adapter().decrypt(guardado), secreto)

    def test_nadie_desactiva_su_segundo_factor(self):
        totp = TOTP.activate(_persona(), generate_totp_secret())
        self.assertFalse(get_adapter().can_delete_authenticator(totp.instance))


class SinRegistroNiRecuperacionPorCorreo(TestCase):
    """C12 y POL-AU-10: las cuentas las crea ADM con aprobación de GER, y la recuperación también
    pasa por los dos."""

    def test_rutas_cerradas(self):
        for nombre in ("account_signup", "account_reset_password", "account_email"):
            with self.subTest(nombre=nombre), self.assertRaises(NoReverseMatch):
                reverse(nombre)
        for ruta in ("/cuentas/signup/", "/cuentas/password/reset/", "/cuentas/email/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)


@requiere_segundo_factor
def _decidir(request):
    return HttpResponse("decidido")


class ReautenticacionEnDecisiones(TestCase):
    """POL-AU-06: una decisión exige el segundo factor en los cinco minutos previos."""

    def setUp(self):
        self.persona = _persona("ver.prueba", Rol.VER)
        TOTP.activate(self.persona, generate_totp_secret())

    def _peticion(self, *registros, metodo="get", ruta="/mediciones/7/aprobar?vista=1"):
        """Petición con la sesión de la persona y sus registros de autenticación: (método,
        segundos que pasaron)."""
        peticion = getattr(RequestFactory(), metodo)(ruta)
        SessionMiddleware(lambda r: None).process_request(peticion)
        peticion.user = self.persona
        for como, hace in registros:
            with mock.patch("time.time", return_value=time.time() - hace):
                record_authentication(peticion, self.persona, como)
        return peticion

    def _va_a_pedir_el_codigo(self, respuesta, destino):
        self.assertEqual(respuesta.status_code, 302)
        partes = urlsplit(respuesta["Location"])
        self.assertEqual(partes.path, reverse("mfa_reauthenticate"))
        self.assertEqual(parse_qs(partes.query)["next"], [destino])

    def test_codigo_de_hace_un_minuto_basta(self):
        respuesta = _decidir(self._peticion(("password", 70), ("mfa", 60)))
        self.assertEqual(respuesta.content, b"decidido")

    def test_codigo_de_hace_seis_minutos_no_basta(self):
        respuesta = _decidir(self._peticion(("password", 370), ("mfa", 360)))
        self.assertNotEqual(respuesta.content, b"decidido")
        self._va_a_pedir_el_codigo(respuesta, "/mediciones/7/aprobar?vista=1")

    def test_la_contrasena_sola_no_basta(self):
        respuesta = _decidir(self._peticion(("mfa", 3600), ("password", 10)))
        self._va_a_pedir_el_codigo(respuesta, "/mediciones/7/aprobar?vista=1")

    def test_un_post_sin_codigo_reciente_no_se_ejecuta(self):
        respuesta = _decidir(self._peticion(metodo="post"))
        self.assertNotEqual(respuesta.content, b"decidido")
        self._va_a_pedir_el_codigo(respuesta, "/mediciones/7/aprobar")

    def test_sin_sesion_va_a_iniciar_sesion(self):
        peticion = self._peticion()
        peticion.user = AnonymousUser()
        respuesta = _decidir(peticion)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta["Location"].startswith(reverse("account_login")))


class SesionDeServidor(TestCase):
    """POL-AU-08: la sesión vive en la base, cambia de identificador al entrar, vence a los 30
    minutos sin actividad y a las 12 horas de iniciada."""

    def setUp(self):
        self.persona = _persona()

    def _clave_de_sesion(self):
        return self.client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_identificador_nuevo_al_entrar(self):
        antes = self.client.session.session_key
        self.client.post(reverse("account_login"), {"login": "tec.prueba", "password": CLAVE})
        despues = self._clave_de_sesion()
        self.assertNotEqual(antes, despues)
        self.assertFalse(Sesion.objects.filter(pk=antes).exists())
        self.assertEqual(Sesion.objects.get(pk=despues).usuario_id, self.persona.pk)

    def test_vence_a_los_30_minutos_sin_actividad(self):
        self.client.force_login(self.persona)
        vence = Sesion.objects.get(pk=self._clave_de_sesion()).expire_date
        self.assertAlmostEqual((vence - timezone.now()).total_seconds(), 30 * 60, delta=60)

    def test_cada_peticion_corre_el_vencimiento(self):
        self.client.force_login(self.persona)
        clave = self._clave_de_sesion()
        Sesion.objects.filter(pk=clave).update(expire_date=timezone.now() + timedelta(minutes=5))
        self.client.get(reverse("salud"))
        vence = Sesion.objects.get(pk=clave).expire_date
        self.assertGreater((vence - timezone.now()).total_seconds(), 29 * 60)

    def test_doce_horas_como_maximo(self):
        self.client.force_login(self.persona)
        sesion = self.client.session
        sesion[INICIO] = int(time.time()) - settings.SESION_MAXIMA - 1
        sesion.save()
        respuesta = self.client.get(reverse("hola"))
        self.assertRedirects(respuesta, reverse("account_login"), fetch_redirect_response=False)
        self.assertFalse(Sesion.objects.filter(usuario=self.persona).exists())

    def test_entrada_y_salida_quedan_en_la_bitacora(self):
        self.client.force_login(self.persona)
        self.client.post(reverse("account_logout"))
        acciones = set(
            Registro.objects.filter(usuario_id=self.persona.pk).values_list("accion", flat=True)
        )
        self.assertEqual(acciones, {"iniciar_sesion", "cerrar_sesion"})


class RevocacionInmediata(TestCase):
    """POL-CA-04 y POL-CA-05: al cambiar lo que la persona puede hacer, se cierran todas sus
    sesiones, en todos los equipos."""

    def setUp(self):
        self.persona = _persona()
        self.gerente = _persona("ger.prueba", Rol.GER)
        self.admin = _persona("adm.prueba", Rol.ADM)

    def _abrir_sesiones(self, cuantas=2):
        for _ in range(cuantas):
            self.client_class().force_login(self.persona)
        self.assertEqual(Sesion.objects.filter(usuario=self.persona).count(), cuantas)

    def _sin_sesiones(self):
        self.assertFalse(Sesion.objects.filter(usuario=self.persona).exists())

    def test_cambio_de_rol(self):
        self._abrir_sesiones()
        self.persona.rol = Rol.VER
        self.persona.save()
        self._sin_sesiones()
        self.assertTrue(Registro.objects.filter(accion="cerrar_sesiones", regla="POL-CA-04").exists())

    def test_baja(self):
        self._abrir_sesiones()
        self.persona.is_active = False
        self.persona.save(update_fields=["is_active"])
        self._sin_sesiones()
        self.assertTrue(Registro.objects.filter(accion="cerrar_sesiones", regla="POL-CA-05").exists())

    def test_cambio_de_contrasena(self):
        self._abrir_sesiones()
        self.persona.set_password(secrets.token_urlsafe(18))
        self.persona.save()
        self._sin_sesiones()

    def test_propuesta_de_rol_aprobada(self):
        self._abrir_sesiones()
        PropuestaRol.objects.create(
            usuario=self.persona,
            rol=Rol.TEC,
            propuesta_por=self.admin,
            estado=EstadoPropuesta.APROBADA,
            aprobada_por=self.gerente,
            aprobada_en=timezone.now(),
        )
        self._sin_sesiones()

    def test_asignacion_nueva(self):
        self._abrir_sesiones()
        titular = Titular.objects.create(codigo="T-900", tipo=Titular.Tipo.FISICA)
        finca = Finca.objects.create(codigo="F-900", nombre="Prueba", titular=titular)
        hoy = timezone.localdate()
        periodo = Periodo.objects.create(
            nombre="P-prueba", inicio=hoy, fin_medicion=hoy, cierre_registro=hoy
        )
        Asignacion.objects.create(
            tecnico=self.persona,
            finca=finca,
            periodo=periodo,
            tipo=Asignacion.Tipo.ORDINARIA,
            desde=hoy,
            creada_por=self.gerente,
        )
        self._sin_sesiones()

    def test_ultimo_acceso_no_revoca(self):
        self._abrir_sesiones()
        self.persona.last_login = timezone.now()
        self.persona.save(update_fields=["last_login"])
        self.assertEqual(Sesion.objects.filter(usuario=self.persona).count(), 2)


class IntentosFallidos(TestCase):
    """POL-AU-07: demora creciente desde el quinto fallo y bloqueo de 15 minutos al décimo, igual
    para una cuenta que existe y para una que no."""

    def setUp(self):
        _persona()
        cache.clear()

    def _entrar(self, clave, usuario="tec.prueba"):
        return self.client.post(reverse("account_login"), {"login": usuario, "password": clave})

    def _fallar(self, veces, usuario="tec.prueba"):
        for _ in range(veces):
            IntentosAcceso.objects.filter(pk=intentos._huella(usuario)).update(espera_hasta=None)
            self._entrar("no-es-la-clave", usuario)

    def _fila(self, usuario="tec.prueba"):
        return IntentosAcceso.objects.get(pk=intentos._huella(usuario))

    def test_cuatro_fallos_no_demoran(self):
        self._fallar(4)
        self.assertIsNone(self._fila().espera_hasta)

    def test_desde_el_quinto_hay_que_esperar_y_la_espera_crece(self):
        self._fallar(5)
        primera = self._fila().espera_hasta - self._fila().ultimo_fallo
        self._fallar(1)
        segunda = self._fila().espera_hasta - self._fila().ultimo_fallo
        self.assertEqual(primera, timedelta(seconds=30))
        self.assertEqual(segunda, timedelta(seconds=60))

    def test_en_espera_ni_la_clave_correcta_entra(self):
        self._fallar(5)
        respuesta = self._entrar(CLAVE)
        self.assertContains(respuesta, "Demasiados intentos fallidos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_al_decimo_bloqueo_de_15_minutos(self):
        self._fallar(10)
        fila = self._fila()
        self.assertEqual(fila.espera_hasta - fila.ultimo_fallo, timedelta(minutes=15))

    def test_entrar_bien_reinicia_el_conteo(self):
        self._fallar(3)
        self._entrar(CLAVE)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertFalse(IntentosAcceso.objects.filter(pk=intentos._huella("tec.prueba")).exists())

    def test_cuenta_inexistente_igual_trato(self):
        self._fallar(5, "nadie.existe")
        self.assertContains(self._entrar("otra", "nadie.existe"), "Demasiados intentos fallidos")

    def test_no_guarda_el_nombre_escrito(self):
        self._fallar(1)
        self.assertFalse(IntentosAcceso.objects.filter(pk="tec.prueba").exists())

    def test_fallos_en_la_bitacora(self):
        self._fallar(5)
        registros = Registro.objects.filter(accion="iniciar_sesion", resultado="denegado")
        self.assertEqual(registros.count(), 5)
        self.assertEqual(registros.filter(regla="POL-AU-07").count(), 1)

    def test_cache_compartida_entre_instancias(self):
        self.assertIsInstance(caches["default"], DatabaseCache)


class RolActivoTecVer(TestCase):
    """Tarea 3.8: con una habilitación temporal, la verificadora entra como técnica o como
    verificadora, nunca como ambas en la misma sesión."""

    def setUp(self):
        self.carla = _persona("ver.prueba", Rol.VER)
        TOTP.activate(self.carla, generate_totp_secret())
        self.admin = _persona("adm.prueba", Rol.ADM)
        self.gerente = _persona("ger.prueba", Rol.GER)

    def _habilitar(self, dias=10):
        return PropuestaRol.objects.create(
            usuario=self.carla,
            rol=Rol.TEC,
            es_habilitacion=True,
            fin_habilitacion=timezone.localdate() + timedelta(days=dias),
            propuesta_por=self.admin,
            estado=EstadoPropuesta.APROBADA,
            aprobada_por=self.gerente,
            aprobada_en=timezone.now(),
        )

    def test_sin_habilitacion_el_rol_queda_fijo(self):
        self.client.force_login(self.carla)
        self.assertEqual(self.client.get(reverse("hola")).status_code, 200)
        self.assertEqual(self.client.session[ROL_ACTIVO], Rol.VER)

    def test_con_habilitacion_tiene_que_elegir(self):
        self._habilitar()
        self.client.force_login(self.carla)
        respuesta = self.client.get(reverse("hola"))
        self.assertRedirects(respuesta, reverse("elegir_rol"), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("elegir_rol")), "Técnico de campo")

    def test_lo_elegido_no_cambia_en_la_sesion(self):
        self._habilitar()
        self.client.force_login(self.carla)
        self.client.post(reverse("elegir_rol"), {"rol": Rol.TEC})
        self.client.post(reverse("elegir_rol"), {"rol": Rol.VER})
        self.assertEqual(self.client.session[ROL_ACTIVO], Rol.TEC)
        self.assertTrue(Registro.objects.filter(accion="elegir_rol", rol=Rol.TEC).exists())

    def test_la_aplicacion_ve_la_habilitacion_antes_de_tener_rol(self):
        """Con los permisos reales de va_app y sin app.rol, la seguridad por fila esconde las
        propuestas de rol; la función de la base responde igual."""
        self._habilitar()
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE va_app")
        self.assertTrue(habilitacion_vigente(self.carla))

    def test_no_elige_un_rol_que_no_tiene(self):
        self._habilitar()
        self.client.force_login(self.carla)
        self.client.post(reverse("elegir_rol"), {"rol": Rol.GER})
        self.assertNotIn(ROL_ACTIVO, self.client.session)

    def test_al_vencer_la_habilitacion_se_cierra_la_sesion(self):
        habilitacion = self._habilitar()
        self.client.force_login(self.carla)
        self.client.post(reverse("elegir_rol"), {"rol": Rol.TEC})
        PropuestaRol.objects.filter(pk=habilitacion.pk).update(
            fin_habilitacion=timezone.localdate() - timedelta(days=1)
        )
        respuesta = self.client.get(reverse("hola"))
        self.assertRedirects(respuesta, reverse("account_login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class VentanaDeLaCuenta(TestCase):
    """Tarea 3.9: AUD fuera de su ventana no inicia sesión (C6, T-09) y OPE no tiene cuenta (T-20)."""

    def _auditora(self, desde, hasta):
        persona = _persona("aud.prueba", Rol.AUD, vigente_desde=desde, vigente_hasta=hasta)
        TOTP.activate(persona, generate_totp_secret())
        return persona

    def _entrar(self, usuario):
        return self.client.post(reverse("account_login"), {"login": usuario, "password": CLAVE})

    def test_t09_una_semana_despues_de_su_ventana(self):
        ahora = timezone.now()
        self._auditora(ahora - timedelta(days=37), ahora - timedelta(days=7))
        respuesta = self._entrar("aud.prueba")
        self.assertContains(respuesta, "no está vigente")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(Registro.objects.filter(accion="iniciar_sesion", resultado="denegado", regla="C6").exists())

    def test_dentro_de_su_ventana_pasa_al_segundo_factor(self):
        ahora = timezone.now()
        self._auditora(ahora - timedelta(days=1), ahora + timedelta(days=30))
        respuesta = self._entrar("aud.prueba")
        self.assertRedirects(respuesta, reverse("mfa_authenticate"), fetch_redirect_response=False)

    def test_auditora_sin_ventana_no_entra(self):
        self._auditora(None, None)
        self.assertContains(self._entrar("aud.prueba"), "no está vigente")

    def test_la_sesion_termina_con_la_ventana(self):
        ahora = timezone.now()
        auditora = self._auditora(ahora - timedelta(days=1), ahora + timedelta(days=30))
        self.client.force_login(auditora)
        self.assertEqual(self.client.get(reverse("hola")).context["user"], auditora)
        Usuario.objects.filter(pk=auditora.pk).update(vigente_hasta=ahora - timedelta(minutes=1))
        self.assertFalse(self.client.get(reverse("hola")).context["user"].is_authenticated)

    def test_t20_ope_no_es_un_rol_de_la_aplicacion(self):
        self.assertNotIn("OPE", Rol.values)
        _persona("ope.prueba", "OPE")
        self.assertContains(self._entrar("ope.prueba"), "no está vigente")

    def test_cuenta_sin_rol_no_entra(self):
        _persona("sin.rol", "")
        self.assertContains(self._entrar("sin.rol"), "no está vigente")

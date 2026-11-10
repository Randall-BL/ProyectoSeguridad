"""Pruebas del segundo factor (tareas 3.3 y 3.4: POL-AU-05, POL-AU-06 y POL-AU-10)."""

import time
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from allauth.account.internal.flows.login import record_authentication
from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch, reverse

from cuentas.decisiones import requiere_segundo_factor
from cuentas.models import Rol, Usuario


def _persona(usuario="tec.prueba", rol=Rol.TEC):
    return Usuario.objects.create_user(username=usuario, rol=rol, identificacion=usuario)


class SegundoFactorObligatorio(TestCase):
    def test_sin_totp_solo_puede_activarlo(self):
        self.client.force_login(_persona())
        respuesta = self.client.get(reverse("hola"))
        self.assertRedirects(respuesta, reverse("mfa_activate_totp"), fetch_redirect_response=False)

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

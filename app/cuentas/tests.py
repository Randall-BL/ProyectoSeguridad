"""Pruebas del segundo factor (tarea 3.3, POL-AU-05 y POL-AU-10)."""

from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

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

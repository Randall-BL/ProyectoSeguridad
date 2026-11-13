"""Pruebas del negocio."""

import tempfile
from pathlib import Path
from unittest import mock

from allauth.mfa.models import Authenticator
from django.core.management import call_command
from django.test import TestCase

from cuentas.models import Usuario


class SemillaConSegundoFactor(TestCase):
    """Decisión 0.4: en la base desplegada cada cuenta de prueba entra con contraseña y TOTP, y su
    semilla queda junto a la contraseña en el archivo de --salida, fuera del repositorio."""

    def test_cada_cuenta_queda_con_totp_y_su_semilla_en_el_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta, mock.patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("SEMILLA_CONTRASENA", None)
            salida = Path(carpeta) / "cuentas.txt"
            call_command("sembrar", salida=salida, stdout=open(os.devnull, "w"))
            texto = salida.read_text(encoding="utf-8")

        cuentas = Usuario.objects.count()
        self.assertEqual(Authenticator.objects.filter(type=Authenticator.Type.TOTP).count(), cuentas)
        self.assertEqual(Authenticator.objects.filter(type=Authenticator.Type.RECOVERY_CODES).count(), cuentas)
        self.assertEqual(texto.count("otpauth://totp/"), cuentas)
        self.assertIn("issuer=Verdeazul", texto)

    def test_la_semilla_local_no_activa_el_segundo_factor(self):
        with mock.patch.dict("os.environ", {"SEMILLA_CONTRASENA": "Una-clave-local-larga-2026"}):
            import os

            call_command("sembrar", stdout=open(os.devnull, "w"))
        self.assertFalse(Authenticator.objects.exists())

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

    def test_un_tecnico_registra_mediciones_solo_en_sus_parcelas(self):
        """Regresión de 0005: como va_app y con rol TEC, la base deja insertar la medición en una
        parcela de una finca asignada y la niega en una ajena (C1)."""
        import os

        from django.db import DatabaseError, connection, transaction

        from negocio.models import Asignacion, Parcela

        with mock.patch.dict("os.environ", {"SEMILLA_CONTRASENA": "Una-clave-local-larga-2026"}):
            call_command("sembrar", stdout=open(os.devnull, "w"))
        ana = Usuario.objects.get(username="tec.ana")
        asignada = Asignacion.objects.filter(tecnico=ana, terminada_en__isnull=True, periodo__estado="abierto").first()
        propia = Parcela.objects.filter(finca=asignada.finca, activa=True).first()
        ajena = Parcela.objects.exclude(finca__asignaciones__tecnico=ana).filter(activa=True).first()

        def insertar(parcela):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE va_app")
                cursor.execute(
                    "SELECT set_config('app.rol', 'TEC', true), set_config('app.usuario', %s, true)", [str(ana.pk)]
                )
                cursor.execute(
                    "INSERT INTO negocio_medicion (id, parcela_id, periodo_id, estado, creada_por_id, creada_en,"
                    " observaciones) VALUES (gen_random_uuid(), %s, %s, 'borrador', %s, now(), '')",
                    [parcela.pk, asignada.periodo_id, ana.pk],
                )

        insertar(propia)
        with self.assertRaises(DatabaseError):
            insertar(ajena)

    def test_la_semilla_local_no_activa_el_segundo_factor(self):
        with mock.patch.dict("os.environ", {"SEMILLA_CONTRASENA": "Una-clave-local-larga-2026"}):
            import os

            call_command("sembrar", stdout=open(os.devnull, "w"))
        self.assertFalse(Authenticator.objects.exists())

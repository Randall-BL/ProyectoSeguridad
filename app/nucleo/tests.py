"""Pruebas del núcleo: el contexto de base de cada petición (tarea 2.5)."""

import secrets
from datetime import date

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from cuentas.models import Rol, Usuario
from negocio.models import Periodo
from nucleo.basedatos import ContextoDeBase


def _lo_que_ve_la_base(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.usuario', true), current_setting('app.rol', true)")
        return HttpResponse("|".join(cursor.fetchone()))


class ContextoDeLaPeticion(TestCase):
    def _pedir(self, usuario, rol):
        peticion = RequestFactory().get("/")
        peticion.user = usuario
        peticion.rol_activo = rol
        return ContextoDeBase(_lo_que_ve_la_base)(peticion).content.decode()

    def test_la_base_sabe_quien_pide_y_con_que_rol(self):
        persona = Usuario.objects.create_user(
            username="ver.prueba", password=secrets.token_urlsafe(18), rol=Rol.VER, identificacion="v"
        )
        self.assertEqual(self._pedir(persona, Rol.TEC), f"{persona.pk}|TEC")

    def test_sin_sesion_no_hay_rol(self):
        self.assertEqual(self._pedir(AnonymousUser(), ""), "|")

    def test_sin_rol_la_aplicacion_no_ve_filas_del_negocio(self):
        hoy = date(2026, 11, 10)
        Periodo.objects.create(nombre="P", inicio=hoy, fin_medicion=hoy, cierre_registro=hoy)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE va_app")
            vistos = []
            for rol in ("", "GER"):
                cursor.execute("SELECT set_config('app.rol', %s, true)", [rol])
                cursor.execute("SELECT count(*) FROM negocio_periodo")
                vistos.append(cursor.fetchone()[0])
        self.assertEqual(vistos, [0, 1])

"""Pruebas del núcleo: el contexto de base de cada petición (tarea 2.5)."""

import secrets
from unittest import mock
from datetime import date

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from autorizacion import motor
from bitacora.models import Registro
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


class InicioPorRol(TestCase):
    """Tarea 4.10: el inicio muestra lo que el rol puede hacer según el motor; sin motor, 503."""

    def setUp(self):
        from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret

        self.persona = Usuario.objects.create_user(
            username="ver.prueba", password=secrets.token_urlsafe(18), rol=Rol.VER, identificacion="v"
        )
        TOTP.activate(self.persona, generate_totp_secret())
        self.client.force_login(self.persona)

    def test_lo_que_puede_hacer_el_rol(self):
        celdas = {"mediciones": [{"verbo": "aprobar", "condiciones": ["C3"]}], "bitacora": []}
        nombres = {"mediciones": "Mediciones", "bitacora": "Bitácora"}
        with mock.patch.object(motor, "permisos_del_rol", return_value=celdas), mock.patch.object(
            motor, "objetos", return_value=nombres
        ):
            respuesta = self.client.get(reverse("inicio"))
        self.assertContains(respuesta, "Mediciones")
        self.assertContains(respuesta, "aprobar · C3")
        self.assertNotContains(respuesta, "Bitácora")

    def test_t41_sin_motor_el_inicio_tambien_se_frena(self):
        with mock.patch.object(motor, "permisos_del_rol", side_effect=motor.MotorSinRespuesta("x")):
            respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.status_code, 503)
        self.assertContains(respuesta, "Servicio no disponible", status_code=503)
        # La denegación queda en la bitácora aunque la respuesta sea un 503.
        self.assertTrue(
            Registro.objects.filter(resultado="denegado", regla__startswith="K-3", usuario_id=self.persona.pk).exists()
        )

    def test_un_error_de_la_vista_no_deja_nada_escrito(self):
        def _falla(request):
            Periodo.objects.create(nombre="X", inicio=date(2026, 1, 1), fin_medicion=date(2026, 1, 1), cierre_registro=date(2026, 1, 1))
            return HttpResponse(status=500)

        peticion = RequestFactory().get("/")
        peticion.user = self.persona
        peticion.rol_activo = Rol.VER
        ContextoDeBase(_falla)(peticion)
        self.assertFalse(Periodo.objects.filter(nombre="X").exists())


class FormularioDeMuestra(forms.Form):
    parcela = forms.CharField(label="Parcela", max_length=10)
    fecha_medicion = forms.DateField(label="Fecha de la medición", help_text="Dentro del período.")
    toneladas = forms.DecimalField(label="Toneladas de CO₂", min_value=0, decimal_places=2)

    def clean(self):
        raise forms.ValidationError("El período cerró antes de enviar la medición.")


class MuestrarioDeComponentes(TestCase):
    """5.15: los componentes para la fase 5 se arman sin estilos en línea, con el estado dicho con
    ícono y texto, y el resumen de errores enlazado con cada campo."""

    def _muestrario(self):
        peticion = RequestFactory().get("/")
        peticion.user = AnonymousUser()
        peticion.rol_activo = ""
        formulario = FormularioDeMuestra({"parcela": "P-01", "fecha_medicion": "2026-13-40", "toneladas": "-3"})
        return render_to_string("nucleo/muestrario.html", {"form": formulario}, request=peticion)

    def test_resumen_de_errores_enlazado_y_anunciado(self):
        html = self._muestrario()
        self.assertIn('class="resumen-errores" role="alert"', html)
        self.assertIn("Revise 3 datos antes de continuar", html)
        self.assertIn('href="#id_toneladas"', html)
        self.assertIn('href="#id_fecha_medicion"', html)
        self.assertIn("El período cerró antes de enviar la medición.", html)

    def test_sin_estilos_ni_scripts_en_linea(self):
        html = self._muestrario().lower()
        for prohibido in ("style=", "<style", "<script"):
            self.assertNotIn(prohibido, html)

    def test_cada_estado_con_icono_y_texto(self):
        for estado, clase, icono in (
            ("borrador", "insignia-borrador", "○"),
            ("enviada", "insignia-pendiente", "→"),
            ("devuelta", "insignia-aviso", "↩"),
            ("aprobada", "insignia-exito", "✓"),
            ("revocado", "insignia-peligro", "✕"),
            ("sustituida", "insignia-gris", "■"),
        ):
            html = render_to_string("nucleo/_estado.html", {"estado": estado, "texto": estado.capitalize()})
            self.assertIn(clase, html)
            self.assertIn(f'<span aria-hidden="true">{icono}</span> {estado.capitalize()}', html)


class PaginaNoEncontrada(TestCase):
    """5.15: la página 404 propia no dice más que la de Django. No repite la dirección pedida ni
    distingue lo que no existe de lo que el motor niega (T-08 responde lo mismo en los dos casos)."""

    def test_no_repite_la_direccion_ni_dice_la_causa(self):
        respuesta = self.client.get("/fincas/no-existe-7f3a/")
        self.assertContains(respuesta, "No encontramos esta página", status_code=404)
        self.assertNotContains(respuesta, "no-existe-7f3a", status_code=404)
        self.assertNotContains(respuesta, "permiso", status_code=404)

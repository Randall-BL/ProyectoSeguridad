"""Pruebas del punto de cumplimiento (fase 4): los hechos salen de la base, y si el motor no
responde la petición se frena (K-3, T-41)."""

import json
import os
import secrets
import threading
import time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import skipUnless

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from autorizacion import hechos, motor, respuestas
from bitacora.models import Registro
from cuentas.models import Rol, Usuario
from negocio.models import (
    Asignacion,
    EstadoMedicion,
    EstadoPeriodo,
    Finca,
    Medicion,
    Parcela,
    Periodo,
    Titular,
    VersionMedicion,
    Vinculo,
)


class _MotorFalso(BaseHTTPRequestHandler):
    """Un OPA de mentira que se porta como se le pida: lento, roto o con respuestas raras."""

    modo = "bien"

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        modo = type(self).modo
        if modo == "lento":
            time.sleep(3)
        if modo == "error":
            self.send_response(500)
            self.end_headers()
            return
        cuerpos = {
            "bien": {"result": {"resultado": "conceder", "regla": "C3", "avisar": False}},
            "lento": {"result": {"resultado": "conceder", "regla": "C3", "avisar": False}},
            "basura": None,
            "sin_politica": {},
            "inventado": {"result": {"resultado": "permitir", "regla": "C3", "avisar": False}},
        }
        cuerpo = b"{no es json" if cuerpos[modo] is None else json.dumps(cuerpos[modo]).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(cuerpo)
        except ConnectionError:
            pass  # La aplicación ya se había rendido: eso es lo que se prueba.

    def log_message(self, *args):
        pass


class FalloCerrado(TestCase):
    """K-3: sin respuesta válida del motor no hay decisión, ni por omisión ni guardada."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), _MotorFalso)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        super().tearDownClass()

    def _preguntar(self, modo):
        _MotorFalso.modo = modo
        with override_settings(OPA_URL=self.url, OPA_LIMITE=0.5):
            return motor.preguntar({"accion": "aprobar"})

    def test_respuesta_valida(self):
        self.assertEqual(self._preguntar("bien"), motor.Decision("conceder", "C3", False))

    def test_t41_motor_lento_frena_en_el_limite(self):
        inicio = time.monotonic()
        with self.assertRaises(motor.MotorSinRespuesta):
            self._preguntar("lento")
        self.assertLess(time.monotonic() - inicio, 1.5)

    def test_t41_motor_apagado(self):
        with override_settings(OPA_URL="http://127.0.0.1:9", OPA_LIMITE=0.5):
            with self.assertRaises(motor.MotorSinRespuesta):
                motor.preguntar({"accion": "aprobar"})

    def test_error_del_motor(self):
        with self.assertRaises(motor.MotorSinRespuesta):
            self._preguntar("error")

    def test_respuesta_que_no_es_json(self):
        with self.assertRaises(motor.MotorSinRespuesta):
            self._preguntar("basura")

    def test_politica_sin_decision(self):
        with self.assertRaises(motor.MotorSinRespuesta):
            self._preguntar("sin_politica")

    def test_resultado_inventado(self):
        with self.assertRaises(motor.MotorSinRespuesta):
            self._preguntar("inventado")

    def test_sin_motor_responde_503_y_lo_anota(self):
        peticion = RequestFactory().post("/mediciones/1/aprobar")
        SessionMiddleware(lambda r: None).process_request(peticion)
        peticion.user = Usuario.objects.create_user(
            username="ver.prueba", password=secrets.token_urlsafe(18), rol=Rol.VER, identificacion="v"
        )
        peticion.rol_activo = Rol.VER
        respuesta = respuestas.sin_motor(peticion, "aprobar", {"tipo": "mediciones"}, "TimeoutError")
        self.assertEqual(respuesta.status_code, 503)
        registro = Registro.objects.get(accion="aprobar")
        self.assertEqual((registro.resultado, registro.regla), ("denegado", "K-3 motor sin respuesta: TimeoutError"))


def _usuario(nombre, rol):
    return Usuario.objects.create_user(
        username=nombre, password=secrets.token_urlsafe(18), rol=rol, identificacion=nombre
    )


class HechosDesdeLaBase(TestCase):
    """Tarea 4.6: lo que recibe el motor sale de las filas, no de la petición."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = _usuario("tec.ana", Rol.TEC)
        cls.carla = _usuario("ver.carla", Rol.VER)
        cls.bruno = _usuario("ver.bruno", Rol.VER)
        cls.sofia = _usuario("sup.sofia", Rol.SUP)
        cls.titular = Titular.objects.create(codigo="T-900", tipo=Titular.Tipo.FISICA)
        cls.finca = Finca.objects.create(codigo="F-900", nombre="Prueba", titular=cls.titular)
        cls.otra = Finca.objects.create(codigo="F-901", nombre="Ajena", titular=cls.titular)
        cls.parcela = Parcela.objects.create(
            finca=cls.finca, codigo="P-1", geometria="POLYGON((-83.69 9.30,-83.68 9.30,-83.68 9.31,-83.69 9.31,-83.69 9.30))"
        )
        hoy = timezone.localdate()
        cls.periodo = Periodo.objects.create(
            nombre="P-prueba", inicio=hoy - timedelta(days=30), fin_medicion=hoy + timedelta(days=30),
            cierre_registro=hoy + timedelta(days=35), estado=EstadoPeriodo.ABIERTO,
        )
        Asignacion.objects.create(
            tecnico=cls.ana, finca=cls.finca, periodo=cls.periodo, tipo=Asignacion.Tipo.ORDINARIA,
            desde=hoy - timedelta(days=30), creada_por=cls.sofia,
        )
        Vinculo.objects.create(usuario=cls.bruno, titular=cls.titular, tipo=Vinculo.Tipo.FAMILIAR)
        # T-06: C escribió la versión 1 y A la versión 2.
        cls.medicion = Medicion.objects.create(
            parcela=cls.parcela, periodo=cls.periodo, estado=EstadoMedicion.ENVIADA, creada_por=cls.carla
        )
        for numero, autor in ((1, cls.carla), (2, cls.ana)):
            VersionMedicion.objects.create(
                medicion=cls.medicion, numero=numero, autor=autor, fecha_medicion=hoy - timedelta(days=5),
                arboles=100, dap_promedio_cm="20.00", altura_promedio_m="12.00", toneladas_co2="10.000",
            )

    def _peticion(self, usuario, rol):
        peticion = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(peticion)
        peticion.user = usuario
        peticion.rol_activo = rol
        return peticion

    def test_fincas_asignadas_del_tecnico(self):
        sujeto, _, parametros, _ = hechos.del_sujeto(self._peticion(self.ana, Rol.TEC))
        self.assertEqual(sujeto["fincas_asignadas"], [str(self.finca.pk)])
        self.assertEqual(sujeto["id"], str(self.ana.pk))
        self.assertEqual(parametros["max_asignaciones_activas"], 20)

    def test_vinculos_declarados(self):
        sujeto, *_ = hechos.del_sujeto(self._peticion(self.bruno, Rol.VER))
        self.assertEqual(sujeto["titulares_con_vinculo"], [str(self.titular.pk)])

    def test_tecnicos_a_cargo(self):
        Usuario.objects.filter(pk=self.ana.pk).update(supervisor=self.sofia)
        sujeto, *_ = hechos.del_sujeto(self._peticion(self.sofia, Rol.SUP))
        self.assertEqual(sujeto["tecnicos_a_cargo"], [str(self.ana.pk)])

    def test_autores_de_todas_las_versiones(self):
        objeto = hechos.de_medicion(self.medicion.pk, self.ana.pk)
        self.assertEqual(sorted(objeto["autores"]), sorted([str(self.carla.pk), str(self.ana.pk)]))
        self.assertEqual((objeto["estado"], objeto["periodo_estado"]), ("enviada", "abierto"))
        self.assertEqual(objeto["finca"], str(self.finca.pk))

    def test_la_finca_nueva_y_el_historial(self):
        _, historial, _, hoy = hechos.del_sujeto(self._peticion(self.bruno, Rol.VER), self.otra.pk)
        self.assertTrue(historial["finca_nueva"])
        self.assertEqual(historial["fincas_24h"], 0)
        self.assertEqual(hoy, str(timezone.localdate()))

    def test_objeto_inexistente(self):
        self.assertIsNone(hechos.de_medicion("00000000-0000-0000-0000-000000000000", self.ana.pk))

    def test_la_aplicacion_puede_preguntar_los_hechos(self):
        """Con los permisos de va_app y sin rol en la transacción, los hechos se calculan igual."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE va_app")
        objeto = hechos.de_medicion(self.medicion.pk, self.ana.pk)
        self.assertEqual(len(objeto["autores"]), 2)

    @skipUnless(os.environ.get("OPA_PRUEBAS"), "requiere el motor real en OPA_URL")
    def test_con_el_motor_real_t05_y_t06(self):
        objeto = hechos.de_medicion(self.medicion.pk, self.bruno.pk)
        bruno = self._peticion(self.bruno, Rol.VER)
        # B tiene vínculo con el titular en estos datos: C17 manda primero.
        self.assertEqual(motor.preguntar(hechos.entrada(bruno, "aprobar", objeto)).regla, "C17")
        Vinculo.objects.filter(usuario=self.bruno).update(retirado_en=timezone.now())
        decision = motor.preguntar(hechos.entrada(bruno, "aprobar", objeto))
        self.assertIn(decision.resultado, {"conceder", "pedir_segundo_factor"})
        carla = self._peticion(self.carla, Rol.VER)
        self.assertEqual(motor.preguntar(hechos.entrada(carla, "aprobar", objeto)).regla, "C3")

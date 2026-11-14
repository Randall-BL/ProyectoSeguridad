"""8.6, cambio de identificador (IDOR, criterio de aceptación 3): con cada rol, cada ruta que recibe
un identificador se pide con el de un objeto ajeno y con uno que no existe.

- Nada se ejecuta fuera de lo que la matriz y el alcance permiten: ningún cambio en la base.
- Para los roles con alcance (TEC por sus fincas, C1; DUE por su titular, C5), un objeto ajeno
  responde exactamente igual que uno inexistente (T-08): la respuesta no revela qué existe.

Las peticiones corren como va_app, con la seguridad por fila activa, igual que en producción: pasan
por el motor real, la vista y la base."""

import uuid
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from unittest import skipUnless

from django.db import connection
from django.urls import reverse

from cuentas.models import PropuestaRol, Usuario
from flujos.tests import MATRIZ, MOTIVO, _opa_disponible, _rutas
from flujos.tests_casos import PERSONAJES, ConPersonajes
from flujos.tests_certificados import como, emitir
from negocio.models import (
    Alerta,
    Asignacion,
    Certificado,
    DatosPersonales,
    Enmienda,
    Finca,
    Medicion,
    Parcela,
    Periodo,
    PropuestaCatalogo,
    PropuestaPeriodo,
    VersionMedicion,
    Vinculo,
)

if emitir is not None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CON_ALCANCE = {"TEC", "DUE"}
# Los objetos que C1 y C5 recortan por finca o por titular. Períodos, cuentas y alertas no tienen ese
# alcance: si la matriz deja leerlos, se leen enteros.
CON_FINCA = {"finca", "parcela", "medicion", "enmienda", "certificado"}


@contextmanager
def como_la_aplicacion():
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE va_app")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


@skipUnless(_opa_disponible() and MATRIZ.exists(), "requiere el motor real (OPA) y matriz.json")
class IdentificadorAjeno(ConPersonajes):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        u = {n: Usuario.objects.get(username=n) for n in
             ("tec.tomas", "ver.diego", "ger.gabriela", "adm.alberto", "ger.gerardo", "ver.bruno")}
        # Todo sobre F-002: fuera del alcance de A (tec.ana, su temporal venció) y de D (due.daniel).
        f002 = Finca.objects.get(codigo="F-002")
        parcela = Parcela.objects.get(finca=f002, codigo="P-1", activa=True)
        ii = Periodo.objects.get(nombre="2026-II")
        m = Medicion.objects.create(parcela=parcela, periodo=ii, creada_por=u["tec.tomas"])
        v = VersionMedicion.objects.create(medicion=m, numero=1, autor=u["tec.tomas"], fecha_medicion=date(2026, 9, 1),
                                           arboles=50, dap_promedio_cm=Decimal("15"), altura_promedio_m=Decimal("9"),
                                           toneladas_co2=Decimal("12.000"))
        Medicion.objects.filter(pk=m.pk).update(version_vigente=v)
        Medicion.objects.filter(pk=m.pk).update(estado="enviada")
        Medicion.objects.filter(pk=m.pk).update(estado="aprobada", aprobada_por=u["ver.diego"])
        e = Enmienda.objects.create(medicion=m, solicitada_por=u["ger.gabriela"], motivo="x", evidencia="x",
                                    responsable=u["tec.tomas"])
        if emitir is not None:
            with como("va_emision") as conexion:
                emitir.emitir(conexion, m.pk, Ed25519PrivateKey.generate())
        cls.ids = {
            "finca": f002.pk, "parcela": parcela.pk, "titular": f002.titular_id, "periodo": ii.pk,
            "medicion": m.pk, "enmienda": e.pk, "cuenta": u["ger.gerardo"].pk,
            "asignacion": Asignacion.objects.filter(tecnico=u["tec.tomas"]).first().pk,
            "alerta": Alerta.objects.create(sujeto=u["tec.tomas"], control="H1", nivel="aviso").pk,
            "vinculo": Vinculo.objects.get(usuario=u["ver.bruno"]).pk,
            "propuesta_catalogo": PropuestaCatalogo.objects.first().pk,
            "propuesta_periodo": PropuestaPeriodo.objects.create(periodo=ii, accion="cerrar", registrada_por=u["adm.alberto"]).pk,
            "propuesta_rol": PropuestaRol.objects.create(usuario=u["tec.tomas"], rol="SUP", propuesta_por=u["adm.alberto"]).pk,
        }
        certificado = Certificado.objects.filter(medicion=m).first()
        if certificado:
            cls.ids["certificado"] = certificado.pk

    def _id(self, ruta):
        nombre = ruta.pattern.converters and next(iter(ruta.pattern.converters))
        if nombre == "propuesta":
            nombre = {"aprobar_catalogo": "propuesta_catalogo", "aprobar_rol": "propuesta_rol"}.get(ruta.name, "propuesta_periodo")
        return self.ids.get(nombre)

    solo_post: set[str] = set()

    def _pedir(self, ruta, identificador):
        """GET, o POST si la ruta solo acepta POST (se recuerda para no repetir el 405)."""
        url = reverse(ruta.name, args=[identificador])
        if ruta.name not in self.solo_post:
            respuesta = self.client.get(url, MOTIVO)
            if respuesta.status_code != 405:
                return respuesta.status_code
            self.solo_post.add(ruta.name)
        datos = {**MOTIVO, "observaciones": "x", "resolucion": "x", "accion": "cerrar"}
        return self.client.post(url, datos).status_code

    def _estado(self):
        """Lo que un cambio de identificador podría alterar."""
        return (
            sorted(Medicion.objects.values_list("id", "estado", "aprobada_por_id")),
            sorted(Enmienda.objects.values_list("id", "estado")),
            sorted(Usuario.objects.values_list("id", "rol", "is_active")),
            sorted(PropuestaRol.objects.values_list("id", "estado")),
            sorted(PropuestaPeriodo.objects.values_list("id", "estado")),
            sorted(PropuestaCatalogo.objects.values_list("id", "estado")),
            sorted(Periodo.objects.values_list("id", "estado")),
            sorted(Asignacion.objects.values_list("id", "terminada_en")),
            sorted(Alerta.objects.values_list("id", "resuelta_en")),
            sorted(DatosPersonales.objects.values_list("titular_id", "nombre", "suprimido_en")),
            sorted(Vinculo.objects.values_list("id", "retirado_en")),
            sorted(Certificado.objects.values_list("id", "estado")),
        )

    def test_con_cada_rol_un_identificador_ajeno_no_da_nada(self):
        import json

        matriz = json.loads(MATRIZ.read_text(encoding="utf-8"))["matriz"]
        rutas = [r for r in _rutas() if getattr(r.callback, "protegida", None) and r.pattern.converters]
        antes = self._estado()
        revisadas = 0
        for rol, usuario in PERSONAJES.items():
            self._como(usuario, rol)
            concedidos = {(p["verbo"], objeto) for objeto, lista in matriz["celdas"].get(rol, {}).items() for p in lista}
            with como_la_aplicacion():
                for ruta in rutas:
                    identificador = self._id(ruta)
                    if identificador is None:
                        continue
                    permitido = ruta.callback.protegida in concedidos
                    recortado = rol in CON_ALCANCE and next(iter(ruta.pattern.converters)) in CON_FINCA
                    if permitido and not recortado:
                        continue  # lo ve entero por la matriz: su caso feliz está en 8.3
                    with self.subTest(rol=rol, ruta=ruta.name):
                        ajeno = self._pedir(ruta, identificador)
                        inexistente = self._pedir(ruta, uuid.uuid4())
                        self.assertNotIn(ajeno, (200, 302), f"{rol} obtuvo {ajeno} en {ruta.name} con un objeto ajeno")
                        self.assertNotIn(inexistente, (200, 302, 500))
                        if rol in CON_ALCANCE:  # ni con el verbo ni sin él se distingue qué existe
                            self.assertEqual(ajeno, inexistente, f"{rol} distingue lo ajeno de lo inexistente en {ruta.name}")
                        revisadas += 1
        self.assertEqual(self._estado(), antes)
        self.assertGreater(revisadas, 100)
        print(f"\n8.6: {revisadas} combinaciones de rol y ruta con un identificador ajeno")

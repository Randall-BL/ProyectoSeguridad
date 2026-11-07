"""Carga los datos de prueba con los personajes de los casos T-01 a T-41 (tareas 2.8 y 2.9).

Las contraseñas nunca están en el repositorio. Salen de una de tres formas:

* ``--salida RUTA``: se generan y se escriben en un archivo nuevo fuera del repositorio.
* ``SEMILLA_CONTRASENA``: todas las cuentas usan la de esa variable (solo para la base local).
* Sin ninguna de las dos: se generan y se imprimen una sola vez, y solo en una terminal, para que
  no terminen en un registro de Cloud Run o de CI.

Se corre con el usuario dueño de la base, una sola vez por base:

    python manage.py sembrar --salida ../../cuentas_prueba.txt
"""

import os
import secrets
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from bitacora.registro import anexar
from cuentas.models import Declaracion, EstadoPropuesta, PropuestaRol, Rol, Usuario
from negocio.models import (
    Asignacion,
    DatosPersonales,
    EstadoCatalogo,
    EstadoMedicion,
    EstadoPeriodo,
    Finca,
    Medicion,
    Parcela,
    Periodo,
    PropuestaCatalogo,
    PropuestaPeriodo,
    Representacion,
    Titular,
    VersionMedicion,
    Vinculo,
)

DOMINIO = "verdeazul.example"

# Usuario, nombre, apellidos, rol, y el papel que cumple en los casos de la matriz.
PERSONAS = [
    ("tec.ana", "Ana", "Quesada Mora", Rol.TEC, "técnica A: T-01 a T-05, T-11, T-13, T-27, T-30"),
    ("tec.tomas", "Tomás", "Arias Vindas", Rol.TEC, "segundo técnico: 20 asignaciones activas (T-38, T-39)"),
    ("ver.bruno", "Bruno", "Solís Badilla", Rol.VER, "verificador B: T-05, T-14, T-17 a T-19, T-29, T-33, T-34"),
    ("ver.carla", "Carla", "Jiménez Ureña", Rol.TEC, "verificadora C, antes técnica: T-06, T-12, T-26"),
    ("ver.diego", "Diego", "Vargas Fallas", Rol.VER, "tercer verificador, sin conflicto con nadie"),
    ("sup.sofia", "Sofía", "Rojas Elizondo", Rol.SUP, "supervisora S: T-27, T-28, T-36, T-38, T-39"),
    ("ger.gabriela", "Gabriela", "Chaves Monge", Rol.GER, "gerente G: T-12, T-24"),
    ("ger.gerardo", "Gerardo", "Alfaro Céspedes", Rol.GER, "segundo gerente, autoriza lo que G solicitó (T-24)"),
    ("adm.alberto", "Alberto", "Navarro Picado", Rol.ADM, "administrador: T-15, T-16, T-22, T-37"),
    ("aud.elena", "Elena", "Castro Brenes", Rol.AUD, "auditora E con ventana vigente: T-09, T-10, T-31"),
    ("due.daniel", "Daniel", "Umaña Calderón", Rol.DUE, "dueño D, persona física (titular T-001): T-08"),
    ("due.rosa", "Rosa", "Brenes Zúñiga", Rol.DUE, "representante de la sociedad T-002: T-08"),
]

# Ventana de la auditora (C6): vigente desde ayer y por 30 días, contados desde el día de la carga.
VENTANA_AUDITORIA_DIAS = 30

# Código, tipo, nombre e identificación. Todos son ficticios; las identificaciones usan el tomo 0000,
# que no existe.
TITULARES = [
    ("T-001", Titular.Tipo.FISICA, "Daniel Umaña Calderón", "0-0000-0011"),  # la cuenta due.daniel
    ("T-002", Titular.Tipo.SOCIEDAD, "Agroforestal Chirripó S.A.", "3-101-000002"),  # la representa due.rosa
    ("T-003", Titular.Tipo.FISICA, "Marta Elizondo Fallas", "1-0000-0003"),
    ("T-004", Titular.Tipo.FISICA, "Luis Solís Badilla", "1-0000-0004"),  # pariente de ver.bruno (T-29)
    ("T-005", Titular.Tipo.SOCIEDAD, "Cafetalera Los Ángeles de Rivas S.A.", "3-101-000005"),
    ("T-006", Titular.Tipo.FISICA, "Jorge Monge Vindas", "1-0000-0006"),
    ("T-007", Titular.Tipo.FISICA, "Lidia Calderón Picado", "1-0000-0007"),
    ("T-008", Titular.Tipo.SOCIEDAD, "Reforestadora Peñas Blancas S.R.L.", "3-102-000008"),
]

# Las cinco fincas que nombran los casos (F1, F2 y F5 en la matriz) y veinte más: H1 y H3 cuentan
# fincas distintas (T-18, T-19, T-33) y K-1 necesita 21 fincas para la asignación número 21 (T-38).
FINCAS_DE_LOS_CASOS = [
    ("F-001", "La Esperanza", "T-001", "Daniel Flores"),
    ("F-002", "Los Cedros", "T-002", "Rivas"),
    ("F-003", "El Roble", "T-002", "San Pedro"),
    ("F-004", "Quebrada Honda", "T-003", "Platanares"),
    ("F-005", "Santa Elena", "T-004", "Pejibaye"),
]
OTRAS_FINCAS = [
    "Las Brisas", "El Guayabo", "La Palma", "Monte Claro", "Río Blanco", "El Jilguero", "La Ceiba",
    "Los Guarumos", "Los Laureles", "El Porvenir", "El Quetzal", "San Rafael", "Las Nubes",
    "El Higuerón", "La Trinidad", "Los Almendros", "El Manantial", "La Colina", "Cerro Azul", "El Bosque",
]
TITULARES_DE_OTRAS = ["T-003", "T-005", "T-006", "T-007", "T-008"]
DISTRITOS = [
    "San Isidro de El General", "El General", "Daniel Flores", "Rivas", "San Pedro", "Platanares",
    "Pejibaye", "Cajón", "Barú", "Río Nuevo", "Páramo", "La Amistad",
]

# Esquina de la cuadrícula de fincas, al sureste de San Isidro de El General (grados WGS 84).
ORIGEN_LON, ORIGEN_LAT, CELDA = -83.69, 9.30, 0.01

# Nombre, inicio, fin de medición y cierre de registro (P-22). 2026-I se cierra al final de la carga.
PERIODOS = [
    ("2026-I", date(2026, 1, 5), date(2026, 6, 12), date(2026, 6, 19)),
    ("2026-II", date(2026, 7, 1), date(2026, 12, 11), date(2026, 12, 18)),
]


class Command(BaseCommand):
    help = "Carga los personajes y los datos de prueba de la matriz (una sola vez por base)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--salida",
            type=Path,
            help="Archivo nuevo, fuera del repositorio, donde quedan las contraseñas generadas.",
        )

    def handle(self, *args, salida=None, **opciones):
        self._revisar_conexion()
        if salida is not None:
            salida = salida.expanduser().resolve()
            if _dentro_del_repositorio(salida):
                raise CommandError("El archivo de contraseñas no puede quedar dentro del repositorio.")
            if salida.exists():
                raise CommandError(f"{salida} ya existe: no se sobrescribe.")
        compartida = os.environ.get("SEMILLA_CONTRASENA")
        if salida is None and not compartida and not self.stdout.isatty():
            raise CommandError(
                "Sin --salida ni SEMILLA_CONTRASENA, las contraseñas solo se imprimen en una terminal."
            )

        with transaction.atomic():
            if Usuario.objects.filter(username__in=[p[0] for p in PERSONAS]).exists():
                raise CommandError("Esta base ya tiene los datos de prueba.")
            self.ahora = timezone.now()
            self.hoy = timezone.localdate()
            claves = self._personas(compartida)
            self._catalogo()
            self._periodos()
            self._primer_periodo()
            self._cerrar_periodo("2026-I")
            self._segundo_periodo()
            self._declaraciones()
            resumen = {
                "usuarios": len(PERSONAS),
                "titulares": len(self.titulares),
                "fincas": len(self.fincas),
                "parcelas": Parcela.objects.count(),
                "periodos": len(self.periodos),
                "asignaciones": Asignacion.objects.count(),
                "mediciones": Medicion.objects.count(),
            }
            anexar(
                accion="sembrar",
                resultado="concedido",
                rol="SIS",
                objeto_tipo="base",
                origen="manage.py sembrar",
                despues=resumen,
            )
            # Dentro de la transacción: si el archivo no se puede escribir, no quedan cuentas con
            # contraseñas que nadie conoce.
            if salida is not None and not compartida:
                _escribir_privado(salida, _tabla(claves))

        self.stdout.write("Cargado: " + ", ".join(f"{valor} {clave}" for clave, valor in resumen.items()))
        if compartida:
            self.stdout.write(f"{len(PERSONAS)} cuentas creadas con la contraseña de SEMILLA_CONTRASENA.")
        elif salida is not None:
            self.stdout.write(f"{len(PERSONAS)} cuentas creadas; contraseñas en {salida}")
        else:
            self.stdout.write(_tabla(claves))
            self.stdout.write("Guárdelas ahora: no se vuelven a mostrar.")

    # --- Comprobaciones -----------------------------------------------------------------------

    def _revisar_conexion(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            usuario = cursor.fetchone()[0]
        if usuario.startswith("va_"):
            raise CommandError(
                f"Conectado como {usuario}: la semilla se corre con el usuario dueño de la base."
            )

    # --- Personas -----------------------------------------------------------------------------

    def _personas(self, compartida):
        self.u = {}
        claves = []
        for numero, (usuario, nombre, apellidos, rol, _papel) in enumerate(PERSONAS, start=1):
            persona = Usuario(
                username=usuario,
                first_name=nombre,
                last_name=apellidos,
                email=f"{usuario}@{DOMINIO}",
                rol=rol,
                identificacion=f"0-0000-{numero:04d}",
            )
            if rol == Rol.AUD:
                persona.vigente_desde = self.ahora - timedelta(days=1)
                persona.vigente_hasta = self.ahora + timedelta(days=VENTANA_AUDITORIA_DIAS)
            clave = compartida or _clave_nueva(persona)
            try:
                validate_password(clave, persona)
            except ValidationError as error:
                raise CommandError(f"La contraseña no sirve para {usuario}: {' '.join(error.messages)}")
            persona.set_password(clave)
            persona.save()
            self.u[usuario] = persona
            claves.append((usuario, rol, clave))

        for tecnico in ("tec.ana", "tec.tomas", "ver.carla"):
            self.u[tecnico].supervisor = self.u["sup.sofia"]
            self.u[tecnico].save(update_fields=["supervisor"])

        # Cada rol lo propuso ADM y lo aprobó GER (C12). La cuenta de ADM es la inicial de la
        # instalación; las de los gerentes las aprueba el otro gerente.
        adm, gabriela, gerardo = self.u["adm.alberto"], self.u["ger.gabriela"], self.u["ger.gerardo"]
        for persona in self.u.values():
            if persona is adm:
                continue
            self._propuesta_rol(persona, persona.rol, aprobada_por=gerardo if persona is gabriela else gabriela)
        return claves

    def _propuesta_rol(self, persona, rol, *, aprobada_por):
        return PropuestaRol.objects.create(
            usuario=persona,
            rol=rol,
            propuesta_por=self.u["adm.alberto"],
            estado=EstadoPropuesta.APROBADA,
            aprobada_por=aprobada_por,
            aprobada_en=self.ahora,
        )

    def _carla_pasa_a_verificadora(self):
        """C fue técnica y después pasó a verificadora con una propuesta aprobada (T-06)."""
        carla = self.u["ver.carla"]
        self._propuesta_rol(carla, Rol.VER, aprobada_por=self.u["ger.gabriela"])
        carla.rol = Rol.VER
        carla.save(update_fields=["rol"])

    # --- Titulares, fincas y parcelas ---------------------------------------------------------

    def _catalogo(self):
        self.titulares = {}
        for codigo, tipo, nombre, identificacion in TITULARES:
            titular = Titular.objects.create(codigo=codigo, tipo=tipo)
            DatosPersonales.objects.create(
                titular=titular,
                nombre=nombre,
                identificacion=identificacion,
                correo=f"{codigo.lower()}@titulares.{DOMINIO}",
                direccion="Pérez Zeledón, San José",
            )
            self.titulares[codigo] = titular

        # C5: D es el titular de T-001; R representa a la sociedad T-002 con un poder escrito.
        Representacion.objects.create(
            usuario=self.u["due.daniel"], titular=self.titulares["T-001"], desde=date(2026, 1, 1)
        )
        Representacion.objects.create(
            usuario=self.u["due.rosa"],
            titular=self.titulares["T-002"],
            desde=date(2026, 1, 1),
            documento="Poder especial de la junta directiva, acta 14-2026",
        )

        self.fincas = {}
        for indice, (codigo, nombre, titular, distrito) in enumerate(_fincas()):
            finca = Finca.objects.create(
                codigo=codigo,
                nombre=f"Finca {nombre}",
                titular=self.titulares[titular],
                ubicacion=f"{distrito}, Pérez Zeledón",
                estado=EstadoCatalogo.APROBADO,
            )
            self._catalogo_aprobado(PropuestaCatalogo.Tipo.ALTA_FINCA, finca)
            for numero, poligono in enumerate(_parcelas(indice), start=1):
                parcela = Parcela.objects.create(
                    finca=finca,
                    codigo=f"P-{numero}",
                    geometria=poligono,
                    activa=True,
                    estado=EstadoCatalogo.APROBADO,
                )
                self._catalogo_aprobado(PropuestaCatalogo.Tipo.GEOMETRIA, finca, parcela)
            self.fincas[codigo] = finca

    def _catalogo_aprobado(self, tipo, finca, parcela=None):
        """C11: ADM propone el alta y GER la aprueba."""
        PropuestaCatalogo.objects.create(
            tipo=tipo,
            finca=finca,
            parcela=parcela,
            propuesta_por=self.u["adm.alberto"],
            estado=EstadoCatalogo.APROBADO,
            aprobada_por=self.u["ger.gabriela"],
            aprobada_en=self.ahora,
        )

    # --- Períodos -----------------------------------------------------------------------------

    def _periodos(self):
        self.periodos = {}
        for nombre, inicio, fin_medicion, cierre_registro in PERIODOS:
            periodo = Periodo.objects.create(
                nombre=nombre,
                inicio=inicio,
                fin_medicion=fin_medicion,
                cierre_registro=cierre_registro,
                estado=EstadoPeriodo.ABIERTO,
            )
            self._periodo_aprobado(periodo, PropuestaPeriodo.Accion.ABRIR)
            self.periodos[nombre] = periodo

    def _cerrar_periodo(self, nombre):
        """C14: ADM registra el cierre y GER lo aprueba. Los borradores nunca enviados quedan
        excluidos; lo enviado se sigue revisando después del cierre (P-06, T-17)."""
        periodo = self.periodos[nombre]
        self._periodo_aprobado(periodo, PropuestaPeriodo.Accion.CERRAR)
        Medicion.objects.filter(periodo=periodo, estado=EstadoMedicion.BORRADOR).update(
            estado=EstadoMedicion.EXCLUIDA
        )
        periodo.estado = EstadoPeriodo.CERRADO
        periodo.save(update_fields=["estado"])

    def _periodo_aprobado(self, periodo, accion):
        PropuestaPeriodo.objects.create(
            periodo=periodo,
            accion=accion,
            registrada_por=self.u["adm.alberto"],
            estado=EstadoCatalogo.APROBADO,
            aprobada_por=self.u["ger.gabriela"],
            aprobada_en=self.ahora,
        )

    # --- Asignaciones y mediciones ------------------------------------------------------------

    def _primer_periodo(self):
        """2026-I, antes del cierre: una medición aprobada y otra enviada que nadie alcanzó a
        revisar. Esa la aprueba B después del cierre (P-06, T-17)."""
        self._asignar("tec.ana", "F-001", "2026-I")
        self._asignar("tec.ana", "F-004", "2026-I")
        self._medicion(
            "F-001", "P-1", "2026-I", [("tec.ana", date(2026, 3, 18), 118, "24.60", "13.80")],
            estado=EstadoMedicion.APROBADA, aprobada_por="ver.bruno",
        )
        self._medicion(
            "F-004", "P-1", "2026-I", [("tec.ana", date(2026, 6, 2), 164, "21.30", "12.40")],
            estado=EstadoMedicion.ENVIADA,
        )

    def _segundo_periodo(self):
        # T-06: C midió F-003 como técnica (versión 1), pasó a verificadora y A completó la
        # medición (versión 2). Al intentar aprobarla, C figura entre los autores.
        asignacion_de_carla = self._asignar("ver.carla", "F-003", "2026-II")
        asignacion_de_carla.terminada_en = self.ahora
        asignacion_de_carla.save(update_fields=["terminada_en"])
        self._carla_pasa_a_verificadora()

        self._asignar("tec.ana", "F-001", "2026-II")
        self._asignar("tec.ana", "F-004", "2026-II")
        self._asignar("tec.ana", "F-003", "2026-II", desde=date(2026, 8, 3))
        # T-27: S le dio a A tres días en F-002 y ya vencieron. F-002 no tiene otra asignación (T-02).
        self._asignar(
            "tec.ana", "F-002", "2026-II",
            desde=self.hoy - timedelta(days=3), hasta=self.hoy - timedelta(days=1),
            motivo="Visita extraordinaria pedida por el titular",
        )
        # T-38: T llega al máximo de 20 asignaciones activas (K-1). F-025 queda libre para la 21.
        for numero in range(5, 25):
            self._asignar("tec.tomas", f"F-{numero:03d}", "2026-II")

        # T-05 y T-03: enviada por A; B la puede aprobar y A ya no la puede cambiar.
        self._medicion(
            "F-001", "P-1", "2026-II", [("tec.ana", date(2026, 9, 15), 121, "25.10", "14.20")],
            estado=EstadoMedicion.ENVIADA,
        )
        # T-01 y T-04: un borrador de A en el período abierto.
        self._medicion("F-001", "P-2", "2026-II", [("tec.ana", date(2026, 10, 20), 96, "22.80", "13.10")])
        self._medicion(
            "F-003", "P-1", "2026-II",
            [
                ("ver.carla", date(2026, 7, 21), 140, "23.40", "12.90"),
                ("tec.ana", date(2026, 8, 12), 143, "23.50", "13.00"),
            ],
            estado=EstadoMedicion.ENVIADA,
        )
        # T-29: medición de F-005, cuyo titular es pariente de B.
        self._medicion(
            "F-005", "P-1", "2026-II", [("tec.tomas", date(2026, 9, 30), 133, "26.20", "15.10")],
            estado=EstadoMedicion.ENVIADA,
        )

    def _asignar(self, tecnico, finca, periodo, *, desde=None, hasta=None, motivo=""):
        """C19: la crea SUP, nunca el mismo técnico; la temporal lleva motivo y fecha de fin."""
        return Asignacion.objects.create(
            tecnico=self.u[tecnico],
            finca=self.fincas[finca],
            periodo=self.periodos[periodo],
            tipo=Asignacion.Tipo.TEMPORAL if hasta else Asignacion.Tipo.ORDINARIA,
            motivo=motivo,
            desde=desde or self.periodos[periodo].inicio,
            hasta=hasta,
            creada_por=self.u["sup.sofia"],
        )

    def _medicion(self, finca, parcela, periodo, versiones, *, estado=EstadoMedicion.BORRADOR, aprobada_por=None):
        """Crea la medición con sus versiones (autor, fecha de medición, árboles, DAP y altura) y la
        lleva al estado pedido por el mismo camino que la aplicación: los disparadores de C2, C3 y
        K-2 revisan cada paso."""
        medicion = Medicion.objects.create(
            parcela=Parcela.objects.get(finca=self.fincas[finca], codigo=parcela, activa=True),
            periodo=self.periodos[periodo],
            creada_por=self.u[versiones[0][0]],
        )
        for numero, (autor, fecha, arboles, dap, altura) in enumerate(versiones, start=1):
            version = VersionMedicion.objects.create(
                medicion=medicion,
                numero=numero,
                autor=self.u[autor],
                fecha_medicion=fecha,
                arboles=arboles,
                dap_promedio_cm=Decimal(dap),
                altura_promedio_m=Decimal(altura),
                toneladas_co2=_toneladas_referencia(arboles, Decimal(dap), Decimal(altura)),
            )
        medicion.version_vigente = version
        medicion.save(update_fields=["version_vigente"])
        if estado in (EstadoMedicion.ENVIADA, EstadoMedicion.APROBADA):
            medicion.estado = EstadoMedicion.ENVIADA
            medicion.save(update_fields=["estado"])
        if estado == EstadoMedicion.APROBADA:
            medicion.estado = EstadoMedicion.APROBADA
            medicion.aprobada_por = self.u[aprobada_por]
            medicion.aprobada_en = self.ahora
            medicion.save(update_fields=["estado", "aprobada_por", "aprobada_en"])
        return medicion

    # --- Declaraciones de vínculos ------------------------------------------------------------

    def _declaraciones(self):
        """POL-CA-14: el personal declara sus vínculos. B declara que el titular de F-005 es
        pariente suyo, así que se abstiene de decidir sobre esa finca (C17, T-29)."""
        for persona in self.u.values():
            if persona.rol == Rol.DUE:
                continue
            tiene_vinculo = persona.username == "ver.bruno"
            Declaracion.objects.create(usuario=persona, sin_vinculos=not tiene_vinculo)
        Vinculo.objects.create(
            usuario=self.u["ver.bruno"], titular=self.titulares["T-004"], tipo=Vinculo.Tipo.FAMILIAR
        )


# --- Datos de campo -----------------------------------------------------------------------------


def _toneladas_referencia(arboles, dap_cm, altura_m):
    """Solo para que los datos de prueba sean verosímiles: biomasa aérea por árbol con la ecuación
    pantropical de Chave et al. (2014), densidad de madera 0,6 g/cm³, 47 % de carbono y 44/12 para
    pasar a CO₂. La aplicación no calcula toneladas: las registra el técnico."""
    biomasa_kg = 0.0673 * (0.6 * float(dap_cm) ** 2 * float(altura_m)) ** 0.976
    co2_t = arboles * biomasa_kg * 0.47 * 44 / 12 / 1000
    return Decimal(str(round(co2_t, 3)))


# --- Geometría ----------------------------------------------------------------------------------


def _fincas():
    yield from FINCAS_DE_LOS_CASOS
    for numero, nombre in enumerate(OTRAS_FINCAS, start=len(FINCAS_DE_LOS_CASOS) + 1):
        titular = TITULARES_DE_OTRAS[numero % len(TITULARES_DE_OTRAS)]
        yield f"F-{numero:03d}", nombre, titular, DISTRITOS[(numero + 3) % len(DISTRITOS)]


def _parcelas(indice):
    """Dos parcelas de unas 11 ha por finca, cada finca en su celda de una cuadrícula de 5 × 5:
    ninguna parcela activa se traslapa con otra (C11)."""
    x = ORIGEN_LON + (indice % 5) * CELDA
    y = ORIGEN_LAT + (indice // 5) * CELDA
    return [_rectangulo(x + 0.001, y + 0.001, 0.003, 0.003), _rectangulo(x + 0.005, y + 0.001, 0.003, 0.0035)]


def _rectangulo(x, y, ancho, alto):
    esquinas = [(x, y), (x + ancho, y), (x + ancho, y + alto), (x, y + alto), (x, y)]
    return "POLYGON((" + ",".join(f"{lon:.4f} {lat:.4f}" for lon, lat in esquinas) + "))"


# --- Contraseñas --------------------------------------------------------------------------------


def _clave_nueva(persona):
    """20 caracteres al azar que pasen los validadores de POL-AU-01."""
    while True:
        clave = secrets.token_urlsafe(15)
        try:
            validate_password(clave, persona)
            return clave
        except ValidationError:
            continue


def _tabla(claves):
    ancho = max(len(u) for u, _, _ in claves)
    filas = [f"{'usuario'.ljust(ancho)}  rol  contraseña"]
    filas += [f"{u.ljust(ancho)}  {r}  {c}" for u, r, c in claves]
    return "\n".join(filas) + "\n"


def _dentro_del_repositorio(ruta):
    raices = [Path(settings.BASE_DIR).resolve()]
    if (raices[0].parent / ".git").exists():
        raices.append(raices[0].parent)
    return any(ruta == raiz or raiz in ruta.parents for raiz in raices)


def _escribir_privado(ruta, texto):
    """Crea el archivo sin permisos para otros usuarios y falla si ya existe."""
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(texto)

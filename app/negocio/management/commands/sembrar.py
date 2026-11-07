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
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from bitacora.registro import anexar
from cuentas.models import EstadoPropuesta, PropuestaRol, Rol, Usuario
from negocio.models import (
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
            self._cerrar_periodo("2026-I")
            self._carla_pasa_a_verificadora()
            resumen = {
                "usuarios": len(PERSONAS),
                "titulares": len(self.titulares),
                "fincas": len(self.fincas),
                "parcelas": Parcela.objects.count(),
                "periodos": len(self.periodos),
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

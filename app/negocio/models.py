"""Los objetos de negocio de la matriz (Entregable 3, §1.2): fincas y parcelas, datos personales
del dueño, períodos, asignaciones, mediciones, enmiendas, certificados y alertas de historial.
Nada de esto se borra: los cambios son versiones nuevas o cambios de estado."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import TruncDate

from .campos import Poligono

USUARIO = settings.AUTH_USER_MODEL


class EstadoCatalogo(models.TextChoices):
    PROPUESTO = "propuesto", "Propuesto"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"


class EstadoPeriodo(models.TextChoices):
    PLANIFICADO = "planificado", "Planificado"
    ABIERTO = "abierto", "Abierto"
    CERRADO = "cerrado", "Cerrado"


class EstadoMedicion(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    ENVIADA = "enviada", "Enviada"
    DEVUELTA = "devuelta", "Devuelta"
    APROBADA = "aprobada", "Aprobada"
    EXCLUIDA = "excluida", "Excluida"
    SUSTITUIDA = "sustituida", "Sustituida"


class EstadoEnmienda(models.TextChoices):
    SOLICITADA = "solicitada", "Solicitada"
    CORREGIDA = "corregida", "Corregida"
    REVISADA = "revisada", "Revisada"
    AUTORIZADA = "autorizada", "Autorizada"
    RECHAZADA = "rechazada", "Rechazada"


class EstadoCertificado(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    REVOCADO = "revocado", "Revocado"


def _id():
    return models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


# --- Titulares y sus datos personales ---------------------------------------------------------


class Titular(models.Model):
    """Persona física o sociedad dueña de fincas (P-15). Fuera de los datos personales se le
    conoce por su código: así aparece en la evidencia que exporta el auditor (C18)."""

    class Tipo(models.TextChoices):
        FISICA = "fisica", "Persona física"
        SOCIEDAD = "sociedad", "Sociedad"

    id = _id()
    codigo = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.codigo


class DatosPersonales(models.Model):
    """Identificación y contacto del titular. Solo ADM los mantiene; al vencer la trazabilidad se
    desasocian (C16), no se borra el titular."""

    id = _id()
    titular = models.OneToOneField(Titular, on_delete=models.PROTECT, related_name="datos")
    nombre = models.CharField(max_length=200)
    identificacion = models.CharField(max_length=30)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    direccion = models.CharField(max_length=300, blank=True)
    suprimido_en = models.DateTimeField(null=True, blank=True)


class Representacion(models.Model):
    """Relación vigente entre una cuenta DUE y un titular: es el titular o un representante con
    autorización escrita (C5, POL-CA-08)."""

    id = _id()
    usuario = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="representaciones")
    titular = models.ForeignKey(Titular, on_delete=models.PROTECT, related_name="representantes")
    desde = models.DateField()
    hasta = models.DateField(null=True, blank=True)
    documento = models.CharField(max_length=200, blank=True)


class Vinculo(models.Model):
    """Vínculo familiar o comercial que una persona del personal declara con un titular. Quien lo
    tiene se abstiene de toda decisión sobre sus fincas (C17). Retirarlo lo aprueba GER (C13)."""

    class Tipo(models.TextChoices):
        FAMILIAR = "familiar", "Familiar"
        COMERCIAL = "comercial", "Comercial"

    id = _id()
    usuario = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="vinculos")
    titular = models.ForeignKey(Titular, on_delete=models.PROTECT, related_name="vinculos")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    declarado_en = models.DateTimeField(auto_now_add=True)
    retiro_solicitado_en = models.DateTimeField(null=True, blank=True)
    retiro_aprobado_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    retirado_en = models.DateTimeField(null=True, blank=True)


# --- Fincas y parcelas ------------------------------------------------------------------------


class Finca(models.Model):
    id = _id()
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=200)
    titular = models.ForeignKey(Titular, on_delete=models.PROTECT, related_name="fincas")
    ubicacion = models.CharField(max_length=300, blank=True)
    estado = models.CharField(
        max_length=10, choices=EstadoCatalogo.choices, default=EstadoCatalogo.PROPUESTO
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.codigo} {self.nombre}"


class Parcela(models.Model):
    """Una hectárea se identifica por la geometría de su parcela (P-21). Una parcela con
    mediciones no se edita: se crea una versión nueva que la reemplaza (C11). El área la calcula
    la base a partir de la geometría."""

    id = _id()
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT, related_name="parcelas")
    codigo = models.CharField(max_length=30)
    geometria = Poligono()
    area_ha = models.DecimalField(max_digits=12, decimal_places=4, null=True, editable=False)
    version = models.PositiveIntegerField(default=1)
    activa = models.BooleanField(default=False)
    estado = models.CharField(
        max_length=10, choices=EstadoCatalogo.choices, default=EstadoCatalogo.PROPUESTO
    )
    reemplaza = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reemplazada_por"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["finca", "codigo", "version"], name="parcela_version_unica"),
        ]


class PropuestaCatalogo(models.Model):
    """Alta de finca, cambio de titular o de geometría: ADM propone y GER aprueba (C11)."""

    class Tipo(models.TextChoices):
        ALTA_FINCA = "alta_finca", "Alta de finca"
        CAMBIO_TITULAR = "cambio_titular", "Cambio de titular"
        GEOMETRIA = "geometria", "Alta o cambio de parcela"

    id = _id()
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT, related_name="propuestas")
    parcela = models.ForeignKey(
        Parcela, null=True, blank=True, on_delete=models.PROTECT, related_name="propuestas"
    )
    titular_nuevo = models.ForeignKey(
        Titular, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    propuesta_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    propuesta_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=10, choices=EstadoCatalogo.choices, default=EstadoCatalogo.PROPUESTO
    )
    aprobada_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    aprobada_en = models.DateTimeField(null=True, blank=True)


# --- Períodos y asignaciones ------------------------------------------------------------------


class Periodo(models.Model):
    """Fin de medición y, unos días después, cierre de registro (P-22). No existe reabrir (C14)."""

    id = _id()
    nombre = models.CharField(max_length=50, unique=True)
    inicio = models.DateField()
    fin_medicion = models.DateField()
    cierre_registro = models.DateField()
    estado = models.CharField(
        max_length=12, choices=EstadoPeriodo.choices, default=EstadoPeriodo.PLANIFICADO
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="periodo_fechas_en_orden",
                condition=Q(inicio__lte=models.F("fin_medicion"))
                & Q(fin_medicion__lte=models.F("cierre_registro")),
            ),
        ]

    def __str__(self):
        return self.nombre


class PropuestaPeriodo(models.Model):
    """ADM registra la apertura o el cierre con las fechas de la coordinación; GER lo aprueba.
    Ninguno de los dos pasos basta solo (C14)."""

    class Accion(models.TextChoices):
        ABRIR = "abrir", "Abrir"
        CERRAR = "cerrar", "Cerrar"

    id = _id()
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name="propuestas")
    accion = models.CharField(max_length=6, choices=Accion.choices)
    registrada_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    registrada_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=10, choices=EstadoCatalogo.choices, default=EstadoCatalogo.PROPUESTO
    )
    aprobada_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    aprobada_en = models.DateTimeField(null=True, blank=True)


class Asignacion(models.Model):
    """Qué técnico mide qué finca: ordinaria, por el período, o temporal, con motivo y fecha de
    fin de 15 días como máximo (C19). Un técnico tiene como máximo el número de asignaciones
    activas que fija ParametroRol, 20 al inicio (K-1)."""

    class Tipo(models.TextChoices):
        ORDINARIA = "ordinaria", "Ordinaria"
        TEMPORAL = "temporal", "Temporal"

    id = _id()
    tecnico = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="asignaciones")
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT, related_name="asignaciones")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name="asignaciones")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    motivo = models.CharField(max_length=300, blank=True)
    desde = models.DateField()
    hasta = models.DateField(null=True, blank=True)
    creada_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)
    terminada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="temporal_con_motivo_y_fin",
                condition=Q(tipo="ordinaria") | (Q(hasta__isnull=False) & ~Q(motivo="")),
            ),
            models.CheckConstraint(
                name="nadie_se_asigna_a_si_mismo", condition=~Q(tecnico=models.F("creada_por"))
            ),
        ]


# --- Mediciones y sus versiones ---------------------------------------------------------------


class Medicion(models.Model):
    """Registro de campo por parcela y período. El contenido vive en VersionMedicion: cada cambio
    es una versión nueva, y la de la enmienda queda propuesta hasta la autorización final."""

    id = _id()
    parcela = models.ForeignKey(Parcela, on_delete=models.PROTECT, related_name="mediciones")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name="mediciones")
    estado = models.CharField(
        max_length=10, choices=EstadoMedicion.choices, default=EstadoMedicion.BORRADOR
    )
    version_vigente = models.OneToOneField(
        "VersionMedicion", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    creada_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)
    aprobada_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    aprobada_en = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)


class VersionMedicion(models.Model):
    """Una versión de una medición, con su autor. Autores(m), el conjunto que miran C3, C8 y C10,
    son los autores de todas las versiones (K-2: se compara el id de usuario)."""

    # Los datos que entran en el cálculo de las toneladas: cambiar uno vuelve material la
    # enmienda (C10).
    CAMPOS_MATERIALES = ("arboles", "dap_promedio_cm", "altura_promedio_m", "toneladas_co2")

    id = _id()
    medicion = models.ForeignKey(Medicion, on_delete=models.PROTECT, related_name="versiones")
    numero = models.PositiveIntegerField()
    autor = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    # La declara el técnico; la de registro la pone el servidor (P-22, C2).
    fecha_medicion = models.DateField()
    fecha_registro = models.DateTimeField(auto_now_add=True)
    arboles = models.PositiveIntegerField()
    dap_promedio_cm = models.DecimalField(max_digits=6, decimal_places=2)
    altura_promedio_m = models.DecimalField(max_digits=6, decimal_places=2)
    toneladas_co2 = models.DecimalField(max_digits=10, decimal_places=3)
    observaciones = models.TextField(blank=True)
    es_propuesta = models.BooleanField(default=False)
    enmienda = models.ForeignKey(
        "Enmienda", null=True, blank=True, on_delete=models.PROTECT, related_name="versiones"
    )
    huella_hoja_campo = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["medicion", "numero"], name="version_numero_unico"),
            models.CheckConstraint(
                name="fecha_medicion_no_posterior_al_registro",
                condition=Q(fecha_medicion__lte=TruncDate("fecha_registro")),
            ),
        ]


# --- Enmiendas --------------------------------------------------------------------------------


class Enmienda(models.Model):
    """Cuatro pasos y al menos tres personas: solicitar (C7), corregir (C9), revisar (C10) y
    autorizar (C8)."""

    id = _id()
    medicion = models.ForeignKey(Medicion, on_delete=models.PROTECT, related_name="enmiendas")
    estado = models.CharField(
        max_length=10, choices=EstadoEnmienda.choices, default=EstadoEnmienda.SOLICITADA
    )
    solicitada_por = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    solicitada_en = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField()
    evidencia = models.TextField()
    # Técnico que corrige: el responsable de la medición o el que SUP designó en su ausencia.
    responsable = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    corregida_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    corregida_en = models.DateTimeField(null=True, blank=True)
    material = models.BooleanField(null=True)
    revisada_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    revisada_en = models.DateTimeField(null=True, blank=True)
    dictamen_favorable = models.BooleanField(null=True)
    observaciones_revision = models.TextField(blank=True)
    autorizada_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    autorizada_en = models.DateTimeField(null=True, blank=True)
    # Si revoca un certificado, GER deja registrado si ya fue comercializado y qué se acordó (C8).
    comercializado = models.BooleanField(null=True)
    acuerdo_dueno = models.TextField(blank=True)


# --- Certificados -----------------------------------------------------------------------------


class Certificado(models.Model):
    """Lo emite y lo revoca solo el sistema (fila SIS, C4). Nunca hay dos vigentes para la misma
    parcela y período, y ninguno se borra: el revocado queda enlazado con su reemplazo."""

    id = _id()
    codigo = models.CharField(max_length=24, unique=True)
    medicion = models.ForeignKey(Medicion, on_delete=models.PROTECT, related_name="certificados")
    parcela = models.ForeignKey(Parcela, on_delete=models.PROTECT, related_name="certificados")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name="certificados")
    toneladas_co2 = models.DecimalField(max_digits=10, decimal_places=3)
    estado = models.CharField(
        max_length=10, choices=EstadoCertificado.choices, default=EstadoCertificado.VIGENTE
    )
    emitido_en = models.DateTimeField(auto_now_add=True)
    revocado_en = models.DateTimeField(null=True, blank=True)
    reemplaza = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reemplazado_por"
    )
    enmiendas_anotadas = models.ManyToManyField(Enmienda, blank=True, related_name="+")
    # Contenido firmado, firma Ed25519 e identificador de la clave (fase 6).
    contenido = models.JSONField()
    firma = models.TextField()
    clave_id = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parcela", "periodo"],
                condition=Q(estado="vigente"),
                name="un_certificado_vigente_por_parcela_y_periodo",
            ),
        ]


# --- Historial: parámetros, lecturas, alertas y exportaciones ---------------------------------


class ParametroRol(models.Model):
    """Umbrales de los controles de historial por rol, que aprueba GER (P-02): no son constantes.
    Valores iniciales: H1 40/60/80 fincas por día (P-13), jornada L-V 6:00-19:00 (P-12), H3 10
    fincas en 60 minutos, y 20 asignaciones activas por técnico (K-1)."""

    rol = models.CharField(max_length=3, primary_key=True)
    h1_aviso = models.PositiveIntegerField(default=40)
    h1_verificacion = models.PositiveIntegerField(default=60)
    h1_restriccion = models.PositiveIntegerField(default=80)
    h3_fincas_hora = models.PositiveIntegerField(default=10)
    jornada_inicio = models.TimeField(default="06:00")
    jornada_fin = models.TimeField(default="19:00")
    dias_laborales = models.CharField(max_length=7, default="12345")
    max_asignaciones_activas = models.PositiveIntegerField(null=True, blank=True)
    aprobado_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    actualizado_en = models.DateTimeField(auto_now=True)


class EventoLectura(models.Model):
    """Una consulta del detalle de una finca: la materia prima de H1 y H3. Los intentos denegados
    por C1 o C5 cuentan doble."""

    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT, related_name="+")
    instante = models.DateTimeField(auto_now_add=True, db_index=True)
    denegado = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["usuario", "instante"], name="lectura_usuario_instante")]


class Alerta(models.Model):
    class Control(models.TextChoices):
        H1 = "H1", "Frecuencia"
        H2 = "H2", "Tiempo"
        H3 = "H3", "Combinada"

    class Nivel(models.TextChoices):
        AVISO = "aviso", "Aviso"
        VERIFICACION = "verificacion", "Verificación adicional"
        RESTRICCION = "restriccion", "Restricción temporal"

    id = _id()
    sujeto = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="alertas")
    control = models.CharField(max_length=2, choices=Control.choices)
    nivel = models.CharField(max_length=12, choices=Nivel.choices)
    detalle = models.JSONField(default=dict)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_por = models.ForeignKey(
        USUARIO, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resuelta_en = models.DateTimeField(null=True, blank=True)
    resolucion = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="nadie_resuelve_su_propia_alerta", condition=~Q(resuelta_por=models.F("sujeto"))
            ),
        ]


class ExportacionAuditoria(models.Model):
    """Paquete de evidencia que genera el sistema para el auditor: sellado, con su identidad y
    con su huella en la bitácora (C18)."""

    id = _id()
    auditor = models.ForeignKey(USUARIO, on_delete=models.PROTECT, related_name="+")
    objeto = models.CharField(max_length=30)
    filtro = models.JSONField(default=dict)
    huella = models.CharField(max_length=64)
    creada_en = models.DateTimeField(auto_now_add=True)

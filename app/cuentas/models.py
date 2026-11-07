"""Objeto «Cuentas y roles» de la matriz: usuarios, su rol, su vigencia y las propuestas de rol
que aprueba GER (regla C12). Los vínculos declarados con titulares viven en negocio.Vinculo."""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Rol(models.TextChoices):
    TEC = "TEC", "Técnico de campo"
    VER = "VER", "Verificador"
    SUP = "SUP", "Supervisor de campo"
    GER = "GER", "Gerencia de Certificación"
    ADM = "ADM", "Administrador de catálogo y cuentas"
    AUD = "AUD", "Auditor externo"
    DUE = "DUE", "Dueño de finca"


class EstadoPropuesta(models.TextChoices):
    PROPUESTA = "propuesta", "Propuesta"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"


class Usuario(AbstractUser):
    """Una persona, una cuenta (POL-CA-01) y un solo rol (RBAC₂, exclusión estática). La única
    excepción, la habilitación temporal de técnico para un verificador, es una PropuestaRol."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rol = models.CharField(max_length=3, choices=Rol.choices, blank=True)
    # Número de identificación de la persona: no hay dos cuentas para la misma persona.
    identificacion = models.CharField(max_length=30, unique=True, null=True, blank=True)
    # Supervisor de un técnico: quién atiende sus alertas (C15).
    supervisor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="tecnicos_a_cargo"
    )
    # Ventana de la cuenta: obligatoria para AUD (C6), opcional para el resto.
    vigente_desde = models.DateTimeField(null=True, blank=True)
    vigente_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "usuario"

    def __str__(self):
        return f"{self.username} ({self.rol or 'sin rol'})"


class PropuestaRol(models.Model):
    """ADM propone un rol (o una habilitación temporal de técnico) y GER lo aprueba. Quien aprueba
    no es quien propone ni el titular de la cuenta (C12)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="propuestas_rol")
    rol = models.CharField(max_length=3, choices=Rol.choices)
    es_habilitacion = models.BooleanField(default=False)
    fin_habilitacion = models.DateField(null=True, blank=True)
    propuesta_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="+")
    propuesta_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=10, choices=EstadoPropuesta.choices, default=EstadoPropuesta.PROPUESTA
    )
    aprobada_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    aprobada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="habilitacion_es_tec_con_fecha_fin",
                condition=models.Q(es_habilitacion=False)
                | models.Q(rol="TEC", fin_habilitacion__isnull=False),
            ),
        ]


class Declaracion(models.Model):
    """Declaración de vínculos al ingresar y antes de cada período (POL-CA-14). Si declara
    vínculos, cada uno queda en negocio.Vinculo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="declaraciones")
    fecha = models.DateTimeField(auto_now_add=True)
    sin_vinculos = models.BooleanField()

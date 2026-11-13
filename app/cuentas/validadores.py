from django.core.exceptions import ValidationError


class SinNombresPropios:
    """POL-AU-03: la contraseña no puede contener el nombre de la persona, de la empresa ni de una
    finca. Se comparan sin mayúsculas las palabras de cinco letras o más."""

    PALABRAS_EMPRESA = ("verdeazul", "carbono")

    def validate(self, password, user=None):
        from negocio.models import Finca

        texto = password.casefold()
        nombres = list(self.PALABRAS_EMPRESA)
        if user is not None:
            nombres += [user.username, user.first_name, user.last_name]
        nombres += Finca.objects.values_list("nombre", flat=True)
        for nombre in nombres:
            for palabra in (nombre or "").casefold().split():
                if len(palabra) >= 5 and palabra in texto:
                    raise ValidationError(
                        "La contraseña no puede contener su nombre, el de la empresa ni el de una finca.",
                        code="nombre_propio",
                    )

    def get_help_text(self):
        return "No puede contener su nombre, el de la empresa ni el de una finca."

from django.urls import path

from nucleo import views

urlpatterns = [
    path("", views.hola, name="hola"),
    path("salud", views.salud, name="salud"),
]

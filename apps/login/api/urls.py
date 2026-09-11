"""Rotas da API de login orquestrado."""

from django.urls import path

from apps.login.api.views import LoginView

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
]

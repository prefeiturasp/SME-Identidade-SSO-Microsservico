"""Rotas da API de sessão compartilhada."""

from django.urls import path

from apps.sessoes.api.views import (
    ConsultarSessaoView,
    CriarSessaoView,
    LogoutSessaoView,
    RenovarSessaoView,
)

urlpatterns = [
    path(
        "sessoes/",
        CriarSessaoView.as_view(),
        name="criar-sessao",
    ),
    path(
        "sessoes/<uuid:sessao_id>/",
        ConsultarSessaoView.as_view(),
        name="consultar-sessao",
    ),
    path(
        "sessoes/<uuid:sessao_id>/renovar/",
        RenovarSessaoView.as_view(),
        name="renovar-sessao",
    ),
    path(
        "sessoes/<uuid:sessao_id>/logout/",
        LogoutSessaoView.as_view(),
        name="logout-sessao",
    ),
]

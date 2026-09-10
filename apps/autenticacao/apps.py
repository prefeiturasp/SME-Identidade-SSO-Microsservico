"""Configuração da app autenticação."""

from django.apps import AppConfig


class AutenticacaoConfig(AppConfig):
    """Configura o app autenticação."""

    name = "apps.autenticacao"
    label = "autenticacao"

    def ready(self) -> None:
        """Registra a extensão de schema OpenAPI da AutenticacaoApiKey."""
        from apps.autenticacao import schema  # noqa: F401

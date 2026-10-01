"""Configuração da app core."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configura o app core."""

    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        """Inicializa os recursos compartilhados da SDK."""
        from sme_sidecar_sdk import runtime
        from sme_sidecar_sdk.config import Settings

        runtime.configure(
            Settings(
                service_name="SME-Identidade-SSO-Microsservico",
                service_version="0.0.1",
            )
        )

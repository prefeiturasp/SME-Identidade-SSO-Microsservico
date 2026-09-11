"""Cliente HTTP do SME-Identidade-Gateway-Microsservico."""

import httpx
from django.conf import settings


def cliente_gateway_ms() -> httpx.Client:
    """Cria um cliente HTTP configurado para o Gateway.

    Uso: ``with cliente_gateway_ms() as cliente: cliente.get(...)``.

    Returns:
        Cliente HTTP com URL base, timeout e API Key do Gateway já
        configurados.
    """
    header = settings.API_KEY_GATEWAY_MS_HEADER
    return httpx.Client(
        base_url=settings.GATEWAY_MS_URL,
        timeout=settings.GATEWAY_MS_TIMEOUT,
        headers={header: settings.API_KEY_GATEWAY_MS},
    )

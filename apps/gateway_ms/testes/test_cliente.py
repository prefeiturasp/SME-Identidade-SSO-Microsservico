"""Testes do cliente HTTP do Gateway."""

from django.test import SimpleTestCase, override_settings

from apps.gateway_ms.cliente import cliente_gateway_ms


@override_settings(
    GATEWAY_MS_URL="http://gateway-ms:8000",
    GATEWAY_MS_TIMEOUT=7.0,
    API_KEY_GATEWAY_MS="chave-gateway",
    API_KEY_GATEWAY_MS_HEADER="X-API-Key",
)
class TestClienteGatewayMs(SimpleTestCase):
    """Testes de configuração do cliente HTTP do Gateway."""

    def test_deve_configurar_base_url_timeout_e_api_key(self) -> None:
        """Deve configurar URL base, timeout e header de API Key."""
        with cliente_gateway_ms() as cliente:
            self.assertEqual(
                str(cliente.base_url),
                "http://gateway-ms:8000",
            )
            self.assertEqual(cliente.timeout.connect, 7.0)
            self.assertEqual(
                cliente.headers["x-api-key"],
                "chave-gateway",
            )

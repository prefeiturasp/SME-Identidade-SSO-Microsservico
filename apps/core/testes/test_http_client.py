"""Testes do cliente HTTP compartilhado."""

from unittest.mock import MagicMock, patch

import httpx
from django.conf import settings
from django.test import SimpleTestCase
from sme_sidecar_sdk import CircuitOpenError

from apps.core.apps import CoreConfig
from apps.core.http_client import ServiceClient

_GATEWAY_BASE_URL = "https://gateway-ms"
_LOGIN_PATH = "/api/v1/autenticacao/login/"
_SISTEMAS_PATH = (
    "/api/v1/autenticacao/usuarios/1234567/sistemas/"
)
_USUARIO_PATH = "/api/v1/autenticacao/usuarios/1234567/"


def _make_gateway_client(
    *,
    api_key: str = "",
    api_key_header: str = "X-API-Key",
) -> ServiceClient:
    """Cria um ServiceClient fictício para o domínio gateway."""
    return ServiceClient(
        base_url=_GATEWAY_BASE_URL,
        dominio="gateway",
        api_key=api_key,
        api_key_header=api_key_header,
    )


class SidecarIntegracaoTest(SimpleTestCase):
    """Valida a integração da aplicação com o SME Sidecar SDK."""

    @patch("sme_sidecar_sdk.runtime.configure")
    def test_inicializa_sidecar_no_boot(
        self,
        mock_configure: MagicMock,
    ) -> None:
        """Deve configurar o Sidecar ao inicializar a app core."""
        config = CoreConfig(
            "apps.core",
            __import__("apps.core"),
        )

        config.ready()

        mock_configure.assert_called_once()

        configuracao = mock_configure.call_args.args[0]

        self.assertEqual(
            configuracao.service_name,
            "SME-Identidade-SSO-Microsservico",
        )

        self.assertEqual(
            configuracao.service_version,
            "0.0.1",
        )

    def test_middleware_observabilidade_esta_configurado(
        self,
    ) -> None:
        """Deve registrar o middleware de observabilidade da SDK."""
        self.assertIn(
            "sme_sidecar_sdk.integrations.django.ObservabilityMiddleware",
            settings.MIDDLEWARE,
        )


class ServiceClientConfigurationTest(SimpleTestCase):
    """Valida a configuração do ServiceClient."""

    def test_remove_barra_final_da_base_url(self) -> None:
        """Deve normalizar a URL base."""
        svc = ServiceClient(
            base_url=f"{_GATEWAY_BASE_URL}/",
            dominio="gateway",
        )

        self.assertEqual(
            svc.base_url,
            _GATEWAY_BASE_URL,
        )

    def test_headers_sem_api_key(self) -> None:
        """Deve enviar somente Accept sem API Key."""
        svc = _make_gateway_client()

        self.assertEqual(
            svc._headers(),  # noqa: SLF001
            {
                "Accept": "application/json",
            },
        )

    def test_headers_com_api_key(self) -> None:
        """Deve incluir a API Key configurada."""
        svc = _make_gateway_client(
            api_key="chave-gateway",
        )

        self.assertEqual(
            svc._headers(),  # noqa: SLF001
            {
                "Accept": "application/json",
                "X-API-Key": "chave-gateway",
            },
        )

    def test_headers_com_nome_customizado_para_api_key(self) -> None:
        """Deve respeitar o nome configurado para o header da API Key."""
        svc = _make_gateway_client(
            api_key="chave-gateway",
            api_key_header="X-Gateway-Key",
        )

        self.assertEqual(
            svc._headers(),  # noqa: SLF001
            {
                "Accept": "application/json",
                "X-Gateway-Key": "chave-gateway",
            },
        )


class ServiceClientRequestTest(SimpleTestCase):
    """Valida a delegação das chamadas HTTP ao Sidecar."""

    @patch("apps.core.http_client.build_http_client")
    def test_cria_cliente_gateway_somente_na_primeira_chamada(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve criar o cliente de forma preguiçosa."""
        svc = _make_gateway_client()

        mock_build_http_client.assert_not_called()

        svc.get(_SISTEMAS_PATH)

        mock_build_http_client.assert_called_once_with(
            "gateway",
            base_url=_GATEWAY_BASE_URL,
            follow_redirects=True,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_reaproveita_cliente_gateway_em_gets(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve reutilizar o mesmo cliente Sidecar nas chamadas GET."""
        svc = _make_gateway_client()

        svc.get(_SISTEMAS_PATH)
        svc.get(
            "/api/v1/autenticacao/usuarios/7654321/sistemas/"
        )

        mock_build_http_client.assert_called_once_with(
            "gateway",
            base_url=_GATEWAY_BASE_URL,
            follow_redirects=True,
        )

        cliente = mock_build_http_client.return_value

        self.assertEqual(
            cliente.get.call_count,
            2,
        )

        cliente.get.assert_any_call(
            _SISTEMAS_PATH,
            headers={
                "Accept": "application/json",
            },
            params=None,
        )

        cliente.get.assert_any_call(
            "/api/v1/autenticacao/usuarios/7654321/sistemas/",
            headers={
                "Accept": "application/json",
            },
            params=None,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_get_sistemas_repassa_headers_e_params(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve repassar GET e preservar resposta de erro HTTP."""
        svc = _make_gateway_client(
            api_key="chave-gateway",
        )

        params = {
            "ativo": True,
        }

        request = httpx.Request(
            "GET",
            f"{_GATEWAY_BASE_URL}{_SISTEMAS_PATH}",
        )
        response = httpx.Response(
            404,
            request=request,
        )

        mock_build_http_client.return_value.get.side_effect = (
            httpx.HTTPStatusError(
                "Not Found",
                request=request,
                response=response,
            )
        )

        resultado = svc.get(
            _SISTEMAS_PATH,
            params=params,
        )

        self.assertIs(
            resultado,
            response,
        )

        mock_build_http_client.return_value.get.assert_called_once_with(
            _SISTEMAS_PATH,
            headers={
                "Accept": "application/json",
                "X-API-Key": "chave-gateway",
            },
            params=params,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_post_login_repassa_payload(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve repassar o payload do login ao Gateway."""
        svc = _make_gateway_client(
            api_key="chave-gateway",
        )

        payload = {
            "login": "1234567",
            "senha": "senha-correta",
        }

        request = httpx.Request(
            "POST",
            f"{_GATEWAY_BASE_URL}{_LOGIN_PATH}",
        )
        response = httpx.Response(
            401,
            request=request,
        )

        mock_build_http_client.return_value.post.side_effect = (
            httpx.HTTPStatusError(
                "Unauthorized",
                request=request,
                response=response,
            )
        )

        resultado = svc.post(
            _LOGIN_PATH,
            payload=payload,
        )

        self.assertIs(
            resultado,
            response,
        )

        mock_build_http_client.return_value.post.assert_called_once_with(
            _LOGIN_PATH,
            headers={
                "Accept": "application/json",
                "X-API-Key": "chave-gateway",
            },
            json=payload,
            params=None,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_post_login_repassa_params(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve repassar query params quando informados no POST."""
        svc = _make_gateway_client()

        payload = {
            "login": "1234567",
            "senha": "senha-correta",
        }
        params = {
            "origem": "sso",
        }

        svc.post(
            _LOGIN_PATH,
            payload=payload,
            params=params,
        )

        mock_build_http_client.return_value.post.assert_called_once_with(
            _LOGIN_PATH,
            headers={
                "Accept": "application/json",
            },
            json=payload,
            params=params,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_post_aceita_lista_como_payload(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve aceitar lista como corpo JSON do POST."""
        svc = _make_gateway_client()

        payload = [
            {
                "login": "1234567",
            },
            {
                "login": "7654321",
            },
        ]

        svc.post(
            _LOGIN_PATH,
            payload=payload,
        )

        mock_build_http_client.return_value.post.assert_called_once_with(
            _LOGIN_PATH,
            headers={
                "Accept": "application/json",
            },
            json=payload,
            params=None,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_put_repassa_payload(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve delegar PUT e preservar resposta de erro HTTP."""
        svc = _make_gateway_client(
            api_key="chave-gateway",
        )

        payload = {
            "ativo": True,
        }

        request = httpx.Request(
            "PUT",
            f"{_GATEWAY_BASE_URL}{_USUARIO_PATH}",
        )
        response = httpx.Response(
            400,
            request=request,
        )

        mock_build_http_client.return_value.put.side_effect = (
            httpx.HTTPStatusError(
                "Bad Request",
                request=request,
                response=response,
            )
        )

        resultado = svc.put(
            _USUARIO_PATH,
            payload=payload,
        )

        self.assertIs(
            resultado,
            response,
        )

        mock_build_http_client.return_value.put.assert_called_once_with(
            _USUARIO_PATH,
            headers={
                "Accept": "application/json",
                "X-API-Key": "chave-gateway",
            },
            json=payload,
            params=None,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_put_repassa_params(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve repassar query params quando informados no PUT."""
        svc = _make_gateway_client()

        payload = {
            "ativo": True,
        }
        params = {
            "forcar": True,
        }

        svc.put(
            _USUARIO_PATH,
            payload=payload,
            params=params,
        )

        mock_build_http_client.return_value.put.assert_called_once_with(
            _USUARIO_PATH,
            headers={
                "Accept": "application/json",
            },
            json=payload,
            params=params,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_get_propaga_timeout(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve preservar erros HTTPX de transporte."""
        svc = _make_gateway_client()

        mock_build_http_client.return_value.get.side_effect = (
            httpx.TimeoutException("timeout")
        )

        with self.assertRaisesRegex(
            httpx.TimeoutException,
            "timeout",
        ):
            svc.get(_SISTEMAS_PATH)


class ServiceClientLifecycleTest(SimpleTestCase):
    """Valida o fechamento do cliente HTTP."""

    @patch("apps.core.http_client.build_http_client")
    def test_close_fecha_cliente_http(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve fechar o cliente já criado."""
        svc = _make_gateway_client()

        svc.get(_SISTEMAS_PATH)
        svc.close()

        mock_build_http_client.return_value.close.assert_called_once_with()

    @patch("apps.core.http_client.build_http_client")
    def test_close_permite_criar_novo_cliente(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Deve recriar o cliente após close."""
        svc = _make_gateway_client()

        svc.get(_SISTEMAS_PATH)
        svc.close()
        svc.get(_SISTEMAS_PATH)

        self.assertEqual(
            mock_build_http_client.call_count,
            2,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_close_sem_cliente_nao_cria_cliente(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """Não deve criar cliente apenas para executar close."""
        svc = _make_gateway_client()

        svc.close()

        mock_build_http_client.assert_not_called()


class ServiceClientCircuitBreakerTest(SimpleTestCase):
    """Valida a conversão do circuito aberto."""

    @patch("apps.core.http_client.build_http_client")
    def test_get_converte_circuito_aberto_em_connect_error(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """GET deve converter CircuitOpenError em ConnectError."""
        svc = _make_gateway_client()

        mock_build_http_client.return_value.get.side_effect = (
            CircuitOpenError("circuito aberto")
        )

        with self.assertRaises(httpx.ConnectError) as contexto:
            svc.get(_SISTEMAS_PATH)

        erro = contexto.exception

        self.assertEqual(
            str(erro),
            "Circuit breaker aberto para gateway",
        )

        self.assertEqual(
            erro.request.method,
            "GET",
        )

        self.assertEqual(
            str(erro.request.url),
            f"{_GATEWAY_BASE_URL}{_SISTEMAS_PATH}",
        )

        self.assertIsInstance(
            erro.__cause__,
            CircuitOpenError,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_post_converte_circuito_aberto_em_connect_error(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """POST deve converter CircuitOpenError em ConnectError."""
        svc = _make_gateway_client()

        mock_build_http_client.return_value.post.side_effect = (
            CircuitOpenError("circuito aberto")
        )

        with self.assertRaises(httpx.ConnectError) as contexto:
            svc.post(
                _LOGIN_PATH,
                payload={
                    "login": "1234567",
                    "senha": "senha-correta",
                },
            )

        erro = contexto.exception

        self.assertEqual(
            str(erro),
            "Circuit breaker aberto para gateway",
        )

        self.assertEqual(
            erro.request.method,
            "POST",
        )

        self.assertEqual(
            str(erro.request.url),
            f"{_GATEWAY_BASE_URL}{_LOGIN_PATH}",
        )

        self.assertIsInstance(
            erro.__cause__,
            CircuitOpenError,
        )

    @patch("apps.core.http_client.build_http_client")
    def test_put_converte_circuito_aberto_em_connect_error(
        self,
        mock_build_http_client: MagicMock,
    ) -> None:
        """PUT deve converter CircuitOpenError em ConnectError."""
        svc = _make_gateway_client()

        mock_build_http_client.return_value.put.side_effect = (
            CircuitOpenError("circuito aberto")
        )

        with self.assertRaises(httpx.ConnectError) as contexto:
            svc.put(
                _USUARIO_PATH,
                payload={
                    "ativo": True,
                },
            )

        erro = contexto.exception

        self.assertEqual(
            str(erro),
            "Circuit breaker aberto para gateway",
        )

        self.assertEqual(
            erro.request.method,
            "PUT",
        )

        self.assertEqual(
            str(erro.request.url),
            f"{_GATEWAY_BASE_URL}{_USUARIO_PATH}",
        )

        self.assertIsInstance(
            erro.__cause__,
            CircuitOpenError,
        )

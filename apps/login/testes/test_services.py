"""Testes do serviço de login orquestrado."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from django.test import SimpleTestCase

from apps.login.services import LoginError, LoginService
from apps.sessoes.dominio import Sessao
from apps.sessoes.services import GatewayIndisponivelError

_AGORA = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)

_DADOS_AUTENTICACAO = {
    "kc_user_id": "5c29cc47-0000-0000-0000-000000000000",
    "username": "1234567",
    "nome": "FULANO DE TAL",
    "email": "fulano@sme.prefeitura.sp.gov.br",
    "ativo": True,
    "cpf": "12345678900",
    "rf": "1234567",
    "roles": {
        "realm_access": {"roles": []},
        "resource_access": {},
    },
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "expires_in": 300,
    "token_enriquecido": "token-enriquecido",
    "data_expiracao_token_enriquecido": "2026-09-09T20:00:00Z",
}


def _resposta_login(
    corpo: dict | None,
    status_code: int = 200,
) -> httpx.Response:
    """Cria uma resposta simulada do endpoint de login do Gateway."""
    return httpx.Response(
        status_code=status_code,
        json=corpo,
        request=httpx.Request(
            "POST",
            "http://gateway-ms/api/v1/autenticacao/login/",
        ),
    )


def _sessao() -> Sessao:
    """Cria uma sessão válida para os testes."""
    return Sessao(
        sessao_id=uuid4(),
        login="1234567",
        kc_user_id=str(_DADOS_AUTENTICACAO["kc_user_id"]),
        sistemas=[
            {
                "sistema_id": 1,
                "sistema_nome": "CoreSSO",
            }
        ],
        criado_em=_AGORA,
        ultima_atividade=_AGORA,
        expira_em=_AGORA + timedelta(hours=8),
    )


class TestLoginServiceAutenticarECriarSessao(SimpleTestCase):
    """Testes de LoginService.autenticar_e_criar_sessao."""

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_login_ok_e_sessao_ok(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve retornar os dados de autenticação e a sessão criada."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            _DADOS_AUTENTICACAO
        )

        sessao = _sessao()
        mock_criar_sessao.return_value = sessao

        resultado = LoginService.autenticar_e_criar_sessao(
            "1234567",
            "senha-correta",
        )

        self.assertEqual(
            resultado.dados_autenticacao,
            _DADOS_AUTENTICACAO,
        )
        self.assertEqual(resultado.sessao, sessao)
        self.assertIsNone(resultado.sessao_erro)

        mock_cliente_gateway.post.assert_called_once_with(
            "/api/v1/autenticacao/login/",
            payload={
                "login": "1234567",
                "senha": "senha-correta",
            },
        )

        mock_criar_sessao.assert_called_once_with(
            "1234567",
            _DADOS_AUTENTICACAO["kc_user_id"],
        )

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_login_ok_mas_sessao_falha_nao_desfaz_login(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve manter o login válido quando a criação da sessão falha."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            _DADOS_AUTENTICACAO
        )

        mock_criar_sessao.side_effect = GatewayIndisponivelError("timeout")

        resultado = LoginService.autenticar_e_criar_sessao(
            "1234567",
            "senha-correta",
        )

        self.assertEqual(
            resultado.dados_autenticacao,
            _DADOS_AUTENTICACAO,
        )
        self.assertIsNone(resultado.sessao)
        self.assertEqual(
            resultado.sessao_erro,
            "Gateway indisponível ao criar sessão.",
        )

        mock_criar_sessao.assert_called_once_with(
            "1234567",
            _DADOS_AUTENTICACAO["kc_user_id"],
        )

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_senha_invalida_lanca_login_error(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve lançar LoginError quando o Gateway retorna 401."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            {"detalhe": "Senha inválida."},
            status_code=401,
        )

        with self.assertRaisesRegex(
            LoginError,
            "Senha inválida.",
        ):
            LoginService.autenticar_e_criar_sessao(
                "1234567",
                "errada",
            )

        mock_criar_sessao.assert_not_called()

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_usuario_inexistente_lanca_login_error(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve lançar LoginError quando o Gateway retorna 204."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            None,
            status_code=204,
        )

        with self.assertRaisesRegex(
            LoginError,
            "Usuário não encontrado.",
        ):
            LoginService.autenticar_e_criar_sessao(
                "0000000",
                "qualquer",
            )

        mock_criar_sessao.assert_not_called()

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_timeout_no_login_lanca_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve lançar GatewayIndisponivelError em timeout."""
        mock_cliente_gateway.post.side_effect = httpx.TimeoutException(
            "timeout"
        )

        with self.assertRaisesRegex(
            GatewayIndisponivelError,
            "timeout",
        ):
            LoginService.autenticar_e_criar_sessao(
                "1234567",
                "senha",
            )

        mock_criar_sessao.assert_not_called()

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_erro_http_no_login_lanca_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve converter HTTPError em GatewayIndisponivelError."""
        mock_cliente_gateway.post.side_effect = httpx.ConnectError(
            "connection refused"
        )

        with self.assertRaisesRegex(
            GatewayIndisponivelError,
            "connection refused",
        ):
            LoginService.autenticar_e_criar_sessao(
                "1234567",
                "senha",
            )

        mock_criar_sessao.assert_not_called()

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services._client")
    def test_status_inesperado_no_login_lanca_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve lançar GatewayIndisponivelError para status inesperado."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            {"erro": "erro interno"},
            status_code=500,
        )

        with self.assertRaisesRegex(
            GatewayIndisponivelError,
            "Gateway retornou status 500.",
        ):
            LoginService.autenticar_e_criar_sessao(
                "1234567",
                "senha",
            )

        mock_criar_sessao.assert_not_called()


class TestLoginServiceAutenticarNoGateway(SimpleTestCase):
    """Testes unitários de LoginService._autenticar_no_gateway."""

    @patch("apps.login.services._client")
    def test_deve_retornar_corpo_da_resposta_quando_status_200(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve retornar o JSON recebido do Gateway."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            _DADOS_AUTENTICACAO
        )

        resultado = LoginService._autenticar_no_gateway(
            "1234567",
            "senha-correta",
        )

        self.assertEqual(resultado, _DADOS_AUTENTICACAO)

        mock_cliente_gateway.post.assert_called_once_with(
            "/api/v1/autenticacao/login/",
            payload={
                "login": "1234567",
                "senha": "senha-correta",
            },
        )

    @patch("apps.login.services._client")
    def test_gateway_401_deve_lancar_login_error(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve interpretar 401 como credenciais inválidas."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            {"detalhe": "não autorizado"},
            status_code=401,
        )

        with self.assertRaisesRegex(
            LoginError,
            "Senha inválida.",
        ):
            LoginService._autenticar_no_gateway(
                "1234567",
                "senha-errada",
            )

    @patch("apps.login.services._client")
    def test_gateway_204_deve_lancar_login_error(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve interpretar 204 como usuário inexistente."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            None,
            status_code=204,
        )

        with self.assertRaisesRegex(
            LoginError,
            "Usuário não encontrado.",
        ):
            LoginService._autenticar_no_gateway(
                "0000000",
                "senha",
            )

    @patch("apps.login.services._client")
    def test_gateway_status_nao_esperado_deve_lancar_erro(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve rejeitar qualquer status diferente de 200, 204 e 401."""
        mock_cliente_gateway.post.return_value = _resposta_login(
            {"erro": "indisponível"},
            status_code=503,
        )

        with self.assertRaisesRegex(
            GatewayIndisponivelError,
            "Gateway retornou status 503.",
        ):
            LoginService._autenticar_no_gateway(
                "1234567",
                "senha",
            )

    @patch("apps.login.services._client")
    def test_http_error_deve_ser_convertido_em_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve converter erros HTTPX em GatewayIndisponivelError."""
        erro_original = httpx.ConnectError("Falha de conexão")
        mock_cliente_gateway.post.side_effect = erro_original

        with self.assertRaises(GatewayIndisponivelError) as contexto:
            LoginService._autenticar_no_gateway(
                "1234567",
                "senha",
            )

        self.assertEqual(
            str(contexto.exception),
            "Falha de conexão",
        )
        self.assertIs(
            contexto.exception.__cause__,
            erro_original,
        )

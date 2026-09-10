"""Testes do serviço de login orquestrado."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch
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
    "roles": {"realm_access": {"roles": []}, "resource_access": {}},
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "expires_in": 300,
    "token_enriquecido": "token-enriquecido",
    "data_expiracao_token_enriquecido": "2026-09-09T20:00:00Z",
}


def _mock_cliente(resposta: httpx.Response) -> MagicMock:
    """Mock do cliente HTTP do Gateway, no formato de context manager."""
    cliente = MagicMock()
    cliente.post.return_value = resposta
    contexto = MagicMock()
    contexto.__enter__.return_value = cliente
    contexto.__exit__.return_value = False
    return contexto


def _resposta_login(
    corpo: dict | None,
    status_code: int = 200,
) -> httpx.Response:
    """Resposta simulada do endpoint de login do Gateway."""
    return httpx.Response(
        status_code,
        json=corpo,
        request=httpx.Request(
            "POST",
            "http://gateway-ms/api/v1/autenticacao/login/",
        ),
    )


def _sessao() -> Sessao:
    return Sessao(
        sessao_id=uuid4(),
        login="1234567",
        kc_user_id=str(_DADOS_AUTENTICACAO["kc_user_id"]),
        sistemas=[{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
        criado_em=_AGORA,
        ultima_atividade=_AGORA,
        expira_em=_AGORA + timedelta(hours=8),
    )


class TestLoginServiceAutenticarECriarSessao(SimpleTestCase):
    """Testes de :meth:`LoginService.autenticar_e_criar_sessao`."""

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services.cliente_gateway_ms")
    def test_login_ok_e_sessao_ok(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve retornar dados de autenticação e a sessão criada."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_login(_DADOS_AUTENTICACAO)
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

        mock_criar_sessao.assert_called_once_with(
            "1234567",
            _DADOS_AUTENTICACAO["kc_user_id"],
        )

    @patch("apps.login.services.SessaoService.criar")
    @patch("apps.login.services.cliente_gateway_ms")
    def test_login_ok_mas_sessao_falha_nao_desfaz_login(
        self,
        mock_cliente_gateway: Mock,
        mock_criar_sessao: Mock,
    ) -> None:
        """Deve retornar os dados de autenticação mesmo sem sessão."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_login(_DADOS_AUTENTICACAO)
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

    @patch("apps.login.services.cliente_gateway_ms")
    def test_senha_invalida_lanca_login_error(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve lançar LoginError quando o Gateway retorna 401."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_login({"detalhe": "Senha inválida."}, status_code=401)
        )

        with self.assertRaises(LoginError):
            LoginService.autenticar_e_criar_sessao("1234567", "errada")

    @patch("apps.login.services.cliente_gateway_ms")
    def test_usuario_inexistente_lanca_login_error(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve lançar LoginError quando o Gateway retorna 204."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_login(None, status_code=204)
        )

        with self.assertRaises(LoginError):
            LoginService.autenticar_e_criar_sessao("0000000", "qualquer")

    @patch("apps.login.services.cliente_gateway_ms")
    def test_timeout_no_login_lanca_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve lançar GatewayIndisponivelError em timeout na 1ª chamada."""
        contexto = MagicMock()
        contexto.__enter__.return_value.post.side_effect = (
            httpx.TimeoutException("timeout")
        )
        mock_cliente_gateway.return_value = contexto

        with self.assertRaises(GatewayIndisponivelError):
            LoginService.autenticar_e_criar_sessao("1234567", "senha")

    @patch("apps.login.services.cliente_gateway_ms")
    def test_erro_generico_no_login_lanca_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve lançar GatewayIndisponivelError em status inesperado."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_login({"erro": "erro interno"}, status_code=500)
        )

        with self.assertRaises(GatewayIndisponivelError):
            LoginService.autenticar_e_criar_sessao("1234567", "senha")

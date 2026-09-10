"""Testes das views da API de login orquestrado."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.login.services import LoginError, ResultadoLogin
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


class TestLoginView(SimpleTestCase):
    """Testes de LoginView."""

    def setUp(self) -> None:
        """Cria os dados utilizados pelos testes."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=settings.API_KEY)
        self.url = reverse("login")

    @patch("apps.login.api.views.LoginService.autenticar_e_criar_sessao")
    def test_login_com_sucesso_retorna_sessao(
        self,
        mock_autenticar: Mock,
    ) -> None:
        """Deve retornar 201 com dados de autenticação e sessão."""
        mock_autenticar.return_value = ResultadoLogin(
            dados_autenticacao=_DADOS_AUTENTICACAO,
            sessao=_sessao(),
            sessao_erro=None,
        )

        response = self.client.post(
            self.url,
            {"login": "1234567", "senha": "senha-correta"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        corpo = response.json()
        assert corpo["kc_user_id"] == _DADOS_AUTENTICACAO["kc_user_id"]
        assert corpo["token_enriquecido"] == "token-enriquecido"
        assert corpo["sessao"]["sistemas"] == [
            {"sistema_id": 1, "sistema_nome": "CoreSSO"}
        ]
        assert corpo["sessao_erro"] is None
        assert "senha" not in corpo

    @patch("apps.login.api.views.LoginService.autenticar_e_criar_sessao")
    def test_login_ok_mas_sessao_falha_retorna_sessao_nula(
        self,
        mock_autenticar: Mock,
    ) -> None:
        """Deve retornar 201 com sessao null e sessao_erro preenchido."""
        mock_autenticar.return_value = ResultadoLogin(
            dados_autenticacao=_DADOS_AUTENTICACAO,
            sessao=None,
            sessao_erro="Gateway indisponível ao criar sessão.",
        )

        response = self.client.post(
            self.url,
            {"login": "1234567", "senha": "senha-correta"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        corpo = response.json()
        assert corpo["sessao"] is None
        assert corpo["sessao_erro"] == "Gateway indisponível ao criar sessão."

    @patch("apps.login.api.views.LoginService.autenticar_e_criar_sessao")
    def test_login_invalido_retorna_401(
        self,
        mock_autenticar: Mock,
    ) -> None:
        """Deve retornar 401 quando as credenciais forem inválidas."""
        mock_autenticar.side_effect = LoginError("Senha inválida.")

        response = self.client.post(
            self.url,
            {"login": "1234567", "senha": "errada"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Login ou senha inválidos."}

    @patch("apps.login.api.views.LoginService.autenticar_e_criar_sessao")
    def test_usuario_inexistente_retorna_401(
        self,
        mock_autenticar: Mock,
    ) -> None:
        """Deve retornar 401 (não 404) quando o usuário não existir."""
        mock_autenticar.side_effect = LoginError("Usuário não encontrado.")

        response = self.client.post(
            self.url,
            {"login": "0000000", "senha": "qualquer"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Login ou senha inválidos."}

    @patch("apps.login.api.views.LoginService.autenticar_e_criar_sessao")
    def test_gateway_indisponivel_na_autenticacao_retorna_502(
        self,
        mock_autenticar: Mock,
    ) -> None:
        """Deve retornar 502 quando o Gateway estiver indisponível."""
        mock_autenticar.side_effect = GatewayIndisponivelError("timeout")

        response = self.client.post(
            self.url,
            {"login": "1234567", "senha": "senha-correta"},
            format="json",
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert response.json() == {"detail": "Gateway indisponível."}

    def test_payload_incompleto_retorna_400(self) -> None:
        """Deve retornar 400 quando faltar campo obrigatório."""
        response = self.client.post(
            self.url,
            {"login": "1234567"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_deve_exigir_api_key(self) -> None:
        """Deve exigir a API Key para autenticar."""
        client = APIClient()

        response = client.post(
            self.url,
            {"login": "1234567", "senha": "senha-correta"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

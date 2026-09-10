"""Testes das views da API de sessão compartilhada."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.sessoes.dominio import Sessao
from apps.sessoes.services import GatewayIndisponivelError, ResultadoValidacao

_AGORA = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)


def _sessao(**overrides: object) -> Sessao:
    dados = {
        "sessao_id": uuid4(),
        "login": "1234567",
        "kc_user_id": "kc-user-id",
        "sistemas": [{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
        "criado_em": _AGORA,
        "ultima_atividade": _AGORA,
        "expira_em": _AGORA + timedelta(hours=8),
    }
    dados.update(overrides)
    return Sessao(**dados)  # type: ignore[arg-type]


class TestCriarSessaoView(SimpleTestCase):
    """Testes de CriarSessaoView."""

    def setUp(self) -> None:
        """Cria os dados utilizados pelos testes."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=settings.API_KEY)
        self.url = reverse("criar-sessao")

    @patch("apps.sessoes.api.views.SessaoService.criar")
    def test_deve_criar_sessao_com_sucesso(
        self,
        mock_criar: Mock,
    ) -> None:
        """Deve retornar 201 com a sessão criada."""
        mock_criar.return_value = _sessao()

        response = self.client.post(
            self.url,
            {"login": "1234567", "kc_user_id": "kc-user-id"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        corpo = response.json()
        assert corpo["login"] == "1234567"
        assert corpo["sistemas"] == [
            {"sistema_id": 1, "sistema_nome": "CoreSSO"}
        ]

    @patch("apps.sessoes.api.views.SessaoService.criar")
    def test_deve_retornar_502_quando_gateway_indisponivel(
        self,
        mock_criar: Mock,
    ) -> None:
        """Deve retornar 502 quando o Gateway estiver indisponível."""
        mock_criar.side_effect = GatewayIndisponivelError("timeout")

        response = self.client.post(
            self.url,
            {"login": "1234567", "kc_user_id": "kc-user-id"},
            format="json",
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY

    def test_deve_exigir_api_key(self) -> None:
        """Deve exigir a API Key para criar a sessão."""
        client = APIClient()

        response = client.post(
            self.url,
            {"login": "1234567", "kc_user_id": "kc-user-id"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deve_retornar_400_quando_payload_invalido(self) -> None:
        """Deve retornar 400 quando faltar campo obrigatório."""
        response = self.client.post(
            self.url,
            {"login": "1234567"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestConsultarSessaoView(SimpleTestCase):
    """Testes de ConsultarSessaoView."""

    def setUp(self) -> None:
        """Cria os dados utilizados pelos testes."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=settings.API_KEY)
        self.sessao_id = uuid4()
        self.url = reverse(
            "consultar-sessao",
            kwargs={"sessao_id": self.sessao_id},
        )

    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_retornar_sessao_valida(
        self,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar 200 com situação válida."""
        mock_validar.return_value = ResultadoValidacao(
            situacao="valida",
            sessao=_sessao(sessao_id=self.sessao_id),
        )

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["situacao"] == "valida"

    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_retornar_sessao_expirada_por_inatividade(
        self,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar 200 com situação expirada por inatividade."""
        mock_validar.return_value = ResultadoValidacao(
            situacao="expirada_por_inatividade",
            sessao=_sessao(sessao_id=self.sessao_id),
        )

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["situacao"] == "expirada_por_inatividade"

    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_retornar_404_quando_sessao_nao_existir(
        self,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar 404 quando a sessão não for encontrada."""
        mock_validar.return_value = ResultadoValidacao(
            situacao="nao_encontrada",
            sessao=None,
            cache_disponivel=True,
        )

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_retornar_503_quando_cache_indisponivel(
        self,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar 503 quando não for possível confirmar o miss."""
        mock_validar.return_value = ResultadoValidacao(
            situacao="nao_encontrada",
            sessao=None,
            cache_disponivel=False,
        )

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestRenovarSessaoView(SimpleTestCase):
    """Testes de RenovarSessaoView."""

    def setUp(self) -> None:
        """Cria os dados utilizados pelos testes."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=settings.API_KEY)
        self.sessao_id = uuid4()
        self.url = reverse(
            "renovar-sessao",
            kwargs={"sessao_id": self.sessao_id},
        )

    @patch("apps.sessoes.api.views.SessaoService.renovar")
    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_renovar_sessao_valida(
        self,
        mock_validar: Mock,
        mock_renovar: Mock,
    ) -> None:
        """Deve retornar 200 com a sessão renovada."""
        sessao = _sessao(sessao_id=self.sessao_id)
        mock_validar.return_value = ResultadoValidacao(
            situacao="valida",
            sessao=sessao,
        )
        mock_renovar.return_value = sessao

        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_200_OK

    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_retornar_409_quando_sessao_expirada(
        self,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar 409 quando a sessão já estiver expirada."""
        mock_validar.return_value = ResultadoValidacao(
            situacao="expirada_por_duracao_maxima",
            sessao=_sessao(sessao_id=self.sessao_id),
        )

        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_409_CONFLICT

    @patch("apps.sessoes.api.views.SessaoService.validar")
    def test_deve_retornar_404_quando_sessao_nao_existir(
        self,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar 404 quando a sessão não for encontrada."""
        mock_validar.return_value = ResultadoValidacao(
            situacao="nao_encontrada",
            sessao=None,
        )

        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestLogoutSessaoView(SimpleTestCase):
    """Testes de LogoutSessaoView."""

    def setUp(self) -> None:
        """Cria os dados utilizados pelos testes."""
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=settings.API_KEY)
        self.sessao_id = uuid4()
        self.url = reverse(
            "logout-sessao",
            kwargs={"sessao_id": self.sessao_id},
        )

    @patch("apps.sessoes.api.views.notificar_logout_global")
    @patch("apps.sessoes.api.views.SessaoService.encerrar")
    def test_deve_encerrar_sessao_com_notificacoes_mistas(
        self,
        mock_encerrar: Mock,
        mock_notificar: Mock,
    ) -> None:
        """Deve retornar 200 mesmo com falha parcial nas notificações."""
        sessao = _sessao(
            sessao_id=self.sessao_id,
            sistemas=[
                {"sistema_id": 1, "sistema_nome": "CoreSSO"},
                {"sistema_id": 176, "sistema_nome": "Boletim Online"},
            ],
        )
        mock_encerrar.return_value = sessao
        mock_notificar.return_value = [
            {
                "sistema_id": 1,
                "sistema_nome": "CoreSSO",
                "sucesso": True,
                "detalhe": None,
            },
            {
                "sistema_id": 176,
                "sistema_nome": "Boletim Online",
                "sucesso": False,
                "detalhe": "timeout",
            },
        ]

        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_200_OK
        corpo = response.json()
        assert corpo["situacao"] == "sessao_encerrada"
        assert len(corpo["notificacoes"]) == 2
        assert corpo["notificacoes"][0]["sucesso"] is True
        assert corpo["notificacoes"][1]["sucesso"] is False

    @patch("apps.sessoes.api.views.SessaoService.encerrar")
    def test_deve_retornar_404_quando_sessao_nao_existir(
        self,
        mock_encerrar: Mock,
    ) -> None:
        """Deve retornar 404 quando a sessão já não existir."""
        mock_encerrar.return_value = None

        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deve_exigir_api_key(self) -> None:
        """Deve exigir a API Key para encerrar a sessão."""
        client = APIClient()

        response = client.post(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

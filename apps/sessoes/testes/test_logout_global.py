"""Testes da propagação de logout global."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from django.test import SimpleTestCase, override_settings

from apps.sessoes.dominio import Sessao
from apps.sessoes.logout_global import notificar_logout_global

_AGORA = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)


def _sessao(sistemas: list[dict]) -> Sessao:
    return Sessao(
        sessao_id=uuid4(),
        login="1234567",
        kc_user_id="kc-user-id",
        sistemas=sistemas,
        criado_em=_AGORA,
        ultima_atividade=_AGORA,
        expira_em=_AGORA + timedelta(hours=8),
    )


class TestNotificarLogoutGlobal(SimpleTestCase):
    """Testes de :func:`notificar_logout_global`."""

    @override_settings(
        LOGOUT_CALLBACKS={
            1: "http://sistema-a/logout/",
            2: "http://sistema-b/logout/",
        },
        SSO_LOGOUT_CALLBACK_TIMEOUT=5,
    )
    @patch("apps.sessoes.logout_global.httpx.post")
    def test_todos_os_sistemas_respondendo_sucesso(
        self,
        mock_post: Mock,
    ) -> None:
        """Deve marcar sucesso quando todos os sistemas respondem 2xx."""
        mock_post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "http://sistema/logout/"),
        )

        sessao = _sessao(
            [
                {"sistema_id": 1, "sistema_nome": "Sistema A"},
                {"sistema_id": 2, "sistema_nome": "Sistema B"},
            ]
        )

        resultados = notificar_logout_global(sessao)

        self.assertEqual(len(resultados), 2)
        self.assertTrue(all(r["sucesso"] for r in resultados))
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(
        LOGOUT_CALLBACKS={1: "http://sistema-a/logout/"},
        SSO_LOGOUT_CALLBACK_TIMEOUT=5,
        API_KEY_GATEWAY_MS="chave-gateway",
        API_KEY_GATEWAY_MS_HEADER="X-API-Key",
    )
    @patch("apps.sessoes.logout_global.httpx.post")
    def test_notificacao_envia_api_key_do_gateway(
        self,
        mock_post: Mock,
    ) -> None:
        """Deve enviar a mesma API Key usada para consultar o Gateway."""
        mock_post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "http://sistema-a/logout/"),
        )

        sessao = _sessao([{"sistema_id": 1, "sistema_nome": "Sistema A"}])

        notificar_logout_global(sessao)

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["X-API-Key"], "chave-gateway")

    @override_settings(LOGOUT_CALLBACKS={})
    @patch("apps.sessoes.logout_global.httpx.post")
    def test_sistema_sem_callback_nao_tenta_rede(
        self,
        mock_post: Mock,
    ) -> None:
        """Não deve chamar a rede para sistema sem callback registrado."""
        sessao = _sessao([{"sistema_id": 99, "sistema_nome": "Sem URL"}])

        resultados = notificar_logout_global(sessao)

        self.assertEqual(len(resultados), 1)
        self.assertFalse(resultados[0]["sucesso"])
        self.assertEqual(resultados[0]["detalhe"], "sem callback registrado")
        mock_post.assert_not_called()

    @override_settings(
        LOGOUT_CALLBACKS={
            1: "http://sistema-a/logout/",
            2: "http://sistema-b/logout/",
        },
        SSO_LOGOUT_CALLBACK_TIMEOUT=5,
    )
    @patch("apps.sessoes.logout_global.httpx.post")
    def test_falha_em_um_sistema_nao_afeta_os_demais(
        self,
        mock_post: Mock,
    ) -> None:
        """Deve isolar a falha de um sistema sem afetar os demais."""

        def _post(url: str, **kwargs: object) -> httpx.Response:
            if url == "http://sistema-a/logout/":
                raise httpx.TimeoutException("timeout")
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
            )

        mock_post.side_effect = _post

        sessao = _sessao(
            [
                {"sistema_id": 1, "sistema_nome": "Sistema A"},
                {"sistema_id": 2, "sistema_nome": "Sistema B"},
            ]
        )

        resultados = notificar_logout_global(sessao)

        por_sistema = {r["sistema_id"]: r for r in resultados}

        self.assertFalse(por_sistema[1]["sucesso"])
        self.assertTrue(por_sistema[2]["sucesso"])

    @override_settings(
        LOGOUT_CALLBACKS={1: "http://sistema-a/logout/"},
        SSO_LOGOUT_CALLBACK_TIMEOUT=5,
    )
    @patch("apps.sessoes.logout_global.httpx.post")
    def test_status_nao_2xx_e_tratado_como_falha(
        self,
        mock_post: Mock,
    ) -> None:
        """Deve tratar status HTTP não-2xx como falha, sem lançar."""
        mock_post.return_value = httpx.Response(
            500,
            request=httpx.Request("POST", "http://sistema-a/logout/"),
        )

        sessao = _sessao([{"sistema_id": 1, "sistema_nome": "Sistema A"}])

        resultados = notificar_logout_global(sessao)

        self.assertFalse(resultados[0]["sucesso"])
        self.assertEqual(resultados[0]["detalhe"], "status 500")

    @override_settings(LOGOUT_CALLBACKS={})
    def test_nunca_lanca_mesmo_sem_nenhum_callback(self) -> None:
        """Nunca deve lançar exceção, mesmo com todos os sistemas falhando."""
        sessao = _sessao(
            [
                {"sistema_id": 1, "sistema_nome": "Sistema A"},
                {"sistema_id": 2, "sistema_nome": "Sistema B"},
            ]
        )

        resultados = notificar_logout_global(sessao)

        self.assertEqual(len(resultados), 2)
        self.assertTrue(all(not r["sucesso"] for r in resultados))

    def test_sessao_sem_sistemas_retorna_lista_vazia(self) -> None:
        """Deve retornar lista vazia quando a sessão não tem sistemas."""
        sessao = _sessao([])

        resultados = notificar_logout_global(sessao)

        self.assertEqual(resultados, [])

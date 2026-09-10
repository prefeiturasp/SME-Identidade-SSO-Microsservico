"""Testes do serviço de domínio da sessão compartilhada."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID, uuid4

import httpx
from django.test import SimpleTestCase, override_settings

from apps.sessoes.dominio import Sessao
from apps.sessoes.services import GatewayIndisponivelError, SessaoService

_AGORA = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)


def _mock_cliente(resposta: httpx.Response) -> MagicMock:
    """Mock do cliente HTTP do Gateway, no formato de context manager."""
    cliente = MagicMock()
    cliente.get.return_value = resposta
    contexto = MagicMock()
    contexto.__enter__.return_value = cliente
    contexto.__exit__.return_value = False
    return contexto


def _resposta_sistemas(
    corpo: dict | None,
    status_code: int = 200,
) -> httpx.Response:
    """Resposta simulada do endpoint de sistemas do Gateway."""
    return httpx.Response(
        status_code,
        json=corpo,
        request=httpx.Request(
            "GET",
            "http://gateway-ms/api/v1/autenticacao/"
            "usuarios/1234567/sistemas/",
        ),
    )


@override_settings(
    SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800,
    SESSAO_DURACAO_MAXIMA_SEGUNDOS=28800,
)
class TestSessaoServiceCriar(SimpleTestCase):
    """Testes de :meth:`SessaoService.criar`."""

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.cliente_gateway_ms")
    def test_deve_criar_sessao_com_sistemas_do_gateway(
        self,
        mock_cliente_gateway: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve criar a sessão com os sistemas retornados pelo Gateway."""
        sistemas = [{"sistema_id": 1, "sistema_nome": "CoreSSO"}]
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_sistemas({"sistemas": sistemas})
        )

        sessao = SessaoService.criar("1234567", "kc-user-id")

        self.assertEqual(sessao.login, "1234567")
        self.assertEqual(sessao.kc_user_id, "kc-user-id")
        self.assertEqual(sessao.sistemas, sistemas)
        self.assertEqual(sessao.criado_em, _AGORA)
        self.assertEqual(sessao.ultima_atividade, _AGORA)
        self.assertEqual(
            sessao.expira_em,
            _AGORA + timedelta(seconds=28800),
        )

        mock_salvar.assert_called_once()
        chave, valor = mock_salvar.call_args.args
        self.assertEqual(chave, f"sessao:{sessao.sessao_id}")
        self.assertEqual(valor, sessao.to_dict())
        self.assertEqual(mock_salvar.call_args.kwargs["timeout"], 1800)

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.cliente_gateway_ms")
    def test_deve_criar_sessao_sem_sistemas_quando_gateway_retorna_204(
        self,
        mock_cliente_gateway: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve criar a sessão com lista vazia quando o Gateway retorna 204."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_sistemas(None, status_code=204)
        )

        sessao = SessaoService.criar("0000000", "kc-user-id")

        self.assertEqual(sessao.sistemas, [])

    @patch("apps.sessoes.services.cliente_gateway_ms")
    def test_deve_levantar_erro_quando_gateway_da_timeout(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve levantar GatewayIndisponivelError em timeout do Gateway."""
        contexto = MagicMock()
        contexto.__enter__.return_value.get.side_effect = (
            httpx.TimeoutException("timeout")
        )
        mock_cliente_gateway.return_value = contexto

        with self.assertRaises(GatewayIndisponivelError):
            SessaoService.criar("1234567", "kc-user-id")

    @patch("apps.sessoes.services.cliente_gateway_ms")
    def test_deve_levantar_erro_quando_gateway_retorna_erro_generico(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve levantar GatewayIndisponivelError em erro genérico."""
        mock_cliente_gateway.return_value = _mock_cliente(
            _resposta_sistemas({"erro": "erro interno"}, status_code=500)
        )

        with self.assertRaises(GatewayIndisponivelError):
            SessaoService.criar("1234567", "kc-user-id")


class TestSessaoServiceValidar(SimpleTestCase):
    """Testes de :meth:`SessaoService.validar`."""

    def _sessao(
        self,
        ultima_atividade: datetime,
        expira_em: datetime,
    ) -> Sessao:
        return Sessao(
            sessao_id=uuid4(),
            login="1234567",
            kc_user_id="kc-user-id",
            sistemas=[],
            criado_em=_AGORA - timedelta(hours=1),
            ultima_atividade=ultima_atividade,
            expira_em=expira_em,
        )

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    @override_settings(SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800)
    def test_sessao_dentro_da_janela_e_valida(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve retornar situação válida dentro da janela de atividade."""
        sessao = self._sessao(
            ultima_atividade=_AGORA - timedelta(minutes=10),
            expira_em=_AGORA + timedelta(hours=4),
        )
        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(resultado.situacao, "valida")
        self.assertEqual(resultado.sessao, sessao)

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    @override_settings(SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800)
    def test_sessao_inativa_alem_do_limite_expira_por_inatividade(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve expirar por inatividade além do tempo configurado."""
        sessao = self._sessao(
            ultima_atividade=_AGORA - timedelta(hours=1),
            expira_em=_AGORA + timedelta(hours=4),
        )
        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(resultado.situacao, "expirada_por_inatividade")

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    @override_settings(SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800)
    def test_sessao_alem_da_duracao_maxima_expira_mesmo_com_atividade(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve expirar por duração máxima mesmo com atividade recente."""
        sessao = self._sessao(
            ultima_atividade=_AGORA - timedelta(minutes=1),
            expira_em=_AGORA - timedelta(seconds=1),
        )
        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(resultado.situacao, "expirada_por_duracao_maxima")

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_inexistente_com_cache_disponivel_e_nao_encontrada(
        self,
        mock_obter: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve retornar não encontrada quando o cache confirma o miss."""
        mock_obter.return_value = None
        mock_disponivel.return_value = True

        resultado = SessaoService.validar(uuid4())

        self.assertEqual(resultado.situacao, "nao_encontrada")
        self.assertTrue(resultado.cache_disponivel)

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_inexistente_com_cache_indisponivel_sinaliza_indisponivel(
        self,
        mock_obter: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve sinalizar cache indisponível quando não confirma o miss."""
        mock_obter.return_value = None
        mock_disponivel.return_value = False

        resultado = SessaoService.validar(uuid4())

        self.assertEqual(resultado.situacao, "nao_encontrada")
        self.assertFalse(resultado.cache_disponivel)


class TestSessaoServiceRenovar(SimpleTestCase):
    """Testes de :meth:`SessaoService.renovar`."""

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.CacheService.obter")
    @override_settings(SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800)
    def test_deve_renovar_sessao_valida(
        self,
        mock_obter: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve atualizar ultima_atividade de uma sessão válida."""
        sessao = Sessao(
            sessao_id=uuid4(),
            login="1234567",
            kc_user_id="kc-user-id",
            sistemas=[],
            criado_em=_AGORA - timedelta(hours=1),
            ultima_atividade=_AGORA - timedelta(minutes=10),
            expira_em=_AGORA + timedelta(hours=4),
        )
        mock_obter.return_value = sessao.to_dict()

        renovada = SessaoService.renovar(sessao.sessao_id)

        self.assertIsNotNone(renovada)
        assert renovada is not None
        self.assertEqual(renovada.ultima_atividade, _AGORA)
        mock_salvar.assert_called_once()

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.CacheService.obter")
    @override_settings(SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800)
    def test_nao_deve_renovar_sessao_expirada(
        self,
        mock_obter: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Não deve renovar (nem salvar) uma sessão já expirada."""
        sessao = Sessao(
            sessao_id=uuid4(),
            login="1234567",
            kc_user_id="kc-user-id",
            sistemas=[],
            criado_em=_AGORA - timedelta(hours=1),
            ultima_atividade=_AGORA - timedelta(hours=1),
            expira_em=_AGORA + timedelta(hours=4),
        )
        mock_obter.return_value = sessao.to_dict()

        renovada = SessaoService.renovar(sessao.sessao_id)

        self.assertIsNone(renovada)
        mock_salvar.assert_not_called()


class TestSessaoServiceEncerrar(SimpleTestCase):
    """Testes de :meth:`SessaoService.encerrar`."""

    @patch("apps.sessoes.services.CacheService.invalidar")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_deve_encerrar_sessao_existente(
        self,
        mock_obter: Mock,
        mock_invalidar: Mock,
    ) -> None:
        """Deve invalidar a chave e retornar a sessão encerrada."""
        sessao = Sessao(
            sessao_id=uuid4(),
            login="1234567",
            kc_user_id="kc-user-id",
            sistemas=[{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
            criado_em=_AGORA,
            ultima_atividade=_AGORA,
            expira_em=_AGORA + timedelta(hours=8),
        )
        mock_obter.return_value = sessao.to_dict()

        encerrada = SessaoService.encerrar(sessao.sessao_id)

        self.assertEqual(encerrada, sessao)
        mock_invalidar.assert_called_once_with(f"sessao:{sessao.sessao_id}")

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.invalidar")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_encerrar_sessao_inexistente_e_idempotente(
        self,
        mock_obter: Mock,
        mock_invalidar: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve retornar None sem lançar ao encerrar sessão inexistente."""
        mock_obter.return_value = None
        mock_disponivel.return_value = True

        resultado = SessaoService.encerrar(UUID(int=0))

        self.assertIsNone(resultado)
        mock_invalidar.assert_not_called()

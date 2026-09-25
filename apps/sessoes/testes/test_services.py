"""Testes do serviço de domínio da sessão compartilhada."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import httpx
from django.test import SimpleTestCase, override_settings

from apps.sessoes.dominio import Sessao
from apps.sessoes.services import (
    GatewayIndisponivelError,
    ResultadoValidacao,
    SessaoService,
)

_AGORA = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)


def _resposta_sistemas(
    corpo: dict | None,
    status_code: int = 200,
) -> httpx.Response:
    """Cria uma resposta simulada do endpoint de sistemas do Gateway."""
    return httpx.Response(
        status_code=status_code,
        json=corpo,
        request=httpx.Request(
            "GET",
            "http://gateway-ms/api/v1/autenticacao/"
            "usuarios/1234567/sistemas/",
        ),
    )


def _sessao(
    *,
    ultima_atividade: datetime | None = None,
    expira_em: datetime | None = None,
) -> Sessao:
    """Cria uma sessão válida para os testes."""
    return Sessao(
        sessao_id=uuid4(),
        login="1234567",
        kc_user_id="kc-user-id",
        sistemas=[
            {
                "sistema_id": 1,
                "sistema_nome": "CoreSSO",
            }
        ],
        criado_em=_AGORA - timedelta(hours=1),
        ultima_atividade=ultima_atividade or (_AGORA - timedelta(minutes=10)),
        expira_em=expira_em or (_AGORA + timedelta(hours=4)),
    )


@override_settings(
    SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800,
    SESSAO_DURACAO_MAXIMA_SEGUNDOS=28800,
)
class TestSessaoServiceCriar(SimpleTestCase):
    """Testes de SessaoService.criar."""

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services._client")
    def test_deve_criar_sessao_com_sistemas_do_gateway(
        self,
        mock_cliente_gateway: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve criar a sessão com os sistemas retornados pelo Gateway."""
        sistemas = [
            {
                "sistema_id": 1,
                "sistema_nome": "CoreSSO",
            }
        ]

        mock_cliente_gateway.get.return_value = _resposta_sistemas(
            {"sistemas": sistemas}
        )

        sessao = SessaoService.criar(
            "1234567",
            "kc-user-id",
        )

        self.assertEqual(sessao.login, "1234567")
        self.assertEqual(sessao.kc_user_id, "kc-user-id")
        self.assertEqual(sessao.sistemas, sistemas)
        self.assertEqual(sessao.criado_em, _AGORA)
        self.assertEqual(sessao.ultima_atividade, _AGORA)
        self.assertEqual(
            sessao.expira_em,
            _AGORA + timedelta(seconds=28800),
        )

        mock_cliente_gateway.get.assert_called_once_with(
            "/api/v1/autenticacao/usuarios/1234567/sistemas/",
        )

        mock_salvar.assert_called_once()

        chave, valor = mock_salvar.call_args.args

        self.assertEqual(
            chave,
            f"sessao:{sessao.sessao_id}",
        )
        self.assertEqual(
            valor,
            sessao.to_dict(),
        )
        self.assertEqual(
            mock_salvar.call_args.kwargs["timeout"],
            1800,
        )

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services._client")
    def test_deve_criar_sessao_sem_sistemas_quando_gateway_retorna_204(
        self,
        mock_cliente_gateway: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve criar sessão vazia quando usuário não possui sistemas."""
        mock_cliente_gateway.get.return_value = _resposta_sistemas(
            None,
            status_code=204,
        )

        sessao = SessaoService.criar(
            "0000000",
            "kc-user-id",
        )

        self.assertEqual(sessao.sistemas, [])
        mock_salvar.assert_called_once()

    @patch("apps.sessoes.services._client")
    def test_deve_levantar_erro_quando_gateway_da_timeout(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve converter timeout em GatewayIndisponivelError."""
        erro_original = httpx.TimeoutException("timeout")

        mock_cliente_gateway.get.side_effect = erro_original

        with self.assertRaises(GatewayIndisponivelError) as contexto:
            SessaoService.criar(
                "1234567",
                "kc-user-id",
            )

        self.assertEqual(
            str(contexto.exception),
            "timeout",
        )
        self.assertIs(
            contexto.exception.__cause__,
            erro_original,
        )

    @patch("apps.sessoes.services._client")
    def test_deve_levantar_erro_quando_gateway_retorna_erro_generico(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve rejeitar status inesperado retornado pelo Gateway."""
        mock_cliente_gateway.get.return_value = _resposta_sistemas(
            {"erro": "erro interno"},
            status_code=500,
        )

        with self.assertRaisesRegex(
            GatewayIndisponivelError,
            "Gateway retornou status 500.",
        ):
            SessaoService.criar(
                "1234567",
                "kc-user-id",
            )


class TestSessaoServiceObterSistemas(SimpleTestCase):
    """Testes de SessaoService._obter_sistemas_do_usuario."""

    @patch("apps.sessoes.services._client")
    def test_deve_retornar_sistemas_do_gateway(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve retornar a lista de sistemas presente no JSON."""
        sistemas = [
            {
                "sistema_id": 1,
                "sistema_nome": "CoreSSO",
            },
            {
                "sistema_id": 2,
                "sistema_nome": "Outro sistema",
            },
        ]

        mock_cliente_gateway.get.return_value = _resposta_sistemas(
            {"sistemas": sistemas}
        )

        resultado = SessaoService._obter_sistemas_do_usuario("1234567")

        self.assertEqual(resultado, sistemas)

        mock_cliente_gateway.get.assert_called_once_with(
            "/api/v1/autenticacao/usuarios/1234567/sistemas/",
        )

    @patch("apps.sessoes.services._client")
    def test_deve_retornar_lista_vazia_quando_gateway_retorna_204(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve retornar lista vazia para resposta 204."""
        mock_cliente_gateway.get.return_value = _resposta_sistemas(
            None,
            status_code=204,
        )

        resultado = SessaoService._obter_sistemas_do_usuario("1234567")

        self.assertEqual(resultado, [])

    @patch("apps.sessoes.services._client")
    def test_deve_retornar_lista_vazia_quando_json_nao_tem_sistemas(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve usar lista vazia quando o campo sistemas está ausente."""
        mock_cliente_gateway.get.return_value = _resposta_sistemas({})

        resultado = SessaoService._obter_sistemas_do_usuario("1234567")

        self.assertEqual(resultado, [])

    @patch("apps.sessoes.services._client")
    def test_deve_converter_http_error_em_gateway_indisponivel(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve converter erros do HTTPX em GatewayIndisponivelError."""
        erro_original = httpx.ConnectError("connection refused")

        mock_cliente_gateway.get.side_effect = erro_original

        with self.assertRaises(GatewayIndisponivelError) as contexto:
            SessaoService._obter_sistemas_do_usuario("1234567")

        self.assertEqual(
            str(contexto.exception),
            "connection refused",
        )
        self.assertIs(
            contexto.exception.__cause__,
            erro_original,
        )

    @patch("apps.sessoes.services._client")
    def test_deve_levantar_erro_para_status_inesperado(
        self,
        mock_cliente_gateway: Mock,
    ) -> None:
        """Deve rejeitar status diferente de 200 e 204."""
        mock_cliente_gateway.get.return_value = _resposta_sistemas(
            {"erro": "serviço indisponível"},
            status_code=503,
        )

        with self.assertRaisesRegex(
            GatewayIndisponivelError,
            "Gateway retornou status 503.",
        ):
            SessaoService._obter_sistemas_do_usuario("1234567")


class TestSessaoServiceObter(SimpleTestCase):
    """Testes de SessaoService.obter."""

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_deve_retornar_sessao_quando_encontrada_no_cache(
        self,
        mock_obter: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve reconstruir a sessão encontrada no cache."""
        sessao = _sessao()
        mock_obter.return_value = sessao.to_dict()

        resultado, cache_disponivel = SessaoService.obter(sessao.sessao_id)

        self.assertEqual(resultado, sessao)
        self.assertTrue(cache_disponivel)

        mock_obter.assert_called_once_with(f"sessao:{sessao.sessao_id}")

        mock_disponivel.assert_not_called()

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_deve_retornar_none_quando_chave_nao_existe(
        self,
        mock_obter: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve distinguir cache disponível de sessão inexistente."""
        sessao_id = uuid4()

        mock_obter.return_value = None
        mock_disponivel.return_value = True

        resultado, cache_disponivel = SessaoService.obter(sessao_id)

        self.assertIsNone(resultado)
        self.assertTrue(cache_disponivel)

        mock_disponivel.assert_called_once_with()

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_deve_sinalizar_cache_indisponivel(
        self,
        mock_obter: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve informar quando o cache não está disponível."""
        mock_obter.return_value = None
        mock_disponivel.return_value = False

        resultado, cache_disponivel = SessaoService.obter(uuid4())

        self.assertIsNone(resultado)
        self.assertFalse(cache_disponivel)


@override_settings(
    SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800,
)
class TestSessaoServiceValidar(SimpleTestCase):
    """Testes de SessaoService.validar."""

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_dentro_da_janela_e_valida(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve retornar situação válida dentro da janela."""
        sessao = _sessao(
            ultima_atividade=_AGORA - timedelta(minutes=10),
            expira_em=_AGORA + timedelta(hours=4),
        )

        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(
            resultado.situacao,
            "valida",
        )
        self.assertEqual(
            resultado.sessao,
            sessao,
        )
        self.assertTrue(
            resultado.cache_disponivel,
        )

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_exatamente_no_limite_de_inatividade_ainda_e_valida(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve aceitar sessão exatamente no limite de inatividade."""
        sessao = _sessao(
            ultima_atividade=_AGORA - timedelta(seconds=1800),
            expira_em=_AGORA + timedelta(hours=4),
        )

        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(
            resultado.situacao,
            "valida",
        )

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_inativa_alem_do_limite_expira_por_inatividade(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve expirar por inatividade acima do limite."""
        sessao = _sessao(
            ultima_atividade=(_AGORA - timedelta(seconds=1801)),
            expira_em=_AGORA + timedelta(hours=4),
        )

        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(
            resultado.situacao,
            "expirada_por_inatividade",
        )
        self.assertEqual(
            resultado.sessao,
            sessao,
        )

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_alem_da_duracao_maxima_expira_mesmo_com_atividade(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve priorizar a expiração por duração máxima."""
        sessao = _sessao(
            ultima_atividade=_AGORA - timedelta(minutes=1),
            expira_em=_AGORA - timedelta(seconds=1),
        )

        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(
            resultado.situacao,
            "expirada_por_duracao_maxima",
        )
        self.assertEqual(
            resultado.sessao,
            sessao,
        )

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_expira_quando_agora_e_igual_a_expira_em(
        self,
        mock_obter: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve expirar quando alcança exatamente a duração máxima."""
        sessao = _sessao(
            ultima_atividade=_AGORA - timedelta(minutes=1),
            expira_em=_AGORA,
        )

        mock_obter.return_value = sessao.to_dict()

        resultado = SessaoService.validar(sessao.sessao_id)

        self.assertEqual(
            resultado.situacao,
            "expirada_por_duracao_maxima",
        )

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

        self.assertEqual(
            resultado.situacao,
            "nao_encontrada",
        )
        self.assertIsNone(
            resultado.sessao,
        )
        self.assertTrue(
            resultado.cache_disponivel,
        )

    @patch("apps.sessoes.services.CacheService.disponivel")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_sessao_inexistente_com_cache_indisponivel_sinaliza_indisponivel(
        self,
        mock_obter: Mock,
        mock_disponivel: Mock,
    ) -> None:
        """Deve sinalizar quando o cache não pode confirmar a sessão."""
        mock_obter.return_value = None
        mock_disponivel.return_value = False

        resultado = SessaoService.validar(uuid4())

        self.assertEqual(
            resultado.situacao,
            "nao_encontrada",
        )
        self.assertIsNone(
            resultado.sessao,
        )
        self.assertFalse(
            resultado.cache_disponivel,
        )


@override_settings(
    SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800,
)
class TestSessaoServiceRenovar(SimpleTestCase):
    """Testes de SessaoService.renovar."""

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_deve_renovar_sessao_valida(
        self,
        mock_obter: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Deve atualizar ultima_atividade de uma sessão válida."""
        sessao = _sessao(
            ultima_atividade=_AGORA - timedelta(minutes=10),
            expira_em=_AGORA + timedelta(hours=4),
        )

        mock_obter.return_value = sessao.to_dict()

        renovada = SessaoService.renovar(sessao.sessao_id)

        self.assertIsNotNone(renovada)

        assert renovada is not None

        self.assertEqual(
            renovada.ultima_atividade,
            _AGORA,
        )

        mock_salvar.assert_called_once()

    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_nao_deve_renovar_sessao_expirada(
        self,
        mock_obter: Mock,
        mock_salvar: Mock,
        mock_now: Mock,
    ) -> None:
        """Não deve renovar uma sessão expirada."""
        sessao = _sessao(
            ultima_atividade=_AGORA - timedelta(hours=1),
            expira_em=_AGORA + timedelta(hours=4),
        )

        mock_obter.return_value = sessao.to_dict()

        renovada = SessaoService.renovar(sessao.sessao_id)

        self.assertIsNone(renovada)
        mock_salvar.assert_not_called()

    @patch("apps.sessoes.services.SessaoService.validar")
    @patch("apps.sessoes.services.SessaoService._salvar")
    def test_nao_deve_renovar_quando_sessao_nao_existe(
        self,
        mock_salvar: Mock,
        mock_validar: Mock,
    ) -> None:
        """Deve retornar None quando a validação não possui sessão."""
        sessao_id = uuid4()

        mock_validar.return_value = ResultadoValidacao(
            situacao="nao_encontrada",
            sessao=None,
            cache_disponivel=True,
        )

        resultado = SessaoService.renovar(sessao_id)

        self.assertIsNone(resultado)
        mock_salvar.assert_not_called()

    @patch("apps.sessoes.services.SessaoService.validar")
    @patch("apps.sessoes.services.SessaoService._salvar")
    def test_nao_deve_renovar_resultado_valido_sem_sessao(
        self,
        mock_salvar: Mock,
        mock_validar: Mock,
    ) -> None:
        """Cobre defensivamente um resultado válido sem sessão."""
        sessao_id = uuid4()

        mock_validar.return_value = ResultadoValidacao(
            situacao="valida",
            sessao=None,
        )

        resultado = SessaoService.renovar(sessao_id)

        self.assertIsNone(resultado)
        mock_salvar.assert_not_called()


class TestSessaoServiceEncerrar(SimpleTestCase):
    """Testes de SessaoService.encerrar."""

    @patch("apps.sessoes.services.CacheService.invalidar")
    @patch("apps.sessoes.services.CacheService.obter")
    def test_deve_encerrar_sessao_existente(
        self,
        mock_obter: Mock,
        mock_invalidar: Mock,
    ) -> None:
        """Deve invalidar a chave e retornar a sessão."""
        sessao = _sessao()

        mock_obter.return_value = sessao.to_dict()

        encerrada = SessaoService.encerrar(sessao.sessao_id)

        self.assertEqual(
            encerrada,
            sessao,
        )

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
        """Deve retornar None para uma sessão inexistente."""
        mock_obter.return_value = None
        mock_disponivel.return_value = True

        resultado = SessaoService.encerrar(UUID(int=0))

        self.assertIsNone(resultado)
        mock_invalidar.assert_not_called()


@override_settings(
    SESSAO_TEMPO_INATIVIDADE_SEGUNDOS=1800,
)
class TestSessaoServiceSalvar(SimpleTestCase):
    """Testes de SessaoService._salvar."""

    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    def test_ttl_deve_usar_tempo_de_inatividade_quando_menor(
        self,
        mock_now: Mock,
        mock_salvar: Mock,
    ) -> None:
        """Deve limitar o TTL pelo tempo máximo de inatividade."""
        sessao = _sessao(
            expira_em=_AGORA + timedelta(hours=4),
        )

        SessaoService._salvar(sessao)

        mock_salvar.assert_called_once_with(
            f"sessao:{sessao.sessao_id}",
            sessao.to_dict(),
            timeout=1800,
        )

    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    def test_ttl_deve_usar_tempo_restante_quando_menor(
        self,
        mock_now: Mock,
        mock_salvar: Mock,
    ) -> None:
        """Deve limitar TTL pelo restante da duração máxima."""
        sessao = _sessao(
            expira_em=_AGORA + timedelta(seconds=600),
        )

        SessaoService._salvar(sessao)

        mock_salvar.assert_called_once_with(
            f"sessao:{sessao.sessao_id}",
            sessao.to_dict(),
            timeout=600,
        )

    @patch("apps.sessoes.services.CacheService.salvar")
    @patch("apps.sessoes.services.timezone.now", return_value=_AGORA)
    def test_ttl_deve_ser_zero_quando_sessao_ja_expirou(
        self,
        mock_now: Mock,
        mock_salvar: Mock,
    ) -> None:
        """Nunca deve gerar TTL negativo."""
        sessao = _sessao(
            expira_em=_AGORA - timedelta(seconds=10),
        )

        SessaoService._salvar(sessao)

        mock_salvar.assert_called_once_with(
            f"sessao:{sessao.sessao_id}",
            sessao.to_dict(),
            timeout=0,
        )

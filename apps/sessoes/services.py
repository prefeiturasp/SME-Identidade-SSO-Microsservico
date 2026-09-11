"""Serviço de domínio da sessão compartilhada."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from django.conf import settings
from django.utils import timezone

from apps.cache import chaves
from apps.cache.services import CacheService
from apps.gateway_ms.cliente import cliente_gateway_ms
from apps.sessoes.dominio import Sessao

logger = logging.getLogger(__name__)


class GatewayIndisponivelError(Exception):
    """O Gateway não respondeu a tempo ou está inacessível.

    Levantada na criação da sessão: sem saber os sistemas do usuário,
    a sessão não tem utilidade, então falhar é o comportamento
    correto em vez de degradar silenciosamente (diferente do padrão
    usado pelo Gateway ao consultar o Token-MS no login, onde a
    ausência de dados complementares não impede a autenticação).
    """


@dataclass
class ResultadoValidacao:
    """Resultado da validação de uma sessão.

    Attributes:
        situacao: Um de ``"valida"``, ``"expirada_por_inatividade"``,
            ``"expirada_por_duracao_maxima"`` ou ``"nao_encontrada"``.
        sessao: A sessão consultada, quando encontrada.
        cache_disponivel: ``False`` quando não foi possível confirmar
            se a sessão existe porque o cache está indisponível.
    """

    situacao: str
    sessao: Sessao | None
    cache_disponivel: bool = True


class SessaoService:
    """Serviço responsável pela sessão compartilhada."""

    @staticmethod
    def criar(login: str, kc_user_id: str) -> Sessao:
        """Cria uma nova sessão compartilhada.

        Consulta o Gateway para obter os sistemas aos quais o usuário
        tem acesso e grava a sessão no cache, com TTL calculado para
        nunca ultrapassar a duração máxima configurada.

        Args:
            login: Login do usuário autenticado.
            kc_user_id: Identificador do usuário no Keycloak.

        Returns:
            A sessão recém-criada.

        Raises:
            GatewayIndisponivelError: O Gateway não respondeu a tempo
                ou está inacessível.
        """
        sistemas = SessaoService._obter_sistemas_do_usuario(login)

        agora = timezone.now()

        sessao = Sessao(
            sessao_id=uuid4(),
            login=login,
            kc_user_id=kc_user_id,
            sistemas=sistemas,
            criado_em=agora,
            ultima_atividade=agora,
            expira_em=agora
            + timedelta(seconds=settings.SESSAO_DURACAO_MAXIMA_SEGUNDOS),
        )

        SessaoService._salvar(sessao)

        logger.info(
            "Sessão %s criada para o login %s com %d sistema(s).",
            sessao.sessao_id,
            login,
            len(sistemas),
        )

        return sessao

    @staticmethod
    def _obter_sistemas_do_usuario(login: str) -> list[dict]:
        """Consulta os sistemas do usuário no Gateway.

        Args:
            login: Login do usuário autenticado.

        Returns:
            Lista de sistemas (``sistema_id``, ``sistema_nome``); lista
            vazia se o Gateway responder 204 (usuário sem sistemas).

        Raises:
            GatewayIndisponivelError: O Gateway não respondeu a tempo
                ou está inacessível.
        """
        try:
            with cliente_gateway_ms() as cliente:
                resposta = cliente.get(
                    f"/api/v1/autenticacao/usuarios/{login}/sistemas/",
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "Falha ao consultar sistemas do usuário %s no Gateway: %s",
                login,
                exc,
            )
            raise GatewayIndisponivelError(str(exc)) from exc

        if resposta.status_code == 204:
            return []

        if resposta.status_code != 200:
            raise GatewayIndisponivelError(
                f"Gateway retornou status {resposta.status_code}."
            )

        corpo = resposta.json()
        sistemas: list[dict] = corpo.get("sistemas", [])
        return sistemas

    @staticmethod
    def obter(sessao_id: UUID) -> tuple[Sessao | None, bool]:
        """Obtém uma sessão do cache.

        Args:
            sessao_id: Identificador da sessão.

        Returns:
            Tupla ``(sessao, cache_disponivel)`` — ``sessao`` é
            ``None`` quando a chave não existe ou o cache está
            indisponível; ``cache_disponivel`` distingue os dois
            casos.
        """
        dados = CacheService.obter(chaves.sessao(sessao_id))

        if dados is not None:
            return Sessao.from_dict(dados), True  # type: ignore[arg-type]

        return None, CacheService.disponivel()

    @staticmethod
    def validar(sessao_id: UUID) -> ResultadoValidacao:
        """Valida uma sessão, sem renovar sua atividade.

        Operação de leitura pura — não atualiza ``ultima_atividade``,
        para que uma consulta não prolongue artificialmente uma
        sessão que deveria expirar por inatividade.

        Args:
            sessao_id: Identificador da sessão.

        Returns:
            Resultado da validação com a situação da sessão.
        """
        sessao, cache_disponivel = SessaoService.obter(sessao_id)

        if sessao is None:
            situacao = "nao_encontrada"
            return ResultadoValidacao(
                situacao=situacao,
                sessao=None,
                cache_disponivel=cache_disponivel,
            )

        agora = timezone.now()

        if agora >= sessao.expira_em:
            return ResultadoValidacao(
                situacao="expirada_por_duracao_maxima",
                sessao=sessao,
            )

        tempo_inativo = (agora - sessao.ultima_atividade).total_seconds()
        if tempo_inativo > settings.SESSAO_TEMPO_INATIVIDADE_SEGUNDOS:
            return ResultadoValidacao(
                situacao="expirada_por_inatividade",
                sessao=sessao,
            )

        return ResultadoValidacao(situacao="valida", sessao=sessao)

    @staticmethod
    def renovar(sessao_id: UUID) -> Sessao | None:
        """Renova a atividade de uma sessão válida.

        Args:
            sessao_id: Identificador da sessão.

        Returns:
            A sessão com ``ultima_atividade`` atualizada, ou ``None``
            se a sessão não existir ou já estiver expirada.
        """
        resultado = SessaoService.validar(sessao_id)

        if resultado.situacao != "valida" or resultado.sessao is None:
            return None

        sessao = resultado.sessao
        sessao.ultima_atividade = timezone.now()

        SessaoService._salvar(sessao)

        logger.info("Sessão %s renovada.", sessao_id)

        return sessao

    @staticmethod
    def encerrar(sessao_id: UUID) -> Sessao | None:
        """Encerra uma sessão, removendo-a do cache.

        Args:
            sessao_id: Identificador da sessão.

        Returns:
            A sessão que foi encerrada (para o chamador poder
            notificar os sistemas conectados), ou ``None`` se a
            sessão já não existia — encerrar uma sessão inexistente é
            idempotente, não é erro.
        """
        sessao, _ = SessaoService.obter(sessao_id)

        if sessao is None:
            return None

        CacheService.invalidar(chaves.sessao(sessao_id))

        logger.info("Sessão %s encerrada.", sessao_id)

        return sessao

    @staticmethod
    def _salvar(sessao: Sessao) -> None:
        """Grava a sessão no cache com o TTL calculado.

        O TTL é sempre o menor entre o tempo de inatividade
        configurado e o tempo restante até a duração máxima da
        sessão — garante que o KeyDB expurga a chave sozinho mesmo
        que a lógica de validação nunca seja chamada de novo.

        Args:
            sessao: Sessão a ser gravada.
        """
        segundos_restantes = (
            sessao.expira_em - timezone.now()
        ).total_seconds()

        ttl = max(
            0,
            min(
                settings.SESSAO_TEMPO_INATIVIDADE_SEGUNDOS,
                int(segundos_restantes),
            ),
        )

        CacheService.salvar(
            chaves.sessao(sessao.sessao_id),
            sessao.to_dict(),
            timeout=ttl,
        )

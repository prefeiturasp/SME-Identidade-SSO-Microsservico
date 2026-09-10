"""Propagação de logout global para os sistemas conectados à sessão."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict

import httpx
from django.conf import settings

from apps.sessoes.dominio import Sessao

logger = logging.getLogger(__name__)


class ResultadoNotificacao(TypedDict):
    """Resultado da notificação de logout a um sistema.

    Attributes:
        sistema_id: Identificador do sistema notificado.
        sistema_nome: Nome do sistema notificado.
        sucesso: ``True`` se a notificação foi entregue com sucesso.
        detalhe: Motivo da falha, quando ``sucesso`` é ``False``.
    """

    sistema_id: int
    sistema_nome: str
    sucesso: bool
    detalhe: str | None


def notificar_logout_global(sessao: Sessao) -> list[ResultadoNotificacao]:
    """Notifica os sistemas conectados à sessão sobre o logout global.

    Dispara uma notificação em paralelo para cada sistema com
    callback configurado (``settings.LOGOUT_CALLBACKS``). Sistemas
    sem callback registrado são marcados como falha sem tentativa de
    rede — não há ainda um cadastro de sistemas com metadados de URL,
    então essa configuração estática é uma lacuna conhecida, não um
    erro de execução.

    Cada notificação é enviada com a mesma API Key usada para
    consultar o Gateway (``settings.API_KEY_GATEWAY_MS``) — reaproveita
    a credencial já configurada em vez de introduzir uma chave dedicada
    por sistema de callback, já que hoje o único receptor real é o
    endpoint de teste E2E do próprio Gateway.

    Esta função nunca propaga exceção: cada falha (timeout, erro de
    transporte, status não-2xx, ausência de callback) é isolada por
    sistema e reportada no resultado, sem interromper a notificação
    dos demais.

    Args:
        sessao: Sessão encerrada, com a lista de sistemas conectados.

    Returns:
        Um resultado por sistema da sessão, na mesma ordem.
    """
    with ThreadPoolExecutor(
        max_workers=max(1, len(sessao.sistemas))
    ) as executor:
        resultados = list(
            executor.map(
                lambda sistema: _notificar_sistema(sistema, sessao),
                sessao.sistemas,
            )
        )

    return resultados


def _notificar_sistema(
    sistema: dict,
    sessao: Sessao,
) -> ResultadoNotificacao:
    """Notifica um único sistema sobre o logout global.

    Args:
        sistema: Dados do sistema (``sistema_id``, ``sistema_nome``).
        sessao: Sessão encerrada, usada para compor o payload enviado
            ao sistema.

    Returns:
        Resultado da notificação a esse sistema.
    """
    sistema_id = sistema["sistema_id"]
    sistema_nome = sistema["sistema_nome"]

    url = settings.LOGOUT_CALLBACKS.get(sistema_id)

    if not url:
        logger.info(
            "Sistema %s (%s) sem callback de logout registrado.",
            sistema_id,
            sistema_nome,
        )
        return ResultadoNotificacao(
            sistema_id=sistema_id,
            sistema_nome=sistema_nome,
            sucesso=False,
            detalhe="sem callback registrado",
        )

    try:
        resposta = httpx.post(
            url,
            json={
                "sessao_id": str(sessao.sessao_id),
                "login": sessao.login,
                "kc_user_id": sessao.kc_user_id,
            },
            headers={
                settings.API_KEY_GATEWAY_MS_HEADER: (
                    settings.API_KEY_GATEWAY_MS
                ),
            },
            timeout=settings.SSO_LOGOUT_CALLBACK_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Falha ao notificar logout ao sistema %s (%s): %s",
            sistema_id,
            sistema_nome,
            exc,
        )
        return ResultadoNotificacao(
            sistema_id=sistema_id,
            sistema_nome=sistema_nome,
            sucesso=False,
            detalhe=str(exc),
        )

    if not resposta.is_success:
        logger.warning(
            "Sistema %s (%s) respondeu %s à notificação de logout.",
            sistema_id,
            sistema_nome,
            resposta.status_code,
        )
        return ResultadoNotificacao(
            sistema_id=sistema_id,
            sistema_nome=sistema_nome,
            sucesso=False,
            detalhe=f"status {resposta.status_code}",
        )

    return ResultadoNotificacao(
        sistema_id=sistema_id,
        sistema_nome=sistema_nome,
        sucesso=True,
        detalhe=None,
    )

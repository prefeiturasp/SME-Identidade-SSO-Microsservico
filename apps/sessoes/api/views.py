"""Views da API de sessão compartilhada."""

import logging
from uuid import UUID

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sessoes.api.serializers import (
    CriarSessaoRequestSerializer,
    LogoutResponseSerializer,
    SessaoResponseSerializer,
    ValidarSessaoResponseSerializer,
)
from apps.sessoes.logout_global import notificar_logout_global
from apps.sessoes.services import GatewayIndisponivelError, SessaoService

logger = logging.getLogger(__name__)

_TAG = ["Sessões"]

_SESSAO_NAO_ENCONTRADA = {"detail": "Sessão não encontrada."}
_CACHE_INDISPONIVEL = {"detail": "Serviço de sessão indisponível."}


class CriarSessaoView(APIView):
    """Cria uma sessão compartilhada, pós-login."""

    @extend_schema(
        tags=_TAG,
        summary="Criar sessão compartilhada",
        description=(
            "Cria uma nova sessão compartilhada para o usuário "
            "autenticado, consultando os sistemas aos quais ele tem "
            "acesso no Gateway."
        ),
        request=CriarSessaoRequestSerializer,
        responses={
            status.HTTP_201_CREATED: SessaoResponseSerializer,
            status.HTTP_502_BAD_GATEWAY: OpenApiResponse(
                description="Gateway indisponível ou não respondeu a tempo.",
            ),
        },
    )
    def post(self, request: Request) -> Response:
        """Cria a sessão compartilhada.

        Args:
            request: Requisição HTTP com ``login`` e ``kc_user_id``.

        Returns:
            A sessão criada; 502 se o Gateway estiver inacessível ou
            não responder a tempo — sem saber os sistemas do usuário,
            a sessão não tem utilidade.
        """
        entrada = CriarSessaoRequestSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            sessao = SessaoService.criar(
                entrada.validated_data["login"],
                entrada.validated_data["kc_user_id"],
            )
        except GatewayIndisponivelError:
            logger.warning(
                "Falha ao criar sessão para %s: Gateway indisponível.",
                entrada.validated_data["login"],
            )
            return Response(
                {"detail": "Gateway indisponível."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        saida = SessaoResponseSerializer(sessao.to_dict())
        return Response(saida.data, status=status.HTTP_201_CREATED)


class ConsultarSessaoView(APIView):
    """Consulta/valida uma sessão compartilhada, sem renová-la."""

    @extend_schema(
        tags=_TAG,
        summary="Consultar sessão compartilhada",
        description=(
            "Consulta o estado atual de uma sessão compartilhada. "
            "Operação de leitura pura — não renova a atividade da "
            "sessão."
        ),
        responses={
            status.HTTP_200_OK: ValidarSessaoResponseSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Sessão não encontrada.",
            ),
            status.HTTP_503_SERVICE_UNAVAILABLE: OpenApiResponse(
                description="Serviço de sessão indisponível.",
            ),
        },
    )
    def get(self, request: Request, sessao_id: UUID) -> Response:
        """Consulta o estado de uma sessão.

        Args:
            request: Requisição HTTP recebida.
            sessao_id: Identificador da sessão.

        Returns:
            Estado da sessão (válida ou expirada); 404 se a sessão
            nunca existiu ou já expurgou; 503 se não for possível
            confirmar (cache indisponível).
        """
        resultado = SessaoService.validar(sessao_id)

        if resultado.sessao is None:
            if not resultado.cache_disponivel:
                return Response(
                    _CACHE_INDISPONIVEL,
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                _SESSAO_NAO_ENCONTRADA,
                status=status.HTTP_404_NOT_FOUND,
            )

        dados = resultado.sessao.to_dict()
        dados["situacao"] = resultado.situacao

        saida = ValidarSessaoResponseSerializer(dados)
        return Response(saida.data)


class RenovarSessaoView(APIView):
    """Renova a atividade de uma sessão compartilhada válida."""

    @extend_schema(
        tags=_TAG,
        summary="Renovar sessão compartilhada",
        description="Atualiza a última atividade de uma sessão válida.",
        responses={
            status.HTTP_200_OK: SessaoResponseSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Sessão não encontrada.",
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="Sessão expirada, não é possível renovar.",
            ),
        },
    )
    def post(self, request: Request, sessao_id: UUID) -> Response:
        """Renova a sessão.

        Args:
            request: Requisição HTTP recebida.
            sessao_id: Identificador da sessão.

        Returns:
            A sessão renovada; 409 se já estiver expirada; 404 se
            não existir.
        """
        resultado = SessaoService.validar(sessao_id)

        if resultado.sessao is None:
            return Response(
                _SESSAO_NAO_ENCONTRADA,
                status=status.HTTP_404_NOT_FOUND,
            )

        if resultado.situacao != "valida":
            return Response(
                {"detail": "Sessão expirada, não é possível renovar."},
                status=status.HTTP_409_CONFLICT,
            )

        sessao = SessaoService.renovar(sessao_id)
        assert sessao is not None  # já validada como "valida" acima

        saida = SessaoResponseSerializer(sessao.to_dict())
        return Response(saida.data)


class LogoutSessaoView(APIView):
    """Encerra uma sessão e propaga o logout aos sistemas conectados."""

    @extend_schema(
        tags=_TAG,
        summary="Encerrar sessão e propagar logout global",
        description=(
            "Encerra a sessão compartilhada e notifica, em paralelo, "
            "todos os sistemas conectados sobre o logout. A sessão é "
            "sempre encerrada — a notificação aos sistemas é melhor "
            "esforço e nunca impede a resposta."
        ),
        responses={
            status.HTTP_200_OK: LogoutResponseSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Sessão não encontrada.",
            ),
        },
    )
    def post(self, request: Request, sessao_id: UUID) -> Response:
        """Encerra a sessão e dispara o logout global.

        Args:
            request: Requisição HTTP recebida.
            sessao_id: Identificador da sessão.

        Returns:
            Confirmação do encerramento com o resumo das
            notificações por sistema; 404 se a sessão já não existia.
        """
        sessao = SessaoService.encerrar(sessao_id)

        if sessao is None:
            return Response(
                _SESSAO_NAO_ENCONTRADA,
                status=status.HTTP_404_NOT_FOUND,
            )

        notificacoes = notificar_logout_global(sessao)

        saida = LogoutResponseSerializer(
            {
                "sessao_id": sessao.sessao_id,
                "situacao": "sessao_encerrada",
                "notificacoes": notificacoes,
            }
        )
        return Response(saida.data)

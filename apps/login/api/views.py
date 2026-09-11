"""Views da API de login orquestrado."""

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.login.api.serializers import (
    LoginRequestSerializer,
    LoginResponseSerializer,
)
from apps.login.services import LoginError, LoginService
from apps.sessoes.services import GatewayIndisponivelError

logger = logging.getLogger(__name__)

_TAG = ["Login"]

_LOGIN_INVALIDO = {"detail": "Login ou senha inválidos."}
_GATEWAY_INDISPONIVEL = {"detail": "Gateway indisponível."}


class LoginView(APIView):
    """Autentica um usuário e cria sua sessão compartilhada.

    Orquestra, numa única chamada, o login no
    SME-Identidade-Gateway-Microsservico e a criação da sessão
    compartilhada no SSO-MS — equivale a
    ``POST /autenticacao/login/`` no Gateway seguido de
    ``POST /sessoes/`` aqui.
    """

    @extend_schema(
        tags=_TAG,
        summary="Login com criação de sessão compartilhada",
        request=LoginRequestSerializer,
        responses={
            status.HTTP_201_CREATED: LoginResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="Login ou senha inválidos.",
            ),
            status.HTTP_502_BAD_GATEWAY: OpenApiResponse(
                description="Gateway indisponível.",
            ),
        },
    )
    def post(self, request: Request) -> Response:
        """Autentica o usuário e cria a sessão compartilhada.

        Args:
            request: Requisição HTTP com ``login`` e ``senha``.

        Returns:
            Dados de autenticação e a sessão criada; 401 se as
            credenciais forem inválidas; 502 se o Gateway estiver
            inacessível na autenticação.
        """
        entrada = LoginRequestSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        login = entrada.validated_data["login"]

        try:
            resultado = LoginService.autenticar_e_criar_sessao(
                login,
                entrada.validated_data["senha"],
            )
        except LoginError:
            return Response(
                _LOGIN_INVALIDO,
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except GatewayIndisponivelError:
            logger.warning(
                "Falha ao autenticar %s: Gateway indisponível.",
                login,
            )
            return Response(
                _GATEWAY_INDISPONIVEL,
                status=status.HTTP_502_BAD_GATEWAY,
            )

        corpo = dict(resultado.dados_autenticacao)
        corpo["sessao"] = (
            resultado.sessao.to_dict() if resultado.sessao else None
        )
        corpo["sessao_erro"] = resultado.sessao_erro

        saida = LoginResponseSerializer(corpo)
        return Response(saida.data, status=status.HTTP_201_CREATED)

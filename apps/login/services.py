"""Serviço de login orquestrado: autenticação + sessão compartilhada."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from apps.gateway_ms.cliente import cliente_gateway_ms
from apps.sessoes.dominio import Sessao
from apps.sessoes.services import GatewayIndisponivelError, SessaoService

logger = logging.getLogger(__name__)


class LoginError(Exception):
    """Login ou senha inválidos.

    Levantada tanto para senha incorreta quanto para usuário
    inexistente no Keycloak — o SSO-MS trata os dois casos da mesma
    forma para não permitir que um consumidor descubra quais logins
    existem testando senhas em branco.
    """


@dataclass
class ResultadoLogin:
    """Resultado do login orquestrado.

    Attributes:
        dados_autenticacao: Dados retornados pelo Gateway (tokens,
            dados cadastrais, roles).
        sessao: A sessão compartilhada criada, ou ``None`` se a
            criação falhou por indisponibilidade do Gateway.
        sessao_erro: Motivo da falha na criação da sessão, quando
            ``sessao`` é ``None``.
    """

    dados_autenticacao: dict
    sessao: Sessao | None
    sessao_erro: str | None


class LoginService:
    """Autentica um usuário e cria sua sessão compartilhada."""

    @staticmethod
    def autenticar_e_criar_sessao(login: str, senha: str) -> ResultadoLogin:
        """Autentica no Gateway e cria a sessão compartilhada.

        A autenticação real acontece no Keycloak, via Gateway. Se ela
        for bem-sucedida mas a criação da sessão falhar por
        indisponibilidade do Gateway (segunda chamada, para obter os
        sistemas do usuário), o login não é desfeito — a sessão
        apenas fica ausente na resposta.

        Args:
            login: RF, CPF ou username do usuário.
            senha: Senha em texto plano.

        Returns:
            Dados de autenticação e a sessão criada (ou o motivo da
            falha, se a sessão não pôde ser criada).

        Raises:
            LoginError: Login ou senha inválidos.
            GatewayIndisponivelError: O Gateway não respondeu a tempo
                ou está inacessível na chamada de autenticação.
        """
        dados_autenticacao = LoginService._autenticar_no_gateway(
            login,
            senha,
        )

        try:
            sessao = SessaoService.criar(
                login,
                dados_autenticacao["kc_user_id"],
            )
            sessao_erro = None
        except GatewayIndisponivelError as exc:
            sessao = None
            sessao_erro = "Gateway indisponível ao criar sessão."
            logger.warning(
                "Login de %s OK, mas sessão não foi criada: %s",
                login,
                exc,
            )

        return ResultadoLogin(
            dados_autenticacao=dados_autenticacao,
            sessao=sessao,
            sessao_erro=sessao_erro,
        )

    @staticmethod
    def _autenticar_no_gateway(login: str, senha: str) -> dict:
        """Autentica o usuário no Gateway.

        Args:
            login: RF, CPF ou username do usuário.
            senha: Senha em texto plano.

        Returns:
            Corpo da resposta do Gateway (tokens, dados cadastrais).

        Raises:
            LoginError: Login ou senha inválidos.
            GatewayIndisponivelError: O Gateway não respondeu a tempo
                ou está inacessível.
        """
        try:
            with cliente_gateway_ms() as cliente:
                resposta = cliente.post(
                    "/api/v1/autenticacao/login/",
                    json={"login": login, "senha": senha},
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "Falha ao autenticar %s no Gateway: %s",
                login,
                exc,
            )
            raise GatewayIndisponivelError(str(exc)) from exc

        if resposta.status_code == 401:
            raise LoginError("Senha inválida.")

        if resposta.status_code == 204:
            raise LoginError("Usuário não encontrado.")

        if resposta.status_code != 200:
            raise GatewayIndisponivelError(
                f"Gateway retornou status {resposta.status_code}."
            )

        corpo: dict = resposta.json()
        return corpo

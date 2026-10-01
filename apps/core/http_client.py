"""Comunicação HTTP com serviços externos."""

from __future__ import annotations

from typing import cast

import httpx
from sme_sidecar_sdk import CircuitOpenError, build_http_client
from sme_sidecar_sdk.http import SyncHTTPClient


class ServiceClient:
    """Executa chamadas HTTP para serviços externos.

    Args:
        base_url: URL base do serviço externo.
        dominio: Nome do domínio associado ao cliente.
        api_key: Chave de autenticação enviada ao serviço externo.
        api_key_header: Nome do header usado para enviar a chave.
    """

    def __init__(
        self,
        base_url: str,
        dominio: str,
        api_key: str = "",
        api_key_header: str = "X-API-Key",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.dominio = dominio
        self._api_key = api_key
        self._api_key_header = api_key_header
        self._client: SyncHTTPClient | None = None

    def _http_client(self) -> SyncHTTPClient:
        """Retorna o cliente HTTP persistente.

        Returns:
            Cliente HTTP configurado com resiliência e observabilidade.
        """
        if self._client is None:
            self._client = build_http_client(
                self.dominio,
                base_url=self.base_url,
                follow_redirects=True,
            )

        return self._client

    def _headers(self) -> dict[str, str]:
        """Monta os headers padrão da requisição.

        Returns:
            Headers com Accept e API Key quando disponível.
        """
        headers = {"Accept": "application/json"}

        if self._api_key:
            headers[self._api_key_header] = self._api_key

        return headers

    def get(
        self,
        path: str,
        params: dict | None = None,
    ) -> httpx.Response:
        """Executa uma requisição GET.

        Args:
            path: Caminho relativo da requisição.
            params: Parâmetros de query enviados na requisição.

        Returns:
            Resposta HTTP recebida do serviço externo.

        Raises:
            httpx.HTTPError: Em caso de falha de transporte ou timeout.
        """
        try:
            return cast(
                httpx.Response,
                self._http_client().get(
                    path,
                    headers=self._headers(),
                    params=params,
                ),
            )
        except httpx.HTTPStatusError as exc:
            return exc.response
        except CircuitOpenError as exc:
            raise self._unavailable_error("GET", path) from exc

    def post(
        self,
        path: str,
        payload: dict | list | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Executa uma requisição POST.

        Args:
            path: Caminho relativo da requisição.
            payload: Corpo JSON enviado na requisição.
            params: Parâmetros de query enviados na requisição.

        Returns:
            Resposta HTTP recebida do serviço externo.

        Raises:
            httpx.HTTPError: Em caso de falha de transporte ou timeout.
        """
        try:
            return cast(
                httpx.Response,
                self._http_client().post(
                    path,
                    headers=self._headers(),
                    json=payload,
                    params=params,
                ),
            )
        except httpx.HTTPStatusError as exc:
            return exc.response
        except CircuitOpenError as exc:
            raise self._unavailable_error("POST", path) from exc

    def put(
        self,
        path: str,
        payload: dict | list | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Executa uma requisição PUT.

        Args:
            path: Caminho relativo da requisição.
            payload: Corpo JSON enviado na requisição.
            params: Parâmetros de query enviados na requisição.

        Returns:
            Resposta HTTP recebida do serviço externo.

        Raises:
            httpx.HTTPError: Em caso de falha de transporte ou timeout.
        """
        try:
            return cast(
                httpx.Response,
                self._http_client().put(
                    path,
                    headers=self._headers(),
                    json=payload,
                    params=params,
                ),
            )
        except httpx.HTTPStatusError as exc:
            return exc.response
        except CircuitOpenError as exc:
            raise self._unavailable_error("PUT", path) from exc

    def close(self) -> None:
        """Fecha conexões HTTP mantidas pelo cliente."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _unavailable_error(
        self,
        method: str,
        path: str,
    ) -> httpx.ConnectError:
        """Trata circuito aberto para erro de indisponibilidade HTTPX.

        Args:
            method: Método HTTP da chamada original.
            path: Caminho relativo chamado na API.

        Returns:
            Erro compatível com os handlers já existentes nas views.
        """
        request = httpx.Request(
            method,
            f"{self.base_url}{path}",
        )

        return httpx.ConnectError(
            f"Circuit breaker aberto para {self.dominio}",
            request=request,
        )

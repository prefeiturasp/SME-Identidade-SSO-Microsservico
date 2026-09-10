"""Testes para apps.autenticacao.api.autenticacao."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.autenticacao.api.autenticacao import AutenticacaoApiKey


class TestAutenticacaoApiKey(SimpleTestCase):
    """Testa a classe de autenticação por API Key."""

    def setUp(self) -> None:
        """Cria os objetos utilizados pelos testes."""
        self.factory = RequestFactory()
        self.auth = AutenticacaoApiKey()

    def _drf_request(
        self,
        headers: dict[str, str] | None = None,
    ) -> Request:
        """Cria uma requisição DRF para os testes."""
        extra: dict[str, Any] = headers or {}

        rf_request = self.factory.get(
            "/",
            **extra,
        )
        return Request(rf_request)

    def test_sem_header_retorna_none(self) -> None:
        """Verifica que a ausência do header de API Key retorna None."""
        settings.API_KEY = "chave-secreta"
        settings.API_KEY_HEADER = "X-API-Key"

        req = self._drf_request()

        assert self.auth.authenticate(req) is None

    def test_chave_correta_autentica(self) -> None:
        """Verifica que a chave correta autentica e retorna usuário."""
        settings.API_KEY = "chave-secreta"
        settings.API_KEY_HEADER = "X-API-Key"

        req = self._drf_request(
            {
                "HTTP_X_API_KEY": "chave-secreta",
            },
        )

        resultado = self.auth.authenticate(req)

        assert resultado is not None

        usuario, _ = resultado
        assert usuario.is_authenticated is True

    def test_chave_incorreta_lanca_excecao(self) -> None:
        """Verifica que uma chave incorreta lança AuthenticationFailed."""
        settings.API_KEY = "chave-correta"
        settings.API_KEY_HEADER = "X-API-Key"

        req = self._drf_request(
            {
                "HTTP_X_API_KEY": "chave-errada",
            },
        )

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(req)

    def test_authenticate_header_retorna_nome_do_header(self) -> None:
        """Verifica que authenticate_header retorna o nome do header."""
        settings.API_KEY_HEADER = "X-API-Key"

        req = self._drf_request()

        assert self.auth.authenticate_header(req) == "X-API-Key"

    def test_header_com_hifens_e_normalizado(self) -> None:
        """Verifica que um header com hífens é normalizado e autentica."""
        settings.API_KEY = "tok123"
        settings.API_KEY_HEADER = "X-Internal-Token"

        req = self._drf_request(
            {
                "HTTP_X_INTERNAL_TOKEN": "tok123",
            },
        )

        resultado = self.auth.authenticate(req)

        assert resultado is not None

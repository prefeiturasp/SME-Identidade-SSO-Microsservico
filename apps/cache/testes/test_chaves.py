"""Testes unitários das funções de geração de chaves de cache."""

from django.test import SimpleTestCase

from apps.cache import chaves


class TestChaves(SimpleTestCase):
    """Testes das funções de geração de chaves de cache."""

    def test_deve_gerar_chave_de_sessao(self) -> None:
        """Deve gerar a chave de cache de uma sessão."""
        resultado = chaves.sessao("11111111-1111-1111-1111-111111111111")

        self.assertEqual(
            resultado,
            "sessao:11111111-1111-1111-1111-111111111111",
        )

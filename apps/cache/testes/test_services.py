"""Testes unitários do serviço de cache."""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.cache.services import CacheService


class TestCacheService(SimpleTestCase):
    """Testes do serviço responsável pelas operações de cache."""

    @patch("apps.cache.services.cache.get")
    def test_deve_obter_valor_do_cache(
        self,
        mock_get: Mock,
    ) -> None:
        """Deve retornar um valor armazenado em cache.

        Args:
            mock_get: Mock da consulta ao cache.
        """
        mock_get.return_value = "valor"

        resultado = CacheService.obter("chave")

        self.assertEqual(resultado, "valor")

        mock_get.assert_called_once_with("chave")

    @patch("apps.cache.services.logger.exception")
    @patch("apps.cache.services.cache.get")
    def test_deve_retornar_none_quando_ocorrer_erro_ao_obter(
        self,
        mock_get: Mock,
        mock_logger: Mock,
    ) -> None:
        """Deve retornar ``None`` quando ocorrer erro ao consultar o cache.

        Args:
            mock_get: Mock da consulta ao cache.
            mock_logger: Mock do logger.
        """
        mock_get.side_effect = Exception()

        resultado = CacheService.obter("chave")

        self.assertIsNone(resultado)

        mock_get.assert_called_once_with("chave")

        mock_logger.assert_called_once_with(
            "Falha ao obter valor do cache.",
        )

    @patch("apps.cache.services.cache.set")
    def test_deve_salvar_valor_no_cache(
        self,
        mock_set: Mock,
    ) -> None:
        """Deve armazenar um valor em cache.

        Args:
            mock_set: Mock da operação de armazenamento.
        """
        CacheService.salvar(
            chave="chave",
            valor="valor",
        )

        mock_set.assert_called_once_with(
            "chave",
            "valor",
            timeout=None,
        )

    @patch("apps.cache.services.cache.set")
    def test_deve_salvar_valor_no_cache_com_timeout(
        self,
        mock_set: Mock,
    ) -> None:
        """Deve armazenar um valor em cache com timeout explícito.

        Args:
            mock_set: Mock da operação de armazenamento.
        """
        CacheService.salvar(
            chave="chave",
            valor="valor",
            timeout=60,
        )

        mock_set.assert_called_once_with(
            "chave",
            "valor",
            timeout=60,
        )

    @patch("apps.cache.services.logger.exception")
    @patch("apps.cache.services.cache.set")
    def test_nao_deve_lancar_excecao_quando_ocorrer_erro_ao_salvar(
        self,
        mock_set: Mock,
        mock_logger: Mock,
    ) -> None:
        """Deve registrar erro quando ocorrer falha ao salvar no cache.

        Args:
            mock_set: Mock da operação de armazenamento.
            mock_logger: Mock do logger.
        """
        mock_set.side_effect = Exception()

        CacheService.salvar(
            chave="chave",
            valor="valor",
        )

        mock_logger.assert_called_once_with(
            "Falha ao salvar valor no cache.",
        )

    @patch("apps.cache.services.cache.delete")
    def test_deve_invalidar_valor_do_cache(
        self,
        mock_delete: Mock,
    ) -> None:
        """Deve remover um valor armazenado em cache.

        Args:
            mock_delete: Mock da operação de remoção.
        """
        CacheService.invalidar("chave")

        mock_delete.assert_called_once_with("chave")

    @patch("apps.cache.services.logger.exception")
    @patch("apps.cache.services.cache.delete")
    def test_nao_deve_lancar_excecao_quando_ocorrer_erro_ao_invalidar(
        self,
        mock_delete: Mock,
        mock_logger: Mock,
    ) -> None:
        """Deve registrar erro quando ocorrer falha ao invalidar o cache.

        Args:
            mock_delete: Mock da operação de remoção.
            mock_logger: Mock do logger.
        """
        mock_delete.side_effect = Exception()

        CacheService.invalidar("chave")

        mock_delete.assert_called_once_with("chave")

        mock_logger.assert_called_once_with(
            "Falha ao invalidar valor do cache.",
        )

    @patch("apps.cache.services.cache.get")
    @patch("apps.cache.services.cache.set")
    def test_deve_retornar_true_quando_cache_disponivel(
        self,
        mock_set: Mock,
        mock_get: Mock,
    ) -> None:
        """Deve retornar ``True`` quando o cache responde ao round-trip.

        Args:
            mock_set: Mock da operação de armazenamento.
            mock_get: Mock da consulta ao cache.
        """
        mock_get.return_value = "1"

        resultado = CacheService.disponivel()

        self.assertTrue(resultado)

    @patch("apps.cache.services.logger.exception")
    @patch("apps.cache.services.cache.set")
    def test_deve_retornar_false_quando_cache_indisponivel(
        self,
        mock_set: Mock,
        mock_logger: Mock,
    ) -> None:
        """Deve retornar ``False`` quando o cache lança exceção.

        Args:
            mock_set: Mock da operação de armazenamento.
            mock_logger: Mock do logger.
        """
        mock_set.side_effect = Exception()

        resultado = CacheService.disponivel()

        self.assertFalse(resultado)

        mock_logger.assert_called_once_with(
            "Falha ao verificar disponibilidade do cache.",
        )

    @patch("apps.cache.services.cache.get")
    @patch("apps.cache.services.cache.set")
    def test_deve_retornar_false_quando_valor_nao_confere(
        self,
        mock_set: Mock,
        mock_get: Mock,
    ) -> None:
        """Deve retornar ``False`` quando o valor lido não confere.

        Args:
            mock_set: Mock da operação de armazenamento.
            mock_get: Mock da consulta ao cache.
        """
        mock_get.return_value = None

        resultado = CacheService.disponivel()

        self.assertFalse(resultado)

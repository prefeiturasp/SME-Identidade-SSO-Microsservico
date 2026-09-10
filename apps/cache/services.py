"""Serviços responsáveis pelas operações de cache."""

import logging
from typing import cast

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CHAVE_HEALTHCHECK = "__cache_healthcheck__"


class CacheService:
    """Serviço responsável pelas operações de cache.

    O KeyDB é a única fonte de verdade da sessão compartilhada — não
    há fallback a um banco relacional, diferente do uso de cache do
    SME-Identidade-Token-Microsservico. Por isso, além das operações
    usuais (fail-safe, nunca propagam exceção), este serviço também
    expõe :meth:`disponivel`, usado para distinguir "sessão não
    existe" de "cache indisponível" quando :meth:`obter` retorna
    ``None``.
    """

    @staticmethod
    def obter(chave: str) -> object | None:
        """Obtém um valor armazenado em cache.

        Caso o serviço de cache esteja indisponível, retorna ``None``,
        permitindo que a aplicação continue normalmente.

        Args:
            chave: Chave utilizada para localizar o valor em cache.

        Returns:
            Valor armazenado ou ``None`` caso não exista ou ocorra alguma
            falha durante a consulta.
        """
        try:
            return cast(object | None, cache.get(chave))

        except Exception:
            logger.exception("Falha ao obter valor do cache.")
            return None

    @staticmethod
    def salvar(
        chave: str,
        valor: object,
        timeout: int | None = None,
    ) -> None:
        """Armazena um valor em cache.

        Caso o cache esteja indisponível, registra a ocorrência em log sem
        interromper o fluxo da aplicação.

        Args:
            chave: Chave utilizada para armazenamento.
            valor: Valor que será armazenado.
            timeout: Tempo de expiração em segundos. Quando omitido,
                usa o padrão configurado em ``CACHES``.
        Returns:
            None
        """
        try:
            cache.set(
                chave,
                valor,
                timeout=timeout,
            )

        except Exception:
            logger.exception("Falha ao salvar valor no cache.")

    @staticmethod
    def invalidar(chave: str) -> None:
        """Remove um valor armazenado em cache.

        Caso o cache esteja indisponível, registra a ocorrência em log sem
        interromper o fluxo da aplicação.

        Args:
            chave: Chave do registro que será removido.
        """
        try:
            cache.delete(chave)

        except Exception:
            logger.exception("Falha ao invalidar valor do cache.")

    @staticmethod
    def disponivel() -> bool:
        """Verifica se o cache está respondendo.

        Faz um round-trip trivial de escrita e leitura. Usado quando
        :meth:`obter` retorna ``None`` e é preciso saber se isso
        significa "chave não existe" ou "cache fora do ar" — distinção
        que importa porque aqui o cache é a única fonte de verdade da
        sessão, sem fallback a um banco relacional.

        Returns:
            ``True`` se o cache respondeu com sucesso, ``False`` caso
            contrário.
        """
        try:
            cache.set(_CHAVE_HEALTHCHECK, "1", timeout=5)
            return bool(cache.get(_CHAVE_HEALTHCHECK) == "1")

        except Exception:
            logger.exception("Falha ao verificar disponibilidade do cache.")
            return False

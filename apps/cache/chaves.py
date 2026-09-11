"""Funções para geração das chaves utilizadas no cache."""

from uuid import UUID


def sessao(sessao_id: UUID | str) -> str:
    """Retorna a chave de cache de uma sessão compartilhada.

    Args:
        sessao_id: Identificador único da sessão.

    Returns:
        Chave utilizada para armazenar a sessão em cache.
    """
    return f"sessao:{sessao_id}"

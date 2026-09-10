"""Modelo de domínio da sessão compartilhada.

A sessão não é persistida em banco relacional — vive inteiramente no
KeyDB, com TTL natural (ver ``apps.sessoes.services.SessaoService``).
Este módulo define apenas a estrutura de dados e sua serialização
para/de JSON, sem lógica de negócio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Sessao:
    """Sessão compartilhada de um usuário entre sistemas integrados.

    Attributes:
        sessao_id: Identificador único da sessão.
        login: Login do usuário autenticado.
        kc_user_id: Identificador do usuário no Keycloak.
        sistemas: Sistemas aos quais o usuário tinha acesso no
            momento da criação da sessão (``sistema_id``,
            ``sistema_nome``).
        criado_em: Data/hora de criação da sessão.
        ultima_atividade: Data/hora da última renovação da sessão.
        expira_em: Teto absoluto de duração máxima da sessão — não se
            move após a criação.
    """

    sessao_id: UUID
    login: str
    kc_user_id: str
    criado_em: datetime
    ultima_atividade: datetime
    expira_em: datetime
    sistemas: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializa a sessão para um dicionário JSON-compatível.

        Returns:
            Dicionário com ``sessao_id`` e datas em formato ISO-8601,
            pronto para armazenamento no cache.
        """
        dados = asdict(self)
        dados["sessao_id"] = str(self.sessao_id)
        dados["criado_em"] = self.criado_em.isoformat()
        dados["ultima_atividade"] = self.ultima_atividade.isoformat()
        dados["expira_em"] = self.expira_em.isoformat()
        return dados

    @classmethod
    def from_dict(cls, dados: dict) -> Sessao:
        """Reconstrói uma sessão a partir de um dicionário serializado.

        Args:
            dados: Dicionário no formato retornado por
                :meth:`to_dict`.

        Returns:
            Instância de :class:`Sessao` com os tipos originais
            restaurados.
        """
        return cls(
            sessao_id=UUID(dados["sessao_id"]),
            login=dados["login"],
            kc_user_id=dados["kc_user_id"],
            sistemas=dados["sistemas"],
            criado_em=datetime.fromisoformat(dados["criado_em"]),
            ultima_atividade=datetime.fromisoformat(
                dados["ultima_atividade"]
            ),
            expira_em=datetime.fromisoformat(dados["expira_em"]),
        )

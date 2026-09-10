"""Testes do modelo de domínio da sessão compartilhada."""

from datetime import UTC, datetime
from uuid import UUID

from django.test import SimpleTestCase

from apps.sessoes.dominio import Sessao


class TestSessao(SimpleTestCase):
    """Testes de serialização de :class:`Sessao`."""

    def setUp(self) -> None:
        """Cria uma sessão de referência para os testes."""
        self.sessao = Sessao(
            sessao_id=UUID("11111111-1111-1111-1111-111111111111"),
            login="1234567",
            kc_user_id="5c29cc47-0000-0000-0000-000000000000",
            sistemas=[{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
            criado_em=datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC),
            ultima_atividade=datetime(
                2026, 9, 8, 10, 0, 0, tzinfo=UTC
            ),
            expira_em=datetime(2026, 9, 8, 18, 0, 0, tzinfo=UTC),
        )

    def test_to_dict_serializa_todos_os_campos(self) -> None:
        """Deve serializar sessao_id e datas como string ISO-8601."""
        dados = self.sessao.to_dict()

        self.assertEqual(
            dados["sessao_id"],
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(dados["login"], "1234567")
        self.assertEqual(
            dados["sistemas"],
            [{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
        )
        self.assertIsInstance(dados["criado_em"], str)
        self.assertIsInstance(dados["ultima_atividade"], str)
        self.assertIsInstance(dados["expira_em"], str)

    def test_from_dict_restaura_tipos_originais(self) -> None:
        """Deve restaurar UUID e datetime a partir do dicionário."""
        dados = self.sessao.to_dict()

        restaurada = Sessao.from_dict(dados)

        self.assertEqual(restaurada.sessao_id, self.sessao.sessao_id)
        self.assertEqual(restaurada.login, self.sessao.login)
        self.assertEqual(restaurada.kc_user_id, self.sessao.kc_user_id)
        self.assertEqual(restaurada.sistemas, self.sessao.sistemas)
        self.assertEqual(restaurada.criado_em, self.sessao.criado_em)
        self.assertEqual(
            restaurada.ultima_atividade,
            self.sessao.ultima_atividade,
        )
        self.assertEqual(restaurada.expira_em, self.sessao.expira_em)

    def test_round_trip_preserva_valores(self) -> None:
        """to_dict seguido de from_dict deve reproduzir a sessão original."""
        restaurada = Sessao.from_dict(self.sessao.to_dict())

        self.assertEqual(restaurada, self.sessao)

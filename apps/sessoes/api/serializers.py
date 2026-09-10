"""Serializers da API de sessão compartilhada."""

from rest_framework import serializers


class CriarSessaoRequestSerializer(serializers.Serializer):
    """Dados necessários para criar uma sessão compartilhada."""

    login = serializers.CharField(
        help_text="Login do usuário autenticado.",
    )
    kc_user_id = serializers.CharField(
        help_text="Identificador do usuário no Keycloak.",
    )


class SistemaSerializer(serializers.Serializer):
    """Sistema associado a uma sessão."""

    sistema_id = serializers.IntegerField()
    sistema_nome = serializers.CharField()


class SessaoResponseSerializer(serializers.Serializer):
    """Representação de uma sessão recém-criada ou renovada."""

    sessao_id = serializers.UUIDField()
    login = serializers.CharField()
    sistemas = SistemaSerializer(many=True)
    criado_em = serializers.DateTimeField(required=False)
    ultima_atividade = serializers.DateTimeField(required=False)
    expira_em = serializers.DateTimeField()


class ValidarSessaoResponseSerializer(serializers.Serializer):
    """Resultado da consulta/validação de uma sessão.

    ``situacao`` assume um de: ``valida``,
    ``expirada_por_inatividade``, ``expirada_por_duracao_maxima``.
    Demais campos são omitidos quando a sessão está expirada — o
    chamador só precisa saber que não pode mais usá-la.
    """

    sessao_id = serializers.UUIDField()
    situacao = serializers.ChoiceField(
        choices=[
            "valida",
            "expirada_por_inatividade",
            "expirada_por_duracao_maxima",
        ],
    )
    login = serializers.CharField(required=False)
    sistemas = SistemaSerializer(many=True, required=False)
    ultima_atividade = serializers.DateTimeField(required=False)
    expira_em = serializers.DateTimeField(required=False)


class NotificacaoLogoutSerializer(serializers.Serializer):
    """Resultado da notificação de logout a um sistema."""

    sistema_id = serializers.IntegerField()
    sistema_nome = serializers.CharField()
    sucesso = serializers.BooleanField()
    detalhe = serializers.CharField(allow_null=True)


class LogoutResponseSerializer(serializers.Serializer):
    """Confirmação do encerramento de sessão e logout global."""

    sessao_id = serializers.UUIDField()
    situacao = serializers.CharField(default="sessao_encerrada")
    notificacoes = NotificacaoLogoutSerializer(many=True)

"""Serializers da API de login orquestrado."""

from rest_framework import serializers

from apps.sessoes.api.serializers import SessaoResponseSerializer


class LoginRequestSerializer(serializers.Serializer):
    """Credenciais recebidas para autenticação de um usuário."""

    login = serializers.CharField(
        help_text="RF, CPF ou username do usuário.",
    )
    senha = serializers.CharField(
        write_only=True,
        help_text="Senha em texto plano (transporte HTTPS).",
    )


class LoginResponseSerializer(serializers.Serializer):
    """Resultado do login com a sessão compartilhada já criada."""

    kc_user_id = serializers.CharField()
    username = serializers.CharField()
    nome = serializers.CharField()
    email = serializers.CharField(allow_null=True, required=False)
    ativo = serializers.BooleanField()
    cpf = serializers.CharField(allow_null=True, required=False)
    rf = serializers.CharField(allow_null=True, required=False)
    roles = serializers.DictField(
        help_text=(
            "realm_access/resource_access repassados pelo Gateway,"
            " formato bruto do Keycloak."
        ),
    )
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    expires_in = serializers.IntegerField(allow_null=True, required=False)
    token_enriquecido = serializers.CharField()
    data_expiracao_token_enriquecido = serializers.DateTimeField()
    sessao = SessaoResponseSerializer(
        allow_null=True,
        help_text=(
            "Sessão compartilhada recém-criada. ``sessao_id`` é o"
            " token de sessão usado pelos sistemas conectados."
        ),
    )
    sessao_erro = serializers.CharField(
        required=False,
        allow_null=True,
        help_text=(
            "Preenchido quando a autenticação teve sucesso mas a"
            " sessão não pôde ser criada — os tokens acima continuam"
            " válidos."
        ),
    )

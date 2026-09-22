# SME Identidade SSO Microsserviço

Documentação técnica do serviço responsável pela sessão compartilhada e pelo logout global entre os sistemas integrados à plataforma Identidade, proporcionando uma experiência de Single Sign-On (SSO) unificada.

O microsserviço atua como *session broker*: cria e mantém a sessão compartilhada de um usuário autenticado (via login orquestrado ou em conjunto com o SME-Identidade-Gateway-Microsservico), e propaga o logout para os demais sistemas conectados quando o usuário sai de qualquer um deles. Não autentica usuários nem detém a projeção de permissões — consome o Gateway e, por meio dele, o SME-Identidade-Token-Microsservico. Ver [Visão geral](arquitetura/visao_geral.md) para o papel completo na plataforma.

```{toctree}
:maxdepth: 2
:caption: Conteúdo

sessoes
arquitetura/visao_geral
arquitetura/fluxo_logout_global
api
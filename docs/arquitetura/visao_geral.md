# Visão geral

O SME-Identidade-SSO-Microsservico atua como *session broker* da
plataforma Identidade: mantém a sessão compartilhada de um usuário
autenticado e coordena o logout entre os sistemas conectados. Não
autentica usuários (isso é responsabilidade do Keycloak, via
SME-Identidade-Gateway-Microsservico) nem detém a projeção de
permissões (SME-Identidade-Token-Microsservico) — consome ambos.

## Papel na plataforma

```text
Usuário
   │
   ▼
SME-Identidade-Gateway-Microsservico  ──(login real, grant password)──▶  Keycloak
   │                                   ──(sistemas do usuário)────────▶  SME-Identidade-Token-Microsservico
   │
   ▼ (pós-login, cria a sessão)
SME-Identidade-SSO-Microsservico
   │
   ├─ consulta sistemas do usuário ──▶  Gateway (que consulta o Token-MS)
   ├─ grava a sessão ────────────────▶  KeyDB
   └─ propaga logout global ─────────▶  callback de cada sistema conectado
```

O SSO-MS **consulta** o Gateway para saber os sistemas do usuário no
momento de criar a sessão — o Gateway não empurra a sessão para o
SSO-MS. Essa direção de dependência mantém o Gateway como o único ponto
de entrada de autenticação da plataforma, com o SSO-MS como uma
capacidade adicional que ele aciona quando necessário.

## Fluxo completo

1. Usuário autentica no Gateway (grant `password` contra o Keycloak).
2. Gateway (ou outro chamador autorizado) cria a sessão compartilhada:
   `POST /identidade-sso/api/v1/sessoes/`.
3. SSO-MS consulta o Gateway para obter os sistemas do usuário e grava
   a sessão no KeyDB.
4. Sistemas conectados consultam/renovam a sessão conforme o usuário
   interage (`GET`/`POST .../renovar/`).
5. Sessão expira automaticamente por inatividade ou por duração
   máxima — ver [Sessão compartilhada](../sessoes.md).
6. Logout em qualquer sistema aciona
   `POST .../logout/`, que encerra a sessão e propaga a notificação
   para os demais sistemas conectados — ver
   [Fluxo de logout global](fluxo_logout_global.md).

## Armazenamento

A sessão vive só em KeyDB — não há Postgres neste serviço. É dado
efêmero com TTL natural, coerente com o papel de *broker*: o SSO-MS não
é a fonte de verdade de identidade ou permissões (isso é Keycloak e
Token-MS), só coordena a sessão enquanto ela dura.

# Fluxo de logout global

Logout em um sistema deve encerrar a sessão nos demais sistemas
conectados na mesma sessão do SSO-MS — evitando sessão órfã ativa em
outro sistema depois que o usuário já saiu.

## Sequência

```text
Sistema A                SSO-MS                    KeyDB          Sistema B / C / ...
   │                        │                         │                  │
   │ POST .../logout/       │                         │                  │
   ├───────────────────────▶│                         │                  │
   │                        │ obtém a sessão          │                  │
   │                        ├────────────────────────▶│                  │
   │                        │◀────────────────────────┤                  │
   │                        │ invalida a chave         │                  │
   │                        ├────────────────────────▶│                  │
   │                        │                         │                  │
   │                        │ dispara notificações em paralelo            │
   │                        │ (ThreadPoolExecutor, 1 POST por sistema)    │
   │                        ├─────────────────────────────────────────────▶
   │                        │◀─────────────────────────────────────────────
   │                        │ agrega resultados        │                  │
   │◀───────────────────────┤ (sempre 200)             │                  │
```

## Decisões

- **Encerrar é garantido, notificar é melhor esforço.** A sessão é
  removida do KeyDB **antes** de qualquer tentativa de notificação. Se
  todas as notificações falharem, a resposta ainda é 200 — o usuário
  não pode ficar com uma sessão "presa" por causa de um sistema fora do
  ar.
- **Notificações em paralelo**, via `concurrent.futures.ThreadPoolExecutor`
  (biblioteca padrão, sem dependência nova). Sequencial seria O(n) na
  latência total e um sistema lento atrasaria a resposta do logout para
  o usuário.
- **Timeout curto por chamada** (`SSO_LOGOUT_CALLBACK_TIMEOUT`, default
  5s) — cada falha (timeout, erro de transporte, status não-2xx) é
  isolada por sistema e nunca propaga exceção para o chamador do
  endpoint de logout.
- **Sistemas legados sem suporte a notificação** (sem endpoint de
  recepção próprio) são tratados como "sem callback registrado" — a
  configuração de URLs (`SSO_LOGOUT_CALLBACKS`) é quem decide quais
  sistemas recebem notificação; sistemas ausentes dessa configuração
  não geram erro, apenas ficam de fora da propagação. A referência para
  saber quais sistemas suportam esse tipo de notificação é a
  classificação de complexidade já levantada no contrato de integração
  da plataforma — não um levantamento novo feito por este serviço.

## Endpoint de recepção de exemplo

O SME-Identidade-Gateway-Microsservico expõe
`POST /identidade-gateway/api/v1/autenticacao/logout-notificacao/` como
sistema de teste E2E do mecanismo — recebe `sessao_id`, `login` e
`kc_user_id`, loga o recebimento e confirma. O Gateway não mantém sessão
própria, então não há nada real a invalidar ali; serve apenas para
validar que a propagação chega a um sistema conectado.

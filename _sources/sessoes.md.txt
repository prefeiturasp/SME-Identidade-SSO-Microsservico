# Sessão compartilhada

Esta página descreve o contrato dos endpoints de sessão compartilhada, a
estrutura de armazenamento no KeyDB e o mecanismo de logout global.
Detalhes de schema (tipos exatos, exemplos gerados) estão disponíveis no
Swagger em `/identidade-sso/api/v1/docs/`.

## Armazenamento

A sessão vive inteiramente no KeyDB — não há persistência em banco
relacional. Cada sessão é identificada por um `sessao_id` (UUID gerado
na criação), permitindo múltiplas sessões simultâneas para o mesmo
usuário (múltiplos dispositivos/abas).

Chave: `sessao:{sessao_id}`. Valor armazenado:

```json
{
  "sessao_id": "uuid",
  "login": "1234567",
  "kc_user_id": "uuid-keycloak",
  "sistemas": [{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
  "criado_em": "iso-datetime",
  "ultima_atividade": "iso-datetime",
  "expira_em": "iso-datetime"
}
```

`expira_em` é o teto absoluto de duração máxima da sessão, fixado na
criação — não se move. `ultima_atividade` se move a cada renovação e é
comparado contra o tempo de inatividade configurado em cada validação.

O TTL de cada escrita no KeyDB é sempre `min(tempo de inatividade,
segundos restantes até expira_em)` — garante que o KeyDB expurga a
chave sozinho mesmo que a lógica de validação nunca seja chamada de
novo, sem depender de uma tarefa de limpeza externa.

## Sistemas da sessão

No momento da criação, o SSO-MS consulta o
SME-Identidade-Gateway-Microsservico (`GET
{GATEWAY_MS_URL}/api/v1/autenticacao/usuarios/{login}/sistemas/`) para
obter os sistemas aos quais o usuário tem acesso. Se o Gateway não
responder a tempo ou estiver inacessível, a criação da sessão falha
(502) — sem saber os sistemas, a sessão não tem utilidade.

## Endpoints

### Login orquestrado

`POST /identidade-sso/api/v1/login/`

Autentica o usuário no SME-Identidade-Gateway-Microsservico
(`POST /api/v1/autenticacao/login/`) e, em caso de sucesso, já cria a
sessão compartilhada — equivale a chamar o login do Gateway seguido de
"Criar sessão" (abaixo) numa única requisição. O `sessao_id` retornado
é o token de sessão usado pelos sistemas conectados; não é emitido
nenhum JWT adicional para representar a sessão.

Request:

```json
{"login": "1234567", "senha": "minhaSenha123"}
```

Resposta 201 — inclui todos os campos retornados pelo login do Gateway
(`access_token`, `refresh_token`, `token_enriquecido`, dados
cadastrais, `roles`) mais o campo `sessao` com o mesmo formato da
resposta de "Criar sessão":

```json
{
  "kc_user_id": "5c29cc47-0000-0000-0000-000000000000",
  "username": "1234567",
  "...": "demais campos do login do Gateway",
  "sessao": {
    "sessao_id": "b2b2b2b2-0000-0000-0000-000000000000",
    "login": "1234567",
    "sistemas": [{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
    "criado_em": "2026-09-09T12:00:00Z",
    "ultima_atividade": "2026-09-09T12:00:00Z",
    "expira_em": "2026-09-09T20:00:00Z"
  },
  "sessao_erro": null
}
```

Resposta 201 com `sessao: null` e `sessao_erro` preenchido — a
autenticação no Keycloak já aconteceu de verdade e não é desfeita por
uma falha secundária ao criar a sessão (mesmo princípio "not-blocking"
que o Gateway já usa para o token enriquecido no login); os tokens
retornados continuam válidos, só falta a sessão compartilhada.

Resposta 401 — login ou senha inválidos. Usuário inexistente no
Keycloak recebe o mesmo tratamento (401), para não permitir que um
consumidor descubra quais logins existem testando senhas em branco.

Resposta 502 — Gateway indisponível na autenticação (primeira
chamada).

### Criar sessão

`POST /identidade-sso/api/v1/sessoes/`

Usado quando a autenticação já ocorreu separadamente (o chamador já
tem `kc_user_id`) — para o fluxo de login + sessão numa única chamada,
ver "Login orquestrado" acima.

Request:

```json
{"login": "1234567", "kc_user_id": "5c29cc47-0000-0000-0000-000000000000"}
```

Resposta 201:

```json
{
  "sessao_id": "b2b2b2b2-0000-0000-0000-000000000000",
  "login": "1234567",
  "sistemas": [{"sistema_id": 1, "sistema_nome": "CoreSSO"}],
  "criado_em": "2026-09-08T10:00:00-03:00",
  "expira_em": "2026-09-08T18:00:00-03:00"
}
```

Resposta 502 — Gateway inacessível ou não respondeu a tempo.

### Consultar/validar sessão

`GET /identidade-sso/api/v1/sessoes/{sessao_id}/`

Operação de leitura pura — **não** renova a atividade da sessão. Renovar
é uma ação explícita (ver abaixo), para que uma consulta não prolongue
artificialmente uma sessão que deveria expirar por inatividade.

Resposta 200, `situacao` pode ser `valida`, `expirada_por_inatividade`
ou `expirada_por_duracao_maxima` — o estado é retornado ao chamador, não
é um erro de protocolo.

Resposta 404 — a sessão nunca existiu ou já foi expurgada do KeyDB
(miss confirmado). Resposta 503 — o KeyDB está indisponível, não é
possível confirmar se a sessão existe (miss não-confirmado). A
distinção entre 404 e 503 importa porque, diferente do cache do
SME-Identidade-Token-Microsservico, aqui não há fallback a um banco —
o KeyDB é a única fonte de verdade da sessão.

### Renovar sessão

`POST /identidade-sso/api/v1/sessoes/{sessao_id}/renovar/`

Atualiza `ultima_atividade` para o instante atual e recalcula o TTL da
chave no KeyDB.

Resposta 200 com a sessão atualizada. Resposta 409 — a sessão já está
expirada, não é possível renovar. Resposta 404 — sessão não encontrada.

### Encerrar sessão (logout global)

`POST /identidade-sso/api/v1/sessoes/{sessao_id}/logout/`

Encerra a sessão no KeyDB e, em seguida, notifica em paralelo cada
sistema presente em `sistemas` sobre o logout global — ver
[Fluxo de logout global](arquitetura/fluxo_logout_global.md).

A sessão é **sempre** encerrada antes de qualquer tentativa de
notificação: encerrar é garantido, notificar é melhor esforço. A
resposta é sempre 200, mesmo que todas as notificações falhem.

Resposta 200:

```json
{
  "sessao_id": "b2b2b2b2-0000-0000-0000-000000000000",
  "situacao": "sessao_encerrada",
  "notificacoes": [
    {"sistema_id": 1, "sistema_nome": "CoreSSO", "sucesso": true, "detalhe": null},
    {"sistema_id": 176, "sistema_nome": "Boletim Online", "sucesso": false, "detalhe": "timeout"}
  ]
}
```

Resposta 404 — a sessão já não existia (mais honesto que responder 200
idempotente vazio; evita mascarar um `sessao_id` inválido enviado por
engano).

## Configuração de callbacks de logout

Não existe ainda um cadastro de sistemas com metadados de URL de
callback — apenas `sistema_id`/`sistema_nome` chegam via CoreSSO
(através do Token-MS e do Gateway). A solução adotada nesta fase é uma
variável de ambiente estática:

```
SSO_LOGOUT_CALLBACKS=1:http://gateway-ms:8000/identidade-gateway/api/v1/autenticacao/logout-notificacao/,176:http://outro-sistema/logout/
```

Formato: `sistema_id:url,sistema_id:url`. Um sistema presente na sessão
mas sem callback configurado é reportado como falha
(`"sem callback registrado"`), sem tentativa de rede — não é um erro de
execução.

Isso é uma **dívida técnica intencional**: a evolução natural é um
cadastro de sistemas versionado com URL de callback por sistema, fora
do escopo desta fase.

Cada notificação é enviada com a mesma API Key usada para consultar o
Gateway (`API_KEY_GATEWAY_MS`/`API_KEY_GATEWAY_MS_HEADER`) — reaproveita
a credencial já configurada em vez de introduzir uma chave dedicada por
sistema de callback, já que hoje o único receptor real é o endpoint de
teste E2E do próprio Gateway.

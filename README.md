# SME-Identidade-SSO-Microsservico

O SME-Identidade-SSO-Microsservico atua como *session broker* da plataforma SME-SP: cria e mantém a sessão compartilhada de um usuário autenticado e propaga o logout entre os sistemas integrados, proporcionando uma experiência unificada de Single Sign-On (SSO).

O serviço não autentica usuários nem detém a projeção de permissões — consome o SME-Identidade-Gateway-Microsservico (autenticação real contra o Keycloak) e, por meio dele, o SME-Identidade-Token-Microsservico (sistemas aos quais o usuário tem acesso). Ver `docs/arquitetura/visao_geral.md` para o papel completo na plataforma.

## Estrutura do repositório

```
.
├── apps/
│   ├── core/            # health check
│   ├── autenticacao/    # autenticação por API Key dos endpoints do SSO-MS
│   ├── cache/           # encapsula operações no KeyDB
│   ├── gateway_ms/      # cliente HTTP do SME-Identidade-Gateway-Microsservico
│   ├── sessoes/         # sessão compartilhada e logout global
│   └── login/           # login orquestrado (Gateway + sessão compartilhada)
├── config/              # settings, urls, wsgi
├── requirements/
│   ├── base.txt         # dependências de produção
│   └── local.txt        # base + ferramentas de desenvolvimento
└── manage.py
```

### apps/core

| Módulo | Responsabilidade |
|---|---|
| `api/views.py` | Endpoints da aplicação, incluindo o health check do serviço |
| `api/serializers.py` | Serialização e validação de dados de entrada e saída |
| `api/urls.py` | Registro e roteamento das URLs da aplicação |

### apps/autenticacao

| Módulo | Responsabilidade |
|---|---|
| `api/autenticacao.py` | `AutenticacaoApiKey`, autenticação por API Key dos endpoints do SSO-MS |
| `schema.py` | Integração da `AutenticacaoApiKey` com o schema OpenAPI (Swagger) |

### apps/cache

| Módulo | Responsabilidade |
|---|---|
| `chaves.py` | Funções puras de geração de chaves de cache |
| `services.py` | `CacheService`, encapsula operações no KeyDB (fail-safe) |

### apps/gateway_ms

| Módulo | Responsabilidade |
|---|---|
| `cliente.py` | Cliente HTTP configurado para o SME-Identidade-Gateway-Microsservico |

### apps/sessoes

| Módulo | Responsabilidade |
|---|---|
| `dominio.py` | Modelo de domínio `Sessao` (dataclass, serializada para o KeyDB) |
| `services.py` | `SessaoService` — criar, consultar, validar, renovar e encerrar sessões |
| `logout_global.py` | Propagação de logout aos sistemas conectados à sessão |
| `api/` | Endpoints REST de sessão compartilhada |

### apps/login

| Módulo | Responsabilidade |
|---|---|
| `services.py` | `LoginService` — autentica no Gateway e cria a sessão numa única chamada |
| `api/` | Endpoint `POST /login/`, orquestração de login + sessão compartilhada |

A sessão compartilhada vive inteiramente no KeyDB (sem persistência em
banco relacional) — ver `docs/sessoes.md` para o contrato completo dos
endpoints e `docs/arquitetura/` para o fluxo de logout global.

## Requisitos

- Python 3.12+
- Docker e Docker Compose

## Configuração do ambiente

```bash
cp .env.example .env
make build
make run
```

**Geral**

| Variável | Padrão | Descrição |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Chave secreta do Django |
| `DJANGO_DEBUG` | `1` | Ativa o modo debug (`0` em produção) |
| `DJANGO_ALLOWED_HOSTS` | `*` | Hosts permitidos, separados por vírgula |
| `NIVEL_LOG` | `INFO` | Nível do logging estruturado (JSON) |
| `API_KEY` | — | Chave exigida dos clientes do SSO-MS |
| `API_KEY_HEADER` | `X-API-Key` | Header usado para enviar a API Key |

**KeyDB (sessão compartilhada)**

| Variável | Padrão | Descrição |
|---|---|---|
| `URL_KEYDB` | `redis://keydb:6379/0` | URL de conexão com o KeyDB |
| `KEYDB_DEFAULT_TIMEOUT` | `300` | TTL padrão do cache, em segundos |

**Integração com o Gateway**

| Variável | Padrão | Descrição |
|---|---|---|
| `GATEWAY_MS_URL` | `http://gateway-ms:8000` | URL base do SME-Identidade-Gateway-Microsservico |
| `GATEWAY_MS_TIMEOUT` | `10` | Timeout das chamadas ao Gateway, em segundos |
| `API_KEY_GATEWAY_MS` | — | Chave enviada ao Gateway |
| `API_KEY_GATEWAY_MS_HEADER` | `X-API-Key` | Header usado para enviar a chave ao Gateway |

**Sessão compartilhada**

| Variável | Padrão | Descrição |
|---|---|---|
| `SESSAO_TEMPO_INATIVIDADE_SEGUNDOS` | `1800` | Tempo de inatividade até a sessão expirar |
| `SESSAO_DURACAO_MAXIMA_SEGUNDOS` | `28800` | Duração máxima da sessão, mesmo com atividade contínua |
| `SSO_LOGOUT_CALLBACKS` | — | Callbacks de logout por sistema, formato `sistema_id:url,sistema_id:url` |
| `SSO_LOGOUT_CALLBACK_TIMEOUT` | `5` | Timeout de cada chamada de notificação de logout |

## Atalhos Make

Use `make help` para listar todos os comandos disponíveis. Os principais:

**Ambiente**

| Comando | Descrição |
|---|---|
| `make run` | Sobe o containers em modo dev (porta 8002) |
| `make build` | Rebuild da imagem dev |
| `make stop` | Para e remove containers |

**Testes**

| Comando | Descrição |
|---|---|
| `make test` | Suite completa com cobertura ≥ 80% |
| `make test-core` | Apenas `apps.core` |
| `make test-cache` | Apenas `apps.cache` |
| `make test-autenticacao` | Apenas `apps.autenticacao` |
| `make test-gateway-ms` | Apenas `apps.gateway_ms` |
| `make test-sessoes` | Apenas `apps.sessoes` |
| `make test-login` | Apenas `apps.login` |

**Qualidade**

| Comando | Descrição |
|---|---|
| `make lint` | ruff + black + isort + mypy |
| `make coverage` | Relatório HTML em `docs/_cov/` |
| `make schema` | Gera schema OpenAPI em `schema.yml` |
| `make docs` | Gera documentação Sphinx em `docs/_build/html/` |

## Endpoints

Consulte o Swagger em `/identidade-sso/api/v1/docs/` para a lista completa de rotas com parâmetros e exemplos de resposta.
# SME-Identidade-SSO-Microsservico

O SME-Identidade-SSO-Microsservico é responsável por centralizar o processo de autenticação da plataforma SME-SP, proporcionando uma experiência unificada de Single Sign-On (SSO) entre os sistemas integrados.

Por meio de uma Universal Login Page customizada e da atuação como session broker, o serviço gerencia e compartilha sessões entre aplicações, permitindo que os usuários autenticados acessem diferentes sistemas sem a necessidade de realizar múltiplos logins.

## Estrutura do repositório

```
.
├── apps/
│   ├── core/           # cliente HTTP
├── config/             # settings, urls, wsgi
├── requirements/
│   ├── base.txt        # dependências de produção
│   └── local.txt       # base + ferramentas de desenvolvimento
└── manage.py
```

### apps/core

| Módulo | Responsabilidade |
|---|---|
| `api/views.py` | Endpoints da aplicação, incluindo o health check do serviço |
| `api/serializers.py` | Serialização e validação de dados de entrada e saída |
| `api/urls.py` | Registro e roteamento das URLs da aplicação |

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

**Qualidade**

| Comando | Descrição |
|---|---|
| `make lint` | ruff + black + isort + mypy |
| `make coverage` | Relatório HTML em `docs/_cov/` |
| `make schema` | Gera schema OpenAPI em `schema.yml` |
| `make docs` | Gera documentação Sphinx em `docs/_build/html/` |

## Endpoints

Consulte o Swagger em `/identidade-sso/api/v1/docs/` para a lista completa de rotas com parâmetros e exemplos de resposta.
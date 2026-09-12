# fastapi-monolith-gallery

Sistema de galeria de fotos desenvolvido durante o workshop do Techleads club.

Galeria minimalista de pastas públicas e privadas com fotos, comentários, curtidas, moderação e perfis públicos. Ver escopo completo em [`ROADMAP.md`](ROADMAP.md).

## Pré-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup rápido

```bash
make install
make db-upgrade
make db-seed
make run
```

Aplicação em http://127.0.0.1:8000

## Comandos

| Comando | Descrição |
|---------|-----------|
| `make install` | Instala dependências (`uv sync --group dev`) |
| `make run` | Sobe o servidor com reload |
| `make test` | Roda pytest |
| `make db-upgrade` | Aplica migrations do Alembic |
| `make db-migrate msg="..."` | Gera nova migration |
| `make db-seed` | Cria o usuário admin inicial (idempotente) |

## Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `DATABASE_URL` | `sqlite:///./data/app.db` | URL do banco SQLite |
| `ADMIN_USERNAME` | `admin` | Username do admin criado pelo seed |
| `ADMIN_EMAIL` | `admin@localhost` | E-mail do admin criado pelo seed |
| `ADMIN_PASSWORD` | `admin` | Senha do admin criado pelo seed |

## Documentação para o time e agentes de IA

- [`ROADMAP.md`](ROADMAP.md) — progresso e tarefas do MVP
- [`AGENTS.md`](AGENTS.md) — convenções de arquitetura e código

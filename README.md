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
| `SESSION_SECRET` | `dev-insecure-change-me` | Assina o cookie de sessão |
| `UPLOAD_DIR` | `<raiz>/uploads` | Diretório local de armazenamento de fotos |
| `MAX_UPLOAD_SIZE` | `10485760` (10 MB) | Tamanho máximo de upload de imagem em bytes |

## Limitações conhecidas do MVP

### Acesso público a `/uploads`

No MVP, fotos são servidas em `/uploads/{filename}` via `StaticFiles`, **sem autenticação nem checagem de visibilidade da pasta**. A página de uma pasta privada retorna 404 para não autorizados, mas quem souber (ou adivinhar) o nome do arquivo ainda pode baixar a imagem diretamente.

**Antes de produção**, é obrigatório adicionar uma camada de segurança, por exemplo:

- rota de download que valida `can_view_folder` antes de servir o arquivo; ou
- storage externo (S3/R2) com URLs assinadas e expiração curta.

A Fase 2 do roadmap evoluirá as regras de acesso à pasta; a proteção dos arquivos em disco deve ser tratada explicitamente no deploy.

## Documentação para o time e agentes de IA

- [`ROADMAP.md`](ROADMAP.md) — progresso e tarefas do MVP
- [`AGENTS.md`](AGENTS.md) — convenções de arquitetura e código

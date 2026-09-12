# Roadmap — Galeria de Imagens (MVP)

Monolito FastAPI + Jinja2, alinhado à estrutura atual (`routes` → `schemas` → `services` → `templates`).

---

## Progresso atual

| Campo | Valor |
|-------|-------|
| **Fase atual** | F0 — Fundação |
| **Última tarefa concluída** | 0.2 |
| **Próxima tarefa** | **0.3** — Auth com sessão (cookie): registro, login, logout |
| **MVP completo?** | Não |

> Ao concluir uma tarefa: marque `[x]` na tabela da fase e atualize esta seção.

---

## Resultado final do MVP

Uma plataforma onde:

1. Usuários se cadastram, fazem login e gerenciam **pastas (folders)** com várias fotos.
2. Pastas são **públicas** (qualquer visitante vê) ou **privadas** (só dono + convidados).
3. Usuários logados **comentam** pastas (em privadas, só convidados).
4. Usuários logados **curtem** pastas.
5. Pastas com **conteúdo adulto** exigem confirmação em modal antes de abrir.
6. Qualquer usuário pode **denunciar** pasta/comentário; **moderadores** revisam; **admins** têm controles extras.
7. Todo usuário tem **perfil público** com username (sem nível/gamificação ainda).

**Fora do MVP:** sistema de níveis, ranking e pontuação por acessos/comentários/curtidas.

---

## Visão das fases

```text
F0  Fundação          → banco, auth, layout, roles          [em andamento]
F1  Pastas + fotos    → CRUD, upload, visibilidade
F2  Privacidade       → convites, regras de acesso
F3  Interação         → comentários, curtidas
F4  Conteúdo adulto   → flag + modal
F5  Moderação         → denúncias + painel moderador
F6  Admin             → controles administrativos
F7  MVP release       → polish, testes, deploy
─────────────────────────────────────────────────
F8  Gamificação       → níveis, pontos, perfil com level (pós-MVP)
```

---

## Fase 0 — Fundação

**Objetivo:** base técnica e autenticação funcionando.

| # | Status | Tarefa | Entregável |
|---|--------|--------|------------|
| 0.1 | [x] | Adicionar SQLAlchemy + Alembic + SQLite (dev) | `src/db.py`, `src/models.py`, migrations |
| 0.2 | [x] | Modelo `User`: id, username (único), email, password_hash, role (`user`/`moderator`/`admin`), created_at | Migration + seed de admin |
| 0.3 | [ ] | Auth com sessão (cookie): registro, login, logout | `routes/auth.py`, `services/auth.py`, templates |
| 0.4 | [ ] | Middleware/dependency `get_current_user` (opcional/anônimo) | Reutilizável em todas as rotas |
| 0.5 | [ ] | Atualizar `base.html`: nav (login/logout), flash messages | Layout mínimo da galeria |
| 0.6 | [ ] | Substituir dashboard por feed vazio "Suas pastas" | `/` autenticado vs visitante |
| 0.7 | [ ] | Testes: registro, login, logout, acesso protegido | `tests/test_auth.py` |

**Critério de pronto:** usuário cria conta, faz login e vê área logada.

---

## Fase 1 — Pastas e fotos

**Objetivo:** CRUD de folders com upload de imagens.

| # | Tarefa | Entregável |
|---|--------|------------|
| 1.1 | Modelo `Folder`: title, slug, description, owner_id, is_public, is_adult (default false), created_at | Migration |
| 1.2 | Modelo `Photo`: folder_id, filename, original_name, order, created_at | Migration |
| 1.3 | Storage local em `uploads/` (configurável por env) | `services/storage.py` |
| 1.4 | Upload com validação (tipo, tamanho, extensão) | Service + testes |
| 1.5 | Criar pasta (título, descrição, pública/privada) | `POST /folders` |
| 1.6 | Listar pastas do usuário logado | `/me/folders` |
| 1.7 | Adicionar/remover/reordenar fotos na pasta | Rotas de gestão |
| 1.8 | Página pública da pasta por slug | `GET /folders/{slug}` |
| 1.9 | Galeria pública: listar pastas públicas recentes | `/explore` ou home para visitantes |
| 1.10 | Testes: criar pasta, upload, listar, ver pasta pública | `tests/test_folders.py` |

**Critério de pronto:** usuário cria pasta, sobe fotos e qualquer um vê pastas públicas.

---

## Fase 2 — Privacidade e convites

**Objetivo:** pastas privadas só para dono e convidados.

| # | Tarefa | Entregável |
|---|--------|------------|
| 2.1 | Modelo `FolderInvite`: folder_id, user_id (ou email pendente), invited_by, status | Migration |
| 2.2 | Service `can_view_folder(user, folder)` | Centraliza regra de acesso |
| 2.3 | Pasta privada retorna 403/404 para não autorizados | Rotas + testes |
| 2.4 | Dono convida por username | `POST /folders/{id}/invites` |
| 2.5 | Dono remove convidado | `DELETE /folders/{id}/invites/{user_id}` |
| 2.6 | Listar convidados da pasta | UI na edição da pasta |
| 2.7 | Pastas privadas não aparecem em `/explore` | Filtro no service |
| 2.8 | Testes: dono vê, convidado vê, terceiro não vê | `tests/test_folder_access.py` |

**Critério de pronto:** privada invisível para quem não foi convidado.

---

## Fase 3 — Comentários e curtidas

**Objetivo:** interação social nas pastas.

| # | Tarefa | Entregável |
|---|--------|------------|
| 3.1 | Modelo `Comment`: folder_id, user_id, body, created_at | Migration |
| 3.2 | Modelo `FolderLike`: folder_id, user_id (unique) | Migration |
| 3.3 | Service `can_comment(user, folder)` — pública: logado; privada: convidado/dono | Regra centralizada |
| 3.4 | Listar comentários na página da pasta | Template + rota |
| 3.5 | Criar comentário (só logado, com permissão) | `POST /folders/{slug}/comments` |
| 3.6 | Curtir/descurtir pasta (toggle) | `POST /folders/{slug}/like` |
| 3.7 | Exibir contador de curtidas e estado "você curtiu" | UI na pasta |
| 3.8 | Perfil público `/users/{username}` — username + pastas públicas | Sem nível ainda |
| 3.9 | Testes: comentar em pública/privada, curtir, perfil | `tests/test_interactions.py` |

**Critério de pronto:** visitante logado interage em pública; em privada só convidados comentam.

---

## Fase 4 — Conteúdo adulto

**Objetivo:** proteção antes de exibir pasta marcada.

| # | Tarefa | Entregável |
|---|--------|------------|
| 4.1 | Flag `is_adult` na criação/edição da pasta | Form + validação |
| 4.2 | Rota intermediária ou gate na visualização | Não renderiza fotos antes da confirmação |
| 4.3 | Modal de confirmação (JS em `static/js/`) | "Tenho 18+ anos, continuar" |
| 4.4 | Persistir confirmação na sessão por pasta (ou cookie) | Evita modal em cada foto |
| 4.5 | Badge "+18" na listagem | Explore e perfil |
| 4.6 | Testes: pasta adulta exige confirmação; após confirmar, libera | `tests/test_adult_content.py` |

**Critério de pronto:** pasta +18 não mostra imagens sem confirmação explícita.

---

## Fase 5 — Denúncias e moderação

**Objetivo:** moderadores revisam conteúdo reportado.

| # | Tarefa | Entregável |
|---|--------|------------|
| 5.1 | Modelo `Report`: reporter_id, target_type (`folder`/`comment`), target_id, reason, status (`open`/`resolved`/`dismissed`), moderator_id, notes | Migration |
| 5.2 | Botão "Denunciar" em pasta e comentário (logado) | Form simples com motivo |
| 5.3 | `POST /reports` — uma denúncia aberta por usuário/alvo | Evita spam |
| 5.4 | Painel `/moderation` (role `moderator` ou `admin`) | Lista denúncias abertas |
| 5.5 | Ações: arquivar, remover comentário, ocultar pasta, banir pasta | Services + audit log simples |
| 5.6 | Notificação visual ao moderador (contador no nav) | Opcional no MVP |
| 5.7 | Testes: criar denúncia, moderador resolve, user comum não acessa painel | `tests/test_moderation.py` |

**Critério de pronto:** denúncia criada → moderador age → conteúdo tratado.

---

## Fase 6 — Admin

**Objetivo:** controles extras para administradores.

| # | Tarefa | Entregável |
|---|--------|------------|
| 6.1 | Painel `/admin` (só `admin`) | Layout separado ou seção no base |
| 6.2 | Listar usuários, buscar por username/email | Tabela simples |
| 6.3 | Promover/rebaixar role (user ↔ moderator) | Sem auto-promoção |
| 6.4 | Desativar usuário ou banir | Flag `is_active` no User |
| 6.5 | Remover qualquer pasta/comentário | Override de moderação |
| 6.6 | Métricas básicas: usuários, pastas, denúncias abertas | Cards no admin |
| 6.7 | Testes: admin acessa; user/moderator não | `tests/test_admin.py` |

**Critério de pronto:** admin gerencia usuários e conteúdo da plataforma.

---

## Fase 7 — MVP release

**Objetivo:** produto utilizável e estável.

| # | Tarefa | Entregável |
|---|--------|------------|
| 7.1 | Páginas de erro 403/404 amigáveis | Templates |
| 7.2 | Paginação em explore, comentários e moderação | Evita listas enormes |
| 7.3 | Limites: max fotos/pasta, max tamanho upload | Config via env |
| 7.4 | README com setup, env vars, `make` commands | Documentação |
| 7.5 | Suite de testes completa + `make test` verde | CI opcional (GitHub Actions) |
| 7.6 | Revisão de segurança básica: CSRF em forms, hash de senha, path traversal no upload | Checklist |
| 7.7 | Deploy mínimo (Dockerfile ou doc de deploy) | Um ambiente de staging |

**Critério de pronto:** MVP entregável em staging/produção.

---

## Fase 8 — Gamificação (pós-MVP)

**Objetivo:** níveis e engajamento. Só depois do MVP fechado.

| # | Tarefa | Entregável |
|---|--------|------------|
| 8.1 | Modelo `UserStats`: views_received, comments_count, likes_received | Migration |
| 8.2 | Eventos: view em pasta, comentário, curtida → pontos | Service assíncrono ou inline |
| 8.3 | Fórmula de nível (ex.: `floor(sqrt(pontos / 10))`) | Configurável |
| 8.4 | Perfil exibe nível + barra de progresso | `/users/{username}` |
| 8.5 | Ranking opcional `/leaderboard` | Top N usuários |
| 8.6 | Testes da fórmula e atualização de stats | `tests/test_gamification.py` |

---

## Modelo de dados (resumo)

```text
User ──┬── Folder ──┬── Photo
       │            ├── FolderInvite
       │            ├── Comment
       │            └── FolderLike
       └── Report (como reporter ou moderator)

Roles: user | moderator | admin
Folder: is_public, is_adult
```

---

## Ordem sugerida de implementação

```text
0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.7
  ↓
1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9 → 1.10
  ↓
2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8
  ↓
3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7 → 3.8 → 3.9
  ↓
4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6
  ↓
5.1 → 5.2 → 5.3 → 5.4 → 5.5 → 5.6 → 5.7
  ↓
6.1 → 6.2 → 6.3 → 6.4 → 6.5 → 6.6 → 6.7
  ↓
7.1 → 7.2 → 7.3 → 7.4 → 7.5 → 7.6 → 7.7
  ↓
[MVP COMPLETO]
  ↓
Fase 8 (gamificação)
```

---

## Decisões técnicas recomendadas (MVP)

| Tema | Decisão |
|------|---------|
| Auth | Sessão com cookie (`SessionMiddleware` + bcrypt) |
| Banco | SQLite local; PostgreSQL no deploy |
| Upload | Filesystem local (`UPLOAD_DIR`) |
| Slug da pasta | Gerado do título, único globalmente |
| Privada não listada | 404 para quem não tem acesso (não revelar existência) |
| Curtidas | No MVP; pontos/nível só na Fase 8 |

---

## Como usar este roadmap

Cada tarefa pode virar um PR pequeno: schema → service → route → template → teste. Uma tarefa por vez, na ordem acima.

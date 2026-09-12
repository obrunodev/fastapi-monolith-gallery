# AGENTS.md — Projeto TLC (monolito FastAPI)

Este arquivo é a regra de ouro para pessoas e agentes de IA que alteram este repositório. Siga-o antes de inventar uma arquitetura nova.

## Objetivo do repositório

Este é um **monolito FastAPI**. Preferimos um único processo, um único deploy e pastas previsíveis a microserviços, camadas extras ou frameworks paralelos.

O frontend atual é **HTML renderizado no servidor** (Jinja2). Não introduza um SPA, bundler ou framework JS sem uma decisão explícita do time.

## Layout obrigatório

```text
src/
  main.py            # fábrica da aplicação e montagem de routers/static
  templating.py      # instância única de Jinja2Templates
  routes/            # endpoints HTTP (finos)
  schemas/           # contratos Pydantic (entrada/saída)
  services/          # regras de negócio e orquestração
  templates/         # HTML (herda de base.html)
  static/            # CSS, JS e assets públicos
tests/               # pytest
```

Não crie `controllers/`, `repositories/`, `usecases/`, `domain/` ou `core/` só por simetria com outros projetos. Extraia uma pasta nova só quando o código já existir em dois ou mais lugares e a extração reduzir complexidade.

Imports usam o pacote `src` (`from src.services.health import get_health`).

## Responsabilidade de cada camada

### `routes/`

- Recebem HTTP, validam via `schemas` (ou parâmetros FastAPI) e devolvem resposta.
- Não acessam banco, filesystem ou APIs externas diretamente.
- Não montam HTML com strings. Páginas usam `templates.TemplateResponse`.
- Um arquivo por área (`health.py`, `pages.py`, `orders.py`). Agrupe rotas relacionadas no mesmo router.
- Registre routers em `src/main.py` via `include_router`. Prefixos (`/api`, `/admin`) só existem quando há um motivo de produto, não por costume.

```python
# Bom
@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return get_health()

# Ruim
@router.get("/health")
def health() -> dict:
    return {"status": "ok", "db": engine.execute("SELECT 1")}
```

### `schemas/`

- Única fonte de contratos da API. Use Pydantic v2.
- Nomes explícitos: `HealthResponse`, `OrderCreate`, `OrderRead`. Evite `Schema`, `DTO` e `Model` genéricos.
- Não coloque I/O, queries ou `datetime.now()` dentro do schema. Validação de formato, sim; efeito colateral, não.
- Endpoints JSON devem declarar `response_model`.

### `services/`

- Onde a regra de negócio vive. Funções ou classes pequenas e testáveis.
- Recebem dados já validados (schemas ou tipos primitivos) e devolvem schemas ou objetos de domínio simples.
- Dependências externas (banco, filas, HTTP) entram por parâmetro ou helper local — não via import global escondido no meio da função, salvo configuração da aplicação.
- Um service não importa `APIRouter` nem `Request`.

### `templates/` e `static/`

- Todo template **estende `templates/base.html`**, salvo necessidade real (e-mail, página de erro isolada, documento para impressão).
- Não duplique `<html>`, `<head>` ou o carregamento de CSS/JS base. Use `{% block content %}`, `{% block extra_head %}` e `{% block extra_scripts %}`.
- CSS e JS entram em `src/static/` e são servidos em `/static`. Não coloque `<style>` ou `<script>` grandes nos templates.
- Templates só apresentam dados. Sem SQL, sem chamadas HTTP, sem regra de autorização além de exibir o que a rota já decidiu.

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<p>Dashboard</p>
{% endblock %}
```

### `main.py`

- `create_app()` constrói a aplicação: static files, routers, middlewares futuros.
- Testes instanciam `create_app()`, não um singleton mutável.
- Não coloque regra de negócio aqui.

## Como crescer o monolito (sem virar um emaranhado)

1. Nova tela HTML: rota em `routes/`, template que herda `base.html`, CSS/JS só se precisar.
2. Novo endpoint JSON: `schema` → `service` → `route` → teste.
3. Persistência: comece pelo ponto de uso no service. Extraia um módulo `src/db.py` ou `src/models.py` quando houver mais de uma tabela ou sessão compartilhada — não no primeiro `SELECT`.
4. Background jobs, cache e filas só quando um requisito concreto exigir. O default é request/response síncrono.
5. Divida o processo em outro serviço apenas se houver motivo operacional (escala independente, isolamento de falha, ciclo de release incompatível). Até lá, pastas novas dentro de `src/` bastam.

## FastAPI e Python — práticas do time

- Python 3.12+. Type hints em funções públicas de routes, schemas e services.
- Prefira funções síncronas até existir I/O assíncrono real (`httpx.AsyncClient`, driver async). Não marque `async def` por estética.
- Use `HTTPException` para erros de API esperados. Não retorne `{"error": "..."}` com status 200.
- IDs e filtros vêm do path/query; o corpo JSON é para dados de escrita.
- Não exponha stack traces, secrets nem SQL em respostas.
- Configuração via variáveis de ambiente (quando surgir). Não commitar `.env` com segredos.
- Datas e dinheiro: tipos explícitos (`datetime`, `Decimal`). Nunca misture `float` com valores monetários.
- Rotas que retornam HTML **e** redirecionamento: anotar `HTMLResponse | RedirectResponse` e usar `response_model=None` no decorator (FastAPI não infere union de responses).
- `get_current_user` já roda globalmente em `create_app()`. Nas rotas:
  - use `Depends(get_current_user)` quando o handler precisa do valor (`if current_user is None`, API JSON com 401);
  - não repasse `current_user` ao template se `_session_context` em `templating.py` já injeta o usuário.
- Endpoints JSON autenticados: `401` via `HTTPException`. Formulários SSR: flash + `RedirectResponse` para `/login`.

### SQLAlchemy (consultas)

- Use **SQLAlchemy 2.0**: `select()` + `session.scalar()` / `session.scalars()`.
- Não use `session.query()` (legado). Siga `src/services/auth.py` e `src/services/folders.py`.

```python
# Bom
user = session.scalar(select(User).where(User.id == user_id))

# Ruim
user = session.query(User).filter(User.id == user_id).first()
```

### Upload e arquivos

- Validação de imagem (magic bytes, extensão, MIME, tamanho) fica em `src/services/storage.py` (`validate_image`, `save_image`).
- Leitura/escrita em disco e path traversal: mesmo módulo. Rotas não acessam filesystem diretamente.
- Limites e paths vêm de `src/config.py` (`UPLOAD_DIR`, `MAX_UPLOAD_SIZE`). Documente novas env vars no `README.md`.

## Testes

- Framework: **pytest**. Cliente: `TestClient` do FastAPI (`httpx` como dependência).
- Todo endpoint novo precisa de teste do contrato feliz (status + corpo ou HTML relevante).
- Teste o comportamento observável da rota/service, não detalhes de Jinja ou de implementação interna.
- Fixtures comuns ficam em `tests/conftest.py`. Reutilize `client`.
- Não dependa de rede, serviços reais ou ordem dos testes. Se um banco aparecer, use fixture isolada (container ou SQLite de teste) — nunca o banco de desenvolvimento compartilhado.
- Nomeie arquivos `test_<area>.py` e funções `test_<comportamento>`.
- Testes de **modelo** isolado: `test_<model>_model.py` (ex.: `test_folder_model.py`).
- Testes de **rotas/fluxo** da área: `test_<area>.py` (ex.: `test_folders.py`).
- Não deixe helpers/fixtures mortos no arquivo de teste.

```python
def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

## Dependências e comandos

Gerenciador oficial: **uv**. Não adicione `requirements.txt` paralelo nem misture `pip install` solto no dia a dia.

```text
make install   # uv sync --group dev
make run       # uvicorn com reload
make test      # pytest
```

- Dependência de runtime: `uv add pacote`
- Dependência de desenvolvimento: `uv add --dev pacote`
- Versões ficam no `pyproject.toml` / `uv.lock`. Commitar o lockfile.

## O que não fazer

- Não criar um segundo `base.html` “só para essa tela” sem justificar.
- Não colocar CSS/JS de página em `templates/` se cabe em `static/`.
- Não deixar a rota falar com banco e montar HTML ao mesmo tempo.
- Não copiar DTOs, mappers e factories de arquiteturas hexagonais sem necessidade.
- Não adicionar autenticação, CORS aberto, admin ou ORM “para já deixar pronto”.
- Não commitar `__pycache__/`, `.venv`, secrets ou dumps.
- Não “consertar” formatação em arquivos que você não está alterando.

## Quando um agente (ou pessoa) termina uma tarefa

1. Implementar **uma tarefa do ROADMAP por vez**; commits separados por tarefa quando possível.
2. Atualizar `ROADMAP.md` (progresso + checkbox) e `.cursor/rules/projeto-tlc.mdc` (o que existe + próxima tarefa).
3. Manter a estrutura de pastas.
4. Rodar `make test` (e `make db-upgrade` se houver migration).
5. Se mudou UI, verificar a página afetada e rotas que compartilham o mesmo template/estado.
6. Descrever a mudança em linguagem de produto (“o /health passa a responder ok”), não só listar arquivos.

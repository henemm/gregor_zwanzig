---
entity_id: ssr_cache_headers_tests
type: tests
created: 2026-05-04
updated: 2026-05-04
status: draft
version: "1.0"
tags: [tests, frontend, sveltekit, http-headers, safari, issue-125]
---

# Tests: SSR Cache-Control Headers (Issue #125)

## Approval

- [x] Approved

## Purpose

TDD-Tests für die HTTP-Response-Header der SvelteKit-SSR-Pages. Validiert,
dass HTML-Responses `Cache-Control: no-cache` setzen, während hash-immutable
Asset-Chunks und API-JSON-Responses unberührt bleiben.

## Source

- **File:** `tests/tdd/test_ssr_cache_headers.py`
- **Identifier:** Funktionen mit Prefix `test_*`

## Bezug

- Bug-Spec: `docs/specs/bugfix/ssr_cache_control_headers.md`
- GitHub Issue #125
- Analyse-Doku: `docs/context/bug-125-safari-html-cache.md`

## Test-Strategie

- **Real HTTP, no mocks** — laut CLAUDE.md ("KEINE MOCKED TESTS") werden alle
  Requests gegen einen echten, deployed Frontend-Server geschickt (Default:
  Staging, via `GZ_TEST_BASE_URL` überschreibbar).
- **Public-Path-Targets** — Tests treffen `/login` (HTML, ohne Auth erreichbar)
  und `/api/health` (JSON, ohne Auth erreichbar), damit kein Login-Setup nötig
  ist.
- **Asset-Pfad dynamisch** — der Asset-Chunk-Pfad wird aus der HTML-Response
  extrahiert (`/_app/immutable/...`-Regex), damit der Test deploy-resistent
  gegen Build-Hash-Wechsel ist.

## Covered Test Functions

- `html_response_has_no_cache_header`
- `asset_chunk_keeps_immutable_header`
- `api_response_not_affected`

### `html_response_has_no_cache_header`

- **Given:** SSR-HTML-Page (`/login`, public)
- **When:** GET-Request mit `httpx`
- **Then:** `cache-control`-Header enthält `no-cache`
- **TDD-Phase:** RED vor dem Fix (Header fehlt komplett), GREEN nach Implementierung in `hooks.server.ts`.

### `asset_chunk_keeps_immutable_header`

- **Given:** Hash-versionierter Asset-Chunk unter `/_app/immutable/...`
- **When:** GET-Request mit `httpx`
- **Then:** `cache-control`-Header enthält `immutable` und kein `no-cache`
- **TDD-Phase:** Guard-Test — bereits GREEN; sichert ab, dass der Fix die
  Long-Cache-Strategie für Assets nicht versehentlich bricht.

### `api_response_not_affected`

- **Given:** API-JSON-Endpoint (`/api/health`, public)
- **When:** GET-Request mit `httpx`
- **Then:** `cache-control`-Header enthält kein `no-cache` aus dem
  `handle`-Hook
- **TDD-Phase:** Guard-Test — bereits GREEN; sichert ab, dass der Fix
  ausschließlich auf HTML-Responses wirkt.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `httpx` | Library | Echte HTTP-Requests gegen Frontend-Server |
| `pytest` | Library | Test-Runner |
| `GZ_TEST_BASE_URL` | Env-Var | Default `https://staging.gregor20.henemm.com` |
| `frontend/src/hooks.server.ts` | Code unter Test | Liefert `Cache-Control`-Header |

## Expected Behavior

### Vor dem Fix (RED)

- `html_response_has_no_cache_header` schlägt fehl: `cache-control`-Header
  fehlt vollständig in der Response.
- `asset_chunk_keeps_immutable_header` läuft grün (Status quo).
- `api_response_not_affected` läuft grün (Status quo).

### Nach dem Fix (GREEN)

- Alle drei Tests laufen grün.

## Known Limitations

- **Staging-Abhängigkeit:** Tests laufen gegen den deployed Server. Lokale
  Ausführung verlangt entweder gestarteten Frontend-Build (`node build/index.js`)
  oder Override via `GZ_TEST_BASE_URL`.
- **Public-Path-Beschränkung:** Tests treffen nur public Paths (`/login`,
  `/api/health`) — auth-pflichtige Routen würden eigene Login-Fixture brauchen.
  Für den Cache-Header-Fix ist das ausreichend, da der Hook für alle Pfade
  identisch arbeitet.

## Changelog

- 2026-05-04: Initial spec für Test-Funktionen rund um Issue #125 angelegt.

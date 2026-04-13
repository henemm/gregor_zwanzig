# Analyse: SvelteKit Frontend Setup + Auth (#26)

**Datum:** 2026-04-13
**Workflow:** sveltekit-setup
**Phase:** 2 (Analyse)

## Request

SvelteKit 5 Projekt aufsetzen mit shadcn-svelte, Cookie-basierter Auth und TypeScript API Client.

## Ist-Zustand

- Go API (Chi v5, Port 8090): CRUD Locations/Trips, OpenMeteo Forecast, Health
- Kein Auth, kein CORS, kein Session-Handling
- Store: data/users/{userid}/ mit hardcoded UserID="default"
- Kein Node.js/Frontend Setup vorhanden
- OpenAPI 3.1 Spec: 6 Schemas

## Architektur-Entscheidung: Shared-Secret Cookie Auth

- SvelteKit besitzt Login-Flow, prueft ENV-Credentials (GZ_AUTH_USER/GZ_AUTH_PASS)
- Signierter httpOnly Cookie gz_session (HMAC-SHA256 mit GZ_SESSION_SECRET)
- Cookie-Format: {userId}.{timestamp}.{signature}
- Go-Middleware validiert denselben Cookie mit demselben Secret
- Kein CORS noetig (Vite-Proxy dev, Nginx prod = same-origin)

## Implementierungs-Phasen

| Phase | Was | Dateien | LOC |
|-------|-----|---------|-----|
| A | SvelteKit Scaffold | 4 | ~80 |
| B | TS Types + API Client | 2 | ~120 |
| C | Auth (SvelteKit) | 3 | ~120 |
| D | Go Auth-Middleware | 3 | ~95 |
| E | Layout Shell | 3 | ~150 |
| Total | | ~15 | ~565 |

## Betroffene bestehende Dateien

- cmd/server/main.go — Middleware-Wiring (+5 LOC)
- internal/config/config.go — SessionSecret, AuthUser, AuthPass (+4 LOC)

## Neue Dateien

### Go
- internal/middleware/auth.go — Cookie-Validierung (~80 LOC)

### Frontend (frontend/)
- package.json, svelte.config.ts, vite.config.ts, tailwind.config.ts, app.css
- src/hooks.server.ts
- src/lib/types.ts, src/lib/api.ts
- src/routes/login/+page.svelte, +page.server.ts
- src/routes/+layout.svelte, +layout.server.ts, +page.svelte

## Risiken

1. Cookie-Sharing zwischen Ports (Dev) — Vite-Proxy loest das
2. Go Store pro-Start statt pro-Request — V1: nur userid-Validierung
3. shadcn-svelte + Svelte 5 — bits-ui 1.x pinnen

## Types (aus openapi.yaml, hand-written)

Location, Waypoint, Stage, Trip, HealthResponse, ApiError — 6 Interfaces, ~40 LOC TS

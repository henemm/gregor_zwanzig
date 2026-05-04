# Context: bug-125-safari-html-cache

**Issue:** [#125](https://github.com/henemm/gregor_zwanzig/issues/125)
**Phase:** Analysis (2026-05-04)

## Problem

Safari Mac liefert nach Frontend-Deploys stale HTML aus dem Browser-Cache aus. Click-Handler reagieren nicht — Symptom: "Neuer Trip"-Button auf `/trips` macht nichts. Reproduzierbar nur in Safari mit aufgewärmtem Cache; in Chrome, Firefox und Playwright (Chromium + WebKit) tritt der Bug nicht auf.

## Root Cause

SSR-HTML-Antworten von gregor20.henemm.com senden **keinen `Cache-Control`-Header**:

```
$ curl -D - https://gregor20.henemm.com/trips
Content-Type: text/html
etag: "..."
X-Content-Type-Options: nosniff
```

Ohne expliziten Header nutzt Safari heuristisches Caching. Nach einem Frontend-Deploy referenziert das gecachte HTML alte Build-Hash-Chunks, die — falls noch vorhanden (immutable Cache) — geladen werden, aber zu inkonsistentem Hydration-State führen. Click-Handler haften nicht.

## Ist-Zustand (aus Analyse)

| Schicht | Status |
|---|---|
| `frontend/src/hooks.server.ts` | Greenfield: nur Auth-Logik, **keine** `setHeaders`-Aufrufe |
| `frontend/src/routes/api/[...path]/+server.ts` | API-Proxy, setzt nur `Content-Type`, kein Cache-Control |
| `henemm-infra/nginx/gregor20.henemm.com.conf` | Pass-Through ohne Cache-Header (anders als `henemm.com.conf`) |
| `/_app/immutable/...` Asset-Chunks | bereits korrekt: `cache-control: public,max-age=31536000,immutable` |
| Tests für HTTP-Header | keine bestehenden in `frontend/`; Pattern in `tests/tdd/test_safari_cache_fix.py` |

## Strategie

**Single Source of Truth:** Cache-Header in der SvelteKit-Quelle setzen, nicht im Edge.

**Fix:** `frontend/src/hooks.server.ts` ergänzt um Content-Type-gefilterten Cache-Header für HTML-Responses:

```ts
const response = await resolve(event);
const ct = response.headers.get('content-type') ?? '';
if (ct.includes('text/html')) {
  response.headers.set('cache-control', 'no-cache');
}
return response;
```

**Bewusst nicht im Scope:**
- Nginx-Layer-Härtung (`gregor20.henemm.com.conf` analog zu `henemm.com.conf`) → eigenes Follow-up-Issue (Defense in Depth, nicht Bug-Fix)
- Service-Worker (existiert nicht, `/service-worker.js` gibt 302)

## Scope

| Datei | Änderung |
|---|---|
| `frontend/src/hooks.server.ts` | +~5 LoC (Header-Block nach `resolve`) |
| `tests/tdd/test_ssr_cache_headers.py` | neu (3 Tests: HTML hat no-cache, Asset bleibt immutable, API unbeeinflusst) |
| `docs/specs/bugfix/ssr_cache_control_headers.md` | neu (Spec) |

**~65 LoC, 2 Code-Dateien** — unter Limit.

## Risiken

- **Falsche Filterung:** API-Antworten oder Asset-Chunks dürfen den `no-cache`-Header **nicht** bekommen. Mitigation: Content-Type-Filter auf `text/html`; Test deckt API + Asset explizit ab.
- **TDD-RED-Ausführung:** Tests brauchen laufenden Frontend-Server. Lokaler Build (`node build/index.js` auf Test-Port) oder Staging nach Auto-Deploy. Zweites passt zum Memory-Punkt "Validator nach Push".

## Test-Ansatz

Echter HTTP-Server (kein Mock) + `httpx`:
1. `GET /` → `cache-control: no-cache` enthalten
2. `GET /_app/immutable/<chunk>.js` → `cache-control: public,max-age=31536000,immutable` unverändert
3. `GET /api/health` (oder beliebiger API-Endpoint) → kein `no-cache` von uns gesetzt

## Verifikation in Prod (nach Deploy)

1. `curl -D - https://gregor20.henemm.com/trips | grep -i cache-control` → zeigt `no-cache`
2. Real-User-Test Safari Mac: vor Deploy `/trips` öffnen → deployen → ohne Cache-Leeren wieder `/trips` → "Neuer Trip" funktioniert

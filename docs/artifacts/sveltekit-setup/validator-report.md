# External Validator Report

**Spec:** docs/specs/modules/sveltekit_setup.md
**Datum:** 2026-04-13T08:24:00Z
**Server:** https://gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Unauthenticated User: Redirect zu /login bei jedem Route-Zugriff | `curl / -> 200` (NiceGUI Dashboard), `curl /trips -> 200` (NiceGUI). Kein Redirect zu /login. | **FAIL** |
| 2 | Login: Credentials gegen ENV pruefen, Cookie setzen, redirect / | `/login -> 404` (NiceGUI 404-Seite). Login-Page existiert nicht. | **FAIL** |
| 3 | Authenticated User: Sidebar-Navigation, Dashboard zeigt Health-Status | Kein SvelteKit Frontend vorhanden. Frontend ist NiceGUI (Vue3/Quasar 3.4.1). Keine SvelteKit-Sidebar. | **FAIL** |
| 4 | API Calls: Cookie wird mitgesendet, Proxy funktioniert | SvelteKit laeuft nicht (Port 3000 nicht erreichbar). Kein Vite-Proxy, kein Nginx-Proxy zu SvelteKit. | **FAIL** |
| 5 | Go API: Validiert Cookie, gibt 401 bei ungueltigem Cookie | Alle 5 Tests bestanden (siehe Finding 4). | **PASS** |
| 6 | Logout: Cookie loeschen, redirect /login | Kein Logout-Mechanismus vorhanden (kein SvelteKit Frontend). | **FAIL** |

## Findings

### Finding 1: SvelteKit Frontend nicht deployed
- **Severity:** CRITICAL
- **Expected:** SvelteKit 5 Frontend auf Port 3000, erreichbar ueber Nginx Reverse-Proxy
- **Actual:** Port 3000 antwortet nicht (`curl http://localhost:3000 -> connection refused`). Server liefert das alte NiceGUI-Frontend (Vue3/Quasar, NiceGUI 3.4.1).
- **Evidence:** WebFetch von / zeigt NiceGUI-Dashboard mit Quasar-Komponenten. WebFetch von /locations zeigt NiceGUI-Locations-Seite mit 15 Location-Cards.

### Finding 2: Login-Page existiert nicht
- **Severity:** CRITICAL
- **Expected:** SvelteKit Login-Formular unter /login mit Credential-Check gegen ENV
- **Actual:** `/login` liefert NiceGUI 404-Seite: "This page doesn't exist. HTTPException: 404: Not Found"
- **Evidence:** `curl -s -w "%{http_code}" /login -> 404`. Response-Body zeigt NiceGUI 404-Template mit SVG-Illustration.

### Finding 3: Kein Auth-Redirect auf Frontend-Routen
- **Severity:** CRITICAL
- **Expected:** hooks.server.ts redirected unauthenticated Users zu /login
- **Actual:** Alle Frontend-Routen (/, /trips, /locations) antworten mit HTTP 200 ohne Authentifizierung. Kein SvelteKit hooks.server.ts aktiv.
- **Evidence:** `curl / -> 200`, `curl /trips -> 200`, `curl /locations -> 200`. Alle liefern NiceGUI-Seiten.

### Finding 4: Go Auth-Middleware funktioniert korrekt
- **Severity:** (positiv — einziger PASS)
- **Expected:** /api/* (ausser /api/health) gibt 401 ohne gueltigen Cookie
- **Actual:** Alle API-Endpunkte korrekt geschuetzt. Health-Endpoint korrekt exempt.
- **Evidence:**
  - `GET /api/trips` ohne Cookie -> `401 {"error":"unauthorized"}` ✓
  - `GET /api/locations` ohne Cookie -> `401 {"error":"unauthorized"}` ✓
  - Abgelaufener Cookie (`default.0.abc123`) -> `401` ✓
  - Manipulierter HMAC (`default.9999999999.deadbeef`) -> `401` ✓
  - Malformed Cookie (`garbage`) -> `401` ✓
  - `GET /api/health` ohne Cookie -> `200 {"status":"ok","version":"0.1.0","python_core":"ok"}` ✓

## Verdict: BROKEN

### Begruendung

**1 von 6 Expected-Behavior-Punkten bestanden** (nur Go Auth-Middleware).

Das SvelteKit-Frontend (die Frontend-Haelfte der Spec) ist auf dem Produktionsserver vollstaendig nicht vorhanden:
- Kein SvelteKit-Prozess laeuft (Port 3000 nicht erreichbar)
- Keine Login-Page (/login -> 404)
- Kein Auth-Redirect auf Frontend-Routen
- Keine SvelteKit Sidebar-Navigation
- Kein Dashboard mit Health-Status
- Kein Logout

Der Server liefert weiterhin das alte NiceGUI-Frontend. Die Go Auth-Middleware auf `/api/*` funktioniert hingegen korrekt und schuetzt alle Endpunkte (ausser /api/health) mit Cookie-basierter HMAC-SHA256 Validierung.

**Fazit:** Backend-Auth (Go Middleware) = implementiert und funktional. Frontend (SvelteKit) = nicht deployed / nicht vorhanden.

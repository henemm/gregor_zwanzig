---
spec: docs/specs/bugfix/ssr_cache_control_headers.md
date: 2026-05-04T16:46Z
server: https://staging.gregor20.henemm.com
---

# External Validator Report

**Spec:** docs/specs/bugfix/ssr_cache_control_headers.md
**Datum:** 2026-05-04T16:46Z
**Server:** https://staging.gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | HTML-Response (SSR-Page) hat `cache-control: no-cache` | `curl -D -` auf `/login`, `/trips`, `/forgot-password`, `/register`, `/compare` — alle `Content-Type: text/html` + `cache-control: no-cache` | PASS |
| 2 | Asset-Chunk `/_app/immutable/…` behält `public,max-age=31536000,immutable` | `curl -D -` auf `/_app/immutable/entry/start.CpR10SZT.js` und `/_app/immutable/assets/0.CqhNk5e7.css` — beide liefern `cache-control: public,max-age=31536000,immutable`, kein `no-cache` | PASS |
| 3 | API-JSON-Response erhält kein `no-cache` vom Handle-Hook | `curl -D -` auf `/api/health` (Content-Type: application/json) und `/api/scheduler/status` (mit Auth-Cookie) — beide ohne `cache-control`-Header | PASS |

## Detailbeweise

### Case 1 — HTML-Responses

```
GET /login → 200 OK  Content-Type: text/html  cache-control: no-cache
GET /trips (auth)  → 200 OK  Content-Type: text/html  cache-control: no-cache
GET /forgot-password → 200 OK  Content-Type: text/html  cache-control: no-cache
GET /register → 200 OK  Content-Type: text/html  cache-control: no-cache
GET /compare (auth, via /locations 301-Redirect) → 200 OK  Content-Type: text/html  cache-control: no-cache
```

Sowohl Public-Pfade (im `publicPaths`-Branch) als auch authentifizierte Pfade (Hauptbranch) setzen den Header — Implementierungsschritt 1 + 2 der Spec sind erfüllt.

### Case 2 — Asset-Chunks unverändert

```
GET /_app/immutable/entry/start.CpR10SZT.js
  Content-Type: text/javascript
  cache-control: public,max-age=31536000,immutable

GET /_app/immutable/assets/0.CqhNk5e7.css
  Content-Type: text/css
  cache-control: public,max-age=31536000,immutable
```

Kein `no-cache` — die Filterregel `content-type includes 'text/html'` greift wie erwartet nicht für JS/CSS.

### Case 3 — API-JSON unbeeinflusst

```
GET /api/health
  Content-Type: application/json
  (kein cache-control im Response — Handle-Hook hat nichts gesetzt)

GET /api/scheduler/status (mit Auth-Cookie)
  Content-Type: application/json
  (kein cache-control)
```

API-JSON-Responses werden vom Filter ignoriert. Der API-Proxy (`+server.ts`) wird nicht überschrieben.

### Zusatzbefund — 302-Redirects

`GET /` → `302 Found` mit `location: /login` enthält kein `cache-control` und keinen HTML-Body. Spec erwähnt explizit unter Implementierungsschritt 4: „Keine Änderungen an `redirect(302, '/login')`". Verhalten konsistent mit Spec — kein Problem.

## Findings

Keine Findings. Alle drei Expected-Behavior-Cases der Spec sind durch echte HTTP-Requests gegen den Staging-Server bestätigt.

## Verdict: VERIFIED

### Begründung

Alle drei Success-Criteria-Punkte aus Spec § Expected Behavior sind durch echte `curl -D -`-Requests gegen `https://staging.gregor20.henemm.com` belegt:

1. SSR-HTML-Responses (sowohl Public- als auch Auth-Branches) tragen `cache-control: no-cache`.
2. Asset-Chunks unter `/_app/immutable/…` behalten `public,max-age=31536000,immutable` und erhalten **kein** `no-cache`.
3. API-JSON-Responses tragen kein vom Handle-Hook gesetztes `no-cache`.

Die Filterregel `content-type includes 'text/html'` wirkt selektiv wie spezifiziert. Der Real-User-Test in Safari (Success-Criterion 4 der Spec) ist Validator-extern und hier nicht prüfbar — aber der HTTP-seitige Fix, der die Voraussetzung für das Safari-Verhalten ist, ist auf Header-Ebene vollständig und konsistent umgesetzt.

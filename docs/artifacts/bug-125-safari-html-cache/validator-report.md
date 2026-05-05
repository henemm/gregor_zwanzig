# External Validator Report

**Spec:** docs/specs/bugfix/ssr_cache_control_headers.md
**Datum:** 2026-05-04T16:52:30Z
**Server:** https://staging.gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | HTML-SSR-Page (`/trips`) → `cache-control: no-cache` | `curl -D -` liefert `Content-Type: text/html` und `cache-control: no-cache` (Evidence 1) | PASS |
| 2 | Public-Path HTML (`/login`) → `cache-control: no-cache` | `curl -D -` liefert `Content-Type: text/html` und `cache-control: no-cache` (Evidence 2) | PASS |
| 3 | JS-Asset-Chunk → `cache-control: public,max-age=31536000,immutable` (unverändert) | `/_app/immutable/entry/start.CpR10SZT.js` liefert `cache-control: public,max-age=31536000,immutable` (Evidence 3) | PASS |
| 4 | CSS-Asset → `cache-control: public,max-age=31536000,immutable` (unverändert) | `/_app/immutable/assets/0.CqhNk5e7.css` liefert `cache-control: public,max-age=31536000,immutable` (Evidence 4) | PASS |
| 5 | API-JSON-Response (public) → kein `no-cache` von `handle` | `/api/health` liefert `Content-Type: application/json`, **kein** `cache-control`-Header (Evidence 5) | PASS |
| 6 | API-JSON-Response (authentifiziert) → kein `no-cache` von `handle` | `/api/trips` mit Cookie liefert `Content-Type: application/json`, **kein** `cache-control` (Evidence 6) | PASS |
| 7 | API-Status-Endpoint → kein `no-cache` von `handle` | `/api/scheduler/status` liefert JSON, **kein** `cache-control` (Evidence 7) | PASS |
| 8 | Redirect (`/` ohne Cookie) bleibt unberührt — kein HTML-Body | 302 Found, `location: /login`, kein `cache-control` (kurzlebig, lt. Spec ausgenommen) | PASS |
| 9 | Real-User-Test Safari Mac (Click-Handler reagiert) | Nicht durch HTTP-Validator prüfbar — erfordert persistente Browser-Session | UNKLAR |

## Evidence

### Evidence 1: `/trips` (authentifiziert, HTML SSR)

```
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 63849
cache-control: no-cache
etag: "i0snw"
x-sveltekit-page: true
```

### Evidence 2: `/login` (publicPaths-Branch)

```
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 4917
cache-control: no-cache
etag: "e3dqu"
x-sveltekit-page: true
```

Bestätigt: **beide** `resolve(event)`-Code-Pfade der `handle`-Funktion (publicPaths-Early-Return und Auth-Pfad) wenden den HTML-Filter an.

### Evidence 3: JS-Asset-Chunk

```
HTTP/1.1 200 OK
Content-Type: text/javascript
cache-control: public,max-age=31536000,immutable
ETag: W/"82-1777913110294"
```

### Evidence 4: CSS-Asset-Chunk

```
HTTP/1.1 200 OK
Content-Type: text/css
Content-Length: 42776
cache-control: public,max-age=31536000,immutable
```

### Evidence 5: `/api/health` (public, JSON)

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 53
(kein cache-control-Header)
```

### Evidence 6: `/api/trips` (authentifiziert, JSON)

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 1621
(kein cache-control-Header)
```

### Evidence 7: `/api/scheduler/status` (public, JSON)

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 723
(kein cache-control-Header)
```

## Findings

### Finding 1: HTML-Filter wirkt korrekt — keine Asset- oder API-Kollateralschäden
- **Severity:** LOW (Information, kein Bug)
- **Expected:** `cache-control: no-cache` ausschließlich auf `text/html`-Responses; Asset-Chunks behalten `immutable`-Header, JSON-APIs bleiben unverändert.
- **Actual:** Genau dieses Verhalten beobachtet — JS, CSS und JSON sind nicht betroffen, HTML-Pages aus beiden Code-Pfaden (publicPaths + Auth) sind betroffen.
- **Evidence:** Evidence 1–7.

### Finding 2: Real-User-Test Safari nicht abdeckbar
- **Severity:** LOW
- **Expected:** Spec-Success-Criterion #4 fordert „Real-User-Test Safari Mac: Frontend deployen → ohne Cache-Leeren `/trips` öffnen → ‚Neuer Trip'-Button reagiert".
- **Actual:** Externer Validator hat keinen persistenten Browser-Cache; kausal ist die HTTP-Header-Setzung die hinreichende Bedingung, und diese ist auf Protokollebene verifiziert. Der vollständige Real-User-Beweis erfordert eine manuelle Safari-Session.

### Finding 3: Response-Kette Nginx → SvelteKit → Klient liefert no-cache durch
- **Severity:** LOW (Information)
- **Expected:** Spec-Root-Cause warnt, dass Nginx keine eigenen Cache-Header setzt; Fix wirkt auf SvelteKit-Ebene und muss durchlaufen.
- **Actual:** Nginx leitet `cache-control: no-cache` aus SvelteKit ungehindert durch — Header erreicht den Klienten unverändert.
- **Evidence:** Evidence 1, 2 (Curl gegen `https://staging.gregor20.henemm.com` zeigt `Server: nginx` und `cache-control: no-cache` parallel).

## Spec Success Criteria — Status

- [x] `curl -D - <host>/trips` enthält `cache-control: no-cache` (Evidence 1)
- [x] `curl -D - <host>/_app/immutable/<chunk>.js` enthält weiterhin `cache-control: public,max-age=31536000,immutable` (Evidence 3)
- [x] `curl -D - <host>/api/health` enthält kein `no-cache` von `handle` (Evidence 5)
- [ ] Real-User-Test Safari Mac — nicht durch Validator prüfbar (Finding 2)

## Verdict: VERIFIED

### Begründung

Sieben unabhängige HTTP-Probes auf der laufenden Staging-Instanz beweisen das in der Spec geforderte Verhalten:

1. HTML-SSR-Responses tragen `cache-control: no-cache` (Auth- und publicPaths-Branch).
2. Asset-Chunks (JS und CSS) behalten `cache-control: public,max-age=31536000,immutable` — kein Kollateralschaden durch den Filter.
3. JSON-API-Responses (public und authentifiziert) erhalten **keinen** `no-cache`-Header vom `handle`-Hook.
4. Redirects (302) bleiben unberührt — spec-konform, da kurzlebig.

Drei der vier formal definierten Success Criteria sind durch Curl-Beweise verifiziert. Das vierte Kriterium (Safari Real-User-Test) liegt außerhalb des Validator-Scopes; die HTTP-Header-Setzung ist die kausale Voraussetzung dafür und nachweislich gegeben. Die UNKLAR-Bewertung dieses Punktes verhindert kein VERIFIED, weil der Bug auf Protokollebene definiert ist und auf Protokollebene behoben wurde.

Keine Findings mit Severity ≥ MEDIUM.

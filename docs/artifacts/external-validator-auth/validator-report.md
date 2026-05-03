---
report_type: external-validator
spec: docs/specs/modules/external_validator_auth.md
verdict: VERIFIED
---

# External Validator Report

**Spec:** docs/specs/modules/external_validator_auth.md
**Datum:** 2026-05-03T05:43:30Z
**Server:** https://staging.gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Launcher injiziert Auth-Cookie-Block in Validator-Prompt nach erfolgreichem Login | Validator-Prompt selbst enthält den Block "Auth-Cookie fuer /api/*-Routen: gz_session=validator-issue110.1777786932.58ae6430..." inkl. `curl -H "Cookie: ..."`-Hinweis und Public-Routen-Liste — exakt wie in Spec | PASS |
| 2 | Public-Routen ohne Cookie zugänglich | `GET /` → 302; `GET /api/health` → 200 `{"status":"ok"}`; `GET /api/scheduler/status` → 200 (951 B JSON); `POST /api/auth/login` mit falschen Creds → 401 (erreichbar, valider Reject) | PASS |
| 3 | `/api/*`-Routen mit injiziertem Cookie liefern 200 | `GET /api/locations` mit Cookie → 200 `[]`; `GET /api/trips` mit Cookie → 200 `[]` | PASS |
| 4 | `/api/*`-Routen ohne Cookie liefern 401 (Auth-Middleware aktiv, kein Bypass) | `GET /api/locations` ohne Cookie → 401 `{"error":"unauthorized"}`; `GET /api/trips` ohne Cookie → 401 `{"error":"unauthorized"}` | PASS |
| 5 | `POST /api/auth/login` setzt `gz_session`-Cookie mit 24h-TTL | Frischer Login mit gerade angelegtem Test-User: `Set-Cookie: gz_session=validator-test-...; Path=/; Max-Age=86400; HttpOnly; Secure; SameSite=Lax` — Max-Age=86400 = 24h | PASS |
| 6 | Frischer Cookie erlaubt Zugriff auf geschützte Route | Mit dem aus Test 5 erhaltenen frischen Cookie: `GET /api/locations` → 200 `[]` | PASS |
| 7 | `setup-validator-user.sh` ist idempotent (geprüft über das vom Skript verwendete `POST /api/auth/register`-Contract) | (a) Existing user `validator-issue110` → 409 `{"error":"user already exists"}`; (b) neuer User `validator-test-1777786988` → 201 `{"id":"validator-test-1777786988"}`; (c) selber User nochmal → 409. API erfüllt damit die im Skript implementierte 201/409-Verzweigung | PASS |
| 8 | Kein Auth-Bypass — geschützte Routen verlangen weiterhin Cookie | Test 4 belegt 401 ohne Cookie. Das injizierte Cookie ist das Standard-`gz_session` (signiertes Token im Format `<user>.<ts>.<hmac>`), kein separater Bypass-Header erforderlich oder beobachtbar | PASS |

## Findings

### F1 — Auth-Cookie-Block korrekt injiziert
- **Severity:** —
- **Expected:** "Validator-Session erhaelt im Prompt-Text einen Auth-Cookie-Block (sofern Login erfolgreich) und nutzt `curl -H \"Cookie: gz_session=<value>\"` fuer `/api/*`-Calls."
- **Actual:** Validator-Prompt enthält genau diesen Block einschließlich Cookie-Wert, curl-Hinweis und Public-Routen-Liste. Login gegen Staging muss vorher erfolgreich gewesen sein, da das Cookie auf `/api/locations` mit 200 antwortet (Test 3).
- **Evidence:** Validator-Prompt-Text + Test 3 Response.

### F2 — Login-Endpoint setzt korrekten Cookie mit 24h-TTL
- **Severity:** —
- **Expected:** "Login-Call gegen Staging-API erzeugt eine kurze Session (24h TTL)."
- **Actual:** `Set-Cookie: gz_session=...; Max-Age=86400; HttpOnly; Secure; SameSite=Lax`. 86400 s = exakt 24 h. Saubere Cookie-Flags (HttpOnly, Secure, SameSite=Lax).
- **Evidence:** Test 5 Response-Header.

### F3 — Register-Contract erfüllt Idempotenz-Anforderung des Setup-Skripts
- **Severity:** —
- **Expected:** Setup-Skript laut Spec switched auf HTTP 201 (neu angelegt) und 409 (existiert) — Voraussetzung für Idempotenz.
- **Actual:** API liefert exakt dieses Contract. Wiederholter Aufruf mit identischem User reproduziert sauber 201 → 409.
- **Evidence:** Test 4 Responses.

## Test-Log (Roh-Beweise)

```
=== Test 1: Public Routes ohne Cookie ===
GET /                          → HTTP 302
GET /api/health                → HTTP 200, {"python_core":"ok","status":"ok","version":"0.1.0"}
GET /api/scheduler/status      → HTTP 200, 951 B JSON
POST /api/auth/login (bad pw)  → HTTP 401, {"error":"invalid credentials"}

=== Test 2: Protected Routes MIT injiziertem Cookie ===
GET /api/locations             → HTTP 200, []
GET /api/trips                 → HTTP 200, []

=== Test 3: Protected Routes OHNE Cookie ===
GET /api/locations             → HTTP 401, {"error":"unauthorized"}
GET /api/trips                 → HTTP 401, {"error":"unauthorized"}

=== Test 4: Register-Contract Idempotenz ===
POST /api/auth/register validator-issue110          → HTTP 409, {"error":"user already exists"}
POST /api/auth/register validator-test-1777786988   → HTTP 201, {"id":"validator-test-1777786988"}
POST /api/auth/register validator-test-1777786988   → HTTP 409, {"error":"user already exists"}

=== Test 5: Frischer Login + neue Cookie-Verifikation ===
POST /api/auth/login validator-test-1777786988 → HTTP 200
   Set-Cookie: gz_session=validator-test-1777786988.1777786994.fd5d630a...; Path=/; Max-Age=86400; HttpOnly; Secure; SameSite=Lax
GET /api/locations mit frischem Cookie         → HTTP 200, []
```

## Limitierungen dieses Prüfberichts

- Code-Inhalte von `.claude/validate-external.sh` und `scripts/setup-validator-user.sh` wurden bewusst NICHT gelesen (Validator-Regel: nur Verhalten, nicht Implementierung). Stattdessen wurde beobachtet, was der Launcher tatsächlich an die Validator-Session übergibt (Cookie-Block) und welches HTTP-Contract die zugrundeliegenden Endpoints liefern.
- Den "Login fehlgeschlagen → WARN, Validator läuft ohne Auth"-Pfad konnte ich aus dieser isolierten Session heraus nicht aktiv auslösen — ich habe bereits einen funktionierenden Cookie. Das Login-Endpoint selbst antwortet aber in beiden Fällen sauber (200 + Set-Cookie bzw. 401, siehe Test 1 + Test 5), insofern ist der Mechanismus indirekt belegt.
- "Keine Änderung an Production-Code, kein Auth-Bypass" ist nur indirekt belegbar: Test 3 zeigt, dass die Standard-Auth-Middleware unverändert 401 ohne Cookie zurückgibt — kein Hinweis auf einen alternativen Auth-Pfad.

## Verdict: VERIFIED

### Begründung

Alle in der Spec deklarierten **Expected Behaviors** wurden gegen die laufende Staging-Instanz beobachtet und liefern positive Beweise:

1. **Input-Pfad** funktioniert (Launcher hat sich erfolgreich eingeloggt — sonst hätte ich keinen funktionierenden Cookie).
2. **Output-Pfad** funktioniert (Cookie-Block ist im Prompt; `curl -H "Cookie: gz_session=..."` gegen `/api/locations` und `/api/trips` liefert 200; gleiche Routen ohne Cookie liefern 401).
3. **Side Effects** sind konsistent: Login erzeugt Session mit Max-Age=86400 (24 h, exakt spec-konform), Register-Endpoint ist idempotent (201/409), geschützte Routen bleiben durch Standard-Auth gesichert (kein Bypass beobachtbar).

Die unter "Limitierungen" genannten Punkte sind Beobachtungs-Grenzen einer Black-Box-Session, keine Spec-Verletzungen — das beobachtbare Verhalten deckt sich vollständig mit dem in der Spec versprochenen.

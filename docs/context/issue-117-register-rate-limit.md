# Issue #117 — Rate-Limit für /api/auth/register

## Symptom

`/api/auth/register` ist explizit von `AuthMiddleware` ausgenommen (`cmd/server/main.go:54`) und hat keinen Rate-Limit. Folge: Account-Spam möglich. Aktueller Storage zeigt 500+ User-Verzeichnisse, davon ~99% mit Präfix `test_*` (E2E-Reste).

## Geschäftsentscheidung

Registration bleibt offen für jeden (User-Entscheid). Schutz erfolgt ausschließlich über Rate-Limit.

## Root Cause

`cmd/server/main.go:54`:
```go
r.Post("/api/auth/register", handler.RegisterHandler(s, bcrypt.DefaultCost))
```

Keine Middleware um den Handler. Die globale `AuthMiddleware` greift nicht (wäre auch Unsinn — Anmeldung ohne Auth). Es fehlt eine spezifische Rate-Limit-Schicht.

## Affected Files

| Datei | Änderung |
|---|---|
| `internal/middleware/ratelimit.go` (neu) | IP-basiertes Token-Bucket (`golang.org/x/time/rate`), pro IP eigener Limiter mit Cleanup, Header `Retry-After` bei 429 |
| `internal/middleware/ratelimit_test.go` (neu) | Tests: 5 erlaubt, 6. blockt, andere IP unabhängig |
| `cmd/server/main.go` (Zeile 54) | `r.Post("/api/auth/register", middleware.RateLimit(...)(handler.RegisterHandler(s, bcrypt.DefaultCost)))` |
| `go.mod` / `go.sum` | Neue Dependency `golang.org/x/time` |

## Konfiguration

- Limit: **5 Registrierungen / IP / Stunde** (Token-Bucket: rate=5/3600s, burst=5)
- IP-Erkennung: `X-Real-IP` (Nginx setzt das), Fallback `RemoteAddr` ohne Port
- Storage: in-memory `map[string]*rate.Limiter`, Mutex-geschützt
- Cleanup: stale Limiter (>1h ungenutzt) per Background-Goroutine alle 10 Min entfernen, sonst Memory-Leak

## Risiko-Analyse

- **Restart resettet Limiter:** Akzeptiert. Spam-Wert pro Restart ist gering (5 weitere Versuche), Bot-Aufwand höher als Nutzen.
- **Hinter Nginx läuft alles über `X-Real-IP`:** Direkter Zugriff auf den Backend-Port ist seit Issue #116 nicht mehr möglich → keine Bypass-Möglichkeit.
- **Echte Wanderer-Registrierung trifft das Limit nicht:** 5/Stunde/IP ist großzügig genug.

## Test-Strategie

Unit-Tests in `ratelimit_test.go` (echte Library, kein Mock):
- `TestRateLimit_AllowsBurst` — 5 Requests aus gleicher IP gehen durch
- `TestRateLimit_BlocksSixth` — 6. Request → HTTP 429
- `TestRateLimit_DifferentIPsIndependent` — 5 IP-A + 5 IP-B beide OK
- `TestRateLimit_PrefersXRealIP` — Header dominiert über RemoteAddr

Integration über Production-Verifikation:
```bash
for i in {1..7}; do
  curl -s -o /dev/null -w "Try $i: %{http_code}\n" \
    -X POST -H "Content-Type: application/json" \
    -d "{\"username\":\"ratelimit_test_$i\",\"password\":\"testpassword123\"}" \
    https://gregor20.henemm.com/api/auth/register
done
# Erwartung: Try 1-5: 201/409 (created/exists), Try 6-7: 429
```

Cleanup nach Test: Test-User wieder löschen.

## Scope

4 Dateien (1 neu, 1 Test neu, 1 Code-Änderung 1 Zeile, go.mod). ~120 LoC. Klein bis mittel.

## Bezug

- GitHub Issue: henemm/gregor_zwanzig#117
- Security Findings: henemm-security#64 (medium, CVSS 5.3), Sammelreport #14400
- Folge-Idee (separat): 500+ test_* User-Verzeichnisse aufräumen

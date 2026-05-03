---
entity_id: register_rate_limit
type: bugfix
created: 2026-05-03
updated: 2026-05-03
status: draft
version: "1.0"
tags: [security, bugfix, go-api, rate-limit, auth, issue-117]
---

# Rate-Limit für /api/auth/register

## Approval

- [ ] Approved

## Purpose

Behebt eine Security-Lücke (medium, CVSS 5.3, henemm-security#64), bei der `/api/auth/register` öffentlich und ohne Rate-Limit erreichbar ist. Folge: Account-Spam ist trivial möglich — der aktuelle Storage zeigt 500+ User-Verzeichnisse, von denen ~99% das Präfix `test_*` tragen (Reste aus E2E-Läufen, die diesen Endpoint missbraucht haben). Geschäftsentscheidung des Users: Registration bleibt OFFEN für jeden, Schutz erfolgt ausschließlich über ein IP-basiertes Rate-Limit. Der Fix fügt eine neue Middleware (`internal/middleware/ratelimit.go`) hinzu, die mittels Token-Bucket pro IP 5 Registrierungen pro Stunde erlaubt und den 6. Versuch mit HTTP 429 + `Retry-After`-Header ablehnt.

## Source

- **File:** `cmd/server/main.go`
- **Identifier:** Zeile 54 — `r.Post("/api/auth/register", handler.RegisterHandler(s, bcrypt.DefaultCost))`
- **New File:** `internal/middleware/ratelimit.go` — `IPRateLimiter` Struct + `Middleware()` HTTP-Wrapper
- **New Test File:** `internal/middleware/ratelimit_test.go`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `golang.org/x/time/rate` | External Library (neue Dependency) | Liefert `rate.Limiter` (Token-Bucket-Implementierung) |
| `net/http` | Stdlib | HTTP-Middleware-Pattern (`http.Handler`) |
| `sync` | Stdlib | `sync.Mutex` für Map-Zugriff auf `map[string]*rate.Limiter` |
| `time` | Stdlib | Cleanup-Goroutine, `Retry-After`-Berechnung |
| `handler.RegisterHandler` (`internal/handler/auth.go`) | HTTP-Handler | Wird gewrappt — Signatur unverändert |
| Nginx-Proxy (`gregor20.henemm.com.conf`) | Infra | Setzt `X-Real-IP`-Header mit Client-IP; einziger Eingangspfad seit Issue #116 |

## Root Cause Analysis

### Aktueller Zustand (BROKEN)

`cmd/server/main.go:54`:

```go
r.Post("/api/auth/register", handler.RegisterHandler(s, bcrypt.DefaultCost))
```

Der Endpoint ist explizit von `AuthMiddleware` ausgenommen (zwingend — Anmeldung ohne Auth) und steht ohne weitere Schutzschicht offen. Es gibt keine Rate-Limit-Middleware im Projekt.

Belegter Schaden:

```
$ ls data/users/ | wc -l
500+

$ ls data/users/ | grep -c '^test_'
~495
```

Diese Verzeichnisse sind keine echten User, sondern Reste aus E2E-Läufen, die `/api/auth/register` ungebremst beanspruchen.

### Sicherheits-Implikation

- Account-Spam: beliebig viele Registrierungen pro Sekunde möglich
- Storage-Wachstum unkontrolliert (User-Dirs + bcrypt-Hashing-Last)
- Klassifiziert als medium / CVSS 5.3 (henemm-security#64)
- Direkter Bypass über Backend-Port seit Issue #116 nicht mehr möglich → einzige Eintrittsstelle ist Nginx, der `X-Real-IP` korrekt setzt

## Implementation Strategy

### 1. `internal/middleware/ratelimit.go` — Neue Middleware

```go
package middleware

import (
    "encoding/json"
    "fmt"
    "net"
    "net/http"
    "strconv"
    "sync"
    "time"

    "golang.org/x/time/rate"
)

type IPRateLimiter struct {
    mu       sync.Mutex
    limiters map[string]*entry
    rate     rate.Limit
    burst    int
    window   time.Duration
}

type entry struct {
    limiter  *rate.Limiter
    lastSeen time.Time
}

// NewIPRateLimiter: 5/Stunde => rate.Every(window/n), burst=n.
func NewIPRateLimiter(n int, window time.Duration) *IPRateLimiter {
    rl := &IPRateLimiter{
        limiters: make(map[string]*entry),
        rate:     rate.Every(window / time.Duration(n)),
        burst:    n,
        window:   window,
    }
    go rl.cleanupLoop()
    return rl
}

func (rl *IPRateLimiter) get(ip string) *rate.Limiter {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    e, ok := rl.limiters[ip]
    if !ok {
        e = &entry{limiter: rate.NewLimiter(rl.rate, rl.burst)}
        rl.limiters[ip] = e
    }
    e.lastSeen = time.Now()
    return e.limiter
}

func (rl *IPRateLimiter) cleanupLoop() {
    t := time.NewTicker(10 * time.Minute)
    defer t.Stop()
    for range t.C {
        cutoff := time.Now().Add(-rl.window)
        rl.mu.Lock()
        for ip, e := range rl.limiters {
            if e.lastSeen.Before(cutoff) {
                delete(rl.limiters, ip)
            }
        }
        rl.mu.Unlock()
    }
}

func (rl *IPRateLimiter) Middleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ip := clientIP(r)
        lim := rl.get(ip)
        if !lim.Allow() {
            retry := int(rl.window.Seconds() / float64(rl.burst))
            w.Header().Set("Content-Type", "application/json")
            w.Header().Set("Retry-After", strconv.Itoa(retry))
            w.WriteHeader(http.StatusTooManyRequests)
            json.NewEncoder(w).Encode(map[string]string{"error": "rate_limit_exceeded"})
            return
        }
        next.ServeHTTP(w, r)
    })
}

func clientIP(r *http.Request) string {
    if v := r.Header.Get("X-Real-IP"); v != "" {
        return v
    }
    host, _, err := net.SplitHostPort(r.RemoteAddr)
    if err != nil {
        return r.RemoteAddr
    }
    return host
}

```

### 2. `cmd/server/main.go:54` — Wrap des Register-Endpoints

Vorher:

```go
r.Post("/api/auth/register", handler.RegisterHandler(s, bcrypt.DefaultCost))
```

Nachher:

```go
registerLimiter := authmw.NewIPRateLimiter(5, time.Hour)
r.Post("/api/auth/register",
    registerLimiter.Middleware(handler.RegisterHandler(s, bcrypt.DefaultCost)).ServeHTTP,
)
```

(Anpassung an die `chi`-Router-Signatur: `Post` erwartet `http.HandlerFunc` — `Middleware()` liefert `http.Handler`, der per `.ServeHTTP` als HandlerFunc gebunden wird.)

### 3. `internal/middleware/ratelimit_test.go` — Unit-Tests

Echte Library, kein Mock. Vier Tests:

**Wichtig:** Tests dürfen NICHT `time.Hour` als Window verwenden, sonst dauert der Suite >1h. Der Constructor `NewIPRateLimiter(burst int, window time.Duration)` muss das Window als Parameter nehmen, damit Tests mit z.B. `100*time.Millisecond` arbeiten können. In Production wird `time.Hour` übergeben.

```go
func TestIPRateLimiter_AllowsBurst(t *testing.T) {
    // limiter := NewIPRateLimiter(5, 100*time.Millisecond)
    // 5 Requests aus IP 1.2.3.4 → alle 200
}

func TestIPRateLimiter_BlocksSixth(t *testing.T) {
    // limiter := NewIPRateLimiter(5, 100*time.Millisecond)
    // Request 1-5: 200, Request 6: 429 + Retry-After-Header gesetzt
}

func TestIPRateLimiter_DifferentIPsIndependent(t *testing.T) {
    // 5x IP A + 5x IP B → alle 10 erlaubt
}

func TestIPRateLimiter_PrefersXRealIP(t *testing.T) {
    // X-Real-IP=9.9.9.9 dominiert über RemoteAddr=1.1.1.1:5000
    // Beide Header-Varianten zählen unterschiedliche Buckets
}
```

### 4. Dependency

```bash
go get golang.org/x/time/rate
go mod tidy
```

`golang.org/x/time` ist Teil des offiziellen Go-`x`-Repos (kein Drittanbieter, stabile API).

## Expected Behavior

### Vor Fix (BROKEN)

- **Input:** `for i in {1..1000}; do curl -X POST .../api/auth/register -d '{...}'; done`
- **Output:** Bis zu 1000 erfolgreiche 201-Registrierungen
- **Side effects:** 1000 neue User-Verzeichnisse, unkontrolliertes Storage-Wachstum

### Nach Fix (GREEN)

- **Input (1.-5. Versuch, gleiche IP, < 1h):** Standard-RegisterHandler-Antworten (201 created, 409 exists, 400 validation)
- **Output:** Handler-Logik unverändert
- **Input (6. Versuch, gleiche IP, < 1h):** `POST /api/auth/register`
- **Output:** HTTP 429, Header `Retry-After: 720` (3600/5), Body `{"error":"rate_limit_exceeded"}`
- **Input (anderer IP, 1.-5. Versuch):** Wieder 5 erlaubt — pro IP unabhängig
- **Side effects:** Andere Auth-Endpoints (`/api/auth/login`, `/forgot-password`, `/reset-password`) bleiben **unverändert** ohne Rate-Limit (bewusst out-of-scope)

## Acceptance Criteria

- [ ] Vor Fix reproduzierbar: 1000 POSTs gegen `/api/auth/register` aus gleicher IP — alle 1000 antworten 201/409 (kein 429)
- [ ] Nach Fix: 5 POSTs gegen `/api/auth/register` aus gleicher IP innerhalb 1h — alle 5 antworten 201/409 je nach Username-Zustand
- [ ] Nach Fix: 6. POST aus gleicher IP innerhalb 1h → HTTP 429 mit Header `Retry-After`, Body `{"error":"rate_limit_exceeded"}`
- [ ] Nach Fix: Parallel ein POST mit anderem `X-Real-IP`-Header → wieder erlaubt (eigenständiger Bucket)
- [ ] Nach Fix: `POST /api/auth/login` bleibt ohne Rate-Limit (kein 429 nach 6 Versuchen)
- [ ] Nach Fix: Alle bestehenden Auth-Handler-Tests in `internal/handler/...` weiterhin grün
- [ ] Unit-Test `TestIPRateLimiter_AllowsBurst` grün
- [ ] Unit-Test `TestIPRateLimiter_BlocksSixth` grün
- [ ] Unit-Test `TestIPRateLimiter_DifferentIPsIndependent` grün
- [ ] Unit-Test `TestIPRateLimiter_PrefersXRealIP` grün
- [ ] Production-Verifikation gegen `https://gregor20.henemm.com/api/auth/register` (Bash-Loop aus Issue-Kontext) zeigt Try 1-5: 201/409, Try 6-7: 429
- [ ] Test-User (`ratelimit_test_*`) nach Verifikation wieder gelöscht

## Files to Modify

| Datei | Änderung | LoC |
|---|---|---|
| `internal/middleware/ratelimit.go` (neu) | `IPRateLimiter` Struct, `NewIPRateLimiter`, `Middleware`, `clientIP`, `cleanupLoop` | ~80 |
| `internal/middleware/ratelimit_test.go` (neu) | 4 Unit-Tests (siehe oben) | ~100 |
| `cmd/server/main.go` (Zeile 54) | Wrap mit `registerLimiter.Middleware(...)` + Limiter-Konstruktion | ~3 |
| `go.mod` / `go.sum` | Neue Dependency `golang.org/x/time` | auto |

Gesamt: 4 Dateien (2 neu, 1 Code-Änderung, 1 Module-Update). ~185 LoC.

## Risk Analysis

- **Restart resettet Limiter:** Akzeptiert. Spam-Wert pro Restart liegt bei 5 weiteren Versuchen pro IP — Bot-Aufwand bleibt höher als Nutzen, und Restarts sind nicht angreifergesteuert.
- **Header-Spoofing über `X-Real-IP`:** Seit Issue #116 ist der Backend-Port ausschließlich via `127.0.0.1` erreichbar. Nginx ist der einzige Eingang und überschreibt eingehende `X-Real-IP`-Header zuverlässig mit der echten Client-IP. Kein realistischer Bypass.
- **Memory-Leak:** Cleanup-Goroutine entfernt alle 10 Min Limiter, die >1h ungenutzt sind. Bei Worst-Case 1000 IPs/h bleibt der Speicherverbrauch deutlich unter 1 MB.
- **Echte Wanderer-Registrierung:** 5/Stunde/IP liegt weit über jedem realistischen Familien-/Hütten-WLAN-Bedarf.

## Bewusst NICHT im Scope

- Rate-Limits für `/api/auth/login`, `/api/auth/forgot-password`, `/api/auth/reset-password` (eigene Folge-Stories falls gewünscht)
- Captcha (würde Geschäftsentscheidung "Registration bleibt offen" widersprechen)
- Persistenter Limiter-State über Restarts hinweg (z. B. Redis) — nicht nötig, siehe Risiko-Analyse
- Cleanup der bestehenden 500+ `test_*`-Verzeichnisse (eigene Story / Maintenance-Job)

## Known Limitations

- Limiter-State ist prozesslokal: Bei künftigem Multi-Instanz-Deployment wäre ein gemeinsamer Backend-Store nötig. Aktuell läuft die Go-API als Single-Instanz (Systemd, Prod + Staging je 1 Prozess), kein Problem.
- IPv4 + IPv6 werden als unterschiedliche Buckets behandelt (jede Variante eigene `X-Real-IP`-Repräsentation). In der Praxis irrelevant: Nginx setzt pro Verbindung genau eine Repräsentation.
- Kein Logging der 429-Events. Falls künftig ein Audit-Trail gewünscht ist, kann ein einfaches `log.Printf` in der Middleware ergänzt werden.

## Bezug

- GitHub Issue: [henemm/gregor_zwanzig#117](https://github.com/henemm/gregor_zwanzig/issues/117)
- Security Findings: henemm-security#64 (medium, CVSS 5.3), Sammelreport #14400
- Voraussetzung-Fix: Issue #116 (Backend bind auf `127.0.0.1`) — verhindert Bypass über direkte Header-Manipulation
- Folge-Idee (separat): 500+ `test_*` User-Verzeichnisse aufräumen

## Changelog

- 2026-05-03: Initial spec created based on Issue #117 analysis

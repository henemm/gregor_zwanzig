---
entity_id: fix_1219_verify_flow_2a_ii
type: feature
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [mail, security, resend, verification, double-opt-in]
workflow: 1219-verify-flow-2a-ii
---

<!-- Issue #1219, Scheibe 2a-ii — Einlösung des E-Mail-Bestätigungslinks (Double-Opt-In Backend) -->

# Fix #1219 (Scheibe 2a-ii) — Einlösung des E-Mail-Bestätigungslinks

## Approval

- [x] Approved (PO 'go' 2026-07-11 — ACs 1–8 auf Deutsch freigegeben)

## Purpose

Scheibe 2a-i (live, `e677b23e`) baut den **Versand-Pfad**: Eine
Adressänderung erzeugt einen 24h-gültigen Verifikations-Token unter
`data/users/<id>/email_verification.json` und schickt eine Bestätigungsmail
mit einem Link auf `{publicHost}/verify-email?user=<id>&token=<t>`. Bis jetzt
läuft ein Klick auf diesen Link ins Leere — es gibt keinen Endpoint, der den
Token entgegennimmt. Diese Scheibe baut den **Einlöse-Pfad**: einen
öffentlichen `VerifyEmailHandler` (POST), der den mitgeschickten Token gegen
den gespeicherten Hash prüft, bei Erfolg `email_verified_at` per
Read-Modify-Write auf den Einlöse-Zeitpunkt setzt und den Token entwertet.
Erst damit ist der Self-Service-Double-Opt-In backend-seitig vollständig: Ein
Nutzer kann eine geänderte Empfänger-Adresse eigenständig verifizieren und
damit für den Resend-Versand (Scheibe 1) freischalten — ohne
Migrationsscript. Die klickbare Frontend-Bestätigungsseite bleibt Scheibe 2b.

## Source

- **File:** `internal/handler/auth.go` — NEU: `func VerifyEmailHandler(s
  *store.Store) http.HandlerFunc`, strukturelles Vorbild `ResetPasswordHandler`
  @272-339. Public (kein Auth-Kontext), `userId`+`token` aus dem
  JSON-Request-Body. Ablauf: Body dekodieren → `LoadVerificationToken(userId)`
  (nil/err → `400 invalid token`) → `time.Now().After(ExpiresAt)` (→
  `400 token expired`) → `bcrypt.CompareHashAndPassword(TokenHash, token)` (→
  `400 invalid token`) → `LoadUser(userId)` → `EmailVerifiedAt = &now` (RMW) →
  `SaveUser(*user)` → `DeleteVerificationToken(userId)` →
  `{"status":"ok"}` (Go-API, `internal/`).
- **File:** `internal/middleware/auth.go` @34-46 — Public-Route-Allowlist:
  `r.URL.Path == "/api/auth/verify-email"` ergänzen (analog
  `/api/auth/reset-password`), sonst 401 vor dem Handler (Go-API,
  `internal/`).
- **File:** `internal/router/router.go` @56-59 — NEU: eigener
  `verifyLimiter := authmw.NewIPRateLimiter(10, time.Hour)` +
  `r.Post("/api/auth/verify-email",
  verifyLimiter.Middleware(handler.VerifyEmailHandler(deps.Store)).ServeHTTP)`,
  identisches Muster zur Reset-Route (Go-API, `internal/`).

> **Schicht-Hinweis:** Reines Go (`internal/handler`, `internal/middleware`,
> `internal/router`). Kein Python, kein Frontend. Alle konsumierten
> Store-/Model-Bausteine (`EmailVerificationToken`,
> `LoadVerificationToken`/`DeleteVerificationToken`) existieren bereits aus
> Scheibe 2a-i.

## Estimated Scope

- **LoC:** ~+55 / -0
- **Files:** 3 (`internal/handler/auth.go` MODIFY, `internal/middleware/auth.go`
  MODIFY, `internal/router/router.go` MODIFY) plus zugehörige Go-Testdatei
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `handler.ResetPasswordHandler` (`internal/handler/auth.go:272-339`) | function | Strukturelles Vorbild: Token laden → Ablauf → bcrypt-Vergleich → User-RMW → Token löschen |
| `store.LoadVerificationToken`/`DeleteVerificationToken` (`internal/store/user.go:145,161`) | function | Token laden/entwerten (existiert aus 2a-i) |
| `store.LoadUser`/`SaveUser` | function | RMW auf `EmailVerifiedAt` (vollständiges Objekt laden, nur ein Feld setzen) |
| `model.EmailVerificationToken` (`internal/model/user.go:42`) | struct | `TokenHash`/`ExpiresAt` (existiert aus 2a-i) |
| `model.User.EmailVerifiedAt` (`internal/model/user.go:32`) | field | Zielfeld, Eignungskriterium der Resend-Allowlist (Scheibe 1) |
| `middleware.AuthMiddleware` (`internal/middleware/auth.go:31-46`) | function | Public-Allowlist um `/api/auth/verify-email` erweitern |
| `middleware.NewIPRateLimiter` (`internal/middleware/ratelimit.go:33`) | function | Rate-Limiter für den öffentlichen Endpoint |
| `router.New` (`internal/router/router.go`) | function | Route registrieren |

## Implementation Details

### 1. `VerifyEmailHandler` (`internal/handler/auth.go`)

Neuer Handler direkt nach `ResetPasswordHandler`. Signatur
`func VerifyEmailHandler(s *store.Store) http.HandlerFunc` (kein `bcryptCost`
nötig — es wird nur verglichen, nicht neu gehasht).

```go
func VerifyEmailHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        var req struct {
            User  string `json:"user"`
            Token string `json:"token"`
        }
        w.Header().Set("Content-Type", "application/json")
        if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.User == "" || req.Token == "" {
            w.WriteHeader(400); w.Write([]byte(`{"error":"invalid request"}`)); return
        }

        vt, err := s.LoadVerificationToken(req.User)
        if err != nil || vt == nil {
            w.WriteHeader(400); w.Write([]byte(`{"error":"invalid token"}`)); return
        }
        if time.Now().After(vt.ExpiresAt) {
            w.WriteHeader(400); w.Write([]byte(`{"error":"token expired"}`)); return
        }
        if err := bcrypt.CompareHashAndPassword([]byte(vt.TokenHash), []byte(req.Token)); err != nil {
            w.WriteHeader(400); w.Write([]byte(`{"error":"invalid token"}`)); return
        }

        user, err := s.LoadUser(req.User)   // RMW: vollständiges Objekt
        if err != nil || user == nil {
            w.WriteHeader(400); w.Write([]byte(`{"error":"invalid token"}`)); return
        }
        now := time.Now().UTC()
        user.EmailVerifiedAt = &now
        if err := s.SaveUser(*user); err != nil {
            w.WriteHeader(500); w.Write([]byte(`{"error":"store_error"}`)); return
        }
        s.DeleteVerificationToken(req.User)
        w.Write([]byte(`{"status":"ok"}`))
    }
}
```

Fehler-Profil bewusst identisch zu Reset: fehlender/abgelaufener/falscher
Token liefert einheitlich `400` ohne preiszugeben, ob der Nutzer existiert.
Der Token wird NUR bei erfolgreicher Verifikation gelöscht — ein `400`
(z.B. abgelaufen) lässt den Store-Zustand unverändert.

### 2. Public-Route-Allowlist (`internal/middleware/auth.go`)

In der Pfad-Bedingung @34-46 einen Zweig ergänzen:
`r.URL.Path == "/api/auth/verify-email"`, direkt neben
`"/api/auth/reset-password"`. Ohne diesen Eintrag würde `AuthMiddleware` den
Request mit 401 abweisen, bevor der Handler läuft — ein aus der Mail heraus
klickender, nicht eingeloggter Nutzer käme nie durch.

### 3. Route + Rate-Limiter (`internal/router/router.go`)

Nach dem Reset-Block (@56-59):

```go
verifyLimiter := authmw.NewIPRateLimiter(10, time.Hour)
r.Post("/api/auth/verify-email",
    verifyLimiter.Middleware(handler.VerifyEmailHandler(deps.Store)).ServeHTTP,
)
```

Eigener Limiter (nicht der Reset-Limiter mitbenutzen) — dieselbe Politik
`(10, time.Hour)` wie beim Reset-Einlösen: großzügig genug für legitime
Retries, eng genug gegen Token-Rateversuche.

## Expected Behavior

- **Input:** `POST /api/auth/verify-email` (public, kein Cookie nötig),
  Body `{"user": "<userId>", "token": "<klartext-token>"}`.
- **Output (Erfolg):** `200 {"status":"ok"}`; `email_verified_at` des
  Nutzers ist auf den Einlöse-Zeitpunkt gesetzt (RMW, alle anderen Felder
  unverändert); die Token-Datei `email_verification.json` ist gelöscht.
- **Output (Fehler):** `400` mit `{"error":"invalid token"}` (fehlend/falsch),
  `{"error":"token expired"}` (abgelaufen) oder `{"error":"invalid request"}`
  (leerer Body/Feld); `500 {"error":"store_error"}` bei Speicherfehler. In
  allen Fehlerfällen bleibt `email_verified_at` unverändert und der Token
  wird NICHT gelöscht.
- **Side effects:** Nach erfolgreicher Verifikation speist sich die
  Resend-Allowlist (Scheibe 1) automatisch aus dem gesetzten
  `email_verified_at` — die Adresse ist ab sofort für den Produktivversand
  freigeschaltet.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit einem gültigen (nicht abgelaufenen)
  Verifikations-Token unter `data/users/<userId>/email_verification.json` /
  When er `POST /api/auth/verify-email` mit `{user: <userId>, token:
  <klartext>}` aufruft / Then antwortet der Endpoint `200 {"status":"ok"}`,
  `email_verified_at` des Nutzers ist auf einen Zeitpunkt „jetzt" gesetzt
  (vorher leer) und die Token-Datei ist gelöscht.
  - Test: Token via `SaveVerificationToken` mit bekanntem Klartext-Hash und
    `ExpiresAt = now+24h` anlegen, User mit `EmailVerifiedAt=nil` anlegen,
    POST absetzen, danach `LoadUser` prüfen (`EmailVerifiedAt != nil`, nahe
    `now`) und `LoadVerificationToken` prüfen (nil).

- **AC-2:** Given ein Nutzer mit einem abgelaufenen Verifikations-Token
  (`ExpiresAt` in der Vergangenheit) / When er den Endpoint mit dem korrekten
  Klartext-Token aufruft / Then antwortet der Endpoint `400 token expired`,
  `email_verified_at` bleibt leer und der Token wird NICHT gelöscht.
  - Test: Token mit `ExpiresAt = now-1m` anlegen, POST, Status 400,
    `LoadUser.EmailVerifiedAt == nil`, `LoadVerificationToken != nil`.

- **AC-3:** Given ein Nutzer mit gültigem Token / When er den Endpoint mit
  einem FALSCHEN Klartext-Token aufruft / Then antwortet der Endpoint
  `400 invalid token`, `email_verified_at` bleibt leer und der Token wird
  NICHT gelöscht (kein Verbrauch durch Fehlversuch).
  - Test: Token anlegen, POST mit `token="falsch"`, Status 400,
    `EmailVerifiedAt == nil`, Token weiterhin vorhanden.

- **AC-4:** Given es existiert KEIN Verifikations-Token für den angegebenen
  `user` (nie erzeugt oder bereits eingelöst) / When der Endpoint aufgerufen
  wird / Then antwortet er `400 invalid token` (keine Preisgabe, ob der
  Nutzer existiert), ohne Zustandsänderung.
  - Test: Ohne vorherigen `SaveVerificationToken` POST absetzen, Status 400.

- **AC-5:** Given Nutzer A besitzt einen gültigen Token und Nutzer B besitzt
  KEINEN (oder einen anderen) Token / When As Klartext-Token mit `user: B`
  eingereicht wird / Then wird B NICHT verifiziert — der bcrypt-Vergleich
  läuft gegen Bs Store (nil/anderer Hash) und liefert `400`; Bs
  `email_verified_at` bleibt leer, As Token bleibt unangetastet.
  - Test: Für A Token `T` anlegen, POST mit `{user: B, token: T}`, Status
    400, `LoadUser(B).EmailVerifiedAt == nil`, `LoadVerificationToken(A) !=
    nil`.

- **AC-6:** Given ein erfolgreich eingelöster Token (AC-1 gelaufen) / When
  derselbe Link/Token ein zweites Mal eingereicht wird / Then antwortet der
  Endpoint `400 invalid token` (der Token wurde bei der ersten Einlösung
  gelöscht — kein Replay).
  - Test: AC-1-POST erfolgreich, denselben POST erneut absetzen, Status 400.

- **AC-7:** Given der Endpoint `/api/auth/verify-email` / When ein
  NICHT-eingeloggter Client (ohne `gz_session`-Cookie) ihn aufruft / Then
  wird der Request von `AuthMiddleware` durchgelassen (Public-Allowlist) und
  erreicht den Handler — der Aufruf endet NICHT mit `401 unauthorized`.
  - Test: Request ohne Cookie durch die `AuthMiddleware`-Kette gegen die
    registrierte Route schicken, prüfen dass der Statuscode aus dem Handler
    stammt (200/400), nicht 401.

- **AC-8:** Given ein leerer Body oder ein Request ohne `user`/`token` / When
  der Endpoint aufgerufen wird / Then antwortet er `400 invalid request`,
  ohne Store-Zugriff/Zustandsänderung.
  - Test: POST mit `{}` bzw. fehlendem Feld, Status 400.

## Known Limitations

- Diese Scheibe baut nur den Backend-Einlöse-Endpoint. Die klickbare
  Frontend-Bestätigungsseite unter `/verify-email` (die den POST auslöst und
  Erfolg/Fehler anzeigt) folgt in Scheibe 2b — bis dahin ist der Endpoint per
  `curl`/Test triggerbar, aber es gibt keine UI, die den Nutzer durch den
  Klick führt.
- Der Endpoint prüft NICHT, ob die im Profil hinterlegte Adresse seit
  Token-Erzeugung erneut geändert wurde. Eine zwischenzeitliche
  Adressänderung erzeugt jedoch (Scheibe 2a-i) einen neuen Token und
  überschreibt den alten Hash → ein alter Link matcht dann nicht mehr
  (`400 invalid token`). Es wird also implizit immer die zuletzt gesetzte
  Adresse verifiziert.
- Kein separater „Token-Resend"-Endpoint — einen neuen Token bekommt der
  Nutzer nur über eine (No-Op-freie) erneute Adressänderung (Scheibe 2a-i).
  Konsistent mit dem Passwort-Reset-Muster.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Strukturell identischer Zwilling des bestehenden
  Passwort-Reset-Einlöse-Handlers (`ResetPasswordHandler`) auf dem in
  Scheibe 2a-i angelegten Token-Typ/-Store. Kein neuer Architekturbaustein,
  keine neue Technologieentscheidung, keine Persistenz-Schema-Änderung.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1219 Scheibe 2a-ii, PO-Entscheidung 2026-07-10 (POST statt GET-Auto-Confirm)

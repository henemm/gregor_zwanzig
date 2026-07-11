---
entity_id: fix_1219_verify_flow_2a
type: feature
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [mail, security, resend, verification, double-opt-in]
workflow: 1219-verify-flow-2a
---

<!-- Issue #1219, Scheibe 2a-i — Versand des E-Mail-Bestätigungslinks (Double-Opt-In Backend) -->

# Fix #1219 (Scheibe 2a-i) — Versand des E-Mail-Bestätigungslinks

## Approval

- [ ] Approved

## Purpose

Scheibe 1 (live) hat `email_verified_at` als striktes Eignungskriterium der
Resend-Allowlist eingeführt — gesetzt werden kann das Feld dort ausschließlich
per Migrationsscript für die beiden Bestandskonten `henning`/`steffi`. Für
jede Adressänderung eines Nutzers (und für künftige neue Konten) fehlt bisher
ein Self-Service-Weg, sich erneut zu verifizieren. Diese Scheibe baut den
**Versand-Pfad** des Double-Opt-In-Flows: Ändert ein Nutzer seine
Empfänger-Adresse (`mail_to`, Rückfall `email`), wird ein zeitlich befristeter
Verifikations-Token erzeugt und eine Bestätigungsmail mit Link an genau diese
neue, noch unverifizierte Adresse verschickt. Der Klick-Endpoint, der den
Token einlöst und `email_verified_at` tatsächlich setzt, ist NICHT Teil
dieser Scheibe (→ Scheibe 2a-ii). Damit die Bestätigungsmail selbst nicht zum
neuen Einfallstor für Test-/Fremd-Adressen wird, bekommt der Versand einen
eigenen, engeren Sicherheits-Sonderpfad ohne Allowlist-Abhängigkeit (er würde
sich sonst selbst blockieren — die Zieladresse ist per Definition noch nicht
verifiziert).

## Source

- **File:** `internal/model/user.go` — NEU: `type EmailVerificationToken
  struct` (Kopie von `PasswordResetToken` @35: `TokenHash string`,
  `ExpiresAt time.Time`) (Go-API, `internal/`).
- **File:** `internal/store/user.go` — NEU:
  `SaveVerificationToken(userId string, token model.EmailVerificationToken)
  error`, `LoadVerificationToken(userId string) (*model.EmailVerificationToken,
  error)`, `DeleteVerificationToken(userId string) error`, nach dem Muster von
  `SaveResetToken`/`LoadResetToken`/`DeleteResetToken` @92-127. Datei:
  `data/users/<id>/email_verification.json` (Go-API, `internal/`).
- **File:** `internal/mail/verify.go` (NEU) — `BuildVerificationMail(publicHost,
  userID, token string) Mail`, nach dem Muster von `BuildResetMail`
  (`internal/mail/reset.go`) (Go-API, `internal/`).
- **File:** `internal/mail/sender.go` — Low-Level-SMTP-Teil von `Send()`
  @353-403 (ab `if cfg.Host == "" ...` bis zum `smtp.SendMail`-Aufruf) wird in
  eine gemeinsame private Hilfsfunktion ausgelagert (kein Duplikat der
  MIME-/STARTTLS-Logik). NEU: `recipientBlockedForVerification(host, to
  string) error` (analog `recipientBlocked` @312-348, aber ohne
  `loadResendAllowlist`-Aufruf). NEU: `SendVerificationMail(cfg MailConfig, to
  string, msg Mail) error` (Go-API, `internal/`).
- **File:** `internal/handler/auth.go` — `UpdateProfileHandler()` @445-514
  (Go-API, `internal/`). Erweitert um Token-Erzeugung + Versand-Goroutine bei
  tatsächlicher Adressänderung; Signaturänderung auf
  `UpdateProfileHandler(s *store.Store, cfg config.Config)
  http.HandlerFunc`.
- **File:** `internal/router/router.go` @62 — Aufruf an neue Handler-Signatur
  anpassen (Go-API, `internal/`).

> **Schicht-Hinweis:** Dieser gesamte Slice ist reines Go
> (`internal/model`, `internal/store`, `internal/mail`, `internal/handler`,
> `internal/router`). Kein Python-Code, kein Frontend betroffen.

## Estimated Scope

- **LoC:** ~+180 / -25
- **Files:** 6 (`internal/model/user.go` MODIFY, `internal/store/user.go`
  MODIFY, `internal/mail/verify.go` CREATE, `internal/mail/sender.go` MODIFY,
  `internal/handler/auth.go` MODIFY, `internal/router/router.go` MODIFY) plus
  zugehörige Go-Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.PasswordResetToken` (`internal/model/user.go:35`) | struct | Strukturelles Vorbild für `EmailVerificationToken` |
| `store.SaveResetToken`/`LoadResetToken`/`DeleteResetToken` (`internal/store/user.go:92-127`) | function | Strukturelles Vorbild für die drei neuen Token-Store-Funktionen |
| `mail.BuildResetMail` (`internal/mail/reset.go`) | function | Vorbild für `BuildVerificationMail` (Link-Aufbau, Plain-/HTML-Body) |
| `mail.recipientBlocked`/`isReservedTestDomain`/`rawContainsTestMailbox` (`internal/mail/sender.go`) | function | Bausteine für `recipientBlockedForVerification` (ohne Allowlist-Anteil) |
| `mail.resendBlocked` (`internal/mail/sender.go:56`) | function | Bleibt unverändert Teil des neuen Sonderpfads (`SendVerificationMail`) |
| `mail.IsTestUser` (`internal/mail/sender.go:48`) | function | Steuert im Handler die Test-User→Gmail-Weiche, wie bereits in `ForgotPasswordHandler` |
| `handler.ForgotPasswordHandler` (`internal/handler/auth.go:167-270`) | function | Strukturelles Vorbild für Token-Erzeugung, Goroutine+Timeout-Versand, Test-User/Resend-Weiche |
| `handler.UpdateProfileHandler` (`internal/handler/auth.go:445-514`) | function | Bestehender Adressänderungs-Reset (`EmailVerifiedAt = nil`, Scheibe 1) — Erweiterungspunkt dieser Scheibe |
| `router.New` (`internal/router/router.go:62`) | function | Ruft `UpdateProfileHandler` mit neuer Signatur auf |
| `config.Config` (`internal/config/config.go`) | struct | Liefert `PublicHost`, `SMTP*`, `GoogleSMTP*`, `FallbackSMTP*` für den Versand-Zweig |
| `middleware.UserIDFromContext` | function | Liefert die echte `user_id` des eingeloggten Nutzers — kein `"default"`-Fallback |

## Implementation Details

### 1. Neuer Token-Typ (`internal/model/user.go`)

```go
// EmailVerificationToken — Issue #1219 Scheibe 2a-i. Struktureller Klon von
// PasswordResetToken: Hash statt Klartext-Token persistiert, mit Ablauf.
type EmailVerificationToken struct {
    TokenHash string    `json:"token_hash"`
    ExpiresAt time.Time `json:"expires_at"`
}
```

### 2. Token-Store (`internal/store/user.go`)

Drei neue Funktionen, 1:1 nach dem Muster von `SaveResetToken`/
`LoadResetToken`/`DeleteResetToken` (@92-127), Zieldatei
`data/users/<id>/email_verification.json` statt `password_reset.json`.
`SaveVerificationToken` überschreibt eine bestehende Datei kommentarlos —
genau das gewünschte Verhalten für AC „zweiter Token entwertet ersten".

### 3. `internal/mail/verify.go` (NEU)

`BuildVerificationMail(publicHost, userID, token string) Mail` — analog
`BuildResetMail`, aber mit eigenem Linkpfad
`{publicHost}/verify-email?user=<url-escaped userID>&token=<url-escaped
token>` (dieselbe Escaping-Disziplin wie im Reset-Link) und eigenem
Betreff/Text ("Bestätige deine E-Mail-Adresse für Gregor 20"). Der Link zeigt
auf eine künftige Frontend-Seite (Scheibe 2b) mit Bestätigungs-Knopf — 2a-i
liefert nur den Link, kein Backend-Endpoint nimmt ihn in dieser Scheibe
entgegen (PO-Entscheidung: POST-Bestätigung statt GET-Auto-Confirm, folgt in
2a-ii). Gültigkeitshinweis im Mailtext: 24 Stunden.

### 4. `internal/mail/sender.go` — Refactor + Sonderpfad

**Refactor (kein Verhaltensunterschied für den bestehenden `Send()`-Aufrufer):**
Der Block ab der Config-Vollständigkeitsprüfung bis zum `smtp.SendMail`-Call
in `Send()` (@360-402) wandert in eine private Funktion, z.B.
`func dialAndSend(cfg MailConfig, to string, msg Mail) error`. `Send()` ruft
nach den bestehenden Guards (`recipientBlocked`, `resendBlocked`) nur noch
`dialAndSend` auf. Kein Duplikat der MIME-/Boundary-/STARTTLS-Logik zwischen
den beiden Sende-Pfaden.

**`recipientBlockedForVerification(host, to string) error`:** Struktureller
Zwilling von `recipientBlocked`, aber OHNE `loadResendAllowlist`-Aufruf.
Prüft stattdessen ausschließlich:
1. `rawContainsTestMailbox(to)` — dasselbe Fangnetz gegen
   `gregor-test@`/`gregor-staging@henemm.com` wie beim Hauptpfad.
2. Genau EIN Empfänger: `splitRecipientField(to)` muss exakt ein Element
   liefern — mehr oder weniger als eins wird geblockt (kein
   Adresslisten-/Trennzeichen-Trick über diesen Pfad).
3. `isReservedTestDomain(normalizedAddrForGuard(to))` — reservierte
   RFC-2606-Domains werden geblockt, auch auf dem Sonderpfad.

Kein Aufruf von `loadResendAllowlist` — die Zieladresse ist per Definition
noch NICHT verifiziert, ein Allowlist-Check würde jede Bestätigungsmail
blockieren.

**`SendVerificationMail(cfg MailConfig, to string, msg Mail) error`:**
```
if err := recipientBlockedForVerification(cfg.Host, to); err != nil { return err }
if err := resendBlocked(cfg.Host); err != nil { return err }
return dialAndSend(cfg, to, msg)
```
Genau EIN vorgesehener Aufrufer im gesamten Codebase: der Versand-Zweig in
`UpdateProfileHandler` (`to` = die vom eingeloggten Nutzer selbst über
`mail_to`/`email` gesetzte neue Adresse). Kein generischer „beliebige Adresse
senden"-Pfad.

### 5. `UpdateProfileHandler` — Token-Erzeugung + Versand

Nach dem bestehenden Reset-Block (@489-496, unverändert: `EmailVerifiedAt =
nil` bei tatsächlicher Änderung) UND vor `s.SaveUser(*user)`: wenn `email`
ODER `mail_to` sich tatsächlich geändert hat, wird die effektive neue
Empfänger-Adresse ermittelt (`mail_to`, Rückfall `email`, exakt dieselbe
Fallback-Logik wie in `ForgotPasswordHandler` @212-215). Ist die Adresse
nicht leer:

1. Zufälliger Token (32 Byte, hex), bcrypt-gehasht — identisches Muster zu
   `ForgotPasswordHandler` @188-203.
2. `EmailVerificationToken{TokenHash: ..., ExpiresAt: time.Now().Add(24 *
   time.Hour)}` → `s.SaveVerificationToken(userId, token)`. Überschreibt
   automatisch einen zuvor bestehenden Verifikations-Token desselben Nutzers.
3. Mail-Versand in Goroutine mit 20s-Timeout, exakt nach dem Muster von
   `ForgotPasswordHandler` @250-266: Test-User (`mail.IsTestUser(userId)`) →
   `cfg.GoogleSMTP*`-Config + `mail.SendWithFallback`; echte User →
   `cfg.SMTP*`-Config + neues `mail.SendVerificationMail` (NICHT
   `SendWithFallback`/`Send` — der Sonderpfad ist zwingend, damit die
   Allowlist-Prüfung nicht greift). `mail.BuildVerificationMail(cfg.PublicHost,
   userId, token)` liefert den Mailinhalt.
4. Der Handler blockiert nicht auf den Versand (Goroutine, wie beim
   Passwort-Reset) und antwortet wie bisher mit dem aktualisierten Profil.

Handler-Signatur ändert sich zu `UpdateProfileHandler(s *store.Store, cfg
config.Config) http.HandlerFunc` — `cfg` wird für `PublicHost` und die
SMTP-Configs benötigt, exakt wie bei `ForgotPasswordHandler`.

### 6. `internal/router/router.go`

Zeile 62: `handler.UpdateProfileHandler(deps.Store)` →
`handler.UpdateProfileHandler(deps.Store, *deps.Config)` — identisches Muster
zum bestehenden `ForgotPasswordHandler`-Aufruf @54.

## Expected Behavior

- **Input:** `PUT /api/auth/profile` (authentifiziert) mit geändertem `email`
  oder `mail_to` gegenüber dem gespeicherten Profil.
- **Output:** Profil wird gespeichert (`email_verified_at` bereits durch
  Scheibe 1 auf leer zurückgesetzt); zusätzlich wird ein neuer
  Verifikations-Token unter `data/users/<userId>/email_verification.json`
  erzeugt (24h gültig, überschreibt einen etwaigen vorherigen Token
  desselben Nutzers) und asynchron eine Bestätigungsmail mit Link an die
  NEUE Adresse verschickt. Bei No-Op-Update (identischer Wert) passiert
  weder das eine noch das andere.
- **Side effects:** Log-Eintrag bei Versand-Fehlschlag/Timeout (Muster
  `ForgotPasswordHandler`); der Versand-Sonderpfad blockiert reservierte
  Test-Domains, das Test-Postfach-Fangnetz und Mehrfach-Empfänger VOR jedem
  SMTP-Connect — kein SMTP-Traffic zu solchen Adressen.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer ändert per `PUT
  /api/auth/profile` seine `mail_to`-Adresse auf einen neuen, gültigen Wert /
  When das Update verarbeitet wird / Then wird ein Verifikations-Token unter
  `data/users/<userId>/email_verification.json` erzeugt und eine
  Bestätigungsmail mit Link an genau diese neue (noch unverifizierte)
  Adresse verschickt.
  - Test: Profil mit `mail_to=alt@x.de` anlegen, `PUT` mit
    `mail_to=neu@x.de` senden, prüfen dass `email_verification.json`
    existiert und der Mailversand (Test-Doppel des SMTP-Sinks/Fixture-Host)
    genau einen Aufruf mit `to=neu@x.de` erhalten hat.

- **AC-2:** Given ein Nutzer sendet ein `PUT`-Update mit identischem
  (unverändertem) `mail_to`-Wert / When das Update verarbeitet wird / Then
  wird WEDER ein Verifikations-Token erzeugt NOCH eine Bestätigungsmail
  verschickt.
  - Test: Profil mit `mail_to=X` anlegen, `PUT` mit `mail_to=X` senden,
    prüfen dass keine `email_verification.json` entsteht (bzw. eine
    vorher bestehende unverändert bleibt) und kein Mailversand-Aufruf
    stattfindet.

- **AC-3:** Given ein Nutzer ändert `mail_to` auf eine reservierte
  RFC-2606-Test-Domain (z.B. `foo@example.com`) / When das Update
  verarbeitet wird und der anschließende Versand-Aufruf läuft / Then wird
  `SendVerificationMail` durch `recipientBlockedForVerification` VOR jedem
  SMTP-Connect abgewiesen — die neue Adresse bekommt nicht einmal die
  Bestätigungsmail.
  - Test: `PUT` mit `mail_to=foo@example.com` senden, Versand-Aufruf
    beobachten/mocken, prüfen dass ein Fehler zurückkommt und kein
    `smtp.SendMail`/Fixture-Host-Kontakt erfolgt; Wiederholung mit
    `.test`/`.invalid`/`.localhost`/`.example`-Domain.

- **AC-4:** Given eine `mail_to`-Änderung auf das rohe Test-Postfach-Literal
  (`gregor-test@henemm.com`, ggf. plus-adressiert) ODER auf einen
  Resend-Host ohne `GZ_RESEND_ALLOWED=1` bzw. unter `go test` / When der
  Versand-Sonderpfad ausgeführt wird / Then greifen
  `rawContainsTestMailbox` bzw. `resendBlocked` (#1122) genauso wie beim
  Hauptpfad und blockieren den Versand.
  - Test: Einmal `to=gregor-test+x@henemm.com` gegen
    `recipientBlockedForVerification` prüfen (Fangnetz greift), einmal
    `SendVerificationMail` unter `go test` gegen einen Resend-Host-String
    aufrufen und den `resendBlocked`-Fehler nachweisen.

- **AC-5:** Given ein `to`-String mit mehreren, durch Komma oder Semikolon
  getrennten Adressen wird an `recipientBlockedForVerification` übergeben /
  When die Prüfung läuft / Then wird der Aufruf abgewiesen, weil mehr als
  ein Empfänger erkannt wird — der Sonderpfad lässt ausschließlich genau
  einen Empfänger zu.
  - Test: `recipientBlockedForVerification(host, "a@x.de,b@x.de")` und
    `"a@x.de; b@x.de")` aufrufen, jeweils einen Fehler erwarten;
    Gegenprobe mit genau einer Adresse liefert `nil`.

- **AC-6:** Given ein Konto mit `test`/`tdd` im Namen (`IsTestUser` liefert
  `true`) ändert seine Adresse / When der Versand-Zweig in
  `UpdateProfileHandler` läuft / Then wird die Bestätigungsmail über die
  `GoogleSMTP*`-Config verschickt, NIE über `SendVerificationMail`/den
  Resend-Sonderpfad.
  - Test: Handler mit einem `test-`-präfigierten `userId` und geänderter
    `mail_to` aufrufen, geladene/verwendete `MailConfig` bzw. den
    aufgerufenen Sendepfad prüfen — muss die Gmail-Config sein.

- **AC-7:** Given ein Nutzer ändert seine Adresse ein zweites Mal, bevor der
  erste Verifikations-Token eingelöst wurde / When das zweite Update
  verarbeitet wird / Then überschreibt `SaveVerificationToken` den
  bestehenden Token vollständig — der `TokenHash` aus dem ersten Versand
  passt danach nicht mehr zum gespeicherten Token (alter Link wertlos).
  - Test: `PUT` mit `mail_to=a@x.de` senden (Token 1 erzeugen, Klartext-Token
    aus dem Test-Doppel des Mailversands abgreifen), danach `PUT` mit
    `mail_to=b@x.de` senden, `LoadVerificationToken` laden, per
    `bcrypt.CompareHashAndPassword` prüfen, dass Token 1 NICHT mehr passt,
    Token 2 (aus dem zweiten Versand) hingegen schon.

- **AC-8:** Given zwei verschiedene Nutzer (A und B) ändern beide ihre
  Adresse / When beide Updates verarbeitet sind / Then liegt Nutzer As
  Verifikations-Token ausschließlich unter `data/users/A/email_verification.json`
  und Nutzer Bs Token ausschließlich unter `data/users/B/email_verification.json`
  — kein globaler oder Cross-User-Speicherort.
  - Test: Zwei Test-User A/B anlegen, für beide `PUT
    /api/auth/profile` mit geänderter `mail_to` aufrufen (jeweils mit dem
    zugehörigen `user_id`-Kontext), Dateisystem/Store-Fixture prüfen: genau
    eine Token-Datei je Nutzerverzeichnis, kein Token außerhalb.

- **AC-9:** Given ein frisch erzeugter Verifikations-Token / When
  `ExpiresAt` auf dem gespeicherten `EmailVerificationToken` ausgelesen wird
  / Then liegt der Zeitstempel bei ca. `Zeitpunkt der Erzeugung + 24 Stunden`
  (Toleranzfenster für Testlaufzeit, z.B. ±1 Minute), nicht bei den 30
  Minuten des Passwort-Reset-Tokens.
  - Test: `PUT`-Update mit geänderter `mail_to` unmittelbar vor/nach einem
    Zeitstempel senden, `LoadVerificationToken` laden, `ExpiresAt` gegen
    `time.Now().Add(24*time.Hour)` mit Toleranz vergleichen.

## Known Limitations

- Diese Scheibe baut ausschließlich den Versand-Pfad. Der Link in der
  Bestätigungsmail führt auf eine Frontend-Route (`/verify-email?...`), die
  bis Scheibe 2b nicht existiert, und es gibt noch KEINEN Backend-Endpoint
  (`VerifyEmailHandler`), der den Token entgegennimmt und `email_verified_at`
  setzt — ein Klick auf den Link läuft bis dahin ins Leere. Kein Nutzer kann
  sich in dieser Scheibe end-to-end selbst verifizieren.
- Bricht die Versand-Goroutine wegen SMTP-Fehler oder 20s-Timeout ab, bleibt
  der bereits gespeicherte Token trotzdem gültig (Verhalten identisch zum
  bestehenden Passwort-Reset-Pfad) — der Nutzer bekommt aber keine Mail und
  müsste eine erneute (No-Op-freie) Adressänderung auslösen, um einen neuen
  Versandversuch zu erzwingen. Kein eigener Retry-Mechanismus in dieser
  Scheibe.
- `recipientBlockedForVerification` prüft NICHT, ob die Adresse zu einem
  existierenden Profil gehört (sie gehört per Konstruktion zum aufrufenden
  Nutzer selbst) — der Sonderpfad ist bewusst nur über den einen,
  fest verdrahteten Aufrufer in `UpdateProfileHandler` erreichbar und nicht
  als generischer öffentlicher Versand-Endpoint gedacht.
- Der alte Verifikations-Token wird bei einer erneuten Adressänderung nicht
  aktiv gelöscht, sondern durch `SaveVerificationToken` überschrieben — es
  existiert kein separater Lösch-Aufruf in dieser Scheibe (funktional
  äquivalent, da der alte Hash nach dem Überschreiben nicht mehr matcht).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung des bestehenden, durch #1122/#1147/#1148/#1219
  etablierten Token-/Mail-Versand-Musters (Passwort-Reset) um einen
  strukturell identischen zweiten Token-Typ und einen engeren
  Sicherheits-Sonderpfad für Empfänger ohne Allowlist-Eintrag — kein neuer
  Architekturbaustein, keine neue Technologieentscheidung.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1219 Scheibe 2a-i, PO-Entscheidung 2026-07-10

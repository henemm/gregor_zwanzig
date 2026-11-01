# Context: feat-2163-s1-auth-haertung-go

## Request Summary
Issue #2163 (Teil von Epic #2138, Multi-User-Readiness) sammelt Kleinbefunde zur Auth-Härtung.
Scheibe 1 umfasst die Go-Punkte. Scheibe 2 (Python-Pfadbauten ohne `VALID_USER_ID_RE`,
`.env.tpl`-Vorlage) folgt in einem eigenen Workflow.

## Ist-Stand je Punkt (gegen `origin/main` 7b8a62fb7 nachgeprüft, 2026-10-31)

Die Zeilenangaben im Issue (Stand 2026-09-06) sind veraltet. Zwei Punkte sind schon erledigt.

| # | Punkt aus #2163 | Stand heute | Fundstelle |
|---|---|---|---|
| 1 | Enumeration: 409 bei Registrierung | **offen** | `internal/handler/auth.go:79-84` (`user already exists`), `:138` |
| 2 | Enumeration: 409 bei Passkey-Registrierung | **offen** | `internal/handler/passkey.go:474,488,542,560` (`user_already_exists`, `email_taken`) |
| 3 | Timing in `ForgotPasswordHandler` (bcrypt nur bei Treffer) | **offen** | `auth.go:461-510`: bei `user == nil` sofort `{"status":"ok"}`, bei Treffer `bcrypt.GenerateFromPassword` + Mailversand |
| 4 | Timing in `LoginHandler` (kein Dummy-Hash) | **offen** | `auth.go:336-355`: `user == nil` → 401 ohne bcrypt; Treffer → `CompareHashAndPassword` |
| 5 | Webhook-Secret-Vergleich nicht konstantzeitig | **erledigt** (#2159) | `telegram_webhook.go:89-92` `secretEqual` (sha256 + `subtle.ConstantTimeCompare`) |
| 6 | `Secure`-Flag hängt an `X-Forwarded-Proto` | **erledigt** | `middleware/auth.go:156-160` `CookieSecure` = TLS **oder** https-`PublicHost`; genutzt in `middleware/auth.go:152`, `lang.go:54`, `auth_oauth.go:55` |
| 7 | `TELEGRAM_BOT_USERNAME`/`TELEGRAM_WEBHOOK_SECRET` per `os.Getenv` | **offen** | `telegram_connect.go:199`, `telegram_webhook.go:44`; analog (nicht im Issue): `inbound_webhooks.go:101-102,148-149` (`SEVEN_*`, `STALWART_*`) |
| 8 | `ProxyHandler` reicht Client-Query ohne `appendUserID` | **offen** | `proxy.go:61-67`; Routen `router.go:234-238,270` (`/api/config`, `/api/metrics`, `/api/templates`, `/api/sms-symbols`, `/api/compare/metrics`) |
| 9 | `scheduler.go` loggt hartkodiert „9 cron entries (10 jobs)" | **offen** | `scheduler.go:373` |

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/auth.go` | Register-, Login-, Forgot-Handler (Punkte 1, 3, 4) |
| `internal/handler/passkey.go` | Passkey-Registrierung (Punkt 2) |
| `internal/handler/telegram_connect.go`, `telegram_webhook.go` | Env-Lesen (Punkt 7) |
| `internal/handler/inbound_webhooks.go` | gleiches Env-Muster für seven/Stalwart (Kandidat für Punkt 7) |
| `internal/config/` | zentrale Konfiguration, Startvalidierung |
| `internal/handler/proxy.go` | `ProxyHandler`, `appendUserID` (Punkt 8) |
| `internal/router/router.go` | Routen + IP-Rate-Limiter (`registerLimiter` 5/h, `loginLimiter` 30/h, `forgotLimiter` 5/h) |
| `internal/scheduler/scheduler.go` | Startlog (Punkt 9) |
| `frontend/src/routes/register/+page.server.ts:74-75` | wertet 409 aus, unterscheidet `email_taken` (#2147 B1, AC-15) |

## Existing Patterns
- Enumerationsschutz existiert bereits in `ForgotPasswordHandler` (immer `{"status":"ok"}`, auch für pfad-unsichere IDs, #2140).
- Konstantzeit-Vergleich: `secretEqual` in `telegram_webhook.go`, `subtle.ConstantTimeCompare` in `auth_oauth.go:103`.
- `CookieSecure` als zentrale Funktion für das Secure-Flag.
- `appendUserID` überschreibt eine client-gesetzte `user_id` (Proxy-Muster für alle nutzerbezogenen Routen).
- IP-Rate-Limiter je Auth-Route in `router.go:64-122`.

## Dependencies
- Upstream: `store.LoadUser`, bcrypt, `config.Config`, Mailversand (Resend) im Forgot-Pfad.
- Downstream: Frontend-Registrierung (`/register`) und Passkey-Registrierung werten 409 und die Fehlercodes `email_taken`/`user_already_exists` aus. Prod-Selftest und e2e-Tests melden sich an.

## Existing Specs / ADRs
- ADR-0003 (Multi-User, Zwei-Nutzer-Test), #2147 B1 (eindeutige E-Mail, `email_taken`), #2140 (Pfad-Traversal, `ValidUserID`), #2159 (Lokalhost-Guard, `secretEqual`).

## Risks & Considerations
- **Punkt 1/2 ist eine Produktfrage, keine reine Technikfrage.** Bei frei gewähltem Benutzernamen verrät die Registrierung zwangsläufig, ob ein Name vergeben ist. Sonst kann der Nutzer keinen anderen wählen. OWASP empfiehlt in diesem Fall, die Enumeration per Rate-Limit zu bremsen (`registerLimiter` 5/h je IP existiert) statt sie zu verbergen. `email_taken` lässt sich dagegen verbergen, indem die Antwort neutral bleibt und eine Mail an die bestehende Adresse geht. Das kollidiert mit #2147 B1 AC-15 (Frontend zeigt „E-Mail vergeben"). In der Analyse ist die Zielform festzulegen, ohne Rückbau von #2147.
- **Timing (3/4):** Ein Dummy-bcrypt im Nicht-Treffer-Zweig gleicht die Laufzeit an. Korrektur (Analyse): Der Mailversand im Forgot-Treffer-Zweig läuft bereits asynchron (Goroutine `auth.go:559`); übrig bleibt nur bcrypt + `SaveResetToken`.
- **Punkt 7:** Startvalidierung darf Prod/Staging nicht am Start hindern, wenn Telegram bewusst nicht konfiguriert ist (leere Werte müssen erlaubt bleiben, nur Lesen über `config`).
- **Punkt 8:** Die Ziele sind heute nutzerunabhängig. Die Härtung soll eine Schutzschicht sein (client-`user_id` verwerfen), ohne die Antworten zu ändern.
- Login- und Registrierungspfad sind der kritische Pfad für alle Nutzer. Ein Fehler sperrt alle aus, deshalb ist das Adversary-Risiko hoch.

## Analysis

### Type
Feature (Härtung; Issue trägt Label `bug`, ist aber kein Fehlverhalten aus Nutzersicht, sondern Sicherheitsnachschärfung).

### Zusätzliche Befunde aus der Analyse (2026-10-31)
- **„In-Memory-Wachstum" (Issue-Titel, kein Body-Punkt): erledigt.** Alle drei In-Memory-Speicher räumen ab: `IPRateLimiter.cleanupLoop` (`middleware/ratelimit.go:60-68`, alle 10 min), `ChallengeStore.gc` (`handler/challenge_store.go:51-59`, jede Minute, 5-min-TTL), `TelegramTokenStore` verwirft abgelaufene Token (`telegram_connect.go:161`). Kein Handlungsbedarf; in der Spec als „bereits erfüllt" festhalten.
- **Passkey-Login-Begin `passkey.go:181`:** `store.LoadUser` validiert seit #2140 selbst (`store/user.go:56`, `ErrInvalidUserID`). Kein Pfad-Traversal-Befund.
- **Passkey-Login-Begin verrät Passkey-Besitz** (200 vs. 401): inhärent bei nicht-discoverable WebAuthn, bekannte Grenze, nicht beheben.
- **Scheduler:** tatsächlich 8 Cron-Einträge (Slice `jobs`, `scheduler.go:335-360`), 9 Statuszeilen (`briefing_dispatch` expandiert doppelt). Log „9 cron entries (10 jobs)" ist doppelt falsch.
- **Gespeicherte Passwort-Hashes:** Cost 10 (`bcrypt.DefaultCost`, `router.go:83`); Tests nutzen MinCost 4.
- **envconfig-Alt-Fallback belegt** (`envconfig@v1.4.0/envconfig.go:194-195`): Feld mit `envconfig:"TELEGRAM_WEBHOOK_SECRET"` liest erst `GZ_TELEGRAM_WEBHOOK_SECRET`, dann unpräfixiert `TELEGRAM_WEBHOOK_SECRET`. Muster existiert bereits (`SMTP_HOST`, `config.go:45`). Prod/Staging-Env-Dateien bleiben unverändert.

### Entscheidung Punkte 1/2 (Registrierungs-Enumeration) — Tech-Lead-Entscheidung, Option (a)
Verhalten bleibt unverändert, als akzeptiertes Restrisiko dokumentiert. Begründung:
- Frei wählbarer Benutzername ist nicht verbergbar (sonst kann der Nutzer keinen anderen wählen); OWASP empfiehlt hier Bremsen per Rate-Limit — `registerLimiter` 5/h je IP existiert.
- `email_taken` ist bestehende, freigegebene Produktentscheidung (#2147 B1 AC-15, Frontendtext „Diese E-Mail-Adresse gehört bereits zu einem Konto…"); die Spec dort notiert die Enumeration bereits bewusst. Keine Entscheidung wird zurückgenommen.
- Passkey-Registrierung kann ohne Konto nicht „neutral erfolgreich" antworten; Neutralisierung bräuchte neuen Mailpfad (Mailbombing-Vektor) und Frontend-Umbau bei geringem Gewinn.
- Umsetzung: Code-Kommentar an `auth.go` Register-409 und `passkey.go` 409-Stellen + AC „Verhalten unverändert, Restrisiko dokumentiert". Der PO sieht das bei der Spec-Freigabe; keine separate Rückfrage.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | Dummy-Hash (`sync.Once`, Cost `bcrypt.DefaultCost`), Dummy-Compare in allen Login-401-Zweigen (pfad-unsicher, LoadUser-Fehler, `user == nil`, leerer/ungültiger `PasswordHash`); Dummy-bcrypt im Forgot-Nicht-Treffer-Zweig; Restrisiko-Kommentar Register-409 |
| `internal/handler/passkey.go` | MODIFY | nur Restrisiko-Kommentar an den 409-Stellen |
| `internal/handler/proxy.go` | MODIFY | `ProxyHandler` verwirft client-`user_id`; Query ohne `user_id` bleibt byte-identisch (kein `Encode()`-Umsortieren) |
| `internal/scheduler/scheduler.go` | MODIFY | Startlog-Zahlen berechnet (Cron-Einträge, Statuszeilen) |
| `internal/config/config.go` | MODIFY | Felder `TelegramWebhookSecret`, `TelegramBotUsername`, `SevenWebhookPathSecret`, `SevenWebhookSigningKey`, `StalwartWebhookPathSecret`, `StalwartWebhookSecret`, alle `default:""` |
| `internal/handler/telegram_webhook.go`, `telegram_connect.go`, `inbound_webhooks.go` | MODIFY | Werte aus Config statt `os.Getenv`; fail-closed 503 bei leerem Wert bleibt |
| `internal/router/router.go` | MODIFY | Config-Werte an die vier Handler durchreichen |
| `internal/handler/proxy_test.go` | MODIFY | ProxyHandler gegen `httptest`-Core: `user_id` weg, Rest unverändert |
| `internal/handler/auth_timing_test.go` | CREATE | Laufzeit-Untergrenze je Nicht-Treffer-Zweig bei echtem Cost 10 (kein Zähler/Funktionsnaht) |
| `internal/config/config_test.go` | MODIFY | unpräfixierter Name wird gelesen, leerer Wert erlaubt, Start ohne Telegram ok |
| `internal/scheduler/*_test.go` | MODIFY/CREATE | Logzahl passt zu registrierten Einträgen |
| `telegram_webhook*_test.go`, `inbound_webhooks*_test.go`, `telegram_webhook_inbound_route_test.go`, `inbound_webhooks_route_test.go`, `account_deletion_leftovers_test.go` | MODIFY | von `os.Setenv`/`t.Setenv` auf Config-Werte umstellen |

SEVEN_*/STALWART_* stehen nicht im Issue: bewusste Erweiterung von Punkt 7 (gleiche Mechanik, sonst bliebe das Muster halb).

### Scope Assessment
- Files: ~8 Produktion, ~10 Test
- Estimated LoC: Produktion ca. +150/-30, Tests ca. +250
- Risk Level: MEDIUM — Login ist kritischer Pfad aller Nutzer (Erfolgspfad aber unverändert); Env-Umstellung hat mittleres Regressionsrisiko in Tests.
- Abtrennbar bei Überschreitung: Punkt 7 als eigene Teilscheibe (größter Testumbau, geringster Sicherheitsgewinn).

### Technical Approach
Reihenfolge: (9) Scheduler-Log → (8) Proxy mit Test → (3+4) gemeinsamer Dummy-Hash → (7) Env über Config. Timing-Test: Zusicherung „Nicht-Treffer dauert ≥ X ms" bei Cost 10 (~50 ms vs. <1 ms ohne Dummy, großzügige Marge), damit der Mutations-Validator das Entfernen des Dummy-Aufrufs am Verhalten sieht. Proxy: `user_id` nur entfernen, wenn vorhanden; Annahme „Core ignoriert `user_id` auf diesen Routen" in die Spec. Staging-Nachweis: Login gültig/ungültig/unbekannt; Telegram-/seven-Webhook mit falschem Secret → 403 (nicht 503) belegt, dass das Secret über Config gelesen wird.

### Dependencies
`store.LoadUser`, bcrypt, `config.Load` (envconfig v1.4.0), Router-Deps; Abnehmer der Register-409 bleiben unberührt (Option a). Scheibe 2 (Python-Pfadbauten ohne `VALID_USER_ID_RE`, `.env.tpl`) bleibt offen ⇒ #2163 nach Scheibe 1 NICHT schließen.

### Open Questions
- keine (Enumeration per Tech-Lead-Entscheidung (a); PO sieht sie bei Spec-Freigabe)

---
entity_id: auth_haertung_go_2163
type: module
created: 2026-10-31
updated: 2026-10-31
status: draft
version: "1.0"
tags: [security, auth, go, epic-2138, issue-2163, scheibe-1]
workflow: feat-2163-s1-auth-haertung-go
---

# Auth-Härtung Go (#2163, Scheibe 1)

## Approval

- [ ] Approved

## Purpose

Kleinbefunde der Auth-Härtung aus #2163 (Epic #2138, Multi-User-Readiness) werden auf der Go-Seite geschlossen: Anmelden und „Passwort vergessen" verraten über ihre Antwortzeit nicht mehr, ob ein Konto existiert; der Proxy lässt keine von außen gesetzte `user_id` zum Python-Core durch; der Scheduler loggt korrekte Zahlen; Geheimnisse für Webhooks kommen über die zentrale Konfiguration statt über verstreute `os.Getenv`-Aufrufe. Die Registrierungs-Enumeration bleibt bewusst unverändert und wird als Restrisiko dokumentiert.

## Source

- **File:** `internal/handler/auth.go`, `internal/handler/passkey.go`, `internal/handler/proxy.go`, `internal/scheduler/scheduler.go`, `internal/config/config.go`, `internal/handler/telegram_webhook.go`, `internal/handler/telegram_connect.go`, `internal/handler/inbound_webhooks.go`, `internal/router/router.go`
- **Identifier:** `LoginHandler`, `ForgotPasswordHandler`, `RegisterHandlerWithInvites`, `ProxyHandler`, Scheduler-Startlog, `config.Config`

> **Schicht-Hinweis:** ausschließlich Go-API (`internal/`, `cmd/`). Kein Frontend, kein Python-Code. Die Python-Pfadbauten ohne `VALID_USER_ID_RE` und die `.env.tpl`-Vorlage gehören zu Scheibe 2.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen, kein Trip- oder Compare-Pendant.
> - **Mandantentrennung (ADR-0003):** Der Proxy-Teil (Punkt 8) wird mit zwei verschiedenen Nutzern getestet (AC-13). `user_id` kommt weiter nur aus dem Auth-Kontext, nie aus der Query, nie `"default"`.
> - **Kanäle:** Briefing- und Alarm-Inhalte sind nicht berührt. Der Punkt-7-Block betrifft nur die Webhook-Eingänge (Telegram, seven.io für SMS und Premium-SMS, Stalwart für E-Mail), nicht deren Inhalt.

## Bereits erfüllt (kein Bau)

Diese Punkte sind gegen `origin/main` (7b8a62fb7, 2026-10-31) nachgeprüft und bereits umgesetzt. Es gibt dafür bewusst keine Bau-ACs.

| Punkt | Stand | Fundstelle |
|---|---|---|
| 5: Webhook-Secret-Vergleich konstantzeitig | erledigt mit #2159 | `internal/handler/telegram_webhook.go:89-92` (`secretEqual`: sha256 + `subtle.ConstantTimeCompare`) |
| 6: `Secure`-Flag am Cookie hängt nicht an `X-Forwarded-Proto` | erledigt | `internal/middleware/auth.go:156-160` (`CookieSecure`: TLS oder https-`PublicHost`), genutzt in `middleware/auth.go:152`, `handler/lang.go:54`, `handler/auth_oauth.go:55` |
| In-Memory-Wachstum (Issue-Titel) | erledigt | `IPRateLimiter.cleanupLoop` (`internal/middleware/ratelimit.go:60-68`, alle 10 Minuten), `ChallengeStore.gc` (`internal/handler/challenge_store.go:51-59`, jede Minute, 5-Minuten-TTL), `TelegramTokenStore` verwirft abgelaufene Token (`internal/handler/telegram_connect.go:161`) |

Ebenfalls geprüft, kein Befund: Passkey-Login-Begin `passkey.go:181` ruft `store.LoadUser`, das seit #2140 selbst validiert (`store/user.go:56`, `ErrInvalidUserID`). Dass Passkey-Login-Begin Passkey-Besitz verrät (200 gegen 401), ist bei nicht-discoverable WebAuthn unvermeidlich und bleibt als bekannte Grenze.

## Bewusst nicht geändert: Registrierung verrät vergebene Namen und E-Mail-Adressen

In einfacher Sprache: Wer sich registriert, erfährt heute, wenn der gewünschte Benutzername oder die E-Mail-Adresse schon vergeben ist (Antwort 409). Das bleibt so. Ein Angreifer könnte damit prüfen, ob es einen bestimmten Namen oder eine Adresse im System gibt. Wir nehmen dieses Restrisiko bewusst in Kauf, weil:

- **Der Benutzername ist frei wählbar.** Ohne die Rückmeldung „vergeben" könnte niemand einen anderen Namen wählen. Das lässt sich nicht verbergen. Die übliche Empfehlung (OWASP) lautet in diesem Fall, die Abfragen zu bremsen statt die Antwort zu verstecken. Diese Bremse gibt es: `registerLimiter` erlaubt 5 Registrierungsversuche pro Stunde je IP-Adresse (`internal/router/router.go`).
- **`email_taken` ist eine freigegebene Produktentscheidung** (#2147 B1, AC-15; Spec `docs/specs/modules/adress_eindeutigkeit_schreibpfade.md`). Das Frontend zeigt „Diese E-Mail-Adresse gehört bereits zu einem Konto…" (`frontend/src/routes/register/+page.server.ts:74-75`), und die Spec dort hält die Enumeration schon als bewusst fest. Wir nehmen keine bestehende Entscheidung zurück.
- **Passkey-Registrierung** kann ohne Konto nicht „neutral erfolgreich" antworten. Eine neutrale Antwort bräuchte einen neuen Mailpfad (Mailbombing-Vektor) und einen Frontend-Umbau bei geringem Gewinn.
- Der „Passwort vergessen"-Pfad antwortet bereits immer neutral (`{"status":"ok"}`, #2140); dort gibt es keine Enumeration über den Inhalt.

Umgesetzt wird nur die Dokumentation: ein Kommentar an der Register-409-Stelle in `auth.go` (`user already exists`, `:79-84`, `:138`) und an den 409-Stellen in `passkey.go` (`:474,488,542,560`) mit Verweis auf diesen Abschnitt, auf ADR-0003 und auf #2147 B1. Folgt Epic #2138 später eine andere Produktentscheidung, ersetzt ein neues ADR diesen Abschnitt.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/auth.go` | MODIFY | Dummy-Hash (`sync.Once`, Cost aus `bcrypt.DefaultCost`), Dummy-Vergleich in allen Login-401-Zweigen und im Forgot-Nicht-Treffer-Zweig; Restrisiko-Kommentar am Register-409 |
| `internal/handler/passkey.go` | MODIFY | nur Restrisiko-Kommentar an den 409-Stellen |
| `internal/handler/proxy.go` | MODIFY | `ProxyHandler` entfernt `user_id` aus der Query |
| `internal/scheduler/scheduler.go` | MODIFY | Startlog-Zahlen aus den registrierten Einträgen berechnet |
| `internal/config/config.go` | MODIFY | sechs neue Felder, `default:""` (Block Punkt 7) |
| `internal/handler/telegram_webhook.go`, `telegram_connect.go`, `inbound_webhooks.go` | MODIFY | Werte aus Config statt `os.Getenv` (Block Punkt 7) |
| `internal/router/router.go` | MODIFY | Config-Werte an die Handler durchreichen (Block Punkt 7) |
| `internal/handler/auth_timing_test.go` | CREATE | Laufzeit-Untergrenzen je Nicht-Treffer-Zweig |
| `internal/handler/proxy_test.go` | MODIFY | Proxy gegen `httptest`-Core |
| `internal/scheduler/*_test.go` | MODIFY/CREATE | Logzahl passt zu den Einträgen |
| `internal/config/config_test.go` | MODIFY | Fallback auf unpräfixierte Namen, leere Werte (Block Punkt 7) |
| `telegram_webhook*_test.go`, `inbound_webhooks*_test.go`, `telegram_webhook_inbound_route_test.go`, `inbound_webhooks_route_test.go`, `account_deletion_leftovers_test.go` (alle unter `internal/handler/`) | MODIFY | von `os.Setenv`/`t.Setenv` auf Config-Werte umstellen (Block Punkt 7) |

## Estimated Scope

- Files: ca. 9 Produktion, ca. 10 Test
- LoC: Produktion ca. +150/-30, Tests ca. +250
- Risk: MEDIUM. Login ist der kritische Pfad aller Nutzer (der Erfolgspfad bleibt unverändert, AC-9); die Env-Umstellung hat mittleres Regressionsrisiko in den Tests.

**Abtrennregel (vorab festgelegt):** Überschreitet die Umsetzung das LoC-Budget (Obergrenze: 250 geänderte Zeilen Produktionscode oder 450 geänderte Zeilen Tests), wird der Punkt-7-Block (AC-15 bis AC-18) als eigene Teilscheibe abgetrennt und in einem Folge-Workflow geliefert; er hat den größten Testumbau und den geringsten Sicherheitsgewinn. Die Blöcke Timing, Proxy und Scheduler werden dann trotzdem ausgeliefert. #2163 bleibt in jedem Fall offen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.LoadUser` | Funktion | lädt Nutzer, validiert die Kennung seit #2140 selbst |
| `golang.org/x/crypto/bcrypt` | Bibliothek | Dummy-Hash und Vergleich; Kosten wie beim Speichern (`router.go:83`, `bcrypt.DefaultCost`) |
| `config.Load` (envconfig v1.4.0) | Modul | liest `GZ_<NAME>`, dann unpräfixiert `<NAME>` (`envconfig.go:194-195`); Muster existiert bereits bei `SMTP_HOST` (`config.go:45`) |
| ADR-0003 | ADR | Mandantentrennung, Zwei-Nutzer-Test, kein `"default"` |
| #2147 B1 | Spec | `email_taken` ist freigegebene Produktentscheidung |
| #2140 | Issue | `ValidUserID`, pfad-unsichere IDs |
| #2159 | Issue | `secretEqual` (bereits erfüllt) |
| `api/routers/config.py`, `api/routers/compare.py:11` | Python-Core | lesen kein `user_id` (Beleg für Punkt 8, vom Orchestrator geprüft) |

## Implementation Details

**Timing (Punkte 3 und 4).** In `auth.go` gibt es einen Dummy-Hash, der einmal per `sync.Once` erzeugt wird. Sein Cost stammt aus derselben Quelle wie der Cost beim Speichern von Passwörtern (`bcrypt.DefaultCost`, siehe `router.go:83`), nicht aus einer hart kodierten Zahl. Jeder Nicht-Treffer-Zweig führt vor seiner unveränderten Antwort einen `bcrypt.CompareHashAndPassword` gegen diesen Dummy-Hash aus und verwirft das Ergebnis.

- Login (`:336-355`): pfad-unsichere ID, `LoadUser`-Fehler, unbekannter Nutzer (`user == nil`), leerer oder ungültiger `PasswordHash`.
- Forgot (`:461-510`): pfad-unsichere ID und unbekannter Nutzer. Der Treffer-Zweig macht bcrypt und `SaveResetToken`; der Mailversand läuft schon asynchron (Goroutine `auth.go:559`) und zählt nicht zur Antwortzeit.
- Antworten (Status, Body, Header) bleiben byte-gleich. Es ändert sich nur die Laufzeit.

**Proxy (Punkt 8).** Entscheidung: Das Umsortieren der Query ist **nicht erlaubt**. Ist keine `user_id` in der Query, wird die Roh-Query unverändert weitergereicht (kein `Encode()`). Ist eine da, werden die Roh-Segmente (an `&` getrennt) geprüft und nur die Segmente mit dem Schlüssel `user_id` (nach URL-Dekodierung, auch ohne Wert) entfernt. Alle anderen Segmente behalten Reihenfolge und Kodierung. Begründung: Der Core darf auf diesen Routen weiter genau die Parameter sehen, die der Client geschickt hat; ein erneutes Kodieren könnte Sonderzeichen, Leerzeichen und Mehrfachparameter verändern und wäre ein unnötiges Regressionsrisiko. Die Ziele (`/api/config`, `/api/metrics`, `/api/templates`, `/api/sms-symbols`, `/api/compare/metrics`; `router.go:234-238,270`) sind heute nutzerunabhängig, weil der Core dort kein `user_id` liest. Die Härtung ist eine Schutzschicht für den Fall, dass ein Core-Endpunkt später `user_id` auswertet.

**Scheduler (Punkt 9).** Die Startzeile `scheduler.go:373` („9 cron entries (10 jobs)") wird aus den tatsächlich registrierten Einträgen berechnet. Heute sind das 8 Cron-Einträge (Slice `jobs`, `:335-360`) und 9 Statuszeilen (`briefing_dispatch` expandiert zu zwei).

**Env über Config (Punkt 7, eigener Block).** Neue Felder in `config.Config`, alle `default:""`: `TelegramWebhookSecret`, `TelegramBotUsername`, `SevenWebhookPathSecret`, `SevenWebhookSigningKey`, `StalwartWebhookPathSecret`, `StalwartWebhookSecret`. Jedes Feld trägt den unpräfixierten Namen als `envconfig`-Tag (z. B. `TELEGRAM_WEBHOOK_SECRET`), sodass `GZ_`-präfixierte und die bisherigen unpräfixierten Werte funktionieren. Die Env-Dateien von Prod und Staging bleiben unverändert. Die Handler erhalten die Werte über den Router; ein leerer Wert hält die Route fail-closed (503).

> **Scope-Erweiterung (begründet):** `SEVEN_*` und `STALWART_*` stehen nicht im Issue (dort nur Telegram). Sie werden mitgezogen, weil `inbound_webhooks.go:101-102,148-149` exakt dasselbe `os.Getenv`-Muster nutzt und die Umstellung sonst halb bliebe. Diese Erweiterung gehört zum abtrennbaren Block.

## Expected Behavior

- **Input:** Login-, Forgot-, Register-Anfragen; Proxy-Anfragen an die fünf nutzerunabhängigen Routen; Webhook-Aufrufe; Serverstart.
- **Output:** unveränderte Antworten (Status und Body); Nicht-Treffer-Zweige brauchen mindestens eine bcrypt-Laufzeit; keine `user_id` beim Core; korrekte Scheduler-Zahlen; Webhooks prüfen Secrets aus der Config.
- **Side effects:** keine neuen Daten, keine neuen Mails, kein Schema-Eingriff.

## Test Plan

Kern-Schicht (Go, deterministisch, ohne Netz, kein Mock-Theater; `httptest`-Core und echter Router erlaubt).

### Automated Tests (TDD RED)

- [ ] Timing-Tests je Nicht-Treffer-Zweig (AC-2 bis AC-7): Der Test baut den Handler mit `bcrypt.DefaultCost` (nicht MinCost) und sichert nur eine **Laufzeit-Untergrenze** zu („dauert ≥ 20 ms", großzügige Marge unter den erwarteten ca. 50 ms bei Cost 10 gegenüber unter 1 ms ohne Dummy). Es gibt **keinen** Vergleich „Treffer ≈ Nicht-Treffer" (flaky). Entfernt jemand den Dummy-Aufruf, wird der Test rot.
- [ ] Antwortgleichheit (AC-8) und Erfolgspfad (AC-9): Status und Body der Nicht-Treffer-Zweige sind byte-gleich zu vorher; gültiger Login liefert weiter Session und Cookie.
- [ ] Dummy-Hash-Kosten (AC-10): `bcrypt.Cost` des Dummy-Hashes gleicht `bcrypt.DefaultCost`.
- [ ] Proxy gegen `httptest`-Core (AC-11 bis AC-13): Core zeichnet die empfangene Query auf; Fälle ohne, mit, mehrfach, Groß/Klein-Variante und Zwei-Nutzer-Test.
- [ ] Scheduler (AC-14): Logzahl gleicht der Anzahl registrierter Einträge, ermittelt aus dem echten Scheduler-Aufbau.
- [ ] Config (AC-15, AC-16): unpräfixierter Name wird gelesen, `GZ_`-Name hat Vorrang, leerer Wert erlaubt, Start ohne Telegram ok.
- [ ] Route-Ebene (AC-17, AC-18): über den echten Router mit Config-Wert: falsches Secret 403, richtiges Secret Erfolg, leerer Wert 503.
- [ ] Register-409 und Passkey-409 unverändert (AC-1).

### Staging-Nachweis (AC-19)

Nach dem Push gegen `https://staging.gregor20.henemm.com`: Login mit gültigem Konto, falschem Passwort und unbekanntem Nutzer; „Passwort vergessen" für unbekannten Nutzer liefert `ok`; Telegram- und seven-Webhook mit falschem Secret liefern 403 (nicht 503 — das belegt, dass das Secret über die Config gelesen wird).

## Acceptance Criteria

**Restrisiko Registrierung (Punkte 1 und 2)**

- **AC-1:** Given ein Benutzername oder eine E-Mail-Adresse ist bereits vergeben / When jemand sich registriert (Konto oder Passkey) / Then antwortet der Server unverändert mit 409 (`user already exists`, `user_already_exists`, `email_taken`), und an den 409-Stellen in `auth.go` und `passkey.go` steht ein Kommentar, der das Restrisiko begründet und auf diese Spec verweist.
  - Test: Handler-Tests für Konto- und Passkey-Registrierung mit vergebenem Namen und vergebener E-Mail erwarten Status und Fehlercode wie bisher.

**Timing (Punkte 3 und 4)**

- **AC-2:** Given eine pfad-unsichere Kennung (z. B. `../x`) / When sie sich anmeldet / Then antwortet der Server unverändert mit 401, braucht aber mindestens die Laufzeit eines bcrypt-Vergleichs bei Standard-Kosten.
  - Test: Login-Handler mit `DefaultCost`; Laufzeit ≥ 20 ms, Antwort wie bisher.
- **AC-3:** Given beim Laden des Nutzers tritt ein Fehler auf / When die Anmeldung läuft / Then antwortet der Server unverändert mit 401 und braucht mindestens eine bcrypt-Laufzeit.
  - Test: Login-Handler mit fehlerhaftem Speicher; Laufzeit ≥ 20 ms, Antwort wie bisher.
- **AC-4:** Given ein unbekannter Nutzer (Laden liefert `nil`) / When er sich anmeldet / Then antwortet der Server unverändert mit 401 und braucht mindestens eine bcrypt-Laufzeit.
  - Test: Login-Handler mit nicht vorhandenem Nutzer; Laufzeit ≥ 20 ms, Antwort wie bisher.
- **AC-5:** Given ein Nutzer mit leerem oder ungültigem `PasswordHash` (z. B. reiner Passkey- oder Google-Account) / When er sich mit einem Passwort anmeldet / Then antwortet der Server unverändert mit 401 und braucht mindestens eine bcrypt-Laufzeit.
  - Test: Login-Handler mit Nutzer ohne Hash und mit kaputtem Hash; je Laufzeit ≥ 20 ms, Antwort wie bisher.
- **AC-6:** Given eine pfad-unsichere Kennung / When „Passwort vergessen" aufgerufen wird / Then antwortet der Server unverändert mit `{"status":"ok"}`, braucht aber mindestens eine bcrypt-Laufzeit.
  - Test: Forgot-Handler mit `DefaultCost`; Laufzeit ≥ 20 ms, Body unverändert.
- **AC-7:** Given ein unbekannter Nutzer / When „Passwort vergessen" aufgerufen wird / Then antwortet der Server unverändert mit `{"status":"ok"}`, versendet keine Mail und braucht mindestens eine bcrypt-Laufzeit.
  - Test: Forgot-Handler mit nicht vorhandenem Nutzer; Laufzeit ≥ 20 ms, Body unverändert, kein Mailversand.
- **AC-8:** Given die Nicht-Treffer-Zweige aus AC-2 bis AC-7 / When sie nach der Änderung antworten / Then sind Status, Body und Header byte-gleich zur Antwort vor der Änderung.
  - Test: Vergleich der aufgezeichneten Antworten mit festen Erwartungswerten je Zweig.
- **AC-9:** Given ein gültiges Konto mit richtigem Passwort / When es sich anmeldet / Then wird wie bisher die Sitzung ausgestellt und das Cookie gesetzt (Erfolgspfad unverändert).
  - Test: Login mit richtigem Passwort liefert 200 und Session-Cookie; falsches Passwort liefert weiter 401.
- **AC-10:** Given der Dummy-Hash / When er erzeugt wird / Then entsteht er genau einmal pro Prozess (`sync.Once`) mit demselben Cost wie beim Speichern von Passwörtern (`bcrypt.DefaultCost`), nicht mit einer hart kodierten Zahl.
  - Test: `bcrypt.Cost` des Dummy-Hashes ist gleich `bcrypt.DefaultCost`; zwei Zugriffe liefern denselben Hash.

**Proxy (Punkt 8)**

- **AC-11:** Given eine Proxy-Anfrage ohne `user_id` in der Query / When der Proxy sie an den Core weitergibt / Then ist die Query byte-identisch zur Anfrage (keine Umsortierung, keine Neu-Kodierung).
  - Test: `httptest`-Core zeichnet die Roh-Query auf; Query mit Sonderzeichen, `+`, `%20` und Mehrfachparametern kommt unverändert an.
- **AC-12:** Given eine Proxy-Anfrage mit `user_id` und weiteren Parametern / When der Proxy sie weitergibt / Then fehlt `user_id` in der Query beim Core, und alle übrigen Parameter bleiben in Reihenfolge und Kodierung erhalten (nur die `user_id`-Segmente werden entfernt, kein `Encode()`).
  - Test: `?a=1&user_id=x&b=%20z&user_id=y` kommt als `?a=1&b=%20z` beim Core an; `?user_id=x` allein ergibt eine leere Query ohne `?`.
- **AC-13:** Given zwei verschiedene angemeldete Nutzer A und B / When A eine Proxy-Anfrage mit `user_id=B` stellt / Then kommt beim Core kein `user_id` an, und die Antwort an A ist dieselbe wie ohne diesen Parameter.
  - Test: Zwei-Nutzer-Test über den echten Router und einen `httptest`-Core; Antwort von A mit `user_id=B` gleicht byte-genau der Antwort ohne den Parameter; beim Core wurde nie `user_id` gesehen. Beleg, dass die Antwort nutzerunabhängig bleibt: `api/routers/config.py` und `api/routers/compare.py:11` lesen kein `user_id`.

**Scheduler (Punkt 9)**

- **AC-14:** Given der Scheduler startet mit seinen registrierten Einträgen / When er die Startzeile loggt / Then nennt sie die tatsächliche Zahl der Cron-Einträge (heute 8) und der Statuszeilen (heute 9), berechnet aus den Einträgen und nicht hart kodiert.
  - Test: Scheduler-Test liest die Logzeile und vergleicht mit der Anzahl der registrierten Einträge; ein zusätzlicher Test-Eintrag verändert die Zahl mit.

**Env über Config (Punkt 7) — eigener, abtrennbarer Block (siehe Abtrennregel; SEVEN_*/STALWART_* sind begründete Scope-Erweiterung)**

- **AC-15:** Given die Env-Variablen `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`, `SEVEN_WEBHOOK_PATH_SECRET`, `SEVEN_WEBHOOK_SIGNING_KEY`, `STALWART_WEBHOOK_PATH_SECRET`, `STALWART_WEBHOOK_SECRET` sind unpräfixiert gesetzt (wie in den Env-Dateien von Prod und Staging) / When `config.Load` läuft / Then stehen die Werte in den sechs neuen Config-Feldern, und ein `GZ_`-präfixierter Wert hat Vorrang.
  - Test: Config-Test mit gesetzten unpräfixierten und präfixierten Namen; Felder tragen den erwarteten Wert.
- **AC-16:** Given keine der sechs Variablen ist gesetzt (Telegram bewusst nicht konfiguriert) / When der Server startet / Then startet er ohne Fehler, die Felder sind leer.
  - Test: `config.Load` ohne diese Variablen liefert keinen Fehler und leere Felder.
- **AC-17:** Given der echte Router ist mit einem Telegram-Secret aus der Config gebaut / When ein Telegram-Webhook eintrifft / Then antwortet er bei falschem Secret mit 403, bei richtigem Secret mit Erfolg und bei leerem Config-Wert mit 503 (fail-closed bleibt).
  - Test: Route-Test über den echten Router ohne `os.Setenv`, nur mit dem Config-Wert; drei Fälle.
- **AC-18:** Given der echte Router ist mit seven.io- und Stalwart-Werten aus der Config gebaut / When ein seven- oder Stalwart-Webhook eintrifft / Then antwortet er bei falschem Secret mit 403, bei richtigem Secret mit Erfolg und bei leerem Config-Wert mit 503.
  - Test: Route-Tests über den echten Router für seven.io (Pfad-Secret und Signatur) und Stalwart (Pfad-Secret und Secret); je drei Fälle.

**Nachweis auf Staging**

- **AC-19:** Given die Änderung ist auf Staging ausgerollt / When Login (gültig, falsches Passwort, unbekannter Nutzer), „Passwort vergessen" für einen unbekannten Nutzer und Telegram- sowie seven-Webhook mit falschem Secret aufgerufen werden / Then liefern sie 200 / 401 / 401, `ok`, und 403 (nicht 503).
  - Test: E2E-Verifikation gegen `https://staging.gregor20.henemm.com` mit Staging-`.env`; Status und Body werden protokolliert.

## Known Limitations

- Registrierung und Passkey-Registrierung verraten vergebene Namen und E-Mail-Adressen (siehe eigener Abschnitt); gebremst nur durch 5 Versuche pro Stunde je IP.
- Passkey-Login-Begin verrät Passkey-Besitz (nicht-discoverable WebAuthn).
- Die Timing-Angleichung ist eine Näherung: Die Tests sichern nur eine Untergrenze zu, keine Gleichheit mit dem Treffer-Zweig. Netzwerk-Jitter und Speicherzugriff bleiben messbar.
- Bei `en`-Nutzern gelten die Antworten wie bisher; die i18n-Fehlertexte aus #2676 sind nicht berührt.
- **Abgetrennt (Abtrennregel aus Scope/Estimated Scope angewendet am 2026-10-31, Test-LoC 1443 > 450):** Punkt 7 (Webhook-Secrets über `config.Config`, AC-15..AC-18) ist NICHT Teil dieser Scheibe, sondern Folgescheibe #2715 (fertiger Stand gesichert im Branch `feat-2163-s1b-webhook-config`). Die Webhooks lesen ihre Secrets bis dahin weiterhin per `os.Getenv`. AC-19 gilt für diese Scheibe nur für die Teile Login/Passwort-vergessen.
- Die tatsächlichen Testdateien heißen abweichend von der Tabelle im Test Plan: `proxy_user_id_strip_test.go` (handler), `proxy_user_id_two_users_test.go` (router), `startup_log_counts_test.go`, `auth_dummy_hash_test.go`, `register_conflict_characterization_test.go`.
- #2163 bleibt nach dieser Scheibe **offen** (Scheibe 2: Python-Pfadbauten ohne `VALID_USER_ID_RE`, `.env.tpl`). PR-Text daher „Refs #2163", nie „Closes".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; bestätigt ADR-0003 (Mandantentrennung)
- **Rationale:** Alle Änderungen sind Härtungen innerhalb bestehender Entscheidungen. Die Registrierungs-Enumeration bleibt wie in #2147 B1 freigegeben; eine spätere Gegenentscheidung bräuchte ein eigenes ADR mit „Abgelöst durch".

## Changelog

- 2026-10-31: Initial spec created (Scheibe 1 von #2163)
- 2026-10-31: Abtrennregel angewendet: Punkt 7 (AC-15..AC-18, Webhook-Secrets über `config.Config`) → Folgescheibe #2715, Branch `feat-2163-s1b-webhook-config`. Umgesetzt in Scheibe 1: Timing-Angleichung Login/Passwort-vergessen, `user_id`-Strip im `ProxyHandler`, korrekte Scheduler-Startzahlen. Testdateinamen weichen von der Tabelle ab (siehe Known Limitations).

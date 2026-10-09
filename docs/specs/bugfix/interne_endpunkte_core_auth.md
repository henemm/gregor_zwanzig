---
entity_id: interne_endpunkte_core_auth
type: bugfix
created: 2026-10-09
updated: 2026-10-09
status: draft
version: "1.0"
workflow: fix-2159-interne-endpunkte-secret
tags: [security, bugfix, go-api, python-core, auth, multi-user, issue-2159]
---

# Interne Go-Endpunkte per Geheimnis schützen (Python nach Go)

## Approval

- [ ] Approved

## Purpose

Die zwei internen Go-Endpunkte `POST /api/internal/telegram-connect` und `POST /api/internal/premium-sms-learn` sind heute nur dadurch geschützt, dass die Anfrage von demselben Server kommt und keinen nginx-Header trägt. Jeder lokale Prozess auf dem Server kann sie aufrufen; `premium-sms-learn` durchläuft dabei alle Nutzer. Der Fix schützt beide Endpunkte mit dem bereits vorhandenen gemeinsamen Geheimnis (`GZ_CORE_SHARED_SECRET`, Header `X-GZ-Core-Auth`, ADR-0062), das bisher nur in Richtung Go nach Python galt. Es ist Verteidigung in der Tiefe: nginx sperrt `/api/internal/` von außen bereits (`deny all`). Aus #2163 werden drei kleine Härtungen mitgenommen (Rate-Limiter, Secure-Cookie, Webhook-Vergleich). Dazu wird der Nebenbefund behoben, dass der Staging-Python-Dienst heute die Produktions-Go-API (Port 8090) statt der Staging-Go-API (8091) aufruft.

## Source

- **File:** `internal/handler/localhost_guard.go`
- **Identifier:** `requireLocalOnly` / `isProxiedRequest` (bleiben als zweite Schicht bestehen)
- **Secondary Files:** `internal/router/router.go` (Routen Z.153/164), `internal/coreauth/` (neu: Prüfung), `src/services/inbound_sms_reader.py`, `src/services/inbound_telegram_reader.py`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `config.Config.CoreSharedSecret` (`internal/config/config.go`) | module | Go-seitiges Geheimnis, Quelle für die Prüfung |
| `internal/coreauth/transport.go` (`HeaderName`) | module | Gemeinsamer Header-Name; neue Prüfung liegt daneben |
| `internal/middleware/status_token.go` | reference | Vorbild für konstantzeitigen Vergleich (sha256 + `subtle`) |
| `internal/middleware/auth.go` (`AuthMiddleware`, `SetSessionCookie`) | module | lässt `/api/internal/` durch; Secure-Flag wird angepasst |
| `internal/handler/auth_oauth.go` | module | Cookie `gz_oauth_state`, Secure-Flag wird angepasst |
| `internal/middleware/ratelimit.go` (`clientIP`) | module | `X-Real-IP` nur bei Loopback-Absender |
| `internal/handler/telegram_webhook.go` | module | Webhook-Secret konstantzeitig vergleichen |
| `api/main.py` (`_core_shared_secret()`) | reference | Vorbild: Secret aus Env, sonst Settings |
| `src/app/config.py` (`Settings`) | module | neues Feld `go_api_url` (`GZ_GO_API_URL`) |
| `tests/tdd/test_egress_single_dial_point.py` | test | Egress-Ratsche, Ausnahmen bisher nach `datei:ZEILE` |
| `docs/adr/0062-python-core-authentifiziert-gegenueber-go.md` | doc | Nachtrag Rückrichtung Python nach Go |
| `docs/reference/api_contract.md` (Z.234-235, ca. 3521-3560) | doc | Statuscodes 401/503 statt nur 403 |
| `/home/hem/gregor_zwanzig_staging/.env` | ops | Betriebsschritt `GZ_GO_API_URL=http://localhost:8091` |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/coreauth/verify.go` | CREATE | `Verify(r, secret)` konstantzeitig und Middleware `RequireCoreAuth(secret)`: leeres Secret 503, fehlend/falsch 401 |
| `internal/router/router.go` | MODIFY | Die zwei `/api/internal/*`-Routen mit `RequireCoreAuth(cfg.CoreSharedSecret)` umhüllen |
| `internal/handler/localhost_guard.go` | KEEP | `requireLocalOnly` bleibt zusätzlich in den Handlern (Handler-Tests unverändert) |
| `src/app/config.py` | MODIFY | Feld `go_api_url` (Env `GZ_GO_API_URL`, Default `http://localhost:8090`) |
| `src/lib/go_internal.py` | CREATE | Zentraler Python-nach-Go-Sende-Helfer: Basis-URL aus Config, Header `X-GZ-Core-Auth`; leeres Secret: nicht senden, loggen |
| `src/services/inbound_sms_reader.py` | MODIFY | Helfer nutzen; 401/403/503 vorübergehend (Lesezeiger rückt nicht vor), 409/429 weiterhin dauerhaft |
| `src/services/inbound_telegram_reader.py` | MODIFY | Helfer nutzen; 401/503 als `error` loggen |
| `tests/tdd/test_egress_single_dial_point.py` | MODIFY | `datei:ZEILE`-Ausnahmen entfallen; Helfer als benannter erlaubter Ausgang (Funktionsname), Höchstzahl gesenkt |
| `internal/middleware/ratelimit.go` | MODIFY | `X-Real-IP` nur bei Loopback-`RemoteAddr` auswerten |
| `internal/handler/telegram_webhook.go` | MODIFY | Webhook-Secret konstantzeitig vergleichen |
| `internal/middleware/auth.go`, `internal/handler/auth_oauth.go` | MODIFY | `Secure` aus Schema von `Config.PublicHost` statt `X-Forwarded-Proto`; `r.TLS`-Zweig bleibt |
| `api/routers/health.py` | MODIFY | Feld `go_api_url` in der Python-Health-Antwort (wirksamer Wert aus demselben Helfer wie die Aufrufe, Vorbild `public_host` #2272) |
| `internal/coreauth/verify_test.go` | CREATE | Einheitstests der Prüfung (401/503/200) |
| `internal/router/internal_routes_core_auth_test.go` | CREATE | Verdrahtung: echter Router, beide Routen, Store mit zwei Nutzern vorher/nachher gleich |
| `internal/middleware/ratelimit_test.go`, `internal/middleware/auth_test.go`, `internal/handler/telegram_webhook_test.go` | MODIFY | Spoofing, Secure-Matrix, Webhook-Vergleich |
| `tests/tdd/test_go_internal_helper.py` | CREATE | Helfer gegen echten lokalen HTTP-Server (Header, Basis-URL), Health-Feld `go_api_url` |
| `tests/tdd/test_inbound_telegram_connect_rejection.py` | CREATE | Telegram-Leser gegen echten lokalen HTTP-Server: 401/503 ⇒ `error`-Logzeile, kein Absturz, keine Erfolgsmeldung an den Nutzer |
| `tests/tdd/test_inbound_sms_learn_rejection.py` | CREATE | SMS-Leser gegen echten lokalen HTTP-Server: 401/403/503 Zeiger bleibt, 409/429 Zeiger rückt vor |
| `docs/adr/0062-python-core-authentifiziert-gegenueber-go.md` | MODIFY | Nachtrag Rückrichtung |
| `docs/reference/api_contract.md` | MODIFY | Statuscodes aktualisieren |

### Estimated Changes

- Files: ca. 11 produktiv, 9 Tests, 2 Doku
- LoC: produktiv +150/-20, Tests +250 (Doku zählt nicht; Limit 250 gilt für produktive Spec-Dateien)

## Implementation Details

- **Go-Prüfung:** `RequireCoreAuth(secret)` liegt im Paket `coreauth`. Ist `secret` leer, antwortet sie sofort 503, ohne den Header zu vergleichen (nie `"" == ""`). Sonst: Header fehlt oder weicht ab 401, Vergleich über sha256 plus `subtle.ConstantTimeCompare`. Erst bei Treffer läuft der Handler, der weiterhin `requireLocalOnly` anwendet. Die Middleware sitzt nur an den zwei `/api/internal/*`-Routen in `router.go`.
- **Python-Helfer:** Eine Funktion in `src/lib/go_internal.py` ist der einzige Ort, der die Go-API intern aufruft. Sie liest Basis-URL aus `Settings.go_api_url`, Secret wie `api/main.py:_core_shared_secret()` (Env, sonst Settings) und setzt `X-GZ-Core-Auth`. Leeres Secret: nicht senden, laut loggen.
- **SMS-Reader:** 401, 403 und 503 gelten als vorübergehend; der Lesezeiger rückt nicht vor, die Nachricht wird beim nächsten Lauf erneut versucht. 409 und 429 bleiben dauerhaft (Zeiger rückt vor).
- **Egress-Ratsche:** Statt zweier Zeilennummern wird der Helfer per Funktionsname als erlaubter Ausgang geführt; Zeilenverschiebungen brechen den Test nicht mehr.
- **Rate-Limiter:** `X-Real-IP` zählt nur, wenn `RemoteAddr` Loopback ist (nginx und SvelteKit kommen von dort, die Kette bleibt intakt).
- **Secure-Cookie:** `Secure` gilt, wenn `r.TLS != nil` oder `Config.PublicHost` mit `https://` beginnt. Gilt für `SetSessionCookie` und `gz_oauth_state`. Das SvelteKit-Login-Cookie bleibt unberührt.
- **Messbarkeit:** Die Python-Health-Antwort (`api/routers/health.py`) erhält das Feld `go_api_url`, gelesen über denselben Helfer, den die Aufrufe nutzen (keine zweite Ableitung, Vorbild `public_host` #2272), ohne Secret. So bleibt ein fehlender Staging-Eintrag nicht hinter dem Default 8090 unsichtbar.

### Deploy- und Betriebshinweise

- Go und Python müssen zusammen ausgerollt werden; das Deploy-Skript startet alle drei Dienste neu, ein Scheibenschnitt ist nicht nötig. Prod- und Staging-`.env` enthalten `GZ_CORE_SHARED_SECRET` bereits.
- **Betriebsschritt vor Staging-Validierung:** In `/home/hem/gregor_zwanzig_staging/.env` die Zeile `GZ_GO_API_URL=http://localhost:8091` ergänzen und `gregor-python-staging` neu starten. Prod braucht keinen Eintrag (Default 8090).
- Fehlkonfiguration äußert sich als 401/503 in den Logs der Leser; Telegram-`/start` und Premium-SMS-Lernen fielen dann aus. Deshalb Staging-Validierung mit Test-Verknüpfung.
- Out of Scope: Restpunkte aus #2163 (Enumeration, Timing, `os.Getenv`, ProxyHandler, Python-Pfadbauten, Log, `.env.tpl`) bleiben in #2163.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `internal/coreauth/verify_test.go`: GIVEN Secret gesetzt WHEN Loopback-Anfrage ohne Header an beide Routen THEN 401 und Store unverändert
- [ ] `internal/coreauth/verify_test.go`: GIVEN Secret gesetzt WHEN falscher Header THEN 401
- [ ] `internal/coreauth/verify_test.go`: GIVEN leeres Secret WHEN Anfrage mit leerem Header THEN 503
- [ ] `internal/coreauth/verify_test.go`: GIVEN korrekter Header von Loopback WHEN Aufruf THEN heutiges Verhalten
- [ ] `tests/tdd/test_go_internal_helper.py`: GIVEN echter lokaler HTTP-Server WHEN Helfer ruft THEN Header und konfigurierte Basis-URL kommen an
- [ ] `internal/router/internal_routes_core_auth_test.go`: GIVEN echter Router, Store mit zwei Nutzern WHEN beide Routen ohne/mit falschem/mit richtigem Header THEN 401/401/heutiges Verhalten, Store bei 401 unverändert
- [ ] `tests/tdd/test_inbound_sms_learn_rejection.py`: GIVEN Server antwortet 401 / 403 / 503 / 409 / 429 WHEN SMS-Reader verarbeitet THEN Zeiger bleibt / bleibt / bleibt / rückt vor / rückt vor
- [ ] `tests/tdd/test_inbound_telegram_connect_rejection.py`: GIVEN Server antwortet 401 / 503 WHEN Telegram-Leser verknüpft THEN `error`-Logzeile, kein Absturz, keine Erfolgsantwort an den Nutzer
- [ ] `internal/middleware/ratelimit_test.go`: GIVEN Nicht-Loopback-Absender mit X-Real-IP WHEN viele Anfragen THEN Zähler nach echter Absenderadresse
- [ ] `internal/handler/telegram_webhook_test.go`: GIVEN richtiges / falsches Secret WHEN Webhook THEN angenommen / abgelehnt
- [ ] `internal/middleware/auth_test.go`: Secure-Matrix (https-PublicHost, http-PublicHost, r.TLS)
- [ ] `tests/tdd/test_egress_single_dial_point.py`: Ratsche ohne Zeilennummern
- [ ] `tests/tdd/test_go_internal_helper.py`: GIVEN `GZ_GO_API_URL=http://localhost:8091` WHEN `/health` abgefragt THEN `go_api_url` == `http://localhost:8091`, kein Secret in der Antwort

## Acceptance Criteria

- **AC-1:** Given das Geheimnis ist gesetzt, When ein Prozess auf dem Server die Endpunkte „Telegram verknüpfen" und „Premium-SMS lernen" ohne das Geheimnis aufruft, Then antwortet das System mit 401 (nicht berechtigt) und kein Nutzer-Datensatz wird verändert (Test: `internal/router/internal_routes_core_auth_test.go` über den echten Router, Datenspeicher vorher/nachher gleich, mit zwei verschiedenen Nutzern).
- **AC-2:** Given das Geheimnis ist gesetzt, When ein Aufruf ein falsches Geheimnis mitschickt, Then antwortet das System mit 401 und verändert nichts (Tests: `internal/coreauth/verify_test.go`, `internal/router/internal_routes_core_auth_test.go`).
- **AC-3:** Given auf der Go-Seite ist kein Geheimnis konfiguriert, When ein Aufruf einen leeren oder gar keinen Header schickt, Then antwortet das System mit 503 (Dienst nicht eingerichtet) und lässt nie „leer gleich leer" als Treffer gelten (Test: `internal/coreauth/verify_test.go`).
- **AC-4:** Given das Geheimnis stimmt und der Aufruf kommt vom Server selbst, When beide Endpunkte aufgerufen werden, Then verhalten sie sich wie bisher, inklusive der bestehenden Ablehnung von Aufrufen mit nginx-Header (Tests: `internal/router/internal_routes_core_auth_test.go` und die bestehenden Handler-Tests unverändert grün).
- **AC-5:** Given eine Basis-Adresse der Go-API ist konfiguriert (`GZ_GO_API_URL`, sonst `http://localhost:8090`), When der Telegram- oder der SMS-Leser die Go-API aufruft, Then geht die Anfrage an genau diese Adresse und trägt das Geheimnis im Header `X-GZ-Core-Auth` (Test: `tests/tdd/test_go_internal_helper.py` gegen einen echten lokalen Testserver).
- **AC-6:** Given die Go-API lehnt einen Premium-SMS-Aufruf mit 401, 403 oder 503 ab, When der SMS-Leser die Nachricht verarbeitet, Then geht die Nachricht nicht verloren, weil der Lesezeiger nicht weiterrückt; bei 409 oder 429 wird sie weiterhin als endgültig erledigt behandelt (Test: `tests/tdd/test_inbound_sms_learn_rejection.py` gegen einen echten lokalen Testserver).
- **AC-7:** Given eine Anfrage kommt nicht vom Server selbst und trägt einen erfundenen `X-Real-IP`-Header, When die Begrenzung der Anfragen pro Absender zählt, Then zählt sie nach der echten Absenderadresse; bei Anfragen von nginx oder dem Frontend (Server selbst) wird `X-Real-IP` weiterhin ausgewertet (Test: `internal/middleware/ratelimit_test.go`).
- **AC-8:** Given der Telegram-Webhook ist mit einem Geheimnis geschützt, When Telegram das richtige Geheimnis schickt, Then wird die Nachricht angenommen, bei falschem oder fehlendem Geheimnis abgelehnt; der Vergleich läuft in konstanter Zeit, damit Antwortzeiten nichts verraten (Test: `internal/handler/telegram_webhook_test.go`).
- **AC-9:** Given `GZ_PUBLIC_HOST` beginnt mit `https://`, When ein Anmelde-Cookie (Sitzung oder `gz_oauth_state`) gesetzt wird, Then ist es als „nur über verschlüsselte Verbindung" (Secure) markiert, auch ohne `X-Forwarded-Proto`; bei `http://` ohne TLS ist es nicht Secure; bei einer echten TLS-Verbindung ist es immer Secure (Test: `internal/middleware/auth_test.go`).
- **AC-10:** Given die Prüfung „nur ein Ausgangstor ins Netz" (Egress-Ratsche), When Quelltext-Zeilen verschoben werden, Then bleibt sie grün, weil der Python-Helfer als benannte Funktion und nicht mehr per Dateizeile erlaubt ist (Test: `tests/tdd/test_egress_single_dial_point.py`).
- **AC-11:** Given der Staging-Dienst läuft, When man die Health-Antwort des Python-Dienstes (`/health`, Feld `go_api_url`) liest, Then steht dort die wirksame Go-Basis-Adresse (ohne Geheimnis), sodass ein fehlender Staging-Eintrag (`http://localhost:8091`) sichtbar wird statt hinter dem Standard 8090 zu verschwinden (Test: `tests/tdd/test_go_internal_helper.py`; Staging-Messung nach dem Betriebsschritt).
- **AC-12:** Given ADR-0062 und der API-Vertrag, When der Fix ausgeliefert ist, Then dokumentiert ADR-0062 die Rückrichtung Python nach Go und `docs/reference/api_contract.md` nennt 401/503 für die zwei internen Endpunkte (Doku-Prüfung im Review, `# doc-compliance-test` nicht erforderlich).
- **AC-13:** Given die Go-API lehnt einen Telegram-Verknüpfungsaufruf mit 401 oder 503 ab, When der Telegram-Leser einen `/start`-Befehl verarbeitet, Then protokolliert er die Ablehnung als Fehler, stürzt nicht ab und meldet dem Nutzer keine erfolgreiche Verknüpfung (Test: `tests/tdd/test_inbound_telegram_connect_rejection.py` gegen einen echten lokalen Testserver).

## Expected Behavior

- **Input:** `POST /api/internal/telegram-connect` bzw. `POST /api/internal/premium-sms-learn` mit oder ohne Header `X-GZ-Core-Auth`.
- **Output:** Go-Secret leer ⇒ 503; Header fehlt/falsch ⇒ 401; Header richtig ⇒ unverändertes heutiges Verhalten (inkl. 403 bei nginx-Header durch `requireLocalOnly`).
- **Side effects:** Bei 401/503 keinerlei Schreibzugriff auf Nutzerdaten. Der SMS-Leser behandelt 401/403/503 als vorübergehend (Lesezeiger bleibt, erneuter Versuch beim nächsten Lauf), 409/429 als endgültig (Zeiger rückt vor).

## Known Limitations

- Restpunkte aus #2163 (Enumeration, Timing, `os.Getenv`, ProxyHandler, Python-Pfadbauten, Log, `.env.tpl`) sind nicht Teil dieses Fixes.
- Das vom SvelteKit-Login selbst gesetzte Session-Cookie (`secure` per `NODE_ENV`) bleibt unberührt.
- Der Staging-Eintrag `GZ_GO_API_URL` ist ein Betriebsschritt außerhalb des Repos; ohne ihn ruft Staging-Python weiter Port 8090 und scheitert dort am abweichenden Geheimnis — sichtbar über `/health` (`go_api_url`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0062 (Nachtrag)
- **Rationale:** ADR-0062 (Python-Core authentifiziert gegenüber Go) wird um die Rückrichtung Python ⇒ Go ergänzt (Nachtrag, kein neues ADR): dasselbe Geheimnis, derselbe Header, gleiche Statuscode-Logik (401 fehlend/falsch, 503 nicht konfiguriert), ein zentraler Sende-Ort je Seite. Die Grundsatzentscheidung wird erweitert, nicht abgelöst.

## Changelog

- 2026-10-09: AC-13 Telegram-Leser-Ablehnung ergänzt (PO-Briefing-Anmerkung)
- 2026-10-09: Messort AC-11 festgelegt (Python-`/health`), Verdrahtungstest über echten Router, SMS-Ablehnungstest getrennt
- 2026-10-09: Initial spec created (Issue #2159, Workflow fix-2159-interne-endpunkte-secret)

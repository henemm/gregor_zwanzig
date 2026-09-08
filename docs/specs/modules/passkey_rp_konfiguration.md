---
entity_id: passkey_rp_konfiguration
type: bugfix
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
tags: [go, tooling, e2e, auth, webauthn, passkey, config]
---

<!-- Issue #2130 (neu geschnitten, Scheibe A von Epic #2127) -->

# Passkey-RP-Konfiguration, Discoverable-Fix und Bewachung

## Approval

- [x] Approved — PO (Henning), 2026-09-08, im Workflow `feat-2130-passkey-anmeldung`

## Purpose

Passkey-Anmeldung wurde nie benutzbar ausgeliefert: Produktion sendet dem Browser `rpId:
"localhost"`, was WebAuthn clientseitig mit `SecurityError` abbricht, bevor irgendein Request
das Backend erreicht (#878, nie geklärt, im Streichdurchgang #1485 versehentlich gestrichen
statt gelöst). Diese Spec macht Passkey erstmals real funktionsfähig — RP-ID/Origins werden aus
der ohnehin vorhandenen `PublicHost`-Konfiguration abgeleitet statt über separate, leicht
vergessene ENV-Variablen gepflegt — und sorgt dafür, dass eine künftige Fehlkonfiguration nicht
wieder drei Monate unbemerkt bleibt: sichtbar über `/api/health`, geprüft vom
Post-Deploy-Selbsttest, und mit einem echten Browser-Nachweis per virtuellem WebAuthn-Authentifikator
abgesichert. Zusätzlich behebt sie einen zweiten, unabhängig verifizierten Defekt: neu angelegte
Passkeys fordern keine "discoverable"-Eigenschaft an und tauchen deshalb im
Autofill-Auswahldialog womöglich gar nicht auf.

## Source

- **File:** `internal/config/config.go:39,45-47` — `PublicHost` als Ableitungsquelle für
  `WebAuthnRPID`/`WebAuthnRPOrigins`
- **Identifier:** `Config` (struct), `Load()`

### Weitere betroffene Dateien

- **File:** `internal/config/config.go` (ERWEITERT) — Ableitungslogik: wenn `GZ_WEBAUTHN_RP_ID`
  bzw. `GZ_WEBAUTHN_RP_ORIGINS` leer sind, RP-ID = Hostanteil von `PublicHost`, RP-Origin =
  Schema+Host von `PublicHost`. Explizite Variablen bleiben als Override erhalten.
- **File:** `cmd/server/main.go:92-101` (ERWEITERT) — `webauthn.Config.AuthenticatorSelection`
  erhält `ResidentKey: protocol.ResidentKeyRequirementPreferred` (global für alle
  Registrierungs-Endpunkte).
- **File:** `internal/handler/passkey.go:478` (ERWEITERT) — `/register/public/begin` ruft
  `BeginRegistration(...)` zusätzlich mit
  `webauthn.WithResidentKeyRequirement(protocol.ResidentKeyRequirementRequired)`
  (`registration_opt.go:40`), weil ohne auffindbares Credential die passwortlose
  Neuregistrierung strukturell keinen Wiedereinstieg erlaubt.
- **File:** `internal/handler/proxy.go:17-42` (ERWEITERT) — `HealthHandler` bekommt einen
  zusätzlichen Parameter (effektive RP-ID) und liefert das Feld `webauthn_rpid` im
  `/api/health`-JSON.
- **File:** `internal/router/router.go:127` (ERWEITERT) — Aufruf von `handler.HealthHandler(...)`
  reicht die aufgelöste RP-ID mit durch.
- **File:** `.claude/hooks/prod_selftest.py:358` (ERWEITERT) — `_check_health()` vergleicht
  `webauthn_rpid` aus der Antwort gegen den Hostnamen von `PROD_BASE` (`gregor20.henemm.com`,
  `prod_selftest.py:59`) und liefert bei Abweichung `False`.
- **File:** `frontend/e2e/start-preview.sh:12` (ERWEITERT) — Origin `http://localhost:4173` (der
  vom lokalen Preview-Server tatsächlich genutzte Port) wird als zusätzlicher erlaubter Origin
  für den lokalen E2E-Lauf gesetzt, weil go-webauthn Origins exakt inklusive Port prüft
  (`protocol/client.go:219-229`).
- **File:** `frontend/e2e/passkey-regression.spec.ts` **(NEU)** — Playwright-Test mit virtuellem
  CDP-Authentifikator, der Registrierung und Login vollständig gegen den echten lokalen
  Go-Server fährt, ohne UI-Abhängigkeit (`page.evaluate()` + `fetch()` gegen die Passkey-Routen).
- **File:** `.env.example` (ERWEITERT) — Kommentarzeile, dass ein frischer lokaler Checkout
  `GZ_PUBLIC_HOST` explizit auf einen lokalen Wert setzen muss, weil `PublicHost` selbst den
  Prod-Default trägt (`config.go:39`) und die Ableitung sonst lokal denselben Fehler in
  umgekehrter Richtung erzeugt.

> **Schicht-Hinweis:** Konfigurationsableitung und ResidentKey-Fix liegen ausschließlich in der
> **Go-API** (`internal/config/`, `cmd/server/`, `internal/handler/`). Die Bewachung liegt in
> **Tooling** (`.claude/hooks/prod_selftest.py`, kein Anwendungscode). Der Nachweis liegt in
> **E2E** (`frontend/e2e/`, Playwright gegen den echten Go-Server, keine SvelteKit-UI-Komponente).
> Bestätigung per Grep: keine der oben gelisteten Dateien liegt unter `frontend/src/` — diese
> Spec ändert **keine** UI (siehe „Was sich NICHT ändert").

## Estimated Scope

- **LoC:** ~250-330 (Analyse-Schätzung: Backend ~90-130, Tooling ~30-50, E2E ~100-150).
  Innerhalb des Standard-Limits von 250 nur knapp möglich — `loc_limit_override 500` bei Bedarf
  ziehen, siehe `CLAUDE.md` „LoC-Limit".
- **Files:** ~7 (config.go, main.go, passkey.go, proxy.go, router.go, prod_selftest.py,
  start-preview.sh) + 1 neue Testdatei + `.env.example`
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go-webauthn/webauthn v0.17.4` | go module | Liefert `webauthn.Config`, `AuthenticatorSelection`, `WithResidentKeyRequirement` — die Bibliothek, deren Zero-Value-Verhalten den Discoverable-Defekt erzeugt |
| `internal/handler/passkey.go` | go package | Bestehende 9 Handler (register/login/discoverable/register-public/delete) — funktionsfähig, werden hier nur an der Registrierungs-Option erweitert, nicht neu geschrieben |
| `internal/handler/auth.go:319,791` | go package | Nutzt `PublicHost` bereits für Verifikations-/Reset-Mail-Links — dieselbe Konfigurationsgröße, keine neue Wahrheit |
| `.claude/hooks/prod_selftest.py::_check_health` | tooling | Bestehende Health-Prüfung (Phase 2), wird um den RP-ID-Vergleich erweitert statt eine neue Gate-Phase einzuführen |
| ADR-0060 | adr | „Dauerhafte Anmeldung mit dateibasierter Sitzungsliste" — Cookie-Format, das `issueSession()` für alle vier Passkey-Pfade ausstellt; diese Spec ändert das Cookie-Verhalten nicht |
| `docs/reference/api_contract.md` §19 | reference | Aktueller, korrekter Vertrag aller 9 Passkey-Routen inkl. Cookie-Format; Referenz statt der veralteten `passkey_webauthn.md` |
| Server-`.env` (Prod + Staging) | ops (außerhalb Repo) | `GZ_PUBLIC_HOST` muss für Staging tatsächlich gesetzt sein, damit die Ableitung dort `staging.gregor20.henemm.com` statt des Prod-Defaults ergibt — Umsetzung im selben Arbeitsschritt, siehe #2200 |

## Implementation Details

### 1. Config-Ableitung statt zweiter Wahrheit

In `internal/config/config.go` nach `Load()`: wenn `WebAuthnRPID`/`WebAuthnRPOrigins` nach dem
`envconfig.Process`-Lauf noch ihren bisherigen Default tragen (bzw. explizit leer sind — je nach
Umsetzung der Default-Erkennung), werden sie aus `PublicHost` abgeleitet: RP-ID = geparster
Hostanteil, RP-Origin = Schema+Host unverändert. Explizit gesetzte `GZ_WEBAUTHN_RP_ID`/
`GZ_WEBAUTHN_RP_ORIGINS` bleiben Override für lokale Entwicklung, in der `PublicHost` selbst nicht
auf `localhost` zeigen soll.

### 2. Auffindbare Passkeys (Discoverable Credentials)

`cmd/server/main.go:97-101`: `webauthn.Config.AuthenticatorSelection` erhält global
`ResidentKey: protocol.ResidentKeyRequirementPreferred`. Zusätzlich in
`internal/handler/passkey.go:478` (`/register/public/begin`, passwortlose Neuregistrierung)
explizit `webauthn.WithResidentKeyRequirement(protocol.ResidentKeyRequirementRequired)`, weil dort
ein nicht-discoverables Credential den Nutzer strukturell handlungsunfähig machen würde (kein
Passwort, kein auffindbarer Passkey = kein Wiedereinstieg).

### 3. Beobachtbarkeit über den bestehenden Health-Endpunkt

`internal/handler/proxy.go`: `HealthHandler` bekommt einen zusätzlichen String-Parameter
(effektive, aufgelöste RP-ID) und schreibt ihn als `webauthn_rpid` ins JSON. Kein neuer
Endpunkt, keine neue Route — Erweiterung des bestehenden `/api/health`.

### 4. Bewachung im Post-Deploy-Selbsttest

`.claude/hooks/prod_selftest.py::_check_health()` liest `webauthn_rpid` aus der bereits
geholten `/api/health`-Antwort und vergleicht ihn gegen `urlparse(PROD_BASE).hostname`
(`gregor20.henemm.com`). Weicht er ab oder fehlt er, liefert die Funktion `False` mit
entsprechender Nachricht — Phase 2 des Selbsttests schlägt fehl, der Deploy gilt als FAIL.
Bewusst **nicht** über die generische AC-Probe (`_probe_ac()`), weil diese nur GET-Requests
gegen Status-Codes prüft und der Passkey-Endpunkt POST-only ist — genau die Lücke, die den
Ausfall drei Monate verdeckt hat.

### 5. Regressionsnachweis per virtuellem Authentifikator

`frontend/e2e/passkey-regression.spec.ts` (neu): `context.newCDPSession(page)` →
`WebAuthn.enable` → `WebAuthn.addVirtualAuthenticator({protocol:'ctap2', transport:'internal',
hasResidentKey:true, hasUserVerification:true, isUserVerified:true})`. Die Zeremonie läuft per
`page.evaluate()` gegen den echten lokalen Go-Server (`GZ_API_BASE=http://localhost:8091`, aus
`frontend/e2e/start-preview.sh`): `fetch('/api/auth/passkey/register/begin')` →
`navigator.credentials.create(...)` → `fetch('.../finish')`, anschließend derselbe Ablauf für
`login`/`discoverable`. Der Test braucht keine wiederhergestellte UI und ist damit unabhängig von
der (in dieser Spec bewusst ausgeklammerten) Frontend-Arbeit.

## Expected Behavior

- **Input:** Serverstart mit `GZ_PUBLIC_HOST` gesetzt (Prod/Staging) bzw. Default (lokal); Browser
  führt WebAuthn-Registrierung/-Login gegen die Passkey-Routen aus; Post-Deploy-Selbsttest ruft
  `/api/health`.
- **Output:** `/api/auth/passkey/*/begin`-Antworten tragen eine RP-ID, die zur aufrufenden Origin
  passt (kein `SecurityError` im Browser mehr); `/api/health` liefert `webauthn_rpid` mit dem
  effektiven Wert; neu angelegte Passkeys sind auffindbar (discoverable).
- **Side effects:** Keine Änderung an Sessions/Cookie-Format, keine Änderung an Passwort- oder
  Magic-Link-Anmeldung, keine neue Abbruchbedingung beim Serverstart.

## Acceptance Criteria

- **AC-1:** Given der Server läuft mit `GZ_PUBLIC_HOST=https://gregor20.henemm.com` und ohne
  explizit gesetzte `GZ_WEBAUTHN_RP_ID` / `GZ_WEBAUTHN_RP_ORIGINS` / When ein Client
  `POST /api/auth/passkey/discoverable/begin` aufruft / Then antwortet der Server mit
  `rpId: "gregor20.henemm.com"` im `publicKey`-Objekt — nicht mehr mit `localhost`.
  - Test: Kern-Schicht, Go-Test gegen die durch `config.Load()` erzeugte reale Default-Kette
    (nicht gegen eine handgebaute Test-`webauthn.New(...)`-Instanz wie die bestehenden 31 Tests),
    prüft den JSON-Wert von `rpId` in der Antwort.

- **AC-2:** Given ein Nutzer registriert im echten Browser (via CDP-virtuellem Authentifikator)
  einen Passkey und meldet sich anschließend über die Autofill-Anmeldung (`discoverable`-Weg)
  an / When die vollständige Registrierungs- und Anmelde-Zeremonie durchläuft, so wie sie mit der
  alten `localhost`-RP-ID am `SecurityError` gescheitert wäre / Then erhält der Browser bei
  Registrierung und Login jeweils eine erfolgreiche Antwort und der Nutzer bekommt eine gültige
  Sitzung (Session-Cookie gesetzt) — die Zeremonie schlägt nicht mehr clientseitig fehl.
  - Test: Live-/Browser-Schicht, Playwright `passkey-regression.spec.ts`, echter Chromium mit CDP
    `WebAuthn.addVirtualAuthenticator` gegen den echten lokalen Go-Server, keine UI-Komponente
    nötig (Ablauf per `page.evaluate()`/`fetch()`).

- **AC-3:** Given ein Nutzer hat einen Passkey über `/api/auth/passkey/register/begin` bzw.
  `/api/auth/passkey/register/public/begin` angelegt / When er sich anschließend über
  `discoverable/begin` **ohne Angabe eines Benutzernamens** anmeldet (die Anfrage enthält keine
  Liste erlaubter Credentials) / Then gelingt die Anmeldung und er erhält eine gültige Sitzung —
  was nur möglich ist, wenn der Passkey auffindbar gespeichert wurde. Geprüft wird die Wirkung,
  nicht dass ein `residentKey`-Feld gesendet wurde.
  - Test: Live-/Browser-Schicht, derselbe Playwright-Test. Zwei Belege in einem Lauf: (1) der
    Anmeldeweg ohne Benutzername gelingt, (2) CDP `WebAuthn.getCredentials` weist das gespeicherte
    Credential als `isResidentCredential: true` aus. Ausdrücklich **nicht** über
    `mediation: 'conditional'` geprüft — der Autofill-Dialog verhält sich im automatisierten
    Browser unzuverlässig und wäre ein wackliger Beleg für eine harte Zusicherung.

- **AC-4:** Given die Prod-`.env` hätte fälschlich keine oder eine falsche `GZ_PUBLIC_HOST`
  gesetzt, sodass die effektive Passkey-RP-ID vom tatsächlichen Produktions-Hostnamen abweicht /
  When der Post-Deploy-Selbsttest (`prod_selftest.py`) nach einem Deploy läuft / Then meldet der
  Health-Check-Schritt einen Fehler (kein `True`) und der Gesamt-Selbsttest schlägt fehl (Exit
  ungleich 0) — die Fehlkonfiguration bleibt nicht mehr unbemerkt wie beim ursprünglichen Ausfall.
  - Test: Kern-Schicht, Python-Test gegen `_check_health()` mit einem gestubbten `/api/health`,
    der ein von `gregor20.henemm.com` abweichendes `webauthn_rpid` liefert; erwartet `(False, ...)`
    als Rückgabe.

- **AC-5:** Given `GZ_PUBLIC_HOST` ist unbrauchbar gesetzt (leer, ohne Schema oder syntaktisch
  kaputt), sodass sich daraus keine Passkey-Domain ableiten lässt / When die Konfiguration geladen
  wird / Then liefert die Ableitung einen brauchbaren Ersatzwert statt eines leeren, protokolliert
  den Fehlgriff sichtbar, und die Anwendung startet vollständig — die Passwort-Anmeldung bleibt
  erreichbar. Eine falsch eingetragene öffentliche Adresse darf niemals den gesamten Dienst am
  Start hindern.
  - Test: Kern-Schicht, Go-Test über mehrere kaputte `PublicHost`-Werte: die Ableitung gibt in
    keinem Fall eine leere RP-ID zurück, und die daraus gebaute WebAuthn-Instanz lässt sich ohne
    Fehler erzeugen (womit die bestehende Startprüfung in `cmd/server/main.go:103` nicht
    auslösen kann).
  - Abgrenzung: Die **bestehende** Startprüfung (`log.Fatalf` bei fehlerhafter
    WebAuthn-Initialisierung, `cmd/server/main.go:103`) bleibt unverändert bestehen. Sie wird
    nicht entfernt — das würde bedeuten, alle neun Passkey-Endpunkte zusätzlich gegen einen
    leeren Zustand absichern zu müssen, ohne dass dem ein realer Fehlerfall gegenübersteht. AC-5
    sichert stattdessen zu, dass die **neu eingeführte Ableitung** diese Prüfung nicht auslösen
    kann.

## Known Limitations

- Kein UI-Zugang zu Passkey in dieser Scheibe — abgetrennt nach #2199.
- Staging-`.env` (`GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com`) ist eine separate
  Server-Änderung außerhalb dieses Repos (Ticket C, #2200) und wird von dieser Spec nicht
  automatisch erledigt — ohne sie bleibt Staging auf dem Prod-Default und Passkey funktioniert
  dort weiterhin nicht (Nebenbefund: Staging-Mails verlinken dann ebenfalls fälschlich auf Prod).
- Das Verhalten realer Plattform-Authentifikatoren (Face ID, Windows Hello) ist mit dem
  virtuellen CDP-Authentifikator nicht abgedeckt — nur die Protokoll-Zeremonie und die
  Server-Konfiguration.
- `WebAuthnID()` gibt weiterhin den Klartext-Username als User-Handle zurück
  (`internal/model/user.go:68`) — kein Sicherheitsloch, aber Abweichung von Best Practice; kein
  Teil dieser Spec, Kandidat für #1199.

## Was sich NICHT ändert

- **Passwort-Anmeldung** (`POST /api/auth/login`) und **Magic-Link-Anmeldung** bleiben in Verhalten
  und Vertrag unverändert.
- **Keine neue Abbruchbedingung beim Serverstart.** Ein fehlerhafter RP-ID-Wert darf nie alle
  Anmeldewege mitreißen; die Ableitung liefert stattdessen einen Ersatzwert und protokolliert
  sichtbar (AC-5). Die **bestehende** Startprüfung in `cmd/server/main.go:103` bleibt unangetastet.
- **Keine UI-Änderung.** Weder `frontend/src/routes/login/+page.svelte` noch
  `frontend/src/routes/account/+page.svelte` werden angefasst — die entfernte Passkey-UI (Commit
  `c09172f5`) bleibt entfernt und ist Gegenstand eines eigenen, nachgelagerten Issues (#2199).
- **Kein neues Cookie-Format.** `issueSession()` (`internal/handler/auth.go:128-146`) und das
  4-teilige Cookie aus ADR-0060 bleiben unverändert; diese Spec rührt an keiner Stelle die
  Session-Ausstellung an.

## Auslieferung

Die Umsetzung dieser Spec macht den Konfigurationsfehler **selbstheilend für Prod**, weil
`PublicHost` dort bereits korrekt gesetzt ist (`GZ_PUBLIC_HOST` fehlt aktuell in der Prod-`.env`,
der Default `https://gregor20.henemm.com` aus `config.go:39` trifft dort zufällig zu). Für
**Staging** ist eine zusätzliche, außerhalb dieses Repos liegende Änderung nötig:
`GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com` muss in
`/home/hem/gregor_zwanzig_staging/.env` gesetzt werden (Server-`.env`, kein Repo-Commit) — dieser
Schritt ist als eigenes, kleines Ticket abgetrennt (#2200) und muss im selben Arbeitsschritt wie
dieser Fix erledigt werden, sonst bleibt Staging-Passkey weiterhin funktionslos. Der übliche Weg
PR → CI → Staging-Auto-Deploy → `deploy-gregor-prod.sh` deckt Server-`.env`-Änderungen nicht ab;
AC-4 stellt sicher, dass eine vergessene oder falsche Prod-`.env` nicht mehr unbemerkt bleibt.

## Test Plan

### Kern-Schicht (deterministisch, ohne Netz/Browser)

- Go-Test: `config.Load()`-Ableitung liefert bei leeren expliziten WebAuthn-Variablen die aus
  `PublicHost` abgeleitete RP-ID/Origins (AC-1). Verfälschung, die dieser Test fängt: die
  Ableitungslogik entfernen oder umkehren (Origin statt Hostanteil in `rpId` schreiben) — der Test
  wird rot, weil er den JSON-Wert prüft, nicht nur, dass ein Feld existiert.
- Go-Test: `AuthenticatorSelection.ResidentKey` steht in der von `/register/begin` und
  `/register/public/begin` erzeugten `BeginRegistration`-Antwort auf `"preferred"` bzw.
  `"required"`. Verfälschung, die dieser Test fängt: die `WithResidentKeyRequirement`-Option
  entfernen — der Test wird rot, weil er den tatsächlich gesendeten Wert liest, nicht nur, dass
  die Funktion aufgerufen wird.
- Go-Test: Die Ableitung liefert für kaputte `PublicHost`-Werte (leer, ohne Schema, syntaktisch
  ungültig) nie eine leere RP-ID, und `webauthn.New()` mit dem Ergebnis wirft keinen Fehler
  (AC-5). Verfälschung, die dieser Test fängt: eine Ableitung, die bei unparsbarer Adresse still
  einen leeren String durchreicht — der Test wird rot, weil er das Ergebnis der Ableitung UND die
  daraus gebaute Instanz prüft, nicht nur, dass eine Prüfung im Code steht.
- Python-Test: `_check_health()` liefert `False`, wenn `webauthn_rpid` von
  `gregor20.henemm.com` abweicht oder fehlt (AC-4). Verfälschung, die dieser Test fängt: den
  Vergleich entfernen oder ihn nur loggen statt `False` zurückzugeben — der Test wird rot, weil er
  den Rückgabewert prüft, nicht nur, dass eine Log-Zeile geschrieben wird.

### Live-/Browser-Schicht (nur `/e2e-verify` bzw. lokal vor Commit)

- Playwright `passkey-regression.spec.ts`: vollständige Registrierung + Discoverable-Login mit
  virtuellem CDP-Authentifikator gegen den echten lokalen Go-Server (AC-2, AC-3). Verfälschung,
  die **nur** diese Ebene fängt: eine falsche RP-Origin (z.B. Port 5173 statt 4173 in
  `start-preview.sh`) — kein Kern-Test kann das fangen, weil der Fehler ausschließlich im
  Browser vor dem ersten HTTP-Request auftritt (genau der Mechanismus, der den Prod-Ausfall drei
  Monate verdeckt hat).
- Optional, keine Pflicht: Staging-Smoke gegen `/api/auth/passkey/discoverable/begin` hinter
  nginx-Basic-Auth (Muster: `frontend/e2e/konto-naechste-pruefung.staging.setup.ts:24-28`) —
  zusätzliche Bestätigung nach Setzen von `GZ_PUBLIC_HOST` auf Staging (#2200), kein Gate dieser
  Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — diese Spec ändert weder Kanäle noch Provider noch Datenmodell/
  Persistenz noch Auth-Paradigma; sie korrigiert eine fehlerhafte Konfigurationsableitung
  innerhalb des durch ADR-0060 bereits festgelegten Session-Modells.
- **Rationale:** ADR-0060 legt das Cookie-Format und die Sitzungsausstellung fest — diese bleiben
  unverändert (siehe „Was sich NICHT ändert"). Die Config-Ableitung ist eine Implementierungs-
  entscheidung ohne architektonische Tragweite über diese Spec hinaus.

## Referenzen

- Issue #2130 (dieser Scope, neu geschnitten aus der ursprünglichen Issue-Beschreibung)
- Abgetrennt: #2199 (Passkey-UI: erster Weg auf dem Handy, Autofill, Konto-Karte, abweisbares
  Angebot), #2200 (`GZ_PUBLIC_HOST` auf Staging setzen)
- Vorgeschichte: #878 (Root-Cause-Klärung, nie abgearbeitet, im Streichdurchgang #1485
  fälschlich gestrichen), #450 (Passkey V1)
- ADR-0060 (Session-/Cookie-Format, unverändert)
- `docs/context/feat-2130-passkey-anmeldung.md` — vollständige Bestandsaufnahme und Analyse,
  Faktenquelle dieser Spec
- `docs/reference/api_contract.md` §19 (ab Zeile 2574) — aktueller Passkey-Routenvertrag

## Changelog

- 2026-09-08: Initial spec created

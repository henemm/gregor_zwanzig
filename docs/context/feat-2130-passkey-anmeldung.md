# Context: feat-2130-passkey-anmeldung

Issue: #2130 (Scheibe 3 zu Epic #2127) · Track: Full Process · erstellt 2026-09-08

## Request Summary

Auf dem Handy soll der Passkey der erste angebotene Anmeldeweg sein (Passwort und Magic-Link
bleiben darunter erreichbar), wer sich mit Passwort anmeldet und keinen Passkey hat bekommt
einmalig ein abweisbares Angebot, und Passkeys sind in der Konto-Ansicht sichtbar und einzeln
entfernbar.

**Korrektur zur Issue-Beschreibung (PO-Hinweis 2026-09-08):** #2130 behauptet, Passkey sei
"bereits vollständig gebaut" und es fehle allein die Herausstellung. Das ist falsch. Passkey hat
in der Praxis **nie funktioniert**, und die Ursache war bis heute nie geklärt (#878 Schritt 1
"Root Cause klären" wurde nie abgearbeitet, das Issue wurde am 2026-08-04 im Streichdurchgang
#1485 **gestrichen**, nicht erledigt).

## Root Cause — gemessen, nicht vermutet

Am Produktivsystem gemessen (2026-09-08):

```
POST https://gregor20.henemm.com/api/auth/passkey/discoverable/begin
→ {"publicKey":{"challenge":"…","timeout":300000,"rpId":"localhost"},"mediation":"conditional"}
```

Die Produktion liefert dem Browser **`rpId: "localhost"`**. Nach WebAuthn-Spec muss die RP-ID
gleich der Origin-Domain sein oder ein registrierbares Domain-Suffix davon; `localhost` ist von
`gregor20.henemm.com` aus keines von beidem. Der Browser bricht `navigator.credentials.create()`
bzw. `.get()` mit `SecurityError` ab — **clientseitig, bevor irgendein Request das Backend
erreicht**. Es konnte also nie ein Passkey registriert und nie einer benutzt werden.

Herkunft des Werts:

| Ort | Befund |
|---|---|
| `internal/config/config.go:45-47` | `WebAuthnRPID` default `"localhost"`, `WebAuthnRPOrigins` default `"http://localhost:5173"` |
| `cmd/server/main.go:92-101` | `webauthn.New()` übernimmt die Config unverändert |
| `/home/hem/gregor_zwanzig/.env` (Prod) | `GZ_WEBAUTHN_RP_ID` / `GZ_WEBAUTHN_RP_ORIGINS` **nicht gesetzt** |
| `/home/hem/gregor_zwanzig_staging/.env` | ebenfalls **nicht gesetzt** |
| systemd-Units + Drop-ins, `.env.example` | ebenfalls nicht gesetzt, keine Vorlage vorhanden |

**Der Fix ist reine Konfiguration, kein Code:** `GZ_WEBAUTHN_RP_ID=gregor20.henemm.com` +
`GZ_WEBAUTHN_RP_ORIGINS=https://gregor20.henemm.com` in der Prod-`.env`, analog
`staging.gregor20.henemm.com` auf Staging. Die Trennung Prod/Staging ist gewollt (Passkeys
hängen am Domainnamen, siehe #2130 selbst und `internal/handler/passkey_test.go:889`).

**Warum die 31 Go-Tests das nie gefangen haben:** Jeder Test baut sich seine eigene
`webauthn.New(...)`-Instanz passend zum Szenario (`newTestWebAuthn`,
`internal/handler/passkey_test.go:231-242`) statt die echte `config.Load()`-Defaultkette zu
durchlaufen. Und ein Fehler, der im Browser vor dem ersten HTTP-Request auftritt, ist von
Handler-Tests strukturell nicht erreichbar. Die Suite war 100 % grün, während die Funktion in
Produktion zu keinem Zeitpunkt benutzbar war.

## Related Files

### Backend (Go) — funktionsfähig, nur falsch konfiguriert

| Datei | Relevanz |
|---|---|
| `internal/config/config.go:45-47` | RPID/Origins/DisplayName — **Fix-Ort für die Defaults/Doku** |
| `cmd/server/main.go:92-101` | `webauthn.New()`-Initialisierung |
| `internal/handler/passkey.go` (569 Z.) | 9 Handler: register/login/discoverable/register-public/delete |
| `internal/router/router.go:93-125` | Routen + IP-Rate-Limiter (30/h regulär, 5/h Public-Registrierung) |
| `internal/handler/challenge_store.go` | prozesslokale `sync.Map`, TTL 5 Min, `Take()` destruktiv (Replay-sicher) |
| `internal/model/user.go:14,55-65,68` | `User.PasskeyCredentials`, `WebAuthnCredential` (inkl. `Label`, `CreatedAt`, `LastUsedAt`), `WebAuthnID()` |
| `internal/handler/auth.go:128-146` | `issueSession()` — **dieselbe** Funktion wie beim Passwort-Login, alle vier Passkey-Pfade nutzen sie |
| `internal/handler/passkey_test.go` (1339 Z., 22 Tests), `passkey_public_test.go` (485 Z., 9 Tests) | mock-frei, echter ECDSA-P-256-Test-Authenticator mit echter Krypto-Verifikation |

Handler-Verträge (Auszug, für die Frontend-Anbindung entscheidend):

- `register/begin`, `login/begin` → `{"publicKey": …}` (Wrapper)
- `discoverable/begin` → **volles Objekt** `{"publicKey": …, "mediation":"conditional"}` — die
  `mediation` muss auf Top-Level stehen, sonst kein Autofill-Picker (`passkey.go:292-293`)
- `login/begin` antwortet bei unbekanntem Nutzer generisch 401 (Anti-Enumeration)
- `DELETE credentials/{id}` verweigert das Löschen des letzten Passkeys bei passwortlosem Nutzer (400)

### Frontend (SvelteKit) — UI existiert nicht

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/passkey.ts` (155 Z.) | vollständige Browser-Hilfsfunktionen, **0 Importe** im gesamten Frontend |
| `frontend/package.json:34` | `@github/webauthn-json ^2.1.1` noch installiert |
| `frontend/src/routes/login/+page.svelte` (120 Z.) | heutige Reihenfolge: Passwort → optional Google-OAuth → Links (Registrieren, Passwort vergessen, Magic-Link). Kein Passkey. |
| `frontend/src/routes/login/+page.server.ts:9-13,15-57` | `load` liefert nur `googleEnabled`; Form-Action postet an `/api/auth/login`, reicht `gz_session` httpOnly weiter |
| `frontend/src/routes/account/+page.svelte` (836 Z.) | Konto-Ansicht; Passkeys-Karte saß laut Diff zwischen "Kanäle" (381) und "Passwort ändern" (477) |
| `frontend/src/service-worker.ts:468,483-498` | ignoriert `/api/*` vollständig; `/login` nicht in der Offline-Positivliste → **kein PWA-Risiko für WebAuthn** |
| `frontend/e2e/global.setup.ts:1-51` | heutiger E2E-Login: Passwort-Formular → `storageState` nach `playwright/.auth/admin.json` |

`frontend/src/lib/passkey.ts` exportiert: `isWebAuthnSupported()` (Z.17), `registerPasskey(label)`
(Z.32-55), `loginWithPasskey(username)` (Z.62-87), `loginWithDiscoverablePasskey(signal?)`
(Z.97-140, umgeht die ponyfill-Lib bewusst, weil sie `mediation`/`signal` strippt),
`deletePasskey(credentialId)` (Z.147-155).

### Die entfernte UI ist aus der Historie wiederherstellbar

Commit **`c09172f5`** (2026-06-24), Message: *"chore(#878): Passkey-UI temporär entfernt — nie
getestet, nie funktioniert"*. Entfernt `login/+page.svelte` (−90 Z.) und `account/+page.svelte`
(−136 Z.):

- **Login:** `autocomplete="username webauthn"` am Username-Feld, `startConditionalUI()` mit
  `PublicKeyCredential.isConditionalMediationAvailable()`, `handlePasskey()` mit deutschen
  Fehlertexten für `NotAllowedError`/`TimeoutError`, Trenner "oder" + Button
  `data-testid="login-passkey-btn"`
- **Account:** komplette Karte `data-testid="passkeys-card"` mit Liste
  (`passkey-row-{id}`, Name aus `authenticator_name`/`label`, "registriert … zuletzt verwendet …"),
  Lösch-Button (`passkey-remove-{id}`), Eingabefeld + `passkey-add-btn`, Hinweistext bei fehlender
  WebAuthn-Unterstützung

## Existing Patterns

- **Mobile-Erkennung** — vierfach etabliert, wiederverwenden statt neu bauen:
  `window.matchMedia('(max-width: 899px)')` in einem `$effect` mit Cleanup, siehe
  `frontend/src/lib/components/trip-detail/TripTabs.svelte:136-140`,
  `compare/CompareTabs.svelte:144`, `compare-new/CompareNewEditor.svelte:112`,
  `trip-new/TripNewEditor.svelte:108`. Breakpoint durchgängig 899px.
- **Karten-Baumuster Konto-Ansicht:** `<Card.Root data-testid>` → `Card.Header`/`Card.Title`/
  `Card.Description` → `Card.Content class="space-y-4"`, Meldungen als farbiges `rounded-md
  border`-`div` (grün `border-green-300 bg-green-50 text-green-800`, rot `border-destructive
  bg-destructive/10 text-destructive`), Icons aus `@lucide/svelte/icons/*`.
- **Session-Ausstellung:** genau eine Funktion (`issueSession()`), von Passwort- und allen
  Passkey-Pfaden geteilt — keine Sonderlocke nötig.

## Dependencies

- **Upstream:** `go-webauthn/webauthn v0.17.4`, `@github/webauthn-json ^2.1.1`, ENV-Konfiguration
  (Prod/Staging `.env`, systemd-EnvironmentFiles → **Änderung im Repo `henemm-infra` bzw. an den
  `.env`-Dateien auf dem Server nötig, nicht im Anwendungs-Repo**)
- **Downstream:** Anmeldung/Session insgesamt (kritischer Pfad); `data/users/<id>/user.json`
  (`PasskeyCredentials`); `data/users/<id>/sessions.json` (ADR-0060)

## Existing Specs

| Dokument | Stand |
|---|---|
| `docs/specs/modules/passkey_webauthn.md` | V1 (#450), Status `draft`, **`[ ] Approved` nie gesetzt**. **Cookie-Format veraltet** (Z.411/434 zeigen 3-Segment `{userId}.{ts}.{hmac}`, `MaxAge=86400`) |
| `docs/specs/_archive/modules/issue_466_passkey_register_public.md` | V2 passwortlose Registrierung, archiviert, `[ ] Approved` |
| `docs/specs/_archive/modules/issue_467_discoverable_credentials.md` | V3 Discoverable + Conditional UI, archiviert, `[ ] Approved` |
| `docs/specs/modules/aaguid_labels.md` | #468, `[x] Approved` — Muster für "eigene Datei on top von V1" |
| `docs/reference/api_contract.md` §19 (ab Z.2574) | alle 9 Passkey-Routen dokumentiert, Cookie-Format **aktuell** (ADR-0060). Bewacht von `tests/test_api_contract_drift.py` |
| ADR-0030 | "Session-Auth über HMAC-Cookie" — **abgelöst durch ADR-0060** |
| ADR-0060 | "Dauerhafte Anmeldung mit dateibasierter Sitzungsliste" (#2129, live seit 06.09.) — Cookie 4-teilig `{userId}.{sessionId}.{ts}.{sig}`, `MaxAge=34560000` |

Keine ADR hat Passkey je abgeschaltet oder zurückgestellt. `docs/project/known_issues.md` enthält
nichts zu Passkey/WebAuthn.

## Risks & Considerations

1. **Der Konfigurations-Fix gehört zur Lieferung, sonst ist die Scheibe wertlos.** Nur UI
   herausstellen, ohne RP-ID zu korrigieren, hieße einen Anmeldeweg an die erste Stelle zu setzen,
   der garantiert scheitert. Die `.env`-Änderung liegt **außerhalb dieses Repos** (Server-`.env` +
   `henemm-infra`) — braucht eine MQ-Nachricht an `infra` oder eine eigene Server-Änderung, und
   ein Deploy-Schritt, den das übliche `deploy-gregor-prod.sh` nicht mit abdeckt.
2. **ResidentKey/Discoverable ungeklärt (unverifiziert).** `webauthn.Config.AuthenticatorSelection`
   ist in `cmd/server/main.go:97-101` nicht gesetzt (Zero-Value, `ResidentKey=""`,
   `go-webauthn@v0.17.4/webauthn/registration.go:70`). Über `/register/begin` angelegte Passkeys
   werden dem Authenticator dann ohne ausdrückliche `residentKey`-Anforderung angeboten — sie
   könnten nicht-discoverable entstehen und im Conditional-UI-Flow (für "Passkey als erster Weg"
   zentral) **gar nicht auftauchen**. Nur per echtem Browser entscheidbar.
3. **Kein Testunterbau für die Browser-Zeremonie.** Weder Vitest- noch Playwright-Test zu Passkey
   existiert, und im ganzen Repo kein virtueller WebAuthn-Authenticator (CDP
   `WebAuthn.addVirtualAuthenticator`). Die in `passkey_webauthn.md` geplante
   `frontend/e2e/passkey.spec.ts` existiert nicht. Genau diese Lücke hat den Prod-Ausfall
   verdeckt — ein Nachweis, der wieder nur Handler testet, würde denselben Fehler erneut
   durchlassen.
4. **Staging-Passkey braucht eigene Registrierung** (andere Domain = anderer RP-ID-Geltungsbereich).
   Staging liegt zusätzlich hinter nginx-Basic-Auth (gemessen: 401 auf
   `/api/auth/passkey/discoverable/begin`) — der Browser-Nachweis muss diese Schicht mit bedienen.
5. **Passkey darf nie der einzige Weg sein** (Issue-Vorgabe): Magic-Link bleibt Rettungsanker,
   Passwort bleibt erreichbar. Ein "Angebot nach Passwort-Login" darf nicht wiederkehrend nerven —
   Abweisung muss persistent sein (Ablageort noch offen: Nutzerprofil vs. Gerätespeicher).
6. **Spec-Hygiene:** `passkey_webauthn.md` ist beim Cookie-Vertrag veraltet und nie freigegeben.
   Beim Schreiben der #2130-Spec nicht daraus abschreiben, sondern gegen `api_contract.md` §19 und
   ADR-0060 arbeiten.
7. **`WebAuthnID()` gibt den Klartext-Username als User-Handle zurück** (`internal/model/user.go:68`).
   Kein Sicherheitsloch, aber Abweichung von der Best Practice (zufälliges opakes Handle). Kein
   Blocker für #2130 — Kandidat für #1199.

---

# Analysis (Phase 2, 2026-09-08)

## Type

**Bug im Gewand eines Features.** #2130 ist als Komfort-Feature geschnitten ("Passkey
herausstellen"), setzt aber eine funktionierende Passkey-Anmeldung voraus, die es nie gab. Der
Kern der Arbeit ist deshalb eine Fehlerbehebung, nicht eine UI-Umsortierung.

## Zweiter belegter Defekt: Passkeys werden nicht auffindbar angelegt

Am vendorten Modul `go-webauthn@v0.17.4` verifiziert (nicht vermutet):

- `webauthn/registration.go:70` reicht `webauthn.Config.AuthenticatorSelection` unverändert an die
  Client-Optionen durch, sofern der Aufrufer keine Option übergibt.
- `internal/handler/passkey.go:65` (`/register/begin`) und `:478` (`/register/public/begin`) rufen
  beide `BeginRegistration(...)` **ohne jede Option** — beide hängen also am Zero-Value aus
  `cmd/server/main.go:97-101`, wo `AuthenticatorSelection` nicht gesetzt ist.
- `protocol/options.go:38,134,138`: `AuthenticatorSelection` ist ein Nicht-Zeiger-Struct mit
  `omitempty` — Go's `encoding/json` lässt solche Structs **nie** weg, es wird
  `"authenticatorSelection":{}` gesendet. `ResidentKey` und `RequireResidentKey` sind beide
  `omitempty` und leer.
- Nach WebAuthn-Spec ist der effektive Wert bei absentem `residentKey` und absentem
  `requireResidentKey`: **`discouraged`**.

**Folge:** Angelegte Passkeys sind nicht zwingend "discoverable". Für `/register/public/begin`
(passwortlose Neuregistrierung) ist das strukturell kaputt — ohne auffindbares Credential kann der
Nutzer später gar nicht wiedergefunden werden. Für den in #2130 zentralen Autofill-Weg
(`/discoverable/begin`) heißt es: der Passkey taucht im Auswahldialog womöglich nicht auf.

Fix: global `ResidentKey: protocol.ResidentKeyRequirementPreferred` in `cmd/server/main.go`, und
für `/register/public/begin` explizit
`webauthn.WithResidentKeyRequirement(protocol.ResidentKeyRequirementRequired)`
(`registration_opt.go:40`).

## Technischer Ansatz

### 1. Konfiguration ableiten statt zwei neue Variablen nachtragen

`PublicHost` (`internal/config/config.go:39`) ist bereits die Größe für die öffentliche Adresse
(genutzt in `internal/handler/auth.go:319,791`). RP-ID und RP-Origins werden daraus **abgeleitet**,
wenn die expliziten WebAuthn-Variablen leer sind: RP-ID = Hostanteil, Origin = Schema+Host. Die
expliziten Variablen bleiben als Override.

Begründung gegenüber "zwei ENV-Variablen setzen": Eine Konfiguration, die an zwei Stellen dieselbe
Wahrheit doppelt und an einer davon still falsch sein kann, hat genau diesen Ausfall erzeugt. Eine
abgeleitete Größe kann nicht auseinanderlaufen.

**Zwei Fallstricke, die die Implementierung mitnehmen muss:**

- `PublicHost` hat selbst den Default `https://gregor20.henemm.com`. Ein frischer Checkout ohne
  `.env` bekäme dann lokal `gregor20.henemm.com` als RP-ID — derselbe Fehler in umgekehrter
  Richtung. `.env.example` braucht den lokalen Override, die lokale `.env` muss ihn aktiv setzen.
- `frontend/e2e/start-preview.sh:12` baut die Preview auf **Port 4173**, der Dev-Server läuft auf
  5173. go-webauthn prüft den Origin exakt inklusive Port (`protocol/client.go:219-229`, kein
  Wildcard). Der E2E-Lauf braucht `http://localhost:4173` in den erlaubten Origins.

### 2. Beobachtbarkeit — der Fehler muss von außen sichtbar sein

Kein `log.Fatalf` bei Fehlkonfiguration: Passkey ist ein optionaler Weg neben Passwort und
Magic-Link; ein Abbruch würde eine Passkey-Fehlkonfiguration in einen Totalausfall **aller**
Anmeldewege verwandeln — schlechter als der Status quo.

Stattdessen, ohne neue Pflichtregel (Regel-Budget!):

- `HealthHandler` (`internal/handler/proxy.go:17-42`) bekommt das Feld `webauthn_rpid` mit der
  **effektiven**, aufgelösten RP-ID (~5-8 LoC).
- `.claude/hooks/prod_selftest.py::_check_health()` (Zeile 358) holt `/api/health` ohnehin schon —
  eine zusätzliche Prüfung vergleicht `webauthn_rpid` gegen den Hostnamen der geprüften Basis-URL.
  Kein neuer Request, kein neuer Gate-Typ, kein Prüfdatum nötig (Erweiterung einer bestehenden
  Phase statt neuer Regel).

Ausdrücklich **nicht** über die generische AC-Probe: `_probe_ac()` (Zeile 239-355) macht nur
GET-Requests und wertet nur Statuscodes aus. `/api/auth/passkey/discoverable/begin` ist POST-only
und liefe dort als `SKIPPED_METHOD_NOT_PROBEABLE` durch — exakt das Muster, das den Ausfall drei
Monate verdeckt hat.

### 3. Nachweis — die Lücke, die den Ausfall verdeckt hat, muss zu

Playwright + CDP: `context.newCDPSession(page)` → `WebAuthn.enable` →
`WebAuthn.addVirtualAuthenticator({protocol:'ctap2', transport:'internal', hasResidentKey:true,
hasUserVerification:true, isUserVerified:true})`. `frontend/playwright.config.ts` setzt in keinem
Projekt ein Gerät, läuft also ohnehin auf Chromium — CDP ist verfügbar.

**Der Test braucht keine wiederhergestellte UI:** Der lokale E2E-Stack spricht einen echten
Go-Server (`frontend/e2e/start-preview.sh:12`, `GZ_API_BASE=http://localhost:8091`). Die Zeremonie
lässt sich vollständig per `page.evaluate()` fahren: `fetch('/api/auth/passkey/register/begin')` →
`navigator.credentials.create(...)` → `fetch('.../finish')`. Damit ist der Nachweis der
Backend-Korrektheit von der UI-Arbeit entkoppelt.

Welche Ebene fängt was (Leitfrage "wirkt vs. steht im Code"):

| Ebene | fängt | fängt NICHT |
|---|---|---|
| Weitere Go-Handler-Tests | nichts Neues — die 31 bestehenden geben sich ihre RP-ID selbst vor | genau den vorliegenden Ausfall |
| `prod_selftest`-Health-Vergleich | falsche/vergessene RP-ID im ausgelieferten Stand | ob der Browser die Zeremonie wirklich durchführen kann |
| CDP-Playwright | beides zusammen, echter Browser gegen echten Server | Verhalten realer Plattform-Authenticatoren |

Staging-Smoke bleibt optional (nginx-Basic-Auth davor, Muster vorhanden in
`frontend/e2e/konto-naechste-pruefung.staging.setup.ts:24-28`) — zusätzliche Bestätigung, kein
Pflichtgate.

## Scope Assessment und Zuschnitt

Geschätzte LoC bei **einem** Ticket: Backend ~90-130 · Tooling ~30-50 · E2E ~100-150 · Frontend
~280-380 = **500-700+**. Das liegt über dem Limit von 250 und auch über dem Override von 500. Der
Schnitt ist damit nicht Geschmackssache, sondern Voraussetzung für eine regelkonforme Lieferung.

| Ticket | Inhalt | LoC |
|---|---|---|
| **A = #2130 (neu geschnitten)** | Config-Ableitung, ResidentKey-Fix, `webauthn_rpid` im Health-Endpunkt, `prod_selftest`-Erweiterung, CDP-Playwright-Regressionstest. **Keine UI.** | ~250-330 (Override 500) |
| **B = neues Issue** | Passkey-UI: erster Weg auf dem Handy, Autofill, Konto-Karte, einmaliges abweisbares Angebot | ~280-380 |
| **C = neues Issue (klein)** | `GZ_PUBLIC_HOST` auf Staging setzen | Ops |

**Reihenfolge A → B.** Nach A ist der Zustand nicht "halb geliefert", sondern sauber: Passkey
funktioniert und ist bewacht, nur noch nicht beworben. B darf nach hinten rutschen, genau wie es
die PO-Einstufung in #2130 vorsieht ("Komfort, kein Sicherheits-Muss").

Für B bereits entschieden: Die Abweisung des einmaligen Angebots gehört **serverseitig ins
Nutzerprofil** (`internal/model/user.go`), nicht in `localStorage` — wer auf Gerät A abweist, soll
auf Gerät B nicht erneut gefragt werden. Das ist eine Schema-Änderung → `data_schema_backup.py`
greift, Read-Modify-Write mit Merge ist Pflicht.

## Dependencies und Ausliefer-Besonderheit

Die `.env`-Änderung liegt **außerhalb dieses Repos** (Server-`.env` für Prod und Staging). Der
übliche Weg PR → CI → Staging → `deploy-gregor-prod.sh` → `prod_selftest.py` deckt sie nicht ab.
Absicherung: Nach der Ableitung aus `PublicHost` genügt **eine** korrekt gesetzte Variable
(`GZ_PUBLIC_HOST`) statt dreier, und der `prod_selftest`-Health-Vergleich schlägt an, falls sie
fehlt — der Fehler kann also nicht mehr still bleiben.

## Nebenbefund

`GZ_PUBLIC_HOST` ist auf Staging nicht gesetzt, Staging läuft auf dem Prod-Default. Damit
verlinken **Staging-Passwort-Reset- und Verifikationsmails auf die Produktion**
(`internal/handler/auth.go:319,791`). Nutzersichtbares Fehlverhalten → eigenes Issue (Ticket C),
im selben Server-Zugriff wie A miterledigt.

## Open Questions

- [ ] Keine offenen technischen Fragen. Der Zuschnitt A/B/C ist eine Produktentscheidung, die
      über die Spec-Freigabe in Phase 3 läuft.

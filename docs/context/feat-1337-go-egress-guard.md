# Context: feat-1337-go-egress-guard

## Request Summary

Epic #1337 (Umgebungs-Isolation), nächste Scheibe: Der **Go-Prozess** (`gregor-api`)
telefoniert heute völlig ungebremst nach draußen — der zentrale Egress-Wächter existiert
nur im Python-Prozess. Zusätzlich ist auf der Python-Seite der **Async-httpx-Transport**
ungepatcht. Beides schließen, mit demselben Host-Inventar und derselben Entscheidungsregel.

## Ist-Stand: Python-Seite (Scheibe A, live)

`src/app/egress_guard.py` (137 Zeilen) patcht bei `is_test_mode` oder `env == "staging"`
drei Transport-Primitive: `httpx.HTTPTransport.handle_request`, `smtplib.SMTP.connect`,
`imaplib.IMAP4.open`. Entscheidungsregel: `INVENTORY[host] is TEST_ACCESS` → durchlassen,
sonst `EgressBlockedError` (BLOCKED **und** undeklariert = Tripwire). Localhost immer frei,
dynamische Test-Hosts (`test_smtp_host`, `imap_host`) werden bei `install()` ergänzt.
Bootstrap: `api/main.py`. In Prod reiner No-Op.

## Lücke 1: Go-Prozess — externe Ausgänge (im Code verifiziert)

| Ort | Ziel-Host | Kosten/Nebenwirkung |
|---|---|---|
| `internal/provider/openmeteo/provider.go` (via `cfg.OpenMeteoBaseURL`/`AQURL`) | `api.open-meteo.com`, `air-quality-api.open-meteo.com` | **Kontingent** (geteilte IP mit Prod → #1329/#1333) |
| `internal/resolver/googlemaps.go` | `nominatim.openstreetmap.org` + **beliebige Nutzer-URL** (`http.NewRequest("GET", input, …)`, Zeile 87) | Fair-Use-Kontingent; beliebiger Host! |
| `internal/resolver/elevation.go` | `api.open-elevation.com` | Fair-Use |
| `internal/resolver/komoot.go` | `www.komoot.com` | Fair-Use |
| `internal/handler/auth_oauth.go` | `www.googleapis.com` (OAuth-Userinfo) | Login-Pfad |
| `internal/scheduler/scheduler.go:433` (`pingHeartbeat`) | `uptime.betterstack.com` | Falsch-Grün im Monitoring |
| `internal/mail/sender.go` (`net/smtp`, nicht HTTP!) | Resend/Google/Fallback-SMTP | **Kosten + echte Empfänger** |

Nicht extern (localhost, unkritisch): `proxy.go`, `preview_proxy.go`, `compare_preset.go`,
`telegram_webhook.go` (leitet nur an den Python-Core weiter), `notify/mq.go` (Port 3457).
**Kein** direkter `api.telegram.org`-Ruf im Go-Prozess.

**Technisch entscheidender Befund:** Alle diese Stellen erzeugen ihre Clients als
`&http.Client{Timeout: …}` **ohne eigenen `Transport`** — sie laufen also alle über
`http.DefaultTransport`. Ein einziger Austausch von `http.DefaultTransport` beim
Prozessstart erfasst damit sämtliche HTTP-Ausgänge, ohne eine einzige Aufrufstelle
anzufassen. Das ist das Go-Pendant zum Python-Monkeypatch. `net/smtp` liegt außerhalb
dieses Wegs und braucht eine eigene Linie in `internal/mail/sender.go`.

## Lücke 2: Python — Async-Transport

`egress_guard.py` patcht nur `httpx.HTTPTransport.handle_request` (synchron).
`httpx.AsyncHTTPTransport.handle_async_request` ist offen. Heute ohne Befund
(`grep` findet in `src/`+`api/` **keinen** `httpx.AsyncClient`), aber der Prozess ist eine
FastAPI-App — der erste async-Aufruf würde still am Wächter vorbeigehen. Vorsorge, klein.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/egress_guard.py` | Referenz-Implementierung + Inventar (Single Source of Truth) |
| `docs/specs/modules/egress_guard.md` | Spec Scheibe A inkl. „Andock-Fläche für Scheiben B–E" |
| `cmd/server/main.go` | Einziger Prozess-Einstieg des Go-Dienstes → Bootstrap-Ort |
| `internal/config/config.go` | `Env` (`GZ_ENV`), `TestFixtureDir` — Aktivierungsbedingung liegt vor |
| `internal/scheduler/scheduler_gate.go` | Vorbild für Fail-safe-Umgebungsschalter („nur exakt `staging` schaltet") |
| `internal/mail/sender.go` | Bestehende Mail-Guards (`resendBlocked` #1122, `recipientBlocked`) — SMTP-Linie andocken, nicht ersetzen |
| `internal/provider/fixture/provider.go` | Bestehender Offline-Weg im Go-Dienst (`GZ_TEST_FIXTURE_DIR`) |
| `tests/test_adr_index_drift.py` | Vorbild für einen Drift-Test zwischen zwei Listen-Quellen |

## Existing Patterns

- **Fail-safe-Umgebungsschalter:** `SchedulerEnabled` schaltet nur bei exakt `"staging"` ab;
  jeder andere Wert = Prod-Verhalten. Dieselbe Richtung muss der Go-Wächter haben —
  ein Fehlgriff darf niemals Prod-Egress blockieren.
- **Default-deny mit Deklaration:** Python-Inventar (TEST_ACCESS/BLOCKED/undeklariert=Tripwire).
- **Guard nah am Primitiv:** Python patcht Transport-Primitive statt Aufrufstellen;
  Go-Äquivalent = `http.DefaultTransport` + `net/smtp`-Wrapper.
- **Drift-Tests statt Laufzeit-Kopplung:** `test_adr_index_drift.py` hält zwei Quellen
  synchron, ohne sie zur Laufzeit zu verbinden.

## Dependencies

- **Upstream:** `GZ_ENV` (systemd-Unit `gregor-api-staging`), `internal/config.Config`,
  Go-Stdlib `net/http`/`net/smtp`, Python `httpx`.
- **Downstream:** Jeder ausgehende Ruf des Go-Dienstes — Wetter-Provider, Ortsauflösung
  (Nominatim/Komoot/Höhe), Google-Login, Heartbeats, Mailversand aus Go.

## Existing Specs

- `docs/specs/modules/egress_guard.md` — Scheibe A (Python), inkl. „Known Limitations",
  in denen Go-Prozess und async-httpx bereits als offene Flanken benannt sind.

## Risks & Considerations

1. **Prod-Ausfall bei Fehlaktivierung** — höchstes Risiko. Der Wächter darf ausschließlich
   bei `GZ_ENV=staging` (bzw. im Go-Test-Binary) greifen; jeder andere Zustand = No-Op.
2. **Staging-Funktionsverlust:** Nominatim/Komoot/Höhen-API/Google-OAuth sind kostenlos und
   nebenwirkungsfrei — würden sie geblockt, wäre Staging als Testumgebung entwertet.
   Sie gehören als TEST_ACCESS ins Inventar, nicht in den Tripwire.
3. **Beliebige Nutzer-URL** in `googlemaps.go` (Share-Link-Auflösung): Der Wächter würde
   Kurzlink-Domains (`maps.app.goo.gl`, `goo.gl`, `www.google.com`) hart blocken →
   Ortsanlage auf Staging kaputt. Muss explizit entschieden und deklariert werden.
4. **Inventar-Duplikat Python↔Go:** Zwei Listen driften auseinander — die Wiederholung
   genau des Fehlers, den das Epic abstellen will. Braucht eine erzwungene Kopplung
   (geteilte Datei oder Drift-Test).
5. **open-meteo-Einstufung:** Python führt es als TEST_ACCESS. Auf BLOCKED zu stellen wäre
   Kontingent-wirksam, gehört aber fachlich zu #1333 (Fixture-Provider auf der
   Staging-Unit) — hier nur die Andock-Stelle schaffen, nicht die Einstufung ändern.
6. **Go-Prozess ohne `httptest`-Netz:** Go-Tests dürfen kein echtes Netz brauchen; der
   Nachweis muss über den ausgetauschten Transport laufen (deterministisch).

## Analysis

### Type

Feature (Epic-Scheibe #1337) — kein Fehlverhalten gemeldet, sondern eine strukturelle
Isolationslücke.

### Technischer Ansatz (Empfehlung)

**1. Ein Andockpunkt statt zehn.** `internal/egress` als neues Paket mit `Install(cfg)`,
aufgerufen genau einmal in `cmd/server/main.go` direkt nach `config.Load()`.
`Install` ersetzt `http.DefaultTransport` durch einen `http.RoundTripper`, der vor dem
Weiterreichen `INVENTORY[req.URL.Hostname()]` prüft. **Verifiziert:** alle externen
Go-Clients (`openmeteo`, `resolver/*`, `auth_oauth`, `pingHeartbeat`) erzeugen
`&http.Client{Timeout: …}` **ohne** eigenen `Transport` und erben damit den Wächter —
keine einzige Aufrufstelle muss angefasst werden. Das ist die exakte Entsprechung zum
Python-Monkeypatch und hält den Diff klein.

**2. Aktivierungsbedingung fail-open Richtung Prod.** Wächter greift nur bei
`cfg.Env == "staging"` oder gesetztem `cfg.TestFixtureDir` — jeder andere Zustand ist
No-Op. Exakt das Muster von `SchedulerEnabled` (nur der Literalwert `"staging"` schaltet).
Ein Konfigurationsfehler kann damit Prod-Egress nicht blockieren.

**3. SMTP separat.** `net/smtp` läuft nicht über `http.DefaultTransport`. In
`internal/mail/sender.go` kommt eine dritte Guard-Zeile vor `dialAndSend` hinzu
(`egress.SMTPAllowed(host)`), **zusätzlich** zu `recipientBlocked`/`resendBlocked` — die
bestehenden Linien bleiben unverändert.

**4. Python-Async-Lücke.** `httpx.AsyncHTTPTransport.handle_async_request` analog patchen,
mit derselben `_is_allowed`-Entscheidung und derselben Restore-Kette in `uninstall`.

**5. Inventar-Drift verhindern.** Empfehlung: **deklarierte Doppel-Liste + erzwungener
Drift-Test** (`tests/test_egress_inventory_drift.py`, Vorbild `test_adr_index_drift.py`),
der beide Quelldateien parst und auf Host-für-Host-Gleichheit prüft.
Verworfen: geteilte JSON-Datei zur Laufzeit — `go:embed` kann keine Datei außerhalb des
Paketverzeichnisses einbinden, also bräuchte es doch wieder eine Kopie; und die live
verifizierte Python-Scheibe A müsste auf Datei-Laden umgebaut werden (Pfadauflösung je
systemd-Unit = neue stille Fehlerquelle). Der Drift-Test erreicht dieselbe Garantie ohne
Laufzeitrisiko.

### Inventar-Ergänzungen (beide Seiten)

| Host | Einstufung | Begründung |
|---|---|---|
| `nominatim.openstreetmap.org`, `api.open-elevation.com`, `www.komoot.com` | TEST_ACCESS | kostenlos, keine Nebenwirkung; Ortsanlage muss auf Staging funktionieren |
| `maps.app.goo.gl`, `goo.gl`, `www.google.com`, `maps.google.com` | TEST_ACCESS | Share-Link-Auflösung (`followGoogleMapsRedirect`) |
| `www.googleapis.com`, `oauth2.googleapis.com`, `accounts.google.com` | TEST_ACCESS | Google-Login auf Staging |
| `uptime.betterstack.com` | **BLOCKED** | Staging darf keine Prod-Heartbeats grün pingen — das wäre Falsch-Grün im Monitoring |
| `api.open-meteo.com`, `air-quality-api.open-meteo.com` | TEST_ACCESS (unverändert) | Einstufung gehört fachlich zu #1333, hier nur Andockstelle |
| `smtp.resend.com`, `smtp.gmail.com` | undeklariert = Tripwire | Default-deny genügt, keine Sonderregel |

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `internal/egress/guard.go` | CREATE | RoundTripper-Wächter, Inventar, `Install`/`SMTPAllowed` |
| `internal/egress/guard_test.go` | CREATE | Tripwire/Allow/No-Op-in-Prod/Idempotenz, netzfrei |
| `cmd/server/main.go` | MODIFY | Bootstrap direkt nach `config.Load()` |
| `internal/mail/sender.go` | MODIFY | dritte Guard-Zeile vor `dialAndSend` |
| `internal/mail/sender_egress_test.go` | CREATE | SMTP-Host geblockt in Staging, frei in Prod |
| `src/app/egress_guard.py` | MODIFY | Async-Transport patchen + Restore |
| `tests/tdd/test_egress_guard_async.py` | CREATE | Async-Pfad blockt/erlaubt |
| `tests/test_egress_inventory_drift.py` | CREATE | Python- und Go-Inventar müssen deckungsgleich sein |
| `docs/specs/modules/egress_guard.md` | MODIFY | Scheibe „Go-Prozess" ergänzen |

### Scope Assessment

- Dateien: 9 (4 neu Test, 1 neu Quelle, 3 modifiziert, 1 Spec)
- Geschätzt: ~+300 LoC (davon ~180 Tests) — **über dem 250er-Rahmen**, PO-Freigabe für
  400 wird bei der Spec-Abnahme mitgeholt
- Risiko: **HIGH** (kritischer Pfad — deshalb fail-open-Aktivierung + Prod-No-Op-Test)

### Open Questions

- [x] open-meteo im Go-Wächter blocken? → Nein, Einstufung unverändert (gehört zu #1333)
- [x] Inventar als geteilte Datei? → Nein, Drift-Test (Begründung oben)
- [x] Telegram im Go-Prozess? → Kein direkter Ruf vorhanden, nur Weiterleitung an Python

# Context: fix-2142-core-auth-shared-secret

## Request Summary

Der Python-Core (FastAPI, `api/main.py`) hat **keinerlei Authentifizierung**. Das gesamte
Anti-Spoofing steckt in einer einzigen Go-Funktion (`internal/handler/proxy.go:140-157`,
`appendUserID`), die eine client-gelieferte `user_id` durch die authentifizierte ersetzt.
Wer den Python-Core direkt anspricht, umgeht diese Stelle vollständig und kann mit frei
gewählter `?user_id=` fremde Daten lesen, fremde Briefings verschicken und über
`POST /api/internal/telegram-webhook` gefälschte Telegram-Kommandos für ein fremdes Konto
ausführen. Blocker aus Epic #2138.

**Erwartung laut Issue:** Shared Secret Go↔Python als Header, Fail-Fast auf beiden Seiten
bei fehlendem Secret, Python lehnt jede Anfrage ohne gültiges Secret mit 401 ab; Bind auf
`127.0.0.1` im Startpfad erzwingen (nicht nur in der Doku); Webhook-Secret zusätzlich in
Python prüfen (Defense in Depth).

### Vorab gemessene Einordnung der Dringlichkeit

Auf dem Server binden **beide** Dienste bereits nur auf Loopback — gemessen mit `ss -ltnp`:
`127.0.0.1:8090` (Go) und `127.0.0.1:8000` (Python); die systemd-Unit `gregor-python.service`
startet mit `uvicorn api.main:app --host 127.0.0.1 --port 8000`. Der Angriff ist damit heute
**nicht aus dem Netz erreichbar**, sondern nur für einen lokalen Prozess auf dem Server.

Das entwertet den Befund nicht:

1. Die Loopback-Bindung steht **ausschließlich in der systemd-Unit** (Repo `henemm-infra`),
   nicht im Anwendungs-Repo. Ein Umzug, ein Container, eine geänderte Startzeile — und der
   Schutz ist still weg, ohne dass ein Test oder ein Gate anschlägt.
2. Netzwerk-Isolation als einziger Schutz ist genau die Annahme, die Epic #2138 für den
   Mehrnutzer-Betrieb ausräumt. Sie ist eine Betriebszusicherung, keine Code-Zusicherung.

## Related Files

### Go — sendende Seite (20 Aufrufstellen, 17 unabhängige Clients)

| File | Relevance |
|------|-----------|
| `internal/handler/proxy.go` | **14** Aufrufstellen; jede Handler-Funktion baut ihren **eigenen** `&http.Client{Timeout: …}` (Timeouts 2 s bis 300 s). Enthält `appendUserID` (Z.140-157) — der einzige bestehende Schutz |
| `internal/handler/preview_proxy.go` | 2 Aufrufstellen (`ComparePreviewProxyHandler` Z.34, `PreviewProxyHandler` Z.72), je eigener Client |
| `internal/handler/compare_preset.go:674` | 1 Aufrufstelle (`SendComparePresetHandler`), eigener Client |
| `internal/handler/telegram_webhook.go:37-74` | 1 Aufrufstelle; Modul-Level-Client (Z.38); reicht den rohen Telegram-Body an Python weiter (Z.63-64) **ohne jeden Auth-Nachweis** — der Kern des Webhook-Teils von #2142 |
| `internal/scheduler/scheduler.go` | 3 Aufrufstellen (Z.478, 619, 675), alle über **einen geteilten** `s.client` (Struct-Feld, gesetzt in `New()` Z.161) |
| `internal/config/config.go` | Config-Struct, `envconfig.Process("GZ", &cfg)` (Z.52) — Präfix `GZ_`. **Alle** Felder haben Defaults, envconfig bricht nie ab |
| `internal/config/session_secret_gate.go` | `ValidateSessionSecret(cfg)` — **fertiges Fail-Fast-Vorbild aus dem Geschwister-Issue #2139** |
| `cmd/server/main.go:28-41` | Startreihenfolge: `config.Load()` → `ValidateSessionSecret` (`log.Fatalf`, Z.35-37) → `egress.Install(cfg)` → … → `ListenAndServe(cfg.Host+":"+cfg.Port)` (Z.109). Ein neues Secret-Gate reiht sich nach Z.37 ein |
| `internal/router/router.go:97-127` | Bekommt `cfg` vollständig über `Deps.Config`, reicht an die Handler-Konstruktoren aber nur `pythonURL string` durch — das Secret muss zusätzlich durchgereicht oder wie `TELEGRAM_WEBHOOK_SECRET` per `os.Getenv` gelesen werden |
| `internal/egress/guard.go:59-70` | Bestehender globaler Transport-Patch (`http.DefaultTransport`) — Vorbild für „ein RoundTripper, der an jedem Request etwas ändert"; trifft aber **alle** Ziele (Open-Meteo, Google Maps, Komoot), müsste also auf den Python-Host filtern |

### Python — empfangende Seite

| File | Relevance |
|------|-----------|
| `api/main.py:102-116` | Registriert 11 Router (`health`, `config`, `forecast`, `gpx`, `scheduler`, `compare`, `notify`, `internal`, `preview`, `validator`, `webhook`) + `debug` nur bei `GZ_ENV=staging`. Hier greift eine App-weite Prüfung |
| `api/main.py:88-98` (`lifespan`) | Einzige Stelle, die beim echten Prozessstart läuft — Vorbild für Fail-Fast **und** für den Bind-Guard |
| `src/app/egress_guard.py:133-161` | Bestes Vorbild für „Wächter im echten Laufzeitprozess": Aktivierungsbedingung, Idempotenz-Flag, Einbau im `lifespan` |
| `src/app/config.py:100-117` | `Settings(BaseSettings)`, `env_prefix="GZ_"`, `.env`-Support. **Kein einziges Pflichtfeld ohne Default** |
| `src/app/config.py:271-286` (`_resend_default_deny`) | Dokumentierte Design-Entscheidung **gegen** Fail-Fast in `Settings()`: „ein Raise würde ganze Apps beim Settings-Konstrukt crashen". Der Fail-Fast gehört also **nicht** in `Settings`, sondern in den `lifespan` |
| `src/app/config.py:31-33` (`_in_pytest`) | Bestehende Testlauf-Erkennung — **mit Vorsicht zu behandeln**, siehe Risiken |
| `api/routers/health.py` | Trivial, ohne Nutzerdaten. Muss ausgenommen bleiben (Begründung unter Risiken) |
| `api/routers/webhook.py:50-71` | Verarbeitet jeden POST-Body ohne eigene Prüfung; Docstring schreibt den Localhost-Trust als Soll fest. `_seen_ids` (Z.34-35) ist prozessglobal |
| `api/routers/notify.py:18`, `api/routers/scheduler.py:26-123, 204, 290` | Sendende Endpoints — hier entsteht echter Versand an fremde Empfänger |
| `api/routers/internal.py:29,55`, `preview.py:30,56,86,129`, `compare.py:27`, `validator.py:183,336,472`, `gpx.py:22` | Lesende bzw. schreibende Endpoints mit `user_id`-Parameter |

### Betrieb und CI

| File | Relevance |
|------|-----------|
| `frontend/e2e/ci-stack.sh` | **Einziger** Ort im Repo, der beide Prozesse als echte Dienste startet (Z.50: `uvicorn … --host 127.0.0.1`). Setzt `GZ_PORT`, `GZ_PYTHON_CORE_URL`, `GZ_DATA_DIR`, `GZ_CACHE_DIR`, `GZ_TEST_FIXTURE_DIR`, `GZ_USER_ID=admin`, `GZ_AUTH_PASS`, `GZ_ENV=staging`; `GZ_SESSION_SECRET` bleibt bewusst ungesetzt |
| `.github/workflows/ci.yml` | `ci-stack.sh` läuft **nur** im `e2e`-Job. `test` (pytest) und `go-test` laufen rein in-process (`TestClient` / `httptest`), ohne Netzwerk-Bind |
| `.env.example`, `.env.tpl`, `.env.e2e` | Die drei ENV-Vorlagen im Repo |
| `henemm-infra` → `gregor-python.service`, `gregor-api.service` | Lesen in Prod **dieselbe** Datei `/home/hem/gregor_zwanzig/.env` (Staging analog `/home/hem/gregor_zwanzig_staging/.env`) |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | Fasst **keine** `.env` an — neue Variablen müssen von Hand auf den Server |

## Existing Patterns

- **Fail-Fast in `main()`, nicht im Config-Load** (Go): `cmd/server/main.go:35-37` prüft nach
  `config.Load()` und beendet mit `log.Fatalf`. Grund: `internal/config/config_test.go` räumt
  die Umgebung leer und erwartet Defaults — eine Prüfung in `Load()` bräche diese Tests.
- **Fail-Fast im `lifespan`, nicht in `Settings()`** (Python): ausdrücklich so entschieden in
  `config.py:271-286`. `install_egress_guard` zeigt die Bauform.
- **Testlauf-Erkennung** existiert doppelt und uneinheitlich: Go über `cfg.TestFixtureDir != ""`
  (`egress/guard.go`, `session_secret_gate.go`), Python über `_in_pytest()` und
  `settings.is_test_mode`.
- **Secret als Header statt im Pfad** ist im Haus bereits entschieden und begründet:
  `internal/handler/telegram_webhook.go:9-12` prüft `X-Telegram-Bot-Api-Secret-Token` und
  erklärt in einem Kommentar, warum das URL-Segment nur noch Routing-Beiwerk ist (Log-Leaks).
- **Fail-closed bei fehlender Konfiguration** ebenda: leeres Secret → HTTP 503
  „webhook not configured" statt offener Endpoint.
- **Namenskonvention `GZ_`** auf beiden Seiten — mit genau einem Ausreißer:
  `TELEGRAM_WEBHOOK_SECRET` (`telegram_webhook.go:40`, ohne Präfix, per `os.Getenv`).

## Dependencies

- **Upstream (Go):** `envconfig` liefert die Konfiguration; `cfg.PythonCoreURL` bestimmt das
  Ziel aller 20 Aufrufe.
- **Upstream (Python):** `pydantic_settings.BaseSettings` liest `GZ_`-Variablen und `.env`.
- **Downstream:** **Jede** Funktion des Produkts, die den Python-Core berührt — Briefing-Versand,
  Vorschauen, Ortsvergleich, GPX-Import, Alarme, Scheduler, Telegram-Inbound. Eine vergessene
  Aufrufstelle bedeutet nicht „etwas unsicherer", sondern **diese Funktion ist tot** (401).
- **Dritter Prozess:** Das Frontend spricht ausschließlich die Go-API an, nie Python direkt —
  es ist von dieser Änderung nicht betroffen.

## Existing Specs

| Dokument | Inhalt |
|----------|--------|
| `docs/adr/0015-dual-stack-zielarchitektur.md` | **Konfliktpunkt:** hält fest, Python „bleibt hinter dem Go-Proxy, keine eigene Auth, keine neuen direkt exponierten Endpoints" |
| `docs/adr/0003-multi-tenant-isolation.md` | Pflicht zur echten `user_id` aus dem Auth-Kontext, nie `"default"` |
| `docs/adr/0030-session-auth-hmac-cookie.md` | Session-Cookie Frontend↔Go — nicht betroffen |
| `docs/specs/modules/go_api_setup.md` | Ursprungsarchitektur Go-Proxy → Python (:8000), ohne Auth |
| `docs/specs/modules/python_userid_integration.md` | Python liest `user_id` als reinen Query-Parameter |
| `docs/specs/bugfix/go_api_bind_localhost.md` | Strukturgleicher Vorgänger: Bind-Härtung für die **Go**-API (Issue #116), `GZ_HOST` mit Default `127.0.0.1` |
| `docs/context/fix-2139-session-secret-failfast.md` | Kontext des Geschwister-Issues, aus dem das Fail-Fast-Muster stammt |

**Es gibt keine Spec, die einen Auth-Vertrag Go→Python beschreibt.** Genau diese Lücke schließt
#2142.

## Risks & Considerations

### R1 — ADR-0015 wird umgekehrt (Prozess-Pflicht)

ADR-0015 hält „keine eigene Auth" in Python als Entscheidung fest. #2142 dreht das um. Nach
Hausregel wird eine dokumentierte Entscheidung nie still zurückgenommen: Es braucht ein
**neues ADR**, das ADR-0015 in diesem Punkt ablöst. Das ist kein Nebenprodukt, sondern ein
Liefergegenstand.

### R2 — 68 Testdateien bauen sich je einen eigenen `TestClient(app)`

Es gibt **keine** gemeinsame Client-Fixture; jede Datei importiert `from api.main import app`
und baut lokal ihren Client, teils mehrfach je Datei. Eine App-weite Pflichtprüfung bricht
diese Tests breit.

Der naheliegende Ausweg — die Prüfung bei `_in_pytest()` überspringen — ist **die gefährlichste
Option**: Dann ist der Wächter im gesamten Testlauf abgeschaltet und **kein** Test kann
beweisen, dass er wirkt. Genau dieses Muster hat uns hier schon einmal ein falsches Grün
geliefert (wirkungsloser Code schirmt die Tests ab). Der Entwurf muss stattdessen dafür sorgen,
dass die Prüfung **auch im Testlauf scharf** ist und die 68 Dateien den Header an **einer**
zentralen Stelle mitgeliefert bekommen (z. B. autouse-Fixture in `tests/conftest.py`), während
ein eigener Test bewusst **ohne** Header anfragt und 401 erwartet. Das ist in der Analyse-Phase
zu entscheiden und in der Spec als Akzeptanzkriterium festzuhalten.

### R3 — Ausrollen kann die Anwendung abschalten

Fail-Fast plus `deploy-gregor-prod.sh`, das die `.env` nicht anfasst, ergibt: Fehlt der Eintrag,
startet der Dienst nach dem Deploy nicht mehr. Entlastend wirkt, dass Go und Python in Prod
**dieselbe** `.env` lesen — ein Eintrag genügt je Umgebung, die beiden Seiten können nicht
auseinanderlaufen. Die Reihenfolge (erst Staging-`.env`, dann Prod-`.env`, dann Merge/Deploy)
gehört als ausdrücklicher Schritt in die Spec, nicht in eine Fußnote. Präzedenzfall aus dem
Deploy-Skript-Kommentar: eine ergänzte `EnvironmentFile`-Zeile lag wochenlang inaktiv und ließ
eine Ausfallmeldung still verschwinden.

### R4 — 20 Aufrufstellen, 17 eigene Clients: eine vergessene Stelle killt eine Funktion

Weil die Prüfung fail-closed ist, ist eine übersehene Aufrufstelle kein Schönheitsfehler,
sondern ein Funktionsausfall (401). Drei Bauformen stehen zur Wahl — Entscheidung gehört in
die Analyse:
(a) 20 Stellen einzeln um ein `Header.Set` ergänzen — maximal fehleranfällig, keine Sperre
gegen die 21. Stelle;
(b) ein gemeinsames Client-Paket (`internal/coreclient`), das alle 17 lokalen
`&http.Client{Timeout: …}` ersetzt — ein Engpass, durch den alles muss;
(c) ein globaler RoundTripper analog `egress.Install`, der auf den Python-Host filtert.
Unabhängig davon braucht es einen Nachweis, der **an der Wirkstelle** misst: nicht „Funktion X
setzt den Header", sondern „jede über den Go-Router erreichbare Python-Route kommt am
Empfänger mit gültigem Header an".

### R5 — `/health` muss ausgenommen bleiben

Go ruft `pythonURL + "/health"` bei jedem `/api/health` selbst auf (`proxy.go:22`), und
`ci-stack.sh:27-28` pollt den Python-Health direkt als Boot-Prüfung, bevor überhaupt etwas
konfiguriert sein kann. Der Endpoint liefert nur `{"status","version"}`, keine Nutzerdaten —
eine Ausnahme ist vertretbar, muss aber in der Spec begründet und **eng** gefasst sein
(genau dieser eine Pfad).

### R6 — Der Bind-Guard hat im Repo keinen Angriffspunkt

Es gibt **kein** `uvicorn.run()` im Repo; die App wird über die uvicorn-Kommandozeile gestartet
(systemd bzw. `ci-stack.sh`). Ein Guard innerhalb von `api/main.py` sieht die Bind-Adresse
darum nicht ohne Weiteres. Optionen: ein repo-eigener Einstiegspunkt (Startskript oder
`uvicorn.run()`-Wrapper), auf den die systemd-Units umgestellt werden — dann liegt die
Zusicherung wirklich im Repo, wie das Issue verlangt; oder ein Guard, der die Startparameter
des laufenden Prozesses auswertet. Der Vorgänger `docs/specs/bugfix/go_api_bind_localhost.md`
konnte das für Go sauber lösen, weil Go seinen Server selbst startet — für Python gilt das
nicht. **Nicht vorschnell entscheiden:** Ist das Shared Secret erst scharf, ist der Bind-Guard
nur noch zweite Verteidigungslinie; ein schlecht gebauter Guard, der beim Start falsch
anschlägt, richtet mehr Schaden an als er verhindert.

### R7 — CI-Stack muss das Secret kennen

`ci-stack.sh` startet beide Prozesse und ist der einzige Ort, an dem die neue Variable für die
Ampel gesetzt werden muss. Anders als bei `GZ_SESSION_SECRET` (dort bewusst ungesetzt, weil
halbseitig gesetzt die Cookie-Signatur bricht) ist das hier unkritisch: Das Skript exportiert
die Variable für **beide** Prozesse gleichzeitig, sie können also gar nicht auseinanderlaufen.

### R8 — Angrenzende Issues nicht mitschleifen

- **#2159** (Lokalhost-Guard hängt allein am nginx-Header-Verhalten) — verwandt, eigener Zuschnitt.
- **#1814** (Telegram-Webhook-Secret im URL-Pfad, Staging) — berührt dieselbe Datei, ist aber
  die *öffentliche* Seite; #2142 betrifft die *interne* Weitergabe Go→Python.
- **#2139** (Session-Secret-Fail-Fast) — liefert das Muster, läuft in einer anderen Sitzung.

### R9 — Namenswahl der Variablen

`GZ_`-Präfix ist die Hausregel (`envconfig.Process("GZ", …)` und `env_prefix="GZ_"`), also
liest dieselbe Variable auf beiden Seiten ohne Zusatzaufwand. Der einzige Gegenbeleg
(`TELEGRAM_WEBHOOK_SECRET` ohne Präfix) ist ein bekannter Ausreißer und **kein** Vorbild.

---

## Analysis

### Type

**Bug** (Security, Blocker aus Epic #2138).

### Empirisch geklärt (nicht vermutet)

| Frage | Messergebnis |
|-------|--------------|
| Läuft der FastAPI-`lifespan` unter `TestClient(app)` ohne `with`-Block? | **Nein.** Belegt gegen `api.main:app`: ohne `with` wird `install_egress_guard` 0-mal aufgerufen, mit `with` 1-mal. Nur **2 von 66** Testdateien benutzen den `with`-Block |
| Erreicht eine autouse-Fixture in `tests/conftest.py` alle Testdateien? | **Ja**, über `monkeypatch.setattr(TestClient, "__init__", …)`. Praktisch nachgestellt mit zwei Testdateien: Default-Header greift, expliziter Header im Testkörper überschreibt weiterhin. Grenze: Clients, die auf **Modulebene** gebaut werden, erreicht der Patch nicht — im Repo kommt das laut `grep -rn "^client = TestClient" tests/` **0-mal** vor |
| Kann die App ihre Bind-Adresse von innen erkennen? | **Ja**, auf drei Wegen (`sys.argv`, `gc`-Introspektion des uvicorn-`Server`-Objekts, `/proc/self/fd`). Der `gc`-Weg liest sogar den tatsächlich gebundenen Socket. Nicht gemessen: `--reload`, Multi-Worker, IPv6 |
| Setzt ein Go-Client einen eigenen `Transport`? | **Nein.** Alle Python-Core-Clients hängen an `http.DefaultTransport` |
| Ersetzt oder umhüllt `egress.Install` den Transport? | **Umhüllt** (`&guardedTransport{next: original}`), `Uninstall` stellt `original` zeiger-identisch wieder her |

### Affected Files (with changes)

**Scheibe 1 — „Go sendet"**

| File | Change | Description |
|------|--------|-------------|
| `internal/coreauth/transport.go` | CREATE | `Install(cfg)` umhüllt `http.DefaultTransport` und setzt den Header **nur** bei Treffer auf Host **und Port** aus `cfg.PythonCoreURL`. Bauform 1:1 nach `internal/egress/guard.go` |
| `internal/config/config.go` | MODIFY | Neues Feld `CoreSharedSecret` (`GZ_CORE_SHARED_SECRET`), Default `""` |
| `internal/config/core_secret_gate.go` | CREATE | `ValidateCoreSharedSecret(cfg)` — Klon des Musters aus `session_secret_gate.go` (#2139), inkl. Ausnahme `TestFixtureDir != ""` |
| `cmd/server/main.go` | MODIFY | Gate nach `ValidateSessionSecret` (Z.37); `coreauth.Install(cfg)` **vor** `egress.Install(cfg)` |
| `frontend/e2e/ci-stack.sh` | MODIFY | `GZ_CORE_SHARED_SECRET` exportieren (erreicht beide Prozesse gleichzeitig) |
| `internal/router/core_auth_sweep_test.go` | CREATE | Der eigentliche Wächter, siehe unten |
| `.env.example` | MODIFY | Neue Variable dokumentieren |

**Scheibe 2 — „Python erzwingt"**

| File | Change | Description |
|------|--------|-------------|
| `api/main.py` | MODIFY | `@app.middleware("http")` auf Modulebene: Header prüfen, `/health` ausnehmen, 401 bei falschem/fehlendem Header, 503 bei nicht konfiguriertem Secret |
| `src/app/config.py` | MODIFY | Feld `core_shared_secret` (`GZ_CORE_SHARED_SECRET`) |
| `api/routers/webhook.py` | MODIFY | Zusätzliche Telegram-Secret-Prüfung (Defense in Depth) |
| `internal/handler/telegram_webhook.go` | MODIFY | Telegram-Secret beim Weiterreichen an Python mitsenden |
| `tests/conftest.py` | MODIFY | Autouse-Fixture: Secret in die Umgebung + `TestClient.__init__` patchen |
| `tests/tdd/test_core_auth_enforcement.py` | CREATE | Positiv-/Negativnachweis inkl. Anfrage **ohne** Header → 401 |
| `docs/adr/00XX-python-core-authentifiziert-gegenueber-go.md` | CREATE | Löst ADR-0015 in diesem Punkt ab |

### Scope Assessment

- Dateien: 7 (Scheibe 1) + 7 (Scheibe 2)
- Geschätzte LoC: Scheibe 1 ≈ 180–250, Scheibe 2 ≈ 135–190 → **zusammen über dem Workflow-Limit von 250**, `loc_limit_override 500` erforderlich
- Risiko: **MITTEL-HOCH** — fail-closed über 20 Aufrufstellen. Ein falscher Host-Filter, eine falsche Installationsreihenfolge oder ein fehlender `.env`-Eintrag legt den gesamten Python-Core lahm

### Technical Approach

**A1 — Go: ein umhüllender Transport statt 20 Einzelpflaster.**
Alle 20 Aufrufstellen bauen `&http.Client{Timeout: …}` ohne eigenen `Transport`, hängen also
am selben `http.DefaultTransport`. Ein neues Paket `internal/coreauth` umhüllt diesen einmal
und setzt den Header ausschließlich bei Anfragen an Host **und Port** des Python-Cores. Damit
bleiben alle 17 unterschiedlichen Timeouts unangetastet, und keine der 20 Stellen wird
angefasst. Verworfen: ein gemeinsames Client-Paket (17 Umbaustellen, jede eine Gelegenheit,
ein Timeout zu verfälschen) und Einzelpflaster (kein struktureller Schutz gegen die 21. Stelle).
Der Preis ist Fernwirkung: ein künftiger Client mit eigenem `Transport` verliert den Header
still — genau dagegen steht A2.

**A1a — Installationsreihenfolge ist eine Zusicherung, keine Stilfrage.**
`coreauth.Install` muss **vor** `egress.Install` laufen. Grund (am Code geprüft): `egress`
merkt sich beim Installieren den vorgefundenen Transport und stellt ihn bei `Uninstall`
zeiger-identisch wieder her. Bei umgekehrter Reihenfolge würde ein `egress.Uninstall` den
Auth-Header mit entfernen. Das gehört als Kommentar an die Stelle **und** als Testfall.

**A2 — Der Nachweis läuft über den echten Router, nicht über die Funktion.**
Ein Sweep-Test zählt mit `chi.Router.Walk()` **alle** registrierten Routen selbsttätig auf
(kein handgepflegter Katalog — das ist der Punkt: die 21. Route wird automatisch erfasst),
schickt gegen jede eine authentifizierte Anfrage und prüft an einem `httptest`-Fake-Python-Core
nur eines: Jeder dort eingetroffene Request trägt den korrekten Header. Routen, die schon vor
dem Python-Aufruf abbrechen, tauchen am Fake gar nicht auf und werden nicht gezählt — gemessen
wird an der Wirkstelle. Präzedenzfälle für „echter Router + Fake-Backend" existieren bereits
(`internal/router/sms_fidelity_preview_test.go`, `briefing_subscription_test.go`).

**A3 — Python: Middleware, nicht `lifespan`.**
Gemessen: Der `lifespan` läuft in 64 von 66 Testdateien nicht. Eine Prüfung, die dort sitzt,
wäre für fast die ganze Testsuite unwirksam — dasselbe Muster, das uns schon einmal falsches
Grün geliefert hat. Die Durchsetzung gehört deshalb in eine `@app.middleware("http")` auf
Modulebene, die bei **jedem** Request greift, unabhängig vom Lifespan-Zustand.
Verhalten: Header fehlt oder falsch → **401**; Secret gar nicht konfiguriert → **503**
„not configured" (fail-closed, exakt das Muster aus `telegram_webhook.go:41-45`).
Ausgenommen ist **genau** `/health` — Go ruft ihn selbst ohne Header auf (`proxy.go:22`) und
`ci-stack.sh:27-28` pollt ihn als Boot-Prüfung; der Endpoint liefert keine Nutzerdaten.

**A4 — Die 68 Testdateien werden zentral versorgt, der Wächter bleibt scharf.**
Eine autouse-Fixture in `tests/conftest.py` setzt das Secret in die Umgebung und patcht
`TestClient.__init__`, sodass jede Instanz den Header trägt — die Testsuite verhält sich damit
wie die Go-API in Produktion. Ausdrücklich **kein** `_in_pytest()`-Bypass: Die Prüfung bleibt
im Testlauf aktiv, und ein eigener Test fragt bewusst **ohne** Header an und erwartet 401.
Ohne diesen Negativtest wäre die Fixture selbst der blinde Fleck.

**A5 — Zwei Scheiben in fester Reihenfolge, kein Übergangsschalter.**
Zuerst „Go sendet" (allein deploybar, Python prüft noch nicht — kein Verhalten ändert sich),
danach „Python erzwingt". Diese Reihenfolge lässt kein Fenster entstehen, in dem Python
bereits blockt, während Go noch nichts sendet. Ein Soft-Enforce-Schalter wäre ein Fremdkörper
(das Haus hat sich in `config.py:271-286` bewusst gegen solche Ausnahmen in `Settings`
entschieden) und müsste später wieder ausgebaut werden.

**A6 — Schritt 0 ist ein Liefergegenstand, keine Fußnote.**
`GZ_CORE_SHARED_SECRET` muss **vor** Scheibe 1 von Hand in die Staging- **und** die Prod-`.env`
eingetragen werden; `deploy-gregor-prod.sh` fasst diese Dateien nicht an. Entlastend: Go und
Python lesen je Umgebung dieselbe Datei, die beiden Seiten können nicht auseinanderlaufen.
Der Präzedenzfall steht im Deploy-Skript selbst — eine ergänzte Umgebungszeile lag dort einmal
wochenlang inaktiv und ließ eine Ausfallmeldung still verschwinden.

**A7 — Der Bind-Guard wird bewusst abgetrennt.**
Er ist zwar baubar (empirisch geprüft, drei Wege), aber jeder davon ist Introspektion eines
fremden Laufzeitobjekts. Die saubere Bauform wäre ein repo-eigener Einstiegspunkt plus
Umstellung der systemd-Units im Repo `henemm-infra` — eine Abhängigkeit über Repo-Grenzen
hinweg, die dieses Ticket nicht nebenbei mitziehen sollte. Ist das Shared Secret scharf,
schließt es die eigentliche Lücke vollständig; der Bind-Guard ist dann zweite
Verteidigungslinie. **Das ist eine Verkleinerung des Ticket-Umfangs und daher vom PO zu
bestätigen** — sie wird in der Spec ausdrücklich als abgetrennte Scheibe ausgewiesen, nicht
stillschweigend weggelassen.

### Open Questions (dem PO mit der Spec vorzulegen)

- [ ] Bind-Guard (Issue-Punkt 2) als eigenes Folge-Ticket abtrennen — einverstanden?

---
entity_id: core_shared_secret_auth
type: bugfix
created: 2026-09-07
updated: 2026-09-07
status: draft
version: "1.0"
tags: [security, bugfix, go-api, python-core, auth, multi-user, issue-2142]
---

# Core Shared-Secret Auth (Go → Python)

## Approval

- [ ] Approved

## Purpose

Behebt eine Auth-Bypass-Lücke (Issue #2142, Blocker aus Epic #2138): Der Python-Core (FastAPI, `api/main.py`) hat **keinerlei Authentifizierung**. Das gesamte Anti-Spoofing steckt bislang in einer einzigen Go-Funktion (`internal/handler/proxy.go:140-157`, `appendUserID`), die eine client-gelieferte `user_id` durch die authentifizierte ersetzt. Wer den Python-Core direkt anspricht — z. B. ein lokaler Prozess auf demselben Server —, umgeht diese Stelle vollständig und kann mit frei gewählter `?user_id=` fremde Daten lesen, fremde Briefings verschicken und über `POST /api/internal/telegram-webhook` gefälschte Telegram-Kommandos für ein fremdes Konto ausführen. Der Fix führt ein gemeinsames Geheimnis (Shared Secret) ein, das Go bei **jeder** Anfrage an Python als Header mitsendet und das Python bei **jeder** eingehenden Anfrage erzwingt.

Vorab gemessen: Auf dem Server binden beide Dienste bereits nur auf Loopback (`ss -ltnp`), der Angriff ist heute nicht aus dem Netz erreichbar. Das entwertet den Befund nicht — die Loopback-Bindung steht ausschließlich in der systemd-Unit (Repo `henemm-infra`, nicht im Anwendungs-Repo) und ist damit eine Betriebszusicherung, keine Code-Zusicherung. Netzwerk-Isolation als einziger Schutz ist genau die Annahme, die Epic #2138 für den Mehrnutzer-Betrieb ausräumt.

## Source

- **File:** `internal/handler/proxy.go`
- **Identifier:** `appendUserID` (Zeile 140-157) — bestehender, unzureichender Schutz; wirkt nur, solange der Python-Core ausschließlich über den Go-Proxy erreicht wird
- **Secondary File:** `api/main.py`
- **Identifier:** Router-Registrierung (Zeile 102-116) — Python-Core besitzt an dieser Stelle keine eigene Auth-Prüfung

> **Schicht-Hinweis:** Zwei getrennte Prozesse, zwei getrennte Scheiben — Go-API (`cmd/server/`, `internal/`) sendet das Geheimnis, Python-Core (`api/`, `src/app/`) erzwingt es. Beide lesen dieselbe Umgebungsvariable `GZ_CORE_SHARED_SECRET` unabhängig voneinander (`envconfig` mit Präfix `GZ` auf Go-Seite, `env_prefix="GZ_"` auf Python-Seite) — kein manueller Abgleich der Variablenwerte nötig, solange beide Prozesse dieselbe `.env`-Datei lesen.

## Estimated Scope

- **LoC:** Scheibe 1 ≈ 180–250, Scheibe 2 ≈ 135–190 — zusammen über dem Workflow-Limit von 250, `loc_limit_override 500` erforderlich
- **Files:** 7 (Scheibe 1) + 7 (Scheibe 2) = 14
- **Effort:** high (fail-closed über 20 Aufrufstellen; ein falscher Host-Filter, eine falsche Installationsreihenfolge oder ein fehlender `.env`-Eintrag legt den gesamten Python-Core lahm)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/egress/guard.go` (`Install`) | Reference Pattern | Bestehender globaler Transport-Patch (`http.DefaultTransport`) — Vorbild für den umhüllenden Auth-Transport; muss auf den Python-Host **und Port** gefiltert werden, sonst leckt das Geheimnis an fremde Ziele (Open-Meteo, Google Maps, Komoot, BetterStack) |
| `internal/config/session_secret_gate.go` (`ValidateSessionSecret`) | Reference Pattern | Fertiges Fail-Fast-Vorbild aus dem Geschwister-Issue #2139 — gleiche Bauform für `ValidateCoreSharedSecret` |
| `cmd/server/main.go` | Consumer | Startreihenfolge: `config.Load()` → `ValidateSessionSecret` → **neu:** `ValidateCoreSharedSecret` → `coreauth.Install(cfg)` → `egress.Install(cfg)` → `ListenAndServe` |
| `internal/router/router.go` | Consumer | Registriert alle Handler-Routen — Grundlage für den `chi.Router.Walk()`-Sweep-Test |
| `src/app/egress_guard.py` (`install_egress_guard`) | Reference Pattern | Bestes Vorbild für „Wächter im echten Laufzeitprozess" auf Python-Seite — Aktivierungsbedingung, Idempotenz-Flag |
| `src/app/config.py` (`Settings`, `_resend_default_deny`) | Reference Pattern | Dokumentierte Design-Entscheidung gegen Fail-Fast im Settings-Konstrukt — der Fail-Fast gehört in den `lifespan`/die Middleware, nicht in `Settings()` |
| `internal/handler/telegram_webhook.go` (`TELEGRAM_WEBHOOK_SECRET`-Prüfung) | Reference Pattern | Bereits entschiedene Bauform „Secret als Header, fail-closed bei fehlender Konfiguration (503)" — Vorbild für die zusätzliche Telegram-Secret-Prüfung in Python |
| `frontend/e2e/ci-stack.sh` | Test Infrastructure | Einziger Ort, der beide Prozesse als echte Dienste startet — muss `GZ_CORE_SHARED_SECRET` für beide Prozesse gleichzeitig exportieren |
| `tests/conftest.py` | Test Infrastructure | Muss eine autouse-Fixture bekommen, die alle 66 Testdateien zentral mit dem Header versorgt, ohne die Prüfung selbst abzuschalten |
| **Downstream:** jede Funktion, die den Python-Core berührt | Consumer | Briefing-Versand, Vorschauen, Ortsvergleich, GPX-Import, Alarme, Scheduler, Telegram-Inbound — eine vergessene Aufrufstelle bedeutet nicht „etwas unsicherer", sondern diese Funktion ist ab Scheibe 2 tot (401) |

## Implementation Details

**Scheibe 1 — „Go sendet" (allein deploybar, ändert kein Verhalten, solange Python noch nicht prüft):**

```
internal/coreauth/transport.go          CREATE  Install(cfg) umhüllt http.DefaultTransport,
                                                 setzt Header X-GZ-Core-Auth NUR bei Treffer
                                                 auf Host UND Port aus cfg.PythonCoreURL
                                                 (Bauform 1:1 nach internal/egress/guard.go)
internal/config/config.go               MODIFY  neues Feld CoreSharedSecret
                                                 (GZ_CORE_SHARED_SECRET), Default ""
internal/config/core_secret_gate.go     CREATE  ValidateCoreSharedSecret(cfg) — Klon aus
                                                 session_secret_gate.go (#2139), inkl.
                                                 Ausnahme TestFixtureDir != ""
cmd/server/main.go                      MODIFY  Gate direkt nach ValidateSessionSecret;
                                                 coreauth.Install(cfg) VOR egress.Install(cfg)
                                                 — siehe Reihenfolge-AC unten
frontend/e2e/ci-stack.sh                MODIFY  GZ_CORE_SHARED_SECRET exportieren
internal/router/core_auth_sweep_test.go CREATE  Sweep-Test über chi.Router.Walk()
.env.example                            MODIFY  neue Variable dokumentieren
```

Reihenfolge-Begründung: `egress` merkt sich beim Installieren den vorgefundenen Transport und stellt ihn bei `Uninstall` zeiger-identisch wieder her. Läuft `coreauth.Install` nach `egress.Install`, verschwindet der Auth-Header bei einem `egress.Uninstall()` still mit.

**Scheibe 2 — „Python erzwingt":**

```
api/main.py                       MODIFY  @app.middleware("http") auf Modulebene: Header
                                           prüfen, /health ausnehmen, 401 bei fehlendem/
                                           falschem Header, 503 bei nicht konfiguriertem
                                           Secret (fail-closed)
src/app/config.py                 MODIFY  Feld core_shared_secret (GZ_CORE_SHARED_SECRET)
api/routers/webhook.py            MODIFY  zusätzliche Telegram-Secret-Prüfung
                                           (Defense in Depth)
internal/handler/telegram_webhook.go MODIFY  Telegram-Secret beim Weiterreichen an Python
                                              mitsenden (heute fehlt das, Zeile 63-64)
tests/conftest.py                 MODIFY  autouse-Fixture: Secret in die Umgebung setzen +
                                           TestClient.__init__ patchen (Patch erreicht
                                           Modul-Level-Clients NICHT — im Repo laut
                                           `grep -rn "^client = TestClient" tests/` 0 Treffer,
                                           also unkritisch)
tests/tdd/test_core_auth_enforcement.py CREATE  Positiv-/Negativnachweis inkl. Anfrage
                                                 OHNE Header → 401
docs/adr/0062-python-core-authentifiziert-gegenueber-go.md  CREATE  löst ADR-0015 in
                                                                     diesem Punkt ab
```

Middleware statt `lifespan`-Hook: Gemessen läuft der `lifespan` in 64 von 66 Testdateien nicht mit (nur 2 Dateien nutzen den `with TestClient(app)`-Block). Eine Prüfung im `lifespan` wäre für fast die ganze Testsuite unwirksam. Die Durchsetzung sitzt deshalb in einer `@app.middleware("http")`, die bei jedem Request greift, unabhängig vom Lifespan-Zustand.

Header-Name auf beiden Seiten: `X-GZ-Core-Auth`. Variablenname auf beiden Seiten: `GZ_CORE_SHARED_SECRET` (Go: `envconfig` mit Präfix `GZ`; Python: `env_prefix="GZ_"` — dieselbe Variable, kein Abgleich nötig, solange Go und Python dieselbe `.env` lesen, was in Prod und Staging bereits der Fall ist).

## Expected Behavior

- **Input (Go → Python, jede der 20 Aufrufstellen):** eine ausgehende HTTP-Anfrage an `cfg.PythonCoreURL`.
- **Output:** die Anfrage trägt den Header `X-GZ-Core-Auth` mit dem Wert aus `GZ_CORE_SHARED_SECRET`.
- **Input (Go → fremdes Ziel, z. B. Open-Meteo):** eine ausgehende HTTP-Anfrage an einen anderen Host/Port als `cfg.PythonCoreURL`.
- **Output:** kein `X-GZ-Core-Auth`-Header wird gesetzt.
- **Input (Python, Anfrage ohne oder mit falschem Header):** beliebiger Endpoint außer `/health`.
- **Output:** HTTP 401, kein Seiteneffekt (kein Versand, keine Daten in der Antwort).
- **Input (Python, Secret im Prozess nicht konfiguriert):** beliebiger Endpoint außer `/health`.
- **Output:** HTTP 503 auf allen Routen außer `/health` (fail-closed).
- **Input (Go-API-Start ohne oder mit zu kurzem `GZ_CORE_SHARED_SECRET`):** Prozessstart.
- **Output:** Prozess beendet sich sofort (Fail-Fast), kein HTTP-Server startet — Ausnahme `TestFixtureDir != ""` (CI-Stack).
- **Side effects:** Bei korrekt gesetztem Secret auf beiden Seiten ändert sich das Laufzeitverhalten aller bestehenden Funktionen (Briefing-Versand, Vorschauen, Ortsvergleich, GPX-Import, Alarme, Scheduler, Telegram-Inbound) nicht.

## Test Plan

### Automated Tests (TDD RED)

#### Go Tests

- [ ] Test 1: GIVEN eine `Config` mit `CoreSharedSecret: ""` und leerem `TestFixtureDir` WHEN `ValidateCoreSharedSecret(cfg)` aufgerufen wird THEN liefert die Funktion einen Fehler ungleich `nil` zurück.
- [ ] Test 2: GIVEN eine `Config` mit gesetztem `TestFixtureDir` und leerem `CoreSharedSecret` WHEN `ValidateCoreSharedSecret(cfg)` aufgerufen wird THEN liefert die Funktion `nil` zurück (CI-E2E-Ausnahme greift).
- [ ] Test 3: GIVEN der echte Router über `router.New(...)` mit installiertem `coreauth.Install` WHEN `chi.Router.Walk()` alle registrierten Routen aufzählt und jede über einen authentifizierten Test-Client gegen einen `httptest`-Fake-Python-Core angefragt wird THEN trägt **jeder** am Fake eingetroffene Request den korrekten `X-GZ-Core-Auth`-Header.
- [ ] Test 4: GIVEN `coreauth.Install(cfg)` gefolgt von `egress.Install(cfg)` und anschließendem `egress.Uninstall()` WHEN eine Anfrage an den Python-Core gesendet wird THEN trägt sie weiterhin den `X-GZ-Core-Auth`-Header (Reihenfolge-Zusicherung).
- [ ] Test 5: GIVEN eine Anfrage an ein fremdes Ziel (anderer Host oder anderer Port als `cfg.PythonCoreURL`) WHEN sie über den mit `coreauth.Install` präparierten `http.DefaultTransport` läuft THEN trägt sie **keinen** `X-GZ-Core-Auth`-Header.

#### Python Tests

- [ ] Test 6: GIVEN das Secret ist im Prozess konfiguriert WHEN eine Anfrage an einen beliebigen Endpoint (außer `/health`) **ohne** `X-GZ-Core-Auth`-Header gesendet wird THEN antwortet der Prozess mit 401 und löst keinen Seiteneffekt aus (kein Versand, keine Daten in der Antwort).
- [ ] Test 7: GIVEN das Secret ist im Prozess konfiguriert WHEN eine Anfrage mit **falschem** `X-GZ-Core-Auth`-Header gesendet wird THEN antwortet der Prozess mit 401.
- [ ] Test 8: GIVEN das Secret ist im Prozess konfiguriert WHEN eine Anfrage mit **korrektem** `X-GZ-Core-Auth`-Header gesendet wird THEN verhält sich der Endpoint unverändert wie vor dieser Änderung.
- [ ] Test 9: GIVEN das Secret ist im Prozess **nicht** konfiguriert WHEN eine Anfrage an einen beliebigen Endpoint (außer `/health`) gesendet wird THEN antwortet der Prozess mit 503.
- [ ] Test 10: GIVEN beliebiger Konfigurationszustand des Secrets WHEN `GET /health` **ohne** `X-GZ-Core-Auth`-Header angefragt wird THEN antwortet der Prozess mit 200.
- [ ] Test 11: GIVEN der Telegram-Webhook-Endpoint erhält einen gültigen `X-GZ-Core-Auth`-Header, aber ein fehlendes oder falsches Telegram-Secret WHEN der Request verarbeitet wird THEN wird **kein** Telegram-Kommando ausgeführt (Defense in Depth, zusätzlich zur Core-Auth-Prüfung).
- [ ] Test 12: GIVEN die autouse-Fixture in `tests/conftest.py` versorgt `TestClient`-Instanzen zentral mit dem Header WHEN ein eigener Test bewusst eine Anfrage **ohne** Header stellt (Header explizit entfernt/überschrieben) THEN antwortet der Prozess mit 401 — der Wächter bleibt auch im Testlauf scharf.

## Acceptance Criteria

**Scheibe 1 — Go sendet**

- **AC-1:** Given die Go-API ist gestartet und `GZ_CORE_SHARED_SECRET` ist gültig konfiguriert / When irgendeine der bestehenden Funktionen (Briefing-Versand, Vorschau, Ortsvergleich, GPX-Import, Alarm, Scheduler, Telegram-Inbound) eine Anfrage an den Python-Core auslöst / Then trägt diese Anfrage nachweislich den Header mit dem gemeinsamen Geheimnis — geprüft über einen Sweep, der **alle** vom Router registrierten Routen selbsttätig aufzählt, nicht über eine von Hand gepflegte Liste, sodass eine künftig hinzukommende Aufrufstelle automatisch mitgeprüft wird.
  - Test: `internal/router/core_auth_sweep_test.go`, Test 3.

- **AC-2:** Given eine Anfrage der Go-API geht an ein Ziel, das **nicht** der Python-Core ist (z. B. Open-Meteo, Google Maps, Komoot, BetterStack) / When diese Anfrage über denselben, mit dem Auth-Mechanismus präparierten HTTP-Transport läuft / Then enthält diese Anfrage das gemeinsame Geheimnis **nicht** — die Filterung erfolgt anhand von Host **und** Port aus der konfigurierten Python-Core-Adresse.
  - Test: `internal/coreauth/transport_test.go` (bzw. gleichwertig benannt), Test 5.

- **AC-3:** Given die Go-API wird ohne `GZ_CORE_SHARED_SECRET` oder mit einem zu kurzen Wert gestartet, und `GZ_TEST_FIXTURE_DIR` ist nicht gesetzt / When der Prozess startet / Then beendet sich der Prozess sofort (Fail-Fast) und der HTTP-Server nimmt keine Anfragen an — mit derselben Ausnahme für den isolierten CI-Stack (`GZ_TEST_FIXTURE_DIR` gesetzt) wie beim Session-Secret-Gate aus #2139.
  - Test: `internal/config/core_secret_gate_test.go`, Test 1 und Test 2.

- **AC-4:** Given `coreauth.Install` und `egress.Install` sind beide aktiv, in dieser Reihenfolge installiert / When anschließend `egress.Uninstall()` aufgerufen wird und danach eine Anfrage an den Python-Core geht / Then trägt diese Anfrage weiterhin den Auth-Header — der Auth-Mechanismus überlebt das Deinstallieren des Egress-Guards, weil er zuerst installiert wurde.
  - Test: `internal/router/core_auth_sweep_test.go` bzw. eigener Reihenfolge-Test, Test 4.

**Scheibe 2 — Python erzwingt**

- **AC-5:** Given der Python-Core hat ein gültiges Geheimnis konfiguriert / When eine Anfrage an einen beliebigen Endpoint ohne den Auth-Header eintrifft / Then antwortet der Python-Core mit 401, und es entsteht kein Seiteneffekt — kein E-Mail-/Telegram-/SMS-Versand, keine Daten werden in der Antwort preisgegeben.
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 6.

- **AC-6:** Given der Python-Core hat ein gültiges Geheimnis konfiguriert / When eine Anfrage mit einem falschen Header-Wert eintrifft / Then antwortet der Python-Core mit 401.
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 7.

- **AC-7:** Given der Python-Core hat ein gültiges Geheimnis konfiguriert / When eine Anfrage mit dem korrekten Header-Wert eintrifft / Then verhält sich der angefragte Endpoint unverändert wie vor dieser Änderung — bestehende Funktionen bleiben für authentifizierte Aufrufer vollständig nutzbar.
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 8.

- **AC-8:** Given beliebiger Konfigurationszustand des Geheimnisses / When `GET /health` ohne Auth-Header angefragt wird / Then antwortet der Python-Core mit 200 — als einzige, eng gefasste Ausnahme, weil Go diesen Pfad selbst ohne Header abruft und der CI-Stack ihn als Boot-Prüfung nutzt, und weil der Endpoint keine Nutzerdaten liefert.
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 10.

- **AC-9:** Given der Python-Core läuft, aber `GZ_CORE_SHARED_SECRET` ist im Prozess gar nicht gesetzt / When eine Anfrage an einen beliebigen Endpoint außer `/health` eintrifft / Then antwortet der Python-Core mit 503 statt die Anfrage unauthentifiziert durchzulassen — fail-closed, niemals offen.
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 9.

- **AC-10:** Given eine Anfrage an den Telegram-Webhook-Endpoint trägt einen gültigen Core-Auth-Header, aber kein oder ein falsches Telegram-Secret / When der Request verarbeitet wird / Then wird kein Telegram-Kommando ausgeführt — die Telegram-Secret-Prüfung wirkt zusätzlich zur allgemeinen Core-Auth-Prüfung (Defense in Depth), und Go sendet dieses Secret beim Weiterreichen an Python mit (heute fehlt das).
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 11.

- **AC-11:** Given die gesamte Python-Testsuite läuft mit einer zentralen autouse-Fixture, die alle `TestClient`-Instanzen automatisch mit dem gültigen Header versorgt / When ein einzelner, bewusst dafür geschriebener Test eine Anfrage ohne diesen Header stellt / Then antwortet der Python-Core mit 401 — die Durchsetzung ist auch im Testlauf scharf, es gibt keine testlauf-spezifische Ausnahme, die die Prüfung insgesamt abschaltet.
  - Test: `tests/tdd/test_core_auth_enforcement.py`, Test 12.

## Known Limitations

- Das gemeinsame Geheimnis schützt gegen einen beliebigen lokalen Prozess auf demselben Server, **nicht** gegen einen Angreifer, der die `.env`-Datei selbst lesen kann — in diesem Fall hat er ohnehin bereits alle anderen dort hinterlegten Zugangsdaten.
- Der im Issue geforderte Bind-Guard („`127.0.0.1` im Startpfad erzwingen") ist bewusst **nicht** Teil dieser Spec — siehe eigener Abschnitt „Abgetrennter Umfang" unten.
- Die Loopback-Bindung beider Dienste bleibt weiterhin eine reine Betriebszusicherung (systemd-Unit im Repo `henemm-infra`), keine Code-Zusicherung. Mit scharfem Shared Secret ist das kein Restrisiko mehr für den in diesem Issue beschriebenen Angriff, wohl aber für andere, hier nicht behandelte Angriffsflächen.
- Bereits laufende Prozesse ändern ihr Verhalten nicht rückwirkend — der Fix wirkt erst beim nächsten Prozessstart nach dem Eintragen des Geheimnisses in die jeweilige `.env`.

## Rollout-Reihenfolge

Die Reihenfolge ist eine Zusicherung, kein Vorschlag — eine vertauschte Reihenfolge legt den Python-Core lahm oder lässt ein Zeitfenster mit widersprüchlichem Verhalten entstehen.

1. **Schritt 0 — Betriebsschritt, vor jedem Code-Merge:** `GZ_CORE_SHARED_SECRET` wird von Hand in `/home/hem/gregor_zwanzig_staging/.env` **und** `/home/hem/gregor_zwanzig/.env` eingetragen. `deploy-gregor-prod.sh` fasst diese Dateien nicht an — ein vergessener Eintrag zeigt sich nicht beim Deploy-Lauf, sondern erst beim nächsten Prozessneustart. Entlastend: Go und Python lesen je Umgebung dieselbe Datei, die beiden Seiten können nicht auseinanderlaufen.
   - **Folge eines vergessenen Eintrags:** Sobald Scheibe 1 (Fail-Fast-Gate) live ist, startet der Go-Dienst nach einem Neustart/Deploy nicht mehr — der Prozess bricht beim Start ab, bevor er Anfragen annimmt.
2. **Scheibe 1 („Go sendet"):** allein deploybar. Python prüft noch nichts, das Laufzeitverhalten ändert sich für Nutzer nicht — Go sendet ab jetzt lediglich zusätzlich den Header mit.
3. **Scheibe 2 („Python erzwingt"):** erst danach. Ab diesem Zeitpunkt lehnt der Python-Core unauthentifizierte Anfragen ab.

Diese feste Reihenfolge verhindert, dass ein Zustand entsteht, in dem Python bereits blockt, während Go den Header noch nicht sendet (kompletter Ausfall) oder umgekehrt ein Übergangsschalter nötig würde, der später wieder ausgebaut werden müsste.

## Abgetrennter Umfang

Der im Issue geforderte **Bind-Guard** („`127.0.0.1` im Startpfad erzwingen") wird als **eigenes Folge-Ticket abgetrennt** und ist **nicht** Teil dieser Spec.

**Begründung:** Es gibt kein `uvicorn.run()` im Repo — die App wird ausschließlich über die uvicorn-Kommandozeile gestartet (systemd-Unit bzw. `ci-stack.sh`). Die saubere Bauform wäre ein repo-eigener Einstiegspunkt plus Umstellung der systemd-Units im Repo `henemm-infra` — eine Abhängigkeit über Repo-Grenzen hinweg, die dieses Ticket nicht nebenbei mitziehen soll. Ist das gemeinsame Geheimnis erst scharf (Scheibe 1 + Scheibe 2 dieser Spec), schließt es die im Issue beschriebene Lücke bereits vollständig; der Bind-Guard wäre dann nur noch eine zweite Verteidigungslinie.

**Diese Verkleinerung des Ticket-Umfangs bedarf der Freigabe durch den Product Owner** — sie wird hier ausdrücklich benannt, nicht stillschweigend weggelassen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0062 (neu, nächste freie Nummer)
- **Rationale:** `docs/adr/0015-dual-stack-zielarchitektur.md` hält als Regel 2 fest: „Der Python-Core bekommt keine eigene Auth und keine neuen direkt exponierten Endpoints; er bleibt hinter dem Go-Proxy." Diese Spec dreht genau diesen Punkt um — der Python-Core bekommt eine eigene Auth-Prüfung. Nach Hausregel wird eine dokumentierte Entscheidung nie still zurückgenommen: Es braucht ein neues ADR, das ADR-0015 in diesem einen Punkt ablöst (Status von ADR-0015 wird auf „Abgelöst durch ADR-0062" gesetzt, alle übrigen Regeln von ADR-0015 — Zuständigkeitsgrenzen, kein Logik-Duplizierung — bleiben unverändert bestehen). Kontext, Entscheidung und verworfene Alternativen für das neue ADR stehen bereits vollständig in `docs/context/fix-2142-core-auth-shared-secret.md` (Abschnitte „Technical Approach" A1–A7 und „Risks & Considerations" R1–R9) und werden beim Anlegen des ADR-Dokuments daraus übernommen.

## Changelog

- 2026-09-07: Initial spec created based on Issue #2142 analysis (`docs/context/fix-2142-core-auth-shared-secret.md`)

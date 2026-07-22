---
entity_id: egress_guard
type: module
created: 2026-07-21
updated: 2026-07-21
status: draft
version: "1.0"
tags: [egress, isolation, staging, security]
workflow: feat-1337-egress-guard-core
---

<!-- Issue #1337 — Scheibe A: Zentraler Egress-Wächter -->

# Egress Guard — Zentraler Egress-Wächter (Scheibe A von #1337)

## Approval

- [x] Approved

## Purpose

Statt Umgebungs-Isolation weiter dienstweise nachzurüsten (jede Nachrüstung ließ
einen Weg offen — Muster siehe SMS-Leck #1336), einen zentralen Egress-Wächter
bauen, durch den in Test/Staging jeder ausgehende Ruf an einen kostenpflichtigen
oder nebenwirkungsbehafteten Dienst läuft. Der Wächter erzwingt pro Host genau
eine deklarierte Isolationsart (`TEST_ACCESS` oder `BLOCKED`) und blockt hart,
wenn ein Host keiner Art zugeordnet ist (Tripwire). In Prod ist er ein reiner
No-Op. Scheibe A liefert Fundament + vollständiges Inventar; Scheiben B–E
(SMS-Finalisierung, Telegram-alle-Methoden, Warn-Dienste, Resend-Relay
infra#114) docken später nur mit Inventar-Zeilen an.

## Source

- **File:** `src/app/egress_guard.py` (NEU)
- **Identifier:** `install_egress_guard(settings)`, `class IsolationKind`, `INVENTORY: dict[str, IsolationKind]`, `class EgressBlockedError`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/config.py` (`Settings`) | module | Liefert `is_test_mode`, `env`, `test_smtp_host`, `imap_host` als einzige Env-Quelle für die Aktivierungs- und Injektions-Entscheidung |
| `httpx.HTTPTransport.handle_request` | stdlib/lib | Transport-Primitiv, fängt in httpx 0.28.1 jeden synchronen Request ab, auch selbstgebaute `httpx.Client()` |
| `smtplib.SMTP.connect` | stdlib | Transport-Primitiv für alle SMTP-Sendewege (email.py Haupt-/Fallback-Host, core.py-Legacy) |
| `imaplib.IMAP4.open` | stdlib | Transport-Primitiv für Stalwart-Inbound (inbound_email_reader.py) |
| `api/main.py` | module | **Primäre** Bootstrap-Aufrufstelle für den echten Laufzeitprozess (`uvicorn api.main:app`, systemd `gregor-python-staging`) — 1 Aufruf im `lifespan`-Startpfad nach Settings-Konstruktion |
| `src/app/cli.py` | module | Zusätzliche Bootstrap-Aufrufstelle für Legacy-Debug-CLI-Läufe (1 Aufruf nach Settings-Konstruktion) |
| `tests/conftest.py` | module | Bootstrap-Aufrufstelle für pytest, inkl. Patch-Restore-Fixture gegen Leak in andere Tests |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/egress_guard.py` | CREATE | Guard-Kern: `IsolationKind`-Enum, `INVENTORY`, `EgressBlockedError`, `install_egress_guard()` mit 3 Monkeypatches + Idempotenz-Flag |
| `tests/tdd/test_egress_guard.py` | CREATE | Tripwire-Beweis via Sentinel: undeklariert→raise, deklariert→durch, Prod→No-Op, selbstgebauter `httpx.Client()`→raise |
| `api/main.py` | MODIFY | 1 Aufruf `install_egress_guard(settings)` im `lifespan`-Startpfad — der echte uvicorn-Prozess (Staging/Test) |
| `src/app/cli.py` | MODIFY | 1 Aufruf `install_egress_guard(settings)` nach Settings-Konstruktion (Legacy-Debug-CLI) |
| `tests/conftest.py` | MODIFY | Installations-Fixture + Restore-Fixture |

### Estimated Changes
- Files: 2 neu, 2 geändert
- LoC: ~200–240 (Limit 250 — Import-Guard für `requests`/`aiosmtplib` bewusst nach Scheibe B–E verschoben, als Restlücke dokumentiert)

## Test Plan

Kern-Schicht (deterministisch, kein Netz, kein Mock-Theater) in
`tests/tdd/test_egress_guard.py`. Zentrale Strategie: das Original-
`handle_request` (bzw. `connect`/`open`) wird durch einen Sentinel ersetzt, der
bei Aufruf eine `AssertedNetworkTouch`-Exception wirft. Das beweist ohne einen
einzigen echten Netzwerk-Touch, ob der Guard *vor* dem Transport entscheidet —
kein Mock, der nur die eigene Annahme zurückspiegelt, sondern ein echter Beweis
über Erreichbarkeit/Nicht-Erreichbarkeit des Transports.

### Automated Tests (TDD RED)

- [ ] Test 1 — Tripwire greift: GIVEN `is_test_mode=True` und ein Host, der in
  `INVENTORY` nicht deklariert ist, WHEN ein Request über `httpx`, `smtplib`
  oder `imaplib` an diesen Host geht, THEN wirft der Guard `EgressBlockedError`
  und der Sentinel-Transport wird nie erreicht.
- [ ] Test 2 — Selbstgebauter Client: GIVEN dieselbe Undeklariert-Situation,
  WHEN der Request über einen manuell instanziierten `httpx.Client()` (nicht
  über einen Shared-Client) läuft, THEN wirft der Guard ebenfalls
  `EgressBlockedError` (beweist, dass der Patch auf Klassenebene sitzt, nicht
  nur auf einer Instanz).
- [ ] Test 3 — Deklarierter Test-Zugang: GIVEN `is_test_mode=True` und ein als
  `TEST_ACCESS` deklarierter Host (`mail.henemm.com` über `smtplib.SMTP`),
  WHEN ein Request an diesen Host geht, THEN lässt der Guard durch und der
  Sentinel feuert (= Beweis „durchgelassen" ohne echte Verbindung).
- [ ] Test 4 — Prod-No-Op: GIVEN `env="production"` und `is_test_mode=False`,
  WHEN `install_egress_guard(settings)` aufgerufen wird, THEN bleibt
  `httpx.HTTPTransport.handle_request` (per Referenz-Identität `is`) identisch
  zur Original-Funktion — kein Patch wurde gesetzt.
- [ ] Test 5 — Alle drei Primitive abgedeckt: GIVEN `is_test_mode=True`, WHEN
  `install_egress_guard(settings)` läuft, THEN sind `httpx.HTTPTransport.
  handle_request`, `smtplib.SMTP.connect` und `imaplib.IMAP4.open` je einzeln
  gepatcht und die Entscheidungsregel greift für jedes für sich (drei separate
  Sentinel-Durchläufe, kein gemeinsamer Kurzschluss-Test).
- [ ] Test 6 — Idempotenz: GIVEN `install_egress_guard(settings)` wurde bereits
  aufgerufen, WHEN der Aufruf ein zweites Mal erfolgt, THEN entsteht kein
  Doppel-Patch — eine einzige Restore-Kette stellt die Original-Referenzen
  vollständig wieder her.
- [ ] Test 7 — Localhost-Ausnahme: GIVEN `is_test_mode=True` und ein Request an
  `localhost`/`127.0.0.1` ohne Inventar-Eintrag, WHEN der Request erfolgt,
  THEN lässt der Guard generisch durch, ohne `EgressBlockedError`.
- [ ] Test 8 — Restore-Fixture gegen Leak: GIVEN die `conftest.py`-Fixture
  installiert den Guard für einen Test, WHEN der Test beendet ist, THEN sind
  die drei Transport-Primitive wieder auf ihre Original-Referenzen
  zurückgesetzt (geprüft durch Referenz-Identitätsvergleich im nachfolgenden
  Test), damit kein Patch-Zustand in nicht-egress-bezogene Tests durchsickert.

## Implementation Details

### Aktivierungsbedingung
`install_egress_guard(settings)` patcht die drei Transport-Primitive **nur**
wenn `settings.is_test_mode or settings.env == "staging"`. In Prod (`env` !=
`"staging"` und nicht `is_test_mode`) wird **gar nicht gepatcht** — echter
No-Op, null Latenz, null Verhaltensänderung. Ein Modul-Level-Flag verhindert
Doppel-Patch bei mehrfachem `install()`-Aufruf (Idempotenz); der zweite Aufruf
ist ein No-Op gegenüber dem ersten Patch-Zustand.

### Inventar & Entscheidungsregel
`INVENTORY: dict[str, IsolationKind]` ist ein hartcodiertes, git-versioniertes
Sicherheits-Manifest (bewusst nicht per Env übersteuerbar — sonst Bypass).
`IsolationKind` hat von Anfang an beide Werte (`TEST_ACCESS`, `BLOCKED`), damit
Scheiben B–E ohne Schema-Bruch andocken. Entscheidungsregel je Host:
- `TEST_ACCESS` → Request durchlassen.
- `BLOCKED` → `EgressBlockedError` werfen, Transport nie erreicht.
- Host in **keiner** Deklaration → `EgressBlockedError` (der Tripwire).
- `localhost`/`127.0.0.1` → generisch durchlassen, keine explizite Deklaration nötig.

Dynamische Test-Hosts (`settings.test_smtp_host`, `settings.imap_host` nach
`for_testing()`) werden bei `install()`-Aufruf zur Laufzeit als `TEST_ACCESS`
in die Inventar-Auswertung injiziert (nicht ins statische Dict geschrieben).

### Initial-Inventar (Scheibe A trägt alle bekannten Hosts ein)
Damit der scharfe Tripwire Staging nicht lahmlegt, deklariert Scheibe A das
vollständige bekannte Host-Set mit konservativer Default-Isolationsart
(Feinjustierung je Dienst folgt in B–E):

| Host | IsolationKind |
|------|---------------|
| `api.open-meteo.com` | TEST_ACCESS |
| `air-quality-api.open-meteo.com` | TEST_ACCESS |
| `dataset.api.hub.geosphere.at` | TEST_ACCESS |
| `warnungen.zamg.at` | TEST_ACCESS |
| `api.brightsky.dev` | TEST_ACCESS |
| `radar-api.protezionecivile.it` | TEST_ACCESS |
| `api.meteoalarm.org` | TEST_ACCESS |
| `public-api.meteofrance.fr` | TEST_ACCESS |
| `www.risque-prevention-incendie.fr` | TEST_ACCESS |
| `gateway.seven.io` | BLOCKED |
| `api.telegram.org` | BLOCKED |
| `mail.henemm.com` | TEST_ACCESS |

`gateway.seven.io` und `api.telegram.org` sind als `BLOCKED` deklariert, weil
sie in Staging keinen dedizierten Test-Zugang haben (SMS-Kosten bzw.
Chat-ID-Risiko) — Scheiben B/C verfeinern das (z.B. Test-Chat-ID als eigener
`TEST_ACCESS`-Pfad), das ist bewusst außerhalb von Scheibe A.

### Deterministischer Tripwire-Test (kein Netz, kein Mock-Theater)
Das Original-`handle_request` wird durch einen Sentinel ersetzt, der eine
`AssertedNetworkTouch`-Exception wirft, sobald er erreicht wird — das beweist
ohne ein gesendetes Byte, ob der Guard *vor* dem Transport entscheidet:
- `is_test_mode=True`, undeklarierter Host (z.B. ein nicht im Inventar
  gelisteter Host) → `EgressBlockedError`, Sentinel nie erreicht. Auch über
  einen selbstgebauten `httpx.Client()` → gleicher Raise.
- Deklarierter Test-Host (`mail.henemm.com` über `smtplib.SMTP`) → durch →
  Sentinel feuert = Beweis „durchgelassen" ohne echte Verbindung.
- `env="production"` → `httpx.HTTPTransport.handle_request` ist identisch mit
  der Original-Funktionsreferenz (kein Patch gesetzt).

### Installation
Drei Bootstrap-Stellen:
- `api/main.py` — **primär**: ein Aufruf `install_egress_guard(settings)` im
  `lifespan`-Startpfad (nach `Settings()`-Konstruktion, vor Telegram-Menü-Init).
  Dies ist der **echte** Laufzeitprozess (`uvicorn api.main:app`, systemd
  `gregor-python-staging.service` mit `GZ_ENV=staging`) — nur hier laufen die
  produktiven Endpunkte (z.B. `POST /api/notify/test`, Scheduler-Dispatch), die
  echten Egress an kostenpflichtige/nebenwirkungsbehaftete Dienste auslösen
  können. Ohne diese Stelle wäre der Server ungeschützt (Fix F001, Adversary
  BROKEN 2026-07-22). No-Op in Prod über die Modul-Aktivierungsbedingung.
- `src/app/cli.py` — zusätzlich: ein Aufruf direkt nach der Settings-
  Konstruktion, greift für jede Legacy-Debug-CLI-Ausführung in Staging.
- `tests/conftest.py` — Fixture, die `install_egress_guard()` vor jedem
  Testlauf aktiviert und nach Testende die Original-Referenzen wiederherstellt
  (Restore-Fixture gegen Leak in andere, nicht-egress-bezogene Tests).

Alle drei Stellen sind gegen Doppel-Install robust: Das modulinterne
`_installed`-Flag macht jeden Zweit-`install()` zum No-Op (z.B. wenn ein Test
via `TestClient` den App-`lifespan` auslöst, während die conftest-Fixture den
Guard bereits installiert hat). `uninstall_egress_guard()` restauriert stets
die beim Modul-Import eingefangenen **wahren** Original-Referenzen — der
App-Start verliert damit keine Restore-Referenz, es entsteht kein Leak.

### Andock-Fläche für Scheiben B–E
B–E fügen ausschließlich Inventar-Zeilen (`host → IsolationKind`) plus je
einen Deklarations-Test hinzu, oder verschärfen einzelne Einträge von
`TEST_ACCESS` auf `BLOCKED`. Die Guard-Mechanik selbst (Monkeypatch-Kern,
Entscheidungsregel, Idempotenz) wird von B–E **nicht** angefasst.

## Expected Behavior

- **Input:** `Settings`-Objekt mit `is_test_mode`, `env`, `test_smtp_host`, `imap_host`; ausgehende Requests über `httpx`, `smtplib`, `imaplib` aus beliebigen Providern/Channels
- **Output:** In Test/Staging entweder durchgelassener Request (deklarierter Host) oder `EgressBlockedError` (undeklarierter/`BLOCKED`-Host); in Prod unverändertes Original-Verhalten
- **Side effects:** Monkeypatch der drei genannten Klassenmethoden ausschließlich innerhalb des Prozesslebenszyklus, in dem `install_egress_guard()` lief; keine Persistenz, keine Datei-Schreibvorgänge

## Acceptance Criteria

- **AC-1:** Given `is_test_mode=True` und ein Host, der in `INVENTORY` nicht deklariert ist / When ein Request über `httpx`, `smtplib` oder `imaplib` an diesen Host geht — auch über einen selbstgebauten `httpx.Client()` / Then wirft der Guard `EgressBlockedError` und der Sentinel-Transport (echter Netzwerk-Touch) wird nie erreicht
  - Test: `test_egress_guard.py::test_undeclared_host_blocked_before_transport` und `test_undeclared_host_blocked_custom_client`

- **AC-2:** Given `is_test_mode=True` und ein als `TEST_ACCESS` deklarierter Host (z.B. `mail.henemm.com` über `smtplib.SMTP`) / When ein Request an diesen Host geht / Then lässt der Guard durch und der Sentinel-Transport wird erreicht (Beweis „durchgelassen" ohne echte Verbindung)
  - Test: `test_egress_guard.py::test_declared_test_access_host_passes_through`

- **AC-3:** Given `env="production"` und `is_test_mode=False` / When `install_egress_guard(settings)` aufgerufen wird / Then bleibt `httpx.HTTPTransport.handle_request` identisch mit der Original-Funktionsreferenz — kein Patch wurde gesetzt, beweisbarer No-Op
  - Test: `test_egress_guard.py::test_prod_mode_installs_no_patch`

- **AC-4:** Given `is_test_mode=True` / When `install_egress_guard(settings)` läuft / Then sind alle drei Transport-Primitive (`httpx.HTTPTransport.handle_request`, `smtplib.SMTP.connect`, `imaplib.IMAP4.open`) gepatcht und die Entscheidungsregel greift für jedes einzeln
  - Test: `test_egress_guard.py::test_all_three_transports_covered`

- **AC-5:** Given `install_egress_guard(settings)` wurde bereits einmal aufgerufen / When der Aufruf ein zweites Mal erfolgt / Then entsteht kein Doppel-Patch (Original-Referenz bleibt über eine einzige Restore-Kette korrekt wiederherstellbar)
  - Test: `test_egress_guard.py::test_double_install_is_idempotent`

- **AC-6:** Given `is_test_mode=True` und ein Request an `localhost` oder `127.0.0.1` / When der Request ohne explizite Inventar-Deklaration erfolgt / Then lässt der Guard generisch durch, ohne `EgressBlockedError`
  - Test: `test_egress_guard.py::test_localhost_passes_through_without_declaration`

## Known Limitations

- Import-Guard (Erkennung von `requests`/`aiosmtplib`, falls künftig eingeführt) ist NICHT Teil von Scheibe A — LoC-Budget. Aktuell gibt es keine `requests`/`aiosmtplib`/`urlopen`-Aufrufe im Repo (nur `urllib.parse.urlencode`), daher keine akute Lücke, aber dokumentierte Restlücke für B–E.
- Validation-Tools (`src/validation/ground_truth.py` — Bergfex, `src/validation/geosphere_validator.py`) sind bewusst außerhalb von Scheibe A — sie laufen nicht im Staging-Report-Prozess.
- `@pytest.mark.live`-Tests installieren den Guard bewusst nicht (echte APIs sind dort gewollt).
- Scheiben B (SMS-Finalisierung), C (Telegram-alle-Methoden), D (Warn-Dienste-Feinjustierung), E (Resend-Relay, infra#114) sind explizit NICHT Teil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Interceptor-Ansatz (zentraler Monkeypatch auf drei Transport-Primitive) statt dünnem Wrapper pro Modul — Begründung siehe `docs/context/feat-1337-egress-guard-core.md` Abschnitt „Warum nicht Wrapper": ein Wrapper reproduziert die Kernursache von #1337 (Disziplin-Abhängigkeit an 15+ Call-Sites, bewiesen durch den bestehenden radar_service-Pfad, der `get_provider`+Fixtures bereits umgeht). Kein eigenständiger ADR nötig, da die Entscheidung vollständig im Analyse-Dokument dokumentiert und hier übernommen ist.

## Regel-Budget

Neuer Laufzeit-Guard: Prüfdatum **2026-10-19** (+90 Tage). Am Prüfdatum gilt:
kein nachweisbarer Fang (kein verhinderter versehentlicher Prod-Call in
Staging) → Rückbau. Alternativ entfällt die Prüfpflicht, wenn der Guard
bestehende dienstweise Guards (14-Türen-Muster, siehe
`reference_env_isolation_all_external_services`) ersetzt statt sie zu
ergänzen.

## Changelog

- 2026-07-21: Initial spec erstellt — Issue #1337, Scheibe A
- 2026-07-21: `## Test Plan`-Sektion ergänzt (nach `## Scope`, vor `## Implementation Details`) — spec-validator INVALID behoben

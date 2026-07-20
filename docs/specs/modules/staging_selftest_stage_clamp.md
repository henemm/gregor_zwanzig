---
entity_id: staging_selftest_stage_clamp
type: bugfix
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [scheduler, weather, staging-e2e, bugfix]
workflow: fix-1325-staging-e2e-selftest
---

<!-- Issue #1325 — Staging-E2E-Selbsttest scheitert an ~5 von 7 Wochentagen -->

# Staging-Selbsttest: Datums-Klemme im Test-Sendepfad (#1325)

## Approval

- [ ] Approved

## Purpose

Der manuelle/staging Test-Sendepfad für Trip-Briefings (`send_test_report` /
`_send_trip_report_outcome(..., allow_test_fallback=True)`) darf nicht mehr
still scheitern, wenn der Test-Trip ausschließlich Etappen in der
Vergangenheit hat. Aktuell rutscht das vergangene Etappendatum ungeklammert
in den Wetter-Abruf, Open-Meteo liefert dafür keine Daten, der Totalausfall-
Schutz (#1113) greift und die Mail wird mit einer irreführenden
"keine Etappendaten"-Meldung verweigert. Das blockiert den Staging-Gate
(#521) und damit jeden Backend-Deploy, sobald der wöchentliche Refresh-Cron
des Test-Trips (Infra, separat) einmal hinterherhinkt.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportSchedulerService._send_trip_report_outcome`, `select_test_stage`, neu `send_test_report_outcome`
- **File:** `api/routers/scheduler.py`
- **Identifier:** `send_test_trip_report`

> Schicht: Python-Core/Domain-Backend (`api/`, `src/services/`) — kein Go-/Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~45 (Kern-Fix) + ~40 (Kern-Tests)
- **Files:** 2 Code-Dateien, 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `datetime.date` (stdlib) | stdlib | Klemm-Arithmetik (`date.today()`, Tagesdifferenz) |
| `providers.base.get_provider` | intern | Provider-Auflösung für `_fetch_weather`; im Repro-Test gezielt gemonkeypatcht (siehe Test Plan) |
| `app.models.TripSegment` | intern | Trägt `start_time`/`end_time`, die geklemmt werden |
| `services.trip_segments.convert_trip_to_segments` | intern | Baut Segmente aus Etappe + Datum (Aufruf bleibt unverändert — Klemme setzt NACH dem Bau an) |
| `FastAPI TestClient` (Test-Dependency, bereits im Projekt genutzt) | test | Router-Ebene für AC-3-Meldungsdifferenzierung |

## Implementation Details

### 1. Datums-Klemme im Test-Fallback-Pfad (`trip_report_scheduler.py`)

Im bestehenden Fallback-Block von `_send_trip_report_outcome()`
(`if not segments and allow_test_fallback:`, aktuell Zeile 709-713) bleibt
`target_date = fb.date` unverändert — nur damit findet
`trip.get_stage_for_date()` weiterhin dieselbe Etappe für Header, Marker,
Snapshot etc. Zusätzlich: liegt `target_date` in der Vergangenheit, werden
NUR die für `_fetch_weather()` (Zeile 746) verwendeten
`start_time`/`end_time` der frisch gebauten Segmente um die Differenz
`date.today() - target_date` Tage nach vorne verschoben (Uhrzeit-Anteil
bleibt erhalten). Neue kleine, reine Hilfsfunktion (keine Netz-/IO-Zugriffe),
z. B. `_clamp_segments_to_today(segments, from_date)`.

Alle anderen Verwendungen von `target_date` (Stage-Header, Multi-Day-Trend,
Thunder-Forecast, Daylight, Vortag-Vergleich, Snapshot, Marker) bleiben
unverändert auf dem echten (ggf. vergangenen) Etappendatum — siehe Known
Limitations.

### 2. Ehrlicher Outcome bei genuinem No-Weather (`trip_report_scheduler.py` + `api/routers/scheduler.py`)

Neue dünne öffentliche Methode `send_test_report_outcome(trip, report_type) -> str`,
die direkt `_send_trip_report_outcome(trip, report_type, allow_test_fallback=True)`
zurückgibt (Outcome-String `"sent" | "no_stage" | "no_weather" | "no_channels"`,
analog zum bestehenden `send_on_demand_report`-Muster aus #1007). Der
bestehende `send_test_report()`-Bool-Wrapper bleibt für seine 6 heutigen
Aufrufer unverändert.

`api/routers/scheduler.py:send_test_trip_report` ruft künftig
`send_test_report_outcome` statt `send_test_report` auf:

- `"no_stage"` → bestehende Meldung "keine Etappendaten für das aktuelle Datum" (bleibt korrekt für den echten No-Stage-Fall)
- `"no_weather"` → neue, ehrliche Meldung ("keine Wetterdaten für die gewählte Etappe verfügbar"), weiterhin HTTP 422
- `"no_channels"` / `"sent"` → HTTP 200 `{"sent": true}` (identisch zum bisherigen bool-True-Verhalten, kein Verhaltensbruch)

## Expected Behavior

- **Input:** Trip mit ausschließlich vergangenen Etappen, Test-Sendepfad (`allow_test_fallback=True`)
- **Output:** Echte Wetterdaten für "heute" werden abgerufen, Briefing wird als `sent` zugestellt statt mit `no_weather`/422 zu scheitern
- **Side effects:** Keine Änderung an Persistenz/Datenmodell; regulärer Scheduler-Pfad (`allow_test_fallback=False`) unverändert; genuine No-Weather-Fälle bekommen eine unterscheidbare, ehrliche Meldung statt der bisherigen No-Stage-Meldung

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen sämtliche Etappen ein Datum < heute tragen, When der Test-Sendepfad (`send_test_report` bzw. `_send_trip_report_outcome` mit `allow_test_fallback=True`) ein Briefing erzeugt, Then wird der Wetter-Abruf mit dem Datum „heute" ausgeführt (das vergangene Etappendatum wird für den Wetterabruf auf heute geklemmt), sodass ein echter Forecast vorliegt und das Briefing als `sent` zugestellt wird — Outcome ist NICHT `no_weather` und die API antwortet NICHT mit 422.
  - Test: Echter Aufruf von `_send_trip_report_outcome(trip, "morning", allow_test_fallback=True)` gegen einen datums-sensitiven Open-Meteo-Provider-Double (siehe Test Plan) — Outcome-String, nicht bloß ein Dateiinhalt.

- **AC-2:** Given der reguläre (Nicht-Test-)Scheduler-Pfad mit `allow_test_fallback=False`, When ein Briefing erzeugt wird, Then bleibt das Verhalten unverändert — es findet KEINE Datums-Klemmung statt. Die Änderung wirkt ausschließlich im Test-Fallback-Pfad.
  - Test: Derselbe Trip, derselbe Aufruf mit `allow_test_fallback=False` → Outcome bleibt `no_stage`, unverändert zum Bestandsverhalten vor diesem Fix.

- **AC-3:** Given ein Test-Sendeversuch, bei dem trotz gültigem (heutigem) Datum tatsächlich keine Wetterdaten beschafft werden können, When der Sendepfad scheitert, Then liefert `api/routers/scheduler.py` eine ehrliche, unterscheidbare Fehlermeldung bzw. der Service einen klar benannten Outcome, der „keine Wetterdaten" von „keine Etappendaten für das aktuelle Datum" (no_stage) sauber trennt — die alte irreführende Meldung darf für den No-Weather-Fall nicht mehr erscheinen.
  - Test: Router-Test (FastAPI TestClient) gegen `POST /api/scheduler/trips/{trip_id}/send` mit demselben Provider-Double (liefert auch für "heute" einen Fehler) → 422-Body enthält die neue Meldung, NICHT mehr "keine Etappendaten für das aktuelle Datum".

## Known Limitations

- Cron-Rechte und -Kadenz des wöchentlichen Test-Trip-Refresh (Defekt 1 aus
  Issue #1325) sind Infra-Zuständigkeit und ausdrücklich NICHT Teil dieser
  Spec/dieses Fixes — separate Koordination via MQ an `infra`.
- Der tote Legacy-Persistenzpfad `data/.../trips/{id}.json` (seit #1250
  Scheibe 7a von keinem Loader mehr gelesen) wird nicht angefasst.
- Die Datums-Klemmung wirkt NUR auf die für den Wetter-Abruf verwendeten
  `start_time`/`end_time` der Segmente. Andere optionale Bausteine, die
  intern ebenfalls das (unveränderte, ggf. vergangene) `target_date`
  verwenden (Multi-Day-Trend, Thunder-Forecast, Daylight-Fenster,
  Vortag-Vergleich), bleiben auf dem echten Etappendatum und können bei
  sehr alten Test-Trips fail-soft leer bleiben — das Kernziel (Mail wird
  versendet, Outcome `sent`) ist davon unberührt.
- Der global aktive `FixtureProvider` (`tests/conftest.py`, `autouse`, alle
  Nicht-`live`-Tests) ist datumsblind — er ignoriert `start`/`end` und
  liefert immer Daten für "heute", unabhängig vom angefragten Zeitraum. Er
  kann diesen Bug NICHT reproduzieren; der Repro-Test (AC-1/AC-3) braucht
  einen dedizierten, datumssensitiven Provider-Double, der wie der echte
  Open-Meteo-Forecast-Endpoint auf Vergangenheits-Anfragen mit Fehler
  reagiert und nur für "heute" reale (aufgezeichnete Innsbruck-)Daten
  liefert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokaler Bugfix, kein architekturrelevanter Präzedenzfall)
- **Rationale:** Entscheidung "Klemmen auf heute im Test-Pfad statt harter
  Ablehnung" statt z. B. "Test-Send verweigern, wenn keine Etappe ≥ heute
  existiert": Zweck des Test-/Staging-Sendepfads ist der Nachweis, dass die
  End-zu-Ende-Pipeline (Rendering, Versand, Zustellung) funktioniert — nicht
  die Verfügbarkeit historischer Forecast-Daten für ein bestimmtes
  Kalenderdatum. In Produktion haben reale Trips praktisch immer
  Zukunfts-Etappen; der All-Past-Fallback trifft nur stale Demo-/Test-Trips.
  Eine harte Ablehnung (Status quo, = der Bug) koppelt die Deploy-Gate-
  Gesundheit unnötig an die Frische eines Cron-Jobs, der fachlich nichts
  mit der Code-Qualität zu tun hat. Die Alternative "Klemmung überall in
  `target_date`" wurde verworfen, weil sie stage-Identifikation über
  `trip.get_stage_for_date()` bricht (kein Stage-Match mehr für die
  geklemmte Zukunftsdatum) — die Klemme bleibt daher gezielt auf die
  Segment-Zeiten beschränkt, die tatsächlich in den Wetter-Abruf gehen.

## Test Coverage

Neue Testdatei `tests/tdd/test_trip_report_test_send_past_stage_clamp.py`
(Kern-Schicht, deterministisch, netzfrei — Namensregel: nach Verhalten
benannt, nicht nach Issue-Nummer):

- **AC-1-Test:** Trip mit zwei Etappen, beide < heute. Ein datumssensitiver
  Provider-Double (Innsbruck-Fixture-Daten, real aufgezeichnete Struktur)
  wird via `monkeypatch.setattr` gezielt für `providers.base.get_provider`
  in diesem Test injiziert — liefert Fehler (`ProviderRequestError`) für
  Zeiträume, die NICHT "heute" abdecken, echte Daten für "heute" (spiegelt
  das reale Open-Meteo-Forecast-Endpoint-Verhalten, kein Mock-Theater).
  Aufruf: `TripReportSchedulerService(user_id=...)._send_trip_report_outcome(trip, "morning", allow_test_fallback=True)`.
  Vor Fix: Outcome `"no_weather"`. Nach Fix: Outcome `"sent"`.
- **AC-2-Test:** Derselbe Trip/Provider-Double, aber
  `allow_test_fallback=False` → Outcome bleibt `"no_stage"`, unverändert.
  Beweist, dass die Klemme den regulären Scheduler-Pfad nicht berührt.
- **AC-3-Test:** Derselbe Trip, Provider-Double liefert Fehler auch für
  "heute" (genuiner Ausfall). Zwei Ebenen:
  - Service: `send_test_report_outcome(trip, "morning")` → Outcome `"no_weather"`.
  - Router: FastAPI-`TestClient`-Aufruf gegen
    `POST /api/scheduler/trips/{trip_id}/send` → HTTP 422, Body enthält die
    neue ehrliche Meldung, NICHT mehr "keine Etappendaten für das aktuelle
    Datum".

Alle Tests laufen unter der bestehenden `_isolate_data_root`-Autouse-Fixture
(`tests/conftest.py`, Issue #1133/#1265) — kein Schreiben in den echten
`data/users/`-Baum.

## Changelog

- 2026-07-20: Initial spec created — Issue #1325, Workflow `fix-1325-staging-e2e-selftest`

---
entity_id: fix_1557_wetter_cache_testisolation
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: draft
version: "1.0"
tags: [tests, weather-cache, test-isolation, ci-ratsche]
workflow: fix-1557-no-weather-outcome
---

<!-- Issue #1557 — Test-Sendepfad meldet `sent`/HTTP 200 statt ehrlichem `no_weather`/422 -->

# Wetter-Cache-Testisolation: `no_weather`-Outcome in AC-3 nicht erreichbar (#1557)

## Approval

- [x] Approved — PO, 2026-08-14, mit Auflage: „wenn auch alle Frontend-Tests
      enthalten sind" ⇒ als **AC-6** aufgenommen.

## Purpose

`tests/tdd/test_trip_report_test_send_past_stage_clamp.py::TestAC3GenuineNoWeatherHonestOutcome`
prüft die in #1325 freigegebene Zusicherung, dass ein echter Wetter-Totalausfall
den ehrlichen Outcome `no_weather` (HTTP 422) liefert statt `sent` (HTTP 200).
Der Test ist isoliert grün, im Verbund mit den vorangehenden Testfällen der
Datei rot — ein **Test-Isolationsfehler**, kein Produktfehler (belegt in
`docs/context/fix-1557-no-weather-outcome.md`). Diese Spec zieht den Fix
ausschließlich auf der Test-/CI-Seite: einen zentralen Reset-Punkt für den
geteilten Wetter-Cache in `tests/conftest.py`, Hermetik für den betroffenen
Router-Testfall, und das Entfernen der Datei aus der CI-Ausschlussliste.
**Produktivcode wird nicht geändert** — das Risiko dafür ist geprüft und
verneint (Kontext-Dokument, Abschnitt „Produktrisiko: geprüft und verneint").

## Source

- **File:** `tests/conftest.py`
- **Identifier:** neue Fixture `_reset_shared_weather_cache` (analog `_reset_shared_radar_cache:280`, `_reset_thunder_window_cache:295`)
- **File:** `tests/tdd/test_trip_report_test_send_past_stage_clamp.py`
- **Identifier:** `TestAC3GenuineNoWeatherHonestOutcome::test_router_returns_422_with_honest_no_weather_message`
- **File:** `.github/ci_tdd_excludes.txt`
- **Identifier:** Zeile 88 (`tests/tdd/test_trip_report_test_send_past_stage_clamp.py`)

> Schicht: reine Test-/CI-Infrastruktur (`tests/`, `.github/`) — kein
> Produktivcode in `src/`, `api/`, `internal/`, `frontend/` betroffen.

## Estimated Scope

- **LoC:** ~20 (Reset-Fixture in `conftest.py` + `monkeypatch.setenv` im Router-Test), 1 Zeile Entfernung in der Ratsche-Liste
- **Files:** 3 (alle Test-/CI-Seite)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_cache.py:308` `reset_shared_weather_cache_for_tests` | intern | bereits vorhandene Test-Reset-Funktion für den Prozess-Singleton `_shared_cache` |
| `tests/conftest.py:280` `_reset_shared_radar_cache` | intern | Vorbild-Fixture (gleiches Muster, anderer Cache, #1329 C2) |
| `tests/conftest.py:295` `_reset_thunder_window_cache` | intern | zweites Vorbild (Prozess-Singleton mit 600s-TTL, gleiches Muster) |
| `monkeypatch` (pytest-Fixture) | test | setzt `GZ_SMTP_HOST`/`GZ_SMTP_USER`/`GZ_SMTP_PASS` für den Router-Testfall |
| `.github/ci_tdd_excludes.txt` | Ratsche | darf nur schrumpfen (#1196) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `tests/conftest.py` | MODIFY | neue `@pytest.fixture(autouse=True) _reset_shared_weather_cache`, ruft `reset_shared_weather_cache_for_tests()` vor und nach jedem Testfall, analog `:280`/`:295` |
| `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` | MODIFY | `monkeypatch.setenv` für `GZ_SMTP_HOST`/`GZ_SMTP_USER`/`GZ_SMTP_PASS` im Testfall `test_router_returns_422_with_honest_no_weather_message` |
| `.github/ci_tdd_excludes.txt` | MODIFY | Zeile 88 (`tests/tdd/test_trip_report_test_send_past_stage_clamp.py`) entfernt |

### Estimated Changes

- Files: 3
- LoC: Produktiv +0/−0, Test ca. +20/−1

## Implementation Details

### 1. Zentraler Cache-Reset (`tests/conftest.py`)

Neue autouse-Fixture, platziert neben den beiden bestehenden Reset-Fixturen
für andere geteilte Caches:

```
@pytest.fixture(autouse=True)
def _reset_shared_weather_cache():
    from services.weather_cache import reset_shared_weather_cache_for_tests
    reset_shared_weather_cache_for_tests()
    yield
    reset_shared_weather_cache_for_tests()
```

Wirkort-Begründung (aus dem Kontext-Dokument übernommen, nicht neu ermittelt):
`SegmentWeatherService.fetch_segment_weather` (`src/services/segment_weather.py:143`)
fragt zuerst den geteilten Wetter-Cache — ein Prozess-Singleton mit 600s-TTL
(`src/services/weather_cache.py:294`). Ohne Reset überlebt ein Cache-Eintrag
aus einem früheren Testfall (z. B. AC-1, das echte Fixture-Daten für das
geklemmte „heute"-Fenster ablegt) in den nächsten Testfall (AC-3, das
denselben Fensterschnitt trifft) hinein, sodass der dort installierte,
absichtlich scheiternde Provider-Double nie aufgerufen wird.

Der Wirkort ist bewusst `tests/conftest.py`, nicht die Testdatei selbst:
sieben bestehende Testdateien setzen den geteilten Wetter-Cache bereits
selbst zurück — in **zwei verschiedenen Bauarten**, was die Handarbeit
sichtbar macht:

- als eigene `@pytest.fixture(autouse=True)`, funktions-scoped:
  `tests/unit/test_alarm_zeitfenster_ziel.py:60-64`,
  `tests/unit/test_alert_data_freshness.py:107-111`,
  `tests/unit/test_forecast_cache_sharing.py:200-206`,
  `tests/unit/test_forecast_budget_gate.py:106-110`
- als direkter Aufruf an der jeweiligen Bedarfsstelle (keine Fixture):
  `tests/tdd/test_compare_alert_day_window.py:261` (in `_stelle_wetter`),
  `tests/unit/test_thunder_night_addendum_parity.py:209` (in `_run_both_paths`),
  `tests/unit/test_segment_weather_snowfall_limit.py:116/128/149/156/184`
  (fünf Aufrufe in derselben Datei)

Eine achte lokale Kopie behebt nur den achten Fall und lässt den neunten
offen. Die zweite Bauart zeigt zusätzlich, dass die Absicherung dort davon
abhängt, ob jemand an der richtigen Stelle daran denkt. Die zwei vorhandenen Vorbilder in `conftest.py`
(`_reset_shared_radar_cache:280`, `_reset_thunder_window_cache:295`, beide aus
#1329 C2) zeigen, dass der geteilte Wetter-Cache in dieser Reihe schlicht
fehlt.

### 2. Hermetik des Router-Testfalls

`test_router_returns_422_with_honest_no_weather_message` hängt aktuell an
`Settings()` aus der Prozessumgebung. Fehlen SMTP-Variablen, antwortet
`api/routers/scheduler.py:228` mit 422 „SMTP not configured", bevor der
eigentlich geprüfte No-Weather-Zweig (`:246`) erreicht wird — lokal nur
deshalb unauffällig, weil eine echte `.env` im Arbeitsordner liegt (Muster
#1477). Der Testfall setzt vor dem Request per `monkeypatch.setenv` Dummy-Werte
für `GZ_SMTP_HOST`, `GZ_SMTP_USER`, `GZ_SMTP_PASS`, damit die Route den
No-Weather-Zweig unabhängig von der Arbeitsumgebung erreicht.

### 3. Ratsche #1196

Zeile 88 (`tests/tdd/test_trip_report_test_send_past_stage_clamp.py`) aus
`.github/ci_tdd_excludes.txt` entfernen. Datei enthält aktuell 30
Einträge (gemessen), danach 29 — ausschließlich Entfernen, keine Ergänzung.

### 4. Kein neuer Wächter

Die Fehlerart ist ein Reihenfolgen-Effekt: ein isolierter Testlauf verdeckt
ihn. Sobald die Datei die Ausschlussliste verlässt, führt der CI-`test`-Job
sie im Verbund aus — genau die Bedingung, unter der der Fehler auftritt —
und `pytest-randomly` variiert zusätzlich die Reihenfolge zwischen Läufen.
Beide Mechanismen existieren bereits; ein zusätzliches Dauergate wäre reiner
Zuwachs ohne eigene Fangfläche (Regel-Budget #1196: kein Zuwachs ohne
Ersatz oder Prüfdatum).

## Expected Behavior

- **Input:** `uv run pytest tests/tdd/test_trip_report_test_send_past_stage_clamp.py --allow-hosts=127.0.0.1,::1 -p no:randomly -q` (ganze Datei, nicht nur die AC-3-Klasse)
- **Output:** Alle Testfälle der Datei grün, inklusive der beiden bisher roten AC-3-Fälle
- **Side effects:** Keine Änderung an Produktivcode, Persistenz oder Laufzeitverhalten; sieben bestehende lokale Reset-Fixturen werden redundant (nicht falsch, siehe Known Limitations)

## Acceptance Criteria

- **AC-1:** Given die vollständige Testdatei `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` wird am Stück ausgeführt (nicht nur die `TestAC3GenuineNoWeatherHonestOutcome`-Klasse isoliert), When der zentrale Wetter-Cache-Reset in `tests/conftest.py` aktiv ist, Then liefern beide Testfälle `test_service_outcome_is_no_weather_when_today_also_fails` und `test_router_returns_422_with_honest_no_weather_message` den erwarteten ehrlichen Outcome (`no_weather` bzw. HTTP 422) statt `sent`/HTTP 200.
  - Test: `uv run pytest tests/tdd/test_trip_report_test_send_past_stage_clamp.py --allow-hosts=127.0.0.1,::1 -p no:randomly -q` — vollständiger Dateilauf (das ist der Wirkort des Bugs, ein isolierter Klassenlauf beweist hier nichts), Exit 0.

- **AC-2:** Given derselbe vollständige Dateilauf mit aktivem zentralem Cache-Reset, When die Testfälle von `TestAC1PastStageClampedToToday` (`:159`) und `TestAC2RegularPathUnclamped` (`:194`) laufen, Then bleiben deren Zusicherungen aus #1325 unverändert grün — der Cache-Reset hebelt die Datums-Klemm-Zusicherung nicht aus.
  - Test: Derselbe Dateilauf wie AC-1; die AC-1/AC-2-Testfälle (Outcome `sent` bzw. `no_stage`, unverändert zu #1325) dürfen durch den Reset nicht rot werden — geprüft im selben `pytest`-Aufruf, keine separate Ausführung.

- **AC-3:** Given der zentrale Reset in `tests/conftest.py` wirkt autouse für alle Tests, When die acht Testdateien mit eigenem Bezug zum geteilten Wetter-Cache (`test_compare_alert_day_window.py`, `test_segment_weather_snowfall_limit.py`, `test_alarm_zeitfenster_ziel.py`, `test_alert_data_freshness.py`, `test_thunder_night_addendum_parity.py`, `test_forecast_cache_sharing.py`, `test_forecast_budget_gate.py`, `test_trip_report_test_send_past_stage_clamp.py`) sowie die Scheduler-/Trip-Suiten (`tests/tdd/test_issue_1012_no_data_guard.py`, `tests/tdd/test_issue_1113_partial_outage_guard.py`, `tests/tdd/test_issue_1007_heute_voll_briefing.py`, `tests/test_success_status_guard.py`) laufen, Then bleiben alle grün — der zentrale Reset richtet keinen Kollateralschaden an.
  - Test: Gemeinsamer benannter Lauf aller genannten Dateien, z. B. `uv run pytest tests/tdd/test_compare_alert_day_window.py tests/unit/test_segment_weather_snowfall_limit.py tests/unit/test_alarm_zeitfenster_ziel.py tests/unit/test_alert_data_freshness.py tests/unit/test_thunder_night_addendum_parity.py tests/unit/test_forecast_cache_sharing.py tests/unit/test_forecast_budget_gate.py tests/tdd/test_trip_report_test_send_past_stage_clamp.py tests/tdd/test_issue_1012_no_data_guard.py tests/tdd/test_issue_1113_partial_outage_guard.py tests/tdd/test_issue_1007_heute_voll_briefing.py tests/test_success_status_guard.py --allow-hosts=127.0.0.1,::1 -p no:randomly -q`, Exit 0. Diese Messung ist Pflicht vor Implementierung-Abschluss — sie ist nicht durch Lesen ableitbar. Fällt sie negativ aus, ist die enge Variante (Reset-Fixture nur lokal in `test_trip_report_test_send_past_stage_clamp.py`, Vorlage: Branch `ws/fix-1557-no-weather` @ `6c3c7ec9`) der dokumentierte Rückfallweg statt des zentralen Resets.

- **AC-4 (Härtung, kein Bugfix — Prämisse in der RED-Phase widerlegt):** Given `test_router_returns_422_with_honest_no_weather_message` läuft mit geleerten `GZ_SMTP_USER`/`GZ_SMTP_PASS`, When der Testfall ausgeführt wird, Then ist sein Ergebnis (HTTP 422 mit No-Weather-Meldung) identisch zum Lauf mit gesetzten Werten — der Testfall setzt die benötigten SMTP-Variablen selbst per `monkeypatch.setenv`, statt sich auf die Arbeitsumgebung zu verlassen.
  - Test: Derselbe Testfall zweimal — einmal regulär, einmal mit `GZ_SMTP_USER= GZ_SMTP_PASS=` — beide Läufe grün mit gleichem Ergebnis.
  - **Messbefund vor Implementierung (RED-Phase, 2026-08-14):** Die ursprünglich aus dem fremden Commit `6c3c7ec9` übernommene Begründung — der Testfall hänge an einer `.env` im Arbeitsordner und antworte sonst mit „SMTP not configured" (`api/routers/scheduler.py:228`) — **ließ sich nicht reproduzieren**. Eine In-Prozess-Sonde misst `can_send_email=False`, und der Testfall erreicht trotzdem den Wetter-Abruf und ist grün (Artefakt `docs/artifacts/fix-1557-no-weather-outcome/ac4-hermetik-nicht-falsifizierbar.txt`). **Ursache präzisiert nach Adversary-Finding F001:** Auslöser ist nicht „pytest" allgemein, sondern die **Test-Benutzerkennung**. `Settings.with_user_profile()` setzt `force_test = (env == "staging") or self._is_test_user(user_id)` und nimmt dann `for_testing()` als Basis (`src/app/config.py:370`); `is_test_user_id()` (`:56-68`) greift bei den Teilstrings `"test"` **oder `"tdd"`**, und die Kennung dieses Testfalls enthält `tdd`. Überschrieben werden `smtp_user`/`smtp_pass` damit aus `GZ_TEST_SMTP_*` — nicht aus den `GZ_SMTP_*`-Variablen, die der Testfall setzt. Ein Router-Aufruf mit normaler Kennung bekäme diese Umlenkung nicht. AC-4 ist deshalb **kein** Bugfix-Kriterium und hat **kein** RED-Artefakt: die `setenv`-Zeilen machen den Testfall unabhängig von der Umgebung (Determinismus, nützlich für fremde Runner), beheben aber keinen nachgewiesenen Defekt. Diese Herabstufung ist bewusst dokumentiert statt stillschweigend übernommen.

- **AC-5:** Given AC-1 bis AC-4 sind erfüllt (Datei läuft im Verbund grün), When `.github/ci_tdd_excludes.txt` geprüft wird, Then fehlt die Zeile `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` und die Gesamtzahl der Einträge ist von 30 auf 29 gesunken.
  - Test: `grep -c '^tests/tdd/' .github/ci_tdd_excludes.txt` liefert `29`; `grep -x 'tests/tdd/test_trip_report_test_send_past_stage_clamp.py' .github/ci_tdd_excludes.txt` liefert keinen Treffer (Exit 1).

- **AC-6:** Given die Änderung betrifft ausschließlich Python-Testinfrastruktur (`tests/conftest.py`, pytest) und kann den Frontend-Testlauf technisch nicht berühren, When der Liefer-PR gebaut wird, Then sind die drei Frontend-Prüfungen der CI-Ampel — `frontend-test` (Vitest/`node --test`), `svelte-check` und `e2e` (Playwright-Positivliste) — auf dem letzten Stand des PR **gemessen** grün, statt als unberührt vorausgesetzt zu werden (PO-Auflage zur Freigabe, 2026-08-14).
  - Test: `frontend-test` per `cd frontend && npm test` — **die Bewertung hängt an der Summary-Zeile `# fail 0`, NICHT am Exit-Code**: `node --test` liefert im Kindprozess auch bei roten Tests Exit 0, ein `$?`-Check allein wäre falsches Grün. Zusätzlich `npx svelte-check --tsconfig ./tsconfig.json` gegen die Baseline und die `e2e`-Lane über `.github/ci_e2e_specs.txt`. Maßgeblich ist der grüne Zustand aller drei GitHub-Actions-Checks am PR-Kopf; ein lokaler Lauf ersetzt ihn nicht, sondern geht ihm voraus.

## Known Limitations

- Die sieben bestehenden lokalen Reset-Fixturen (`test_compare_alert_day_window.py:261` u. a., siehe Implementation Details) werden **nicht** entfernt — sie werden durch den zentralen Reset redundant, nicht falsch. Ein Aufräumen ist eine eigene, breit streuende Änderung außerhalb dieser Scheibe.
- Nebenbefund `src/services/dispatch_orchestrator.py:85-88`: im regulären Scheduler-Lauf zählt nur `no_weather` als `failed`; `no_stage`, `no_channels` und `channels_unreachable` zählen als `sent`, der Lauf meldet `status: "ok"` (`api/routers/scheduler.py:55-57`) obwohl niemand etwas erhalten hat. Gleiche Fehlerklasse wie #1557 (unverdiente Erfolgsmeldung, #1405), aber eigener Auslöser und nutzersichtbar im Monitoring ⇒ eigenes Issue, nicht Teil dieser Spec.
- Nebenbefund `src/services/trip_command_processor.py:270-271`: der Default-Zweig lässt jeden unbekannten Outcome still auf den „Keine Etappe geplant"-Text fallen — ebenfalls nicht Teil dieser Scheibe.
- Kein neuer Rückfall-Wächter (siehe Implementation Details Punkt 4) — bewusster Verzicht, kein vergessenes Gate.

## Nicht in dieser Scheibe

- Kein Aufräumen der sieben bestehenden lokalen Reset-Fixturen (siehe Known Limitations).
- Kein neues Issue für `dispatch_orchestrator.py:85-88` oder `trip_command_processor.py:270` — nur benannt, nicht bearbeitet.
- Kein Produktivcode-Fix — es gibt keinen (Risiko geprüft und verneint, Kontext-Dokument).
- Kein neues CI-Gate/Dauer-Wächter für Reihenfolgen-Effekte (bewusste Entscheidung, s.o.).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Test-/CI-Fix ohne Wirkung auf Produktivverhalten,
  Datenmodell, Kanäle oder Provider — keine der in `docs/adr/README.md`
  genannten Entscheidungsflächen ist berührt.

## Test Plan

### Automated Tests (bereits vorhanden, werden durch diesen Fix grün statt neu geschrieben)

- [ ] `TestAC3GenuineNoWeatherHonestOutcome::test_service_outcome_is_no_weather_when_today_also_fails` — GIVEN ein Provider-Double, der auch für „heute" scheitert, WHEN der Test-Sendepfad im Dateiverbund läuft, THEN ist der Service-Outcome `no_weather`.
- [ ] `TestAC3GenuineNoWeatherHonestOutcome::test_router_returns_422_with_honest_no_weather_message` — GIVEN denselben Provider-Double und gesetzte Dummy-SMTP-Env, WHEN `POST /api/scheduler/trips/{id}/send` im Dateiverbund läuft, THEN antwortet die Route mit HTTP 422 und der No-Weather-Meldung.

### Nicht-Regression

- [ ] `TestAC1PastStageClampedToToday` und `TestAC2RegularPathUnclamped` derselben Datei bleiben im Verbund grün (AC-2 dieser Spec).
- [ ] Die acht Cache-Testdateien plus die vier Scheduler-/Trip-Suiten aus AC-3 bleiben im gemeinsamen Lauf grün.
- [ ] Die Frontend-Prüfungen `frontend-test`, `svelte-check` und `e2e` sind am PR-Kopf grün (AC-6) — Bewertung von `frontend-test` über die Summary-Zeile `# fail 0`, nicht über den Exit-Code.

## Changelog

- 2026-08-14: Initial spec created — Issue #1557, Workflow `fix-1557-no-weather-outcome`

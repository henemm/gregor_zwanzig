---
entity_id: fix_1339_nachtwetter_fallback
type: module
created: 2026-08-05
updated: 2026-08-05
status: implemented
version: "1.0"
tags: [bugfix, weather, night-block, gap-detection]
workflow: fix-1339-nachtwetter-fallback
---

# Fix #1339 — Zieldaten-Ausfall wird nicht mehr still durch Segment-Startwetter ersetzt

## Approval

- [ ] Approved

## Purpose

`fetch_night_weather()` liefert das Wetter fürs Nachtlager am Zielort. Schlägt der Abruf fehl
(Netz-/Kontingentfehler), gibt die Funktion heute fälschlich die Zeitreihe der letzten Etappe
zurück (Segment-Start-Geografie, nicht der Zielort) statt ehrlich `None`. Weil die
Lückenerkennung diese Ersatzdaten als „vollständig" ansieht, geben alle vier Versandkanäle eine
positive Entwarnung fürs Nachtlager ab, obwohl dort keine echten Zieldaten vorlagen. Dieser Fix
entfernt den falschen Fallback, sodass echte Abruf-Fehler ehrlich als Lücke sichtbar werden.

## Source

- **File:** `src/services/segment_weather.py`
- **Identifier:** `def fetch_night_weather` (Zeilen 395-455, konkret der `except`-Block
  443-455)

## Estimated Scope

- **LoC:** ~15-30 (Kernfix: ~4 Zeilen entfernen in `segment_weather.py`; plus neue fokussierte
  Testdatei)
- **Files:** 1 Produktivdatei (`src/services/segment_weather.py`) + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.trip_report_scheduler.TripReportSchedulerService._fetch_night_weather` | function | Versandpfad — reiner Delegator seit #1315, ruft `fetch_night_weather()` unverändert auf; profitiert automatisch vom Fix |
| `services.preview_service` (Zeile 217) | function call | Web-Vorschau — ruft dieselbe Funktion mit optionalem `provider` (Demo-Modus, `FixtureProvider`, #483); profitiert automatisch vom Fix |
| `services.notification_service.compute_has_gap` | function | Liest den Rückgabewert von `fetch_night_weather()` (über den Delegator) und leitet daraus `has_gap` ab — unverändert, reagiert bereits korrekt auf `None` |
| `output.renderers.day_window.build_day_window_points` | function | Liest `night_weather`; dokumentiert bereits „`night_weather=None` -> fail-soft" (Zeile 119) — unverändert |
| `output.renderers.trip_report.TripReportFormatter.format_email` | function | Rendert `has_gap` in alle vier Kanäle (SMS `TH:?`, Klartext-Mail, Kopf-Pille, Telegram-Fusszeile) — unverändert |

## Implementation Details

Der `except`-Block in `fetch_night_weather()` (`src/services/segment_weather.py:443-455`) wird von

```python
    except Exception as e:
        logger.warning(f"Failed to fetch night weather: {e}")
        # Fallback: use last segment's timeseries (evening hours only)
        if last_segment.timeseries and last_segment.timeseries.data:
            return last_segment.timeseries
        return None
```

zu

```python
    except Exception as e:
        logger.warning(f"Failed to fetch night weather: {e}")
        return None
```

geändert — die beiden Fallback-Zeilen (Kommentar + `if`-Block mit `return last_segment.timeseries`)
entfallen ersatzlos. Der Rückgabetyp bleibt exakt `Optional[NormalizedTimeseries]`; nur der
Inhalt des Fehlerfalls wird ehrlicher (immer `None` statt manchmal Ersatzdaten). Kein weiterer
Code wird geändert — `compute_has_gap()` und `build_day_window_points()` funktionieren bereits
korrekt für `None` (Fix #1331/#1334, „Erkennung == Anzeige per Konstruktion").

## Expected Behavior

- **Input:** `fetch_night_weather(last_segment, provider=None)`, wobei der interne
  `service.fetch_segment_weather(night_segment, ...)`-Aufruf eine `Exception` wirft (z. B.
  Netz-/Kontingentfehler beim Live-Provider).
- **Output:** `None` — unabhängig davon, ob `last_segment.timeseries` Daten enthält oder nicht.
- **Side effects:** Ein `logger.warning(...)`-Eintrag wie bisher; keine sonstigen Änderungen. Der
  Erfolgspfad (`try`-Block) und der Demo-Vertrag (`provider`-Parameter, #483) sind unberührt.

## Acceptance Criteria

- **AC-1 (Kernfix):** Given ein Provider, dessen `fetch_segment_weather()`-Aufruf für die
  Nacht-Zeitreihe eine Exception wirft / When `fetch_night_weather()` aufgerufen wird / Then
  liefert die Funktion `None`, NICHT die Zeitreihe der letzten Etappe.
  - Test: Provider-Double (kein Mock-Theater — simuliert reales Fehlerverhalten eines Providers,
    kein zurückgespiegeltes Sollverhalten), dessen `fetch_segment_weather()` bewusst wirft.
    Assertion prüft `result is None` UND explizit per Wert-Ungleichheit, dass NICHT
    `last_segment.timeseries` zurückkommt (z. B. `result != last_segment.timeseries` bzw.
    Vergleich der enthaltenen Datenpunkte, nicht nur Identitätsprüfung).

- **AC-2 (Wirkung an der Stelle, an der sie zählt):** Given der Fehlerfall aus AC-1 / When das
  Ergebnis (`None`) über `compute_has_gap()` an den vollen Renderpfad
  (`TripReportFormatter.format_email(..., has_gap=...)`) übergeben wird / Then zeigt mindestens
  ein Versandkanal (SMS-Text `TH:?` oder Klartext-Mail `?` statt „kein Gewitter") den
  Unsicherheitsmarker statt einer positiven Entwarnung.
  - Test: Aufbau analog zu `test_notification_service.py::test_gap_flows_through_format_email_into_all_four_channels`
    — `compute_has_gap(segments, None, tz)` liefert `True`, danach
    `TripReportFormatter().format_email(segments, ..., has_gap=has_gap)` aufrufen und in
    `report.sms_text` bzw. `report.email_plain` den Unsicherheitsmarker prüfen. Beweis am ECHTEN
    Renderpfad, nicht nur an `compute_has_gap()` isoliert — die Fehl-Entwarnung ist die
    sicherheitsrelevante Richtung, die an der Wirkstelle geprüft sein muss.

- **AC-3 (Beide Aufrufer, kein Divergenzrisiko):** Given derselbe Fehlerfall wie in AC-1 / When
  sowohl der Versandpfad (`TripReportSchedulerService._fetch_night_weather()`) als auch die
  Vorschau (Aufruf von `fetch_night_weather()` in `preview_service.py:217`) denselben Fehler
  erleben / Then liefern beide `None` — identisches Verhalten, da beide dieselbe geteilte
  Funktion aufrufen.
  - Test: Ein Test mit zwei Aufrufstellen (oder zwei kleine Tests im selben Modul) — einmal über
    `TripReportSchedulerService._fetch_night_weather(last_segment)` mit dem werfenden
    Provider-Double gepatcht, einmal über direkten Aufruf von `fetch_night_weather(last_segment,
    provider=<werfender Provider>)`, wie es `preview_service.py` täte. Beide Aufrufe müssen
    `None` liefern.

- **AC-4 (Mutations-Gegenprobe, PFLICHT):** Wird die entfernte Fallback-Zeile versuchsweise
  wieder eingebaut (`return last_segment.timeseries` im `except`-Block), MUSS mindestens ein Test
  aus AC-1 oder AC-2 rot werden. Verbindliche Vorgabe an den Adversary in Phase 6 — die
  Fehl-Entwarnung ist die sicherheitsrelevante Richtung, die geprüft sein muss.
  - Test: Kein separater automatisierter Test — wird vom `implementation-validator`-Agent in
    Phase 6 als Mutationsprobe manuell durchgeführt (String-Ersetzung mit externer
    Sicherungskopie, kein `git checkout/stash/reset`).

## Bestehende Tests, die unverändert grün bleiben müssen

- `tests/unit/test_notification_service.py::TestComputeHasGapRealSendPath::test_non_covering_night_weather_fallback_yields_gap`
- `tests/unit/test_notification_service.py::TestComputeHasGapRealSendPath::test_non_covering_night_weather_fallback_flows_into_all_four_channels`
- `tests/unit/test_day_window_gap_detection.py::test_night_weather_covering_only_pre_arrival_hours_is_a_gap`
- `tests/unit/test_preview_night_block.py` (Erfolgspfad, `_SpyProvider`)

Alle vier bauen eine synthetische `NormalizedTimeseries` per Hand bzw. testen nur den
Erfolgspfad — sie rufen `fetch_night_weather()` nicht im Fehlerfall auf und erwarten dabei nicht
den Fallback-Rückgabewert. Sie testen die generische Robustheit von `compute_has_gap()`
(Verteidigung in der Tiefe), nicht den entfernten Fallback selbst.

## Known Limitations

- Keine bekannten — der Mechanismus zur Lückenerkennung und -anzeige ist bereits vollständig
  vorhanden (Fix #1331/#1334); dieser Fix schließt nur die letzte unehrliche Datenquelle
  (`fetch_night_weather()`s Fehlerfall).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix, keine neue Architektur, keine Schnittstellenänderung — der
  Rückgabetyp `Optional[NormalizedTimeseries]` bleibt exakt gleich, nur der `None`-Zweig wird
  ehrlicher (kein Fallback auf falsche Ersatzdaten mehr).

## Test Plan

### Automated Tests (TDD RED)

Neue Testdatei nach Verhalten benannt (KEIN `test_issue_1339*`/`test_1339*`), z. B.
`tests/tdd/test_night_weather_fetch_failure_stays_honest.py`:

- [ ] AC-1: GIVEN ein werfender Provider-Double / WHEN `fetch_night_weather()` aufgerufen wird /
      THEN liefert die Funktion `None`, nicht `last_segment.timeseries`.
- [ ] AC-2: GIVEN der Fehlerfall aus AC-1 / WHEN das `None`-Ergebnis über `compute_has_gap()` in
      `TripReportFormatter.format_email()` einfließt / THEN zeigt SMS oder Klartext-Mail den
      Unsicherheitsmarker `?` statt „kein Gewitter"/positiver Entwarnung.
- [ ] AC-3: GIVEN derselbe Fehlerfall / WHEN sowohl der Scheduler-Delegator als auch der direkte
      Aufruf mit `provider=`-Parameter (Vorschau-Muster) denselben Fehler erleben / THEN liefern
      beide `None`.

## Acceptance Criteria (Zusammenfassung)

Siehe Sektion „Acceptance Criteria" oben — AC-1 bis AC-4, davon AC-1 bis AC-3 automatisiert
getestet, AC-4 als Pflicht-Mutationsprobe im Adversary-Schritt.

## Changelog

- 2026-08-05: Initial spec created

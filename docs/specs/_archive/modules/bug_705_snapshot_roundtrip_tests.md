# Spec: Round-Trip-Tests für weather_snapshot Deserialisierungspfad (Issue #705)

## Kontext

Commit `3e4e44ed` behebt `TypeError: can't compare offset-naive and offset-aware datetimes`
in `_deserialize_timeseries()` (weather_snapshot.py:199-200). Der Fix normalisiert naive
Zeitstempel aus dem JSON zu UTC-aware.

Die Tests AC-7 und AC-8 in `test_issue_704_telegram_interactive_navigation.py` erzeugen
`ForecastDataPoint`-Objekte mit `tzinfo=timezone.utc`. Dadurch enthält das gespeicherte JSON
Zeitstempel der Form `"2026-08-20T07:00:00+00:00"` — mit Timezone-Offset. Beim Laden erkennt
`datetime.fromisoformat()` diesen Offset → aware datetime → Fix-Zweig `if ts_dt.tzinfo is None`
wird **nie ausgeführt**.

**Folge:** Wird der Fix aus `weather_snapshot.py:199-200` entfernt, bleiben AC-7 und AC-8 grün.
Der Regressionsschutz fehlt.

## Scope

**Ausschließlich Tests** — kein Produktionscode wird verändert.

Betroffene Datei: `tests/tdd/test_issue_704_telegram_interactive_navigation.py`

## Acceptance Criteria

**AC-1:** Given die Test-Hilfsfunktion `_save_snapshot_with_hourly()` / When sie Snapshots
schreibt / Then müssen die `ForecastDataPoint.ts`-Werte **ohne** `tzinfo` (offset-naive)
instanziiert werden, sodass das gespeicherte JSON `"2026-08-20T07:00:00"` ohne `+00:00` enthält.

**AC-2:** Given ein Snapshot mit naiven Zeitstempeln im JSON / When AC-7
(`test_ac7_dd_hours_today_returns_compact_table`) den vollständigen Pipeline-Pfad durchläuft
(save → JSON → load → drilldown → Formatter) / Then muss der Test grün sein (kein TypeError,
`result.success == True`, Tabellen-Body vorhanden).

**AC-3:** Given ein Snapshot mit naiven Zeitstempeln im JSON / When AC-8
(`test_ac8_dd_hours_tomorrow_returns_table`) den vollständigen Pipeline-Pfad durchläuft / Then
muss der Test grün sein (kein TypeError, `result.success == True`, Temperatur-Spalte vorhanden).

**AC-4:** Given der Fix in `weather_snapshot.py:199-200` ist rückgängig gemacht (Zeilen entfernt) /
When AC-7 oder AC-8 ausgeführt werden / Then müssen sie mit `TypeError: can't compare
offset-naive and offset-aware datetimes` fehlschlagen (Regressionsschutz bestätigt).

**AC-5:** Given alle anderen Tests in `test_issue_704_telegram_interactive_navigation.py` /
When die Test-Suite vollständig ausgeführt wird / Then müssen alle bisherigen Tests (AC-1 bis
AC-10) weiterhin grün sein (keine Regressionen durch die Änderung).

## Technische Umsetzung

In `_segment()` (Zeile 98): `tzinfo=timezone.utc` entfernen →
`datetime(day.year, day.month, day.day, h, 0)` (naive).

Die `start_time`/`end_time` im `TripSegment` bleiben UTC-aware (sie gehen nicht durch
`_deserialize_timeseries()` und der `_reconstruct_segment()`-Pfad hat keinen UTC-Fix nötig).

## Test-Nachweis für AC-4 (RED vor Fix)

```bash
# Fix temporär entfernen
# Dann: uv run pytest tests/tdd/test_issue_704_telegram_interactive_navigation.py::test_ac7_dd_hours_today_returns_compact_table -v
# Erwartet: FAILED mit TypeError
```

## Changelog

- 2026-06-10: Initial spec (Issue #705)

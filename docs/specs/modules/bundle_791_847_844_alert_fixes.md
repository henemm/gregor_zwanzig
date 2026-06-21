---
entity_id: bundle_791_847_844_alert_fixes
type: bugfix
created: 2026-06-21
updated: 2026-06-21
status: draft
workflow: bug-844-active-segment-filter
---

# Alert-Bundle #791/#847/#844 — Lokalzeit, Ziel-Etappen-Label, Zeitfilter

## Approval

- [x] Approved

## Purpose

Drei zusammenhängende Defekte im Alert-Pfad werden in einem Bundle behoben: Radar-Alerts zeigen kein verifiziertes Lokalzeit-Verhalten (kein Test, Issue #791), Wetteränderungs-Alerts nennen beim Ziel-Segment keine Etappen-Nummer (#847), und Alerts feuern für Segmente die noch in der Zukunft liegen (#844).

## Source

- **File:** `src/services/trip_alert.py`, `src/output/renderers/email/alert_compact.py`, `src/output/renderers/email/helpers.py`
- **Identifier:** `_fetch_fresh_weather`, `render_deviation_alert`, `_line`, `build_segment_label`

## Estimated Scope

- **LoC:** ~120 (+) / ~5 (-)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py` | module | Alert-Logik: Radar + Abweichungs-Checks |
| `src/output/renderers/email/alert_compact.py` | module | Knapper Abweichungs-Alert-Renderer (#816) |
| `src/output/renderers/email/helpers.py` | module | `build_segment_label` — Segment-Label-Builder |
| `src/utils/timezone.py` | utility | `tz_for_coords`, `local_fmt` — Zeitzonenauflösung |
| `tests/tdd/test_bundle_791_847_844_alerts.py` | test | TDD-Nachweis für alle drei ACs |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/helpers.py` | MODIFY | `build_segment_label`: neuer optionaler Parameter `stage_label` für Ziel-Branch (#847) |
| `src/output/renderers/email/alert_compact.py` | MODIFY | `_line()` + `render_deviation_alert`: `stage_label` durchreichen bis `build_segment_label` (#847) |
| `src/services/trip_alert.py` | MODIFY | `_fetch_fresh_weather`: Zeitfilter — Segmente mit `start_time > now_utc` überspringen (#844) |
| `tests/tdd/test_bundle_791_847_844_alerts.py` | CREATE | TDD-Tests für #791, #847, #844 |

### Estimated Changes

- Files: 4
- LoC: +120 / -5

## Implementation Details

### #791 — Radar-Alert Lokalzeit (Regression-Test, kein Code-Fix)

Der Fix ist seit Issue #822 in `check_radar_alerts` vorhanden: `format_now_text(result, tz=tz, ...)` erhält `tz = tz_for_coords(lat, lon)`. Es fehlt ein Integration-Test der den vollständigen `check_radar_alerts`-Pfad mit `mail_sink` durchläuft und beweist, dass der Alert-Body die Onset-Zeit in der lokalen Zeitzone enthält — nicht in UTC.

Testaufbau: `tz = ZoneInfo("Europe/Paris")`, UTC-Offset +2h, Onset-Zeit UTC 10:00 → erwartet im Body `12:00`.

### #847 — Ziel-Segment ohne Etappen-Label

Aktueller Stand in `build_segment_label` (helpers.py Zeile 755):

```python
if str(s.segment.segment_id) == "Ziel":
    return f"🏁 Ziel ({start})"
```

Das `stage_label` (z. B. "Etappe 2") wird nicht einbezogen. Änderung:

1. Signatur: `build_segment_label(change, segments, *, tz, stage_label=None)`
2. Ziel-Branch: `f"🏁 Ziel, {stage_label} ({start})"` wenn `stage_label` gesetzt, sonst altes Format
3. `_line(change, segments, *, tz, stage_label=None)` — Parameter hinzufügen, an `build_segment_label` weitergeben
4. Aufruf in `render_deviation_alert` Loop: `_line(c, segments, tz=tz, stage_label=stage_label)`

IST: `Gewitterenergie (CAPE) 250.0 → 1270.0 (🏁 Ziel (15:02))`
SOLL: `Gewitterenergie (CAPE) 250.0 → 1270.0 (🏁 Ziel, Etappe 2 (15:02))`

### #844 — Zeitfilter: nur aktive Segmente fetchen

In `_fetch_fresh_weather` (trip_alert.py:720–734) war der erste Fix unvollständig: er übersprang nur zukünftige Segmente (`start_time > now_utc`), aber bereits absolvierte Segmente (`end_time < now_utc`) wurden weiterhin gefetcht und lösten Alerts aus.

Korrekter Fix: **ausschließlich das aktuell laufende Segment** fetchen.

```python
now_utc = datetime.now(timezone.utc)
today_utc = now_utc.date()
for cached in cached_weather:
    if cached.segment.end_time < now_utc:
        continue  # Bereits absolviert — überspringen
    if cached.segment.start_time.date() > today_utc:
        continue  # Beginnt erst morgen oder später — überspringen
    ...
```

Bedingung: `start_time <= now_utc <= end_time`. Alles davor oder danach wird übersprungen.

## Acceptance Criteria

- **AC-1:** Given ein Radar-Alert für einen Trip in der Zeitzone Europe/Paris (UTC+2) mit Regen-Onset um 10:00 UTC, / When der Nutzer die Alert-Benachrichtigung erhält, / Then zeigt der Alert-Text die Lokalzeit „12:" und nicht die UTC-Zeit „10:".

- **AC-2:** Given ein Wetteränderungs-Alert der eine Änderung am Ziel-Segment von Etappe 2 enthält, / When der Nutzer die Alert-E-Mail liest, / Then ist das Ziel-Segment als „Ziel, Etappe 2" ausgewiesen — nicht anonym als bloßes „Ziel".

- **AC-3:** Given ein Trip mit zwei Segmenten — Segment A begann vor 30 Minuten und endet in 60 Minuten (aktiv), Segment B beginnt erst morgen, / When der Alert-Service Wetteränderungen prüft, / Then wird Segment B nicht gefetcht — nur heutige Segmente (aktiv oder noch kommend heute) erscheinen im Ergebnis.

- **AC-3b:** Given ein Trip mit zwei Segmenten — Segment X lief von 10:00–11:00 Uhr (bereits absolviert, end_time < now) und Segment Y läuft aktuell von 11:00–13:00 Uhr (aktiv), / When der Alert-Service um 12:00 Uhr Wetteränderungen prüft, / Then wird Segment X nicht gefetcht — bereits absolvierte Segmente lösen keine Alerts mehr aus.

## Testing Notes

- AC-1: Kein Mock des Zeitzonenauflösers; reale `tz_for_coords`-Logik muss greifen. Beweis via `mail_sink` DI-Seam (kein SMTP).
- AC-2: Pure-Function-Test ohne API-Aufruf; synthetische `WeatherChange`-Liste mit `segment_id="Ziel"` ausreichend.
- AC-3 (`test_ac3_no_fetch_for_future_segments`): Direkt `_fetch_fresh_weather` mit aktivem + zukünftigem Segment aufrufen. Kein Mock; nur das aktive Segment darf gefetcht werden.
- AC-3b (`test_ac3b_no_fetch_for_past_segments`): Direkt `_fetch_fresh_weather` mit vergangenem + aktivem Segment aufrufen. Kein Mock; nur das aktive Segment darf im Ergebnis sein.

## Known Limitations

- AC-3/AC-3b testen `_fetch_fresh_weather` direkt, nicht den vollständigen Scheduler-Zyklus; Scheduler-E2E gegen Staging ist Post-Deploy-Verifikation vorgesehen.
- `build_segment_label` wird auch vom Radar-Alert-Pfad aufgerufen. Dort wird `stage_label` nicht übergeben — korrekt, Radar-Alerts haben kein Etappen-Kontext.

## Changelog

- 2026-06-21: Initial spec created
- 2026-06-21: AC-3b hinzugefügt — vergangene Segmente (end_time < now) ebenfalls überspringen (Issue #844 Re-Open)

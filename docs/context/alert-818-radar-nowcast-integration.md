# Context: Alert-Rework Slice 3 — Radar-Nowcast in den einen Wächter integrieren

Issue #818 · Epic #813 Slice 3/3

## Request Summary

Radar-Nowcast-Alerts werden in den gemeinsamen Alert-Wächter aus Slice 1 (#816) integriert: gleicher Mail-/Telegram-Pfad, gleicher alert_state-Speicher (Throttle-Zeiten raus aus separater Datei), und ein "nur kommende Strecke"-Filter damit abgeschlossene Segmente ignoriert werden. Statt eigener Radar-Schwellwerte wird der Nowcast gegen den Briefing-Snapshot verglichen ("Regen ab 14:30, im Briefing nicht angekündigt").

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/services/trip_alert.py` | Hauptdatei: `check_radar_alerts()`, `_radar_throttle_times`, `check_and_send_alerts()` |
| `src/services/alert_state.py` | Ziel-Speicher für Radar-Throttle (Slice 1); JSON-Schema `{metric:seg_id → {last_reported_value, reported_at}}` |
| `src/services/radar_service.py` | `NowcastResult` Dataclass; Felder: onset_minutes, intensity_label, source, frames, is_convective |
| `src/outputs/radar_alert.py` | Mail-Body-Builder für Radar-Alerts (Betreff, Body) |
| `src/services/trip_segments.py` | `TripSegment.end_time` (UTC) für den Zeitfilter |
| `src/services/trip_report_scheduler.py` | Briefing-Reset (`_reset_alert_state_after_briefing`), Snapshot-Schreiben (Zeile 665) |
| `src/providers/brightsky.py` | Nowcast-Provider; liefert NowcastResult |
| `tests/tdd/test_issue_816_alert_deviation.py` | Referenz-Tests Slice 1 (alert_state-Muster) |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Referenz-Tests Slice 2 (Radar + Segment) |

## Existing Patterns

- **alert_state-Schema (Slice 1):** `{"<metric>:<segment_id>": {"last_reported_value": float, "reported_at": ISO8601}}`. Radar-Throttle soll mit Key-Schema `"radar_throttle:<trip_id>"` integriert werden (kein Wert-Delta, nur Zeitstempel).
- **Segment-Zeitfilter:** `segment.end_time < now_utc` → überspringen (Muster existiert bereits in `_fetch_fresh_weather`).
- **Mail-Pfad Slice 1:** `render_deviation_alert` → knapper Body, kein Briefing-Inhalt. Radar soll denselben Versand-Pfad nutzen (nicht einen zweiten E-Mail-Client öffnen).
- **Briefing-Snapshot lesen:** `WeatherSnapshotService.load_dated(trip_id, target_date)` liefert Segment-Wetterdaten → `hourly`-Zeitreihe für Vergleich.

## NowcastResult-Felder

```python
@dataclass
class NowcastResult:
    onset_minutes: Optional[int]   # Minuten bis Regen ≥ 0,1 mm/h; None = kein Regen in 60 min
    intensity_label: str            # z.B. "Starker Hagel/Gewitter", "Leichter Regen"
    source: str                     # "radar" | "INCA" | "AROME-FR" | "minutely_15"
    frames: list
    is_convective: bool             # True bei WMO 95/96/99 (Gewitter/Hagel)
```

## Radar-Throttle heute vs. Ziel

| Heute | Ziel (#818) |
|-------|------------|
| Separate Datei `radar_alert_throttle.json` | alert_state-Key `"radar_throttle:<trip_id>"` |
| In-Memory-Dict `_radar_throttle_times` in TripAlertService | AlertStateService lädt/schreibt |
| `_load_radar_throttle()` / `_save_radar_throttle()` | AlertStateService.load/save |
| Cooldown-Prüfung in `_is_radar_throttled()` | Analog, gegen `reported_at` im alert_state |

## Vergleichslogik Nowcast vs. Briefing-Snapshot

Anforderung A: Nowcast-Onset wird **nicht** gegen absolute Radar-Schwellwerte geprüft, sondern gegen den Briefing-Stundenwert für das betroffene Zeitfenster:

1. Onset-Zeit berechnen: `now + timedelta(minutes=onset_minutes)` (lokale Segment-TZ)
2. Aus Briefing-Snapshot: `hourly[onset_hour].precip_mm` (oder thunder_level bei is_convective)
3. Wenn Briefing für diesen Stundenwert **keinen/kaum Niederschlag** vorhergesagt hat (< Bagatellschwelle, z.B. 0.5 mm) und Nowcast sagt Onset → Alert: "Regen ab HH:MM, im Briefing für HH:00 nicht angekündigt"
4. Wenn Briefing bereits Regen vorhergesagt hat → kein Radar-Alert (erwartet)

## Dependencies

- **Upstream:** `alert_state.py` (Slice 1, #816 ✅), `trip_segments.py` (Slice 2, #822 ✅), WeatherSnapshotService, NowcastResult
- **Downstream:** `trip_report_scheduler.py` ruft `check_radar_alerts()` auf; nach Briefing wird `alert_state` resettet (inkl. Radar-Throttle)

## Existing Specs

- `docs/specs/modules/` → alert-State-Spec: Slice-1-Spec prüfen
- Referenz-Tests in `tests/tdd/test_issue_816_alert_deviation.py` und `test_issue_822_radar_nowcast_segment.py`

## Analysis

### Type
Feature (Slice 3/3 von Epic #813)

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|-------|-------------|--------------|
| `src/services/trip_alert.py` | MODIFY | `check_radar_alerts()`: Briefing-Lookup einbauen, Throttle-Methoden auf AlertStateService umstellen |
| `src/services/alert_state.py` | MODIFY (optional) | Kein Schema-Change nötig — additiv kompatibel; evtl. Lazy-Migration |
| `tests/tdd/test_issue_818_radar_briefing_integration.py` | CREATE | Neue Tests: Briefing-Filter, Fallback, Throttle via alert_state |
| `tests/tdd/test_issue_827_radar_throttle_recording.py` | MODIFY | Throttle-Setup auf alert_state umstellen (falls B implementiert) |

### Scope Assessment
- Dateien: 2 produktiv + 2 Test
- Geschätzte LoC: +170–210 (A: ~40 produktiv + 100–140 Tests; B optional: ~30 weitere)
- Risiko: **Mittel** — Zeitstempel-Normierung (naive vs. UTC) ist kritischer Fallstrick

### Technical Approach

**Requirement A (Nowcast vs. Briefing):**
1. Hilfsfunktion `_briefing_precip_for_onset(snapshot, segment_id, onset_dt, tz) → Optional[float]`
2. Snapshot laden via `WeatherSnapshotService(user_id).load_dated(trip.id, today)`
3. `hourly[onset_hour].precip_1h_mm` matchen — **ACHTUNG: Snapshot-Timestamps sind naiv (kein tzinfo)** → UTC-Stunden-Normierung erforderlich
4. Alert unterdrücken wenn `precip_1h_mm >= 0.5` — sonst Alert senden
5. Fallback wenn Snapshot nicht da: Alert senden (bisheriges Verhalten erhalten)

**Requirement B (Radar-Throttle → alert_state):**
- Empfehlung: Vereinfachte Migration — neues Schreiben in `alert_state["radar_throttle"]["reported_at"]`, Lese-Fallback auf alte `radar_alert_throttle.json` für einen Release-Zyklus
- Key-Schema: `"radar_throttle"` ohne trip_id (trip_id ist schon Dateiname)
- Briefing-Reset (`_reset_alert_state_after_briefing`) löscht die gesamte Datei → Radar-Throttle wird automatisch mitgeresettet ✓

**Requirement C (Nur kommende Segmente):**
- Ist bereits implementiert in `check_radar_alerts()` Z. 616–631
- Kein neuer Code nötig — nur Nachweis-Test schreiben

### Open Questions
- [x] ~~Ist Segment-Filter bereits implementiert?~~ JA, Z. 616–631
- [x] ~~Wird check_radar_alerts im Scheduler aufgerufen?~~ JA, via Go-Cron `/api/scheduler/radar-alert-checks` (*/15 min)
- [ ] Bagatellschwelle für Briefing-Vergleich: 0.5 mm oder konfigurierbar?
- [ ] Doppel-Alert-Risiko (Forecast-Abweichung + Radar für gleichen Regen): In Scope für #818 oder separates Issue?

## Risiken & Considerations

1. **alert_state-Schema-Erweiterung:** Radar-Throttle-Key hat keinen `last_reported_value` (nur Zeitstempel) — Schema muss diesen Sonderfall dokumentieren oder ein dediziertes Feld bekommen.
2. **Briefing-Snapshot-Granularität:** Snapshot speichert Tagesaggregate und Stundenwerte. Der Vergleich benötigt stündliche Präzipitation (`hourly[h].precip_mm`); falls nur Tagesaggregate vorhanden → Fallback-Logik nötig.
3. **Doppel-Alert-Risiko:** Ohne Throttle könnten Forecast-Deviation-Alert UND Radar-Alert für denselben Regen gleichzeitig feuern. Gemeinsamer Pfad reduziert das, aber explizite De-Duplikation prüfen.
4. **Segment-Zeitfilter Granularität:** "Nur heutige Etappe" vs. "nur zukünftige Segmente" — Spezifikation muss klären ob mehrtägige Touren mehrere Stage-Segmente liefern oder nur den heutigen.
5. **Migration bestehender `radar_alert_throttle.json`-Dateien:** Bei Umstellung auf alert_state müssen vorhandene Throttle-Zeiten (für `data/users/*/`) migriert oder bei erstem Zugriff als "abgelaufen" behandelt werden.

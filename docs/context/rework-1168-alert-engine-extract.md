# Context: rework-1168-alert-engine-extract (Scheibe 1 von Epic #1095)

## Request Summary
Den Deviation-Alert-Auswertungskern aus `src/services/trip_alert.py` in einen
**location-generischen Shared-Service** herauslösen, sodass Trip **und** (später)
Orts-Vergleich ihn nutzen — ohne Duplikation. Reiner Umbau: Trip-Alarm-Verhalten bleibt
bit-identisch. GitHub: #1168. Übergeordnete Architektur-Analyse:
`docs/context/feat-1095-compare-alerts.md` (Abschnitt „Architektur-Gegenüberstellung").

## Scope (nur Scheibe 1)
- **IN:** Engine location-generisch extrahieren; geteilte Wetter-Beschaffungs-Schnittstelle
  einziehen; ADR schreiben.
- **OUT:** Compare-Anbindung/Snapshot (#1169), Config-UI (#1170). Kein Compare-Code.

## Extraktions-Ziele (bereits trip-unabhängig — Belege aus Epic-Analyse)
| Baustein | Quelle | Kopplung |
|---|---|---|
| Change-Detection | `trip_alert.py:546` `_detect_all_changes` | generisch (matcht `segment_id`) |
| Filter significant | `trip_alert.py:580` `_filter_significant_changes` | pure |
| Filter vs. State | `trip_alert.py:229` `_filter_against_alert_state` | staticmethod, Key `metric:segment_id` |
| Severity | `trip_alert.py:597` `_highest_severity` | pure staticmethod |
| Quiet-Hours | `trip_alert.py:423` `_is_quiet_hours` | nur 2 Config-Felder |
| Cooldown | `trip_alert.py:448` `_is_throttled_with_cooldown` | Config + id-Namespace |
| Detektor-Wahl | `trip_alert.py:251` `_select_change_detector` | nur `display_config` |
| Kanalwahl | `trip_alert.py:1071` `_effective_alert_channels` | nur `alert_rules`+`report_config` |
| State/Dedup | `src/services/alert_state.py:34-61` | `trip_id` = reiner Datei-Namespace → Entity-ID-abstrahieren |

## Geteilte Wetter-Beschaffung (der eigentliche Neu-Aufwand)
Zwei Wrapper über DERSELBEN Provider-Ebene, müssen unter eine location-generische
Schnittstelle:
- Trip: `SegmentWeatherService` / `TripSegment` (`trip_alert.py:909-931`)
- Compare: `ForecastService` / `Location` (`comparison_engine.py:322-331`)
- Gemeinsame Basis: `providers.base.get_provider("openmeteo")`

## Bereits geteilt (NICHT anfassen)
- Rendering: ADR-0011 — ein Renderer, 4 Kanäle (`src/output/renderers/alert/`)
- Versand: ADR-0017 — `NotificationService` einziger Orchestrierer
  (`trip_alert.py:965` delegiert an `send_deviation_alert`)

## Invariante (HART)
Trip-Alarme verhalten sich nach dem Umbau **identisch**. Trip bleibt erster Consumer der
extrahierten Engine.

## Dependencies
- Upstream: Provider-Ebene, `alert_state`, `NotificationService`, Change-Detektoren
  (`weather_change_detection.py`, `alert_preset.py`).
- Downstream: heutiger Scheduler-Job `/api/scheduler/alert-checks` → `check_all_trips()`
  (`api/routers/scheduler.py:50-57`); nach Scheibe 2 zusätzlich Compare.

## Existing Specs / ADRs
- ADR-0009 (Alerts als Abweichungs-Wächter — Bezugsanker), ADR-0011 (Render-Ort),
  ADR-0016 (Official-Alerts location-generisch), ADR-0017 (Output-Konsolidierung).
- Neu zu schreiben: ADR „Gemeinsames Deviation-Alert-Gehirn für Trip + Compare".

## Risks & Considerations
1. **Regressions-Risiko am Live-Alarm-Pfad** — bit-identisches Trip-Verhalten ist AC-Pflicht.
   Test: echter Trip-Alarm-Durchlauf (KEINE Mocks), Vorher/Nachher identisch.
2. **Keine Mocks** (CLAUDE.md): Alert-Tests gegen echte Wetter-/Versand-Pfade.
3. **ADR-Pflicht** (`adr_guard`): Architektur-Entscheidung dokumentieren, sonst Commit-Block.
4. **LoC-Limit 250** — Extraktion kann groß werden; ggf. `loc_limit_override` (erst nach
   Rücksprache, Memory-Regel: kein Override ohne Permission).
5. Reine Backend/Python-Scheibe — kein Mail-Renderer-Gate, keine UI-Gates erwartet.

## Analysis (Scheibe 1)

### Type
Rework/Refactor (kein neues Verhalten). Verhaltens-Invarianz ist das zentrale AC.

### Technischer Ansatz (Empfehlung)
Neuen location-generischen Service einführen (z.B. `DeviationAlertEngine` in
`src/services/`), der auf `List[SegmentWeatherData]` (bzw. eine generische
Punkt-Wetter-Struktur) + einem Config-/Snapshot-Objekt operiert. `TripAlertService` wird
zum dünnen Adapter: baut die Trip-Segmente/Config, ruft die Engine, delegiert Versand.
`alert_state` bekommt einen generischen Namespace (Entity-ID statt `trip_id`), abwärts-
kompatibel für bestehende Trip-State-Dateien. Wetter-Beschaffung hinter ein schmales
Interface, das Trip- und (später) Location-Quelle bedienen kann.

### Scope-Schätzung
Mittel–groß; primär Verschiebe-/Adapter-Arbeit. Voraussichtlich >250 LoC → Override-Frage
an PO stellen, bevor implementiert wird.

### Open Questions
- [ ] Namens-/Modul-Schnitt der neuen Engine (Bestätigung in Spec-Phase).
- [ ] Rückwärtskompatibilität bestehender `alert_state/<trip_id>.json`-Dateien —
      Migrationsfreiheit (Namespace bleibt `trip_id` für Trips).

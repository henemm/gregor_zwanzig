# Context: Issue #822 — Radar-Regen-Nowcast segmentbewusst machen

## Request Summary
Der Radar-/Regen-Nowcast-Alert prüft heute nur `stage.waypoints[0]` (Einzelpunkt), nennt
keinen Ort und feuert bei vielen Touren nicht. Er soll dieselbe GPX-/Waypoint-Segment-Ableitung
nutzen wie das Briefing, den Ort als „Etappe N, km X–Y" benennen (via `build_segment_label`),
die Tour-Zeitzone verwenden und den Cooldown dynamisch ausweisen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py` (`check_radar_alerts` ~Z. 545-637) | **Hauptziel**: nutzt heute `wp=stage.waypoints[0]; svc.get_nowcast(wp.lat,wp.lon)` — auf Segmente umstellen |
| `src/services/trip_report_scheduler.py` (`_convert_trip_to_segments` Z. 668-852) | **Wiederverwendung**: erzeugt `List[TripSegment]` mit `distance_from_start_km`, Koords, Zeiten, segment_id (1..N/"Ziel") aus Stage-Waypoint-Paaren (Haversine) — dieselbe Quelle wie Briefing |
| `src/output/renderers/email/helpers.py` (`build_segment_label` Z. 737-769) | erzeugt „Etappe N, km X–Y, HH:MM–HH:MM" aus segment_id+km+Zeiten+tz; Fallback „Segment N (HH:MM–HH:MM)" |
| `src/output/renderers/email/alert_compact.py` (`render_deviation_alert`) | Vorbild: wie der Abweichungs-Alert Segmente an `build_segment_label` + `tz` reicht |
| `src/services/radar_service.py` (`RadarNowcastService.get_nowcast`, `format_now_text`, `NowcastResult`) | Nowcast pro Koordinate; `NowcastResult(onset_minutes,intensity_label,source,is_convective)` — KEIN Ort-Feld, KEIN Caching |
| `src/utils/timezone.py` (`tz_for_coords(lat,lon)`) | Tour-TZ aus Koordinaten (Briefing: `tz_for_coords(segments[0].start_point...)`) |
| `src/app/models.py` (`TripSegment` Z. 315-329, `GPXPoint` Z. 268-274) | Segment-/Punkt-Felder inkl. `distance_from_start_km` |
| `src/app/trip.py` (`Trip.alert_cooldown_minutes` ~Z. 197) | Per-Trip-Cooldown; Default `throttle_hours=2` |

## Existing Patterns
- **Segment-Ableitung (SSoT):** `_convert_trip_to_segments(trip, date)` → `List[TripSegment]`. Briefing-Kette: `generate_briefing` → `_convert_trip_to_segments` → `fetch_segment_weather` → Formatter.
- **Ort-Label:** `build_segment_label(change_like, segments, tz=...)` — braucht `segment_id` (str), Segmente mit km+Zeiten, tz. Der Abweichungs-Alert (#816) nutzt genau das.
- **Tour-TZ:** überall ad-hoc via `tz_for_coords(lat, lon)` (kein `Trip.tz`-Feld).
- **Cooldown effektiv:** `trip.alert_cooldown_minutes if not None else throttle_hours*60` (Default 120 min). `get_time_until_next_alert(trip.id)` liefert Restzeit.

## Dependencies
- **Upstream:** `_convert_trip_to_segments` (Scheduler-Service — privat!), `RadarNowcastService.get_nowcast`, `build_segment_label`, `tz_for_coords`, `radar_alert_due(result, threshold_min=20)`.
- **Downstream:** `check_radar_alerts` wird vom Go-Cron `radar_alert_checks` (*/15) via `/api/scheduler/radar-alert-checks` aufgerufen (#773). Throttle/alert_log-Recording-Semantik (#773 F001) muss erhalten bleiben.

## Architektur-Frage (Wiederverwendung)
`_convert_trip_to_segments` ist eine **private** Methode von `TripReportSchedulerService`, `check_radar_alerts` lebt in `TripAlertService`. Sauberster Seam: die Segment-Ableitung in einen **gemeinsamen Helfer** (Modul-Funktion) extrahieren, den beide nutzen — statt private Methode quer aufzurufen. Refactor berührt den Briefing-Kernpfad → Roundtrip-Test (Briefing-Segmente vorher==nachher).

## Existing Specs
- `docs/specs/modules/issue_816_alert_deviation_core.md` (Abweichungs-Alert; nutzt build_segment_label)
- `docs/specs/modules/issue_773_radar_alert_wiring.md` (Radar-Alert-Verdrahtung)

## Offene Produkt-Frage (für Analyse/Spec)
**Welches Segment prüfen?** Der Alert meldet imminenten Regen (onset ≤ 20 min) — relevant ist, wo der Wanderer *jetzt* ist.
- (A, empfohlen) **Aktuelles/nächstes Segment** per Tageszeit (Segment dessen [start_time,end_time] „jetzt" enthält; sonst nächstes) → 1 Nowcast-Call (wie heute), maximal relevant.
- (B) **Alle Tagessegmente** prüfen → ~N Calls, könnte mehrere/kombinierte Alerts geben; Rate-Limit/Kosten beachten.

## Risks & Considerations
- **Refactor am Briefing-Kernpfad** (`_convert_trip_to_segments` extrahieren) — Briefing darf nicht brechen (Roundtrip-Test).
- **Stages ohne Waypoints**: liefern weiter leere Segmente → kein Alert (konsistent mit Briefing, ehrlich). Kein Regress, aber dokumentieren.
- **Kosten**: get_nowcast pro Segment; bei Variante B Rate-Limits (Open-Meteo/BrightSky). Variante A hält 1 Call.
- **Throttle/Recording-Semantik (#773 F001)**: Alert-Log + Throttle IMMER bei gefallenem Alert + Kanal — beibehalten.
- **Mandantentrennung**: `load_all_trips(user_id=self._user_id)` bleibt.
- **TZ**: `format_now_text` nutzt Server-`.astimezone()` → auf Tour-TZ umstellen (Onset-Zeit korrekt).
- **NowcastResult hat kein Ort-Feld**: Ort kommt aus dem Segment-Kontext im Aufrufer, nicht aus dem Result.

# Context: Issue #816 — Alert-Rework Slice 1 (Forecast-Abweichungs-Kern)

## Request Summary
Der Metrik-Alert (`check_and_send_alerts`, Forecast-Pfad) soll künftig **Abweichungen
gegenüber dem letzten verschickten Briefing** melden statt absoluter Schwellwerte.
Drei Bausteine: (A) Briefing-Snapshot als stabile, read-only Referenz, (B) Melde-Gedächtnis
`alert_state` gegen Wiederholungs-Spam, (C) symmetrische Δ-Erkennung, (D) knappe
Vorher→Jetzt-Benachrichtigung mit Segment (Zeit + km). Teil von Epic #813, PO-Entscheidung (a):
Abweichung **ersetzt** absolute Schwellen.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/services/trip_alert.py` | **Kern.** `check_and_send_alerts` (Z. 80–179). Snapshot-Overwrite Z. 160–168 muss raus (A). Throttle/QuietHours bleiben. Detektor-Auswahl `_select_change_detector` (Z. 181). |
| `src/services/weather_change_detection.py` | Δ-Erkennung. `detect_changes` ist bereits symmetrisch (`abs(delta) > threshold`, Z. 280). `_detect_absolute_changes` (above/below, Z. 307) **entfällt im Alert-Pfad** (C). |
| `src/services/weather_snapshot.py` | Referenz-Store. `load(trip_id)` liest das beim Briefing gespeicherte `{trip_id}.json`. Bleibt Lese-Quelle. |
| `src/services/trip_report_scheduler.py` | Z. 628–633: Briefing-Versand speichert Snapshot (`save`/`save_dated`). Hier muss der `alert_state`-**Reset** beim Briefing-Versand andocken (B). |
| `src/app/models.py` | `WeatherChange` (Z. 405) trägt `old_value/new_value/delta/threshold/severity/direction/segment_id`. `TripSegment.start_point.distance_from_start_km` (#801) für km-Angabe. |
| `src/output/renderers/email/__init__.py` | `render_email(report_type="alert", changes=...)` rendert heute die **volle** Briefing-Mail + Änderungsblock. Slice 1 braucht knappen Alert-Render-Pfad (D). |
| `src/output/renderers/email/helpers.py` | `format_change_line` (Z. 707) + `build_segment_label` (Z. 729) — vorhandene SSoT für Vorher→Jetzt-Zeile. Label hat **keine km** → erweitern. |
| `src/output/renderers/email/plain.py` | Z. 190–195: `━━ Wetteränderungen ━━`-Block (nutzt die Helper). |
| `src/app/metric_catalog.py` | `get_change_detection_map()` — Δ-Default-Quelle für Slice 1 (Temp 5.0, Wind/Böen 20.0, Regen 10.0, …). |

## Existing Patterns
- **Pro-Trip-Persistenz unter `data/users/<user_id>/<x>.json`** (throttle, radar_throttle, alert_log) — Muster für neuen `alert_state`-Store.
- **Mandantentrennung:** `TripAlertService(user_id=...)`, alle Pfade `data/users/{user_id}/`. PFLICHT auch für `alert_state`.
- **Best-effort-Versand** (#656): `_send_alert` liefert `deliverable_any` sobald ein Kanal erreichbar; Throttle/Log nur dann.
- **Δ-Erkennung symmetrisch** existiert bereits im delta-Pfad — die Asymmetrie kommt nur aus `_detect_absolute_changes`.

## Dependencies
- **Upstream:** `WeatherSnapshotService.load`, `WeatherChangeDetectionService`, `MetricCatalog.get_change_detection_map`, `render_email`/`format_change_line`, `EmailOutput`/`TelegramOutput`.
- **Downstream:** Scheduler-Cron (`check_all_trips`, 30 Min); Briefing-Versand (Reset-Hook); Cockpit-Alert-Log.

## Existing Specs
- `docs/specs/modules/trip_alert.md` (v2.0)
- `docs/specs/modules/weather_change_detection.md` (v2.0)
- `docs/specs/modules/weather_snapshot.md` (v1.0)

## Risks & Considerations
- **Spam-Risiko durch stabile Referenz:** Genau deshalb `alert_state` (B). Ohne Melde-Gedächtnis würde jeder 30-Min-Lauf dieselbe Abweichung erneut melden, weil der Snapshot nicht mehr mitwandert. **A und B müssen zusammen ausgeliefert werden.**
- **Δ-Stufe für Re-Alert** = der jeweilige Threshold (z.B. Regen 10 mm → Re-Alert erst bei weiteren ≥10 mm gegen den zuletzt gemeldeten Wert).
- **Teil-Rücknahme #809/#701:** Im Alert-Pfad wird die absolute Regel-Auswertung deaktiviert (Δ statt Absolut). Das #809-Self-Heal-Gerüst (alert_rules-Ableitung) bleibt unberührt; der Tab-Rework auf Δ-Schwellen ist Slice 2.
- **Δ-Startwerte des Issues** (Böen 25, Regen 8, Schneefallgrenze 300) weichen von MetricCatalog-Defaults ab → Slice-1-Quelle bleibt MetricCatalog (Scope-Grenze), Feinjustage = Slice 2 (Tab).
- **Daten-Schema-Backup:** Neuer Store unter `data/users/` — Backup-Hook + Mandantentest mit zwei Nutzern.
- **Scope-Disziplin:** NUR Forecast-Pfad. `check_radar_alerts` (Nowcast) bleibt unangetastet (Slice 3).
- **Mail-E2E:** Knappe Alert-Mail braucht eigenen Validator-Pfad — `briefing_mail_validator.py` ist auf `trip-briefing` getaggt; Alert-Mail = anderer Typ (Header `X-GZ-Mail-Type` prüfen).

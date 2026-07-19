# Context: issue-1316-alert-time-filter

**Issue:** [#1316](https://github.com/henemm/gregor_zwanzig/issues/1316) — Briefing zeigt abgelaufene amtliche Warnungen — Warnungs-Pfad hat keinerlei Zeitfilter

## Analysis

### Type
Bug (User-Report mit Screenshot, Abend-Briefing 18.07.2026 18:00 MESZ, Trip KHW 403 Etappe 9)

### Symptom
Warnblock listet Gewitterwarnungen `Sa 18.07. 00:00–01:00` und `01:00–02:00` — zum Versandzeitpunkt (18:00) seit >16 h abgelaufen. Das Abend-Briefing gilt für die Etappe von **morgen**, zeigt aber Warnungen von heute Nacht.

### Root Cause (verifiziert)
Es existiert **kein Zeitfilter** im gesamten Warnungs-Pfad:
- `get_official_alerts_for_location(lat, lon)` (`src/services/official_alerts/base.py:45-120`): nur Quell-/Hazard-Dedup, kein `valid_to >= now`.
- MeteoAlarm fragt bewusst 23 h rückwärts ab (Sendezeit-Fenster, `meteoalarm.py:213-220`), filtert danach nicht; GeoSphere (`geosphere_warn.py:107-135`) reicht alles durch.
- `target_date` (evening → morgen, `trip_report_scheduler.py:525-539`) wird beim Abruf (`:765`) nie mit `valid_from/valid_to` geschnitten.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/base.py` | MODIFY | Pure Filterfunktion `filter_alerts_to_window` + Fenster-Parameter an `get_official_alerts_for_location`, Anwendung VOR Dedup-Pass 1 |
| `src/services/official_alerts/__init__.py` | MODIFY | Export der Filterfunktion |
| `src/services/trip_report_scheduler.py` | MODIFY | Zeile ~765: Etappenfenster `segments[0].start_time`/`segments[-1].end_time` übergeben |
| `tests/tdd/test_official_alert_dedup_timespan.py` u. a. | MODIFY | Fixtures mit fixen Kalenderdaten (2026-07-13/14, bereits Vergangenheit) auf injiziertes `now` umstellen |
| Neuer Kern-Test | CREATE | Verhaltens-Test Zeitfenster-Filter (Name nach Verhalten, nicht Issue-Nr.) |

### Scope Assessment
- Files: 4–6
- Estimated LoC: +80/-20 (inkl. Tests)
- Risk Level: MEDIUM (geteilte Funktion, 4 Konsumenten: Briefing, Compare, Compare-Alarm, Alert-Pfad)

### Technical Approach (PO-Entscheid 2026-07-18: „zusätzlich auf morgen zuschneiden")
1. Pure Funktion `filter_alerts_to_window(alerts, window_start, window_end)` in `base.py`, Überlappungssemantik; Alerts ohne Zeitangaben bleiben (fail-safe).
2. Anwendung **vor Dedup-Pass 1** — sonst kann eine abgelaufene starke Warnung eine gültige schwächere derselben Gefahr verdrängen (Pass 2 verwirft die gültige → Ergebnis leer).
3. Signatur `get_official_alerts_for_location(lat, lon, window_start=None, window_end=None)`, effektives Fenster `[max(now, window_start), window_end or ∞)` — Klemme auf `now` als Invariante, `now` für Tests injizierbar.
4. Briefing übergibt Etappenfenster aus `TripSegment.start_time/end_time` (`trip_segments.py`, SSoT #822 — Wiederverwendung, kein Neubau).
5. Übrige 3 Aufrufstellen (`comparison_engine.py:224`, `compare_official_alert.py:162`, `trip_alert.py:942`) unverändert — Default `[now, ∞)` behebt dort denselben Fehler gratis.
6. MeteoAlarm-Query-Fenster NICHT anfassen (filtert Sendezeit, nicht Gültigkeit; ≥24 h = API-Fehler).

### Verworfene Alternativen
- Filter je Quelle: Duplikation + bei MeteoAlarm semantisch unmöglich (Query-Param = Sendezeit).
- Filter beim Konsumenten (nach Fetch): Dedup-Interaktionsfehler (s. o.) + für künftige Konsumenten vergessbar.

### Dependencies
- `trip_segments.py` (Etappenfenster, unverändert nutzen)
- Renderer-Mail-Gate #811: Mail-Inhalt ändert sich → `briefing_mail_validator.py` + `test_issue_811_mode_matrix.py` Pflicht vor Commit.

### Known Limitations (in Spec aufnehmen)
- Test-/On-Demand-Briefing auf komplett vergangene Etappe: Fenster vor `now` → Warnblock leer.
- Bereits gemeldete abgelaufene Einträge bleiben im Alert-State (harmlos, Key enthält Zeitraum).
- MeteoAlarm-Sendezeit-Limitation (>23 h alte Publikationen fehlen) bleibt unverändert.

### Open Questions
Keine — Fix-Umfang vom PO entschieden (2026-07-18, AskUserQuestion: „Zusätzlich auf morgen zuschneiden").

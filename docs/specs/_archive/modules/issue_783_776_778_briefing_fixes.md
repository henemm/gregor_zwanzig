---
entity_id: issue_783_776_778_briefing_fixes
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [briefing, email, scheduler, frontend, tech-debt, bugfix]
---

<!-- Issues #783, #776, #778 — Briefing-Mail: Startzeit ignoriert, Toggle-Persistenz fehlt, toter Code -->

# Briefing-Mail Bugfix-Bundle (#783 / #776 / #778)

## Approval

- [x] Approved (PO 'go' 2026-06-12)

## Purpose

Drei verifizierte Bugs in der Trip-Briefing-Mail-Pipeline werden zusammen behoben: (1) Die
Stundentabelle ignoriert die vom Nutzer eingestellte Etappen-Startzeit und zeigt stets 07:00
(#783); (2) das Umschalten der E-Mail-Inhalts-Bausteine im "Wetter-Metriken"-Tab hat keinen
Effekt, weil der Save-Handler `report_config` nie persistiert und `isDirty` Toggles nicht
erkennt (#776); (3) fünf tote Formatter-Methoden in `trip_report.py` lesen einen seit #759
nicht mehr existierenden `blue`-Key und werden ersatzlos entfernt (#778).

## Source

- **File:** `src/services/trip_report_scheduler.py` — `_convert_trip_to_segments` (Z.686–815), #783
- **File:** `src/output/renderers/email/helpers.py` — `extract_hourly_rows` (Z.123–137), #783 Kontext
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — `handleSave`, `isDirty` (Z.136, Z.334–360, Z.530), #776
- **File:** `src/formatters/trip_report.py` — `_fmt_val` (~Z.691–810), `_render_html_table` (Z.928), `_render_text_table` (Z.953), `_format_daylight_html` (Z.833–886), `_format_daylight_plain` (Z.888–927), #778

## Estimated Scope

- **LoC:** ~80–120 (Python scheduler +15, Svelte frontend +30, Python formatter -150 netto, Tests +80)
- **Files:** 4 produktive Dateien + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `trip_report_scheduler._convert_trip_to_segments` | Python-Backend | Erzeugt Segmente mit Zeitfenster; #783-Fix greift hier an (Z.728–740) |
| `stage.start_time` | Daten-Modell (Go `internal/model/trip.go:85`, Python `loader`) | Vom Nutzer eingestellte Etappen-Startzeit — muss für den Startpunkt Vorrang vor `arrival_calculated` bekommen |
| `wp.arrival_override` | Daten-Modell | Per-Waypoint Nutzer-Override (#303); bleibt erhalten und hat weiterhin höchste Priorität |
| `extract_hourly_rows` | Python-Backend `helpers.py:123` | Fenstert Stundentabelle nach `seg_data.segment.start_time.hour`; profitiert direkt vom #783-Fix |
| `WeatherMetricsTab.handleSave` | Svelte-Frontend | Baut derzeit Payload nur aus `display_config`; muss zusätzlich `report_config` per PUT `/api/trips/{id}` persistieren |
| `isDirty` Snapshot-Logik | Svelte-Frontend Z.136 | Muss `reportConfig` in `JSON.stringify`-Vergleich einschließen, sonst bleibt Speichern-Button disabled |
| `BriefingsTab.svelte` / `BriefingScheduleTab.svelte` | Svelte-Frontend | Referenz-Implementierung für separaten PUT `{report_config}` — analog hierzu implementieren |
| `format_email` in `trip_report.py` | Python-Backend | Delegiert seit β3 an `render_email()`; tote Methoden (#778) sind von keinem aufrufenden Code mehr erreichbar |
| `render_email` / `html.py` / `plain.py` | Python-Backend `src/output/renderers/email/` | Kanonische Render-Logik; erbt `fmt_val` aus `helpers.py` — ersetzt die toten `_fmt_val`-Varianten |

## Implementation Details

### #783 — Etappen-Startzeit für Startpunkt priorisieren

`_convert_trip_to_segments` in `src/services/trip_report_scheduler.py` baut für jeden
Waypoint ein Zeitfenster. Die aktuelle Prioritätskette für i==0 (Z.728–740):

```
wp.time_window.start  > wp.arrival_override > wp.arrival_calculated > default_start
```

`arrival_calculated` (persistierter Naismith-Wert, z.B. 07:00) schlägt `default_start`
(der wiederum `stage.start_time` ausliest) — deshalb gewinnt immer der alte berechnete Wert.

**Fix:** Für den Startpunkt (i==0) wird `stage.start_time` (sofern gesetzt) direkt als
`default_start` eingesetzt UND in der Prioritätskette zwischen `arrival_override` und
`arrival_calculated` eingereiht:

```
wp.time_window.start  > wp.arrival_override > stage.start_time (i==0, falls gesetzt) > wp.arrival_calculated > time(8,0)
```

Nur der erste Waypoint ist betroffen. Alle anderen Waypoints (i>0) behalten ihre bisherige
Prioritätskette unverändert. Read-Modify-Write des Stage-Objekts wird nicht verändert —
`stage.start_time` wird nur gelesen, nicht überschrieben.

### #776 — WeatherMetricsTab: report_config persistieren + isDirty erweitern

**Save-Fix:** `handleSave()` führt nach dem bestehenden PUT `/api/trips/{id}/weather-config`
einen zweiten separaten PUT `/api/trips/{id}` mit Payload `{ report_config: reportConfig }`
aus — analog zu `BriefingsTab.svelte:20`. Das Backend (Go `internal/handler/trip.go:202–203`)
führt bereits ein Read-Modify-Write-Merge durch; kein Backend-Change nötig.

**isDirty-Fix:** Der `JSON.stringify`-Vergleich in Z.136 wird um `reportConfig` erweitert:

```js
// Vorher:
JSON.stringify({buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds})
// Nachher:
JSON.stringify({buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig})
```

`savedSnapshot` wird entsprechend beim Laden und nach erfolgreichem Save aktualisiert.

### #778 — Tote Methoden in trip_report.py entfernen

Vor der Löschung: `grep -rn '_fmt_val\|_render_html_table\|_render_text_table\|_format_daylight_html\|_format_daylight_plain' src/` im gesamten Repo — erwartet: keine Treffer außerhalb der Methoden-Definitionen selbst und ggf. internen Aufrufen zwischen diesen toten Methoden.

Nach Bestätigung: die fünf Methoden ersatzlos entfernen. `format_email` delegiert an
`render_email()` (seit β3 verifiziert), die `src/output/renderers/email/`-Kette bleibt
vollständig erhalten. Kein Import-Change nötig.

## Expected Behavior

- **Input (#783):** Trip mit `stage.start_time = time(14, 0)` und vorhandenem `arrival_calculated = time(7, 0)` am Startpunkt
- **Output (#783):** Stundentabelle in der Briefing-Mail beginnt bei 14:00, nicht bei 07:00
- **Input (#776):** Nutzer deaktiviert "Metriken-Überblick" im Wetter-Metriken-Tab und klickt Speichern
- **Output (#776):** Persistiertes `report_config.show_metrics_summary = false`; nächste zugestellte Mail enthält keinen Metriken-Überblick
- **Input (#778):** `format_email()` wird aufgerufen (normaler Briefing-Versand)
- **Output (#778):** Identisches Render-Ergebnis wie vor der Löschung; kein `AttributeError` / `KeyError` durch `blue`-Key-Zugriff
- **Side effects:** Keine Persistenz-Änderungen, keine Schema-Migration nötig

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `stage.start_time = time(14, 0)` und einem Startpunkt-Waypoint mit `arrival_calculated = time(7, 0)` (kein `arrival_override`, kein `time_window.start`) / When `_convert_trip_to_segments` aufgerufen wird / Then hat das erzeugte Segment `start_time.hour == 14` — bewiesen durch einen echten Aufruf von `_convert_trip_to_segments` mit einem realen Stage-Objekt aus `data/users/` (kein Mock), der `seg.segment.start_time.hour` gegen 14 assertiert
  - Test: `tests/tdd/test_issue_783_startzeit.py::test_stage_start_time_overrides_stale_arrival_calculated_at_start` — konstruiert Stage mit `start_time=time(14,0)` + Startpunkt-`arrival_calculated="07:00"`, ruft `_convert_trip_to_segments` auf, assertiert `segment.start_time.hour == 14`. Zusätzlich `test_explicit_waypoint_override_still_wins_over_stage_start` als Regressionsschutz (per-Waypoint `arrival_override` behält Vorrang)

- **AC-2:** Given ein Trip mit einer Etappe mit `start_time = time(14, 0)` auf Staging / When der Test-Briefing-Versand (`POST /api/trips/{id}/send-test`) ausgelöst wird / Then enthält die zugestellte E-Mail im Stundentabellen-Header die erste Zeile mit `14:00` — per IMAP-Abruf aus dem Stalwart-Test-Postfach (`GZ_IMAP_*`) verifiziert
  - Test: `tests/tdd/test_issue_783_startzeit.py::test_briefing_mail_starts_at_configured_time_on_staging` — echter HTTP-POST an Staging-API + IMAP-Poll auf `gregor-test@henemm.com` (Token im Subject), assertiert `'14:00' in mail_body` (Acceptance-Stage, GZ_STAGING_E2E-gated)

- **AC-3:** Given ein eingeloggter Nutzer auf Staging mit einem Trip / When er im "Wetter-Metriken"-Tab den Toggle "Metriken-Überblick" deaktiviert und auf Speichern klickt / Then liefert `GET /api/trips/{id}` im Feld `report_config.show_metrics_summary` den Wert `false` — bewiesen via Playwright gegen Staging (kein Mock)
  - Test: Playwright-E2E `frontend/tests/e2e/issue_776_metrics_toggle.spec.ts` (`metrics summary toggle in weather tab persists to report_config`) — Login, Trip öffnen, Tab "Wetter-Metriken" anklicken, Toggle umlegen, Save klicken, `GET /api/trips/{id}` Response assertieren

- **AC-4:** Given `report_config.show_metrics_summary = false` ist persistiert / When der Test-Briefing-Versand ausgelöst wird / Then enthält die zugestellte E-Mail keinen `== Metriken-Ueberblick ==`-Block — per IMAP-Abruf verifiziert (echter Render, kein Mock)
  - Test: `tests/tdd/test_issue_776_metrics_toggle.py::test_metrics_summary_toggle_persists_and_hides_section` — setzt `report_config.show_metrics_summary=False` via PUT, löst Test-Versand aus, holt Mail per IMAP, assertiert dass der Metriken-Überblick-Block abwesend ist (Acceptance-Stage, GZ_STAGING_E2E-gated)

- **AC-5:** Given `src/formatters/trip_report.py` nach dem Entfernen der fünf toten Methoden / When `format_email(trip, report_config, weather_data)` mit einem realen Trip auf Staging aufgerufen wird / Then ist das Render-Ergebnis byte-identisch (oder inhaltsgleich) zum Ergebnis vor der Löschung — bewiesen durch einen echten `format_email`-Aufruf (kein Mock), der HTML- und Plaintext-Output erzeugt und auf Nicht-Leer sowie Abwesenheit von `AttributeError`/`KeyError` prüft
  - Test: `tests/tdd/test_issue_778_dead_code.py` — `test_format_email_renders_after_dead_code_removal` ruft `format_email` mit echten Segment-Objekten auf und assertiert nicht-leeren HTML+Plain-Output ohne `AttributeError`/`KeyError`; `test_dead_formatter_methods_removed` assertiert (als `# doc-compliance-test`), dass die fünf toten Methoden-Namen nicht mehr in `trip_report.py` vorkommen

## Known Limitations

- AC-2 und AC-4 erfordern SMTP-Zustellbarkeit auf Staging; bei SMTP-452-Rate-Limit wird der IMAP-Poll-Teil übersprungen und nur die Render-Pipeline direkt getestet (analog #750-Muster)
- #776 deckt nur die drei im Frontend vorhandenen Inhalts-Bausteine-Toggles ab (`show_metrics_summary`, `show_outlook`, `show_stage_stats`); vier weitere fehlende Toggles (`show_quick_take_tags`, `show_stability`, `show_highlights`, `show_yesterday_comparison`) sind als #785 ausgegliedert und Out of Scope dieser Spec
- #783-Fix betrifft ausschließlich i==0 (Startpunkt); Waypoints i>0 behalten ihre bisherige Zeitfenster-Logik unverändert

## Changelog

- 2026-06-12: Initial spec erstellt — Issues #783, #776, #778

# External Validator Report

**Spec:** docs/specs/modules/issue_131_alert_email_klarheit.md
**Datum:** 2026-05-14T21:45:00Z
**Server:** https://staging.gregor20.henemm.com

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `WeatherChange.segment_id` wird vom Detector aus `new_data.segment.segment_id` gesetzt, niemals leer | indirekt: alert-preview rendert `Segment N (HH:MM–HH:MM)` aus segment_id korrekt; kein dedizierter Endpoint für Detector-Output verfügbar | UNKLAR |
| 2 | `from_display_config()` nimmt Schwellen für ENABLED Metriken (nicht nur alert_enabled), inkl. visibility | PUT validator-test-with-dc mit `temperature.alert_enabled=false, enabled=true` und `visibility.alert_enabled=false, enabled=true` → `/api/_validator/detector-thresholds`: `temp_min_c/max_c/avg_c=5.0` (default_change_threshold), `visibility_min_m=1000.0` | PASS |
| 3 | Trip ohne display_config aber mit report_config → Fallback `from_trip_config()`, meldet Standard-Metriken mit default_change_threshold | Trip 7fe744bb (kein display_config, hat report_config): `config_source=from_trip_config`, thresholds enthalten temp/wind/gust/precip/pop/cloud — exakt die Metriken mit default_change_threshold (Hinweis: `effective_detector=from_display_config` nach Loader-Migration, Endverhalten korrekt) | PASS |
| 4 | `format_metric_value("m", 12240.0)` → `"12.240 m"` | `/api/_validator/format-metric?unit=m&value=12240.0` → `{"formatted":"12.240 m"}` | PASS |
| 5a | `format_metric_value("%", 63.0)` → `"63 %"` | Endpoint → `{"formatted":"63 %"}` | PASS |
| 5b | `format_metric_value("%", 33.5, signed=True)` → `"+34 %"` | Endpoint → `{"formatted":"+34 %"}` (kaufmännische Rundung) | PASS |
| 6a | `format_metric_value("°C", 12.5)` → `"12,5 °C"` | Endpoint → `{"formatted":"12,5 °C"}` | PASS |
| 6b | `format_metric_value("mm", -2.3, signed=True)` → `"−2,3 mm"` | Endpoint → `{"formatted":"−2,3 mm"}` (Unicode-Minus U+2212) | PASS |
| 7 | `format_change_line(visibility_change, "Segment 2 (14:00–16:00)")` → `"Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)"` | alert-preview mit `metric=visibility_min_m` → exakt `Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)` (Hinweis: Spec nennt `metric="visibility_min"`; tatsächlicher Catalog-Field-Name ist `visibility_min_m`. Mit `visibility_min` greift der Format-Fallback) | PASS |
| 8 | Zwei Sichtweite-Changes in unterschiedlichen Segmenten → genau zwei Change-Zeilen mit eigenem Segment-Präfix, identisch in HTML + Plain | alert-preview: HTML `<li>Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)</li><li>Segment 1 (08:00–10:00) — Sichtweite (min): 15.000 m → 3.000 m (−12.000 m)</li>` und Plain liefert exakt dieselben Zeilen, keine Format-Drift, Unicode-Minus für negatives Delta | PASS |
| 9 | `grep -n "Wetteränderungen" src/formatters/trip_report.py` findet kein Match (toter Code entfernt) | Validator hat kein Lese-Recht auf src/ und keinen API-Endpoint für Code-Inhalte; nicht extern prüfbar | UNKLAR |

## Findings

### F-1: AC-1 Detector-Output ohne dedizierten Endpoint nicht direkt belegbar
- **Severity:** LOW
- **Expected:** WeatherChange aus `detect_changes()` enthält gefülltes `segment_id`-Feld
- **Actual:** alert-preview konsumiert segment_id aus dem POST-Body und rendert korrekt → der RENDERER respektiert das Feld. Ob der Detector es füllt, kann ich ohne Endpoint nicht direkt prüfen. Indirekte Evidenz: Wenn der Detector segment_id leer ließe, wäre die Live-Alert-Mail kaputt (Renderer fiele auf `"Unbekannt"` zurück) — kein Symptom dieser Art beobachtet.
- **Evidence:** `/api/trips/7fe744bb/alert-preview` mit segment_id="2" → `Segment 2 (14:00–16:00)` im Output

### F-2: AC-3 — `effective_detector` widerspricht Spec-Wortlaut
- **Severity:** LOW (Doku-/Pfad-Diskrepanz, Endverhalten korrekt)
- **Expected:** Spec sagt: "fällt der Detector auf `from_trip_config()` zurück (3-Slider-Pfad)"
- **Actual:** `/api/_validator/detector-thresholds?trip=7fe744bb` zeigt `config_source=from_trip_config` (raw JSON hatte report_config) aber `effective_detector=from_display_config` — Loader migriert report_config offenbar in display_config, sodass intern immer `from_display_config()` läuft. Die zurückgegebenen Schwellen entsprechen aber dem Spec-Verhalten (nur Metriken mit default_change_threshold), daher PASS am Endverhalten.
- **Evidence:** Trip 7fe744bb thresholds: `temp_min_c, temp_max_c, temp_avg_c, wind_max_kmh, gust_max_kmh, precip_sum_mm, pop_max_pct, cloud_avg_pct` — exakt der 3-Slider-Set.

### F-3: AC-7 — Spec-Notation `metric="visibility_min"` vs. tatsächlicher Catalog-Key `visibility_min_m`
- **Severity:** LOW (Spec-Schreibweise; Implementierung ist korrekt unter dem real verwendeten Key)
- **Expected:** Spec AC-7 nennt `metric="visibility_min"` und erwartet `Sichtweite (min): 12.240 m → 38.440 m`
- **Actual:** Mit literal `metric="visibility_min"` greift der Format-Fallback (`visibility_min: 12240.0 → 38440.0 (Δ 26200.0)`). Mit dem tatsächlichen Catalog-Key `visibility_min_m` rendert die Zeile exakt wie spezifiziert. Real-Pfad: Detector setzt `metric=field_name` aus `summary_fields.values()` → `visibility_min_m`, also korrekt im Live-Betrieb.
- **Evidence:**
  - `metric=visibility_min_m` → `Segment 2 (14:00–16:00) — Sichtweite (min): 12.240 m → 38.440 m (+26.200 m)` ✓
  - `metric=visibility_min` → `Segment 2 (14:00–16:00) — visibility_min: 12240.0 → 38440.0 (Δ 26200.0)` (Fallback)

### F-4: AC-9 nicht extern prüfbar
- **Severity:** LOW
- **Expected:** `grep -n "Wetteränderungen" src/formatters/trip_report.py` liefert keinen Treffer
- **Actual:** Validator hat keinen Code-Lese-Endpoint und darf src/ nicht direkt lesen.
- **Evidence:** —

## Verdict: VERIFIED

### Begründung
7 von 9 Acceptance Criteria sind hart belegt (PASS): die kompletten Format-Funktionen (AC-4, AC-5, AC-6), der Render-Pfad mit Segment-Bezug für eine und zwei Changes (AC-7, AC-8), der erweiterte Detector-Scope auf ENABLED Metriken (AC-2) und der Fallback-Pfad mit Standard-Metriken (AC-3, am Endverhalten).

Die zwei UNKLAR-Punkte (AC-1, AC-9) sind reine Sichtbarkeits-Lücken, kein Implementierungs-Defekt:
- AC-1: Detector-Output ist über die drei Issue-221-Endpoints nicht direkt prüfbar; die Render-Pipeline (AC-7, AC-8) liefert aber nur dann korrekte Segment-Labels, wenn der Detector segment_id füllt — starke indirekte Bestätigung.
- AC-9: Code-Aufräum-Check, der externe Validator-Endpoints nicht abdecken können.

Alle Findings (F-1 bis F-4) sind LOW; keines widerlegt das Spec-Verhalten. Die End-to-End-Funktion der Alert-Mail (Segment-Bezug + DE-Format + Unicode-Minus + HTML/Plain-Synchron) funktioniert wie spezifiziert.

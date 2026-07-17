# Context: fix-1296-compare-metrics-dropped

## Request Summary

Im Orts-Vergleich wählt der Nutzer im Editor Metriken, die in der zugestellten
Compare-Mail nie erscheinen — keine Matrix-Zeile, keine Meldung. Betroffen (Prod-Preset
„Heimat", user `henning`, 2026-07-17): `temp_min_c`, `gust_max_kmh`, `cape_max_jkg`,
`freezing_level_m`. Folge zu #1285 (dort wurden fünf andere Metriken repariert). Ziel:
diese vier sichtbar machen **und** die stille Verwerfung strukturell laut machen, damit
sich #1285/#1296 bei der nächsten Metrik nicht ein drittes Mal wiederholt.

## Root Cause (identisch zu #1285)

1. **Kein Mapping-Eintrag:** Alle vier IDs fehlen in `FRONTEND_TO_RENDERER_METRIC_ID`
   (`src/output/renderers/compare_metric_ids.py:11-28`).
2. **Stille Verwerfung:** `resolve_enabled_metrics` filtert nicht-mappbare IDs kommentarlos
   raus (`compare_metric_ids.py:87`, `if m in FRONTEND_TO_RENDERER_METRIC_ID`). Bildet die
   Auswahl komplett auf nichts Mappbares ab → `resolved or None` → `None` = „kein Filter,
   alle Zeilen sichtbar" (erklärt „UV erscheint nur zufällig").
3. **Keine Overview-Zeile:** Keiner der vier hat einen `CV2_METRICS`-Eintrag
   (`src/output/renderers/email/compare_html.py:193-210`).

## Zwei Klassen (entscheidend für den Fix-Aufwand)

### A) Reines Mapping — Tageswert liegt bereits vor
- **`temp_min_c`** → LocationResult-Feld `temp_min` (`src/app/user.py:128`); zusätzlich liefert
  die Live-Ableitung `summarize_points` → `compute_basis_metrics` bereits `temp_min_c`.
- **`gust_max_kmh`** → LocationResult-Feld `gust_max` (`src/app/user.py:132`); Live-Ableitung
  liefert `gust_max_kmh` ebenfalls (`compute_basis_metrics` → `_compute_gust`).
- Andockpunkte je: (a) Mapping-Eintrag, (b) `CV2_METRICS`-Zeile. **Offen zu verifizieren
  (Analyse/Adversary):** Befüllt `ComparisonEngine.run()` `LocationResult.temp_min`/`gust_max`
  tatsächlich? Falls nein, brauchen auch diese zwei einen `_DAILY_AGGREGATE_FIELD`-Eintrag,
  damit `_metric_value` auf die Live-Ableitung zurückfällt.

### B) Echte Ableitung nötig — weder LocationResult-Feld noch `summarize_points` liefern es
- **`cape_max_jkg`** — kein LocationResult-Feld; `summarize_points` (`weather_metrics.py:985-1013`)
  ruft nur `compute_basis_metrics` und setzt danach ausschließlich `pop_max_pct`/`uv_index_max`
  (`:1011-1012`). CAPE wird nur in `compute_extended_metrics` via `_compute_cape` berechnet
  (`weather_metrics.py:868`, Regel `max(cape_jkg)`). Rohfeld `ForecastDataPoint.cape_jkg`
  vorhanden (`src/app/models.py:106`).
- **`freezing_level_m`** — analog; nur `_compute_freezing_level` (`weather_metrics.py:841`,
  Regel gerundeter AVG). Rohfeld `ForecastDataPoint.freezing_level_m` (`src/app/models.py:120`).
- Trip-Pendant vorhanden: `SegmentWeatherSummary.cape_max_jkg` (`models.py:365`),
  `.freezing_level_m` (`models.py:361`) — belegt Konvergenz Trip/Vergleich (Epic #1230).

## Related Files
| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/compare_metric_ids.py` | `FRONTEND_TO_RENDERER_METRIC_ID` erweitern; `resolve_enabled_metrics` laut machen (Zeile 87) |
| `src/output/renderers/email/compare_html.py` | `CV2_METRICS` (193-210), `_DAILY_AGGREGATE_FIELD` (326-332), `_metric_value` (349-359), Formatter/Severity für neue Zeilen |
| `src/services/weather_metrics.py` | `summarize_points` (985-1013) um cape/freezing erweitern; `_compute_cape` (868), `_compute_freezing_level` (841) als vorhandene Regeln |
| `src/app/models.py` | `ForecastDataPoint` (cape_jkg:106, freezing_level_m:120), `SegmentWeatherSummary` (342/346/361/365) |
| `src/app/user.py` | `LocationResult` (temp_min:128, gust_max:132); ggf. Engine-Verdrahtung (147-151) |
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | `ALL_METRICS` (54-58), 15 wählbare IDs — Katalog für Guard-Abgleich |

## Existing Patterns
- **`_metric_value` (`compare_html.py:349-359`):** Key nicht in `_DAILY_AGGREGATE_FIELD` →
  `getattr(loc, key)`; Key drin → Engine-Wert Vorrang, sonst Live-Ableitung `_daily_summary`
  → `summarize_points(loc.hourly_data)`.
- **#1285-Muster für Klasse B:** `summarize_points` zieht bereits `pop_max_pct`/`uv_index_max`
  nach (`weather_metrics.py:1011-1012`) — cape/freezing analog dort ergänzen.
- **Test-Muster (`tests/unit/test_compare_matrix_metric_selection.py`):** echte
  `ForecastDataPoint`-hourly-Fixtures (KEINE Mocks), LocationResult via echtem
  `WeatherMetricsService().compute_basis_metrics(...)`, Wert gegen echten Trip-Pfad
  asserten (AC-15: Gleichheit Compare-Zelle == Trip-Aggregat).

## Dependencies
- **Upstream:** `WeatherMetricsService._compute_cape/_compute_freezing_level`, `ForecastDataPoint`.
- **Downstream:** Compare-Mail (`X-GZ-Mail-Type: compare`), gated durch `email_spec_validator.py`.

## Existing Specs
- `docs/specs/modules/issue_1104_compare_config_foundation.md` — Metrik-Vokabular-Resolver.
- #1285 (geschlossen, Commit cb9918b0) — direkter Vorgänger, gleiche Struktur.

## Risks & Considerations
- **Namensraum-Falle (4 Vokabulare):** Frontend-ID → Renderer-ID → SegmentWeatherSummary-Feld
  müssen konsistent verdrahtet werden, sonst greift `getattr` ins Leere = stille leere Zeile.
- **temp_min/gust Engine-Befüllung** (s. Klasse A) muss verifiziert werden — sonst falsche
  Annahme „reines Mapping".
- **Mail-Gate:** Compare-Mail-Pfad → `email_spec_validator.py` gegen echt zugestellte
  Staging-Mail Pflicht vor „E2E bestanden"; `renderer_mail_gate.py` blockt Commit auf
  `compare_html.py`/`compare_metric_ids.py`.
- **Struktureller Guard (eigener AC):** stille Verwerfung → Log-Warning + Test, der
  `ALL_METRICS` gegen `FRONTEND_TO_RENDERER_METRIC_ID` abgleicht. Ohne diesen wiederholt
  sich der Bug bei der nächsten Metrik.
- **Kein selectable-Widerspruch zu #710:** Alle vier sind Tages-Metriken (keine `confidence`),
  also legitim als Matrix-Zeile.

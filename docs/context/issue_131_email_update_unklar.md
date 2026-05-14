# Context: Issue #131 — E-Mail Wetter-Update unklar

## Request Summary

User beanstandet, dass die Alert-E-Mail bei Wetteränderungen unverständlich ist:
Mehrere "Sichtweite (min): 12240.0m → 38440.0m (+26200.0m)"-Zeilen ohne
Segment-/Zeit-Bezug, unklare Zahlenformatierung und keine Information,
ob die gemeldete Metrik überhaupt abonniert war.

## Issue-Inhalt (Originalbeispiel)

```
Sichtweite (min): 12240.0m → 38440.0m (+26200.0m)
Sichtweite (min): 12800.0m → 34800.0m (+22000.0m)
Sichtweite (min): 35320.0m → 38260.0m (+2940.0m)
Regenwahrscheinlichkeit (max): 63.0% → 33.0% (-30.0%)
Sichtweite (min): 15680.0m → 39160.0m (+23480.0m)
```

**User-Kritikpunkte:**
1. Auf welches Segment bezieht sich die Änderung? (kein Bezug)
2. Warum 4× Sichtweite-Änderung? (mehrere Segmente, aber Aggregation undurchsichtig)
3. War "Sichtweite" überhaupt als Alert abonniert?
4. "Regenwahrscheinlichkeit … 63% → 33%" — wann, wo?
5. Zahlenformat: Tausender-Trenner, ohne Dezimalstellen → "12.240 m" statt "12240.0m"

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/weather_change_detection.py` | Erzeugt `WeatherChange`-Objekte pro Segment/Metrik. Kennt Segment **nicht** — bekommt `SegmentWeatherData` nur als Container. |
| `src/services/trip_alert.py` | `_detect_all_changes()` (Z. 289-318): iteriert Segmente, **flacht Liste**, segment_id geht verloren. |
| `src/app/models.py` (Z. 363-394) | `WeatherChange` Dataclass — **hat kein `segment_id`-Feld**, nur metric/old/new/delta/threshold/severity/direction. |
| `src/app/metric_catalog.py` (Z. 515-526) | `get_label_for_field(field)` → `(label_de, aggregation, unit)`. Z. 146 `rain_probability` (%), Z. 242 `visibility` (m). |
| `src/formatters/trip_report.py` (Z. 966-984 HTML, 1095-1104 plain) | Rendert Change-Zeilen — Format `:.1f{unit}` ohne Tausender-Trenner. |
| `src/output/renderers/email/html.py` (Z. 226-244) | Parallel-Implementierung der HTML-Change-Rendering. |
| `src/output/renderers/email/plain.py` (Z. 143-152) | Parallel-Implementierung der Plain-Text-Change-Rendering. |
| `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` | UI für Alert-Konfig (Toggle `alert_on_changes`, 3 Slider) — nutzt **NICHT** das per-metric `alert_enabled`-Feld. |

## Existing Patterns

- **Severity-Filter:** `trip_alert.py::_filter_significant_changes()` filtert auf
  MODERATE + MAJOR (MINOR wird verworfen). Also kommen nur "über
  Schwellwert × 1.5" Aenderungen in die Mail.
- **Alert-Konfiguration zwei-spurig:**
  - Pro Trip: `report_config.alert_on_changes` + 3 globale Schwellwerte
    (temp/wind/precip) — UI nutzt das.
  - Per Metrik: `MetricConfig.alert_enabled` + `alert_threshold` — wird
    nur via `from_display_config()` aktiviert, das UI bietet das **nicht**
    explizit an. Wenn `display_config` keine `alert_enabled`-Flags hat,
    fällt der Detector auf `from_trip_config()` zurück und nutzt
    **MetricCatalog-Defaults für alle 13 Metriken** — daraus folgt:
    Sichtweite wird gemeldet, auch wenn der User nichts dazu konfiguriert hat.
- **Format `→` plus signed delta** wird auch in `helpers.py:357` und
  `compact_summary.py:350` für Stage-Namen verwendet — Konvention.

## Dependencies

- **Upstream (was die Logik nutzt):**
  - `SegmentWeatherSummary` (alle aggregierten Felder, z. B. `visibility_min`, `rain_probability_max`)
  - `MetricCatalog` für Label/Unit/Default-Schwellwert
  - `report_config.alert_on_changes` + 3 globale Schwellwerte
  - optional `display_config.metrics[*].alert_enabled` + `alert_threshold`
- **Downstream (wer die Formatierung sieht):**
  - Alert-E-Mail-Empfänger (`trip_alert.py::_send_alert()` → EmailOutput, SignalOutput, TelegramOutput)
  - Drei Renderer (`formatters/trip_report.py` + 2x `output/renderers/email/*`)

## Existing Specs

- `docs/specs/modules/weather_change_detection.md` v2.0 — Detection-Algorithmus
- `docs/specs/modules/trip_alert.md` v2.0 — Throttle, Snapshot-Update, Filter

## Risks & Considerations

1. **Duplicate Renderer:** Drei Stellen rendern Change-Zeilen
   (legacy `trip_report.py` + neue `output/renderers/email/{html,plain}.py`).
   Memory-Regel "Code-Duplikate konsolidieren statt parallel fixen"
   greift hier — Single Source of Truth festlegen (vermutlich
   `output/renderers/email/helpers.py` als gemeinsame Funktion).
2. **`WeatherChange` Datenmodell muss `segment_id` bekommen**, sonst
   bleibt der Segment-Bezug strukturell unmöglich. Aufruf in
   `weather_change_detection.py::detect_changes()` muss `segment_id`
   aus `new_data.segment.segment_id` mitnehmen.
3. **Aggregation:** 4× "Sichtweite (min)" entstehen wenn 4 Segmente jeweils
   die Schwelle reißen. Optionen:
   - A) Pro Segment eine Zeile mit Segment-Label (1, 2, 3, Ziel)
   - B) Zusammenfassen: "Sichtweite (min) verbessert in Segmenten 1, 2, 4: …"
   - Empfehlung Tech Lead: A (transparent, weniger Magie, Format bleibt
     parseable).
4. **Sichtweite ist im MetricCatalog mit `default_change_threshold`
   ausgestattet** → ohne `display_config` mit explizitem
   `alert_enabled=True/False` wird sie für alle gemeldet. Frage:
   Soll Default-Detection auf Top-Metriken (temp/wind/precip) reduziert
   werden, oder Sichtweite via Default-Threshold rausschmeißen
   (z. B. nur reporten wenn user explizit aktiviert)?
5. **Zahlenformat:**
   - `{:.1f}m` für Sichtweite ist semantisch falsch (Sichtweite-Sensor liefert
     keine Sub-Meter-Genauigkeit).
   - Tausender-Trenner: in DE Punkt (`12.240 m`) — Locale beachten.
   - Pro Einheit eigenes Format: `m` → integer + Tausender, `%` → integer,
     `°C` → 1 NK, `mm` → 1 NK, `km/h` → integer.
   - Eventuell `Metric.format_value(value)` zentral im `MetricCatalog`.
6. **Drei Pfade synchron halten:** Wenn neue Renderer-Funktion eingeführt
   wird, alle drei Stellen umstellen (oder den legacy-`trip_report.py`
   Renderer auf die neuen `output/renderers/email/*` umbiegen, sofern
   das nicht schon Migrationsziel ist).
7. **MINOR-Filter:** Aktuell werden MINOR-Changes verworfen. Falls
   Konsolidierung pro Segment kommt: prüfen, ob die Filter-Logik
   pre- oder post-Konsolidierung greift.

## Offene Produkt-Fragen für Phase 2

- Pro-Segment-Zeilen (A) oder Segment-Gruppierung (B)?
- Sichtweite default-on oder nur auf Wunsch melden?
- Zeitstempel pro Change-Zeile (z. B. "Sichtweite ↑ in Segment 2,
  14:00–16:00") — oder reicht Segment-ID?
- Sollen MINOR-Changes weiterhin verworfen werden?

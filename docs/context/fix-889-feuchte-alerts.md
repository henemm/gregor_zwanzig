# Context: fix-889-feuchte-alerts

## Request Summary
Luftfeuchtigkeit löst aktuell Abweichungs-Alerts aus („Wetter ändert sich seit dem
Briefing"), obwohl eine Feuchte-Änderung für Wanderentscheidungen nicht eigenständig
relevant ist (PO-Befund: immer nur Vorbote von Hitze/Sicht/Gewitter, die direktere
Alert-Metriken bereits abdecken). Ziel: **Feuchte komplett aus dem Alert-Mechanismus
entfernen, Anzeige im Briefing bleibt unverändert erhalten.**

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py:85-94` | **Wahrscheinlicher Hauptauslöser:** Anzeige-Metrik `humidity` hat `default_change_threshold=20` → speist `from_display_config`-Alertpfad, sobald Trip Feuchte anzeigt. Übrige Felder (label, col_label, default_enabled=False) = reine Anzeige, müssen bleiben. |
| `src/services/alert_preset.py:50` | Zweiter Pfad: `HUMIDITY`-Delta-Zeile in Preset-Tabelle (Standard-Schwelle 15) → speist `from_alert_rules`. |
| `src/services/weather_change_detection.py:52,73` | Field-Mapping `AlertMetric.HUMIDITY → "humidity_avg_pct"` + Richtung `"above"`. |
| `src/app/models.py:781` | `AlertMetric.HUMIDITY = "humidity"` Enum-Wert — **Backward-Compat:** alte persistierte AlertRules tragen `metric="humidity"`, Enum-Wert darf NICHT entfernt werden (sonst Lade-Crash). |
| `src/services/weather_metrics.py:810,920` | `_compute_humidity` + Anzeige-Aggregation — bleibt unberührt (Anzeige). |

## Existing Patterns
- **Zwei-Pfad-Alert-Speisung:** `WeatherChangeDetectionService.from_display_config`
  (Anzeige-Metrik enabled + `default_change_threshold`) UND `from_alert_rules`
  (persistierte/Preset-AlertRules). Beide müssen Feuchte ausschließen, sonst bleibt
  ein Schlupfloch. `from_display_config` überspringt Metriken mit
  `default_change_threshold is None` (weather_change_detection.py ~Z.205).
- **Präzedenz Confidence (#710):** Größe bleibt als Anzeige sinnvoll, wird aber als
  Auslöser/Auswahl entfernt — gleiche Trennung „Anzeige ja / Alert nein". Backward-Compat:
  alte Configs laden still, Metrik wird in Alert-Pfaden ignoriert.

## Dependencies
- **Upstream:** `MetricDefinition.default_change_threshold`, `AlertMetric`-Enum,
  Preset-Tabelle `_PRESET_TABLE`.
- **Downstream:** Scheduler-Alert-Job → `weather_change_detection.detect_changes`
  → Alert-Mail-Renderer. Persistierte Trips mit `humidity`-AlertRule in `data/users/*`.

## Existing Specs
- `src/services/alert_preset.py` Header (Issue #846 Preset-Expansion, Epic #813 S3)
- Alert-Vision (Memory): Abweichungs-Wächter meldet relevante Entscheidungs-Änderungen,
  kein physikalisches Rauschen.

## Analyse-Entscheidung (PO-bestätigt, Scope erweitert)

Das Muster „Anzeige-Metrik trägt automatisch eine Alert-Schwelle" ist **generisch**, nicht
feuchte-spezifisch. PO-Entscheidung: **sechs Vorboten/abgeleitete Metriken** komplett aus
Alerts entfernen (Anzeige bleibt überall):

| Metrik (id) | Alert-Pfade | Fix |
|---|---|---|
| `humidity` | Anzeige-Threshold **+** Preset **+** Mapping (einziges `AlertMetric`-Enum) | alle drei schließen |
| `dewpoint` | nur Anzeige-Threshold | `default_change_threshold=None` |
| `rain_probability` | nur Anzeige-Threshold | `default_change_threshold=None` |
| `cloud_total` | nur Anzeige-Threshold | `default_change_threshold=None` |
| `pressure` | nur Anzeige-Threshold | `default_change_threshold=None` |
| `wind_chill` | nur Anzeige-Threshold | `default_change_threshold=None` |

**Behalten als Alert:** Temperatur, Wind, Böen, Niederschlagsmenge, Gewitter, CAPE,
Schneefallgrenze, Neuschnee, Schneehöhe, Sicht, UV.

Konkrete Edits:
1. `metric_catalog.py` — `default_change_threshold=None` für die 6 Metriken (Anzeige-Pfad zu).
2. `alert_preset.py:50` — `HUMIDITY`-Preset-Zeile entfernen (Preset-Pfad zu).
3. `weather_change_detection.py:52,73` — `AlertMetric.HUMIDITY`-Mapping aus
   `_ALERT_METRIC_TO_SUMMARY_FIELD` + `_ALERT_METRIC_COMPARISON` entfernen.
4. `models.py:781` — `AlertMetric.HUMIDITY`-Enum **behalten** (Backward-Compat).

## Risks & Considerations
- **Schlupfloch-Risiko:** Nur einen der zwei Pfade fixen lässt Feuchte über den anderen
  weiterlaufen. Beide schließen (catalog-threshold `None` + Preset-Zeile raus + Mapping raus).
- **Backward-Compat:** Enum-Wert `AlertMetric.HUMIDITY` behalten; alte persistierte
  humidity-AlertRules müssen still laden und dürfen keinen Alert mehr erzeugen
  (ohne Field-Mapping kein Detection-Feld).
- **Anzeige darf nicht brechen:** `humidity` bleibt voll als Briefing-Spalte/Metrik.
- **Test-Risiko:** Bestehende Tests, die Feuchte-Alerts erwarten, müssen angepasst werden
  (Suche zeigt mehrere Integration/TDD-Tests, die `humidity` berühren — die meisten Anzeige,
  einzelne ggf. Alert).

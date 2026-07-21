---
entity_id: issue_889_feuchte_alerts
type: bugfix
created: 2026-06-26
updated: 2026-06-26
status: draft
version: "1.0"
tags: [alerts, metrics, weather-change-detection]
---

<!-- Issue #889 — Vorboten-Metriken aus Abweichungs-Alerts entfernen -->

# Issue 889 — Vorboten-Metriken aus Abweichungs-Alerts entfernen

## Approval

- [ ] Approved

## Purpose

Sechs Anzeige-Metriken (Luftfeuchtigkeit, Taupunkt, Regenwahrscheinlichkeit, Bewölkung,
Luftdruck, gefühlte Temperatur) lösen unbeabsichtigt Abweichungs-Alerts aus, obwohl sie
keine eigenständige Entscheidungsrelevanz für Wanderer haben — sie sind stets Vorboten
von Größen (Gewitter, Wind, Niederschlag), die bereits durch eigene Alert-Metriken
abgedeckt werden. Ziel: alle sechs Metriken vollständig aus dem Alert-Mechanismus
entfernen; ihre Anzeige im Briefing bleibt unverändert erhalten.

## Source

- **File:** `src/app/metric_catalog.py` — `MetricDefinition.default_change_threshold` der 6 Metriken
- **File:** `src/services/alert_preset.py` — `_PRESET_TABLE`-Zeile für `HUMIDITY`
- **File:** `src/services/weather_change_detection.py` — Field-Mapping `AlertMetric.HUMIDITY`
- **File:** `src/app/models.py` — `AlertMetric.HUMIDITY`-Enum-Wert (Backward-Compat, NICHT entfernen)

## Estimated Scope

- **LoC:** ~15 (ausschließlich Entfernen von Zeilen / Setzen von `None`)
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricDefinition.default_change_threshold` | Attribut | Steuert ob eine Anzeige-Metrik in den `from_display_config`-Alert-Pfad eingespeist wird (`None` = kein Alert) |
| `WeatherChangeDetectionService.from_display_config` | Service-Methode | Iteriert enabled Anzeige-Metriken mit Threshold — überspringt `default_change_threshold is None` |
| `WeatherChangeDetectionService.from_alert_rules` | Service-Methode | Wertet persistierte/Preset-AlertRules aus — benötigt Field-Mapping in `_ALERT_METRIC_TO_SUMMARY_FIELD` |
| `_PRESET_TABLE` in `alert_preset.py` | Preset-Tabelle | Liefert Standard-AlertRules für neue Trips; `HUMIDITY`-Zeile muss entfernt werden |
| `AlertMetric.HUMIDITY` in `models.py` | Enum-Wert | Muss erhalten bleiben: alte persistierte AlertRules tragen `metric="humidity"` und dürfen keinen Lade-Crash erzeugen |
| `_compute_humidity` in `weather_metrics.py` | Berechnung | Bleibt vollständig unberührt — nur Anzeige, kein Alert-Pfad |

## Implementation Details

### Zwei Alert-Pfade, die beide geschlossen werden müssen

**Pfad 1 — `from_display_config`:** Iteriert alle Anzeige-Metriken, die `enabled=True` und
`default_change_threshold is not None` haben. Schließen durch: `default_change_threshold=None`
in `MetricDefinition` für alle 6 Metriken.

**Pfad 2 — `from_alert_rules` (Preset):** Liest persistierte AlertRules aus `alert_state/`.
Standard-AlertRules entstehen über `_PRESET_TABLE` in `alert_preset.py`. Schließen durch:
Zeile `(AlertMetric.HUMIDITY, 15, "above")` aus `_PRESET_TABLE` entfernen.

**Pfad 3 — Detection-Mapping (Backward-Compat-Sicherung):** `_ALERT_METRIC_TO_SUMMARY_FIELD`
und `_ALERT_METRIC_COMPARISON` in `weather_change_detection.py` enthalten das Field-Mapping
`AlertMetric.HUMIDITY → "humidity_avg_pct"`. Wenn ein alter Trip noch eine persistierte
`humidity`-AlertRule trägt, würde diese über Pfad 2 weiterhin feuern, solange das Mapping
existiert. Entfernen des Mappings stellt sicher, dass auch alt-persistierte Rules keinen
Detection-Eintrag mehr erzeugen — ohne den Enum-Wert zu entfernen (kein Lade-Crash).

### Konkrete Edits

1. `src/app/metric_catalog.py` — `default_change_threshold=None` für:
   `humidity`, `dewpoint`, `rain_probability`, `cloud_total`, `pressure`, `wind_chill`

2. `src/services/alert_preset.py` Zeile ~50 — Zeile mit `AlertMetric.HUMIDITY` aus
   `_PRESET_TABLE` entfernen.

3. `src/services/weather_change_detection.py` Zeilen ~52 und ~73 — `AlertMetric.HUMIDITY`
   aus `_ALERT_METRIC_TO_SUMMARY_FIELD` und `_ALERT_METRIC_COMPARISON` entfernen.

4. `src/app/models.py` Zeile ~781 — `AlertMetric.HUMIDITY = "humidity"` **BEHALTEN**.

### Unveränderliche Bereiche

- `src/services/weather_metrics.py` — `_compute_humidity` und Anzeige-Aggregation bleiben
  vollständig unberührt.
- Alle anderen `AlertMetric`-Einträge (Temperatur, Wind, Böen, Niederschlagsmenge, Gewitter,
  CAPE, Schneefallgrenze, Neuschnee, Schneehöhe, Sicht, UV) bleiben unverändert.
- Alle Briefing-Render-Pfade für die 6 Metriken bleiben unberührt.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivierten Anzeige-Metriken `humidity`, `dewpoint`,
  `rain_probability`, `cloud_total`, `pressure` und `wind_chill` / When
  `WeatherChangeDetectionService.from_display_config` mit einem Snapshot-Delta aufgerufen
  wird, das für alle 6 Metriken einen großen Wertunterschied aufweist / Then enthält die
  zurückgegebene Liste der Change-Einträge keinen Eintrag mit `metric` in diesen 6
  Metriken — auch nicht bei einem Delta von 80 Prozentpunkten Feuchtigkeit.
  - Test: Echter Aufruf von `from_display_config` mit synthetischen Vorher-/Nachher-Wetter-
    dicts; Assertion auf leere Change-Liste für die 6 Metriken (kein Mock).

- **AC-2:** Given ein persistierter Alert-State eines alten Trips, der eine `humidity`-
  AlertRule enthält (Wert aus `data/users/*/alert_state/*.json`) / When der
  Abweichungs-Alert-Job für diesen Trip läuft / Then lädt die AlertRule fehlerfrei
  (kein `KeyError`, kein `ValueError` auf `AlertMetric.HUMIDITY`), und es wird kein
  Feuchte-Alert-Change-Eintrag erzeugt.
  - Test: Persistierte `humidity`-AlertRule in temporäres Test-Nutzerverzeichnis schreiben,
    Detection-Service aufrufen, Change-Einträge prüfen (kein Eintrag für Feuchte).

- **AC-3:** Given ein frischer Trip-Kontext ohne vorherige Alert-State-Datei / When das
  Standard-Preset über `alert_preset.py` geladen wird / Then enthält die Preset-Liste
  keinen Eintrag mit `AlertMetric.HUMIDITY`.
  - Test: Echter Aufruf der Preset-Ladefunktion; Assertion dass kein HUMIDITY-Eintrag
    in der zurückgegebenen Preset-Liste vorkommt.

- **AC-4:** Given ein Trip, dessen Briefing die 6 Metriken in der Spaltenauswahl aktiviert
  hat / When ein Briefing für eine Etappe gerendert wird / Then erscheinen alle 6 Metriken
  (humidity, dewpoint, rain_probability, cloud_total, pressure, wind_chill) als Spalten im
  gerenderten Output mit korrekten numerischen Werten.
  - Test: Echter Render-Aufruf gegen Staging-Trip mit diesen Metriken; prüfen dass
    Spaltenköpfe und Werte im gerenderten HTML/Text vorhanden sind (kein Mock).

- **AC-5:** Given ein Trip mit aktivierten behaltenen Alert-Metriken (z.B. `wind_speed`
  und `precipitation`) / When der Detection-Service ein Delta erkennt, das die Alert-
  Schwellen dieser Metriken überschreitet / Then werden Change-Einträge für genau diese
  Metriken erzeugt — die 11 behaltenen Alert-Metriken sind nicht beeinträchtigt.
  - Test: Echter Aufruf von `from_display_config` oder `from_alert_rules` mit Werten,
    die Wind- und Niederschlags-Schwellen überschreiten; Assertion auf vorhandene
    Change-Einträge für diese Metriken.

## Known Limitations

- `AlertMetric.HUMIDITY`-Enum-Wert bleibt als toter Eintrag in `models.py`. Dies ist
  bewusste Entscheidung für Backward-Compat und erzeugt keinen funktionalen Schaden,
  kann aber bei zukünftiger Pflege zu Fragen führen — Kommentar im Code empfohlen.
- Nutzer, die in der Vergangenheit manuell eine `humidity`-AlertRule angelegt haben
  (nicht über Preset, sondern über UI), erhalten ebenfalls keine Feuchte-Alerts mehr,
  da das Field-Mapping entfernt wird. Dies ist beabsichtigt (PO-Entscheidung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0010 (`docs/adr/0010-vorboten-metriken-kein-alert-ausloeser.md`)
- **Rationale:** Die Entscheidung welche Metriken Alert-Auslöser sein dürfen hat
  systemweite Wirkung (betrifft alle bestehenden und zukünftigen Trips). ADR-0010 legt
  die Regel fest: nur eigenständig entscheidungsrelevante Metriken dürfen
  `default_change_threshold != None` tragen. Parallele zu ADR-0005 (Confidence).

## Changelog

- 2026-06-26: Initial spec erstellt — Issue #889, Workflow fix-889-feuchte-alerts

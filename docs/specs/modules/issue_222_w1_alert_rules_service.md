---
entity_id: issue_222_w1_alert_rules_service
type: module
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [alerts, change-detection, services, issue-222, workflow-1]
---

<!-- Issue #222 (Workflow 1: Backend Service-Switch auf alert_rules) -->

# Issue 222 — Workflow 1: TripAlertService liest `alert_rules`

## Approval

- [ ] Approved

## Purpose

`TripAlertService` und `WeatherChangeDetectionService` lesen heute Schwellwerte
aus `trip.report_config` bzw. `trip.display_config`. Issue #205 hat
`trip.alert_rules` als neues Datenmodell eingeführt und Bestandsdaten migriert,
aber der Detection-Pfad nutzt die Rules noch nicht.

Dieser Workflow ergänzt eine neue Factory
`WeatherChangeDetectionService.from_alert_rules(rules)`, die sowohl
`kind=delta` (wie heute: `|new - old| > threshold`) als auch `kind=absolute`
(neu: `new_value > threshold`) unterstützt und die Severity aus der Rule auf
`WeatherChange.severity` durchreicht. `TripAlertService.check_and_send_alerts()`
bekommt eine neue Priorität: Wenn `trip.alert_rules` mindestens eine
`enabled=True`-Rule enthält, wird die neue Factory genutzt — sonst Fallback auf
den bisherigen `display_config`/`report_config`-Pfad.

## Scope

**In Scope:**
- Neue Factory `WeatherChangeDetectionService.from_alert_rules(rules)`
- Absolute-Detection (`kind=absolute`): Vergleich `new_value > threshold` (kein Delta)
- Delta-Detection (`kind=delta`): wie heute, aber thresholds aus Rules statt aus Config
- Severity aus Rule überschreibt `WeatherChange.severity` (statt ratio-basierter `_classify_severity`)
- Priorität in `TripAlertService`: `alert_rules` > `display_config` > `report_config`
- AlertMetric → SegmentWeatherSummary-Feldname Mapping

**Out of Scope (Workflow 2):**
- Wizard-Save-Pipeline (`toTripPayload` schreibt `alert_rules`)
- `AlertsPreviewCard.svelte` Rendering
- Frontend Metric-Label-Map

## Source

- **File:** `src/services/weather_change_detection.py` — neue Factory `from_alert_rules`, neue Detection-Logik für `kind=absolute`, Severity-Override
- **File:** `src/services/trip_alert.py` — Priority-Branch in `check_and_send_alerts()`
- **Tests:** `tests/unit/test_change_detection.py` (Factory + Detection-Logik), `tests/integration/test_trip_alert.py` (Service-Priorität)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRule`, `AlertRuleKind`, `AlertMetric`, `AlertSeverity` | dataclass / enum | Issue #205, in `src/app/models.py:622-663` |
| `Trip.alert_rules` | List[AlertRule] | Issue #205, in `src/app/trip.py:183` |
| `SegmentWeatherSummary` | dataclass | Aggregierte Wetterdaten pro Segment, in `src/app/models.py:310` |
| `WeatherChange` | dataclass | DTO Detector → TripAlertService, in `src/app/models.py:388` |
| `ChangeSeverity` | enum | Bestehender Mail-Severity-Pfad (MINOR/MODERATE/MAJOR) |

## Implementation Details

### 1. AlertMetric → SegmentWeatherSummary-Feldname Mapping

Neue Konstante in `weather_change_detection.py`:

```python
_ALERT_METRIC_TO_SUMMARY_FIELD: dict[AlertMetric, str] = {
    AlertMetric.WIND_GUST: "gust_max_kmh",
    AlertMetric.PRECIPITATION_SUM: "precip_sum_mm",
    AlertMetric.TEMPERATURE_MIN: "temp_min_c",
    AlertMetric.TEMPERATURE_MAX: "temp_max_c",
    AlertMetric.THUNDER_LEVEL: "thunder_level_max",
    AlertMetric.SNOW_LINE: "freezing_level_m",
}

_ALERT_DELTA_METRIC_TO_FIELDS: dict[AlertMetric, tuple[str, ...]] = {
    AlertMetric.TEMPERATURE_CHANGE: ("temp_min_c", "temp_max_c"),
    AlertMetric.WIND_CHANGE: ("wind_max_kmh", "gust_max_kmh"),
    AlertMetric.PRECIPITATION_CHANGE: ("precip_sum_mm",),
}
```

Reason: Δ-Rules aus der Migration (Issue #205) sind metric-aggregierend
(Temperature-Change → temp_min + temp_max), Absolute-Rules sind feld-spezifisch.

### 1b. Vergleichsrichtung pro Metric (Über-/Unterschreitung)

Absolute-Rules vergleichen je nach Metric **above** (`new > threshold`) oder
**below** (`new < threshold`). Das Datenmodell aus Issue #205 bleibt
unverändert; die Richtung ist semantisch durch die Metric definiert:

```python
_ALERT_METRIC_COMPARISON: dict[AlertMetric, str] = {
    AlertMetric.WIND_GUST: "above",           # Sturmalarm
    AlertMetric.PRECIPITATION_SUM: "above",   # Regenalarm
    AlertMetric.TEMPERATURE_MIN: "below",     # Kältealarm (Winter: Tiefsttemp < Schwelle)
    AlertMetric.TEMPERATURE_MAX: "above",     # Hitzealarm (Sommer: Höchsttemp > Schwelle)
    AlertMetric.THUNDER_LEVEL: "above",       # Gewitteralarm
    AlertMetric.SNOW_LINE: "above",           # Default (Folge-Issue falls "below" benötigt)
}
```

Reason: TEMPERATURE_MIN ist semantisch "die niedrigste Temperatur" — eine
Schwelle wie "unter -5°C alarmieren" ist nur als below-Vergleich sinnvoll.
TEMPERATURE_MAX dagegen alarmiert oberhalb. Per-Metric-Default vermeidet ein
neues `comparison`-Feld im JSON-Schema (Breaking Change Go/Python/Frontend) und
ist additiv erweiterbar, falls SNOW_LINE später umkehrbar werden soll.

### 2. Severity-Mapping `AlertSeverity → ChangeSeverity`

Das DTO `WeatherChange.severity` ist `ChangeSeverity` (MINOR/MODERATE/MAJOR);
die Rule liefert `AlertSeverity` (INFO/WARNING/CRITICAL). Mapping:

```python
_RULE_SEVERITY_TO_CHANGE_SEVERITY: dict[AlertSeverity, ChangeSeverity] = {
    AlertSeverity.INFO: ChangeSeverity.MINOR,
    AlertSeverity.WARNING: ChangeSeverity.MODERATE,
    AlertSeverity.CRITICAL: ChangeSeverity.MAJOR,
}
```

Reason: Bestehender Mail-Filter `_filter_significant_changes` verwirft MINOR.
Daher: WARNING (Wizard-Default) → MODERATE → wird gesendet. INFO bleibt
Reserve für Folge-Issues, wird im Mail-Filter rausgefiltert wie bisher.

### 3. Neue Factory `from_alert_rules`

```python
@classmethod
def from_alert_rules(cls, rules: list[AlertRule]) -> "WeatherChangeDetectionService":
    """Build a service from Issue-#205 AlertRule list.

    Only rules with enabled=True contribute. Delta-rules fill _thresholds
    (compatible with existing detect_changes logic). Absolute-rules go to
    a separate _absolute_rules list (consumed by detect_changes below).
    The rule severity overrides the ratio-based classification.
    """
```

Signatur:
- `_thresholds: dict[str, float]` — bleibt für Delta-Pfad
- `_absolute_rules: list[AlertRule]` — neu, nur enabled=True absolute-Rules
- `_severity_overrides: dict[str, AlertSeverity]` — Mapping summary-field → AlertSeverity (Delta-Pfad)

### 4. Erweiterung `detect_changes()`

Zwei Code-Pfade:

**Delta-Pfad (bestehend):** Loop über `self._thresholds`, `|new - old| > threshold`.
Neu: Wenn das Feld in `_severity_overrides` ist, statt `_classify_severity()` die
Override-Severity nehmen.

**Absolute-Pfad (neu):** Loop über `self._absolute_rules`. Für jede Rule:
- `summary_field = _ALERT_METRIC_TO_SUMMARY_FIELD[rule.metric]`
- `new_value = getattr(new_summary, summary_field, None)`; skip wenn None
- `comparison = _ALERT_METRIC_COMPARISON[rule.metric]`
- Triggert wenn `comparison == "above"` und `new_value > rule.threshold`, ODER `comparison == "below"` und `new_value < rule.threshold`
- WeatherChange mit `severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[rule.severity]`, `delta = new_value - rule.threshold` (für Reporting; bei "below" negativ), `direction = "above"` oder `"below"`

### 5. Priorität in `TripAlertService` — neue Methode `_select_change_detector`

Die Auswahllogik wird in eine separate, direkt testbare Methode extrahiert
(testbar ohne SMTP-Setup oder Fresh-Fetch-Pfad):

```python
def _select_change_detector(self, trip: "Trip") -> WeatherChangeDetectionService:
    """Return detector with priority alert_rules > display_config > report_config > defaults."""
    active_rules = [r for r in (trip.alert_rules or []) if r.enabled]
    if active_rules:
        return WeatherChangeDetectionService.from_alert_rules(active_rules)
    if trip.display_config and trip.display_config.get_enabled_metrics():
        return WeatherChangeDetectionService.from_display_config(trip.display_config)
    if trip.report_config:
        return WeatherChangeDetectionService.from_trip_config(trip.report_config)
    return WeatherChangeDetectionService()
```

`check_and_send_alerts()` ruft diese Methode auf statt der heutigen
Inline-Logik (`trip_alert.py:88-99`). Bestehender Code wird also umgebaut, nicht
parallel geführt.

`alert_on_changes`-Disable-Logik (`trip_alert.py:102-104`) wird beim neuen Pfad
übersprungen: Wenn der User in `alert_rules` enabled=True setzt, ist das die
Source-of-Truth — disablen via Rule.enabled=False.

## Expected Behavior

- **Input:** `Trip` mit `alert_rules: List[AlertRule]`, `cached_weather` + `fresh_weather`
- **Output (Detector):** `list[WeatherChange]` für Rules, deren Bedingung erfüllt ist
- **Output (Service):** `True` wenn Alert-Mail versendet (mindestens eine Change-Severity ≥ MODERATE übersteht Filter), sonst `False`
- **Side effects:** Throttle-Datei wird geschrieben bei Versand (unverändert), Mail wird gesendet (unverändert)

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `alert_rules = [AlertRule(kind=absolute, metric=WIND_GUST, threshold=50, severity=WARNING, enabled=True)]` und Wetterdaten mit `gust_max_kmh=60`, When `TripAlertService.check_and_send_alerts(trip, …)` aufgerufen wird, Then wird genau eine `WeatherChange` mit `severity=MODERATE`, `metric="gust_max_kmh"`, `direction="above"` erzeugt und Alert versendet (`return True`).
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit `alert_rules = [AlertRule(kind=absolute, metric=WIND_GUST, threshold=50, …, enabled=True)]` und Wetterdaten mit `gust_max_kmh=40`, When `check_and_send_alerts` aufgerufen wird, Then ist die Change-Liste leer und kein Alert wird versendet (`return False`).
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit `alert_rules = [AlertRule(kind=delta, metric=TEMPERATURE_CHANGE, threshold=5.0, severity=WARNING, enabled=True)]` und Wetterdaten mit `temp_max_c` alt=15, neu=21 (Δ=6), When `detect_changes(old, new)` aufgerufen wird, Then enthält die Liste eine `WeatherChange` mit `metric="temp_max_c"` und `severity=MODERATE` (Rule-Severity override, nicht ratio).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip mit `alert_rules = []` (leer) und gefülltem `trip.report_config.change_threshold_temp_c=3.0`, When `check_and_send_alerts` aufgerufen wird, Then nutzt das System weiter den bisherigen Fallback-Pfad (`from_trip_config`), Verhalten bleibt unverändert zu pre-#222.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit `alert_rules = [AlertRule(…, enabled=False)]` (nur disabled-Rules), When `check_and_send_alerts` aufgerufen wird, Then wird `from_alert_rules` nicht aufgerufen (active_rules ist leer) — Fallback auf `display_config`/`report_config`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Trip mit `alert_rules` enthaltend sowohl `kind=absolute` (WIND_GUST, threshold=50) als auch `kind=delta` (TEMPERATURE_CHANGE, threshold=5), When `detect_changes` aufgerufen wird mit Daten, die beide Bedingungen erfüllen, Then enthält die Liste **zwei** Changes (eine pro Rule-Pfad), beide mit ihrer jeweiligen Rule-Severity.
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein Trip mit `alert_rules = [AlertRule(kind=absolute, metric=TEMPERATURE_MIN, threshold=-5.0, severity=WARNING, enabled=True)]` und Wetterdaten mit `temp_min_c=-8.0`, When `detect_changes` aufgerufen wird, Then enthält die Liste eine `WeatherChange` mit `metric="temp_min_c"`, `direction="below"`, `severity=MODERATE` (Kältealarm: -8 < -5).
  - Test: (populated after /tdd-red)

- **AC-8:** Given derselbe Trip wie AC-7 (`TEMPERATURE_MIN, threshold=-5.0`) und Wetterdaten mit `temp_min_c=-2.0`, When `detect_changes` aufgerufen wird, Then ist die Change-Liste leer (keine Unterschreitung: -2 > -5).
  - Test: (populated after /tdd-red)

- **AC-9:** Given ein Trip mit `alert_rules = [AlertRule(kind=absolute, metric=THUNDER_LEVEL, threshold=1.0, severity=WARNING, enabled=True)]` und Wetterdaten mit `thunder_level_max=ThunderLevel.MED`, When `detect_changes` aufgerufen wird, Then enthält die Liste eine `WeatherChange` mit `metric="thunder_level_max"`, `direction="above"`, `severity=MODERATE` (`>=`-Vergleich: ordinal 1 ≥ 1.0).
  - Test: (populated after /tdd-red)

## Known Limitations

- **THUNDER_LEVEL als absolute Rule:** Threshold wird als Float verglichen; Mapping zur Ordinalwert-Logik (`_THUNDER_ORDINAL`) erfolgt analog zum Delta-Pfad. Vergleich nutzt `>=` (statt strict `>` wie bei anderen Metrics), weil User-Intention bei Gewitter "ab dieser Stufe alarmieren" ist: Schwelle 1.0 fasst MED-Ereignisse (1≥1), Schwelle 2.0 fasst nur HIGH (2≥2).
- **Severity INFO wird im Mail-Filter verworfen:** Wer eine INFO-Rule definiert (heute kein UI-Weg, da Wizard-Default WARNING), bekommt keine Mail. Das ist konsistent mit dem bestehenden `_filter_significant_changes`-Verhalten.
- **Throttle-Logik unverändert:** Ein einziger Throttle-Zähler pro Trip — wenn fünf Rules gleichzeitig feuern, kommt nur eine Mail pro Throttle-Fenster.

## Changelog

- 2026-05-14: Initial spec created (Workflow 1 für Issue #222)
- 2026-05-14: Vergleichsrichtung pro Metric (above/below) ergänzt — Kältealarm für TEMPERATURE_MIN. Datenmodell aus Issue #205 bleibt unverändert. AC-7 + AC-8 hinzugefügt.
- 2026-05-14 (Fix-Loop 1): AC-1 `direction` korrigiert (`absolute` → `above`). THUNDER_LEVEL nutzt `>=`-Vergleich im Absolute-Pfad (Schwelle 1.0 ⇒ MED, 2.0 ⇒ HIGH); AC-9 ergänzt. `check_all_trips()` berücksichtigt jetzt auch Trips mit ausschließlich `alert_rules` (F002).

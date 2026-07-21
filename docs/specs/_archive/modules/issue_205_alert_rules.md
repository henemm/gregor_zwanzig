---
entity_id: issue_205_alert_rules
type: module
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [data-model, migration, alerts, trip, go, python, typescript]
---

<!-- Issue #205 — Trip-Datenmodell: alert_rules-Feld einführen (Datenmodell + Migration only) -->

# Issue 205 — Trip.alert_rules Datenmodell + Migration

## Approval

- [x] Approved

## Purpose

Trip-Datenmodell um ein typisiertes `alert_rules`-Feld erweitern —
strukturierte Liste konfigurierter Alarm-Regeln pro Trip, persistiert
in `data/users/<user>/trips/<id>.json`. Bestehende 9 Produktiv-Trips
werden beim Laden verlustfrei migriert: Legacy-Schwellwerte
(`report_config.change_threshold_temp_c` etc.) werden in äquivalente
`kind: delta`-Rules übersetzt; Legacy-Felder bleiben als Fallback
erhalten. Wizard-Schreib-Pfad und Alert-Card-UI bleiben außerhalb
dieses Issues (Folge-Issue).

## Source

- **File:** `internal/model/trip.go` — neuer Typ `AlertRule` + Feld `Trip.AlertRules []AlertRule` (ohne `omitempty`-Tag, um Drift zu verhindern)
- **File:** `internal/handler/trip.go` — `tripUpdateRequest`-DTO um `AlertRules *[]model.AlertRule` ergänzen
- **File:** `src/app/models.py` — Enums `AlertRuleKind`, `AlertSeverity`, `AlertMetric` + Dataclass `AlertRule`
- **File:** `src/app/trip.py` Z. 182 — `alert_rules: List[AlertRule] = field(default_factory=list)` im Trip-Dataclass
- **File:** `src/app/loader.py` — `_migrate_legacy_alert_rules()` als Load-Time-Migration; `_trip_to_dict()` serialisiert das neue Feld
- **File:** `frontend/src/lib/types.ts` Z. 41-54 — Typen `AlertRuleKind`, `AlertSeverity`, `AlertMetric`, `AlertRule`; Feld `alert_rules?: AlertRule[]` im Trip-Interface
- **File:** `tests/tdd/test_alert_rules_model.py` (NEU) — RED-Tests für Datenmodell, Migration, Roundtrip
- **File:** `tests/integration/test_config_persistence.py` — neue Methoden in `TestConfigRoundtrip` für `alert_rules`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip` Go-Struct (`internal/model/trip.go`) | intern | Bekommt neues Feld `AlertRules`; JSON-Roundtrip muss `[]AlertRule` als leeres Array statt null persistieren |
| `Trip` Python-Dataclass (`src/app/trip.py`) | intern | Bekommt `alert_rules`-Feld; `__post_init__` bleibt unverändert |
| `Trip` TS-Interface (`frontend/src/lib/types.ts`) | intern | Bekommt optionales `alert_rules`-Feld; Konsumenten ignorieren es vorerst |
| `TripReportConfig.change_threshold_temp_c/wind_kmh/precip_mm` + `alert_on_changes` | intern | Quelle der Legacy-Migration; bleiben in `report_config` erhalten (Fallback) |
| `uuid.uuid4` | stdlib | Stable IDs für migrierte Rules; vergeben in der Migrationsfunktion server-seitig |
| `data_schema_backup.py` Hook | intern | Triggert automatisch beim ersten Edit auf `internal/model/trip.go` / `src/app/models.py` / `src/app/loader.py` → tar.gz in `.backups/` |

## Implementation Details

### 1. Typ-System (drei Sprachen, identische Field-Namen)

#### Go (`internal/model/trip.go`)

```go
type AlertRuleKind string
const (
    AlertRuleKindAbsolute AlertRuleKind = "absolute"
    AlertRuleKindDelta    AlertRuleKind = "delta"
)

type AlertSeverity string
const (
    AlertSeverityInfo     AlertSeverity = "info"
    AlertSeverityWarning  AlertSeverity = "warning"
    AlertSeverityCritical AlertSeverity = "critical"
)

type AlertMetric string
const (
    AlertMetricWindGust            AlertMetric = "wind_gust"
    AlertMetricPrecipitationSum    AlertMetric = "precipitation_sum"
    AlertMetricTemperatureMin      AlertMetric = "temperature_min"
    AlertMetricTemperatureMax      AlertMetric = "temperature_max"
    AlertMetricThunderLevel        AlertMetric = "thunder_level"
    AlertMetricSnowLine            AlertMetric = "snow_line"
    AlertMetricTemperatureChange   AlertMetric = "temperature_change"
    AlertMetricWindChange          AlertMetric = "wind_change"
    AlertMetricPrecipitationChange AlertMetric = "precipitation_change"
)

type AlertRule struct {
    ID        string        `json:"id"`
    Kind      AlertRuleKind `json:"kind"`
    Metric    AlertMetric   `json:"metric"`
    Threshold float64       `json:"threshold"`
    Unit      string        `json:"unit,omitempty"`
    Severity  AlertSeverity `json:"severity"`
    Enabled   bool          `json:"enabled"`
}

// Trip-Struct bekommt:
//   AlertRules []AlertRule `json:"alert_rules"`   // KEIN omitempty!
```

**KRITISCH:** `AlertRules` ohne `omitempty`-JSON-Tag. Grund: bei Round-Trip
durch Go würde `omitempty` ein leeres Array beim Save löschen, was nach
Re-Load `nil` statt `[]` ergibt — Drift.

#### Python (`src/app/models.py`)

```python
class AlertRuleKind(str, Enum):
    ABSOLUTE = "absolute"
    DELTA = "delta"

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertMetric(str, Enum):
    WIND_GUST = "wind_gust"
    PRECIPITATION_SUM = "precipitation_sum"
    TEMPERATURE_MIN = "temperature_min"
    TEMPERATURE_MAX = "temperature_max"
    THUNDER_LEVEL = "thunder_level"
    SNOW_LINE = "snow_line"
    TEMPERATURE_CHANGE = "temperature_change"
    WIND_CHANGE = "wind_change"
    PRECIPITATION_CHANGE = "precipitation_change"

@dataclass
class AlertRule:
    id: str
    kind: AlertRuleKind
    metric: AlertMetric
    threshold: float
    severity: AlertSeverity
    enabled: bool
    unit: str = ""
```

#### TypeScript (`frontend/src/lib/types.ts`)

```typescript
export type AlertRuleKind = 'absolute' | 'delta';
export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertMetric =
  | 'wind_gust' | 'precipitation_sum'
  | 'temperature_min' | 'temperature_max'
  | 'thunder_level' | 'snow_line'
  | 'temperature_change' | 'wind_change' | 'precipitation_change';

export interface AlertRule {
  id: string;
  kind: AlertRuleKind;
  metric: AlertMetric;
  threshold: number;
  unit?: string;
  severity: AlertSeverity;
  enabled: boolean;
}

// Trip-Interface bekommt:
//   alert_rules?: AlertRule[];
```

### 2. Load-Time-Migration in `src/app/loader.py`

```python
import uuid
from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity

# Mapping Legacy report_config -> AlertMetric + Unit
_LEGACY_DELTA_MAPPING: list[tuple[str, AlertMetric, str]] = [
    ("change_threshold_temp_c",   AlertMetric.TEMPERATURE_CHANGE,   "°C"),
    ("change_threshold_wind_kmh", AlertMetric.WIND_CHANGE,          "km/h"),
    ("change_threshold_precip_mm", AlertMetric.PRECIPITATION_CHANGE, "mm"),
]


def _migrate_legacy_alert_rules(data: dict) -> list[AlertRule]:
    """
    Generates AlertRule list from legacy report_config fields.

    - alert_on_changes=True  -> rules.enabled = True
    - alert_on_changes=False -> rules.enabled = False (NOT discarded — preserves
                                user-configured thresholds; user can re-enable in UI)
    - if data already has 'alert_rules' -> use as-is, no re-migration

    Legacy fields stay in report_config (Fallback for TripAlertService until
    it's switched over in a follow-up issue).
    """
    existing = data.get("alert_rules")
    if existing is not None:
        return [_alert_rule_from_dict(r) for r in existing]

    report_config = data.get("report_config", {}) or {}
    enabled = bool(report_config.get("alert_on_changes", False))

    rules: list[AlertRule] = []
    for legacy_field, metric, unit in _LEGACY_DELTA_MAPPING:
        threshold = report_config.get(legacy_field)
        if threshold is None:
            continue
        rules.append(AlertRule(
            id=str(uuid.uuid4()),
            kind=AlertRuleKind.DELTA,
            metric=metric,
            threshold=float(threshold),
            unit=unit,
            severity=AlertSeverity.WARNING,
            enabled=enabled,
        ))
    return rules


def _alert_rule_from_dict(d: dict) -> AlertRule:
    return AlertRule(
        id=d["id"],
        kind=AlertRuleKind(d["kind"]),
        metric=AlertMetric(d["metric"]),
        threshold=float(d["threshold"]),
        unit=d.get("unit", ""),
        severity=AlertSeverity(d["severity"]),
        enabled=bool(d["enabled"]),
    )
```

In `load_trip()`/`_parse_trip()` wird `trip.alert_rules =
_migrate_legacy_alert_rules(data)` aufgerufen. In `_trip_to_dict()` wird das
Feld als `"alert_rules": [{...}, ...]` serialisiert.

### 3. Backward-Kompatibilität

- Trips ohne `alert_rules` im JSON: Migration läuft, generiert Rules aus
  Legacy-Feldern → erste Save persistiert die neuen Rules.
- Trips mit `alert_rules` im JSON: Migration ist No-Op, lädt die existierende
  Liste.
- Legacy `report_config.change_threshold_*` und `alert_on_changes` bleiben
  unverändert im JSON — `TripAlertService` liest sie weiter, bis er in
  einem Folge-Issue auf `trip.alert_rules` umgestellt wird.

### 4. Go-Backend Read-Modify-Write

`UpdateTripHandler` in `internal/handler/trip.go` bekommt im
`tripUpdateRequest`-DTO:
```go
type tripUpdateRequest struct {
    // ... existing fields
    AlertRules *[]model.AlertRule `json:"alert_rules,omitempty"`
}
```

Bei `req.AlertRules != nil` ersetzt der Handler `trip.AlertRules`. Bei `nil`
bleibt das bestehende Feld erhalten (Read-Modify-Write Pattern wie bei
anderen Configs).

## Expected Behavior

- **Input (Load):** Trip-JSON aus `data/users/<user>/trips/<id>.json`
- **Output (Load):** Trip-Dataclass mit `alert_rules: List[AlertRule]` —
  entweder direkt aus JSON oder aus Legacy-`report_config`-Feldern migriert
- **Side effects:**
  - Erster Save eines bisher unmigriiertenTrips persistiert `alert_rules`
    als neues Feld im JSON
  - Legacy-Felder bleiben unverändert
  - Hook `data_schema_backup.py` schreibt automatisch `.backups/data-pre-rework-<ts>.tar.gz` vor dem ersten Edit dieser Spec

## Acceptance Criteria

- **AC-1:** Given die Dataclass-Definition existiert / When ein
  `AlertRule(id="abc", kind=AlertRuleKind.DELTA, metric=AlertMetric.WIND_CHANGE, threshold=20.0, unit="km/h", severity=AlertSeverity.WARNING, enabled=True)` instanziiert wird /
  Then enthält das Objekt alle sieben Felder mit korrekten Typen, und der
  `metric`-Wert ist String-vergleichbar mit `"wind_change"` (str-Enum).

- **AC-2:** Given das Trip-Dataclass-Modul / When ein Trip ohne explizites
  `alert_rules`-Argument konstruiert wird (`Trip(id="x", name="y", stages=[...])`) /
  Then ist `trip.alert_rules` eine leere Liste (kein None, kein Crash),
  und das Feld ist eine `list[AlertRule]`-Annotation.

- **AC-3:** Given ein Trip-JSON mit `report_config = {alert_on_changes: True,
  change_threshold_temp_c: 5.0, change_threshold_wind_kmh: 20.0,
  change_threshold_precip_mm: 10.0}` und ohne `alert_rules`-Feld /
  When `_migrate_legacy_alert_rules(data)` aufgerufen wird /
  Then liefert die Funktion drei `AlertRule`-Objekte zurück: jeweils mit
  `kind="delta"`, korrektem `metric`, korrektem `threshold`, korrekter
  `unit`, `severity=warning`, `enabled=True` und einer per `uuid.uuid4()`
  generierten `id` (UUID-Format, Länge 36).

- **AC-4:** Given derselbe Trip-JSON wie AC-3 aber mit `alert_on_changes: False` /
  When `_migrate_legacy_alert_rules(data)` aufgerufen wird /
  Then sind alle drei generierten Rules mit `enabled=False` markiert —
  die Schwellwert-Konfiguration bleibt erhalten, nur die Aktivität ist aus.
  Datenverlust-Prinzip aus BUG-DATALOSS-GR221 ist eingehalten.

- **AC-5:** Given ein Trip-JSON, das bereits ein `alert_rules`-Array enthält
  (z. B. nach erstem Save) /
  When `_migrate_legacy_alert_rules(data)` aufgerufen wird /
  Then liefert die Funktion die existierende Liste 1:1 zurück, ohne neu zu
  generieren (No-Op-Pfad) — keine doppelten Rules aus Legacy-Feldern.

- **AC-6:** Given ein Trip mit drei migrierten `alert_rules` /
  When der Trip durch `_trip_to_dict()` serialisiert und anschließend mit
  `load_trip()` zurückgeladen wird /
  Then sind alle drei Rules identisch (gleiche IDs, gleiche Felder), und die
  Legacy-Felder `report_config.change_threshold_*` sind im JSON unverändert
  vorhanden — Roundtrip ohne Datenverlust.

- **AC-7:** Given das Go-Struct `Trip` mit `AlertRules []AlertRule` ohne
  `omitempty`-Tag /
  When ein Trip mit `AlertRules: []AlertRule{}` durch `json.Marshal` läuft /
  Then enthält das JSON-Ergebnis `"alert_rules":[]` (leeres Array, nicht
  fehlend, nicht null). Verhindert Drift, wenn ein Trip ohne Rules durch die
  Go-API geht.

- **AC-8:** Given der TS-Interface-Export in `frontend/src/lib/types.ts` /
  When ein TypeScript-Modul `import type { AlertRule, AlertRuleKind, AlertSeverity, AlertMetric } from '$lib/types'` macht /
  Then sind alle vier Typen exportiert und das Trip-Interface hat
  `alert_rules?: AlertRule[]` als optionales Feld.

- **AC-9:** Given die 9 produktiv existierenden Trip-JSONs in
  `data/users/admin/trips/` und `data/users/default/trips/` /
  When jeder Trip mit `load_trip()` geladen, mit `_trip_to_dict()` serialisiert
  und das Ergebnis mit dem ursprünglichen JSON verglichen wird /
  Then sind alle Felder ausser dem neuen `alert_rules` (das jetzt hinzugefügt
  ist) byte-identisch zum Original — Migration ist additiv, keine Bestandsdaten
  werden überschrieben.

## Known Limitations

- **`TripAlertService` liest weiterhin `report_config`** — die neue
  `alert_rules`-Struktur ist persistiert, aber noch nicht von der Alert-Logik
  konsumiert. Folge-Issue baut `WeatherChangeDetectionService.from_alert_rules()`
  und stellt den Service um. Bis dahin sind Alerts datenmodell-mäßig korrekt,
  aber die ausgeführte Logik bleibt unverändert.
- **Wizard schreibt noch nicht auf `alert_rules`** — Step 4 Briefings und
  Legacy-Wizard pflegen weiter `report_config`. Folge-Issue stellt
  Save-Pipeline um. Bis dahin: Migration läuft beim Laden, neue Rules
  erscheinen nach erstem Save.
- **AlertsPreviewCard bleibt Skeleton** — Folge-Issue rendert `trip.alert_rules`
  als `AlertRow`-Liste.
- **LoC-Override auf 300:** Drei Sprachen + Migration + Tests gehen knapp
  über 250. Override gilt nur für diesen Workflow.

## Changelog

- 2026-05-14: Initial — Datenmodell + Migration only (Wizard/UI in Folge-Issue).

---
entity_id: issue_434_per_report_layouts
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [backend, data-model, per-report, channel-layouts, issue-434]
---

# Issue #434 — Per-Report-Layout-Overrides (Abend ≠ Morgen)

## Approval

- [ ] Approved

## Purpose

Erweitert das in #429 eingeführte `per_channel_layouts`-Datenmodell um eine zweite Überschreibungsebene, die es erlaubt, dass Morgen- und Abend-Briefing für denselben Kanal unterschiedliche Spalten-Konfigurationen tragen. Das neue Feld `channel_layouts_per_report` in `display_config` bildet eine verschachtelte Struktur `{report_type: {channel: [MetricConfig]}}`, die in der Prioritätskaskade von `get_metrics_for_channel()` als höchste Stufe ausgewertet wird — vor dem kanal-spezifischen Fallback (#429) und dem globalen Fallback.

## Source

- **Schicht:** Python-Backend + Frontend-Typen (kein Go-Backend-Umbau nötig)
- **Dateien (geändert):**
  - `src/app/models.py` — `UnifiedWeatherDisplayConfig` um `per_report_layouts`-Feld erweitern; `get_metrics_for_channel()` um erste Kaskadenebene ergänzen
  - `src/app/loader.py` — `_parse_display_config()` um `channel_layouts_per_report`-Zweig erweitern; `_trip_to_dict()` und die beiden weiteren Serialisierungsstellen um `per_channel_layouts` und `per_report_layouts` ergänzen
  - `src/formatters/trip_report.py` — Aufruf `get_metrics_for_report_type()` auf `get_metrics_for_channel("email", report_type)` umstellen (Bug-Fix)
  - `frontend/src/lib/types.ts` — neues Interface `ChannelLayoutsPerReport` + `DisplayConfig` additiv erweitern

> **Schicht-Hinweis:** Primär Python-Backend (`src/app/`). `internal/model/trip.go` bleibt **unverändert** — `Trip.DisplayConfig` ist `map[string]interface{}` und reicht `channel_layouts_per_report` verbatim durch.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig` (`src/app/models.py`) | Python-Klasse (vorhanden, wird erweitert) | Empfängt neues Feld `per_report_layouts`; `get_metrics_for_channel()` erhält erste Kaskadenebene |
| `MetricConfig` (`src/app/models.py`) | Python-Dataclass (vorhanden, unverändert) | Einzelne Metrik-Konfiguration; wird in `per_report_layouts`-Listen verwendet |
| `_parse_display_config` (`src/app/loader.py`) | Python-Funktion (vorhanden, wird erweitert) | Parst `channel_layouts_per_report`-Zweig aus JSON |
| `_trip_to_dict` (`src/app/loader.py`) | Python-Funktion (vorhanden, wird gefixt) | Schreibt `per_channel_layouts` und `per_report_layouts` zurück in den Dict (latenter Serialisierungs-Bug seit #429) |
| `get_metrics_for_channel` (`src/app/models.py`) | Python-Methode (vorhanden, #429) | Erhält neue erste Kaskadenebene: per_report schlägt per_channel schlägt global |
| `trip_report.py:73` (`src/formatters/trip_report.py`) | Python-Aufrufstelle (vorhanden, wird gefixt) | Bug: ruft bisher `get_metrics_for_report_type()` statt `get_metrics_for_channel("email", ...)` auf |
| `DisplayConfig` / `ChannelLayouts` (`frontend/src/lib/types.ts`) | TypeScript-Interfaces (vorhanden, werden erweitert) | `DisplayConfig` erhält `channel_layouts_per_report?: ChannelLayoutsPerReport`; neues Interface hinzufügen |
| Issue #429 per_channel_layouts | Upstream-Feature (live) | Zweite Kaskadenebene, die #434 ergänzt; Fallback-Logik von #429 bleibt unverändert |

## Scope

**Backend-only.** Dieser PR liefert Datenmodell, Parsing, Serialisierung, Email-Renderer-Fix und TypeScript-Typen. Ein UI-Toggle (Wizard-Tab oder Trip-Detail-Karte) kommt als separates Folge-Issue, analog zum Muster #429 (Datenmodell) → #430/#431 (UI).

Nicht in Scope:
- Frontend-UI für per-report-Overrides (kein Wizard-Step, kein Trip-Detail-Tab)
- SMS/Telegram/Signal-Renderer analog zu Email — nur Email-Renderer-Bug wird behoben; andere Renderer nutzen `render_for_channel` (bereits korrekt nach #429)
- Go-Backend-Änderungen — `map[string]interface{}` reicht alles additiv durch

## Implementation Details

### 1. `UnifiedWeatherDisplayConfig` — neues Feld + Kaskadenebene (`src/app/models.py`)

Neues Feld neben `per_channel_layouts`:

```python
@dataclass
class UnifiedWeatherDisplayConfig:
    # ... bestehende Felder unverändert ...
    per_channel_layouts: dict[str, list[MetricConfig]] | None = None  # #429, vorhanden
    per_report_layouts: dict[str, dict[str, list[MetricConfig]]] | None = None  # #434, NEU
    # Struktur: { "morning": { "email": [...] }, "evening": { "email": [...] } }
    # None = kein per-report-Override gespeichert → nächste Kaskadenebene aktiv
```

`get_metrics_for_channel()` um erste Kaskadenebene ergänzen (vor dem bestehenden `per_channel_layouts`-Check):

```python
def get_metrics_for_channel(self, channel: str, report_type: str) -> list[MetricConfig]:
    # Ebene 1 (NEU #434): per_report_layouts[report_type][channel]
    if (
        self.per_report_layouts is not None
        and report_type in self.per_report_layouts
        and channel in self.per_report_layouts[report_type]
    ):
        report_channel_metrics = self.per_report_layouts[report_type][channel]
        # Leere Liste: expliziter User-Wunsch → kein Fallback
        if len(report_channel_metrics) == 0:
            return []
        # Nicht-leere Liste: report_type-Filter anwenden (analog #429)
        return self._filter_by_report_type(report_channel_metrics, report_type)

    # Ebene 2 (#429): per_channel_layouts[channel]
    if (
        self.per_channel_layouts is not None
        and channel in self.per_channel_layouts
    ):
        channel_metrics = self.per_channel_layouts[channel]
        if len(channel_metrics) == 0:
            return []
        return self._filter_by_report_type(channel_metrics, report_type)

    # Ebene 3: globaler Fallback
    return self.get_metrics_for_report_type(report_type)
```

Die `_filter_by_report_type()`-Hilfsmethode (privat) extrahiert die bestehende Flag-Filterlogik aus der #429-Implementierung, um Duplikation zu vermeiden.

### 2. `_parse_display_config` — `channel_layouts_per_report`-Zweig (`src/app/loader.py`)

Nach dem bestehenden `channel_layouts`-Parsing-Block (aus #429), vor dem `return UnifiedWeatherDisplayConfig(...)`:

```python
# Issue #434: per-report-Overrides laden (optional, backward-compat)
per_report_layouts: dict[str, dict[str, list[MetricConfig]]] | None = None
raw_per_report = data.get("channel_layouts_per_report")
if raw_per_report and isinstance(raw_per_report, dict):
    per_report_layouts = {}
    for report_type, channels_dict in raw_per_report.items():
        if not isinstance(channels_dict, dict):
            continue
        per_report_layouts[report_type] = {}
        for ch, ch_metrics in channels_dict.items():
            if not isinstance(ch_metrics, list):
                continue
            per_report_layouts[report_type][ch] = [
                MetricConfig(
                    metric_id=mc_data["metric_id"],
                    bucket=mc_data.get("bucket", "primary"),
                    order=mc_data.get("order", 0),
                    enabled=mc_data.get("enabled", True),
                    aggregations=mc_data.get("aggregations", ["min", "max"]),
                    morning_enabled=mc_data.get("morning_enabled"),
                    evening_enabled=mc_data.get("evening_enabled"),
                    use_friendly_format=mc_data.get("use_friendly_format", True),
                    alert_enabled=mc_data.get("alert_enabled", False),
                    alert_threshold=mc_data.get("alert_threshold"),
                    horizons=mc_data.get("horizons"),
                )
                for mc_data in ch_metrics
            ]
    if not per_report_layouts:
        per_report_layouts = None
```

Im `UnifiedWeatherDisplayConfig(...)`-Konstruktor-Aufruf:
```python
return UnifiedWeatherDisplayConfig(
    # ... bestehende Argumente unverändert ...
    per_channel_layouts=per_channel_layouts,   # #429
    per_report_layouts=per_report_layouts,      # #434, NEU
)
```

### 3. Serialisierungs-Fix (`src/app/loader.py`)

Latenter Bug aus #429: `_trip_to_dict()` schreibt `per_channel_layouts` nicht zurück. Gleiches gilt für die zwei weiteren Serialisierungsstellen (locations, subscriptions). Alle drei werden behoben:

```python
# in _trip_to_dict() und analogen Stellen:
if dc.per_channel_layouts is not None:
    display_dict["channel_layouts"] = {
        ch: [_metric_config_to_dict(mc) for mc in metrics]
        for ch, metrics in dc.per_channel_layouts.items()
    }
if dc.per_report_layouts is not None:
    display_dict["channel_layouts_per_report"] = {
        report_type: {
            ch: [_metric_config_to_dict(mc) for mc in metrics]
            for ch, metrics in channels_dict.items()
        }
        for report_type, channels_dict in dc.per_report_layouts.items()
    }
```

`_metric_config_to_dict()` ist eine neue private Hilfsfunktion, die ein `MetricConfig`-Objekt in einen serialisierbaren Dict umwandelt (vermeidet Duplikation über alle 3 Serialisierungsstellen).

### 4. Email-Renderer-Fix (`src/formatters/trip_report.py`)

Bug-Fix an Zeile 73 (eine Zeile):

```python
# Vorher (Bug):
metrics = display_config.get_metrics_for_report_type(report_type)

# Nachher (Fix):
metrics = display_config.get_metrics_for_channel("email", report_type)
```

Ohne diesen Fix haben weder #429-Overrides noch #434-Overrides Wirkung für den Email-Kanal.

### 5. Frontend-Typen (`frontend/src/lib/types.ts`)

Neues Interface vor `DisplayConfig`:

```typescript
// Issue #434 — per-report-Overrides (snake_case auf der Wire)
export interface ChannelLayoutsPerReport {
  morning?: ChannelLayouts;  // ChannelLayouts = Issue #429
  evening?: ChannelLayouts;
}
```

`DisplayConfig` additiv erweitern:

```typescript
export interface DisplayConfig {
  preset_name?: string;
  metrics?: WeatherConfigMetric[];
  channel_layouts?: ChannelLayouts;              // Issue #429
  channel_layouts_per_report?: ChannelLayoutsPerReport;  // Issue #434, NEU
}
```

## Expected Behavior

- **Input:** `display_config`-Dict aus der Datenbank, mit oder ohne `channel_layouts_per_report`-Schlüssel
- **Output:** `UnifiedWeatherDisplayConfig`-Instanz mit optional befülltem `per_report_layouts`; `get_metrics_for_channel()` wertet die dreistufige Kaskade aus
- **Side effects:** Serialisierungsstellen schreiben `per_channel_layouts` und `per_report_layouts` vollständig zurück (Roundtrip-Integrität)

## Acceptance Criteria

**AC-1:** Given ein Trip-JSON mit `channel_layouts_per_report: { "morning": { "email": [...] }, "evening": { "email": [...] } }` /
When `_parse_display_config()` aufgerufen wird /
Then ist `dc.per_report_layouts["morning"]["email"]` eine Liste von `MetricConfig`-Objekten mit den korrekten Feldern, und `dc.per_report_layouts["evening"]["email"]` enthält die Abend-spezifische Liste.

**AC-2:** Given ein Trip-JSON ohne `channel_layouts_per_report`-Schlüssel (älterer Trip) /
When `_parse_display_config()` aufgerufen wird /
Then ist `dc.per_report_layouts` None und `get_metrics_for_channel("email", "evening")` liefert dasselbe Ergebnis wie vor diesem PR — kein Regressions-Verhalten.

**AC-3:** Given `dc.per_report_layouts["morning"]["email"]` enthält eine nicht-leere Liste, und `dc.per_channel_layouts["email"]` enthält eine abweichende Liste /
When `get_metrics_for_channel("email", "morning")` aufgerufen wird /
Then wird ausschließlich die `per_report_layouts`-Liste zurückgegeben (gefiltert nach `morning_enabled`/`enabled`) — die `per_channel_layouts`-Liste wird ignoriert.

**AC-4:** Given `dc.per_report_layouts` ist None, aber `dc.per_channel_layouts["email"]` enthält eine Liste /
When `get_metrics_for_channel("email", "evening")` aufgerufen wird /
Then wird die `per_channel_layouts["email"]`-Liste zurückgegeben (Fallback auf #429-Ebene), nicht die globale Liste.

**AC-5:** Given `dc.per_report_layouts["evening"]["email"]` ist eine explizit leere Liste /
When `get_metrics_for_channel("email", "evening")` aufgerufen wird /
Then wird eine leere Liste zurückgegeben — kein Fallback auf `per_channel_layouts` oder die globale Liste (leere Liste ist expliziter User-Wunsch).

**AC-6:** Given ein Trip mit `per_channel_layouts` und `per_report_layouts` wird durch `_trip_to_dict()` serialisiert /
When das resultierende Dict durch `_parse_display_config()` wieder geparst wird /
Then ist der wiederhergestellte `UnifiedWeatherDisplayConfig` strukturell identisch zum Original — vollständiger Roundtrip ohne Datenverlust für beide Felder.

**AC-7:** Given `trip_report.py` wird aufgerufen und der Trip hat `per_report_layouts["evening"]["email"]` gesetzt /
When der Email-Renderer für den Abend-Report ausgeführt wird /
Then verwendet der Renderer die `per_report_layouts`-Metriken-Liste statt der globalen Liste — der Email-Renderer-Bug ist behoben.

## Out of Scope

- Frontend-UI: Kein Wizard-Step, keine Trip-Detail-Karte für per-report-Overrides — kommt als Folge-Issue
- SMS/Telegram/Signal-Renderer: Nur der Email-Renderer-Bug wird behoben; andere Renderer nutzen bereits `render_for_channel` korrekt (seit #429)
- Go-Backend: `internal/model/trip.go` bleibt unverändert — `map[string]interface{}` reicht alles additiv durch

## Known Limitations

- Analog zu #429: Explizit leere Liste in `per_report_layouts[report_type][channel]` liefert leere Ausgabe ohne Fallback. Das ist gewollt, kann aber zu leeren Briefings führen, wenn das UI irrtümlich eine leere Liste schreibt.
- Die Serialisierungs-Fix-Stellen (Locations, Subscriptions) müssen manuell identifiziert und gefixt werden — ohne diesen Fix würden `per_channel_layouts`- und `per_report_layouts`-Werte bei der nächsten Speicheroperation verloren gehen.
- Fehlende Pflichtfelder im JSON (z.B. `metric_id` fehlt) lösen wie bei #429 einen `KeyError` aus — fail-fast, keine Silent-Failures.

## Changelog

- 2026-05-29: Initial spec für Issue #434 — Per-Report-Layout-Overrides (Abend ≠ Morgen).

---
entity_id: issue_429_channel_layouts
type: module
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [backend, frontend, data-model, channel-layouts, issue-429, epic-428]
---

# Issue #429 — Datenmodell „Layout pro Kanal" + Backward-Compat

## Approval

- [ ] Approved

## Purpose

Erweitert `UnifiedWeatherDisplayConfig` um vier kanal-spezifische Metriken-Listen (`email`, `telegram`, `signal`, `sms`) unter dem neuen Feld `per_channel_layouts`, damit spätere Wizard- und Trip-Detail-Screens (Issue #431) pro Kanal eigene Spalten-Reihenfolgen und Bucket-Zuordnungen speichern können. Bestehende Trips, die nur die globale `metrics`-Liste kennen, werden durch einen Loader-Fallback bit-identisch weitergerendert — kein Datenverlust, keine erzwungene Migration.

## Source

- **Schicht:** Python-Backend + Frontend-Typen (kein Go-Backend-Umbau nötig)
- **Dateien (geändert):**
  - `src/app/models.py` — `UnifiedWeatherDisplayConfig` um `per_channel_layouts`-Feld + `get_metrics_for_channel()`-Methode erweitern
  - `src/app/loader.py` — `_parse_display_config()` um `channel_layouts`-Zweig + Backward-Compat-Logik erweitern
  - `src/output/renderers/channel_layout.py` — `render_for_channel()` auf `get_metrics_for_channel()` umstellen
  - `frontend/src/lib/types.ts` — `DisplayConfig`-Interface um `channel_layouts?: ChannelLayouts` erweitern + neues `ChannelLayouts`-Interface hinzufügen

> **Schicht-Hinweis:** Primär Python-Backend (`src/app/`). `internal/model/trip.go` bleibt **unverändert** — `Trip.DisplayConfig` ist bereits `map[string]interface{}` und reicht das neue `channel_layouts`-Objekt verbatim durch.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig` (`src/app/models.py:478`) | Python-Klasse (vorhanden, wird erweitert) | Empfängt neues Feld `per_channel_layouts` + neue Methode `get_metrics_for_channel()` |
| `MetricConfig` (`src/app/models.py:457`) | Python-Dataclass (vorhanden, unverändert) | Einzelne Metrik-Konfiguration; wird in per_channel_layouts-Listen verwendet |
| `_parse_display_config` (`src/app/loader.py:311`) | Python-Funktion (vorhanden, wird erweitert) | Parst `channel_layouts`-Zweig aus JSON; Backward-Compat-Logik |
| `render_for_channel` (`src/output/renderers/channel_layout.py:52`) | Python-Funktion (vorhanden, wird angepasst) | Erhält Metriken-Liste jetzt via `get_metrics_for_channel()` statt `get_metrics_for_report_type()` |
| `CHANNEL_LIMITS` (`src/output/renderers/channel_layout.py:20`) | Python-Dict (vorhanden, unverändert) | Spalten-Limits pro Kanal bleiben unverändert |
| `Trip.DisplayConfig` (`internal/model/trip.go:75`) | Go-Map (`map[string]interface{}`) | Reicht `channel_layouts`-Objekt additiv durch; kein Go-Umbau |
| `DisplayConfig` / `WeatherConfigMetric` (`frontend/src/lib/types.ts:166,127`) | TypeScript-Interfaces (vorhanden, werden erweitert) | `DisplayConfig` erhält `channel_layouts?: ChannelLayouts`; neues `ChannelLayouts`-Interface |

## Scope

**Nur Read-Pfad + Typen.** Dieser PR macht den Loader, das Datenmodell und den Renderer fit für kanal-spezifische Listen. Der schreibende Pfad (Wizard-Editor, Trip-Detail-Tab) kommt in Issue #431 (PR 3).

Nicht in Scope:
- Schreibender Pfad im Frontend (Wizard Step 4 Layout-Editor, Trip-Detail-Tab) — Issue #431
- UI für Kanal-Layout-Auswahl — Issue #431
- Stepper 4→5 Umbau — Issue #430 (PR 2)
- 4-Optionen-Format-Dropdown — Issue #435
- Per-Report-Overrides (Abend ≠ Morgen für denselben Kanal) — Issue #434
- Go-Backend-Änderungen — `Trip.DisplayConfig map[string]interface{}` reicht alles additiv durch

## Implementation Details

### 1. `UnifiedWeatherDisplayConfig` — neues Feld + Methode (`src/app/models.py`)

Neues Feld als optionaler Dict:

```python
@dataclass
class UnifiedWeatherDisplayConfig:
    # ... bestehende Felder unverändert ...
    per_channel_layouts: dict[str, list[MetricConfig]] | None = None
    # None = kein Kanal-Layout gespeichert → globale Fallback-Liste aktiv
```

Neue Methode direkt nach `get_metrics_for_report_type()`:

```python
def get_metrics_for_channel(self, channel: str, report_type: str) -> list[MetricConfig]:
    """Liefert die Metriken-Liste für einen Kanal.

    Priorität:
    1. Wenn per_channel_layouts nicht None ist UND channel im Dict ist
       UND die Liste nicht leer ist → kanal-spezifische Liste,
       gefiltert nach enabled + morning_enabled/evening_enabled (wie
       get_metrics_for_report_type).
    2. Sonst: Fallback auf get_metrics_for_report_type(report_type).

    Besonderheit leere Liste: Wenn per_channel_layouts[channel] == []
    (User hat alle Metriken deaktiviert), wird KEINE Fallback-Liste
    zurückgegeben — leere Liste ist gewollt.
    """
    if (
        self.per_channel_layouts is not None
        and channel in self.per_channel_layouts
    ):
        channel_metrics = self.per_channel_layouts[channel]
        # Leere Liste: User wollte diesen Kanal leer → direkt zurück
        if len(channel_metrics) == 0:
            return []
        # Nicht-leere Liste: report_type-Filter anwenden
        result = []
        for mc in channel_metrics:
            if report_type == "morning":
                if mc.morning_enabled is True:
                    result.append(mc)
                elif mc.morning_enabled is False:
                    pass
                elif mc.enabled:
                    result.append(mc)
            elif report_type == "evening":
                if mc.evening_enabled is True:
                    result.append(mc)
                elif mc.evening_enabled is False:
                    pass
                elif mc.enabled:
                    result.append(mc)
            else:
                if mc.enabled:
                    result.append(mc)
        return result
    # Fallback: globale Liste
    return self.get_metrics_for_report_type(report_type)
```

### 2. `_parse_display_config` — `channel_layouts`-Zweig (`src/app/loader.py`)

Am Ende von `_parse_display_config()`, nach dem Parsen der globalen `metrics`-Liste und vor dem `return UnifiedWeatherDisplayConfig(...)`:

```python
# Issue #429: kanal-spezifische Layouts laden (optional, backward-compat)
per_channel_layouts: dict[str, list[MetricConfig]] | None = None
raw_channel_layouts = data.get("channel_layouts")
if raw_channel_layouts and isinstance(raw_channel_layouts, dict):
    # Mindestens ein Kanal muss vorhanden sein
    if any(raw_channel_layouts.values()):
        per_channel_layouts = {}
        for ch, ch_metrics in raw_channel_layouts.items():
            if not isinstance(ch_metrics, list):
                continue
            ch_parsed = []
            for mc_data in ch_metrics:
                mid = mc_data["metric_id"]
                bucket = mc_data.get("bucket", "primary")
                order = mc_data.get("order", 0)
                ch_parsed.append(MetricConfig(
                    metric_id=mid,
                    enabled=mc_data.get("enabled", True),
                    aggregations=mc_data.get("aggregations", ["min", "max"]),
                    morning_enabled=mc_data.get("morning_enabled"),
                    evening_enabled=mc_data.get("evening_enabled"),
                    use_friendly_format=mc_data.get("use_friendly_format", True),
                    alert_enabled=mc_data.get("alert_enabled", False),
                    alert_threshold=mc_data.get("alert_threshold"),
                    horizons=mc_data.get("horizons"),
                    bucket=bucket,
                    order=order,
                ))
            per_channel_layouts[ch] = ch_parsed
```

Im `UnifiedWeatherDisplayConfig(...)`-Konstruktor-Aufruf:
```python
return UnifiedWeatherDisplayConfig(
    # ... bestehende Argumente unverändert ...
    per_channel_layouts=per_channel_layouts,
)
```

**Backward-Compat-Invariante:**
- `data` ohne `channel_layouts`-Key → `per_channel_layouts = None` → `get_metrics_for_channel` fällt auf globale Liste zurück
- `channel_layouts` vorhanden, aber alle Kanal-Listen leer → Bedingung `any(raw_channel_layouts.values())` ist False → `per_channel_layouts = None` → Fallback wie oben

### 3. `render_for_channel` — Aufruf-Stelle (`src/output/renderers/channel_layout.py`)

Eine Zeile ändern (Zeile 59):

```python
# Vorher:
enabled = dc.get_metrics_for_report_type(report_type)

# Nachher:
enabled = dc.get_metrics_for_channel(channel, report_type)
```

Die restliche Logik (primary/secondary-Sortierung, CHANNEL_LIMITS, overflow) bleibt byte-gleich.

### 4. Frontend-Typen (`frontend/src/lib/types.ts`)

Neues Interface vor `DisplayConfig`:

```typescript
// Issue #429 — kanal-spezifische Layout-Listen (snake_case auf der Wire)
export interface ChannelLayouts {
  email?:    WeatherConfigMetric[];
  telegram?: WeatherConfigMetric[];
  signal?:   WeatherConfigMetric[];
  sms?:      WeatherConfigMetric[];
}
```

`DisplayConfig` additiv erweitern:

```typescript
export interface DisplayConfig {
  preset_name?: string;
  metrics?: WeatherConfigMetric[];
  channel_layouts?: ChannelLayouts;  // Issue #429
}
```

## Expected Behavior

- **Input:** `display_config`-Dict aus der Datenbank, mit oder ohne `channel_layouts`-Schlüssel
- **Output:** `UnifiedWeatherDisplayConfig`-Instanz mit optional befülltem `per_channel_layouts`; `render_for_channel()` liefert kanal-spezifische `ChannelLayout`-Instanz
- **Side effects:** Keine (reiner Read-Pfad; schreibender Pfad bleibt unverändert bei globaler `metrics`-Liste)

## Acceptance Criteria

**AC-1:** Given ein Trip-JSON mit einem `channel_layouts`-Objekt, das mindestens einen Kanal mit nicht-leerer Metrik-Liste enthält /
When `_parse_display_config()` aufgerufen wird /
Then ist `dc.per_channel_layouts` nicht None und enthält für jeden angegebenen Kanal eine Liste von `MetricConfig`-Objekten mit den korrekten Feldern (metric_id, bucket, order, enabled).

**AC-2:** Given ein Trip-JSON ohne `channel_layouts`-Schlüssel (älterer Trip) /
When `_parse_display_config()` aufgerufen wird /
Then ist `dc.per_channel_layouts` None und `get_metrics_for_channel("email", "evening")` liefert dasselbe Ergebnis wie `get_metrics_for_report_type("evening")`.

**AC-3:** Given `dc.per_channel_layouts` enthält einen Eintrag für `"email"` mit N nicht-leeren Metriken /
When `dc.get_metrics_for_channel("email", "evening")` aufgerufen wird /
Then werden genau die Metriken aus dem Email-Layout zurückgegeben, gefiltert nach `enabled` und `evening_enabled`-Flag — nicht aus der globalen `metrics`-Liste.

**AC-4:** Given `dc.per_channel_layouts` enthält keinen Eintrag für `"signal"` (nur `"email"` und `"telegram"` gespeichert) /
When `dc.get_metrics_for_channel("signal", "morning")` aufgerufen wird /
Then wird auf die globale `get_metrics_for_report_type("morning")`-Liste zurückgefallen und das Ergebnis ist identisch zum Verhalten ohne `per_channel_layouts`.

**AC-5:** Given `render_for_channel("telegram", dc, "evening")` wird aufgerufen und `dc.per_channel_layouts["telegram"]` enthält 10 Metriken (alle primary) /
When `render_for_channel` ausgeführt wird /
Then greift das `CHANNEL_LIMITS["telegram"]["max_table_cols"]=8`-Limit: maximal 7 Metriken in `table_columns` (Slot 0 = Zeit), der Rest in `detail_metrics`.

**AC-6:** Given ein alter Trip ohne `channel_layouts` wird durch die komplette Render-Pipeline geschickt (Loader → `render_for_channel` → `ChannelLayout`) /
When das Ergebnis mit dem Ergebnis vor dem PR verglichen wird /
Then sind `table_columns`, `detail_metrics` und `demoted_count` bit-identisch — kein Unterschied im gerenderten Output für bestehende Trips.

**AC-7:** Given `dc.per_channel_layouts["sms"]` ist eine leere Liste (User hat alle SMS-Metriken deaktiviert) /
When `dc.get_metrics_for_channel("sms", "evening")` aufgerufen wird /
Then wird eine leere Liste zurückgegeben — kein Fallback auf die globale Liste (leere Liste ist expliziter User-Wunsch).

**AC-8:** Given das TypeScript-Interface `ChannelLayouts` ist in `types.ts` definiert und `DisplayConfig.channel_layouts` ist optional typisiert /
When TypeScript-Code `const cl: ChannelLayouts = trip.display_config?.channel_layouts ?? {}` schreibt /
Then kompiliert der Code ohne Typfehler und alle vier Kanal-Felder (`email`, `telegram`, `signal`, `sms`) sind als `WeatherConfigMetric[]` korrekt typisiert.

## Out of Scope

- Schreibender Pfad im Frontend: Wizard Step 4 Layout-Editor und Trip-Detail-Tab schreiben weiterhin nur `display_config.metrics` (global) — Issue #431
- UI für Kanal-Auswahl im Editor — Issue #431
- Stepper 4→5 Umbau — Issue #430 (PR 2)
- 4-Optionen-Format-Dropdown — Issue #435
- Go-Backend-Änderungen an `internal/model/trip.go` — `map[string]interface{}` reicht alles additiv durch
- Per-Report-Overrides (Abend ≠ Morgen pro Kanal) — Issue #434

## Known Limitations

- Wenn `per_channel_layouts[channel]` explizit als leere Liste gespeichert ist, liefert `get_metrics_for_channel` eine leere Liste ohne Fallback — das ist gewollt (expliziter User-Wunsch), kann aber zu leeren Briefings für diesen Kanal führen, wenn der Wizard-Editor irrtümlich eine leere Liste schreibt.
- Per-Report-Overrides innerhalb eines Kanal-Layouts (Abend ≠ Morgen für denselben Kanal) werden durch das bestehende `morning_enabled`/`evening_enabled`-Flag-System auf `MetricConfig` abgebildet; eine getrennte `channel_layouts.email_morning` / `channel_layouts.email_evening`-Struktur ist erst in Issue #434 vorgesehen.
- Der Loader validiert `channel`-Schlüssel nicht gegen `CHANNEL_LIMITS`; unbekannte Kanal-Namen (z.B. `"whatsapp"`) werden stillschweigend in `per_channel_layouts` aufgenommen, aber von keinem Render-Pfad gelesen. `render_for_channel` wird im aktuellen Codebase nur mit den 4 bekannten Kanal-Namen aufgerufen (`narrow.py:168` ruft `"signal"`/`"telegram"`); ein Aufruf mit unbekanntem Kanal würde an `CHANNEL_LIMITS[channel]` einen `KeyError` werfen. Eine defensive `.get()`-Variante ist bewusst nicht implementiert — fail-fast verhindert stille Fehlkonfiguration in zukünftigen Aufrufern.
- Fehlende Pflichtfelder im JSON (z.B. `metric_id` fehlt in einem `channel_layouts`-Eintrag) lösen einen `KeyError` aus — identisches Verhalten wie der bestehende globale `metrics`-Pfad. Beide Pfade vertrauen auf wohlgeformte Daten aus dem Go-Store. Defensive `.get()`-Guards sind außerhalb von #429-Scope und gehören in ein eigenes Hardening-Ticket.

## Changelog

- 2026-05-28: Initial spec für Issue #429 (PR 1/4 von Epic #428).
- 2026-05-28: Known-Limitations präzisiert (Adversary-Findings F001 + F002 — beide LOW, no-action, dokumentarisch geklärt).

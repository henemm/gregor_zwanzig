---
entity_id: issue_435_metric_format_modes
type: module
created: 2026-05-28
updated: 2026-05-28
status: draft
version: "1.0"
tags: [output, weather, metrics, frontend, backend, migration]
---

<!-- Issue #435 — Backend-Modell für 4 Format-Optionen (Roh/Skala/Vereinfacht/Symbol) -->

# Issue 435 — Metrik-Format-Modi (Roh/Skala/Vereinfacht/Symbol)

## Approval

- [x] Approved

## Purpose

`MetricConfig` kennt heute nur `use_friendly_format: bool`, das alle
nicht-numerischen Darstellungen unter einem einzigen Flag zusammenfasst — obwohl
`wind_direction` eine Kompass-Skala rendert, `cloud_total` ein Emoji und
`visibility` einen Klartext-Kurztext. Dieses Modul erweitert das Backend-Modell
und den Renderer um einen expliziten `format_mode`-String pro Metrik (Werte:
`raw / scale / simplified / symbol`), sodass das Frontend-Dropdown aus
Wizard-Step 3 und dem WeatherConfigDialog nur die im Katalog erlaubten Modi pro
Metrik anbieten kann und der gewählte Modus verlustfrei persistiert und gerendert
wird.

## Source

> **PFLICHT — Schicht-Hinweis:** Affected Files MUSS die richtige Schicht treffen:
> - **Frontend / User-UI** → `frontend/src/...` (SvelteKit, produktive Oberfläche auf gregor20.henemm.com)
> - **Go-API** → `api/`, `internal/`, `cmd/` (Production-API auf Port 8090)
> - **Python-Backend** → `src/services/`, `src/app/`, `src/providers/` (FastAPI Core über `api.main:app`)
>
> Im Zweifel vor dem Spec-Schreiben grep auf den betroffenen Symbol-Namen — Server-Code (Go vs. Python) und UI-Code (SvelteKit vs. Server-Templates) sind getrennt. Es gab in der Vergangenheit Doppelarbeit, weil Specs Helper-Funktionen in der falschen Schicht verortet haben (Issue #129).

**Python-Backend (~235 LoC)**

- `src/app/metric_catalog.py` — `MetricDefinition`: `format_modes` + `default_format_mode` ergänzen; alle 25 Einträge füllen (~45 LoC)
- `src/app/models.py` — `MetricConfig`: `format_mode: Optional[str] = None` hinzufügen; `use_friendly_format` bleibt als `@deprecated` (~20 LoC)
- `src/app/loader.py` — `_resolve_format_mode()`-Adapter; Schreib-Pfade schreiben beide Felder (~30 LoC)
- `src/output/renderers/email/helpers.py` — `fmt_val()` auf `mode: str` umstellen; `build_format_modes()` statt `build_friendly_keys()`; neuer Simplified-Kürzel-Helfer (~60 LoC)
- `src/formatters/trip_report.py` — `_build_friendly_keys()` durch Import aus `helpers.py` ersetzen (Vor-Commit); CAPE-Highlight und Wind-Direction-Merge auf `format_mode` umstellen (~30 LoC)
- `src/formatters/compact_summary.py` — Adjektiv-Pfade an `format_mode` koppeln, Briefing-Texte bleiben unberührt (~20 LoC)
- `src/formatters/sms_trip.py` — Token-Pfad auf `format_mode in {"symbol","scale"}` umstellen (~10 LoC)
- `src/services/weather_metrics.py` — `format_wind_strength(kmh)` und `format_precip_intensity(mm)` als neue Single-Source-Helfer extrahiert (~20 LoC)
- `src/output/tokens/builder.py` + `src/output/tokens/dto.py` — Token-Builder-Adapter (~10 LoC)

**Go/Python-API (~30 LoC)**

- `api/routers/config.py` — `/api/metrics`-Endpoint liefert `format_modes` und `default_format_mode` pro Eintrag mit aus (~30 LoC)

**Frontend (~70 LoC)**

- `frontend/src/lib/types.ts` — `MetricEntry` um `format_modes: string[]` und `default_format_mode: string` erweitern; `WeatherConfigMetric` um `format_mode?: string` (~8 LoC)
- `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` — Dropdown-Options aus `m.format_modes` filtern; `format_mode` persistieren; `use_friendly_format` parallel weiterschreiben (~20 LoC)
- `frontend/src/lib/components/WeatherConfigDialog.svelte` — 2-Wege-Segmented-Control durch N-Optionen-Dropdown ersetzen (~15 LoC)
- `frontend/src/lib/components/WeatherMetricsTab.svelte`, `metricsEditor.ts`, `Step4Layout.svelte`, `SavePresetDialog.svelte` — analog auf `format_mode` umstellen (~27 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricDefinition` (`src/app/metric_catalog.py`) | Python-Backend | Single Source of Truth für erlaubte Modi pro Metrik; neue Felder `format_modes: tuple[str, ...]` und `default_format_mode: str` |
| `MetricConfig` (`src/app/models.py`) | Python-Backend | Pydantic-Persistenz-Modell; neues Feld `format_mode: Optional[str]`; `use_friendly_format` bleibt `@deprecated` |
| `fmt_val()` (`src/output/renderers/email/helpers.py`) | Python-Backend | Zentraler Renderer; Verzweigung wechselt von `bool` zu `mode: str` |
| `degrees_to_compass()` (`src/services/weather_metrics.py`) | Python-Backend | Kompass-Skala für `wind_direction`; bestehende Implementierung, bleibt als Baustein |
| `get_weather_emoji()` (`src/services/weather_metrics.py`) | Python-Backend | Symbol-Quelle für `sunshine`; bestehende Implementierung, bleibt als Baustein |
| `compact_summary._format_wind` / `._format_precipitation` (`src/formatters/compact_summary.py`) | Python-Backend | Quelle der Simplified-Adjektive; werden nach `weather_metrics.py` extrahiert (Single Source) |
| `_build_friendly_keys` (`src/formatters/trip_report.py:640`) | Python-Backend | Duplikat von `helpers.py:505`; wird im Vor-Commit durch Import ersetzt |
| `data_schema_backup.py` Hook | Python-Backend | Pre-Snapshot bei jedem Edit auf `src/app/models.py` (CLAUDE.md-Pflicht, Daten-Schema-Reworks) |
| `/api/metrics` (`api/routers/config.py`) | Go/Python-API | Liefert pro Metrik `format_modes[]` und `default_format_mode`; Frontend liest daraus die erlaubten Optionen |
| `Step3Weather.svelte` (`frontend/src/lib/components/trip-wizard/steps/`) | Frontend | Wizard-Dropdown; heute Mapping `mode !== 'raw'` → bool; muss auf `format_mode`-String umgestellt werden |
| `WeatherConfigDialog.svelte` (`frontend/src/lib/components/`) | Frontend | Locations-/Subscriptions-Dialog; heute 2-Wege-Segmented-Control |

## Implementation Details

### Schritt 1 — Konsolidierungs-Vor-Commit

`_build_friendly_keys()` in `trip_report.py:640` durch Import aus `email/helpers.py` ersetzen.
Bestehende Tests bleiben grün. Damit ist die Diff der eigentlichen Erweiterung in einer Stelle lokalisiert.

### Schritt 2 — Katalog-Erweiterung

```python
# src/app/metric_catalog.py
@dataclass
class MetricDefinition:
    # bestehende Felder ...
    format_modes: tuple[str, ...] = ("raw",)
    default_format_mode: str = "raw"
```

Verbindliche Modus-Tabelle aller 25 Metriken:

| Metrik-ID | `format_modes` | `default_format_mode` |
|---|---|---|
| `temperature` | `("raw",)` | `raw` |
| `wind_chill` | `("raw",)` | `raw` |
| `humidity` | `("raw",)` | `raw` |
| `dewpoint` | `("raw",)` | `raw` |
| `wind` | `("raw","simplified")` | `raw` |
| `gust` | `("raw","simplified")` | `raw` |
| `wind_direction` | `("raw","scale")` | `scale` |
| `precipitation` | `("raw","simplified")` | `raw` |
| `rain_probability` | `("raw",)` | `raw` |
| `confidence` | `("raw",)` | `raw` |
| `thunder` | `("symbol",)` | `symbol` |
| `cape` | `("raw","symbol")` | `symbol` |
| `snowfall_limit` | `("raw",)` | `raw` |
| `precip_type` | `("raw",)` | `raw` |
| `cloud_total` | `("raw","symbol")` | `symbol` |
| `cloud_low` | `("raw","symbol")` | `symbol` |
| `cloud_mid` | `("raw","symbol")` | `symbol` |
| `cloud_high` | `("raw","symbol")` | `symbol` |
| `visibility` | `("raw","simplified")` | `simplified` |
| `sunshine` | `("raw","symbol")` | `symbol` |
| `uv_index` | `("raw",)` | `raw` |
| `pressure` | `("raw",)` | `raw` |
| `freezing_level` | `("raw",)` | `raw` |
| `snow_depth` | `("raw",)` | `raw` |
| `fresh_snow` | `("raw",)` | `raw` |

`api/routers/config.py` liefert `format_modes` und `default_format_mode` in der `/api/metrics`-Response mit aus.

### Schritt 3 — Datenmodell + Read-Adapter

```python
# src/app/models.py
class MetricConfig(BaseModel):
    # ... bestehende Felder
    use_friendly_format: bool = True  # @deprecated — Backward-Compat
    format_mode: Optional[str] = None  # "raw" | "scale" | "simplified" | "symbol"
```

Read-Adapter in `loader.py`:

```python
def _resolve_format_mode(mc_data: dict, metric_id: str) -> str:
    if (raw := mc_data.get("format_mode")) is not None:
        return raw
    if not mc_data.get("use_friendly_format", True):
        return "raw"
    return get_metric(metric_id).default_format_mode
```

Schreib-Pfade schreiben `format_mode` und `use_friendly_format` parallel:
- `format_mode="raw"` → `use_friendly_format=False`
- alle anderen Modi → `use_friendly_format=True`

### Schritt 4 — Renderer-Umbau

`fmt_val()` Signatur: `format_modes: dict[str, str]` statt `friendly_keys: set`.
`build_format_modes()` ersetzt `build_friendly_keys()` als Spalten-Index-Builder.
`format_wind_strength(kmh: float) -> str` und `format_precip_intensity(mm: float) -> str`
werden als neue Helfer in `src/services/weather_metrics.py` definiert (Single Source)
und von `fmt_val` für den `simplified`-Pfad genutzt.

Renderer-Mappings:
- `mode="raw"` → numerisch mit Einheit (unverändertes heutiges Verhalten)
- `mode="scale"` → Kompass-Punkte (nur `wind_direction`)
- `mode="simplified"` → Adjektiv-Kürzel ohne Zahl in HTML-Tabelle (`wind`, `gust`, `precipitation`, `visibility`)
- `mode="symbol"` → Emoji-Darstellung (`cloud_*`, `cape`, `sunshine`, `thunder`)

Wind-Direction-Merge-Trigger: `wind_direction.format_mode == "scale"` (bisher `use_friendly_format=True`).
Bei `format_mode="raw"` steht Wind-Richtung als Grad in eigener Spalte.

Token-Builder: `format_mode in {"symbol", "scale"}` → `\x00{friendly_label}`-SMS-Token,
sonst numerischer Token.

### Schritt 5 — Frontend-Types + API-Konsum

```typescript
// frontend/src/lib/types.ts
interface MetricEntry {
  // ... bestehende Felder
  format_modes: string[];
  default_format_mode: string;
}

interface WeatherConfigMetric {
  // ... bestehende Felder
  use_friendly_format?: boolean;  // @deprecated
  format_mode?: string;
}
```

Wizard-Step 3 filtert Dropdown-Options aus `m.format_modes`:
```typescript
// statt: m.use_friendly_format = mode !== 'raw'
m.format_mode = mode;
m.use_friendly_format = mode !== 'raw';  // Backward-Compat parallel schreiben
```

`WeatherConfigDialog` ersetzt die 2-Wege-Segmented-Control durch ein N-Optionen-Dropdown
aus `metric.format_modes`, analog zu Step 3.

### Schritt 6 — Cleanup-Marker

`use_friendly_format` wird in `models.py` und `types.ts` mit `@deprecated`-Kommentar
markiert. Ein Folge-Issue „Remove legacy friendly bool" wird eröffnet (Out-of-Scope für #435).

### LoC-Budget

~350 LoC gesamt — überschreitet 250er-Grenze. `loc_limit_override 400` ist in Phase 6 zu setzen.
Begründung: Der Datenmodell-Schwenk berührt jeden Read/Write-Pfad; Aufteilung würde
das Frontend zwischendurch in Bug-Zustand belassen (alle Modi außer raw → boolean-Kollaps).

## Expected Behavior

- **Input:** UI-Auswahl eines `format_mode`-Strings pro Metrik im Wizard-Step 3 oder WeatherConfigDialog (nur aus `metric.format_modes` erlaubten Werten)
- **Output:** Persistiertes `format_mode` in `MetricConfig`; gerenderte E-Mail/SMS/Compact-Summary respektiert den Modus pro Metrik; `/api/metrics` liefert `format_modes[]` + `default_format_mode` pro Metrik; Frontend-Dropdown zeigt nur erlaubte Modi
- **Side effects:**
  - Bestandsdaten ohne `format_mode`-Feld werden beim Lesen automatisch über `_resolve_format_mode()` auf den Katalog-Default der Metrik gemappt — kein Daten-Migrations-Skript nötig
  - Schreib-Pfade persistieren `format_mode` und `use_friendly_format` parallel (Backward-Compat für ältere Frontend-Versionen)
  - Pre-Snapshot via `data_schema_backup.py` bei jedem Edit auf `src/app/models.py`

## Acceptance Criteria

- **AC-1 — Katalog liefert format_modes pro Metrik:** Given der `/api/metrics`-Endpoint wird aufgerufen / When eine Metrik mit Friendly-Render existiert (z.B. `cloud_total`) / Then enthält die Response `format_modes` als Liste mit allen erlaubten Modi (z.B. `["raw","symbol"]`) und `default_format_mode` als String aus dieser Liste (z.B. `"symbol"`).
  - Test: (populated after /tdd-red)

- **AC-2 — Wizard-Dropdown filtert auf erlaubte Modi:** Given Step3Weather lädt den Metrik-Katalog / When der User das Format-Dropdown einer Metrik öffnet (z.B. `temperature` mit `format_modes=["raw"]`) / Then werden NUR die im Katalog erlaubten Optionen angezeigt — keine „Symbol"-Option bei reinem Roh-Modus.
  - Test: (populated after /tdd-red)

- **AC-3 — Bestandsdaten lesen ohne Verhaltensänderung:** Given eine bestehende Trip-Konfiguration mit `use_friendly_format=true` und ohne `format_mode` / When der Loader die Konfiguration liest / Then wird `format_mode` auf den `default_format_mode` der Metrik aus dem Katalog resolved (z.B. `cloud_total` → `symbol`, `wind_direction` → `scale`, `visibility` → `simplified`) und das gerenderte HTML/SMS ist bit-identisch zum heutigen Verhalten.
  - Test: (populated after /tdd-red)

- **AC-4 — Schreib-Pfade speichern beide Felder parallel:** Given der User wählt im Wizard `format_mode='symbol'` für `cloud_total` / When der Trip gespeichert wird / Then enthält der persistierte `MetricConfig` sowohl `format_mode='symbol'` als auch `use_friendly_format=True` (Backward-Compat für alte Frontend-Versionen).
  - Test: (populated after /tdd-red)

- **AC-5 — Renderer respektiert format_mode pro Metrik:** Given eine Metrik-Config mit `format_mode='raw'` für `cloud_total` / When der E-Mail-Report gerendert wird / Then zeigt die Tabelle den numerischen Prozentwert (`50%`) statt des Wolken-Emoji.
  - Test: (populated after /tdd-red)

- **AC-6 — Simplified-Kürzel in HTML-Tabelle für Wind/Niederschlag:** Given eine Metrik-Config mit `format_mode='simplified'` für `wind` / When der E-Mail-Report gerendert wird / Then zeigt die Wind-Spalte das Kürzel-Adjektiv (`schwach` / `mäßig` / `stark`) ohne nachfolgende km/h-Zahl, während Compact-Summary die volle Phrase (`schwacher Wind 12 km/h`) beibehält.
  - Test: (populated after /tdd-red)

- **AC-7 — Wind-Richtungs-Merge an scale-Modus gekoppelt:** Given `wind_direction.format_mode='scale'` / When der Report gerendert wird / Then wird die Wind-Richtung als Kompass-Punkt (N/NE/E/...) in die Wind-Spalte gemergt (heutiges Verhalten). Given `wind_direction.format_mode='raw'` / When der Report gerendert wird / Then steht die Wind-Richtung als Grad-Wert in einer eigenen Spalte (neues, semantisch korrektes Verhalten).
  - Test: (populated after /tdd-red)

- **AC-8 — SMS-Token-Pfad bit-identisch:** Given eine Metrik mit `format_mode='symbol'` (z.B. `cape`) / When ein SMS-Token gebaut wird / Then ist die Token-Ausgabe bit-identisch zur heutigen `use_friendly_format=True`-Pfad-Ausgabe (Goldens unverändert).
  - Test: (populated after /tdd-red)

- **AC-9 — WeatherConfigDialog zeigt N-Optionen-Dropdown:** Given der WeatherConfigDialog wird für eine Location geöffnet / When eine Metrik mit `format_modes=["raw","symbol"]` angezeigt wird / Then zeigt der Dialog ein Dropdown mit beiden Optionen (statt der heutigen 2-Wege-Segmented-Control „Roh/Indikator").
  - Test: (populated after /tdd-red)

- **AC-10 — Konsolidierung Duplikat:** Given `_build_friendly_keys` existiert heute in `email/helpers.py` und `trip_report.py` / When der Vor-Commit der Spec umgesetzt wird / Then existiert die Funktion nur noch in `email/helpers.py` und `trip_report.py` importiert sie.
  - Test: (populated after /tdd-red)

## Known Limitations

- Nur die Modi gebaut, die heute schon im Code existieren (konservativ, PO-Entscheidung 2026-05-28). Folge-Issues für neue Mappings (z.B. Beaufort-Skala für Wind, Temperatur-Symbole) bleiben offen.
- `use_friendly_format` bleibt vorerst im Datenmodell mit `@deprecated`-Markierung; Cleanup in separatem Folge-Issue.
- `fmt_val`-Quasi-Duplikat in `trip_report.py:653–770` (zweite Renderer-Stelle, analog zu `email/helpers.py:332–449`) ist Out-of-Scope für #435 — eigenes Refactor-Issue.
- `visibility`-Symbol-Variante (z.B. ✅/⚠️ statt Textklassen) wird in dieser Iteration nicht angeboten; Folge-Issue, falls gewünscht.
- `loc_limit_override 400` ist in Phase 6 zu setzen (Gesamt ~350 LoC, überschreitet 250er-Default).
- `_resolve_format_mode()` in `src/app/loader.py` wird im Production-Read-Pfad heute nicht aufgerufen — die äquivalente Resolution erfolgt zur Render-Zeit in `_effective_format_mode` (`src/output/renderers/email/helpers.py`). Beide Funktionen halten denselben Vertrag, sind aber Duplikate. Konsolidierung in Folge-Issue (Adversary F001, 2026-05-28).
- `_resolve_format_mode()` und `_effective_format_mode()` lassen unbekannte `format_mode`-Strings (z.B. `"Symbol"` mit Großbuchstaben, `"raw_v2"`) ungeprüft durch. `fmt_val` fällt in solchen Fällen auf den Friendly-/Symbol-Pfad zurück (graceful degradation), kein Crash. Strikte Validierung in [Issue #446](issue_446_format_mode_validation.md) (implementiert 2026-05-29).

## Changelog

- 2026-05-28: Initial spec created (Phase 3, Issue #435)
- 2026-05-28: Fix-Loop #1 — `thunder.format_modes` von `("raw","symbol")` auf `("symbol",)` korrigiert (kein numerischer Raw-Render existiert; Adversary F003). Known Limitations um F001/F004 ergänzt.

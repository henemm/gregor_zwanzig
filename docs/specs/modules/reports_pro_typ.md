---
entity_id: reports_pro_typ
type: module
created: 2026-04-20
updated: 2026-04-20
status: draft
version: "1.0"
tags: [metrics, formatter, config, serialization, ui, morning, evening, report-type]
---

# Reports pro Typ Phase A: Per-Report-Type Metric Filtering

## Approval

- [ ] Approved

## Purpose

Aktiviert die bereits in `MetricConfig` vorhandenen Felder `morning_enabled` und `evening_enabled`, sodass Morgen- und Abendreports unterschiedliche Metrik-Auswahlen zeigen koennen. Ohne dieses Feature sind die Felder zwar in `models.py` deklariert, werden aber weder serialisiert noch vom Formatter oder der UI ausgewertet — das Ergebnis sind identische Metrik-Saetze in beiden Report-Typen.

## Source

- **Files:**
  - `src/app/models.py` (MODIFY) — neue Methode `get_metrics_for_report_type()` auf `UnifiedWeatherDisplayConfig`
  - `src/app/loader.py` (MODIFY) — Serialisierung von `morning_enabled`/`evening_enabled` ergaenzen
  - `src/formatters/trip_report.py` (MODIFY) — Metrik-Filterung am Einstiegspunkt `format_email()`
  - `src/web/pages/weather_config.py` (MODIFY) — M/A-Toggle-Spalten pro Metrik-Zeile in der Konfigurationsdialog-UI

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricConfig` | dataclass | Traegt `morning_enabled`, `evening_enabled`, `enabled` (Felder existieren bereits) |
| `UnifiedWeatherDisplayConfig` | dataclass | Container fuer `metrics: list[MetricConfig]`; hier wird die neue Methode ergaenzt |
| `MetricCatalog` | module | Definitionen aller verfuegbaren Metriken; keine Aenderung, aber referenziert in loader.py |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportFormatter.format_email()` | method | Ruft `get_metrics_for_report_type()` auf und ersetzt `dc.metrics` per `dataclasses.replace()` |
| `TripReportSchedulerService` | service | Keine Aenderung — gibt `report_type` bereits weiter an den Formatter |
| `weather_config.py` (NiceGUI Dialog) | UI page | Zeigt M/A-Toggles und persistiert die neuen Felder beim Speichern |

---

## Implementation Details

### 1. src/app/models.py — get_metrics_for_report_type()

Neue Methode auf `UnifiedWeatherDisplayConfig` (ca. +20 LoC):

```python
def get_metrics_for_report_type(self, report_type: str) -> list[MetricConfig]:
    """
    Return the metrics relevant for a given report type.

    For "morning" and "evening", morning_enabled/evening_enabled act as
    per-type overrides over the global `enabled` flag:
      - morning_enabled=True  -> include in morning even if enabled=False
      - morning_enabled=False -> exclude from morning even if enabled=True
      - morning_enabled=None  -> fall back to global `enabled`
    Same logic applies for evening_enabled.

    For all other report_types (e.g. "alert"): return only globally enabled metrics.
    """
    result = []
    for mc in self.metrics:
        if report_type == "morning":
            if mc.morning_enabled is True:
                result.append(mc)
            elif mc.morning_enabled is False:
                pass  # explicitly excluded
            else:  # None -> inherit global
                if mc.enabled:
                    result.append(mc)
        elif report_type == "evening":
            if mc.evening_enabled is True:
                result.append(mc)
            elif mc.evening_enabled is False:
                pass  # explicitly excluded
            else:  # None -> inherit global
                if mc.enabled:
                    result.append(mc)
        else:
            if mc.enabled:
                result.append(mc)
    return result
```

Semantik-Tabelle zur Klarstellung:

| `enabled` | `morning_enabled` | Ergebnis im Morgenreport |
|-----------|-------------------|--------------------------|
| True | None | erscheint (inherit) |
| False | None | fehlt (inherit) |
| True | False | fehlt (override) |
| False | True | erscheint (override) |
| True | True | erscheint |
| False | False | fehlt |

### 2. src/app/loader.py — Serialisierungsluecke schliessen

Die Deserialisierung liest `morning_enabled` und `evening_enabled` bereits (loader.py:198-199). Die Serialisierung (dict-Ausgabe beim Speichern) muss ergaenzt werden.

In **beiden** Speicherpfaden — Trip und Location — den MetricConfig-zu-dict-Block erweitern:

```python
# Vorher (nur `enabled` wird geschrieben):
metric_dict = {
    "id": mc.id,
    "enabled": mc.enabled,
    # ...weitere Felder
}

# Nachher (morning_enabled und evening_enabled ergaenzen):
metric_dict = {
    "id": mc.id,
    "enabled": mc.enabled,
    "morning_enabled": mc.morning_enabled,   # neu
    "evening_enabled": mc.evening_enabled,   # neu
    # ...weitere Felder unveraendert
}
```

`None`-Werte werden als JSON `null` serialisiert, was bei der Deserialisierung korrekt zu `None` zurueckgemapped wird.

### 3. src/formatters/trip_report.py — Gefilterte Metriken in format_email()

Am Anfang von `format_email()`, nachdem `dc` (DisplayConfig) aufgeloest wurde, eine gefilterte Kopie erstellen:

```python
import dataclasses

def format_email(self, ..., report_type: str = "morning", ...) -> str:
    # ... bestehende dc-Aufloesung ...

    if report_type in ("morning", "evening"):
        active_metrics = dc.get_metrics_for_report_type(report_type)
        dc = dataclasses.replace(dc, metrics=active_metrics)

    # alle nachgelagerten Methoden (_extract_hourly_rows, _dp_to_row,
    # _aggregate_night_block, etc.) sehen automatisch nur die
    # typ-spezifischen Metriken -- keine weiteren Aenderungen noetig
```

`dataclasses.replace()` erzeugt eine flache Kopie. Da kein nachgelagerter Code `dc.metrics` mutiert, ist das ausreichend.

### 4. src/web/pages/weather_config.py — M/A-Toggle-Spalten

Zwei kompakte Checkbox-Spalten "M" (Morgen) und "A" (Abend) neben jeder Metrik-Zeile einfuegen (ca. +70 LoC):

**Darstellung:**

```
[x] Temperatur    [M] [A]
[x] Wind          [M] [ ]
[ ] Schneefallgr. [M] [A]   <- enabled=False, aber morning/evening override moeglich
```

**Initialisierungslogik:**
- `morning_enabled=None` -> M-Checkbox erscheint gecheckt (zeigt inherited state visuell als aktiv)
- `evening_enabled=None` -> A-Checkbox erscheint gecheckt (gleiche Logik)
- `enabled=False` -> globales Disable-State wird visuell kommuniziert (z.B. ausgegraute Zeile), aber M/A bleiben interaktiv fuer Overrides

**Speicher-Handler:**

```python
def save_metric_config(mc_id, enabled, m_checked, a_checked):
    # m_checked=True, mc.morning_enabled war None -> bleibt None (kein Override gesetzt)
    # m_checked=False, mc.morning_enabled war None -> setze morning_enabled=False
    # Logik: nur explizite False-Eintraege als Override speichern;
    #        True-Zustand bei None-Ausgangswert bleibt None (inherit)
    morning_val = None if m_checked else False
    evening_val = None if a_checked else False
    # Achtung: True-Override (Metrik in Report erzwingen trotz disabled=False)
    # kann ebenfalls gesetzt werden -- UI muss diesen Fall sichtbar machen
```

Fuer den True-Override-Fall (disabled global, aber in einem Report erzwingen) kann die UI einen dritten Zustand des Checkboxes oder ein separates "force"-Icon verwenden. Implementierungsdetail obliegt dem Developer Agent, solange die drei Zustaende (None, True, False) korrekt gespeichert werden.

---

## Expected Behavior

- **Input:** `report_type` string ("morning" oder "evening") wird von `TripReportSchedulerService` an `format_email()` weitergegeben.
- **Output:** Das generierte E-Mail enthaelt nur jene Metriken, die fuer den jeweiligen Report-Typ konfiguriert sind.
- **Side effects:**
  - Bestehende Konfigurationsdateien ohne `morning_enabled`/`evening_enabled` werden korrekt deserialisiert (None-Default greift).
  - Beim naechsten Speichern in der UI werden die neuen Felder in die Konfigurationsdatei geschrieben.
  - Keine Aenderung an der Scheduler-Logik oder dem E-Mail-Versand-Kanal.

**Regression-Schutz:** Wenn `morning_enabled=None` und `evening_enabled=None` (Default fuer alle bestehenden Konfigurationen), liefert `get_metrics_for_report_type()` exakt dieselbe Liste wie bisher `[mc for mc in metrics if mc.enabled]`. Kein bestehendes Verhalten aendert sich ohne explizite Konfigurationsaktion des Users.

---

## Files to Change

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/app/models.py` | MODIFY -- neue Methode `get_metrics_for_report_type()` | +20 |
| 2 | `src/app/loader.py` | MODIFY -- `morning_enabled`/`evening_enabled` in Serialisierung | +10 |
| 3 | `src/formatters/trip_report.py` | MODIFY -- Filterung am Einstiegspunkt `format_email()` | +15 |
| 4 | `src/web/pages/weather_config.py` | MODIFY -- M/A-Toggle-Spalten im Konfig-Dialog | +70 |

**Total: ca. +115 LoC netto**

---

## Known Limitations

- SvelteKit-Frontend (`WeatherConfigDialog.svelte`) wird in Phase A nicht angepasst. Die per NiceGUI gespeicherten `morning_enabled`/`evening_enabled`-Werte sind fuer das Svelte-Frontend transparent (es liest/schreibt sie derzeit nicht).
- Alert-spezifische Metrik-Sets (Phase C) sind Out of Scope. `get_metrics_for_report_type("alert")` faellt auf den globalen `enabled`-Zustand zurueck.
- Per-Metrik-Zeithorizonte (Phase D) sind Out of Scope.
- Template-Defaults pro Report-Typ sind Out of Scope.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `dataclasses.replace()` erzeugt Shallow Copy -- koennte bei zukuenftiger Mutation von `dc.metrics`-Elementen zu Seiteneffekten fuehren | LOW | Keine Methode mutiert `dc.metrics` heute; im Code-Review darauf achten |
| `save_location`-Pfad in loader.py wird vergessen | MEDIUM | Beide Speicherpfade (Trip und Location) explizit im Developer-Briefing adressieren |
| UI-Zustand bei `morning_enabled=True` (Override auf disabled Metrik) ist komplex darzustellen | LOW | Developer Agent entscheidet ueber Darstellung; Kernlogik in `get_metrics_for_report_type()` ist unabhaengig davon |
| Bestehende Konfigurationsdateien haben kein `morning_enabled`/`evening_enabled` | LOW | Deserialisierung nutzt bereits `.get("morning_enabled", None)` in loader.py:198-199 |

## Changelog

- 2026-04-20: v1.0 Initial spec created (Reports pro Typ Phase A)

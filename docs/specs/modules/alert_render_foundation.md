---
entity_id: alert_render_foundation
type: module
created: 2026-06-29
updated: 2026-06-29
status: draft
version: "1.0"
tags: [alert, metric-catalog, weather-change, slice-1]
---

# Alert-Render-Fundament (Slice 1 von #914)

## Approval

- [ ] Approved

## Purpose

Fundament für das generische Alert-Render-System (#914): Die render-relevanten
Metrik-Stammdaten (`sms_code`, `decimals`, Vergleichsrichtung `cmp`) werden zur
**Single Source** in `metric_catalog.py` gemacht und über `/api/metrics` ausgespielt;
ein ausgelöster Alert führt zusätzlich die **Stunde des auslösenden Werts**
(`occurred_at`) mit. Slice 1 baut **nur** das Fundament — die vier Renderer (Slice 2)
und die Vorschau (Slice 3) folgen separat.

## Source

- **File:** `src/app/metric_catalog.py` — `MetricDefinition` + Registry
- **File:** `src/app/models.py` — `WeatherChange` (additives Feld `occurred_at`)
- **File:** `src/services/weather_change_detection.py` — `occurred_at` befüllen, `cmp` aus Katalog
- **File:** `api/routers/config.py` — `/api/metrics` um neue Felder erweitern
- **Identifier:** `MetricDefinition`, `WeatherChange`, `detect_changes`, `get_metrics`

> **Schicht:** Reines **Python-Backend** (`src/app`, `src/services`) + Go/Python-API-Router
> (`api/routers`). **Keine** Mail-Inhalts-Dateien (`src/output/renderers/email/*`,
> `src/formatters/*`, `src/outputs/email.py`) — bewusst, damit das Renderer-Mail-Gate
> in Slice 1 nicht greift. Kein Frontend-Code in diesem Slice.

## Estimated Scope

- **LoC:** ~180–230
- **Files:** 4–5 (+ Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog.MetricDefinition` | erweitert | trägt `sms_code`, `decimals`, `cmp` |
| `models.WeatherChange` | erweitert | trägt optional `occurred_at` |
| `weather_change_detection` | nutzt | befüllt `occurred_at`, liest `cmp` aus Katalog |
| `/api/metrics` (config-Router) | nutzt | exponiert neue Felder ans Frontend |
| `_ALERT_METRIC_COMPARISON` (heute in detection) | abgelöst | Vergleichsrichtung wandert in Katalog |

## Implementation Details

**1. `MetricDefinition` (metric_catalog.py) — drei neue Felder (additiv, defaults):**

```
sms_code: str = ""        # GSM-7-tauglicher Token (1–2 Großbuchstaben, ASCII), kollisionsfrei
decimals: int | None = None  # Rundungsstellen für Darstellung; None => bestehende Einheit-Heuristik
cmp: str = ""             # "über" | "unter" — Seite, auf der die Schwelle alarmiert
```

- Für **alle alert-fähigen** Metriken werden `sms_code` + `cmp` gesetzt. Bestehende
  Codes bleiben unverändert (`N D R PR W G TH`); neu vergeben: `cape=CP`, `fresh_snow=SN`,
  `snowfall_limit=SL`, `visibility=VS`, `humidity=HU`. `decimals` gemäß Issue-Tabelle
  (z. B. `precip=1`, `visibility=1`, sonst `0`).
- **Single-Source-Regel:** SMS-Codes existieren ab jetzt nur hier. (Die doppelte
  `SMS_SYMBOL_BY_METRIC` in `sms_trip.py` wird **erst in Slice 2** entfernt — Slice 1
  fügt den Katalog als Quelle hinzu, ohne die Mail-Dateien anzufassen.)
- Helper `get_sms_code(metric_id) -> str`, `get_decimals(metric_id) -> int`,
  `get_cmp(metric_id) -> str` (analog zu bestehenden Lookups).

**2. `WeatherChange` (models.py) — additives Feld:**

```
occurred_at: str | None = None   # "HH:MM" — Stunde des auslösenden (Peak-)Werts; None erlaubt
```

- Rein additiv (Default `None`), damit `alert_state`-JSON und bestehende Persistenz
  unberührt bleiben (Read-Modify-Write; keine Pflichtfeld-Migration).

**3. `weather_change_detection.detect_changes()`:**

- Beim Erzeugen eines `WeatherChange` die Stunde des Peak-Werts aus der stündlichen
  `ForecastDataPoint`-Liste des Segments bestimmen und als `occurred_at` ("HH:MM")
  setzen. Lässt sich die Stunde nicht eindeutig bestimmen → `None` (best-effort).
- Vergleichsrichtung (`cmp`) wird aus dem Katalog gelesen statt aus dem lokalen
  `_ALERT_METRIC_COMPARISON`-Dict; das Dict wird zur dünnen Ableitung aus dem Katalog
  oder entfällt (keine zweite Quelle).

**4. `/api/metrics` (api/routers/config.py):**

- Response pro Metrik um `sms_code`, `decimals`, `cmp` ergänzen (nur für ausgespielte,
  `selectable=true` Metriken). Bestehende Felder unverändert.

## Expected Behavior

- **Input:** unveränderter Detektions-/Katalog-Pfad.
- **Output:** `WeatherChange` trägt jetzt `occurred_at`; `/api/metrics` liefert
  `sms_code`/`decimals`/`cmp`; Katalog ist alleinige Quelle dieser Stammdaten.
- **Side effects:** keine neue Persistenz; `occurred_at` ist optional und additiv.

## Acceptance Criteria

- **AC-1:** Given der Metrik-Katalog / When ich alle alert-fähigen Metriken abfrage /
  Then hat **jede** einen nicht-leeren, ASCII-only, kollisionsfreien `sms_code`
  (inkl. `cape=CP`, `fresh_snow=SN`, `snowfall_limit=SL`, `visibility=VS`, `humidity=HU`)
  und die etablierten Codes (`N D R PR W G TH`) sind unverändert.
  - Test: Echte Iteration über `get_all_metrics()` + alert-fähige Filterung; Assert auf
    Eindeutigkeit (kein Duplikat), ASCII, Nicht-Leere; Assert konkreter Werte für die
    neuen und die etablierten Codes. Zusätzlich: `humidity=HU` via direktem Katalog-Lookup
    (da `humidity` als Vorboten-Metrik aus dem Alert-Filter herausfällt, aber `sms_code`
    trotzdem tragen muss — F003).

- **AC-2:** Given eine alert-fähige Metrik / When ich ihre Vergleichsrichtung abfrage /
  Then liefert der Katalog `cmp` „über" bzw. „unter" passend zur Metrik (z. B.
  `temp_min`→„unter", `gust`→„über"), und die Detektion verwendet **diese** Quelle
  (kein abweichendes zweites Mapping mehr maßgeblich).
  - Test: Für mehrere Metriken `get_cmp()` gegen erwartete Seite prüfen; ein
    Detektions-Durchlauf mit echten Werten erzeugt `WeatherChange`, dessen
    Schwellseite mit der Katalog-`cmp` übereinstimmt.

- **AC-3:** Given ein realer Vorhersage-Datensatz, der eine Schwelle überschreitet /
  When die Detektion einen `WeatherChange` erzeugt / Then ist `occurred_at` als
  plausible Stunde „HH:MM" innerhalb des Segment-Zeitfensters gesetzt (oder `None`,
  wenn nicht bestimmbar — nie ein Fehler/Crash).
  - Test: Detektion mit echten/echt-strukturierten stündlichen Datenpunkten; Assert
    `occurred_at` ist `None` **oder** matcht `^\d{2}:\d{2}$` und liegt im Fenster.

- **AC-4:** Given das laufende Backend / When das Frontend `GET /api/metrics` aufruft /
  Then enthält jeder ausgespielte Metrik-Eintrag die Felder `sms_code`, `decimals`,
  `cmp`, und die bestehenden Felder bleiben unverändert vorhanden.
  - Test: Echter HTTP-Call gegen den laufenden Endpunkt; Assert auf Präsenz + Typ der
    neuen Felder und Fortbestand der alten.

- **AC-5:** Given bestehende gespeicherte Alert-/Trip-Daten / When Code mit dem neuen
  `WeatherChange`-Feld geladen und wieder gespeichert wird / Then gehen keine
  bestehenden Felder verloren (Roundtrip ohne Daten-Diff; `occurred_at` default `None`).
  - Test: Echter Load→Save→Load-Roundtrip eines bestehenden Datensatzes; Assert
    Feld-Gleichheit außer dem additiven `occurred_at`.

## Known Limitations

- `occurred_at` ist **best-effort** (Peak-Stunde); ist sie nicht eindeutig bestimmbar,
  bleibt sie `None`. Die Renderer (Slice 2) behandeln `@hh` ohnehin als optional.
- Die doppelte `SMS_SYMBOL_BY_METRIC` in `sms_trip.py` bleibt in Slice 1 **noch**
  bestehen (Entfernung in Slice 2, um das Renderer-Mail-Gate gebündelt zu durchlaufen).
  Während Slice 1 sind die Codes konsistent, weil die neuen Katalog-Codes mit den
  etablierten übereinstimmen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (Alert-Render — ein Backend-Renderer, Registry als Single Source)
- **Rationale:** Slice 1 realisiert den Single-Source-Teil der Entscheidung (Stammdaten
  im Katalog) und das nötige Datenmodell-Fundament (`occurred_at`).

## Changelog

- 2026-06-29: Initial spec created (Slice 1 von #914).

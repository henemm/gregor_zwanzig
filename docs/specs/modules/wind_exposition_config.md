---
entity_id: wind_exposition_config
type: module
created: 2026-02-18
updated: 2026-02-18
status: implemented
version: "1.0"
tags: [wind, exposition, config, trip, ui, elevation]
---

# F7c: Trip-Level Wind-Exposition Config v1.0

## Approval

- [x] Approved (2026-02-18)

## Purpose

Ermoeglicht es, den `min_elevation_m`-Schwellwert fuer die Wind-Exposition-Erkennung
pro Trip zu konfigurieren statt ihn global hardcoded zu lassen.

Behebt das bekannte Problem aus F7 und F7b: `min_elevation_m = 2000m` ist fuer viele
exponierte Routen zu hoch (GR20 kritische Abschnitte 1600-2000m, GR221 Gratkamm
800-1000m). Ausserdem wird der globale Default von 2000m auf 1500m gesenkt, was
fuer die Mehrheit der Wanderrouten besser passt.

## Source

- **Geaendert:** `src/app/models.py` — neues Feld in `TripReportConfig`
- **Geaendert:** `src/services/trip_report_scheduler.py` — liest Config-Wert und uebergibt ihn
- **Geaendert:** `src/services/wind_exposition.py` — globaler Default 2000→1500
- **Geaendert:** `src/app/loader.py` — laedt/speichert neues Feld
- **Geaendert:** `src/web/pages/report_config.py` — UI-Eingabe fuer den Schwellwert
- **Geaendert:** `tests/integration/test_wind_exposition_pipeline.py` — Config-Tests

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WindExpositionService` | service (F7) | Akzeptiert bereits `min_elevation_m` als Parameter |
| `TripReportConfig` | DTO (models.py) | Traegt das neue optionale Feld |
| `TripReportSchedulerService` | service (F7b) | Ruft `detect_exposed_from_segments()` auf — uebergibt neuen Wert |
| `loader.py` | core | Serialisiert/Deserialisiert `TripReportConfig` aus Trip-JSON |
| `report_config.py` | UI | Bestehender Dialog fuer Trip-Report-Einstellungen |

## Implementation Details

### 1) models.py — Neues Feld in TripReportConfig

```python
@dataclass
class TripReportConfig:
    ...
    # Wind-Exposition
    wind_exposition_min_elevation_m: Optional[float] = None  # NEU; None = globaler Default (1500m)
```

Gueltiger Bereich: 500–4000m. `None` bedeutet "globalen Default verwenden"
(derzeit 1500m in `WindExpositionService`).

### 2) wind_exposition.py — Globalen Default senken

```python
def detect_exposed_from_segments(
    self,
    segments: list[TripSegment],
    min_elevation_m: float = 1500.0,  # GEAENDERT: war 2000.0
) -> list[ExposedSection]:
    ...

def detect_exposed_sections(
    self,
    track: GPXTrack,
    radius_km: float = 0.3,
    min_elevation_m: float = 1500.0,  # GEAENDERT: war 2000.0
) -> list[ExposedSection]:
    ...
```

Beides Methoden erhalten den neuen Default, weil beide denselben Parameter tragen
und die bisherige Doku 2000m als "bekannte Einschraenkung" fuhrt.

### 3) trip_report_scheduler.py — Config-Wert lesen und weiterreichen

```python
def _send_trip_report(self, trip, report_type):
    ...
    segments = self._convert_trip_to_segments(trip, target_date)
    ...

    # NEU: Trip-spezifischen Schwellwert lesen (fallback auf Service-Default)
    min_elev = None
    if trip.report_config and trip.report_config.wind_exposition_min_elevation_m is not None:
        min_elev = trip.report_config.wind_exposition_min_elevation_m

    from services.wind_exposition import WindExpositionService
    try:
        if min_elev is not None:
            exposed_sections = WindExpositionService().detect_exposed_from_segments(
                segments, min_elevation_m=min_elev
            )
        else:
            exposed_sections = WindExpositionService().detect_exposed_from_segments(segments)
    except Exception as e:
        logger.warning(f"Wind exposition detection failed for {trip.id}: {e}")
        exposed_sections = []
    ...
```

### 4) loader.py — Feld lesen und schreiben

**Laden (`load_trip`):**

```python
report_config = TripReportConfig(
    ...
    wind_exposition_min_elevation_m=rc_data.get("wind_exposition_min_elevation_m"),  # NEU
)
```

**Speichern (`save_trip`):**

```python
data["report_config"] = {
    ...
    "wind_exposition_min_elevation_m": trip.report_config.wind_exposition_min_elevation_m,  # NEU
}
```

`None` wird als JSON-`null` gespeichert und durch `.get()` wieder als `None` geladen —
Rundtrip-sicher ohne Migration.

### 5) report_config.py — UI-Eingabe

**Im Dialog (`show_report_config_dialog`):**

```python
# Wind-Exposition Section
ui.label("Wind-Exposition").classes("text-subtitle1 q-mt-md")

elev_input = ui.number(
    label="Wind-Exposition ab Höhe (m)",
    value=config.wind_exposition_min_elevation_m,  # None zeigt Placeholder
    placeholder="1500",
    min=500,
    max=4000,
    step=100,
).classes("w-48")
```

**In `make_save_handler` — Signatur und `do_save` erweitern:**

```python
def make_save_handler(
    ...,
    elev_input,  # NEU
    ...
):
    def do_save():
        ...
        # Lese Elevation-Input (None wenn leer)
        min_elev = float(elev_input.value) if elev_input.value else None

        config = TripReportConfig(
            ...,
            wind_exposition_min_elevation_m=min_elev,  # NEU
        )
        ...
```

**Aufruf von `make_save_handler` im Dialog anpassen:**

```python
ui.button(
    "Speichern",
    on_click=make_save_handler(
        trip.id,
        morning_input,
        evening_input,
        email_checkbox,
        sms_checkbox,
        alert_checkbox,
        elev_input,   # NEU
        dialog,
        user_id,
    )
).props("color=primary")
```

## Expected Behavior

- **Input:** `TripReportConfig.wind_exposition_min_elevation_m` — optionaler Float oder `None`
- **Output:** `WindExpositionService.detect_exposed_from_segments()` wird mit dem trip-spezifischen
  Schwellwert aufgerufen; bei `None` greift der Service-Default (1500m)
- **Side effects:** Keine — neues Feld wird ins Trip-JSON persistiert

### Beispiele

1. **GR20, `wind_exposition_min_elevation_m=1800`**
   - Abschnitte ab 1800m werden als exponiert gewertet
   - Vorher (2000m Default): Abschnitte auf 1800-2000m wurden ignoriert

2. **GR221 Mallorca, `wind_exposition_min_elevation_m=800`**
   - Gratkamm auf 800-1000m wird erkannt
   - Mit Default 1500m wuerde kein einziger Abschnitt feuern

3. **Kein Wert gesetzt (`None`)**
   - Service nutzt Default: 1500m (neu), vormals 2000m
   - Bestehende Trips ohne dieses Feld profitieren automatisch vom gesenkten Default

### Edge Cases

| Situation | Verhalten |
|-----------|-----------|
| `wind_exposition_min_elevation_m=None` | `detect_exposed_from_segments(segments)` — Service-Default 1500m |
| Feld fehlt in alter Trip-JSON | `rc_data.get(...)` gibt `None` → identisch zu "nicht gesetzt" |
| Wert ausserhalb 500-4000m | UI-Validierung durch `min`/`max` auf `ui.number`; Scheduler akzeptiert trotzdem jeden Float |
| `report_config=None` | Kein Wind-Exposition-Config → Service-Default 1500m |

## Scope

| Datei | Aenderung | Geschaetzte LoC |
|-------|-----------|-----------------|
| `src/app/models.py` | 1 Feld in `TripReportConfig` | ~2 |
| `src/services/wind_exposition.py` | Default-Wert in 2 Methoden aendern | ~2 |
| `src/services/trip_report_scheduler.py` | Config-Wert lesen + bedingter Aufruf | ~10 |
| `src/app/loader.py` | Feld laden + speichern | ~4 |
| `src/web/pages/report_config.py` | UI-Input + Handler-Signatur | ~20 |
| `tests/integration/test_wind_exposition_pipeline.py` | Config-Tests ergaenzen | ~25 |
| **Total** | | **~63** |

### Out of Scope

- Validierung des Bereichs (500-4000m) im Scheduler/Service — UI-Validierung genuegt
- Migration bestehender Trip-JSONs — `None`-Default ist rueckwaertskompatibel
- `radius_km` konfigurierbar machen — bleibt auf 0.3km (separates Feature)
- `detect_exposed_sections(track)` (GPX-Track-Variante) — Scheduler nutzt diese Methode nicht

## Test Plan

### Integration Tests (test_wind_exposition_pipeline.py — Erweiterung)

- [ ] `test_custom_min_elevation_used`: Segment auf 1600m, `min_elevation_m=1500` gesetzt → `WIND_EXPOSITION` Risk
- [ ] `test_default_min_elevation_1500`: Segment auf 1600m, kein Config-Override → Risk (1500m Default)
- [ ] `test_segment_below_custom_elevation`: Segment auf 900m, Config 1500m → kein Risk
- [ ] `test_none_config_uses_service_default`: `wind_exposition_min_elevation_m=None` → Service-Default aktiv
- [ ] `test_loader_roundtrip`: Feld wird in JSON gespeichert und korrekt geladen
- [ ] `test_loader_missing_field_defaults_to_none`: Altes JSON ohne das Feld → `None`

## Acceptance Criteria

- [ ] `TripReportConfig.wind_exposition_min_elevation_m: Optional[float] = None` existiert in `models.py`
- [ ] `WindExpositionService` nutzt 1500m als Default (nicht mehr 2000m)
- [ ] Scheduler liest `trip.report_config.wind_exposition_min_elevation_m` und uebergibt es an den Service
- [ ] `loader.py` laedt und speichert das Feld korrekt (inkl. `None` → `null` → `None` Roundtrip)
- [ ] UI zeigt Zahlen-Eingabe "Wind-Exposition ab Höhe (m)" mit Placeholder "1500" im Report-Config-Dialog
- [ ] UI speichert den eingegebenen Wert oder `None` (bei leerem Feld)
- [ ] Alle bestehenden Tests weiterhin gruen (keine Regression)

## Known Limitations

- **Bereichs-Validierung nur im UI:** Ein direkt manipuliertes Trip-JSON kann Werte ausserhalb
  500-4000m enthalten — der Service akzeptiert diese ohne Fehler.
- **`detect_exposed_sections(track)`-Variante** hat ebenfalls `min_elevation_m`-Parameter, wird
  aber vom Scheduler nicht aufgerufen. Der Default wird trotzdem gesenkt fuer Konsistenz.
- **radius_km** bleibt unkonfigurierbar — nach wie vor 300m um jeden Gipfel/Pass.

## Changelog

- 2026-02-18: v1.0 — Implemented. Per-trip `wind_exposition_min_elevation_m` config added to TripReportConfig, UI input in report config dialog, global default lowered from 2000m to 1500m.

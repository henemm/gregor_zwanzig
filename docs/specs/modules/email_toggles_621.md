---
entity_id: email_toggles_621
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [output, email, config, issue-621]
---

# Mail-Elemente abschaltbar — Konfig-Felder + Render-Gating (Issue #621)

## Approval

- [x] Approved

## Purpose

Jedes (vom PO freigegebene) Element der Briefing-Mail soll an-/abschaltbar sein.
Dieses Issue liefert die **additiven Konfig-Felder auf `TripReportConfig`** und die
**Render-Gating-Logik** (HTML + Plain-Text). Default = bisheriges Verhalten (alles an),
kein Bestandstrip ändert sich. Die Bedien-Oberfläche kommt aus #619, das Mail-Aussehen
aus #613 (bereits live).

## Source

- **File:** `src/app/models.py` (`TripReportConfig`) — 5 additive Felder
- **File:** `src/app/loader.py` (`_parse_trip` report_config-Block) — Parsing mit Default-Fallback
- **File:** `src/output/renderers/email/html.py` (`render_html`) — Gating der HTML-Blöcke
- **File:** `src/output/renderers/email/plain.py` (`render_plain`) — Gating der Plain-Blöcke
- **File:** `src/output/renderers/email/__init__.py` (`render_email`) — kwarg-Durchreichung
- **File:** `src/formatters/trip_report.py` (`format_email`) — Toggles aus `report_config` lesen + weiterreichen
- **File:** `src/services/trip_report_scheduler.py` + `src/services/preview_service.py` — `trip.report_config` übergeben
- **Schicht:** Python-Backend. Go (`internal/model/trip.go`) speichert `report_config` als opaques `map[string]interface{}` und merged Top-Level (Issue #99) → **kein Go-Change nötig**.

## Estimated Scope

- **LoC:** ~150–200 (5 Felder + Loader + 2 Renderer-Gates + Pipeline-Durchreichung)
- **Files:** 7 (models, loader, html, plain, __init__, trip_report, scheduler/preview)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` | bestehendes Dataclass | trägt die neuen Schalter |
| `render_html` / `render_plain` | bestehende Pure-Funcs | Gating-Ziele |
| `build_daily_aggregates` | bestehender Helfer | Tages-Summe-Werte (wird um Temp erweitert) |
| `format_email` | bestehende Pipeline | reicht Toggles durch |

## Implementation Details

### Neue Felder auf `TripReportConfig` (additiv, sichere Defaults)

```python
show_stage_stats: bool = True          # Etappen-Kennzahlen-Raster
show_quick_take_tags: bool = True      # Quick-Take-Chips (nur HTML)
show_stability: bool = True            # Großwetterlage-Label
show_highlights: bool = True           # Zusammenfassung (Highlights)
daily_summary_metrics: list[str] = field(
    default_factory=lambda: ["precipitation", "wind", "visibility", "thunder"]
)                                      # Tages-Summe-Auswahl (Muster sms_metrics)
```

### Loader (`loader.py`)

Jedes Feld via `rc_data.get("<feld>", <default>)` parsen — fehlendes Feld = alter Zustand
(Backward-Compat, keine Migration). `daily_summary_metrics` analog `multi_day_trend_reports`.

### Render-Gating

Die 5 Toggles werden als explizite kwargs (backward-kompatible Defaults) durch
`format_email → render_email → render_html / render_plain` gereicht. `format_email`
erhält sie aus dem (neuen, optionalen) `report_config`-Parameter; Scheduler und
Preview-Service übergeben `trip.report_config`.

| Toggle | HTML-Gate (`render_html`) | Plain-Gate (`render_plain`) |
|---|---|---|
| `show_stage_stats` | `stats_grid_html` nur wenn True | stage_stats-Zeile nur wenn True |
| `show_quick_take_tags` | `quick_take_html` nur wenn True | — (kein Plain-Äquivalent, Chips sind HTML) |
| `show_stability` | `stability_html` nur wenn True | Stabilitäts-Block nur wenn True |
| `show_highlights` | `highlights_html` nur wenn True | Highlights-Block nur wenn True |
| `daily_summary_metrics` | Tages-Summe metrik-gefiltert; leere Liste → ganzer Block fehlt | identisch gefiltert |

### Tages-Summe metrik-getrieben

Der Tages-Summe-Block (HTML + Plain) wird aus `daily_summary_metrics` in **fester
Reihenfolge** aufgebaut, eine Zelle/Zeile pro gewählter Metrik. Aggregation fest pro Metrik:

| Metrik-ID | Label | Aggregat |
|---|---|---|
| `precipitation` | Regen gesamt | Σ `precip_1h_mm` (mm) |
| `wind` | Max Böe | max `gust_kmh` (km/h) |
| `visibility` | Min Sicht | min `visibility_m` → km |
| `thunder` | Gewitter | max `thunder_level` (kein/MED/HIGH) |
| `temperature` | Temp | min/max `temp_c` (°C) |

`build_daily_aggregates` wird um `min_temp_c`/`max_temp_c` erweitert. Unbekannte/leere
Metrik-IDs werden ignoriert; leere Liste → kein Block.

## Expected Behavior

- **Input:** `format_email(..., report_config=<TripReportConfig|None>)`. None → alle Defaults (alles an).
- **Output:** HTML + Plain-String, in denen abgeschaltete Sektionen fehlen und angeschaltete vorhanden sind.
- **Side effects:** keine; rein additiv, keine Migration, kein Datenverlust (Loader-Default = alter Zustand).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `show_stage_stats=False` / When die Mail (HTML + Plain) gerendert wird / Then fehlt das Etappen-Kennzahlen-Raster komplett, während bei `True` Distanz/Aufstieg/Abstieg/Max-Höhe/Segmente erscheinen.
  - Test: `render_html`/`render_plain` je einmal mit True und False aufrufen; Kennzahlen-Werte nur im True-Output nachweisen.

- **AC-2:** Given ein Trip mit `show_quick_take_tags=False` / When die HTML-Mail mit Gewitter-/Böen-Daten gerendert wird / Then erscheinen keine Quick-Take-Chips, während sie bei `True` als farbige Chips vorhanden sind.
  - Test: `render_html` mit True und False aufrufen; Chip-Markup nur im True-Output nachweisen.

- **AC-3:** Given ein Trip mit `show_stability=False` und vorliegendem Großwetterlagen-Ergebnis / When die Mail (HTML + Plain) gerendert wird / Then fehlt das Großwetterlage-Label, während es bei `True` erscheint.
  - Test: `render_html`/`render_plain` mit StabilityResult und beiden Schalterstellungen aufrufen; Label nur im True-Output nachweisen.

- **AC-4:** Given ein Trip mit `show_highlights=False` und vorhandenen Highlights / When die Mail (HTML + Plain) gerendert wird / Then fehlt der Highlights/Zusammenfassungs-Block, während er bei `True` erscheint.
  - Test: `render_html`/`render_plain` mit Highlights und beiden Schalterstellungen aufrufen; Highlights nur im True-Output nachweisen.

- **AC-5:** Given ein Trip mit `daily_summary_metrics=["precipitation","thunder"]` / When die Mail (HTML + Plain) gerendert wird / Then enthält der Tages-Summe-Block nur Regen-Summe und Gewitter, nicht Max-Böe und Min-Sicht.
  - Test: `render_html`/`render_plain` mit dieser Auswahl aufrufen; nur die zwei gewählten Kennzahlen im Tages-Summe-Block nachweisen, die anderen zwei abwesend.

- **AC-6:** Given ein Trip mit `daily_summary_metrics=[]` (leer) / When die Mail gerendert wird / Then fehlt der gesamte Tages-Summe-Block in HTML und Plain.
  - Test: `render_html`/`render_plain` mit leerer Liste aufrufen; „Tages-Summe" im Output abwesend nachweisen.

- **AC-7:** Given ein gespeicherter Trip OHNE die neuen Felder im `report_config` / When er via Loader geladen und gerendert wird / Then verhält er sich wie bisher (alle vier Sektionen an, Tages-Summe = Regen/Wind/Sicht/Gewitter) — kein Bestandstrip ändert sich, keine Felder gehen verloren.
  - Test: Trip-JSON ohne neue Felder durch `loader._parse_trip` laden; Defaults (alle True, 4er-Liste) prüfen und vollständige Mail rendern.

- **AC-8:** Given ein Trip mit `daily_summary_metrics=["temperature"]` / When die Mail gerendert wird / Then erscheint im Tages-Summe-Block die Temperatur (min/max °C), korrekt aus den Stundenwerten berechnet.
  - Test: `render_html`/`render_plain` mit bekannten temp_c-Stundenwerten aufrufen; Min/Max gegen Sollwerte prüfen.

- **AC-9:** Given das fertige Feature auf Staging mit Defaults (alles an) / When eine echte Test-Mail an `gregor-test@henemm.com` gesendet und per IMAP geprüft wird / Then meldet `email_spec_validator.py` Exit 0.
  - Test: Test-Trip auf Staging triggern, IMAP-Abruf, `email_spec_validator.py` Exit 0.

## Known Limitations

- `show_quick_take_tags` wirkt nur auf HTML (Chips sind ein visuelles Element; Plain hat keine Entsprechung) — bewusst.
- Immer an, KEIN Schalter (PO-Entscheidung): Kopf, Fußzeile, Unsicherheits-Hinweis.
- Bedien-Oberfläche (#619) und Go-Persistenz bleiben unverändert; Go merged `report_config` opaque.

## Changelog

- 2026-06-06: Initial spec created (Issue #621, Backend-Teil; UI → #619)

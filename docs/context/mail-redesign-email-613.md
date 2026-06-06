# Context: mail-redesign-email-613

## Request Summary

E-Mail-Briefing (Morgen/Abend) optisch 1:1 nach Claude-Design-Handoff „Gregor 20 — Mail Vorschau" (`EmailPreview`) umsetzen. Python-HTML-Renderer, Outlook-kompatibel, keine React-Übernahme.

## Entwurfsquelle (im Repo gesichert)

| Datei | Inhalt |
|------|--------|
| `docs/design-requests/mail-vorschau-2026-06-05/Gregor 20 - Mail Vorschau.html` | Schaukasten-Seite (3 Sektionen: Email, SMS, Config-Varianten) |
| `docs/design-requests/mail-vorschau-2026-06-05/screen-output-preview.jsx` | `EmailPreview` (Zeile 21) = Soll-Quelle für #613 |
| `docs/design-requests/mail-vorschau-2026-06-05/tokens.css` | Design-Tokens |

## Soll-Struktur `EmailPreview` (Reihenfolge)

1. **Header** — Eyebrow „MORGEN-BRIEFING · CODE" (mono, accent), Etappentitel, Datum/Zeit-Zeile, rechts „GREGOR ZWANZIG" + Trip-Kürzel + Etappe N/12
2. **Etappen-Kennzahlen als Raster** (Desktop 5 Spalten / Mobile 3): Distanz, ↑Aufstieg, ↓Abstieg, Max Höhe, Segmente
3. **Quick-Take** — Eyebrow + Fließtext + **farbige Schlagwort-Chips** (tone warn/ok/info)
4. **Stirnlampe** — Block mit Zeit (mono, tabular-nums) + Dämmerungs-/Wolken-Korrektur + **visueller `DaylightBar`-Leiste**
5. **Etappen-Verlauf** — Segment-Blöcke mit Risiko-Punkt (`RiskDot`) pro Stunde, gruppierten Spalten; Mobile: `EmailHourList` statt breiter Tabelle
6. **Wetter am Ziel** — Block auf getöntem Grund
7. **Ausblick · nächste 4 Tage** — `UpcomingRow` (Tag, Code, Titel, Temp, Risk, Note)
8. **Tages-Summe** — Raster (Desktop 4 / Mobile 2): Regen gesamt, Max Wind, Min Sicht, Gewitter % max
9. **Footer** — dunkel (`#1d1c1a`), Befehls-Links

## Ist-Struktur (`src/output/renderers/email/html.py`, `render_html` Z.245-594)

Reihenfolge: Header → stability → summary(info-box) → confidence → daylight(text-box) → changes → segments → night → thunder → trend → highlights → footer(dunkel).

| Soll-Element | Ist | Lücke |
|---|---|---|
| Header-Eyebrow + accent | ✅ `sig.eyebrow` Z.569 | Layout/rechte Spalte fehlt |
| Etappen-Kennzahlen-Raster | ⚠️ nur Text `stats_line` Z.274-285 | → Raster bauen |
| Quick-Take-Chips | ❌ nur `summary_html` Info-Box | **neu** |
| DaylightBar visuell | ⚠️ `_format_daylight_html` Z.81 nur Text | **Leiste neu** |
| Segment-Tabelle + RiskDot | ✅ Tabelle Z.287-339 (`km X,X–Y,Y` Z.318) | Risk-Punkt-Optik |
| Wetter am Ziel | ✅ „Ziel"-Segment Z.302 | Styling |
| Ausblick 4 Tage | ✅ `trend_html` Z.457 (schon nah am Design!) | ggf. UpcomingRow-Optik |
| **Tages-Summe** | ❌ | **neu** |
| Footer dunkel + Befehle | ✅ Z.586-590 | Link-Optik |

## Wichtig — Segment-Kilometer

Entwurf zeigt **einzelne** km-Zahl (`seg.km`). FALSCH für uns. `html.py:318` + `plain.py:206` geben den **km-Bereich** aus (`km {start}–{end}`, z. B. `km 1,9–4,2`). MUSS erhalten bleiben (PO-Vorgabe, „wie kürzlich geändert").

## Bereits adaptierte Design-Sprache (durch #561)

Akzent `#c45a2a`, Inter/JetBrains Mono, „05 · Ausblick"-Eyebrow, tabular-nums — der Trend-Block ist bereits design-nah. Das senkt den Aufwand.

## Verfügbare Daten (für neue Sektionen)

`ForecastDataPoint`: t2m_c, wind10m_kmh, gust_kmh, precip_1h_mm, pop_pct, thunder_level, cloud_total_pct, visibility_m, uv_index, freezing_level_m, wind_chill_c. → **Tages-Summe** (Regen Σ, Max Wind/Böen, Min Sicht, Gewitter max) und **Quick-Take-Chips** vollständig aus vorhandenen Reihen ableitbar, keine neuen Provider-Felder nötig.

## Relevante Dateien

| Datei | Relevanz |
|------|----------|
| `src/output/renderers/email/html.py` | Hauptrenderer — hier alle Änderungen |
| `src/output/renderers/email/plain.py` | Text-Fallback — Tages-Summe/Chips als Text spiegeln |
| `src/output/renderers/email/design_tokens.py` | Farb-/Font-Tokens |
| `src/output/renderers/email/helpers.py` | `pill_html` (Outlook-Chip-Baustein bereits da!), build_* |
| `src/formatters/trip_report.py` | Adapter, ruft render_email; ggf. Tages-Summe-Aggregat hier |

## Aufteilung 2026-06-05 (PO): #613 = NUR visuelles Aussehen

PO bestätigte Split. Dependency-Kette: **#613 (Aussehen) → #621 (Konfig-Felder/Backend) → #619 (Frontend-UI)**.

**#613-Scope (DIESER Workflow):** Neue Sektionen (Kennzahlen-Raster, Quick-Take-Chips, Tageslicht-Leiste, Tages-Summe) + Umstyling. Alle Sektionen **fest an** mit Standards (Tages-Summe-Default Regen/Wind/Sicht/Gewitter). km-Bereich bleibt. Plain-Text-Parität. KEINE Konfig-Felder hier.

Die folgenden Felder gehören zu **#621**, NICHT #613:

**Neue Felder (additiv):**
- `show_stage_stats: bool = True` — Etappen-Kennzahlen-Raster
- `show_quick_take_tags: bool = True` — Quick-Take-Chips
- `show_stability: bool = True` — Großwetterlage (PO: abschaltbar)
- `show_highlights: bool = True` — Zusammenfassung
- `daily_summary_metrics: list[str] = ["precipitation","wind","visibility","thunder"]` — Tages-Summe (Muster `sms_metrics` Z.555). Aggregation fest pro Kennzahl: Regen Σ · Wind/Böen/Gewitter max · Sicht min · Temp min/max.

**Immer an, KEIN Schalter** (PO): Kopf, Fußzeile, Unsicherheits-Hinweis.
**Bestehende Schalter unverändert:** show_compact_summary, show_daylight, show_night_block, thunder_forecast_days, multi_day_trend_reports, alert_on_changes.

**Hinweis Umfang:** #613 ist dadurch groß (3 neue Sektionen + Restyle + 5 Felder + Render-Bedingungen + Plain-Text) — voraussichtlich >250 LoC. Vor LoC-Override PO fragen oder splitten (Memory-Regel).

**Koordination:** Trip-Editor-Session `worktree-inherited-noodling-pebble` behält #619 im Auge.

## Risiken

- **Outlook-Kompatibilität:** keine flex/grid-Risiken in Mail-Clients — Raster via `<table>`/inline. `pill_html` existiert bereits für Outlook-Chips.
- **Plain-Text-Parität:** jede neue Sektion auch in `plain.py`.
- **Datenverlust:** kein Schema-Eingriff (reine Darstellung).
- **Abnahme nur über echte Test-Mail** (`gregor-test@henemm.com`) + `email_spec_validator.py` Exit 0 — kein Browser-Check.

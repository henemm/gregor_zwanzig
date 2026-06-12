# Context: #759 (Ampel-Metriken) + #669 (Gewitter-Badge Ausblick)

## Request Summary
- **#759** (rework, medium): E-Mail-Wetter-Metriken sollen ein **Ampelsystem** bekommen — explizit genannt für **Wind, Böen, Regen, Regenwahrscheinlichkeit**. „Einfache Darstellung".
- **#669** (feature, low, design-compliance): Im E-Mail-**Ausblick** („05 · Nächste Etappen") soll Gewitter je Folge-Etappe als **roter ⚡-Badge mit Zeitfenster** erscheinen (z.B. „⚡ Gewitter möglich 15:00–16:00").

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py` `fmt_val` (~Z.380–510) | Zellen-Formatierung der Stundentabelle — hier sitzt die Ampel-Tint-Logik je Metrik |
| `src/output/renderers/email/html.py` `trend_rows`/Ausblick (~Z.460–591) | #669: GEWITTER-Spalte je Folge-Etappe (aktuell farbiges Quadrat + Wort) |
| `src/output/renderers/email/helpers.py` `format_trend_tokens` (~Z.556–668) | Liefert `thunder_token` mit @-Stunden — Datenquelle fürs #669-Zeitfenster |
| `src/output/tokens/metrics.py` `render_threshold_peak_value` | Erzeugt `MED@15(HIGH@16)` → erste Schwellen-Stunde + Peak-Stunde = Zeitfenster |
| `src/app/metric_catalog.py` `display_thresholds` | SSoT der Ampel-Schwellen pro Metrik |
| `src/output/renderers/email/design_tokens.py` | Farb-Hex-Werte (G_DANGER, G_WX_THUNDER etc.) |

## Existing Patterns — Ampel-Stand HEUTE (in `fmt_val`)
| Metrik | col_key | display_thresholds | Ampel-Status heute |
|--------|---------|--------------------|--------------------|
| **Böen** | `gust` | `{yellow:50, red:80}` | ✅ gelb/rot Background-Tint auf Zahl |
| **Wind** | `wind` | — (keine) | ❌ keinerlei Farbe |
| **Regen** | `precip` | `{blue:5}` | nur blau (1 Stufe), keine Ampel |
| **Regenwahrsch.** | `pop` | `{blue:80}` | nur blau (1 Stufe), keine Ampel |
| CAPE | `cape` | `{yellow:1000}` | gelb / Emoji-Modus 🟢🟡🟠🔴 |
| Sicht | `visibility` | `{orange_lt:500}` | orange |
| Gewitter | `thunder` | — | rot/gelb je Level |

**Befund #759:** Böen hat bereits eine 2-Stufen-Tint-Ampel (gelb/rot). „auch für Wind/Regen/Regenwahrscheinlichkeit" = dieses Muster konsistent auf die anderen drei ausrollen. Tint-auf-Zahl bewahrt den Wert (Design-Prinzip „Hoher Kontrast = Lesbarkeit", Briefing-Werkzeug braucht echte Zahl).

**Risk-Schwellen (SSoT-Kandidaten für Ampel-Stufen, aus `risk_thresholds`):**
- wind: medium 50 / high 70
- precip: medium 20 (nur 1 Stufe)
- rain_probability: medium 80 (nur 1 Stufe)

## Existing Pattern — #669 Zeitfenster
`thunder_token` = `render_threshold_peak_value("TH", hourly_thunder, threshold=1, level_labels={1:MED,2:HIGH})`
→ Form `MED@15` oder `MED@15(HIGH@16)`. Die @-Stunden (erste Schwellen-Stunde, Peak-Stunde) sind das **Zeitfenster** → `15:00–16:00`. Keine neue Datenquelle nötig (Issue bestätigt).

## Dependencies
- Upstream: `metric_catalog.display_thresholds`, `format_trend_tokens`, `render_threshold_peak_value`
- Downstream: `fmt_val` wird von `_render_html_table` + `_render_mobile_compact_rows` (Mobile) genutzt → Ampel greift in beiden. Plain-Text-Mail (`plain.py`) hat keine Farben → unberührt.

## Existing Specs
- `docs/specs/modules/issue_240_email_design_tokens.md` — Design-Tokens
- `docs/specs/modules/weather_config.md` — MetricCatalog

## Risks & Considerations
- **#759 Produkt-Entscheidung offen:** Tint-auf-Zahl (Wert bleibt) vs. reine Symbol-Ampel (🟢🟡🔴, Wert weg). „Einfache Darstellung" ist mehrdeutig → PO-Klärung.
- **#759 Schwellen für Regen/Regenwahrscheinlichkeit** haben heute nur 1 Risk-Stufe → 2-Stufen-Ampel braucht eine zweite Schwelle (Vorschlag aus Risk-Werten ableiten).
- **Outlook (Outlook.com)** ignoriert CSS-Variablen → nur inline-Hex (Pattern existiert bereits).
- Mobile-Compact-Grid (`_render_mobile_compact_rows`) nutzt `html=False` → bekommt aktuell KEINE Tints; Ampel müsste dort separat gedacht werden (Monospace-Grid).
- Plain-Text-Mail bleibt unberührt (keine Farbe).

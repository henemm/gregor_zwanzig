# Context: Issue #810 — Format-Modus 'Roh' wirkungslos für Wind/Böen/Regen in HTML-Briefing

## Request Summary
Stellt der Nutzer Wind/Böen/Regen(/Regenwahrscheinlichkeit) auf Format **„Roh"** (`use_friendly_format=false`), zeigt die HTML-Briefing-Mail trotzdem die 4-stufigen Ampelpunkte 🟢🟡🟠🔴 (eingeführt #759) statt der rohen Zahlenwerte. Bug grundsätzlich an der Quelle fixen, Code sauber halten.

## Root Cause (verifiziert)
`src/output/renderers/email/helpers.py::fmt_val` — drei Stellen geben im HTML-Pfad `ampel_dot(...)` **unbedingt** zurück, VOR jeder `use_friendly`-Prüfung:
- Z.446–448 `wind`/`gust`: `if html: return ampel_dot(...)` → raw-Zahl-Pfad (`s = f"{val:.0f}"` + Kompass) im HTML nie erreicht.
- Z.459–461 `precip`: `if html: return ampel_dot(...)` → `return f"{val:.1f}"` nie erreicht.
- Z.500–501 `pop`: `if html: return ampel_dot(...)` → `return f"{val:.0f}"` nie erreicht.

`use_friendly` wird Z.428 korrekt berechnet (`(mode is not None and mode != "raw") or (mode is None and key in friendly_keys)`), aber für diese 3 Keys nicht konsultiert.

## Korrekt-Vorbilder im selben File
- `cloud` (Z.465 ff.): `if not use_friendly: return f"{val:.0f}"`
- `sunshine` (Z.481 ff.): `if not use_friendly: ... return f"{hours:.1f} h"`
- `cape` (Z.504 ff.) / `visibility` (Z.520 ff.): `if not use_friendly:` zuerst.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py` | `fmt_val` — die 3 Bug-Stellen (Fix hier) |
| `src/output/renderers/email/html.py` | Ruft `fmt_val(html=True/False, format_modes=...)` für Tabelle + mobile-compact |
| `src/output/renderers/email/__init__.py` | `build_format_modes(display_config)` → `format_modes` |

## Fix-Richtung (saubere Quelle)
`if html:` → `if html and use_friendly:` für wind/gust, precip, pop. Fall-through liefert dann den bereits existierenden raw-Zahl-Pfad (auch im HTML). Plain-Part ist bereits raw — nur HTML betroffen. ~3 Zeilen.

## Dependencies
- Upstream: `get_metric(...).display_thresholds`, `_AMPEL_KEY_TO_METRIC_ID`, `ampel_dot`
- Downstream: HTML-Tabelle + mobile-compact-Zeilen der Trip-Briefing-Mail

## Risks & Considerations
- Default (Einfach/indicator) MUSS weiterhin Ampel zeigen → nur der `not use_friendly`-Fall ändert sich (Regress-Schutz nötig).
- SMS/Plain unverändert.
- Gegenprobe: `use_friendly=True` → Ampel bleibt; `=False` → Zahl.

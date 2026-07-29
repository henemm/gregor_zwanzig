# Context: fix-1414-wind-boeen-spalten

## Request Summary

Issue #1414 meldete, dass in der HTML-Stundentabelle der Trip-Briefing-Mail alle
32 Wind- und alle 32 Boeen-Zellen leer bleiben, obwohl der Klartext-Block
derselben Mail Stundenwerte nennt (max 15 km/h Wind, max 41 km/h Boeen).

**Ergebnis der Kontextphase: kein Fehlverhalten.** Die Zellen sind nicht leer,
sie enthalten den seit #759/#1222 vorgesehenen Ampel-Punkt. Der Befund entstand
durch Messung des Zell-*Textinhalts*; der Punkt ist reines CSS-Markup ohne Text.

## Nachweis (echte Staging-Mail, IMAP `gregor-test@henemm.com`, 2026-07-28 23:01 UTC)

Trip `staging-validator-rolling`, Report `evening`, `X-GZ-Mail-Type: trip-briefing`,
`X-GZ-Format: full`:

| Spalte | Zellen | Inhalt |
|---|---|---|
| Wind | 32 | 32x gruener Ampel-Punkt (`#15803d`), Textinhalt leer |
| Gust | 32 | 30x gruen, 2x gelb (`#ca8a04`), Textinhalt leer |

Die Golden-Fixtures im Repo (`tests/golden/email/*-html.txt`) zeigen dasselbe
Markup — der Zustand ist also weder neu noch durch #1357 (`07fe4641`, hat die
Stundentabelle nicht angefasst) oder #1377 (`dbbb30fb`, nur Ampel-Schwellen)
entstanden.

## Warum das so gewollt ist

Die Darstellung je Wettergroesse ist **nutzergesteuert** (Roh vs. Einfach,
`use_friendly_format` je Metrik):

- **Roh** → Zahl, kein Ampel-Punkt
- **Einfach** (Voreinstellung, `getattr(mc, "use_friendly_format", True)`) → Ampel-Punkt

Der Testtrip hat eine leere `display_config` (`{}`) und laeuft damit auf der
Voreinstellung „Einfach".

Belegt durch gruene Bestandstests (64 Tests, Lauf 2026-07-29):
`tests/tdd/test_issue_810_raw_format_ampel.py` (u.a.
`test_issue810_wind_raw_shows_number_no_ampel`,
`test_issue810_wind_simplified_still_ampel`),
`tests/tdd/test_issue_811_mode_matrix.py`, `tests/tdd/test_ampel_css_dots.py`.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py:591` | `fmt_val()` — Zellformatierung; Wind/Boeen-Zweig 652-667 |
| `src/output/renderers/email/helpers.py:542` | `_ampel_dot_severity()` — liefert reinen CSS-Punkt ohne Text |
| `src/output/renderers/email/helpers.py:491` | `_ampel_dot_css()` — `<span>` ohne Textinhalt |
| `src/output/renderers/email/helpers.py:1006` | `build_html_indicator_keys()` — Default `use_friendly_format=True` |
| `src/output/renderers/email/html.py:588-628` | Zell-Toenung je Ampel-Level (unabhaengig vom Punkt, erst ab gelb) |
| `src/app/metric_catalog.py:154,170` | Katalogeintraege `wind`/`gust` — Keys konsistent, keine Namensabweichung |

## Nebenbefund

Die Verifikations-/Pruefmechanik misst Ampel-Zellen als „leer", weil sie nur den
Textinhalt liest. Das hat den Fehlalarm ausgeloest und wird ohne Anpassung
wiederkehren. Kein blockierendes Gate → Sammel-Eintrag #1199, kein eigenes Issue.

## Outcome

Kein Code-Change. Issue #1414 als „kein Fehler" geschlossen, Workflow beendet.

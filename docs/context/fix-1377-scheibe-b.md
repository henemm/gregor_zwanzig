# Context: fix-1377-scheibe-b

## Request Summary

Issue #1377 Scheibe B: Die Renderer sollen ihre eigenen Ampel-Schwellen aufgeben
und dem zentralen Katalog folgen, den Scheibe A (`dbbb30fb`) zur einzigen Quelle
gemacht hat. Ziel: gleiche Vorhersage ⇒ gleiche Warnfarbe in Trip-Briefing und
Ortsvergleich.

## Ausgangslage: wer heute welche Schwellen führt

| Groesse | Trip-Zelle `html.py:615-628` | Ausblick `outlook.py:197-200` | Vergleich `compare_html.py:88-123` | Katalog (Ziel) |
|---|---|---|---|---|
| Regen mm | >1 / >4 / >8 | ≥2 / ≥5 / ≥8 | >1 / >4 / >8 | **1 / 5 / 10** |
| Regenwahrsch. % | >50 / >70 / >85 | ≥50 / ≥70 / ≥85 | ≥40 / ≥60 / ≥80 | **30 / 60 / 80** |
| Wind km/h | >20 / >30 (2-stufig) | ≥20 / ≥30 | bereits Katalog | **30 / 50 / 70** |
| Boeen km/h | >30 / >45 / >60 | ≥30 / ≥45 / ≥60 | >30 / >45 / >60 | 30 / 45 / 60 (deckungsgleich) |
| Sichtweite | <2 / <1 / <0,5 km | — | <5000 / <3000 / <1000 m | **2000 / 1000 / 500 m** |
| UV-Index | — | — | ≥3 / ≥6 / ≥8 | 3 / 6 / 8 (deckungsgleich) |
| Temperatur | neutral (Kachel) | — | ≥28 / ≥31 / ≥34 | 28/31/34 **+ Kaelte 0/-5/-15** |
| Gewitter | >0 / >20 / >30 | MED/HIGH-Map | eigene Stufen | **keine Schwellen** |

Fett = sichtbare Aenderung in der Mail. Gewitter ist laut Issue ausdruecklich
NICHT Teil von #1377 (Datenform-Divergenz `thunder_pct` vs. Stufen → #1372) und
muss von der Umstellung ausgenommen bleiben — der Katalog fuehrt fuer `thunder`
keine `display_thresholds`, eine naive Umstellung wuerde die Faerbung ersatzlos
verlieren.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/metric_format.py:104` | `severity_for(metric_id, value)` — Ziel-API, Rueckgabe green/yellow/orange/red oder None |
| `src/output/metric_format.py:115-172` | `severity_from_thresholds(thresholds, value)` — SSoT aus Scheibe A; **Argumentreihenfolge invers** zu `helpers._level_from_thresholds(value, thresholds)` |
| `src/output/renderers/email/design_tokens.py:67-89` | `tone_css(level) -> (bg, fg)`; kennt NUR green/yellow/orange/red, sonst `KeyError` |
| `src/output/renderers/email/html.py:596-628` | Zell-Toenung; Zeilen 604-612 bereits katalogbasiert, 615-628 hartcodierter Rest |
| `src/output/renderers/email/html.py:147-168` | `_row_risk` + `_RISK_DOT_COLORS` — drittes Vokabular `ok/watch/risk`, kein Unit-Test |
| `src/output/renderers/email/outlook.py:57-73,197-201` | `_outlook_cell_bg` generisch + vier hartcodierte Schwellen-Tupel |
| `src/output/renderers/email/compare_html.py:62-63,88-123` | Vokabular-Uebersetzung + acht `_sev_*`; `_sev_wind`/`_sev_cape` bereits migriert |
| `src/output/renderers/email/helpers.py:1340-1444` | `_pill_for_metric` — Klasse-2-Neutralitaet (Punkt 5 der Restliste) |
| `src/app/metric_catalog.py` | 9 Metriken MIT `display_thresholds`, 15 OHNE |

## Existing Patterns

- **Migration ist zweimal vorgemacht:** `_sev_wind` (`compare_html.py:92-98`) und
  `_sev_cape` (`:122-123`) rufen bereits `severity_for` — inklusive
  Regressionstests (`tests/tdd/test_compare_wind_severity_regression.py`,
  `test_compare_cape_severity_ampel.py`). Das ist die Vorlage fuer die uebrigen.
- **`None`-Kontrakt (#1214/#1377 F001):** keine Schwellen ⇒ `None` ⇒ keine
  Aussage, nie ein stilles „green". Muss beim Anschluss neuer Metriken bewusst
  behandelt werden.
- **Golden-Regenerierung:** `uv run python3 tests/golden/email/regenerate.py`,
  danach `git diff` sichtpruefen und `uv run pytest tests/golden/email/` **zweimal**
  grün (Byte-Stabilitaet).

## Dependencies

- **Upstream:** `metric_catalog.display_thresholds` → `severity_from_thresholds`
  → `severity_for` / `helpers.ampel_level`; `design_tokens.tone_css`.
- **Downstream:** `_render_html_table` (Aufrufer `html.py:687,965,1015,1061`),
  `render_outlook_table` (Aufrufer `html.py:1117` Trip, `compare_html.py:906`
  Compare), `build_metrics_summary_pills` (Aufrufer `html.py:1179`,
  `plain.py:170`, `compact.py:156`).

## Existing Specs

- `docs/specs/modules/ampel_schwellen_katalog.md` — Scheibe A
- `docs/specs/modules/briefing_mail_inhalt.md`, `briefing_mail_validator.md`

## Risks & Considerations

1. **Die Umstellung ist NICHT unsichtbar.** Vier Groessen aendern ihre Faerbung
   (Regen, Regenwahrscheinlichkeit, Wind, Sichtweite im Vergleich). Die
   PO-Auflage aus #1377 („abweichende Groessen einzeln vorlegen") gilt erneut,
   weil Scheibe A fuer genau diese vier Groessen nichts festgelegt hat.
2. **`tone_css` ist nicht wertgleich, nur teilweise.** Die Hintergruende
   gelb/orange/rot stimmen exakt (`#fbeeb8`/`#fad6b8`/`#f6c5bf`). Aber: `tone_css`
   kennt zusaetzlich **green** (`#dbeadd`) — heute wird gruen gar nicht getoent —
   und liefert eine **Vordergrundfarbe**, die heute nicht gesetzt wird. Naive
   Uebernahme = sichtbare Aenderung. Vorgabe: nur `[0]` (bg) verwenden, green
   weiterhin ungetoent.
3. **Vier Vokabulare, nicht zwei.** Neben `green/yellow/orange/red` (Trip) und
   `ok/caution/warn/danger` (Vergleich) existieren `ok/watch/risk` (`_row_risk`)
   und `ok/warn/risk/info` (`_PILL_TAG_PALETTE`, `helpers.py:1086-1095`). Alle
   rein intern, nie im Markup → Umbenennung ohne Golden-Diff moeglich.
4. **Gewitter ausnehmen** (s.o.) — sonst Verlust der Faerbung.
5. **`_row_risk` hat keinen Unit-Test** — nur indirekt ueber Golden-Snapshots
   abgedeckt. Vor Umbau Test nachziehen.
6. **Parity-Tests brechen mit:** `test_shared_outlook_renderer.py` und
   `test_trip_outlook_parity.py` pruefen Byte-Identitaet, nicht Semantik — sie
   schlagen bei jeder Schwellenaenderung fehl und muessen mitgezogen werden.
7. **Zusatzfundstellen ueber das Issue hinaus:** `html.py:243-245` (Hero-/Mobil-
   Stundenliste, dieselben Schwellen ein drittes Mal), `html.py:1091-1107`
   (`_confidence_dot_color`, Duplikat zu `outlook._acc_dot` mit ANDEREN Stufen
   und ANDERER Palette), `helpers.py:838-841` (Wind 30/50). Scope-Entscheidung
   noetig: mitnehmen oder als Restliste fuehren.
8. **LoC-Limit 250** — vier Renderer plus Tests plus Golden. Aufteilung in
   Teilscheiben pruefen, bevor das Limit reisst.
9. **`_COL_KEY_TO_METRIC_ID` (html.py:552, lokal) und `_AMPEL_KEY_TO_METRIC_ID`
   (helpers.py:579) sind redundante Teilkopien** von
   `metric_catalog.get_metric_by_col_key` und weichen voneinander ab (`cape`
   fehlt in helpers). Ablœsung moeglich; Unschaerfe: `html.py:625` behandelt
   `vis` UND `visibility`, der Katalog kennt nur `visibility`.

## Testabdeckung heute

- Zell-Toenung: `tests/test_ampel_schwellen_katalog.py`, `test_issue_795_briefing_quality.py`, `test_fix_911_visual_table.py`, `test_issue_911_mail_details.py`
- `_row_risk`: **kein direkter Test**
- Ausblick: `test_shared_outlook_renderer.py`, `test_trip_outlook_parity.py`, `test_compare_outlook.py`
- Vergleich `_sev_*`: `test_compare_wind_severity_regression.py`, `test_compare_cape_severity_ampel.py`, `test_official_alert_badge_color.py`
- Golden HTML (5 Dateien): `arlberg-winter-morning`, `corsica-vigilance`, `gr20-spring-morning`, `gr20-summer-evening`, `gr221-mallorca-evening`

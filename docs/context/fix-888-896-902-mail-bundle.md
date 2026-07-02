# Context: fix-888-896-902-mail-bundle

## Request Summary

Bundle aus drei Adversary-Nebenbefunden im Briefing-Mail-Umfeld: (#888) Ampel-Emoji und
Threshold-Highlighting senden widersprüchliche Signale in derselben Tabellenzelle,
(#896) die Vortags-Zeilen-Salienz hängt an `default_change_threshold` und ist seit #889
für Vorboten-Metriken zu niedrig, (#902) Outlook-Desktop verliert die Spaltenlinien der
Datenzellen, weil diese bewusst keine Inline-Borders tragen (Test-Regex-Kontrakt).

## Stand-Abgleich (wichtig!)

**#888 beschreibt einen veralteten Codestand.** Das `color:#c2410c`-Text-Wrapping existiert
seit dem #956-Umbau nicht mehr (PO-Entscheidung „keine farbigen Text-Spans", Kommentar
`html.py:531-534`). Der Konflikt besteht aber weiterhin in neuer Form — **verifiziert am
2026-07-02 (HEAD 4dbb4535)**:

```
_render_html_table([{'time':'08:00','wind':25.0}], friendly_keys=set(),
                   format_modes={'wind':'raw'}, indicator_keys={'wind'})
→ Wind-Zelle: <span style="display:block;background:#fbeeb8;…">🟢</span>
```

🟢 (Ampel: sicher, Katalog-`display_thresholds`) auf gelbem Warn-Hintergrund (hartcodierte
`_WIND_THRESHOLD=20.0`). Zwei entkoppelte Schwellensysteme, ein Widerspruch.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py:455-580` | `_render_html_table`: Zell-Rendering, cell_bg-Tönung (`:531-564`), hartcodierte Schwellen (`:496-501`), data-label-td ohne Inline-Style (`:565`), Time-Zelle mit Inline-Style (`:519`), `_td_grid` (`:510`) |
| `src/output/renderers/email/html.py:1432-1453` | `<style>`-Block mit td-Border-Regeln — Outlook strippt diese (#902) |
| `src/output/renderers/email/helpers.py:371-394` | `ampel_dot`: Emoji-Erzeugung aus Katalog-`display_thresholds` — kennt Threshold-Level bereits |
| `src/output/renderers/email/helpers.py:410-535` | `fmt_val`: `_use_ampel`-Dispatch (`:443-446`), Ampel-Pfade wind/gust/precip/pop/cape |
| `src/output/renderers/email/helpers.py:797-834` | `build_format_modes` / `build_html_indicator_keys` (`_AMPEL_CAPABLE_METRIC_IDS` `:814`) |
| `src/output/renderers/email/__init__.py:93-125` | `render_html`: Parameter-Erzeugung + Durchreichen |
| `src/services/day_comparison.py:229-301` | `_SALIENCE_FACTOR=0.6` (`:229`), `_get_threshold` (`:232-245`), Relevanzfilter `abs(avg) >= thr` (`:278-280`) — #896 |
| `src/app/metric_catalog.py` | `default_change_threshold`: seit #889 `None` für humidity(:123), cloud_total(:295), pressure(:386), wind_chill(:110), dewpoint(:135); rain_probability=20.0(:209) |
| `tests/tdd/test_issue_759_email_ampel.py:294` | Strikter Extraktions-Regex `<td data-label="[^"]*">` — bricht bei Inline-Styles (#902) |
| `tests/tdd/test_issue_811_mode_matrix.py:144,574` | Gleicher strikter Regex, 2 Stellen; Datei ist Renderer-Commit-Gate-Nachweis |

## Existing Patterns

- Ampel-Emojis beziehen ihre Stufen (🟢🟡🟠🔴) aus dem Metrik-Katalog (`display_thresholds`) —
  Single Source für Schwellen, konsistent mit ADR-0011-Denkweise (Registry als Single Source).
- Die cell_bg-Tönung nutzt dagegen **eigene hartcodierte** Schwellen (`_WIND_THRESHOLD` etc.) —
  historisch gewachsen, Duplikat-Schwellenquelle.
- Outlook-Kompatibilität wird im Renderer bereits per Inline-Styles gelöst (Time-Zelle,
  Header, `_td_grid`); nur die data-label-Zellen sind ausgenommen — wegen des Test-Regex-Kontrakts
  (Kommentar `html.py:514-517, 559`).
- Hook-Validatoren (`briefing_mail_validator.py:127`, `email_spec_validator.py:128`) nutzen
  tolerante Regexes (`<td[^>]*>`) — **brechen nicht** bei Inline-Styles auf Datenzellen.

## Dependencies

- **Upstream:** `metric_catalog.get_metric` (display_thresholds, default_change_threshold),
  `DisplayConfig` (use_friendly_format, metrics).
- **Downstream (#902-Kontrakt):** test_759:294, test_811:144+574 (strikte data-label-Regexes);
  `test_issue_811_mode_matrix.py` ist zugleich Pflicht-Nachweis des un-überspringbaren
  Renderer-Commit-Gates (`renderer_mail_gate.py`) — Regex-Änderung dort muss zusammen mit
  Renderer-Änderung grün werden.
- **Downstream (#896):** Vortags-Vergleichstext in HTML- und Plain-Mail
  (`html.py:1272-1276`, `plain.py:129-130`).

## Existing Specs

- `docs/specs/tests/issue_814_ampel_einfach_roh_tests.md` + `issue_759_669_email_ampel_gewitter_tests.md` — Ampel/Einfach-Modus (#888)
- `docs/specs/tests/issue_811_mail_quality_gate_tests.md` — Mode-Matrix-Gate (#902)
- `docs/specs/tests/bug_838_day_comparison_kwarg_tests.md` — day_comparison (#896)
- ADR-0010 (`docs/adr/0010-vorboten-metriken-kein-alert-ausloeser.md`) — Grund für `None`-Thresholds (#896)
- ADR-0011 — Single-Source-Renderer-Prinzip

## Risks & Considerations

- **#888:** Fix-Richtung ist eine Design-Entscheidung: (a) cell_bg unterdrücken wenn Zelle
  Ampel-Indikator ist (eine Schwellenquelle gewinnt — minimal-invasiv), oder (b) cell_bg an
  Katalog-Schwellen koppeln (größerer Umbau). Empfehlung: (a).
- **#896:** Fallback 3.0 ist für %-Metriken (humidity, cloud_total) viel zu niedrig →
  Vortags-Zeile wird geschwätzig. Eigene Salienz-Tabelle stellt Verhalten von vor #889 wieder
  her (humidity 12.0, rain_probability 12.0, cloud_total 18.0, pressure 6.0). Die Salienz-Logik
  ist derzeit **ungetestet** — kein Test ruft `_get_threshold` direkt.
- **#902:** Regex-Anpassung in test_811/test_759 verändert Gate-Testcode — legitim, weil das
  Issue genau das vorsieht; muss aber im selben Commit wie die Renderer-Änderung grün sein
  (Renderer-Gate verlangt frischen Matrix-Nachweis + Validator-Lauf gegen Staging-Mail).
- Mail-Pfad-Regel: Nach Push Staging-Mail per `briefing_mail_validator.py` (Exit 0) verifizieren,
  echte Mail Zahl-für-Zahl prüfen (Memory-Regel).
- Nutzen von #902 ist bewusst klein (Zielgruppe liest mobil) — Aufwand minimal halten.

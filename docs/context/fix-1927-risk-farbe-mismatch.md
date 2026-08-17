# Context: fix-1927-risk-farbe-mismatch

## Request Summary
Issue #1927: In der Trip-E-Mail-Stundentabelle wirkt die Farbe des "Risk"-Punkts am
Zeilenende nicht stimmig zum Warn-Level der übrigen Ampel-Spalten (z. B. Thdr). Gemeldet
anhand eines Screenshots aus der heutigen 7:05-Mail, Etappe 10, SEG 4 (Stunde 12: Thdr=MED,
Risk-Punkt sichtbar rot statt der erwarteten mittleren Farbe).

## Root Cause (bestätigt, ΔE76 nachgerechnet)
Zwei unabhängige Farbpaletten für dieselbe 3/4-stufige Ampel-Bedeutung im selben Report:

| Palette | Datei | Level → Hex |
|---|---|---|
| `_AMPEL_DOT_COLORS` (Spalten Thdr/Wind/Gust/Rain/Rain%) | `src/output/renderers/email/helpers.py:588-593` | green `#15803d`, yellow `#d69500`, orange `#d4530a`, red `#a8104a` |
| `_RISK_DOT_COLORS` (Risk-Spalte, Zeilenende) | `src/output/renderers/email/html.py:236-239` | ok `#15803d`, watch `#c2410c`, risk `#b91c1c` |

Fix #1801 (PO-Entscheid 2026-08-14, Commit `6d54fee1`) hat den Orange↔Rot-Abstand der
`_AMPEL_DOT_COLORS`-Palette bewusst von ΔE76 16,4 auf 54,4 vergrößert, damit beide Farben in
einem kleinen Punkt klar unterscheidbar sind. `_RISK_DOT_COLORS` wurde dabei laut
Commit-Kommentar ausdrücklich als "Nicht-Ziel" ausgenommen und blieb auf der **alten, zu
engen** Distanz: `watch` (#c2410c) vs. `risk` (#b91c1c) = ΔE76 **16,4** — numerisch identisch
mit dem Wert, den #1801 für die anderen Spalten gerade als "zu eng, nicht unterscheidbar"
korrigiert hat.

**Zusätzlich, unabhängig gefunden:** `_row_risk()` (`html.py:214`) liest `r.get("vis")`, der
Katalog-Spalten-Key für Sichtweite heißt aber `"visibility"` (`metric_catalog.py:556`) —
Sichtweite fließt dadurch nie in die Risk-Berechnung ein (Default 99 km → immer "green"-Beitrag).
Wirkt Richtung "zu grün", nicht "zu rot" — erklärt NICHT den gemeldeten Fall, ist aber ein
echter Bug in derselben Funktion und wird im selben Zug mitbehoben.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py:200-232` | `_row_risk()` — Severity-Berechnung (Logik korrekt, kein Bug in der Stufen-Ermittlung selbst) |
| `src/output/renderers/email/html.py:214` | `vis`/`visibility`-Key-Mismatch |
| `src/output/renderers/email/html.py:235-239` | `_RISK_DOT_COLORS` — veraltete, zu enge Palette |
| `src/output/renderers/email/html.py:143-155` | `_risk_dot()` — rendert Punkt + Ring aus `_RISK_DOT_COLORS` |
| `src/output/renderers/email/helpers.py:582-620` | `_AMPEL_DOT_COLORS` / `_ampel_dot_css()` — die per #1801 bereits korrigierte, kanonische Palette |
| `src/output/renderers/email/design_tokens.py:63-92` | `tone_css()` — SSoT für Zell-Hintergrundtönung (bereits geteilt, Vorbild für die Dot-Vereinheitlichung) |

## Existing Patterns
- Fix #1801 S1 hat die Zell-Hintergrundfarben bereits auf eine einzige Quelle (`tone_css()`)
  vereinheitlicht ("statt vier lokaler Hex-Kopien", `html.py:243-248`). Die Dot-Füllfarben
  (nicht die Zell-Hintergründe) sind aber weiterhin zweigleisig: `_AMPEL_DOT_COLORS`
  (helpers.py) für Spalten-Dots, `_RISK_DOT_COLORS` (html.py) für den Risk-Dot.
- `_row_risk` ist die einzige Aufrufstelle im ganzen Repo (`html.py:849`); kein zweiter
  Berechnungspfad aktiv. `_render_mobile_hour_list` (html.py) und `compute_stage_weather`
  (`src/services/stage_weather.py`) sind toter Code ohne Aufrufer — nicht Teil des Fixes.

## Dependencies
- Upstream: `severity_for()`/`metric_catalog.py`-Schwellen (unverändert korrekt),
  `_thunder_risk_level()` (unverändert korrekt, per #1418 bereits gehärtet).
- Downstream: nur die visuelle Darstellung der Trip-E-Mail (HTML-Renderer). Keine
  Alarm-/Versandlogik betroffen.

## Existing Specs
- `docs/specs/modules/fix_1418_gewitter_risikopunkt.md` — Ursprungs-Spec der `_row_risk`-Logik.
- Kein bestehendes Spec-Dokument für die Dot-Farbpalette selbst; #1801 lief vermutlich als
  Fast-Track ohne Vollspec (zu prüfen, aber nicht blockierend).

## Risks & Considerations
- Palette-Vereinheitlichung darf die bereits bestehenden Golden-Snapshot-/Renderer-Tests für
  die Risk-Spalte nicht durch reine Hex-Wert-Änderung rot werden lassen, ohne dass die Tests
  bewusst nachgezogen werden (Snapshot-Tests sind zulässiger Kollateralschaden bei einer
  gewollten visuellen Änderung, aber die Änderung muss im Test sichtbar/benannt sein).
- Sauberste Lösung: `_RISK_DOT_COLORS` entfällt zugunsten von `_AMPEL_DOT_COLORS`/derselben
  Quelle (SSoT, analog `tone_css()`) statt nur die Hex-Werte zu kopieren — vermeidet erneutes
  Auseinanderlaufen bei der nächsten Farbanpassung.
- `vis`/`visibility`-Fix ist unabhängig und sollte nicht mit dem Farb-Fix vermischt diskutiert
  werden (zwei separate ACs in der Spec).

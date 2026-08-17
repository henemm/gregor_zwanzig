---
entity_id: fix_1927_risk_dot_farbpalette
type: module
created: 2026-08-17
updated: 2026-08-17
status: implemented
version: "1.0"
tags: [email-renderer, risk-dot, farbpalette, bugfix]
---

# Risk-Dot-Farbpalette in Trip-E-Mail vereinheitlichen (Issue #1927)

## Approval

- [x] Approved — PO „go" 2026-08-17

## Purpose

In der Trip-E-Mail-Stundentabelle hat die Risk-Spalte (letzte Spalte, Zeilenende) eine
eigene, veraltete Farbpalette (`_RISK_DOT_COLORS`), die vom Fix #1801 (PO-Entscheid
2026-08-14) ausdrücklich ausgenommen wurde. Dadurch bleibt der Orange↔Rot-Abstand der
Risk-Spalte bei ΔE76 16,4 — demselben Wert, den #1801 für die übrigen Ampel-Spalten
(Thdr/Wind/Gust/Rain/Rain%) gerade als "nicht unterscheidbar" korrigiert hat (dort jetzt
ΔE76 54,4). Ergebnis: der Risk-Punkt wirkt bei mittlerer Warnstufe optisch wie "rot" statt
"mittel/orange" — genau der vom Nutzer gemeldete Fall (Etappe 10, SEG 4, Stunde 12,
Thdr=MED). Diese Spec vereinheitlicht die Risk-Dot-Farbgebung auf dieselbe Quelle wie die
übrigen Ampel-Spalten (SSoT) und behebt zusätzlich einen unabhängig gefundenen
Schlüssel-Mismatch (`vis` statt `visibility`), der die Sichtweite komplett aus der
Risk-Berechnung ausschließt.

## Source

- **File:** `src/output/renderers/email/html.py`
  - **Identifier:** `_RISK_DOT_COLORS` (Zeile 235-239) — veraltete, eigene Palette
  - **Identifier:** `_risk_dot()` (Zeile 143-155) — rendert Dot + Ring, `ring_map` dort
    ebenfalls hartcodiert als dritte Farb-Kopie
  - **Identifier:** `_row_risk()` (Zeile 200-232) — Severity-Berechnung; Bug bei Zeile 214
    (`r.get("vis")`)
  - **Aufrufstelle:** Zeile 849 (`_dot_color = _RISK_DOT_COLORS[_row_risk(r)][0]`, innerhalb
    `_render_html_table()`, Zeile 668-875 — der einzige produktive Aufrufpfad; `_row_risk`
    hat laut Analyse keinen zweiten Aufrufer im Repo)
- **File:** `src/output/renderers/email/helpers.py`
  - **Identifier:** `_AMPEL_DOT_COLORS` (Zeile 588-593) — kanonische, per #1801 bereits
    korrigierte Palette (green/yellow/orange/red), Ziel-SSoT dieser Spec

> **Schicht-Hinweis:** Beide Dateien liegen im Python-Core (`src/output/renderers/email/`,
> FastAPI-Backend-Renderer für die Trip-Briefing-E-Mail). Keine Go-API-, Frontend- oder
> Alarm-/Versandlogik betroffen — reine Darstellungsschicht des HTML-Renderers.

## Estimated Scope

- **LoC:** ~25-35 Produktivcode (Umbau zweier Dicts + eine Zeile Key-Fix + Import) + ~40-60
  Testcode (zwei neue, benannte Testdateien mit je 2-3 Fällen)
- **Files:** 2 Produktivdateien (`html.py`, `helpers.py` nur ggf. Export-Sichtbarkeit, keine
  inhaltliche Änderung an `_AMPEL_DOT_COLORS` selbst nötig) + 2 neue Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_AMPEL_DOT_COLORS` (`helpers.py:588-593`) | Datenquelle | Kanonische Ampel-Farbpalette (green/yellow/orange/red), wird zur einzigen Quelle für Dot-Füllfarben |
| `severity_for("visibility", ...)` / `metric_catalog.py:556` (`col_key="visibility"`, `display_thresholds={yellow_lt:2000, orange_lt:1000, red_lt:500}`) | Datenquelle | Bestätigt den korrekten Row-Key `"visibility"` und die Schwellen für AC-2 |
| `design_tokens.tone_css()` (`design_tokens.py:63-92`) | Vorbild-Pattern | SSoT-Vorbild für Zell-Hintergründe (Fix #1801 S1) — analoges Muster, nicht direkt wiederverwendbar für Dot-Füllfarben (andere Werteform: Hex+Ring-RGBA statt CSS-Klasse) |
| `tests/tdd/test_row_risk_gewitter.py` | Bestandstest | Nutzt Fixture-Key `"vis"` (Zeile 26: `_HARMLESS = {..., "vis": 20000.0}`) — bleibt nach dem Key-Fix technisch grün (visibility fällt dann auf den Default 99 km zurück, ebenfalls "green"-Beitrag), ist aber ab jetzt ein irreführendes Fixture. Empfehlung: bei Gelegenheit auf `"visibility"` umbenennen (kein Teil dieser Spec, da nicht bugauslösend). |

## Implementation Details

```
1) _RISK_DOT_COLORS (html.py:235-239) entfällt. Die Risk-Spalte bezieht Fuellfarbe
   UND Ring-Farbe aus _AMPEL_DOT_COLORS (helpers.py), importiert analog zum bereits
   bestehenden Import von _HAIL_RING_COLOR (html.py:37).

2) Mapping vom dreiwertigen Risk-Vokabular auf die vierwertige Ampel-Palette (_row_risk
   liefert "ok"/"watch"/"risk", _AMPEL_DOT_COLORS kennt "green"/"yellow"/"orange"/"red"):
     ok    -> "green"   (#15803d, unveraendert)
     watch -> "orange"  (#d4530a) -- DESIGN-ENTSCHEIDUNG, s. unten
     risk  -> "red"     (#a8104a, ersetzt das bisherige #b91c1c)
   Diese Zuordnung darf als eigene, benannte Konstante (z.B. ein dict) im
   Produktivcode stehen -- Name/Form ist Implementierungsdetail, nicht Teil der ACs.

3) _risk_dot()'s hartcodierter ring_map (html.py:145-149, dritte Farb-Kopie) entfaellt
   zugunsten einer Ableitung aus _AMPEL_DOT_COLORS.values() (fill -> ring), damit Fuell-
   und Ringfarbe nicht erneut auseinanderlaufen koennen.

4) _row_risk() Zeile 214: r.get("vis") -> r.get("visibility") (Katalog-col_key,
   metric_catalog.py:556).

5) _render_mobile_hour_list() (html.py:278-431, inkl. der _risk_dot()-Aufrufstelle
   Zeile 392 und ihrer lokalen risk_color-Farbtabelle Zeile 339) ist toter Code ohne
   Aufrufer im Repo -- AUSSERHALB des Scopes dieser Spec. Falls dort dieselbe alte
   Farbtabelle stehen bleibt, ist das kein Regressions-Risiko (nie ausgefuehrt).
```

## Design-Entscheidung: "watch" -> orange (nicht yellow)

`_row_risk()` bildet `worst in ("yellow", "orange")` beide Ampel-Einzelstufen auf
`"watch"` ab — es gibt keine 1:1-Entsprechung zwischen dem dreiwertigen RiskDot-Vokabular
und der vierwertigen Ampel-Palette. Für die Farbe von `"watch"` muss zwischen
`_AMPEL_DOT_COLORS["yellow"]` (#d69500) und `_AMPEL_DOT_COLORS["orange"]` (#d4530a)
gewählt werden.

**Empfehlung dieser Spec: `orange` (#d4530a).** Begründung: `"watch"` wird sowohl von
einzelnen yellow- als auch orange-Metriken ausgelöst UND zusätzlich von
Gewitter-MED/LOW (`_thunder_risk_level`). Die schärfere der beiden Nachbarfarben ist die
sicherere Wahl, um eine echte Warnung nicht optisch zu verwässern — ein Nutzer, der den
Risk-Punkt als alleinigen Schnellindikator liest (ohne die Einzelspalten zu prüfen), soll
im Zweifel eher zu vorsichtig als zu sorglos gewarnt werden.

**Dies ist eine Design-Entscheidung, keine Code-Mechanik — der PO prüft und bestätigt sie
explizit bei der Spec-Freigabe** (ggf. Korrektur auf `yellow`, falls gewünscht).

## Expected Behavior

- **Input:** Eine Tabellenzeile (`dict`) mit Metrikwerten (`wind`, `gust`, `precip`, `pop`,
  `visibility`, `thunder`), wie sie `_render_html_table()` pro Stunde übergeben wird.
- **Output:** Der gerenderte `<td>`-Risk-Dot am Zeilenende trägt exakt die Hex-Füllfarbe
  aus `_AMPEL_DOT_COLORS`, gemäß der Zuordnung `ok→green`, `watch→orange`, `risk→red` —
  identisch zu den Farben, die dieselbe Stufe in den übrigen Ampel-Spalten der Zeile
  bekäme. Sichtweite (`visibility`-Feld, Meter) fließt korrekt in die
  Risk-Level-Berechnung ein.
- **Side effects:** Keine. Reine Darstellungsänderung, keine Alarm-/Versandlogik, keine
  Persistenzänderung.

## Acceptance Criteria

- **AC-1:** Given eine Tabellenzeile, deren berechneter Risk-Level `"watch"` ist (z. B.
  `wind`/`gust`/`precip`/`pop` harmlos-grün, `thunder="MED"` — löst laut `_row_risk` genau
  `"watch"` aus) / When die Zeile über den produktiven Renderpfad
  (`_render_html_table([row], ...)` bzw. direkt `_risk_dot()` mit der aus `_row_risk()`
  abgeleiteten Füllfarbe) gerendert wird / Then enthält der resultierende HTML-Dot-Span
  exakt `background:#d4530a` (dieselbe Hex-Farbe wie `_AMPEL_DOT_COLORS["orange"][0]`) und
  **nicht** mehr die alte Farbe `#c2410c`. Eine zweite Zeile mit Risk-Level `"risk"`
  (z. B. `thunder="HIGH"`) rendert `background:#a8104a` (nicht mehr `#b91c1c`) — identisch
  zur `red`-Farbe der übrigen Ampel-Spalten.
  - Test: Neue Datei `tests/tdd/test_risk_dot_matches_ampel_palette.py`. Ruft
    `_row_risk(row)` und danach den echten Rendering-Baustein `_risk_dot()`
    (bzw. `_render_html_table([row], friendly_keys=set(), indicator_keys={...})` für den
    End-to-End-Nachweis) mit fixen, harmlosen/warn-/kritischen Eingabewerten auf und prüft
    den **gerenderten HTML-String** auf die erwartete Hex-Farbe per `in`-Check auf den
    `style`-Attribut-Wert (kein Dateiinhalt-Check des Quelltexts — geprüft wird die
    Laufzeit-Ausgabe der Funktion). Assert zusätzlich, dass die alten Hex-Werte
    (`#c2410c`, `#b91c1c`) NICHT mehr im Output vorkommen (Regressionsschutz gegen ein
    stillschweigendes Wieder-Auseinanderlaufen der Paletten).

- **AC-2:** Given eine Tabellenzeile mit `visibility=200` (Meter, unterhalb der roten
  Katalog-Schwelle `red_lt=500.0`, `metric_catalog.py:556`) und allen anderen Metriken im
  harmlosen/grünen Bereich (`wind`, `gust`, `precip`, `pop` klein, `thunder="NONE"`) / When
  `_row_risk(row)` aufgerufen wird / Then ist das Ergebnis `"risk"` (Sichtweite fließt in
  die Berechnung ein) — vor dem Fix liefert dieselbe Zeile `"ok"`, weil `r.get("vis")` auf
  den Default `99.0` km zurückfällt und die tatsächliche Sichtweite nie gelesen wird.
  - Test: Neue Datei `tests/tdd/test_row_risk_reads_visibility_key.py`. Ruft `_row_risk()`
    direkt mit einer Zeile auf, die `"visibility": 200` (nicht `"vis"`) trägt, und
    assertet `== "risk"`. Ein zweiter Fall mit `"visibility": 20000` (weit, grün) bei
    sonst identischen harmlosen Werten assertet `== "ok"` (Positivkontrolle: der Test
    fängt nicht nur "irgendein Wert wird gelesen", sondern dass der tatsächliche
    Sicht-Wert das Ergebnis wirklich verschiebt — kein Test, der zufällig auch bei einem
    ignorierten Feld grün bliebe).

## Known Limitations

- `_render_mobile_hour_list()` (`html.py:278-431`) enthält eine vierte, unabhängige
  Farb-Kopie (Zeile 339: `risk_color = {"ok": "#15803d", "watch": "#c2410c", "risk":
  "#b91c1c"}`) und ruft `_risk_dot()` mit dieser alten Palette auf (Zeile 392). Die
  Funktion hat laut Repo-weiter Suche **keinen Aufrufer** — toter Code, außerhalb des
  Scopes dieser Spec. Kein Nutzerrisiko, da nie ausgeführt.
- `_confidence_dot_color()` (`html.py:1338-1354`, live, gerendert bei
  `_stage.get("confidence_pct")`) und `_RISK_LEGEND_ITEMS` (`html.py:1642-1647`, die
  RISK-Legenden-Zeile unter der Tabelle) tragen je eine **eigene, wiederum andere**
  hartcodierte Farbtabelle für dasselbe Ampel-Vokabular (`_confidence_dot_color` nutzt
  noch die alten `#c2410c`/`#b91c1c`; `_RISK_LEGEND_ITEMS` nutzt eine vierte, komplett
  andere Hex-Familie `#2f8a3e`/`#e3b008`/`#e07b1a`/`#c52a22`). Beide sind **nicht** Teil
  des gemeldeten Bugs (#1927 betrifft ausschließlich den Risk-Dot am Zeilenende der
  Stundentabelle) und werden hier **nicht** mitgeändert, um den Fix klein und gezielt zu
  halten. Nebenbefund gemäß CLAUDE.md-Triage → gehört ins Sammel-Issue #1199, kein
  eigenes Issue (kein nutzersichtbares Fehlverhalten belegt, rein kosmetische
  Inkonsistenz mit unklarem eigenem Impact).
- Bestandstest `tests/tdd/test_row_risk_gewitter.py` (Fixture-Key `"vis"`) bleibt nach
  AC-2 technisch grün, wird aber semantisch irreführend (siehe Dependencies-Tabelle) —
  kein Teil dieser Spec, da er den Bug nicht auslöst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-/Konsistenzkorrektur an bestehender Darstellungslogik
  (Vereinheitlichung zweier bereits vorhandener Farbtabellen auf eine gemeinsame Quelle,
  analog dem bereits etablierten `tone_css()`-SSoT-Muster aus Fix #1801 S1) plus ein
  einzeiliger Schlüssel-Fix. Kein neues Architekturmuster, kein neuer Kanal, keine neue
  Datenstruktur, keine Entscheidungsfläche im Sinne von `docs/adr/README.md`.

## Changelog

- 2026-08-17: Initial spec created (Issue #1927)

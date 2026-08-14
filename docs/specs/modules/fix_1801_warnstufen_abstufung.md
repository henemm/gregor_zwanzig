---
entity_id: fix_1801_warnstufen_abstufung
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: draft
workflow: fix-1801-warnstufen-abstufung
version: "1.0"
tags: [email, design-tokens, ampel, kontrast, chips]
---

# Warnstufen-Farbabstufung + Chip-Farben im Metriken-Überblick (Bug #1801)

## Approval

- [ ] Approved

## Purpose

Der Farbabstand zwischen den Ampelstufen „mittel" (orange) und „hoch" (rot)
ist in Mail-Renderern (Trip-Stundentabelle, Ortsvergleich) messbar der
kleinste der gesamten Skala — nur ein Fünftel des Sprungs grün→gelb. Zusätzlich
zeigt der „Metriken-Überblick" (Chip-Leiste) bei drei Metriken (Gewitter, UV,
Feuchte) eine Farbe, die nicht zur tatsächlich berechneten Ampelstufe passt —
beim Gewitter-Chip sogar mit strukturellem Widerspruch zur Stundentabelle. Die
Spec behebt beides: eine klarer unterscheidbare Ampel-Palette (inkl. WCAG-Fix
beim grünen Zelltext) und eine an den Katalog angeschlossene, konsistente
Chip-Einfärbung.

## Source

- **File:** `src/output/renderers/email/design_tokens.py`
  **Identifier:** `_TONE_CSS`, `tone_css()`, `G_SUCCESS`
- **File:** `src/output/renderers/email/helpers.py`
  **Identifier:** `_AMPEL_DOT_COLORS`, `_PILL_TAG_PALETTE`, `_PILL_TONE_MAP`,
  `pill_html()`, Chip-Zweige `metric_id == "thunder"` / `"uv_index"` / `"humidity"`
- **File:** `src/output/renderers/email/html.py`
  **Identifier:** vier lokale Kopien der Flächen-/Text-Farbdicts (u. a. Zeilen
  ~781, ~798, ~817, ~823) — Trip-Stundentabelle Desktop-Rendering
- **File:** `src/output/renderers/email/outlook.py`
  **Identifier:** zwei lokale Kopien (Zeilen ~92-96, ~202-203) + abweichender
  `"LOW"`-Gelbton (Zeile ~201)
- **File:** `src/output/metric_format.py`
  **Identifier:** `thunder_ampel_band()` (Zeile 255, bestehende SSoT, Issue
  #1491/ADR-0025) — wird vom Gewitter-Chip neu konsumiert, nicht verändert

> **Schicht-Hinweis:** Alles Python-Core / Mail-Renderer
> (`src/output/renderers/email/`), keine Go-API- oder Frontend-Berührung.
> `frontend/src/app.css` spiegelt `G_SUCCESS` separat für das Web-Frontend —
> bewusst **nicht** im Scope (siehe „Nicht-Ziele").

## Estimated Scope

- **LoC:** ~120-160 (Kernänderungen). Regenerierte Goldens zählen **nicht
  gegen das Produktiv-Budget (250)**, aber sehr wohl gegen das separate
  **Test-Budget (500)** — am Gate gemessen: `edit_gate.py:285-295` teilt das
  Delta anhand von `DEFAULT_TEST_PATH_PATTERNS` (`(^|/)tests?/`) in zwei Töpfe,
  und `tests/golden/email/*` fällt in den Test-Topf. Die drei HTML-Goldens
  sind je 60 Zeilen → max. ~180 Zeilen Test-Delta. Beide Budgets halten.
- **Files:** 4 Produktivdateien (design_tokens.py, helpers.py, html.py,
  outlook.py) + 4 Bestandstests (MODIFY) + 6 Golden-Referenzdateien
  (REGENERATE)
- **Effort:** medium (zwei Scheiben, Renderer-Commit-Gate #811 verlangt beide
  Mail-Validatoren)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0008 (Kontrast vor Optik) | Architekturentscheidung | Begründet den WCAG-AA-Fix am grünen Zelltext als Pflicht, nicht Kür |
| ADR-0025 / Issue #1491 (`thunder_ampel_band` als einzige Quelle) | Architekturentscheidung | Gewitter-Chip MUSS an diese Quelle andocken, keine eigene Logik |
| `thunder_ampel_band()` (`src/output/metric_format.py:255`) | Funktion | Liefert Ampelband aus `ThunderLevel`, bereits vorhandene SSoT |
| `_sms_mention_threshold()` / Katalog `display_thresholds` | Funktion/Daten | Liefert UV-Schwellen (3/6/8) für den UV-Chip-Fix |
| `renderer_mail_gate.py` (Commit-Gate #811) | Gate | Blockiert Commit, bis `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` erfolgreich lief |
| `data_schema_backup.py` | Hook | Nicht relevant (kein Schema-Rework), nur informativ geprüft |

## Scheibenschnitt

| Scheibe | Inhalt | Sichtbar? | Golden-Vergleich? |
|---|---|---|---|
| **S1** | Farb-Duplikate auf eine Quelle konsolidieren (`html.py`, `outlook.py` → `tone_css()`; Punktfarben auf eine Dot-Quelle) | Nein — byte-identisch | Ja, muss identisch bleiben |
| **S2** | Neue Ampel-Palette + WCAG-Fix + vierter Chip-Ton + Gewitter-/UV-/Feuchte-Chip-Fix | Ja | Ja, Goldens werden regeneriert |

S1 zuerst: ein unsichtbarer Umbau lässt sich am Golden-Vergleich beweisen
(bleibt er byte-identisch, war der Umbau korrekt); S2 setzt danach an **einer**
Stelle an statt an acht Kopien parallel. Präzedenz: Issue #1214 Scheibe 2
(`compare_html.py`/`corridor_mark.py`).

## Implementation Details

### S1 — Farb-Konsolidierung (unsichtbar)

`design_tokens.py::tone_css()` ist bereits als Single Source of Truth für
`(bg, fg)`-Tupel der vier Ampelstufen deklariert, wird aber von `html.py`
(vier eigene Kopien) und `outlook.py` (zwei eigene Kopien) nicht benutzt —
sie führen dieselben Hex-Werte lokal. Ebenso existieren die Ampel-Punktfarben
(`_AMPEL_DOT_COLORS` in `helpers.py`) unabhängig von den Flächenfarben.

S1 ersetzt die lokalen Dicts in `html.py`/`outlook.py` durch Aufrufe von
`tone_css()` bzw. der konsolidierten Dot-Quelle. Kein Farbwert ändert sich in
dieser Scheibe — reine Strukturänderung. Beweis: alle sechs
`tests/golden/email/*.txt`-Dateien bleiben byte-identisch.

### S2 — Neue Palette + Chip-Fixes (sichtbar)

**Neue Ampel-Werte** (ersetzen die bisherigen in der jetzt einzigen Quelle
`design_tokens.py::_TONE_CSS` + `helpers.py::_AMPEL_DOT_COLORS`):

| Stufe | Punkt (alt → neu) | Fläche (alt → neu) | Text (alt → neu) |
|---|---|---|---|
| grün | `#15803d` *(unverändert)* | `#dbeadd` *(unverändert)* | `#3a7d44` → `#2f6b39` |
| gelb | `#ca8a04` → `#d69500` | `#fbeeb8` → `#fdf4cd` | `#5e4a00` *(unverändert)* |
| orange | `#c2410c` → `#d4530a` | `#fad6b8` → `#fbe3cc` | `#8a3506` → `#7d3400` |
| rot | `#b91c1c` → `#a8104a` | `#f6c5bf` → `#f7d3e2` | `#8a1009` → `#7d0c39` |

Wirkung Übergang orange→rot: Punktabstand (ΔE76) 16,4 → 54,4, Flächenabstand
13,6 → 20,2. Alle Zell-Texte ≥ 4,5:1 (grün steigt 4,01 → 5,12:1).

**Wichtige Scoping-Entscheidung zum grünen Text (Zusatzbefund dieser Spec,
über die Kontext-Analyse hinaus):** `#3a7d44` ist heute die Konstante
`G_SUCCESS` in `design_tokens.py` — verifiziert wiederverwendet in mind. drei
Stellen außerhalb der Ampel-Zellfärbung: der amtlichen 4-Stufen-Warnpalette
(`compare_html._ALERT_LEVEL_CELL[1]`, geprüft von
`tests/tdd/test_official_alert_badge_color.py:25` mit hartkodiertem
`GREEN = "#3a7d44"`) und dem Korridor-Marker-Grün
(`tests/tdd/test_trip_mail_corridor_mark.py:26`,
`tests/tdd/test_compare_mail_corridor_mark.py:79`, beide mit hartkodiertem
`border-left:3px solid #3a7d44`). Würde `G_SUCCESS` selbst auf `#2f6b39`
geändert, brächen diese drei unbeteiligten Tests — genau die
„Bedeutungs-Kopplung", die der Code-Kommentar in `design_tokens.py`
(„die beiden Paletten dürfen niemals vermischt werden") für die
amtliche-vs-Ampel-Trennung bereits ausdrücklich verbietet.

**Entscheidung:** Eine **neue, eigenständige Konstante** (z. B.
`G_AMPEL_TEXT_GREEN = '#2f6b39'`) trägt den WCAG-Fix, ausschließlich verwendet
in `_TONE_CSS["green"]`. `G_SUCCESS` bleibt bei `#3a7d44` — amtliche
Warnstufen-Badges und Korridor-Marker bleiben unberührt, ihre Tests brauchen
keine Anpassung. Damit ist `tests/tdd/test_email_design_tokens.py:47`
(`assert G_SUCCESS == "#3a7d44"`) weiterhin gültig und **nicht** Teil der
Betroffene-Dateien-Liste unten.

**Neuer vierter Chip-Ton** `caution` (schließt die Lücke aus Befund C: Chips
konnten bisher nur 3 von 4 Ampelstufen zeigen, weil `ampel_yellow` und
`ampel_orange` beide auf `"warn"` abbildeten):

| Ton | Grund (alt → neu) | Text (alt → neu) | Rahmen (alt → neu) | Text/Grund |
|---|---|---|---|---|
| ok | `#dcf2e1` *(unverändert)* | `#14532d` *(unverändert)* | `#86c89a` *(unverändert)* | 7,74:1 |
| **caution** *(neu)* | `#fdf2c4` | `#6b5200` | `#e0b93c` | 6,59:1 |
| warn | `#fde6cc` → `#fbe0c4` | `#7c2d12` → `#7d3400` | `#f0a060` → `#e59248` | 7,01:1 |
| risk | `#fadcd6` → `#fad3e1` | `#7f1d1d` → `#7d0c39` | `#e88472` → `#dd7ba2` | 7,80:1 |
| info | `#dde8f3` *(unverändert)* | `#1e3a5f` *(unverändert)* | `#8aacd0` *(unverändert)* | 9,26:1 |

`_PILL_TONE_MAP` wird von 4 auf 5 Einträge erweitert:
`"ampel_green": "ok"`, `"ampel_yellow": "caution"` *(neu, statt `"warn"`)*,
`"ampel_orange": "warn"`, `"ampel_red": "risk"`.

**Drei Chip-Fehler** (Auszählung aller 15 Chips, Befund B des Kontext-Dokuments):

1. **Gewitter** (`helpers.py`, Zweig `metric_id == "thunder"`): liefert heute
   für jede Gewittererwähnung fest `"ampel_red"`. Fix: Farbe aus
   `thunder_ampel_band(max_lvl)` ableiten (`max_lvl` wird im selben Codeblock
   bereits berechnet, bisher nur für die Uhrzeit genutzt) statt neu zu
   berechnen — schließt an die deklarierte Einzelquelle
   `thunder_ampel_band()` an (ADR-0025), damit Chip und Stundentabelle
   bauartbedingt nicht mehr auseinanderlaufen können.
2. **UV** (`helpers.py`, Zweig `metric_id == "uv_index"`): liefert heute fest
   `_PILL_NEUTRAL_TONE`. Fix: Ampelfarbe aus den Katalog-Schwellen (gelb ab 3,
   orange ab 6, rot ab 8) ableiten wie bei den übrigen Schwellen-Metriken
   (`ampel_stage_tone`-Muster).
3. **Feuchte** (`helpers.py`, Zweig `metric_id == "humidity"`): liefert heute
   bei Schwellenüberschreitung fest `"ampel_yellow"`, obwohl die Metrik im
   Katalog keine `display_thresholds` führt. Fix: neutraler Ton
   (`_PILL_NEUTRAL_TONE`) wie bei den übrigen stufenlosen Metriken (Wolken,
   0°-Linie, Taupunkt, Sonne) — Regel wird durchgängig: *Schwellen vorhanden →
   Ampelfarbe, sonst neutral.*

## Betroffene Dateien

| Datei | Art | Warum |
|---|---|---|
| `src/output/renderers/email/design_tokens.py` | MODIFY | `_TONE_CSS` neue Werte, `tone_css()` bleibt Schnittstelle, neue Konstante `G_AMPEL_TEXT_GREEN`, `G_SUCCESS` unverändert |
| `src/output/renderers/email/helpers.py` | MODIFY | `_AMPEL_DOT_COLORS` (S2-Werte), `_PILL_TAG_PALETTE` (5. Ton), `_PILL_TONE_MAP` (caution ergänzt), 3 Chip-Zweige (thunder/uv_index/humidity) |
| `src/output/renderers/email/html.py` | MODIFY | S1: vier Kopien Fläche/Text auf `tone_css()` umstellen; S2 profitiert automatisch von der einen Quelle |
| `src/output/renderers/email/outlook.py` | MODIFY | S1: zwei Kopien auf `tone_css()` umstellen (LOW-Gelbton bleibt bewusst abweichend, s. Nicht-Ziele) |
| `tests/golden/email/*.txt` (6 Dateien) | REGENERATE | via `tests/golden/email/regenerate.py`, S1 identisch / S2 mit neuer Palette |
| `tests/tdd/test_issue_795_briefing_quality.py` | MODIFY | Zeile 246 `test_thunder_pill_is_red_plain`: Fixture nutzt `ThunderLevel.MED`, `thunder_ampel_band(MED)` liefert `"orange"` — Assertion muss auf `tone == "ampel_orange"` geändert werden. Zeile 551: Kommentar „by design" wird falsch, Assertion `>= 3` → `== 4` (vierter Ton `caution` neu unterscheidbar) |
| `tests/tdd/test_bundle_851_852_email_pill_format.py` | MODIFY | Zeile 35 fordert für `ampel_orange` die **warn**-Rahmenfarbe mit dem alten Hex-Wert `#f0a060` — auf den neuen Wert `#e59248` ändern |
| `tests/test_ampel_schwellen_katalog.py` | MODIFY | Zeilen 34-36 mappen die alten Flächen-Hex-Werte (`#fbeeb8`/`#fad6b8`/`#f6c5bf`) auf Ampelstufen — auf die neuen S2-Werte (`#fdf4cd`/`#fbe3cc`/`#f7d3e2`) aktualisieren |

**Explizit NICHT in dieser Liste** (Begründung s. „Nicht-Ziele"):
`tests/tdd/test_email_design_tokens.py` (G_SUCCESS bleibt unverändert),
`tests/tdd/test_official_alert_badge_color.py`,
`tests/tdd/test_trip_mail_corridor_mark.py`,
`tests/tdd/test_compare_mail_corridor_mark.py`,
`tests/tdd/test_metric_format.py`.

## Nicht-Ziele

Drei Wiederverwender in `html.py` benutzen dieselben Hex-Werte wie die
Ampel-Palette, tragen aber eine andere Bedeutung und bleiben unangetastet
(eigene lokale Konstanten statt gemeinsamer Quelle — sonst zöge ein künftiger
Palettenwechsel sie still mit):

- `_RISK_DOT_COLORS` (~Zeile 236) sowie die davon abgeleiteten hartkodierten
  Duplikate im mobilen Kurzfassungs-Rendering (~Zeilen 330, 349, 353, 363) —
  bewusst **drei**stufiger mobiler RiskDot („keine vierte Punktfarbe",
  Kommentar Zeile 207).
- `_confidence_dot_color` (~Zeile 1334) — Ausblick-Verlässlichkeit, andere
  Bedeutungsachse.
- `_trend_color` (~Zeile 1484) — Vortagesvergleich-Pfeil, andere
  Bedeutungsachse.

Weitere ausdrücklich ausgenommene Stellen:

- `outlook.py:201` `"LOW": "#fbe6c3"` — ein von der Ampel-Skala abweichender
  Gelbton für eine andere Outlook-eigene Stufenbezeichnung; wird nicht
  angeglichen, da außerhalb des vierstufigen Ampel-Vokabulars.
- `G_SUCCESS`, `_ALERT_LEVEL_CELL` (amtliche 4-Stufen-Warnpalette) und die
  Korridor-Marker-Farbe — siehe Scoping-Entscheidung oben. Amtliche
  Warnstufen und Metrik-Ampel sind laut Code-Kommentar in
  `design_tokens.py` zwei getrennte Systeme, die „niemals vermischt werden"
  dürfen; dieser Fix respektiert das für Grün genauso wie es der bestehende
  Code für G_ALERT_L4/Hagel-Ring bereits für Violett tut.
- `frontend/src/app.css` — spiegelt `#3a7d44`/`G_SUCCESS` als `--g-success`
  für das Web-Frontend (eigenes UI-System, SvelteKit). Bewusst ausgelassen,
  da dieser Fix ausschließlich Mail-Renderer betrifft; wird im PR vermerkt.

## Known Limitations

- **Gelber Punkt auf gelber Fläche bleibt schwach unterscheidbar (2,33:1).**
  Ein satteres Dottergelb auf gelbem Grund gibt das physikalisch nicht her,
  ohne der Fläche ihre Signalwirkung zu nehmen. Die Stufe bleibt über Fläche
  und Ring erkennbar, nicht primär über den Punkt-Kontrast. Bewusst
  hingenommen, kein offener Folge-Punkt.
- Chip-Palette (caution-Ton, warn/risk-Anpassungen) ist aus dem
  Karmin-Entscheid des PO abgeleitet, wurde aber nicht separat als eigener
  GitHub-Kommentar freigegeben — Freigabe erfolgt mit dieser Spec.

## Acceptance Criteria

### Scheibe S1 — Farb-Konsolidierung (unsichtbar)

- **AC-1:** Given der E-Mail-Renderer verwendet heute an mehreren Stellen (`html.py`, `outlook.py`) eigene Kopien der Ampel-Flächen- und Textfarben statt der einen Quelle `design_tokens.py::tone_css()` / When diese Kopien durch Aufrufe der zentralen Funktion ersetzt werden / Then erzeugen alle sechs Referenz-Mails unter `tests/golden/email/` exakt denselben Byte-Inhalt wie vor der Umstellung.
  - Test: `tests/golden/email/test_email_html_golden.py`, `test_email_plain_golden.py`, `test_outlook_thunder_day_night_golden.py` — regenerierte Ausgabe wird byte-für-byte mit dem Vor-Zustand verglichen (Fixtures `regenerate.py`).

- **AC-2:** Given die Ampel-Punktfarben (der farbige Kreis vor jedem Messwert in Stundentabelle und Ortsvergleich) werden heute unabhängig von den Flächenfarben definiert / When sie ebenfalls auf eine einzige Quelle zusammengeführt werden / Then zeigt jede Ausgabe, die vorher eine Punktfarbe darstellte, exakt dieselbe Farbe wie vor der Zusammenführung.
  - Test: derselbe Golden-Vergleich wie AC-1 (Punktfarben sind Teil des HTML-Outputs) sowie `tests/test_ampel_schwellen_katalog.py` (bestehende Katalog-Tests, unverändert grün).

### Scheibe S2 — Neue Palette + Chip-Fixes (sichtbar)

- **AC-3:** Given die Ampelstufen „mittel" (orange) und „hoch" (rot) liegen heute farblich zu dicht beieinander (Punktabstand ΔE76 nur 16,4) / When die neue Palette (orange `#d4530a`/`#fbe3cc`/`#7d3400`, rot `#a8104a`/`#f7d3e2`/`#7d0c39`) eingesetzt wird / Then beträgt der Punktabstand zwischen orange und rot mindestens 50 (ΔE76) statt vorher rund 16.
  - Test: neuer/erweiterter Test in `tests/test_ampel_schwellen_katalog.py` oder `tests/tdd/test_email_design_tokens.py`, der die Hex-Werte aus `_TONE_CSS`/`_AMPEL_DOT_COLORS` gegen die Zielwerte-Tabelle prüft und den ΔE76-Abstand berechnet.

- **AC-4:** Given der grüne Zelltext in der Ampel-Tabelle unterschreitet heute die WCAG-AA-Kontrastgrenze (4,01:1 auf `#dbeadd`) / When der Text auf die neue Konstante `#2f6b39` umgestellt wird / Then beträgt der Kontrast des grünen Zelltexts mindestens 4,5:1, ohne dass sich die Farbe der amtlichen Warnstufe 1 (`G_SUCCESS`) verändert.
  - Test: Kontrast-Assertion in `tests/tdd/test_email_design_tokens.py` (analog zur bestehenden AA-Prüfung für andere Töne) sowie unveränderter Lauf von `tests/tdd/test_official_alert_badge_color.py` (bleibt grün, keine Anpassung nötig).

- **AC-5:** Given der Gewitter-Chip im Metriken-Überblick zeigt heute immer die rote Farbe, unabhängig von der tatsächlichen Gewitterstärke / When der Chip die Farbe stattdessen aus der bereits vorhandenen Stufenzuordnung `thunder_ampel_band()` bezieht / Then zeigt der Chip bei mittlerer Gewitterstärke dieselbe Farbe wie die entsprechenden Stunden in der Stundentabelle (orange statt rot).
  - Test: `tests/tdd/test_issue_795_briefing_quality.py::test_thunder_pill_is_red_plain` (angepasst auf `ThunderLevel.MED` → `ampel_orange`) + neuer Test für `ThunderLevel.HIGH` → `ampel_red` zur Abgrenzung.

- **AC-6:** Given der UV-Chip zeigt heute unabhängig vom UV-Wert immer eine neutrale (blaue) Farbe, obwohl der Katalog Schwellen (3/6/8) führt / When der Chip die Schwellen auswertet / Then zeigt der Chip bei einem UV-Höchstwert oberhalb der obersten Schwelle (z. B. UV 8,5) die rote Ampelfarbe statt der neutralen Farbe.
  - Test: neuer Test in `tests/test_ampel_schwellen_katalog.py` oder in `helpers.py`-Testdatei, der `_pill_for_metric("uv_index", ...)` mit Werten unter/über den drei Schwellen aufruft und die zurückgegebene Tonstufe prüft.

- **AC-7:** Given der Feuchte-Chip zeigt heute bei Schwellenüberschreitung eine gelbe Warnfarbe, obwohl die Metrik im Katalog keine Ampel-Schwellen führt / When der Chip auf die neutrale Farbe umgestellt wird / Then zeigt der Feuchte-Chip unabhängig vom Wert immer die neutrale Farbe, wie die übrigen stufenlosen Metriken (Wolken, 0°-Linie, Taupunkt, Sonne).
  - Test: neuer Test, der `_pill_for_metric("humidity", ...)` mit einem hohen Feuchtewert aufruft und `_PILL_NEUTRAL_TONE` statt `ampel_yellow` erwartet.

- **AC-8:** Given die Chip-Palette kann heute nur drei unterscheidbare Töne darstellen, weil „gelb" und „orange" auf denselben Ton „warn" abgebildet werden / When ein vierter Ton `caution` eingeführt wird / Then rendern Chips mit den vier Ampelstufen grün/gelb/orange/rot vier optisch unterscheidbare Hintergrundfarben statt drei.
  - Test: `tests/tdd/test_issue_795_briefing_quality.py` (Assertion auf `len(seen_bg) >= 3` → `== 4`, Zeile 551) sowie neuer Test, der `pill_html()` für alle vier Ampel-Töne aufruft und vier unterschiedliche `bg`-Hex-Werte erwartet.

- **AC-9:** Given zwei Bestandstests frieren das heutige Fehlverhalten fest (Gewitter-Chip immer rot; orange nutzt die warn-Rahmenfarbe des alten Hex-Werts) / When diese Tests auf das neue, korrekte Verhalten angepasst werden / Then bestätigen die aktualisierten Tests das neue Verhalten und ziehen den Fix nicht durch weiterhin bestehende falsche Erwartungen zurück.
  - Test: `tests/tdd/test_issue_795_briefing_quality.py:246`, `tests/tdd/test_bundle_851_852_email_pill_format.py:35` (beide angepasst, s. Betroffene Dateien) laufen grün gegen den neuen Code.

- **AC-10:** Given die amtliche Warnstufen-Farbe (Stufe 1, grün) und der Korridor-Marker nutzen denselben Grundton `#3a7d44` wie bisher die Ampel-Zellfarbe / When die Ampel-Palette für WCAG-Kontrast und Abstufung angepasst wird, ohne die gemeinsam genutzte Konstante `G_SUCCESS` zu verändern / Then bleiben die amtliche Warnstufe 1 und der Korridor-Marker farblich exakt unverändert (`#3a7d44`).
  - Test: `tests/tdd/test_official_alert_badge_color.py`, `tests/tdd/test_trip_mail_corridor_mark.py`, `tests/tdd/test_compare_mail_corridor_mark.py`, `tests/tdd/test_metric_format.py::TestAlertLevelSeparation` laufen **ohne Codeänderung** weiterhin grün.

## Test-Plan

| AC | Wo | Wie |
|---|---|---|
| AC-1 | `tests/golden/email/test_email_html_golden.py`, `test_email_plain_golden.py`, `test_outlook_thunder_day_night_golden.py` | Byte-Vergleich der 6 Golden-Referenzdateien vor/nach S1-Konsolidierung, kein Diff erlaubt |
| AC-2 | dieselben Golden-Tests + `tests/test_ampel_schwellen_katalog.py` | Punktfarben sind Teil des HTML-Outputs (im Golden enthalten); bestehende Katalog-Tests bleiben unverändert grün |
| AC-3 | `tests/tdd/test_email_design_tokens.py` oder `tests/test_ampel_schwellen_katalog.py` | Direkter Hex-Wert-Vergleich gegen Zielwerte-Tabelle + ΔE76-Berechnung (Lab-Farbraum) für orange↔rot |
| AC-4 | `tests/tdd/test_email_design_tokens.py` | WCAG-Kontrastformel (relative Luminanz) auf `(bg, fg)` von `_TONE_CSS["green"]`, Grenze ≥ 4,5:1; zusätzlich `G_SUCCESS == "#3a7d44"` bleibt unverändert geprüft |
| AC-5 | `tests/tdd/test_issue_795_briefing_quality.py` | `build_metrics_summary_pills()` mit Fixture `ThunderLevel.MED`/`HIGH` aufrufen, Ton mit `thunder_ampel_band()`-Ergebnis abgleichen |
| AC-6 | neuer Test (Datei nach Namensregel, z. B. `tests/test_uv_chip_ampel.py` oder Ergänzung in `tests/test_ampel_schwellen_katalog.py`) | `_pill_for_metric("uv_index", werte)` für Werte unter 3, zwischen 3-6, 6-8, über 8 aufrufen, Ton prüfen |
| AC-7 | dieselbe neue Testdatei/-erweiterung wie AC-6 | `_pill_for_metric("humidity", hoher_wert)` aufrufen, `_PILL_NEUTRAL_TONE` erwarten |
| AC-8 | `tests/tdd/test_issue_795_briefing_quality.py:551` + Erweiterung | `pill_html()` für alle vier Ampel-Töne aufrufen, `len(seen_bg) == 4` |
| AC-9 | `tests/tdd/test_issue_795_briefing_quality.py`, `tests/tdd/test_bundle_851_852_email_pill_format.py` | Bestehende Testläufe grün nach Anpassung der Assertions auf die neuen Werte |
| AC-10 | `tests/tdd/test_official_alert_badge_color.py`, `test_trip_mail_corridor_mark.py`, `test_compare_mail_corridor_mark.py`, `test_metric_format.py` | Unveränderter Testlauf (kein Code-Edit an diesen Dateien) bleibt grün — Regressionsnachweis für die Scoping-Entscheidung |

Zusätzlich **Pflicht vor „E2E bestanden"** (unabhängig von den ACs, projektweite
Regel): `briefing_mail_validator.py` gegen echte Staging-Mail sowie
`renderer_mail_gate.py` (verlangt `test_issue_811_mode_matrix.py` grün + einen
frischen erfolgreichen Validator-Lauf im selben Commit).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0008 (Kontrast vor Optik), ADR-0025 (eine Gewitter-Quelle
  für alle Briefing-Kanäle)
- **Rationale:** ADR-0008 verlangt WCAG-AA-Mindestkontrast als Vorrang vor
  ästhetischer Präferenz — der grüne Zelltext (4,01:1) verstößt dagegen und
  wird mit dieser Spec korrigiert. ADR-0025 erklärt `thunder_ampel_band()`
  zur einzigen Quelle für Gewitterstufe → Ampelband; der Gewitter-Chip-Fix
  schließt eine bisher übersehene Ausnahme an diese Quelle an, statt neue
  Logik zu bauen. Kein neues ADR nötig — beide bestehenden werden fortgeführt,
  nicht abgelöst.

## Changelog

- 2026-08-14: Initial spec created (Bug #1801, Analyse aus
  `docs/context/1801-warnstufen-abstufung.md` + Issue-Kommentare, PO-Entscheid
  Karminrot statt Violett + alle drei Chip-Fälle im Fix; zusätzlich eigener
  Befund während Spec-Erstellung: `G_SUCCESS`-Wiederverwendung in amtlicher
  Warnpalette/Korridor-Marker verlangt eine neue, getrennte Konstante statt
  direkter Wertänderung — siehe AC-10).

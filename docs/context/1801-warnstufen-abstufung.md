# Kontext: #1801 — Abstufung zwischen mittlerer und hoher Gefahr nicht klar genug

**Workflow:** `fix-1801-warnstufen-abstufung` · **Typ:** Bug · **Issue:** [#1801](https://github.com/henemm/gregor_zwanzig/issues/1801)

## Symptom (PO, mit drei Screenshots belegt)

1. Gelb/Orange/Rot der Gefahrenstufen liegen optisch zu dicht beieinander.
   Wunsch: Gelb → dottergelb, Orange → Warnorange, Rot → Richtung Violett.
2. Die Farbe der Chips im „Metriken-Überblick" passt nicht zum tatsächlichen
   Warnlevel: Chip „Gewitter … CAPE" ist **rot**, die Stundentabelle zeigt für
   dieselben Stunden nur die **mittlere** Stufe (oranger Punkt auf gelbem Grund).

## Befund (gemessen, nicht geschätzt)

### A) Farbabstand — Beschwerde ist belegbar

Abstand benachbarter Stufen (ΔE76 im Lab-Raum, höher = besser unterscheidbar):

| Übergang | Punkt | Fläche |
|---|---|---|
| grün → gelb | 73,0 | 23,6 |
| gelb → orange | 39,9 | 15,7 |
| **orange → rot** | **16,4** | **13,6** |

Der Sprung „mittel → hoch" ist der kleinste der Skala — gut ein Fünftel von
grün→gelb. Zusätzlich gefunden: der **grüne Zell-Text** verfehlt heute WCAG-AA
(`#3a7d44` auf `#dbeadd` = 4,01:1, Grenze 4,5:1) — Verstoß gegen ADR-0008.

### B) Chip-Farben — drei Ausreißer, nicht einer

Die Regel im Katalog: Metrik führt `display_thresholds` → Stufe berechenbar;
keine Schwellen → nichts einzufärben. Auszählung **aller 15 Chips**:

| Chip | Schwellen | Farbquelle | Bewertung |
|---|---|---|---|
| Wind, Böen, Regen, Regen-W., Sicht, Temp, gef. Temp | ja | `ampel_stage_tone` | korrekt |
| **Gewitter** | ordinal | **fest `"ampel_red"`** | **Fehler** |
| **UV** | **ja** (3/6/8) | **fest `_PILL_NEUTRAL_TONE`** | **Fehler** |
| **Feuchte** | **keine** | **fest `"ampel_yellow"`** | **inkonsistent** |
| Wolken, 0°-Linie, Taupunkt, Sonne | keine | neutral | korrekt |

### C) Strukturursache: Chips können nur 3 von 4 Stufen zeigen

`helpers.py:1255-1259` bildet `ampel_yellow` UND `ampel_orange` auf denselben
Eintrag `"warn"` ab. Punkt 2 des Issues ist deshalb **nicht isoliert behebbar**:
Selbst ein korrekt ermitteltes „mittel" sähe aus wie „leicht". Beide Teile des
Issues treffen sich an dieser Stelle.

### D) Deklarierte SSoT wird vom Chip umgangen

`thunder_ampel_band()` (`src/output/metric_format.py:255`, Issue #1491/ADR-0025)
ist die erklärte einzige Quelle Gewitterstufe → Ampelband; Stundentabelle und
Ortsvergleich nutzen sie. **Nur der Chip nicht** — daher der Widerspruch zwischen
Screenshot 2 und 3. Der Fix schließt den Chip an das Vorhandene an, statt neue
Logik zu bauen. Im selben Block liegt `max_lvl` bereits fertig berechnet vor und
wird heute nur für die Uhrzeit verwendet.

## PO-Entscheidungen

- **Karminrot statt Violett** (2026-08-13). Grund: `#6d28d9` ist doppelt belegt —
  amtliche Warnstufe 4 (`G_ALERT_L4`) **und** Hagel-Ring, letzterer laut Code
  bewusst, weil er „in KEINER Ampelstufe vorkommt". Echtes Violett bräuchte
  vorher eine Neukennzeichnung beider.
- **Alle drei Chip-Fälle** (Gewitter, UV, Feuchte) gehören in den Fix — damit
  gilt einheitlich: *Schwellen vorhanden → Ampelfarbe, sonst neutral.*

## Zielwerte

### Ampel (Punkt/Fläche/Text) — Stundentabelle, Ortsvergleich

| Stufe | Punkt | Fläche | Text |
|---|---|---|---|
| grün | `#15803d` | `#dbeadd` | `#3a7d44` → **`#2f6b39`** (AA-Fix) |
| gelb | `#ca8a04` → **`#d69500`** | `#fbeeb8` → **`#fdf4cd`** | `#5e4a00` |
| orange | `#c2410c` → **`#d4530a`** | `#fad6b8` → **`#fbe3cc`** | `#8a3506` → **`#7d3400`** |
| rot | `#b91c1c` → **`#a8104a`** | `#f6c5bf` → **`#f7d3e2`** | `#8a1009` → **`#7d0c39`** |

Wirkung orange→rot: Punkt 16,4 → **54,4**, Fläche 13,6 → **20,2**.
Alle Zell-Texte ≥ 4,5:1; grün steigt 4,01 → 5,12:1.

**Bewusst hingenommen:** Der gelbe Punkt hebt sich von gelber Fläche weiterhin
nur schwach ab (2,33:1) — physikalisch nicht besser lösbar, ohne der Fläche ihre
Signalwirkung zu nehmen. Stufe bleibt über Fläche + Ring erkennbar.

### Chips (Grund/Text/Rahmen) — eigenes Wertesystem, vierter Ton neu

| Ton | Grund | Text | Rahmen | Text/Grund |
|---|---|---|---|---|
| ok | `#dcf2e1` | `#14532d` | `#86c89a` | 7,74:1 |
| **caution** (neu) | `#fdf2c4` | `#6b5200` | `#e0b93c` | 6,59:1 |
| warn | `#fde6cc` → **`#fbe0c4`** | `#7c2d12` → **`#7d3400`** | `#f0a060` → **`#e59248`** | 7,01:1 |
| risk | `#fadcd6` → **`#fad3e1`** | `#7f1d1d` → **`#7d0c39`** | `#e88472` → **`#dd7ba2`** | 7,80:1 |
| info | `#dde8f3` | `#1e3a5f` | `#8aacd0` | 9,26:1 |

Abstand warn→risk: Grund 10,7 → **21,9**, Rahmen 23,7 → **57,9**.
Abstand risk↔info(blau) 18,4 — keine Verwechslung.

## Betroffene Dateien

| Datei | Art | Warum |
|---|---|---|
| `src/output/renderers/email/design_tokens.py` | MODIFY | `_TONE_CSS` (SSoT-Anspruch) + neue Dot-Quelle |
| `src/output/renderers/email/helpers.py` | MODIFY | `_AMPEL_DOT_COLORS`, `_PILL_TAG_PALETTE`, `_PILL_TONE_MAP`, 3 Chip-Zweige |
| `src/output/renderers/email/html.py` | MODIFY | 4 Kopien Fläche/Text + 2 Kopien Punkt |
| `src/output/renderers/email/outlook.py` | MODIFY | 2 Kopien + abweichender LOW-Ton |
| `tests/golden/email/*.txt` (6) | REGENERATE | generiert via `regenerate.py` |
| `tests/tdd/test_issue_795_briefing_quality.py` | MODIFY | Zeile 246 nagelt den Bug fest (s.u.) |
| `tests/tdd/test_bundle_851_852_email_pill_format.py` | MODIFY | Zeile 35 friert „orange = warn" ein |
| `tests/tdd/test_email_design_tokens.py` | MODIFY | Zeile 47 lockt `G_SUCCESS` |
| `tests/test_ampel_schwellen_katalog.py` | MODIFY | Zeilen 34-36 mappen alte Flächen-Hex |

**Zwei Bestandstests halten den Bug fest — verifiziert, nicht vermutet:**
- `test_issue_795_briefing_quality.py:246` `test_thunder_pill_is_red_plain`:
  Fixture setzt `ThunderLevel.MED`, Test fordert `tone == "ampel_red"`.
  `thunder_ampel_band(MED)` liefert `"orange"` → muss mitgeändert werden.
- `test_bundle_851_852_email_pill_format.py:35`: fordert für `ampel_orange`
  ausdrücklich die **warn**-Rahmenfarbe — der Bug, in einem Test eingefroren.
- `test_issue_795_briefing_quality.py:551` nennt die Kollision „by design"
  (`assert len(seen_bg) >= 3`) — Kommentar wird falsch, Assertion auf `== 4`.

## Kollateral-Risiko (vor der Umsetzung zu entscheiden)

Drei Features in `html.py` benutzen **dieselben Hex-Werte**, gehören aber nicht
zum Scope. Eine blinde Text-Ersetzung färbt sie mit um:
- `_RISK_DOT_COLORS` (~236) — bewusst **drei**stufiger mobiler RiskDot
  („keine vierte Punktfarbe", Kommentar Zeile 207)
- `_confidence_dot_color` (~1334) — Ausblick-Verlässlichkeit
- `_trend_color` (~1477) — Vortagesvergleich-Pfeil

Ebenso `outlook.py:201` `"LOW": "#fbe6c3"` — vom Rest abweichender Gelbton.

**Entscheidung:** Diese vier bleiben unangetastet und bekommen eigene lokale
Konstanten. Sie tragen eine andere Bedeutung als die Gefahren-Ampel; sie an
dieselbe Quelle zu hängen wäre eine Bedeutungs-Kopplung, die beim nächsten
Palettenwechsel still das Falsche mitzieht.

Weiteres Gate: `renderer_mail_gate.py` blockiert jeden Commit auf
`src/output/renderers/email/*`, solange `tests/golden/email/` rot ist →
`regenerate.py` gehört in denselben Commit.

**Nicht im Scope:** `frontend/src/app.css` spiegelt `#3a7d44` als
`--g-success`. Das ist das Web-Frontend (eigenes UI-System), nicht der
Mail-Renderer. Bewusst ausgelassen, im PR zu vermerken.

## Scheibenschnitt

| Scheibe | Inhalt | Sichtbar? | Golden? |
|---|---|---|---|
| **S1** | Farb-Duplikate auf eine Quelle (`html.py`, `outlook.py` → `tone_css()`; neue Dot-SSoT) | nein — byte-identisch | nein |
| **S2** | Neue Ampel-Palette + 4. Chip-Ton + Gewitter/UV/Feuchte | ja | ja |

S1 zuerst, weil S2 danach an **einer** Stelle ansetzt statt an acht Kopien
parallel — und weil ein unsichtbarer Umbau sich am Golden-Vergleich beweisen
lässt: bleibt er byte-identisch, war der Umbau korrekt. Präzedenz: #1214
Scheibe 2 hat `compare_html.py`/`corridor_mark.py` bereits so migriert.

## Offene Punkte

- [ ] Chip-Palette (Abschnitt „Zielwerte") ist aus dem Karmin-Entscheid
      abgeleitet, nicht separat freigegeben → geht mit der Spec zur Freigabe.
- [x] **LoC-Zählung der Goldens geklärt (am Gate gemessen, 2026-08-14):**
      `edit_gate.py:285-295` teilt das Delta in zwei Töpfe. `tests/golden/email/*`
      matcht `DEFAULT_TEST_PATH_PATTERNS` (`(^|/)tests?/`) → zählt gegen das
      **Test**-Budget (500), nicht gegen die 250 Produktivzeilen. Die drei
      HTML-Goldens sind je 60 Zeilen (minifiziert) → max. ~180 Zeilen Delta.
      Der Zwei-Scheiben-Schnitt hält.

# Context: fix-1222-css-dots

## Request Summary
In E-Mails (Trip-Briefings UND Alert-Mails) dürfen die **Kreis-Emojis** 🟢🟡🟠🔴
nicht mehr erscheinen. Stattdessen die **gestylten CSS-Dots** (farbiger Kreis
mit hellem Ring) verwenden, wie in der Claude-Design-Vorlage — RICHTIG-Screenshot.
Wetter-Symbole (☀️⛅⚡) sind NICHT betroffen. Referenz-Implementierung existiert
bereits: `_risk_dot()` in `html.py` (Risk-Spalte, Ortsvergleich-Mail v2).

## Der Bug (FALSCH-Screenshot)
HTML-Stundentabelle im Trip-Briefing zeigt in den Ampel-Spalten (Wind/Böen/Regen/
Regenwahrsch./CAPE) die Emoji-Kreise 🟢🟡 statt der gestylten Dots. Quelle:
`ampel_dot()` liefert wörtlich Emoji als Zelleninhalt.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/output/renderers/email/helpers.py:391` | `ampel_dot()` → gibt Emoji zurück, landet in HTML-Zellen — **Kern-Bug** |
| `src/output/renderers/email/helpers.py:363-368` | `_AMPEL_LEVEL_TO_EMOJI`-Map (green→🟢…) |
| `src/output/renderers/email/helpers.py:871,896` | `_AMPEL_EMOJIS` + `ampel_stage_index()` — nutzt `ampel_dot()`-Rückgabe als **Lookup-Key** (`.index()`) → darf beim Umbau NICHT brechen |
| `src/output/renderers/email/helpers.py:904-913` | `tone_symbol()` → Emoji für **Plain-Text**-Pills |
| `src/output/renderers/email/helpers.py:360` | `AMPEL_LEGEND` Emoji-String — im Live-HTML NICHT gerendert (html.py:1463 übergibt `""`), vermutl. tot |
| `src/output/renderers/email/html.py:98-110` | `_risk_dot()` — **RICHTIG-Referenz**: CSS-Dot mit Ring (box-shadow) |
| `src/output/renderers/email/html.py:503-564` | `fmt_val()`-Zweige rufen `ampel_dot()` für wind/precip/pop/cape (HTML) |
| `src/output/renderers/email/plain.py:158` | Plain-Text-Pills nutzen `tone_symbol()` (Emoji) |
| `src/output/renderers/alert/official_alerts.py:25-29,188` | `_LEVEL_WORDS` Emoji — nur im **Plain**-Notice (`render_official_alert_notice_plain`); HTML-Badge nutzt Farb-Border, kein Emoji ✓ |
| `src/output/renderers/trip_report.py:777-783` | Emoji in `_fmt_val`/`_render_html_table` — **toter Code** (format_email delegiert an `render_email`, Methoden ohne Aufrufer) |
| `src/services/trip_command_processor.py:163,651` | SMS/Command-Kontext — **außerhalb E-Mail-Scope** |

## Existing Patterns
- **CSS-Dot mit Ring (RICHTIG):** `_risk_dot(color)` → `<span … border-radius:50%;
  background:{color};box-shadow:0 0 0 3px {ring}>`. Aktuell 3-farbig (grün/orange/rot).
  Braucht 4-Stufen-Variante (green/yellow/orange/red) für die Ampel.
- **Farb-SSoT:** `_AMPEL_STAGE_COLORS` (Pills, Vollfarbe+weißer Text) und
  `_level_from_thresholds()` (Level-Resolver) existieren bereits.
- **Level-Resolver `_level_from_thresholds()`** liefert `green|yellow|orange|red` —
  kann `ampel_stage_index` direkt speisen (Entkopplung von Emoji-Lookup).

## Dependencies
- **Upstream:** `ampel_dot()` hängt an `_level_from_thresholds()` + `_AMPEL_LEVEL_TO_EMOJI`.
- **Downstream von `ampel_dot()`:** (a) HTML-Zellen via `fmt_val()` [FIX-Ziel],
  (b) `ampel_stage_index()` → `ampel_stage_tone()` → Pill-Farben [darf nicht brechen].

## Existing Specs
- Issue #759 (4-Stufen-Ampel), #795 (EIN Ampel-System Pill+Tabelle), #888 (Level-Tönung),
  #814 (Einfach/Roh-Vertrag), #1110 (Ortsvergleich-Mail v2 mit CSS-Dots — der „vorher korrekt"-Stand).
- Renderer-Commit-Gate #811: `test_issue_811_mode_matrix.py` + `briefing_mail_validator.py`
  müssen frisch grün sein bevor Commit von Mail-Renderer-Dateien durchgeht.

## Risks & Considerations
- **Kopplung `ampel_stage_index` an Emoji-Lookup** (`_AMPEL_EMOJIS.index(ampel_dot(...))`):
  Wenn `ampel_dot` künftig CSS-HTML statt Emoji zurückgibt, bricht `.index()`.
  → Entkopplung nötig: `ampel_stage_index` auf `_level_from_thresholds()` umstellen.
- **Plain-Text (tone_symbol, official notice):** CSS-Dots sind in reinem Text unmöglich.
  Offene PO-Frage für die Spec: Emoji durch Text-Marker ersetzen ODER weglassen (bei
  official notice steht das Wort GRÜN/GELB/… ohnehin daneben). RICHTIG-Referenz gilt HTML.
- **4. Farbe (gelb):** `_risk_dot` kennt nur 3 Farben; Ampel hat 4 Stufen. Gelb-Dot-Farbe
  + Ring müssen zum Design passen (Kontrast-Leitprinzip beachten).
- **Renderer-Gate #811** greift beim Commit — Modus-Matrix-Test + Mail-Validator einplanen.
- **`briefing_mail_validator.py`** prüft evtl. auf Emoji-Präsenz → ggf. Anpassung (eigener Workflow für Validator-Änderungen laut CLAUDE.md).
- Toter Emoji-Code in `trip_report.py` + `AMPEL_LEGEND`: opportunistisch bereinigen oder als Nebenbefund notieren.

## Analysis

### Type
Bug (nutzersichtbare Fehldarstellung in HTML-Mail).

### Wichtigste Erkenntnis (entscheidet den Fix-Zuschnitt)
`ampel_dot()` läuft **ausschließlich im HTML-Pfad** — alle vier Aufrufer in
`fmt_val()` sind mit `if html and _use_ampel` geschützt (helpers.py:503/517/557/563).
Der einzige Nicht-HTML-Konsument ist `ampel_stage_index()`, und der nutzt die
Emoji-Rückgabe nur als Lookup-Key (`_AMPEL_EMOJIS.index(ampel_dot(...))`).
→ `ampel_dot()` darf gefahrlos CSS-HTML zurückgeben, **sobald** `ampel_stage_index`
vorher auf den bestehenden `_level_from_thresholds()`-Resolver umgestellt ist.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/email/helpers.py` | MODIFY | `ampel_dot()` gibt 4-Stufen-CSS-Dot (Ring) statt Emoji zurück; neuer Helper `_ampel_dot_css()`; `ampel_stage_index()` auf `_level_from_thresholds()` entkoppeln; `AMPEL_LEGEND` (tot) entfernen |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Plain-Notice: Kreis-Emoji entfernen (Wort GRÜN/… bleibt) |
| `src/output/renderers/email/plain.py` | MODIFY (evtl.) | Plain-Pills: Kreis-Emoji entfernen — abhängig von PO-Entscheidung |
| `src/output/renderers/email/helpers.py` `tone_symbol()` | MODIFY (evtl.) | Plain-Marker — abhängig von PO-Entscheidung |
| `src/output/renderers/trip_report.py` | MODIFY (opt.) | Toten Emoji-Code entfernen oder als Nebenbefund #1199 |
| `tests/…` | CREATE/MODIFY | RED-Test: HTML-Ampelzelle enthält CSS-Dot, kein Emoji |

### Scope Assessment
- Files: 2–4 (Kern: helpers.py + official_alerts.py; plain.py je nach Entscheid)
- Estimated LoC: +50/-25
- Risk Level: MEDIUM (Kern-Mail-Pfad, Renderer-Gate #811, Kopplung ampel_stage_index)

### Technical Approach
1. **HTML-Dot (Kern):** Neuer 4-Stufen-Helper in `helpers.py`, Palette an
   `_risk_dot()`-Design angelehnt (saturierter Fill + heller Ring via box-shadow),
   erweitert um Gelb/Amber. `ampel_dot()` gibt diesen Span zurück.
2. **Entkopplung:** `ampel_stage_index()` → `_level_from_thresholds()` direkt
   (kein Emoji-`.index()` mehr). Pill-Farben (`ampel_stage_tone`) bleiben unberührt.
3. **Alert-HTML:** Badge nutzt bereits Farb-Border, kein Emoji — nichts zu tun.
4. **Plain-Text:** CSS unmöglich → Kreis-Emoji entfernen (PO-Entscheidung Details).
5. **Tote Emoji-Reste** (`trip_report._fmt_val`, `AMPEL_LEGEND`) bereinigen.

### Open Questions — GEKLÄRT
- [x] **Plain-Text-Ersatz:** PO-Entscheidung 2026-07-10 → **Emoji ersatzlos weglassen**.
      Official-Notice behält das Wort GRÜN/GELB/ORANGE/ROT; Metriken-Pills im
      Plain-Text tragen künftig nur noch das Label ohne Marker.


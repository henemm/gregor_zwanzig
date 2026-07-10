# Context: fix-1056-vigilance-badge-color

## Request Summary
Amtliche Warnungen der Stufe 2 (Vigilance-Gelb) werden im HTML-Mail-Badge als grün
(`G_SUCCESS`) gerendert — optisch identisch zu „kein Alert". Das Level→Farb-Mapping
soll die reale 4-Stufen-Skala (grün/gelb/orange/rot) abbilden. PO-Vorgabe für die
Analyse: Variante prüfen, in der die höchste Stufe **Violett** statt Rot nutzt, damit
Stufe 3 (Orange) kräftiger Richtung Rot rücken kann → bessere Stufen-Trennung.

## Kern-Fundstelle (Issue-Text veraltet)
Der Issue nennt `compare_html.py:144-159`. Der Code wurde seit #1034/#1087 (ADR-0011,
Epic #1073 Slice 3) in **eine geteilte Komponente** konsolidiert:

**`src/output/renderers/alert/official_alerts.py:56-61`** — das einzige Level→Farb-Mapping:
```python
if alert.level <= 2:
    color = G_SUCCESS      # ← BUG: Level 2 (gelb) wird grün
elif alert.level == 3:
    color = G_WARNING      # orange
else:
    color = G_DANGER       # rot
```

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/output/renderers/alert/official_alerts.py:56-61` | **Zu fixen**: Level→Farb-Mapping (einzige Stelle) |
| `src/output/renderers/alert/official_alerts.py:24-29` | `_LEVEL_WORDS`: mappt bereits KORREKT 1🟢/2🟡/3🟠/4🔴 (Text, #1172) → Beweis der Inkonsistenz |
| `src/output/renderers/email/design_tokens.py:25-29` | Farb-Tokens: nur `G_SUCCESS/G_WARNING/G_DANGER` — **kein Gelb, kein Violett** vorhanden |
| `src/services/official_alerts/models.py:19` | `OfficialAlert`-Docstring dokumentiert Semantik „1=grün, 2=gelb, 3=orange, 4=rot" — Renderer widerspricht dem |
| `src/services/official_alerts/vigilance.py:135` | Vigilance emittiert nur `level >= 2` → **Level 2 ist der Regelfall**, nicht die Ausnahme |
| `src/output/renderers/email/html.py:1413` | Konsument 1: Trip-Briefing-Mail ruft `render_official_alerts_html` |
| `src/output/renderers/email/compare_html.py:422,429-437` | Konsument 2: Orts-Vergleich-Mail (Thin-Wrapper `_render_official_alerts_block`) |

## Existing Patterns
- **Ein geteilter Renderer** für beide Mail-Pfade (Compare + Trip-Briefing) — Fix wirkt automatisch auf beide.
- **Token-Additiv**: Neue semantische Farben werden in `design_tokens.py` als `G_*`-Konstante ergänzt (nie bestehende umbenennen — s. Risiken).
- Badge = `border-left:4px solid {color}` auf `G_PAPER`-Hintergrund, Text in `G_INK` (dunkel). **Die Farbe ist ein 4px-Rand-Akzent, keine Textfarbe.**
- `_LEVEL_WORDS` zeigt das bereits etablierte 4-Stufen-Vokabular (Emoji + GRÜN/GELB/ORANGE/ROT) für den Standalone-Text.

## Dependencies
- **Upstream:** `OfficialAlert.level` (int 1-4), `design_tokens.py`-Farbkonstanten.
- **Downstream:** `render_official_alerts_html` → Trip-Briefing-Mail **und** Compare-Mail. Beide Mail-Pfade liegen hinter:
  - **Renderer-Mailgate #811** (`renderer_mail_gate.py`) — blockt Commit auf Mail-Inhalts-Dateien bis `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` grün.
  - **Mail-Validatoren** (`briefing_mail_validator.py` / `email_spec_validator.py`) für „E2E bestanden".

## Existing Specs
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — Fundament OfficialAlert.
- `docs/specs/modules/issue_1087_*` (Trip-Alert-Renderer, ADR-0011) — Byte-Gleichheits-Kontrakt.

## Risks & Considerations
1. **Golden-Byte-Regression (#1087 AC-2):** `tests/tdd/test_issue_1087_trip_official_alerts.py:348-354`
   friert ein **Level-3-Badge** auf `#c8882a` (G_WARNING/orange) ein. → Bleibt Stufe 3 = orange,
   ist der Test unberührt. Wird Stufe 3 (PO-Violett-Idee) kräftiger Richtung Rot verschoben,
   **muss dieses Golden-Fragment mit-aktualisiert werden** (bewusst, mit Begründung).
2. **Token-Test hart:** `tests/tdd/test_email_design_tokens.py:47-49` asserted die exakten Hex-Werte
   von `G_SUCCESS/G_WARNING/G_DANGER`. → **Neue Tokens hinzufügen, bestehende NICHT ändern/umbenennen.**
3. **Kontrast des Farb-Rands (WCAG):** Der 4px-Rand ist ein **grafisches** Element (WCAG-Schwelle 3:1 zu
   G_PAPER `#f6f4ee`), keine Textfarbe. Ein reines Hell-Gelb kann auf Off-White < 3:1 → unsichtbar werden.
   → Analyse muss einen **ausreichend dunklen Gelb-/Amber-Ton** wählen (PO-Grundsatz „Lesbarkeit vor Optik").
4. **Farbe = alleiniger Severity-Träger im Badge:** Der Badge trägt aktuell KEIN Level-Wort/Emoji
   (das steckt nur im Standalone-Text). Bei nur-Farbe verstößt das gegen PO-Grundsatz „Akzent nie
   alleiniger Lesbarkeits-Träger". Analyse prüft, ob das Level-Wort (GELB/ORANGE/ROT) in den Badge gehört —
   entweder in Scope oder als bewusster Folge-Eintrag (#1199).
5. **Zwei Mail-Pfade** ändern sich gleichzeitig (Compare + Trip-Briefing) → Staging-Verifikation beider.

## PO-Vorgabe für die Analyse (verankert)
Analyse arbeitet konkrete Hex-Werte für die 4-Stufen-Skala aus, stellt **Variante A (amtlich: rot oben)**
gegen **Variante B (Violett oben, Orange kräftiger)** gegenüber, prüft je Stufe den Rand-Kontrast (≥3:1 zu
G_PAPER) und legt in der Spec eine **begründete Empfehlung** vor. Finale Farbwahl entscheidet der PO bei der
AC-Freigabe.

## Analysis

### Type
Bug (klarer Root Cause, ein 6-Zeilen-Block; kein Agenten-Fan-out nötig).

### Root Cause
`official_alerts.py:56-61` mappt `level <= 2 → G_SUCCESS` (grün). Vigilance emittiert nur
`level >= 2`, d.h. jede Vigilance-Warnung fällt in diesen Zweig und wird grün gerendert —
optisch = „kein Alert". Widerspricht `OfficialAlert`-Docstring **und** dem `_LEVEL_WORDS`-Text
derselben Datei (der bereits 2🟡GELB sagt).

### Kontrast-Analyse (Rand-Akzent vs. G_PAPER #f6f4ee, grafische Schwelle 3:1)
- Bestand: G_SUCCESS 4,55:1 ✓ · **G_WARNING 2,72:1 ✗ (unter Schwelle!)** · G_DANGER 5,37:1 ✓
- Helle Gelbtöne (#ffd400/#e6b800/#caa316): 1,3–2,2:1 → unbrauchbar; Gelb muss dunkel (Gold/Senf) sein.
- **Ergebnis:** Variante A (rot oben) scheitert praktisch — Gelb/Orange zu nah, Stufe 3 säße auf
  sub-Schwellen-G_WARNING. **Variante B (Violett oben)** trennt alle 4 Stufen sauber, jede ≥3:1.

### Empfohlene Palette (Variante B — PO entscheidet final bei AC-Freigabe)
| Level | Bedeutung | Token | Hex | Kontrast |
|-------|-----------|-------|-----|----------|
| 1 | grün | `G_SUCCESS` (unverändert) | #3a7d44 | 4,55:1 |
| 2 | gelb | `G_ALERT_L2` (neu) | #9a6f00 | 4,11:1 |
| 3 | orange→rot | `G_ALERT_L3` (neu) | #c8482a | 4,32:1 |
| 4 | violett | `G_ALERT_L4` (neu) | #6d28d9 | 6,46:1 |

Mapping als `_LEVEL_COLORS: dict[int,str]` (spiegelt `_LEVEL_WORDS`), Fallback `>4 → G_ALERT_L4`.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/email/design_tokens.py` | MODIFY | +3 Tokens `G_ALERT_L2/L3/L4` (G_WARNING/G_DANGER unangetastet) |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `if/elif`-Kette → `_LEVEL_COLORS`-Dict; Import der neuen Tokens |
| `tests/tdd/test_email_design_tokens.py` | MODIFY | Assert der 3 neuen Token-Hex-Werte |
| `tests/tdd/test_issue_1087_trip_official_alerts.py` | MODIFY | Golden-Fragment (Level-3-Badge) auf neuen Rot-Orange-Wert nachziehen (bewusst) |
| `tests/tdd/test_official_alert_badge_color.py` | CREATE | Repro (verhaltensbenannt): Level-2-Badge ≠ G_SUCCESS, je Level korrekte Farbe |

### Scope Assessment
- Files: 5 (2 src, 3 tests) · Est. LoC: +50/-10 (≪ 250) · Risk: **MEDIUM** (geteilter Mail-Renderer, 2 Pfade, Mailgate #811)

### Technical Approach
Reine Mapping-Korrektur + additive Tokens. Kein Verhaltens-/Datenpfad-Risiko. Golden-Byte-Test
(Level 3) bewusst mit-aktualisieren, weil Stufe 3 farblich verschoben wird.

### Open Questions
- [ ] **Level-Wort im Badge?** Der Badge trägt aktuell nur Farbe als Severity-Cue (Text = Label, kein
  „GELB/ORANGE"). Robuster gegen Farbfehlsichtigkeit wäre, das Level-Wort in den Badge zu nehmen.
  **Empfehlung: NICHT in diesem Fix** (bläht Golden/Validator-Fläche auf) → als Folge-Eintrag #1199.
  Dieser Fix behebt den gemeldeten Bug (Farbe), nicht die Badge-Struktur.


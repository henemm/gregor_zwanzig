<!-- gregor-zwanzig-handoff: stable_id=ink-contrast-audit -->
# Issue 16 · Contrast-Audit der Ink-Skala (WCAG-AA-Konformität auf weißer Card)

**Type:** Accessibility · Tokens · Documentation
**Priority:** Medium (Folgewerk zu #15 — kein Blocker, aber Konsequenz aus dem PO-Leitprinzip „hoher Kontrast = Lesbarkeit")
**Design Reference:**
- PO-Leitprinzip: `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md` § „Folge-Beobachtung"
- Token-Definitionen: `docs/design-system/TOKENS.md` § Ink

---

## Problem

Nach Festlegung des PO-Leitprinzips „hoher Kontrast = Lesbarkeit" (2026-05-25) und der Surface-Entscheidung in #15 (`--g-card #ffffff`) ergibt sich, dass **`--g-ink-4 #9a958a` auf weißer Card nur 2.85:1** liefert — unter WCAG-AA-Minimum von 4.5:1 für normalen Text.

`docs/design-system/TOKENS.md` nennt `--g-ink-4` zwar als „Hint, Placeholder, Captions". WCAG erlaubt Placeholder und Disabled-States als kontrastausgenommen (dekorativ), aber **Captions sind echter Inhalt** und müssen AA erfüllen. Es ist heute nicht überprüft, ob/wo `--g-ink-4` in der Codebase für tatsächlichen Caption-Text verwendet wird.

Sekundär: `--g-accent #c45a2a` auf Weiß liefert 4.5:1 — gerade AA-konform, aber **nicht AAA-konform** (7:1). Für reinen Link/Body-Text bedeutet das: nicht ausschließlich farbig markieren — zusätzlich Unterstreichung oder Bold.

---

## Konzept · Drei Audit-Schritte

1. **Messen** — Kontrast-Matrix für alle Ink-, Accent- und Semantic-Tokens auf den drei produktiven Hintergründen (`--g-card #ffffff`, `--g-card-alt #faf8f1`, `--g-paper #f6f4ee`).
2. **Klassifizieren** — pro Token Verwendungsfreigabe nach WCAG-Schwellen (AA-text, AA-large, AAA-text, „decorative only").
3. **Bereinigen** — `grep`-Audit der Codebase, alle Verstöße entweder ersetzen oder mit explizitem `// audit:exempt — reason`-Kommentar versehen.

---

## Constraints

| ID | Constraint |
|---|---|
| C1 | Kontrastmessung gemäß WCAG 2.1 §1.4.3 (relative luminance, 4.5:1 AA / 7:1 AAA für normalen Text; 3:1 AA / 4.5:1 AAA für Large Text ≥ 18 pt regular oder 14 pt bold). |
| C2 | Body-Text (`< 14 pt`) darf NUR `--g-ink`, `--g-ink-2` (`--g-ink-strong` nach Rename), `--g-ink-3` (`--g-ink-muted`) verwenden. |
| C3 | `--g-ink-4` (`--g-ink-faint`) ist **dekorativ** — ausschließlich für Placeholder, Disabled-State, und rein ornamentale Glyphen ohne Lese-Inhalt. Keine Captions, keine Help-Texte, keine echten Daten-Labels. |
| C4 | `--g-accent` als Textfarbe nur in Kombination mit Unterstreichung oder `font-weight ≥ 600`, weil Color-Only nicht AAA erfüllt. Für reine Akzent-Hintergründe (Pills, Badges) keine Einschränkung. |
| C5 | Semantic-Farben (`--g-good`, `--g-warn`, `--g-bad`, `--g-info`) müssen ebenfalls vermessen werden; falls eine durchfällt → entweder als Hintergrund-Token (Pill-Background) klassifizieren oder Wert anpassen. Wert-Anpassung erfordert PO-Bestätigung. |
| C6 | Backward-compatible: keine Token-Namen ändern, keine Werte ohne PO-Freigabe ändern. Audit ist primär Doku + Cleanup. |

---

## Erwartete Kontrast-Matrix (Vorab-Berechnung Sandbox)

| Token | Wert | auf `#fff` | auf `#faf8f1` | auf `#f6f4ee` | Klassifikation |
|---|---|---|---|---|---|
| `--g-ink` | `#1a1a18` | 19.6 : 1 | 19.0 : 1 | 18.4 : 1 | **AAA-text** ✓ |
| `--g-ink-2` | `#45433d` | 9.7 : 1 | 9.4 : 1 | 9.1 : 1 | **AAA-text** ✓ |
| `--g-ink-3` | `#6b675c` | 5.0 : 1 | 4.8 : 1 | 4.7 : 1 | **AA-text** ✓ (knapp unter AAA) |
| `--g-ink-4` | `#9a958a` | 2.85 : 1 | 2.76 : 1 | 2.68 : 1 | **decorative only** — fällt sogar bei AA-Large (3:1) auf Off-White durch |
| `--g-accent` | `#c45a2a` | 4.55 : 1 | 4.39 : 1 | 4.27 : 1 | **AA-text** (auf Card), borderline auf card-alt/paper — nur mit Underline oder Bold |
| `--g-accent-deep` | `#8c3e1a` | 7.9 : 1 | 7.7 : 1 | 7.5 : 1 | **AAA-text** ✓ — bevorzugte Accent-Text-Farbe |
| `--g-good` | `#3d6b3a` | 6.0 : 1 | 5.8 : 1 | 5.6 : 1 | **AA-text** ✓ |
| `--g-warn` | `#c08a1a` | 3.7 : 1 | 3.6 : 1 | 3.5 : 1 | **AA-large only** — nicht für Body, nur für Labels/Icons ≥ 14 pt bold |
| `--g-bad` | `#a83232` | 6.2 : 1 | 6.0 : 1 | 5.8 : 1 | **AA-text** ✓ |
| `--g-info` | `#2c5a8c` | 6.9 : 1 | 6.7 : 1 | 6.5 : 1 | **AA-text** ✓ |

**Auffällig:** `--g-warn` fällt für Body-Text durch. Häufig wird er aber genau dort verwendet (Tabelle in Briefing-Card zeigt z. B. einen 52 km/h-Wert in Warn-Gelb). Audit muss prüfen, ob das ein Problem ist.

(Vorab-Berechnung — Claude Code soll mit einem zuverlässigen Tool re-messen und Abweichungen melden.)

---

## Acceptance Criteria

- [ ] **Audit-Report** als Datei `docs/design-system/CONTRAST-AUDIT.md` mit der vollständigen Kontrast-Matrix (alle Ink/Accent/Semantic-Tokens × {Card, Card-Alt, Paper}) gemessen mit einem reproduzierbaren Tool (z. B. `wcag-contrast`-npm-Paket oder `axe-core`).
- [ ] **TOKENS.md** ergänzt: pro Token eine „Verwendungs-Freigabe"-Spalte (`AAA-text` / `AA-text` / `AA-large` / `decorative only`).
- [ ] **`grep`-Audit** der Codebase (`frontend/src/`) nach `--g-ink-4` / `--g-ink-faint`:
  - Pro Fundstelle Klassifikation: ist es Placeholder/Disabled (OK) oder echter Caption-Text (FIX)?
  - Liste in `CONTRAST-AUDIT.md` als Anhang.
- [ ] **Fixes durchgeführt** für Caption-/Help-Text-Verstöße: `--g-ink-4` → `--g-ink-3` (jeweils oder kontextbezogen).
- [ ] **`grep`-Audit** nach `--g-accent` als `color:`-Wert (nicht als `background:`):
  - Pro Fundstelle prüfen, ob Underline oder Bold/Weight ≥ 600 gesetzt ist.
  - Falls nicht: hinzufügen.
- [ ] **`grep`-Audit** nach `--g-warn` als `color:`-Wert auf Body-Text-Elementen (`<span>`, `<td>`, `<p>` mit `font-size < 14 pt`):
  - Falls Fundstellen: PO eskalieren (Wert anpassen oder Verwendung ändern — siehe Edge Cases).
- [ ] **Showcase-Route** `/_design-system` ergänzt um eine Sektion „Kontrast-Belege": die Audit-Matrix visuell rendern (Token-Swatch + Kontrast-Zahl + Pass/Fail-Badge), damit künftige Token-Änderungen sofort sichtbar bewertet werden können.

---

## Edge Cases

| Fall | Erwartetes Verhalten |
|---|---|
| `--g-ink-4` als Border-Color (nicht Text) | OK — Borders haben kein WCAG-Minimum (außer Form-Inputs §1.4.11 = 3:1 vs. Hintergrund; `--g-ink-4` liefert das knapp). |
| `--g-ink-4` als Icon-Color (dekorativer Glyph ohne Lesefunktion) | OK — keine Lese-Bedeutung. Aber: wenn das Icon eine Information trägt (Status, Aktion), dann fällt es unter §1.4.11 (3:1) — und `--g-ink-4` ist mit 2.85:1 unter dem Schwellenwert. Fix: `--g-ink-3`. |
| `--g-warn` als Text-Farbe in einer Briefing-Tabelle (Wert „52 km/h") | Diskussion mit PO: a) Wert anpassen auf `#a87a14` (~5:1), oder b) Symbol-Affordance ergänzen (Warn-Dreieck-Glyph), damit der gelbe Wert nicht alleinige Information trägt. Empfehlung: (b), weil Wertanpassung die Brand-Konsistenz mit `--g-weather-sun` (gleicher Hex-Stamm) bricht. |
| Dark-Mode-Variante (falls je gebaut) | Außerhalb dieses Audits — eigener Issue. |
| User-eigene Browser-/OS-Themes mit Color-Override | Außerhalb — nicht Verantwortung der App. |

---

## Out of Scope (Folge-Issues)

- **Dark-Mode-Variante**: Kontrast-Audit für eine hypothetische Dark-Variante. Erst wenn Dark-Mode überhaupt gebaut wird.
- **Token-Wert-Änderungen**: Falls das Audit ergibt, dass `--g-warn` nicht ausreicht — die Wert-Anpassung ist ein separater PO-Entscheidungs-Issue (kein Code-Change ohne Freigabe, siehe C6).
- **Komponenten-API-Änderungen**: Falls eine Komponente strukturell falsch designt ist (z. B. Caption ohne semantische Struktur) — eigener Issue. Hier nur Token-Verwendung in Bestandskomponenten korrigieren.
- **Forms-WCAG-Audit** (§1.4.11 Form-Input-Borders, §1.3.5 Autocomplete) — eigener Accessibility-Issue.

---

## Referenz-Dateien

1. `docs/design-system/TOKENS.md` — aktuelle Token-Definitionen
2. `tokens.css` — Werte (kanonisch)
3. `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md` — PO-Leitprinzip + ursprüngliche Beobachtung
4. WCAG 2.1 §1.4.3 (Contrast Minimum), §1.4.6 (Contrast Enhanced), §1.4.11 (Non-Text Contrast)

---

## Sequenz-Hinweis

Dieses Issue ist **kein Blocker für #15**. Beide können parallel laufen. Logische Reihenfolge:

1. #15 baut die Atomic-Library — referenziert dabei korrekt benannte Ink-Tokens (post-Rename oder Bridge).
2. #16 (dieses Issue) misst, dokumentiert, bereinigt — touchiert dieselben Bausteine ggf. nochmal, aber nur an der Stelle, wo das Audit ein konkretes Problem findet.
3. Showcase-Sektion „Kontrast-Belege" landet im selben `/_design-system`-Route wie #15.

<!-- gregor-zwanzig-handoff: stable_id=surface-stack-migration -->
# Issue 17 · Surface-Stack-Migration — weiße Cards auf warmer Off-White-Page

**Type:** Foundation · Tokens · Visual-Regression
**Priority:** High (Blocker für die noch offenen Unter-Issues des Atomic-Design-Epics #368)

**Design Reference:**
- PO-Entscheidung + Leitprinzip: `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md` § A2
- Leitprinzip in `CLAUDE.md` § „Design-Leitprinzipien (PO-bestätigt)" — *hoher Kontrast = Lesbarkeit*
- Sandbox-Source: `tokens.css` (Repo-Root) — die Sandbox-Werte sind die Migrations-Zielwerte

---

## Problem

`frontend/src/app.css` und Sandbox-`tokens.css` divergieren in den Surface-Werten. Die Production-Card-Surface (`--g-surface-1 #edeae1`) sitzt auf einer ebenfalls beigen Page-Surface — Cards „verschmelzen" mit dem Hintergrund. Das verletzt das PO-Leitprinzip „hoher Kontrast = Lesbarkeit" und macht Card-Container in Briefings / Metrics-Editor / Mobile-Listen schlecht greifbar.

Die Sandbox hat dieses Problem nicht: Cards sind reinweiß auf warmer Off-White-Page. Diese Entscheidung wurde am 25. Mai 2026 vom PO bestätigt.

---

## Konzept · Nur Werte tauschen, keine Namen ändern

Dieses Issue **tauscht ausschließlich Werte** im Surface-Stack von `app.css`. Es **nutzt weiter die bestehenden Code-Namen** (`--g-surface-0/1/2/raised`). Token-Rename ist ein **separates Folge-Issue** und kommt **nach** diesem.

**Rationale für die Reihenfolge:** Werte vor Namen ist die kleinere, fokussiertere Änderung. Atom-Migration (offene #368-Unter-Issues) muss auf finalen Surface-Werten landen, sonst werden Atome zweimal angefasst. Naming-Migration kann danach in Ruhe folgen, weil sie Werte unangetastet lässt.

---

## Zielwerte (Sandbox-Stack)

| `app.css`-Token | Aktueller Wert | **Neuer Wert** | Sandbox-Pendant | Rolle |
|---|---|---|---|---|
| `--g-surface-0` | (prüfen) | `#f6f4ee` | `--g-paper` | Page-Hintergrund, warm Off-White |
| `--g-surface-1` | `#edeae1` | **`#ffffff`** | `--g-card` | Karten, Modals, Eingabe-Container — **der Knackpunkt** |
| `--g-surface-2` | (prüfen) | `#ecead9` | `--g-paper-deep` | Tieferliegende Surface (Page-Section-Dividers, Footer) |
| `--g-surface-raised` | (prüfen) | `#faf8f1` | `--g-card-alt` | Card-in-Card, Striping, Hover-Tint |
| `--g-rule` | (prüfen) | `#d8d3c2` | `--g-rule` | Sichtbare Linien |
| `--g-rule-soft` | (prüfen) | `#e7e2d3` | `--g-rule-soft` | Subtile Linien innerhalb Cards |

Alle anderen Tokens (Ink, Accent, Semantic, Weather, Radii, Shadows, Fonts) bleiben **unverändert**. Auch Code-Namen bleiben unverändert.

---

## Constraints

| ID | Constraint |
|---|---|
| C1 | Nur Werte tauschen, keine Namen ändern, keine neuen Tokens hinzufügen. |
| C2 | Migration findet **vor** der Token-Rename-Migration und **vor** allen noch offenen Unter-Issues von Epic #368 statt. Bereits fertige Unter-Issues (#369 Token-Bridge, #370 Brand-Bibliothek) werden auf die neuen Werte gehoben, nicht neu gebaut. |
| C3 | Keine Inline-Hex-Werte in Komponenten oder Page-CSS. Alle Surface-Referenzen müssen über `var(--g-surface-*)` laufen. Falls Audit Inline-Werte findet → ersetzen (siehe Acceptance Criteria). |
| C4 | Dark-Mode-Variante (`.dark` block in `app.css`) bleibt in diesem Issue **unangetastet**. Falls bereits eine Dark-Variante existiert, wird sie separat in einem Folge-Issue ans neue System angeglichen. |
| C5 | Visuelle Regression: Vor und nach der Änderung Screenshots derselben drei Routes (`/`, `/trips/[id]`, `/trips/neu` oder Pendant) ablegen — als Beleg in der PR. |
| C6 | Shadow-Tokens (`--g-elev-1/2/3` oder `--g-shadow-1/2/3`) ggf. nachjustieren: weiße Cards auf warmem Hintergrund brauchen leicht stärkere Schatten als beige-auf-beige, sonst „schweben" sie nicht visuell. Empfehlung: aktuelle Werte verdoppeln in Alpha (`rgba(26,26,24,.04)` → `rgba(26,26,24,.08)` für `--g-elev-1`). PO-Bestätigung holen, falls signifikante Änderung. |

---

## Acceptance Criteria

- [ ] **`frontend/src/app.css`** im `:root`-Block: alle sechs Surface/Rule-Werte aus der Tabelle oben gesetzt.
- [ ] **`grep -rn "#edeae1\|#ecead9\|#e8e3d4" frontend/src/`**: keine verbleibenden Treffer in produktivem Code. Falls vorhanden → durch `var(--g-surface-*)` ersetzen. Treffer in `app.css` selbst sind erwartet (Wert-Definition, nicht Verwendung).
- [ ] **Showcase-Route** (`/_design-system` oder Pendant) rendert visuell konsistent: Cards sind weiß, Page-Hintergrund warm Off-White, Card-Alt-Container sichtbar abgesetzt.
- [ ] **Visual-Regression-Belege:** Screenshots vor/nach für mindestens `/` (Home), `/trips` (Listing), `/trips/neu` (Wizard) — als PR-Anhang. PO sieht sich die Belege an.
- [ ] **Shadow-Audit:** Falls Karten visuell „verschwimmen" — `--g-elev-*`-Alpha leicht erhöhen (siehe C6) und in PR begründen.
- [ ] **`.dark`-Block:** unverändert; falls darin Surface-Werte stehen, mit Kommentar `/* Dark-Surface-Migration: eigener Folge-Issue */` markieren.
- [ ] **Sync-Eintrag in `docs/design-system/TOKENS.md`:** Tabelle der neuen Surface-Werte ergänzen / aktualisieren, damit Doku und Code wieder deckungsgleich sind.

---

## Edge Cases

| Fall | Erwartetes Verhalten |
|---|---|
| Ein bestehendes Atom (z. B. aus #370) verwendet `background: var(--g-surface-1)` | Funktioniert automatisch — Atom rendert nach Migration mit weißem Card-Hintergrund, kein Code-Change am Atom nötig. |
| Eine Komponente verwendet Inline-Hex (`background: #edeae1`) | Verstoß gegen C3. Fix: durch Token-Referenz ersetzen. |
| Eine Komponente verwendet `--g-surface-1` als **Text**-Farbe (statt Hintergrund) | Sehr unwahrscheinlich, aber möglich. Im PR begründen oder fixen. |
| Card auf weißer Card (z. B. Modal über Listing) | Soll funktionieren — Modal kriegt `--g-surface-raised` (`#faf8f1`), Hintergrund-Listing bleibt `--g-surface-1` (`#ffffff`). Falls visuell zu wenig Trennung: Shadow-Audit nach C6. |
| Forms-Inputs mit `--g-surface-1`-Hintergrund | Bisher beige-Input auf beige-Card war passabel. Künftig: weißer Input auf weißer Card — Border muss klar sichtbar bleiben. Falls Input verschwindet: Border-Color auf `--g-rule` (`#d8d3c2`) sicherstellen. |
| Print-CSS (falls vorhanden) | Surface-Tokens werden in Print üblicherweise auf `transparent` / `#fff` gemappt — unverändert lassen. |

---

## Out of Scope (eigene Folge-Issues)

- **Token-Rename** (`--g-surface-0/1/2/raised` → bleibt; Sandbox-Namen ziehen nach): separater Issue, basiert auf Mapping-Tabelle aus `RESPONSE-FROM-CLAUDE-DESIGN.md` § A3. Bestätigt durch PO ohne Disagreement.
- **Dark-Mode-Surface-Migration:** Erst wenn Dark-Mode überhaupt offiziell wird.
- **Shadow-System-Überarbeitung** (z. B. neue Elevation-Stufe): falls C6 zeigt, dass die heutigen drei Stufen nicht reichen.
- **Form-Component-Borders:** Falls Input-/Select-Borders nach Migration zu schwach werden — eigener UX-Polish-Issue.

---

## Referenz-Dateien

1. `tokens.css` (Sandbox, Repo-Root) — kanonische Quelle der Zielwerte
2. `docs/design-system/TOKENS.md` — Doku, wird mit-aktualisiert
3. `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md` § A2 — PO-Entscheidung
4. `CLAUDE.md` § „Design-Leitprinzipien (PO-bestätigt)" — Leitprinzip

---

## Sequenz im Kontext der laufenden Migration

```
Heute (Mai 2026):
  ✅ #369 Token-Bridge — abgeschlossen, Produktion
  ✅ #370 Brand-Bibliothek (BrandIcon/Wordmark) — abgeschlossen, Produktion
  🔄 #371–#374 Atomic-Design-Unter-Issues — offen

Reihenfolge ab jetzt:
  → 1. DIESES Issue (#17 Surface-Stack-Migration) — Werte tauschen
  → 2. Token-Rename-Issue (folgt, basiert auf A3-Mapping-Tabelle)
  → 3. #371–#374 abschließen — laufen auf finalen Werten + finalen Namen
  → 4. #377 Contrast-Audit der Ink-Skala — misst gegen finale Surface-Werte
  → 5. Organisms-Migration nach Abschluss von #364 (Output-Layout-System)
```

Dieses Issue ist **klein im Scope**, aber **hohe Priorität**, weil es allen folgenden Atom-Migrationen erspart, später erneut angefasst zu werden.

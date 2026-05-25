# Rückmeldung an Claude Design · Atomic-Design-Angleichung (Handoff-Issue #15)

**Adressat:** Claude Design (claude.ai/design) · liest dieses Repo, **nicht** GitHub-Issues — daher liegt diese Rückmeldung als Datei im Repo.
**Bezug:** Handoff `h/jRZoYSUSOBacVsm3RSbgQg`, Spec `claude-code-handoff/issue-bodies/body-15-atomic-design-library.md` (stable_id=`atomic-design-component-library`).
**Erstellt:** 2026-05-25 von Claude Code (Repo `henemm/gregor_zwanzig`).
**Spec-Kopien für diese Migration:** `docs/design-requests/issue_15_atomic_design/spec/` (brand-kit / atoms / molecules / mobile-shell / screen-design-system / organisms / tokens.css / inventory / body-15).

---

## 0 · Gesamthaltung

Wir übernehmen die Atomic-Design-Hierarchie **1:1** in den SvelteKit-Code. Ziel ist der vom PO gewünschte 1:1-Bezug zwischen Design-Bausteinen und Code-Bausteinen.

Entscheidungen des Product Owners zu dieser Migration:
- **Fundament zuerst:** erst die Bibliothek (Brand · Atoms · Molecules · Mobile-Primitive) + Showcase-Route bauen, dann ziehen die Screens nach.
- **Mobile-Layer vollständig:** die komplette `M*`-Touch-Bausteinsammlung aus `mobile-shell.jsx` wird mitgebaut (nicht nur bei Bedarf).

Das meiste ist bei uns bereits vorhanden — `frontend/src/lib/components/ui/` (shadcn-svelte-Stil, Svelte 5 Runes + TypeScript) deckt die Mehrzahl der Atome ab. Es ist überwiegend **Umsortieren + Umbenennen + ein paar neue Molecules + der Marken-Glyph**, kein Neubau.

Die folgenden Punkte sind die Stellen, an denen ein **wörtliches** 1:1 nicht praktikabel ist — mit Bitte um Reaktion auf eurer Seite, wo markiert.

---

## A · BLOCKER: Token-Vokabular weicht ab (Action für Claude Design)

Die Design-Tokens sind die unterste Schicht des gemeinsamen Vokabulars. Aktuell existieren **zwei nicht-deckungsgleiche Namenssätze**:

| Quelle | Vokabular |
|---|---|
| Sandbox `tokens.css` **und** repo `docs/design-system/TOKENS.md` | `--g-good` / `--g-warn` / `--g-bad`, `--g-card` / `--g-card-alt`, `--g-weather-*`, `--g-font-sans` / `--g-font-mono`, `--g-rule`, `--g-shadow-1..3`, `--g-ink-2..4`, `--g-accent-deep/soft/tint`, `--g-r-1..4` |
| Ausgelieferte Produktion `frontend/src/app.css` (speist 142 Komponenten) | `--g-success` / `--g-warning` / `--g-danger`, `--g-surface-0..2` / `--g-surface-raised`, `--g-wx-*`, `--g-font-ui` / `--g-font-data`, `--g-rule-soft`, `--g-elev-1..3`, `--g-ink-faint/muted/strong`, nur `--g-accent` |

Folge: Würden wir eure JSX-Bausteine wörtlich übernehmen, zeigen sie auf **nicht existierende** Tokens → kein Rendering (das warnt body-15 §C1/Schritt-1 selbst an).

**Korrektur (Wert-Abgleich durchgeführt):** Die Divergenz ist **Name UND Wert** — nicht nur Benennung. Beispiele: `--g-card` ist im Design **reines Weiß** `#ffffff`, unser nächstes Pendant `--g-surface-1` ist beige `#edeae1`; `--g-weather-snow`/`-sun` und einige Radien (`--g-r-3/4`) weichen ebenfalls ab. Vollständige Gegenüberstellung: **`spec/TOKEN-MAPPING.md`**.

**Unser Vorgehen (Code-Seite, ohne eure Mitwirkung nötig):**
Damit die 1:1 übernommenen Atomic-Bausteine **pixeltreu zum Design** rendern, ergänzen wir die Sandbox-Tokens **mit den Sandbox-Werten unter den Sandbox-Namen additiv** in `app.css` (nicht als Alias auf abweichende Bestands-Werte). Bestehende Tokens bleiben unangetastet → keine bestehende Route ändert sich (body-15 §C6). Wo Name **und** Wert identisch sind, aliasen wir (`--g-font-sans → var(--g-font-ui)`). Drei Namens-Kollisionen (`--g-info`, `--g-paper-deep`, `--g-rule-soft`) behalten **unseren** Wert.

**Die zwei „Lücken"-Tokens sind geklärt:** `--g-accent-deep/soft/tint` und `--g-weather-cloud` sind in eurer `tokens.css` bereits mit Werten definiert (`#8c3e1a` / `#f3d9c8` / `rgba(196,90,42,.08)` / `#9a958a`) — wir übernehmen diese. Bitte nur **bestätigen**, dass sie so beabsichtigt sind.

**Echte Design-Frage an euch + PO:** Durch die Wert-Unterschiede koexistieren vorerst **zwei leicht verschiedene Farbwelten** (neue Bibliothek = Sandbox-Werte, Bestands-Screens = app.css-Werte). Soll die *gesamte* App perspektivisch auf die Sandbox-Werte umstellen — insbesondere **weiße Karten überall** statt beige? Das ist eine Design-Entscheidung, kein Code-Thema, und wird **nicht** im Fundament-Epic gelöst. Bitte Position dazu.

**Langfristige Namens-Vereinheitlichung:** Damit künftige Handoffs *ohne* additive Doppel-Tokens 1:1 passen, sollten wir uns auf **einen** kanonischen Namenssatz einigen. Da `docs/design-system/TOKENS.md` bereits eure Namen führt, wäre der saubere Weg, perspektivisch auch `app.css` darauf umzustellen (großer Rename über 142 Dateien — eigenes Issue). Bis dahin trägt die Bridge.

---

## B · Compound-Bausteine bleiben reichhaltiger als die Skizzen (kein Action nötig)

Unsere `Dialog`-, `Table`-, `Select`- und `Card`-Bausteine sind im Code bereits **zusammengesetzt und barrierefrei** (mehrteilig, ARIA-konform, auf bits-ui/shadcn-svelte-Basis). Im Sandbox-Modell ist `Card` ein einzelnes Atom, und `Dialog`/`Table`/`Select` existieren nur als Inline-Markup in den Screens.

**Entscheidung:** Wir behalten unsere Compound-Bausteine als kanonische Code-Variante. Bitte diese **nicht** als flache Einzel-Atome nachspezifizieren — in der Spec genügt der Verweis „nutzt den bestehenden `Card`/`Dialog`/`Table`/`Select`-Baustein". Visuell bleibt es deckungsgleich; nur die innere Struktur ist im Code reicher.

---

## C · React→Svelte-Idiom: Bausteine sind visuell, nicht strukturell 1:1 (informativ)

Wie in eurem README vorgesehen übersetzen wir pixelgenau, kopieren aber **nicht** die JSX-Interna. Konkret ändern sich Prop-Formen:
- Callback-Props (`onToggle`, `onChange`, `onEdit`) → Svelte-Events / `bind:`-Bindungen.
- Element-als-Prop (`icon={<svg/>}`, `right={…}`) → Svelte-Snippets bzw. benannte Slots.
- `window.X`-Globals → echte Modul-Imports.
- SSR-Festigkeit: keine `window.*`-Zugriffe ohne Browser-Guard (body-15 Edge-Case).

Kein Handlungsbedarf bei euch — nur die Erklärung, warum der Code nicht byte-gleich zur JSX aussieht. Der **Marken-Glyph** (Berg+Blitz-SVG-Pfad in `BrandIcon`/`BrandIconSquare`) wird hingegen **byte-genau** übernommen (body-15 verlangt das).

---

## D · Organisms vorerst nicht migriert (Sequenz-Hinweis)

body-15 schließt eine `organisms/`-Ebene bewusst aus den Acceptance-Kriterien aus. Genau richtig: Der große Organismus (`MetricsEditor` / Output-Layout) wird **gerade aktiv** in Issue **#364** (Schritt B von #331) umgebaut. Wir bauen in #15 nur **Brand + Atoms + Molecules + Mobile-Primitive + Showcase** — additiv, in neuen Ordnern. Die Organisms (`organisms.jsx`) und die Screen-Migration ziehen wir **nach** Abschluss von #364 nach, um Kollisionen zu vermeiden.

Hinweis zur Sandbox: `docs/atomic-design-inventory.md` notiert selbst, dass `screen-metrics-editor.jsx` noch Inline-Kopien der ME*-Sub-Komponenten enthält („beim nächsten Touch durch Organism-API ersetzen"). Das ist ein Aufräum-Punkt auf eurer Seite, keiner bei uns.

---

## E · Veraltete Verweise im Handoff (kleine Korrektur eurerseits)

1. **body-15 „Design Reference"** verweist auf `Gregor 20 - Redesign v2.html` → Section „01 · Komponenten-System". Laut `atomic-design-inventory.md` §0/Session 8 wurde diese Datei aber **gelöscht** und durch **`Gregor 20 - Komponenten.html`** ersetzt. Bitte den Verweis in der Spec auf die neue Datei korrigieren, damit künftige Leser nicht ins Leere laufen.
2. **Repo-Issue #312** (`for:claude-design`: „Fehlende UI-Primitive — Toast, DropdownMenu, Segmented Control, Switch, Sheet") ist durch den aktuellen Stand **weitgehend erfüllt**: `Switch` + `Segmented` liegen in `atoms.jsx`, `Toast`/`Sheet`/`Drawer` in `mobile-shell.jsx`. Wir aktualisieren/schließen #312 auf unserer Seite entsprechend — nur zur Info, dass diese Primitive jetzt spezifiziert sind.

---

## F · Was wir 1:1 übernehmen (Bestätigung, kein Action)

- **Brand:** `BrandIcon`, `BrandIconSquare`, `BrandWordmark` (Lockup = Glyph + Mono-Typo `gregor . zwanzig`, Caption `V0.20 · WETTER-BRIEFING`, Default `icon="left"`), `BrandUserBadge`, `BrandSidebar`, `BrandShell`. SVG-Pfade byte-genau. — Löst zugleich unser offenes Issue **#279** (Wordmark-Glyph).
- **Atoms** (13), **Molecules** (10), **Mobile-Primitive** (12 `M*`) exakt aus dem Katalog in body-15.
- **Showcase-Route** `/_design-system` als Regressions-Referenz, Sektionen 1–6 wie in body-15.
- **Naming-Konvention** und **Konflikt-Regel** (brand-kit gewinnt) wie spezifiziert; die Komponenten-Disziplin (Lese-Regel vor jeder UI-Arbeit) wird in der Frontend-Doku verankert.

---

## Zusammenfassung der Bitten an Claude Design

| # | Bitte | Aufwand bei euch |
|---|---|---|
| A1 | Bestätigen, dass `--g-accent-deep/soft/tint` + `--g-weather-cloud` so beabsichtigt sind (Werte in eurer `tokens.css` vorhanden) | trivial |
| A2 | **Design-Entscheidung:** App-weit auf Sandbox-Werte umstellen (u. a. weiße Karten) — ja/nein? | Entscheidung |
| A3 | Langfristig: ein kanonischer Namenssatz (Vorschlag: `app.css` auf eure Namen umstellen, eigenes Issue) | mittel |
| E1 | body-15 „Design Reference" von `Redesign v2.html` auf `Komponenten.html` korrigieren | trivial |
| B/D | Dialog/Table/Select/Card **nicht** als flache Atome nachspezifizieren; Organisms-Migration erst nach #364 | kein Code, nur Spec-Hinweis |

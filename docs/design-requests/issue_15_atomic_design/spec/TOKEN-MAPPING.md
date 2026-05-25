# Token-Mapping · Sandbox `tokens.css` ↔ Produktion `app.css`

Grundlage für die Token-Bridge (#369). Vergleich der Werte beider Quellen, Stand 2026-05-25.

**Erkenntnis:** Die Divergenz ist **Name UND Wert** — nicht nur Benennung. Mehrere Tokens haben in der Sandbox andere Werte als in unserer ausgelieferten `app.css` (z. B. Karte = reines Weiß vs. beiges Surface). Damit die 1:1 übernommenen Atomic-Bausteine **pixeltreu zum Design** rendern, werden die Sandbox-Werte unter den Sandbox-Namen **additiv** in `app.css` ergänzt. Bestehende Tokens bleiben unangetastet → keine bestehende Route ändert sich.

Legende: **= identisch** · **≈ leicht abweichend** · **✗ deutlich abweichend** · **NEU = bei uns nicht vorhanden** · **KOLLISION = gleicher Name, anderer Wert**

> **Update #378 (Surface-Stack-Migration, 2026-05-25):** Die Spalte „Unser Wert" unten zeigt den Stand **vor** #378. Seither tragen `--g-surface-1` = `#ffffff`, `--g-surface-2` = `#ecead9`, `--g-surface-raised` = `#faf8f1` und `--g-rule-soft` = `#e7e2d3` — Surface-/Rule-Werte von Code und Sandbox sind damit deckungsgleich (einzige Ausnahme: `--g-paper-deep` bleibt `#ede9df`).

| Sandbox-Token | Sandbox-Wert | Unser Pendant | Unser Wert | Status | Bridge-Aktion |
|---|---|---|---|---|---|
| `--g-paper` | `#f6f4ee` | `--g-paper` | `#f6f4ee` | = | nichts (identisch) |
| `--g-paper-deep` | `#ecead9` | `--g-paper-deep` | `#ede9df` | ≈ | unseren behalten |
| `--g-card` | `#ffffff` | `--g-surface-1` | `#edeae1` | ✗ | **NEU** `--g-card: #ffffff` |
| `--g-card-alt` | `#faf8f1` | `--g-surface-2` | `#e3dfd4` | ✗ | **NEU** `--g-card-alt: #faf8f1` |
| `--g-rule` | `#d8d3c2` | — | — | NEU | **NEU** `--g-rule: #d8d3c2` |
| `--g-rule-soft` | `#e7e2d3` | `--g-rule-soft` | `#e7e2d3` | = | **[#378]** migriert → `#e7e2d3` |
| `--g-ink` | `#1a1a18` | `--g-ink` | `#1a1a18` | = | nichts |
| `--g-ink-2` | `#45433d` | `--g-ink-muted` | `#5c5a52` | ✗ | **NEU** `--g-ink-2: #45433d` |
| `--g-ink-3` | `#6b675c` | — | — | NEU | **NEU** `--g-ink-3: #6b675c` |
| `--g-ink-4` | `#9a958a` | `--g-ink-faint` | `#9c9a90` | ≈ | **NEU** `--g-ink-4: #9a958a` |
| `--g-accent` | `#c45a2a` | `--g-accent` | `#c45a2a` | = | nichts |
| `--g-accent-deep` | `#8c3e1a` | — | — | NEU | **NEU** (Sandbox-Wert) |
| `--g-accent-soft` | `#f3d9c8` | — | — | NEU | **NEU** (Sandbox-Wert) |
| `--g-accent-tint` | `rgba(196,90,42,.08)` | — | — | NEU | **NEU** (Sandbox-Wert) |
| `--g-good` | `#3d6b3a` | `--g-success` | `#3a7d44` | ≈ | **NEU** `--g-good: #3d6b3a` |
| `--g-warn` | `#c08a1a` | `--g-warning` | `#c8882a` | ≈ | **NEU** `--g-warn: #c08a1a` |
| `--g-bad` | `#a83232` | `--g-danger` | `#b33a2a` | ≈ | **NEU** `--g-bad: #a83232` |
| `--g-info` | `#2c5a8c` | `--g-info` | `#2a6cb3` | KOLLISION | unseren behalten |
| `--g-weather-rain` | `#4a7ab8` | `--g-wx-rain` | `#4a7fb5` | ≈ | **NEU** `--g-weather-rain` |
| `--g-weather-snow` | `#8aa4c0` | `--g-wx-snow` | `#a8c8e8` | ✗ | **NEU** `--g-weather-snow` |
| `--g-weather-thunder` | `#c43a2a` | `--g-wx-thunder` | `#c43a2a` | = | Alias auf `--g-wx-thunder` |
| `--g-weather-sun` | `#d99a2a` | `--g-wx-sun` | `#e8a820` | ✗ | **NEU** `--g-weather-sun` |
| `--g-weather-cloud` | `#9a958a` | — | — | NEU | **NEU** (Sandbox-Wert) |
| `--g-font-sans` | Inter Tight … | `--g-font-ui` | Inter Tight … | = | Alias `var(--g-font-ui)` |
| `--g-font-mono` | JetBrains Mono … | `--g-font-data` | JetBrains Mono … | = | Alias `var(--g-font-data)` |
| `--g-r-1` | `2px` | `--g-radius-xs` | `2px` | = | Alias `var(--g-radius-xs)` |
| `--g-r-2` | `4px` | `--g-radius-sm` | `4px` | = | Alias `var(--g-radius-sm)` |
| `--g-r-3` | `6px` | `--g-radius-md` | `8px` | ✗ | **NEU** `--g-r-3: 6px` |
| `--g-r-4` | `10px` | `--g-radius-lg` | `12px` | ✗ | **NEU** `--g-r-4: 10px` |
| `--g-r-pill` | `999px` | `--g-radius-pill` | `99rem` | ≈ | Alias `var(--g-radius-pill)` |
| `--g-shadow-1..3` | s. tokens.css | `--g-elev-1..3` | abweichend | ≈ | **NEU** (Sandbox-Werte) |
| `--g-s-1..20` | 4–80px | `--g-s-1..20` | 4–80px | = | nichts (identisch) |
| `--g-text-xs..5xl` | 11–60px | `--g-text-*` | identisch | = | nichts |
| `--g-track-*` | identisch | `--g-track-*` | identisch | = | nichts |

## Konsequenz / offene Design-Frage (für Claude Design + PO)

Die Wert-Unterschiede (vor allem **weiße Karte** vs. beiges Surface, abweichende Semantik-/Wetterfarben) bedeuten: Solange wir additiv brücken, koexistieren **zwei leicht verschiedene Farbwelten** — die neue Atomic-Bibliothek (Sandbox-Werte) und die bestehenden Screens (app.css-Werte). Das ist bewusste, temporäre Doppelung während der Migration.

**Zu klären (kein Blocker für #369):** Soll die *gesamte* App perspektivisch auf die Sandbox-Werte umstellen (z. B. weiße Karten überall)? Das ist eine **Design-Entscheidung**, kein reines Code-Thema → geht an Claude Design / PO, nicht im Fundament-Epic gelöst.

## Drei Kollisionen (gleicher Name, anderer Wert)

`--g-info` und `--g-paper-deep` existieren bei uns bereits mit abweichenden Werten. Wir **behalten unsere Werte** (würde sonst bestehende UI verändern). Neue Bausteine erben für diese zwei unsere Variante — die Unterschiede sind klein und unkritisch. (`--g-rule-soft` wurde mit **#378** auf den Sandbox-Wert `#e7e2d3` migriert — keine Kollision mehr.)

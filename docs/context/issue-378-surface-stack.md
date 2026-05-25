# Context: issue-378-surface-stack

## Request Summary

Surface-Stack-Migration (#378): In `frontend/src/app.css` werden **ausschließlich die Werte** des Surface-/Rule-Token-Stacks auf die Sandbox-Zielwerte getauscht, sodass Karten **reinweiß** (`#ffffff`) auf warmer Off-White-Page sitzen statt beige-auf-beige. **Keine Token-Namen ändern, keine neuen Tokens.** Fundament-Issue: muss vor den offenen Atom-Migrationen (#371–#374) landen, damit Atome nicht zweimal angefasst werden.

## Zielwerte (Quelle: #378-Tabelle + `docs/design-system/TOKENS.md`)

| `app.css`-Token | Ist-Wert | Soll-Wert | Status |
|---|---|---|---|
| `--g-surface-0` | `#f6f4ee` | `#f6f4ee` | ✅ bereits korrekt |
| `--g-surface-1` | `#edeae1` | **`#ffffff`** | ❌ ändern — der Knackpunkt (Karten) |
| `--g-surface-2` | `#e3dfd4` | `#ecead9` | ❌ ändern |
| `--g-surface-raised` | `var(--g-surface-1)` | `#faf8f1` | ❌ ändern (direkter Hex statt Alias) |
| `--g-rule` | `#d8d3c2` | `#d8d3c2` | ✅ bereits korrekt |
| `--g-rule-soft` | `rgba(26,26,24,0.08)` | `#e7e2d3` | ❌ ändern — ⚠️ Konflikt mit #369-Doku (s. u.) |

→ **Effektiv vier Werte zu ändern** (surface-1, surface-2, surface-raised, rule-soft); zwei sind bereits korrekt.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/app.css` (Z. 58–179) | **Kern.** `:root`-Block mit Surface-Stack (Z. 62–70), Rule-Tokens (Z. 140/148), Sandbox-Bridge-Tokens (Z. 146–168), Shadows (Z. 104–106 `--g-elev-*`, Z. 177–179 `--g-shadow-*`). |
| `frontend/src/lib/tokens-bridge.test.ts:82` | **Muss mit-angepasst werden.** `assert.ok(hasDecl('--g-surface-1', '#edeae1'), …)` — sichert aktiv den ALTEN Wert ab. Bricht nach Migration. Zeile auf `#ffffff` heben. Einzige Test-Datei, die Surface-Werte fixiert. |
| `docs/design-system/TOKENS.md` (Z. 9–16) | Doku-Sync (AC). Dokumentiert bereits Sandbox-Namen (`--g-card #ffffff`, `--g-card-alt #faf8f1`, `--g-paper-deep #ecead9`), aber **keine `--g-surface-*`-Tabelle** → ergänzen. |
| `docs/design-requests/issue_15_atomic_design/spec/TOKEN-MAPPING.md` (Z. 12, 54) | #369-Entscheidung: „`--g-rule-soft`/`--g-paper-deep` behalten unsere Werte". **#378 hebt diese Entscheidung für `--g-rule-soft` auf** → Doku-Notiz nötig. |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` (Z. 8/51) | Nutzt `--g-surface-raised` (Aktiv-Hervorhebung). Profitiert automatisch vom neuen Wert, kein Code-Change. |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte:455` | `background: var(--g-surface-raised)`. Ebenso automatisch. |
| `frontend/src/lib/components/.../*[data-slot="g-card"]` (app.css:338–345) | Card-Slot nutzt `background: var(--g-surface-1)` + `box-shadow: var(--g-elev-1/2)`. Wird nach Migration weiß; Shadow-Audit (C6) hier relevant. |

## Existing Patterns

- **Token-Bridge (#369, fertig):** Sandbox-Namen (`--g-card`, `--g-card-alt`, `--g-good`, `--g-weather-*`, `--g-font-sans`) sind bereits in `app.css` als parallele Definitionen/Aliase vorhanden. `--g-card` ist schon `#ffffff` — nach #378 wird `--g-surface-1` damit deckungsgleich (die Production-Komponenten nutzen aber `--g-surface-1`, daher die Notwendigkeit von #378).
- **Alle Surface-Referenzen laufen über `var(--g-surface-*)`** — Audit ergab **keine** Inline-Hex-Verstöße (C3) in produktivem Code. Einzige Hex-Treffer der alten Werte: die Definitionen in `app.css` selbst (erwartet) + der o. g. Regressions-Test.
- **Zwei Shadow-Systeme nebeneinander:** `--g-elev-1/2/3` (von Card-Slots genutzt) und `--g-shadow-1/2/3` (Bridge). C6 betrifft die von Cards tatsächlich genutzten `--g-elev-*`.

## Dependencies

- **Upstream (Quelle der Zielwerte):** #378-Tabelle + `TOKENS.md`. ⚠️ Die in #378 als „kanonische Quelle" referenzierte `tokens.css` im Repo-Root **existiert nicht (mehr)** — Quelle der Wahrheit ist daher die Issue-Tabelle und `TOKENS.md`.
- **Downstream:** Alle Komponenten mit `var(--g-surface-1/2/raised)` rendern automatisch neu (Cards weiß). Offene Atom-Migrationen #371–#374 bauen auf den finalen Werten auf — #378 ist deren Blocker.

## Existing Specs

- Kein `docs/specs/modules/`-Eintrag für #378 vorhanden → in Phase 3 neu anlegen (`issue_378_surface_stack.md`), AC-N-Format (created ≥ 2026-05-11).
- Verwandt: Epic #368 (`docs/design-requests/issue_15_atomic_design/spec/body-15-atomic-design-library.md`), TOKEN-MAPPING.md.

## Risks & Considerations

1. **Test-Regression (sicher):** `tokens-bridge.test.ts:82` bricht garantiert. Anpassung auf `#ffffff` ist Teil von #378, nicht optional. TDD-RED kann genau diesen Test als Startpunkt nutzen.
2. **Doku-Konflikt #369 ↔ #378 bei `--g-rule-soft`:** TOKEN-MAPPING.md sagt „behalten" (`rgba(26,26,24,0.08)`), #378 sagt ändern (`#e7e2d3`). #378 ist neuer + höher priorisiert → gewinnt. TOKEN-MAPPING.md-Notiz muss aktualisiert werden, sonst widersprüchliche Doku.
3. **`--g-paper-deep` Inkonsistenz:** app.css hat `#ede9df`, Sandbox-Ziel ist `#ecead9` (= neuer `--g-surface-2`). #378-Tabelle listet `--g-paper-deep` NICHT → bleibt per C1 unangetastet. Erzeugt minimal abweichenden Beige-Ton zwischen surface-2 und paper-deep. In Analyse entscheiden, ob mit-angeglichen wird (sauber) oder strikt nach Tabelle (konservativ).
4. **Shadow-Audit (C6):** Cards nutzen `--g-elev-1` (`rgba(26,26,24,0.08)`). Bei beige→weiß evtl. zu schwach → Karten „verschwimmen". Visuell prüfen; bei Bedarf Alpha leicht erhöhen — **PO-Bestätigung bei signifikanter Änderung** (Issue-Vorgabe).
5. **Form-Inputs (Edge Case):** weißer Input auf künftig weißer Card — Border (`--g-rule #d8d3c2`) muss klar sichtbar bleiben. Visuell prüfen.
6. **`.dark`-Block (C4):** existiert NICHT in app.css → trivial erfüllt, nichts zu tun.
7. **Visual-Regression-Routes (C5):** Real existierende Pfade: `/` (Home), `/trips` (Listing), `/trips/new` (Wizard — **nicht** `/touren/neu`). Showcase-Route ist `/_design` (**nicht** `/_design-system`; letztere wäre #374, noch offen).
8. **LoC:** sehr klein (≈4 CSS-Werte + 1 Testzeile + Doku). Weit unter 250-Limit.

## Analyse-Ergebnisse (Phase 2 — getroffene Entscheidungen)

Unabhängige Strategie-Bewertung (Plan-Agent) bestätigt Scope und Risiko-Bild. Entschieden:

- **TDD-Reihenfolge:** Erst `tokens-bridge.test.ts:82` auf `#ffffff` heben → Test wird sofort ROT (app.css hat noch alten Wert). Dann die vier app.css-Werte setzen → GREEN. Nur dieser eine Test sichert einen Surface-Wert (surface-1); für surface-2/raised/rule-soft existiert kein Regressions-Guard.
- **`--g-paper-deep` (#ede9df) bleibt UNANGETASTET** — strikt nach Constraint C1 (nur die sechs Tabellen-Tokens). Delta zu neuem surface-2 (#ecead9) ist < 5 ΔE, im Browser praktisch nicht unterscheidbar → Konsistenz-Mangel, kein Defekt. Gemeinsam sichtbar u. a. in `BottomNav`, `ChannelPreviewCard`, Modal-Sheets, `BrandSidebar`. Falls je gewünscht: separates Folge-Issue, nicht #378.
- **`--g-rule-soft` wird geändert** (`#e7e2d3`), #378 schlägt die alte #369-„behalten"-Notiz. Token wird ausschließlich als `border-color` genutzt (nie als Hintergrund/Durchscheinen) → Wechsel transparent→opak ist visuell ungefährlich. `TOKEN-MAPPING.md` Z. 16 mit-aktualisieren.
- **Shadow (`--g-elev-1`) NICHT in #378 ändern.** `0 1px 3px rgba(26,26,24,0.08)` liegt für weiße Karten auf Off-White an der Wahrnehmungsgrenze, aber eine Erhöhung ist eine PO-pflichtige Design-Entscheidung (C6) und kein Werte-Tausch. → In der Visual-Regression-Prüfung beurteilen; falls Karten „verschwimmen", separater Schritt mit PO-Freigabe (Vorschlag dann: Alpha 0.08 → 0.12).
- **Scope final:** 4 Dateien, ~10–11 LoC. Weit unter Limits (5 Dateien / 250 LoC).

**Visuell zu prüfende Nebeneffekte (in E2E/Screenshot-Phase):** weiße Form-Inputs auf weißen Karten (Border `--g-rule #d8d3c2` muss sichtbar bleiben); Shadcn-Aliase `--color-card`/`--color-sidebar` werden automatisch weiß (gewollt); `RecommendationBanner` `color-mix` mit surface-2 minimal wärmer (`/compare`).

## Korrektur zur User-Anfrage (`#378 → #369 → #368`)

**#369 (Token-Bridge) und #370 (Brand-Bibliothek) sind bereits fertig implementiert und in Produktion** (Alias-Schicht in app.css Z. 146–168, `TOKEN-MAPPING.md`, `frontend/src/lib/brand/`) — nur die GitHub-Issues sind ungeschlossen. Ein Workflow für #369 wäre Doppelarbeit. Tatsächlich offene Folge-Arbeit nach #378: **#371–#374** (Atoms/Molecules/Mobile/Showcase) als Bausteine von Epic #368.

---
entity_id: issue_378_surface_stack
type: module
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [design-system, surface-tokens, foundation, visual-regression, issue-378, epic-368]
---

<!-- Issue #378 — Surface-Stack-Migration: weiße Cards auf warmer Off-White-Page (reiner Werte-Tausch) -->

# Issue #378 — Surface-Stack-Migration (weiße Cards auf warmer Off-White-Page)

## Approval

- [ ] Approved

## Zweck

Der Surface-Token-Stack in `frontend/src/app.css` setzt aktuell Karten auf einen beigen Ton (`--g-surface-1: #edeae1`), der mit der ebenfalls beigen Page-Surface verschmilzt. Das verletzt das PO-Leitprinzip „hoher Kontrast = Lesbarkeit". Dieser Fix tauscht **ausschließlich vier Werte** im Surface-/Rule-Stack auf die Sandbox-Zielwerte (Karten reinweiß `#ffffff` auf warmer Off-White-Page), **ohne Token-Namen zu ändern und ohne neue Tokens**. Begleitend werden ein Regressions-Test und zwei Doku-Dateien synchronisiert. Fundament-Issue: muss vor den offenen Atom-Migrationen #371–#374 landen, damit Atome nicht zweimal angefasst werden.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/app.css` — vier Surface-/Rule-Werte im `:root`-Block tauschen (Z. 63, 64, 70, 140). Namen bleiben unverändert.
- `frontend/src/lib/tokens-bridge.test.ts:82` — Regressions-Assertion `--g-surface-1 == #edeae1` auf `#ffffff` heben (sichert sonst den alten Wert ab → bricht garantiert).
- `docs/design-requests/issue_15_atomic_design/spec/TOKEN-MAPPING.md:16` — `--g-rule-soft`-Eintrag von „unseren behalten" auf „[#378] auf `#e7e2d3` migriert" aktualisieren.
- `docs/design-system/TOKENS.md` — Surface-Stack-Tabelle (`--g-surface-0/1/2/raised`, `--g-rule`, `--g-rule-soft`) ergänzen/aktualisieren, damit Doku und Code deckungsgleich sind.

**Neue Test-Datei:** keine — der bestehende `tokens-bridge.test.ts` deckt die zentrale Assertion ab (TDD-RED via Anpassung Z. 82).

**NICHT ändern:**
- Token-**Namen** (`--g-surface-0/1/2/raised`, `--g-rule`, `--g-rule-soft` bleiben) — Token-Rename ist ein separates Folge-Issue.
- `--g-paper-deep` (`#ede9df`) — nicht in der #378-Tabelle, bleibt per Constraint C1 unangetastet (Δ < 5 ΔE zum neuen surface-2, kein Defekt).
- `--g-elev-*` / Shadow-Tokens — Erhöhung ist PO-pflichtige Design-Entscheidung (C6), kein Werte-Tausch; nur in Visual-Regression beurteilen.
- `.dark`-Block — existiert nicht in app.css; nichts zu tun (C4 trivial erfüllt).
- Svelte-Komponenten — alle Surface-Referenzen laufen bereits über `var(--g-surface-*)`; kein Code-Change nötig (Audit ergab keine Inline-Hex-Verstöße).

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit-Layer: `frontend/src/app.css` + `frontend/src/lib/tokens-bridge.test.ts`) plus Doku (`docs/`). Keine Go-API- und keine Python-Backend-Schicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für Frontend-CSS-Custom-Properties; enthält den Surface-Stack |
| `frontend/src/lib/tokens-bridge.test.ts` | Test (node:test) | Regressions-Guard der #369-Token-Bridge; Z. 82 sichert aktuell den alten surface-1-Wert |
| `docs/design-system/TOKENS.md` | Dokumentation | Token-Referenz; Surface-Tabelle muss mit Code deckungsgleich werden |
| `docs/design-requests/issue_15_atomic_design/spec/TOKEN-MAPPING.md` | Dokumentation | #369-Mapping; rule-soft-„behalten"-Notiz wird durch #378 überholt |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | Konsument | Nutzt `--g-surface-raised` — profitiert automatisch, kein Code-Change |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Konsument | Nutzt `--g-surface-raised` — profitiert automatisch, kein Code-Change |

## Implementation Details

### 1. `frontend/src/app.css` — vier Werte tauschen

```
Z. 63   --g-surface-1:    #edeae1;            →  --g-surface-1:    #ffffff;
Z. 64   --g-surface-2:    #e3dfd4;            →  --g-surface-2:    #ecead9;
Z. 70   --g-surface-raised: var(--g-surface-1); →  --g-surface-raised: #faf8f1;
Z. 140  --g-rule-soft: rgba(26, 26, 24, 0.08); →  --g-rule-soft: #e7e2d3;
```

Bereits korrekt, **nicht anfassen:** `--g-surface-0: #f6f4ee` (Z. 62), `--g-rule: #d8d3c2` (Z. 148).

### 1b. `frontend/src/app.css` — `@property`-Fallback-Werte mitziehen (F002, Adversary-Fund)

Die `@property`-Deklarationen (Issue #218, rgb-Normalisierung) tragen `initial-value`-Fallbacks der Shadcn-Surface-Aliase, die auf `var(--g-surface-1/2)` zeigen. Sie standen noch auf den alten beigen Werten in rgb-Form und werden mitgezogen, sonst greift bei „invalid at computed value time" ein beiger Fallback für eine weiße Karte:

```
Z. 8   --color-card          initial-value: rgb(237, 234, 225) → rgb(255, 255, 255)
Z. 10  --color-muted         initial-value: rgb(227, 223, 212) → rgb(236, 234, 217)
Z. 20  --color-sidebar       initial-value: rgb(237, 234, 225) → rgb(255, 255, 255)
Z. 22  --color-sidebar-accent initial-value: rgb(227, 223, 212) → rgb(236, 234, 217)
```

Reiner Werte-Tausch (kein Name/neues Token), konsistent mit C1.

### 2. `frontend/src/lib/tokens-bridge.test.ts` (Zeile 82)

```
Vorher:  assert.ok(hasDecl('--g-surface-1', '#edeae1'), '--g-surface-1 darf nicht veraendert sein');
Nachher: assert.ok(hasDecl('--g-surface-1', '#ffffff'), '--g-surface-1 ist nach #378 reinweiß (Surface-Stack-Migration)');
```

### 3. `docs/design-requests/issue_15_atomic_design/spec/TOKEN-MAPPING.md` (Zeile 16)

`--g-rule-soft`-Zeile: Aktions-Spalte von „unseren behalten" auf „[#378] migriert → `#e7e2d3`" ändern. Begleitnotiz (Z. 54, Aufzählung von rule-soft/paper-deep/info) ggf. anpassen, sodass rule-soft nicht mehr als „behalten" geführt wird.

### 4. `docs/design-system/TOKENS.md` — Surface-Stack-Tabelle

Eine Tabelle mit den finalen Werten der Code-Namen ergänzen: `--g-surface-0 #f6f4ee`, `--g-surface-1 #ffffff`, `--g-surface-2 #ecead9`, `--g-surface-raised #faf8f1`, `--g-rule #d8d3c2`, `--g-rule-soft #e7e2d3` — jeweils mit Rolle. Bestehende Sandbox-Namen-Tabelle (`--g-card` etc.) bleibt.

## Expected Behavior

- **Input:** keiner zur Laufzeit — statischer CSS-Werte-Tausch.
- **Output:** Karten (`[data-slot="g-card"]`, alle `var(--g-surface-1)`-Flächen) rendern reinweiß; sekundäre Flächen (`--g-surface-2`) und Card-in-Card (`--g-surface-raised`) sind klar abgesetzt; Trennlinien (`--g-rule-soft`) opak warm-beige.
- **Side effects:** Shadcn-Aliase `--color-card`/`--color-sidebar` (→ `var(--g-surface-1)`) werden automatisch weiß (gewollt). `RecommendationBanner` `color-mix` mit surface-2 minimal wärmer (kein Defekt).

## Acceptance Criteria

- **AC-1:** Given `frontend/src/app.css` nach der Migration / When man `--g-surface-1` ausliest / Then ist der Wert exakt `#ffffff` (Karten reinweiß, der Knackpunkt des Issues).
  - Test: (populated after /tdd-red)

- **AC-2:** Given `frontend/src/app.css` nach der Migration / When man `--g-surface-2`, `--g-surface-raised` und `--g-rule-soft` ausliest / Then sind die Werte exakt `#ecead9`, `#faf8f1` und `#e7e2d3` (kein `var(...)`-Verweis mehr bei surface-raised).
  - Test: (populated after /tdd-red)

- **AC-3:** Given der bestehende Regressions-Test `tokens-bridge.test.ts` / When die Frontend-Test-Suite läuft / Then ist sie grün — die Assertion in Z. 82 erwartet `#ffffff`, und alle übrigen Bridge-Assertions (`--g-success`, `--g-wx-thunder`, Radien, Schrift-Aliase, Kollisions-Tokens) bleiben unverändert grün.
  - Test: (populated after /tdd-red)

- **AC-4:** Given die nicht zu migrierenden Tokens / When man `--g-surface-0`, `--g-rule` und `--g-paper-deep` ausliest / Then sind sie unverändert (`#f6f4ee`, `#d8d3c2`, `#ede9df`) — keine ungeplanten Token-Änderungen.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die produktiven Frontend-Quellen (`frontend/src/` ohne `app.css`-Definitionszeilen und ohne die Test-Assertion) / When man nach den alten Hex-Literalen `#edeae1`, `#e3dfd4` grept / Then gibt es keine Treffer in produktivem Komponenten-/Page-Code (Constraint C3).
  - Test: (populated after /tdd-red)

- **AC-6:** Given `docs/design-system/TOKENS.md` und `docs/design-requests/issue_15_atomic_design/spec/TOKEN-MAPPING.md` / When man die Surface-/rule-soft-Einträge prüft / Then sind sie mit den neuen Code-Werten deckungsgleich (TOKENS.md listet die sechs finalen Surface-Werte; TOKEN-MAPPING.md führt rule-soft nicht mehr als „behalten").
  - Test: (populated after /tdd-red)

- **AC-7:** Given die `@property`-Fallback-Werte in `app.css` (F002) / When man `frontend/src/` nach den alten Surface-Werten in rgb-Form (`rgb(237,234,225)`, `rgb(227,223,212)`) durchsucht / Then gibt es außerhalb der Test-Negativ-Assertions keine Treffer, und die `initial-value`-Fallbacks der Surface-Aliase tragen `rgb(255,255,255)` bzw. `rgb(236,234,217)`.
  - Test: `tokens-bridge.test.ts` → `#378 AC-7: keine alten beigen Surface-Fallbacks in @property (rgb-Form, F002)`

## Known Limitations

- **`--g-paper-deep` (#ede9df) bleibt** minimal verschieden vom neuen `--g-surface-2` (#ecead9). Bewusst (C1, < 5 ΔE, nicht unterscheidbar). Etwaige Angleichung ist ein separates Folge-Issue.
- **Shadow-Audit (C6) nicht enthalten:** Falls weiße Karten auf Off-White optisch „verschwimmen", folgt eine PO-freigabepflichtige `--g-elev-1`-Verstärkung (Vorschlag Alpha 0.08 → 0.12) in einem separaten Schritt — nicht in #378.
- **Dark-Mode (C4):** kein `.dark`-Block vorhanden; Dark-Surface-Migration erst, wenn Dark-Mode offiziell wird.

## Changelog

- 2026-05-25: Initial spec created (Issue #378, Surface-Stack-Migration)
- 2026-05-25: Scope-Ergänzung nach Adversary-Verifikation (VERIFIED) — F002: `@property`-`initial-value`-Fallbacks der Surface-Aliase (`--color-card/-muted/-sidebar/-sidebar-accent`) in rgb-Form mitgezogen (AC-7, Implementation Detail 1b). F001: TOKENS.md-Fußnote korrigiert (`--g-surface-2` ≠ `--g-paper-deep`, nur gleicher Wert wie Sandbox-paper-deep).

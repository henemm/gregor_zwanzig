---
entity_id: issue_519_token_konsolidierung
type: module
created: 2026-06-01
updated: 2026-06-01
status: active
version: "1.0"
tags: [frontend, design-tokens, css, app.css, cleanup, consolidation]
---

# Spec: Issue #519 — Token-Konsolidierung — Duale Semantik-Token-Systeme vereinheitlichen

## Approval

- [x] Approved

## Purpose

Bereinigt zwei parallele Token-Namespaces in `frontend/src/app.css`, die seit dem Contrast-Audit #377 als Fehlerquelle bekannt sind: semantische Status-Token (`--g-success/warning/danger` vs. `--g-good/warn/bad`) und Wetter-Token (`--g-weather-*` vs. `--g-wx-*`). Die Alt-Namen werden zu Aliases auf die kanonischen Werte umgebaut, alle Svelte-Dateien die Alt-Namen direkt referenzieren werden auf die kanonischen Token umgestellt, und die shadcn-Bridge (`--color-destructive: var(--g-danger)`) bleibt unberührt.

## Source

- **Files:**
  - `frontend/src/app.css`
  - `frontend/src/lib/tokens-bridge.test.ts`
  - `frontend/src/routes/_design-system/+page.svelte`
  - `docs/design-system/TOKENS.md`
  - ~37 Svelte-Dateien unter `frontend/src/` (mechanisches Find-Replace)
- **Identifier:** CSS-Custom-Properties `--g-success`, `--g-warning`, `--g-danger`, `--g-weather-*`

## Estimated Scope

- **LoC:** ~50 Änderungen (überwiegend Find-Replace)
- **Files:** ~42
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS | Zentrales Token-Sheet; enthält sowohl Alt-Definitionen als auch kanonische Werte |
| `frontend/src/lib/tokens-bridge.test.ts` | Test | Regression-Assert auf Zeile 83 prüft `--g-success` mit hartem Hex-Wert — muss auf Alias-Form umgeschrieben werden |
| `frontend/src/routes/_design-system/+page.svelte` | Svelte-Komponente | Showcase nutzt `--g-weather-*` an 5 Stellen statt kanonischer `--g-wx-*` |
| `docs/design-system/TOKENS.md` | Dokumentation | Wetter-Sektion muss `--g-wx-*` als kanonisch ausweisen |
| shadcn-Bridge in `app.css` | CSS | `--color-destructive: var(--g-danger)` + `@property`-Deklaration bleiben unberührt (C1) |

## Implementation Details

### 1. `tokens-bridge.test.ts:83` — Regression-Assert anpassen

Zeile 83 prüft aktuell `assert.ok(hasDecl('--g-success', '#3a7d44'))`. Da `--g-success` nach der Migration ein Alias (`var(--g-good)`) ist und keinen direkten Hex-Wert mehr hat, muss der Assert auf Alias-Form umgestellt werden:

```ts
// alt
assert.ok(hasDecl('--g-success', '#3a7d44'));

// neu
assert.ok(hasDecl('--g-success', 'var(--g-good)'));
```

### 2. `app.css` — Alias-Umstellung der Alt-Token (Zeilen 73–75)

Die drei Alt-Definitionen werden von eigenständigen Werten auf Aliases der kanonischen Token umgestellt:

```css
/* alt */
--g-success: #3a7d44;
--g-warning: #c8882a;
--g-danger:  #b33a2a;

/* neu */
--g-success: var(--g-good);   /* Alias auf #3d6b3a */
--g-warning: var(--g-warn);   /* Alias auf #c08a1a */
--g-danger:  var(--g-bad);    /* Alias auf #a83232 */
```

Die kanonischen Werte `--g-good: #3d6b3a`, `--g-warn: #c08a1a`, `--g-bad: #a83232` bleiben unverändert (C2, C3).

### 3. `app.css` — Pill/Dot-Slots intern migrieren (Zeilen 370–384, 455–457)

Interne Verwendungen von `var(--g-success)` und `var(--g-warning)` innerhalb von `app.css` selbst (Pill- und Dot-Slot-Definitionen) werden auf die kanonischen Token umgestellt:

```css
/* Überall in app.css */
var(--g-success) → var(--g-good)
var(--g-warning) → var(--g-warn)
```

`var(--g-danger)` bleibt in `app.css` stehen, da die shadcn-Bridge (`--color-destructive: var(--g-danger)`) darauf angewiesen ist (C1).

### 4. ~37 Svelte-Dateien — Find-Replace in Svelte-Quellcode

Mechanisches Find-Replace über alle `*.svelte`- und `*.ts`-Dateien unter `frontend/src/` (ausgenommen `_design-system/+page.svelte`, das separat behandelt wird):

```
var(--g-success) → var(--g-good)
var(--g-warning) → var(--g-warn)
```

`var(--g-danger)` in Svelte-Dateien bleibt erhalten — als Alias auf `--g-bad` ist es korrekt und bricht keine shadcn-Bridge.

Vorgeschlagener Befehl zur Identifikation der betroffenen Dateien:

```bash
grep -rl 'var(--g-success)\|var(--g-warning)' frontend/src/ --include='*.svelte' --include='*.ts'
```

### 5. Neuer Source-Inspection-Test `token-consolidation.test.ts`

Neuer Test-File unter `frontend/src/lib/__tests__/token-consolidation.test.ts` (node:test), der per Datei-Grep sicherstellt, dass kein Svelte-File mehr `var(--g-success)` oder `var(--g-warning)` direkt referenziert. Dieser Test schlägt CI-seitig an, falls eine künftige Änderung Alt-Token wieder einschleppt:

```ts
import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import { test, describe } from 'node:test';
import assert from 'node:assert';

// Rekursiv alle *.svelte-Dateien einsammeln, auf Alt-Token prüfen
```

### 6. `_design-system/+page.svelte` — Wetter-Token migrieren (5 Stellen)

Die 5 Stellen in `frontend/src/routes/_design-system/+page.svelte`, die `var(--g-weather-*)` referenzieren, werden auf `var(--g-wx-*)` umgestellt:

```
var(--g-weather-clear)  → var(--g-wx-clear)
var(--g-weather-cloudy) → var(--g-wx-cloudy)
... (analog für alle 5 Wetter-Token)
```

`--g-weather-*` ist ausschließlich im Design-System-Showcase definiert. Alle produktiven Komponenten nutzen bereits `--g-wx-*`.

### 7. `TOKENS.md` — Wetter-Sektion dokumentieren

In `docs/design-system/TOKENS.md` die Wetter-Token-Sektion aktualisieren: `--g-wx-*` als kanonisch ausweisen, `--g-weather-*` als veralteten Alias markieren (oder entfernen, falls nur Showcase-intern).

## Expected Behavior

- **Input:** SvelteKit-Build mit allen Svelte-Komponenten und `app.css`
- **Output:** Alle Status-Token werden über einen einzigen kanonischen Namespace aufgelöst; `--g-good/warn/bad` sind die maßgeblichen Quellen; `--g-success/warning/danger` sind reine Aliases ohne eigene Farbwerte; Wetter-Token nutzen durchgängig `--g-wx-*`
- **Side effects:** Keine visuellen Änderungen — Alias-Werte und kanonische Werte konvergieren auf dieselben Farben. Die shadcn-Bridge (`--color-destructive`) funktioniert weiterhin über `var(--g-danger)` → `var(--g-bad)`.

## Acceptance Criteria

- **AC-1:** Given app.css ist geladen, When `--g-success`, `--g-warning`, `--g-danger` ausgelesen werden, Then verweisen alle drei auf kanonische Werte: `--g-success` = `var(--g-good)`, `--g-warning` = `var(--g-warn)`, `--g-danger` = `var(--g-bad)`.
  - Test: `frontend/src/lib/issue_519_token_konsolidierung.test.ts`

- **AC-2:** Given alle Svelte-Dateien in `frontend/src/`, When nach `var(--g-success)` oder `var(--g-warning)` gesucht wird, Then gibt es keine Fundstelle in einer `*.svelte`-Datei.
  - Test: `frontend/src/lib/issue_519_token_konsolidierung.test.ts`

- **AC-3:** Given app.css ist geladen, When `--color-destructive` ausgelesen wird, Then ist der Wert `var(--g-danger)` (shadcn-Bridge bleibt erhalten; transitiv: `--g-danger` → `var(--g-bad)` → `#a83232`).
  - Test: `frontend/src/lib/issue_519_token_konsolidierung.test.ts`

- **AC-4:** Given `_design-system/+page.svelte` ist der aktuelle Quellstand, When das Wetter-Token-Array ausgelesen wird, Then nutzen alle 5 Token-Referenzen `var(--g-wx-*)` — keine Referenz auf `var(--g-weather-*)` bleibt übrig.
  - Test: `frontend/src/lib/issue_519_token_konsolidierung.test.ts`

- **AC-5:** Given app.css ist geladen, When `--g-good`, `--g-warn`, `--g-bad` ausgelesen werden, Then sind die Werte exakt `#3d6b3a`, `#c08a1a`, `#a83232` (kanonische Werte unverändert).
  - Test: `frontend/src/lib/issue_519_token_konsolidierung.test.ts`

## Known Limitations

- `--g-danger` bleibt in app.css als vollwertiger Alias erhalten (nicht entfernt) — die shadcn-Bridge `--color-destructive: var(--g-danger)` und die zugehörige `@property`-Deklaration mit `initial-value: rgb(179,58,42)` setzen diesen Namen voraus.
- `--g-weather-*` wird nur im Showcase-Route `_design-system/+page.svelte` genutzt. Sollte der Showcase in einem späteren Issue als eigenständige Route entfernt werden, können die Alias-Definitionen in `app.css` ebenfalls gelöscht werden.
- Der neue Test `token-consolidation.test.ts` prüft nur Svelte-Dateien per Quelltext-Grep. CSS-interne Verwendungen in `app.css` selbst werden nicht durch diesen Test abgedeckt — die Alias-Umstellung in Schritt 3 ist manuell zu verifizieren.

## Changelog

- 2026-06-01: Initial spec created
- 2026-06-01: Implementiert und VERIFIED durch Adversary

<!-- gregor-zwanzig-handoff: stable_id=foundation-css-tokens -->
## Problem

Several components reference CSS variables that **do not exist** in `frontend/src/app.css`, and the inline fallbacks point at generic blue/gray hex codes. Result: large parts of the UI render in the wrong color (system blue `#2563eb`, neutral gray borders) instead of the brand palette (burnt orange `#c45a2a`, ink-based borders).

This single fix flips a huge fraction of the "default-styled" look that the screenshots show — especially in the Alert-Rules editor, ModeCard, and any component that hard-codes `var(--g-primary, ...)` or `var(--g-border, ...)`.

### Root cause

`app.css` defines the token namespace as:

- `--g-accent` (brand accent — burnt orange)
- `--g-ink`, `--g-ink-muted`, `--g-ink-faint` (typography + borders)
- `--g-surface-0/1/2` (surfaces)
- `--g-success`, `--g-warning`, `--g-danger`, `--g-info`

But components reference **legacy names that were never declared**:

| Used in code | Status | Correct token |
|---|---|---|
| `--g-primary` | ❌ undefined | use `--g-accent` (for selected/active state) or `--g-ink` (for primary buttons) |
| `--g-border` | ❌ undefined | `--g-ink-faint` |
| `--color-input` (Tailwind theme alias) | ✅ defined but resolves to `--g-ink-faint` | keep |

Because the CSS-var fallbacks resolve, no error is thrown — the wrong color just silently leaks through.

## Files to fix

Search the repo for the two patterns and replace:

```bash
# from frontend/
rg --files-with-matches "var\(--g-primary" src
rg --files-with-matches "var\(--g-border" src
```

Known affected files (non-exhaustive — finish with the ripgrep results above):

- `src/lib/components/alert-rules-editor/AlertRuleRow.svelte` (lines ~135–199 — `.field`, `.btn-primary`, `.btn-secondary`)
- `src/lib/components/alert-rules-editor/ModeCard.svelte` (lines ~70–94 — `.mode-card`, `.mode-card.selected`)
- Any other component that imports raw CSS with these vars

## Required changes

### 1. Replace fallback hex codes with real token names

For `--g-border`:
```diff
- border: 1px solid var(--g-border, #e5e7eb);
+ border: 1px solid var(--g-ink-faint);
```

For `--g-primary` — **the semantic differs by context**:
- **Selected / active state** (e.g. `ModeCard.selected`, focus ring): use `--g-accent`
- **Primary action button background**: use `--g-ink` (the design uses ink-on-paper for primary CTAs; accent is reserved for "New Trip"-style brand moments)

Example (ModeCard.selected):
```diff
.mode-card.selected {
-   border-color: var(--g-primary, #2563eb);
-   box-shadow: 0 0 0 1px var(--g-primary, #2563eb) inset;
+   border-color: var(--g-accent);
+   box-shadow: 0 0 0 1px var(--g-accent) inset;
+   background: color-mix(in oklab, var(--g-accent) 6%, var(--g-surface-1));
}
```

Example (AlertRuleRow `.btn-primary`):
```diff
.btn-primary {
-   background: var(--g-primary, #2563eb);
-   color: #fff;
-   border-color: var(--g-primary, #2563eb);
+   background: var(--g-ink);
+   color: var(--g-paper);
+   border-color: var(--g-ink);
}
```

### 2. Remove the hex fallbacks entirely

After the rename, drop the second argument to `var()` — fallbacks hide future bugs. The tokens are defined globally in `app.css`, so they will always resolve.

```diff
- color: var(--g-ink-muted, #6b7280);
+ color: var(--g-ink-muted);
```

### 3. Add a lint rule (optional but recommended)

Add an ESLint or stylelint rule that flags `var(--g-` calls with a second arg as warnings. Prevents regression.

## Acceptance criteria

- [ ] `rg "var\(--g-primary" src` returns **zero matches** in `.svelte`, `.css`, `.ts`.
- [ ] `rg "var\(--g-border" src` returns **zero matches**.
- [ ] `rg "#2563eb|#e5e7eb|#6b7280|#f3f4f6" src` returns zero matches in component CSS (these were the most common fallbacks).
- [ ] **Visual:** In the AlertRulesEditor screen (Trip edit → Alarmregeln tab), the "Speichern" button is **black/ink** (not blue), and the **selected ModeCard outline is burnt-orange** (not blue). See `Vorher` screenshot below.
- [ ] No new TypeScript or build errors.
- [ ] Existing component tests still pass.

## 📎 Attachments (drag into the issue)

- `uploads/CleanShot 2026-05-20 at 15.08.42@2x.png` — current Alarmregeln edit form showing the blue "Speichern" button + blue ModeCard ring
- `uploads/CleanShot 2026-05-20 at 15.09.38@2x.png` — current Alarmregeln list with blue checkbox + brown "warning" pill (the pill is correct, the checkbox is the bug)
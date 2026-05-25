---
entity_id: issue_376_channel_preview_select_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, frontend, svelte5, select, design-system, issue-376, issue-278, issue-272]
parent: issue_376_channel_preview_select
phase: phase5_tdd_red
---

# Issue #376 — ChannelPreviewBlock auf Select.svelte migrieren: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_376_channel_preview_select.md`.
Da Issue #376 rein Frontend ist (eine Svelte-Komponente, kein Python-Code), prüfen
die Tests Inhalts-Invarianten der Svelte-Datei: Wegfall des nativen `<select>`,
Import + Verwendung von `Select.svelte`, Erhalt des `data-testid` und des
#272-iOS-Zoom-Guards sowie die app-weite #278-Regel (`rg '<select\b'`).

Parent-Spec: `docs/specs/modules/issue_376_channel_preview_select.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_376_channel_preview_select.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_376_channel_preview_select.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_no_native_select_in_channel_preview_block` | AC-1 | ChannelPreviewBlock.svelte enthält kein natives `<select>` mehr |
| `test_ac1_imports_select_component` | AC-1 | ChannelPreviewBlock importiert `Select` aus `$lib/components/ui/select` |
| `test_ac3_testid_on_select_component` | AC-3 | `data-testid="channel-preview-mobile-select"` steht auf dem `<Select>`-Tag |
| `test_ac4_scoped_ios_zoom_guard_present` | AC-4 | Scoped Override `.ch-select :global(.gz-select select)` setzt `font-size: 16px` |
| `test_ac5_no_native_selects_outside_component` | AC-5 | `rg '<select\b'` über `frontend/src` findet Treffer NUR in `Select.svelte` |

> AC-2 (Laufzeit-`bind:value`-Verhalten / Kanalwechsel) ist nicht statisch prüfbar
> und wird in der E2E-/Visual-Verifikation (Phase 7, Playwright) abgedeckt.

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_ac1_no_native_select_in_channel_preview_block` | FAIL | Datei enthält noch das native `<select>` (Z. 75) |
| `test_ac1_imports_select_component` | FAIL | Kein Import von Select vorhanden |
| `test_ac3_testid_on_select_component` | FAIL | `data-testid` sitzt auf nativem `<select>`, kein `<Select>`-Tag vorhanden |
| `test_ac4_scoped_ios_zoom_guard_present` | FAIL | Kein `:global(.gz-select select)`-Override im `<style>`-Block |
| `test_ac5_no_native_selects_outside_component` | FAIL | ChannelPreviewBlock ist noch in der Liste nativer Selects |

Alle 5 Tests müssen im RED-Zustand FAIL sein — das ist der RED-Beweis.

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_376_channel_preview_select.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_376_channel_preview_select.py -v
```

## Changelog

- 2026-05-25: Initial test manifest erstellt für Issue #376 (Select-Migration ChannelPreviewBlock).

---
entity_id: bug_305_mobile_email_v2
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: implemented
version: "1.0"
tags: [bugfix, email, mobile, dual-mode, responsive, ios-mail, issue-305]
---

# Issue #305 v2 — Echter Fix: HTML-E-Mail Mobile-Kompakt-Layout

## Approval

- [x] Approved

## Zweck

Erster Fix (Commit `e3978df`): `<thead>`/`<tbody>` + Breakpoint 600px. Unvollständig — CSS `display:block` auf `td` verwandelt jede Tabellenzelle in eine gelabelte Zeile: bei 15 Metriken × 6h entstehen 90+ gestapelte Zeilen pro Segment.

**Echter Root Cause:** Kein separater Mobile-Inhalt. Die Desktop-Tabelle wird via CSS in ein Card-per-Row-Layout umgewandelt — für multi-column Wetter-Tabellen grundsätzlich unbrauchbar.

**Lösung:** Dual-Mode-Rendering analog zu `compare_html.py`.

## Quelle / Source

**Geänderte Datei:** `src/output/renderers/email/html.py`

**Ebenfalls angepasst (Regression-Fix):**
- `tests/tdd/test_issue_257_trip_briefing_polish.py::test_ac5_mobile_table_resp_rule` — kodierte das alte Card-per-Row-CSS, das Bug #305 v2 absichtlich ersetzt

## Implementation

1. **Neue Funktion `_render_mobile_compact_rows()`** — eine Zeile pro Stunden-Slot: `08:00  15.0 · 12 · 0.2 · ⚡ mögl.`
2. **Segment-Schleife** — jedes Segment erzeugt `<div class="section desktop-only">` + `<div class="mobile-compact" style="display:none">`
3. **Night-Block** — identisches Dual-Mode-Muster
4. **CSS:** `.desktop-only { display: block; }` / `.mobile-compact { display: none; }` als Basis; `@media (max-width:600px)` schaltet um mit `display: none/block !important`

## Acceptance Criteria

- **AC-7:** Given render_html() / When HTML geprüft / Then enthält es `desktop-only` mit `<table>`
  - Test: `TestMobileCompactLayout::test_desktop_only_wrapper_exists`

- **AC-8:** Given render_html() / When HTML geprüft / Then enthält es `mobile-compact`
  - Test: `TestMobileCompactLayout::test_mobile_compact_wrapper_exists`

- **AC-9:** Given render_html() / When @media-Block geprüft / Then `.desktop-only { display: none }` im @media
  - Test: `TestMobileCompactLayout::test_css_hides_desktop_on_mobile`

- **AC-10:** Given render_html() / When @media-Block geprüft / Then `.mobile-compact { display: block }` im @media
  - Test: `TestMobileCompactLayout::test_css_shows_compact_on_mobile`

- **AC-11:** Given 375px Viewport / When Sichtbarkeit `.desktop-only` / Then `offsetHeight == 0`
  - Test: `TestMobileCompactLayoutPlaywright::test_desktop_only_hidden_at_375px`

- **AC-12:** Given 375px Viewport / When Sichtbarkeit `.mobile-compact` / Then `offsetHeight > 0`
  - Test: `TestMobileCompactLayoutPlaywright::test_mobile_compact_visible_at_375px`

- **AC-13:** Given 375px Viewport / When scrollWidth vs clientWidth / Then kein Overflow
  - Test: `TestMobileCompactLayoutPlaywright::test_mobile_compact_no_overflow_at_375px`

## Changelog

- 2026-05-22: Echter Fix implementiert. Dual-Mode: `div.desktop-only` / `div.mobile-compact` mit CSS-Switch bei 600px. Adversary-Finding F001 (Regression in test_issue_257) behoben durch Test-Update.

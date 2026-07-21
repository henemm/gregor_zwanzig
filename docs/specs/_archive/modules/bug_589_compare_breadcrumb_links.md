---
entity_id: bug_589_compare_breadcrumb_links
type: bugfix
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [frontend, compare, navigation, breadcrumb]
---

# Bug #589 — Compare-Detail Breadcrumb Links

## Approval

- [ ] Approved

## Purpose

Der Breadcrumb auf der Compare-Detail-Seite (`/compare/[id]`) zeigt "WORKSPACE · ORTS-VERGLEICHE / DETAIL" als statischen Text. Keines der Elemente ist anklickbar. "ORTS-VERGLEICHE" muss auf `/compare` verlinken, "WORKSPACE" auf `/`.

## Source

- **File:** `frontend/src/routes/compare/[id]/+page.svelte`
- **Identifier:** `<Eyebrow>WORKSPACE · ORTS-VERGLEICHE / DETAIL</Eyebrow>` (Zeile 56)

## Estimated Scope

- **LoC:** ~10
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Eyebrow` | atom | Wrapper für die Breadcrumb-Zeile |

## Implementation Details

Ersetze die statische `<Eyebrow>`-Zeile durch eine strukturierte Breadcrumb mit `<a>`-Links:

```svelte
<!-- Vorher (kaputt) -->
<Eyebrow>WORKSPACE · ORTS-VERGLEICHE / DETAIL</Eyebrow>

<!-- Nachher (korrekt) -->
<nav aria-label="Breadcrumb">
  <Eyebrow>
    <a href="/" class="breadcrumb-link">WORKSPACE</a>
    <span aria-hidden="true"> · </span>
    <a href="/compare" class="breadcrumb-link">ORTS-VERGLEICHE</a>
    <span aria-hidden="true"> / </span>
    <span>DETAIL</span>
  </Eyebrow>
</nav>
```

CSS (scoped, im `<style>`-Block der Seite):
```css
.breadcrumb-link {
  color: inherit;
  text-decoration: none;
}
.breadcrumb-link:hover {
  text-decoration: underline;
}
```

## Acceptance Criteria

**AC-1:** Given ich bin auf der Compare-Detail-Seite `/compare/[id]` / When ich auf "ORTS-VERGLEICHE" im Breadcrumb klicke / Then navigiert der Browser zu `/compare` (Orts-Vergleich-Übersicht).

**AC-2:** Given ich bin auf der Compare-Detail-Seite `/compare/[id]` / When ich auf "WORKSPACE" im Breadcrumb klicke / Then navigiert der Browser zu `/` (Startseite/Workspace).

**AC-3:** Given ich bin auf der Compare-Detail-Seite `/compare/[id]` / When ich den Breadcrumb anschaue / Then zeigt "DETAIL" keinen Hover-Underline und ist kein Link (ist die aktuelle Seite).

**AC-4:** Given ich bin auf der Compare-Detail-Seite `/compare/[id]` / When ich mit der Maus über "ORTS-VERGLEICHE" oder "WORKSPACE" fahre / Then erscheint ein Underline (hover-Feedback).

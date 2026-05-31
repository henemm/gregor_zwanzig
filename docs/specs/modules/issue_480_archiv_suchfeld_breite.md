---
entity_id: issue_480_archiv_suchfeld_breite
type: module
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [frontend, archiv, layout, bug]
---

# Archiv — Suchfeld volle Breite (Issue #480)

## Approval

- [ ] Approved

## Purpose

Das Suchfeld im Archiv-Screen ist auf eine feste Breite von 380px fixiert (~40% des Content-Bereichs). Es soll die gesamte verfügbare Breite innerhalb der Toolbar einnehmen, damit die Suchfläche maximal genutzt wird.

## Source

- **File:** `frontend/src/routes/archiv/+page.svelte`
- **Identifier:** Toolbar-Div, Such-Wrapper (Zeile 92–101)

## Estimated Scope

- **LoC:** 1
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Segmented` atom | UI-Abhängig | Sortier-Tabs rechts des Suchfelds — behalten natürlichen Platz, kein Einfluss |

## Implementation Details

```diff
- <div style="position:relative;flex:0 0 380px">
+ <div style="position:relative;flex:1">
```

`flex:1` ist Kurzform für `flex:1 1 0%` — das Suchfeld wächst auf den verfügbaren Rest, nachdem die Segmented-Sortier-Kontrolle ihren natürlichen Platz beansprucht hat. Der `gap:16px` zwischen den beiden Elementen bleibt erhalten.

## Expected Behavior

- **Input:** Browser rendert `/archiv`
- **Output:** Suchfeld-Wrapper nimmt den gesamten verbleibenden horizontalen Raum der Toolbar ein
- **Side effects:** Keine — `Segmented`-Sortierung rechts bleibt unverändert, `input width:100%` innerhalb des Wrappers wirkt bereits korrekt

## Acceptance Criteria

- **AC-1:** Given der Archiv-Screen ist geöffnet / When die Toolbar gerendert wird / Then erstreckt sich das Suchfeld über die volle verfügbare Breite (mind. 60% des Content-Bereichs bei Standard-Desktop-Breite)

- **AC-2:** Given das Suchfeld ist voll breit / When der User Text eintippt / Then funktioniert die Live-Filterung der Archiv-Tabelle unverändert korrekt

## Known Limitations

- Die JSX-Design-Vorlage (`screen-archive.jsx`) hat ebenfalls `flex: "0 0 380px"` — dieser Wert ist laut Audit-Finding M-08 ein Fehler in der Vorlage und wird durch diese Spec übersteuert.

## Changelog

- 2026-05-31: Initial spec created (Audit-Finding M-08, Issue #480)

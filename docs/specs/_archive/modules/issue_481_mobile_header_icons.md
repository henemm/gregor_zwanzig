---
entity_id: issue_481_mobile_header_icons
type: bugfix
created: 2026-05-31
updated: 2026-05-31
completed: 2026-05-31
status: complete
version: "1.0"
tags: [bugfix, mobile, header, icons, svelte, frontend, issue-481]
---

<!-- Issue #481 — Bug: Mobile Header zeigt Dark-Mode-Toggle statt Glocke + Plus -->

# Issue #481 — Bug-Fix: Mobile Header rechte Icons (Glocke + Plus)

## Approval

- [x] Approved — Implementation 2026-05-31 LIVE

## Purpose

Der mobile Header (`TopAppBar.svelte`) zeigt rechts einen Dark-Mode-Toggle (MoonIcon/SunIcon), obwohl laut Design-Handoff (Finding M-09) dort eine deaktivierte Glocke als Benachrichtigungs-Placeholder und ein Plus-Button für „Neuer Trip" stehen sollen. Der Fix ersetzt den Dark-Mode-Toggle durch die laut Spezifikation vorgesehenen beiden Icons und schafft damit Konformität mit dem SOLL-Zustand aus der Atomic-Design-Analyse.

## Source

- **File:** `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte`
- **Identifier:** `TopAppBar`

> **Schicht-Hinweis:** Ausschließlich Frontend-Layer (`frontend/src/`). Keine Go-API-, keine Python-Backend-Änderung.

## Estimated Scope

- **LoC:** ~12 netto
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/mobile/MIcon.svelte` | Svelte-Komponente | Liefert `bell`- und `plus`-Icons; bereits vorhanden und in Nutzung |
| `frontend/src/routes/+layout.svelte` | Svelte-Komponente | Übergibt `darkMode`/`ontoggleDark` Props an TopAppBar; bleibt unverändert — Props im Interface bleiben optional erhalten |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Svelte-Komponente | Hat eigenen Dark-Mode-Toggle für Desktop/Drawer; bleibt unverändert |
| `@lucide/svelte` (MoonIcon, SunIcon) | NPM-Dependency | Imports werden aus TopAppBar.svelte entfernt; Paket selbst bleibt im Projekt |

## Implementation Details

In `TopAppBar.svelte` werden folgende Änderungen vorgenommen:

1. **Imports entfernen:** `MoonIcon` und `SunIcon` aus `@lucide/svelte` werden aus dem `<script>`-Block entfernt.

2. **Props beibehalten:** `export let darkMode = false` und `export let ontoggleDark = () => {}` bleiben im Interface (vermeidet Prop-Warnings in `+layout.svelte`, das sie weiterhin übergibt). Sie werden aber nicht mehr gerendert.

3. **Rechten Slot ersetzen:** Der bestehende `<button>` mit MoonIcon/SunIcon-Bedingungslogik wird durch zwei neue Elemente ersetzt:

```svelte
<!-- Glocke: Placeholder, kein Benachrichtigungssystem vorhanden -->
<button
  disabled
  aria-label="Benachrichtigungen"
  data-testid="top-app-bar-bell"
  class="top-app-bar-action top-app-bar-action--disabled"
>
  <MIcon kind="bell" />
</button>

<!-- Plus: navigiert zu /trips/new -->
<a
  href="/trips/new"
  aria-label="Neuer Trip"
  data-testid="top-app-bar-new-trip"
  class="top-app-bar-action"
>
  <MIcon kind="plus" />
</a>
```

4. **Alter testid entfernen:** `data-testid="top-app-bar-toggle-dark"` entfällt; kein Test referenziert ihn.

5. **CSS:** `top-app-bar-action--disabled` setzt `opacity: 0.4; cursor: default` um den Placeholder-Status visuell anzuzeigen.

### LoC-Budget

| Datei | Δ LoC |
|-------|--------|
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | ~+8 / -6 = ~+2 netto |
| **Gesamt** | **~12 Änderungszeilen (weit unter 250 LoC-Limit)** |

## Expected Behavior

- **Input:** Mobiler Viewport (TopAppBar sichtbar); Nutzer öffnet die App oder navigiert
- **Output:**
  - Rechts im Header: Glocken-Icon (deaktiviert, opacity gedimmt) und Plus-Icon nebeneinander
  - Klick auf Plus navigiert zu `/trips/new`
  - Klick auf Glocke hat keine Wirkung (button disabled)
  - Hamburger links und Wordmark Mitte bleiben unverändert
  - Dark-Mode-Toggle ist nicht mehr im mobilen Header sichtbar
- **Side effects:** Dark-Mode-Funktionalität auf Desktop/Drawer (Sidebar.svelte) bleibt vollständig erhalten; Props-Interface von TopAppBar bleibt kompatibel mit +layout.svelte

## Acceptance Criteria

- **AC-1:** Given die App ist auf mobilem Viewport geöffnet / When der Header sichtbar ist / Then zeigt `[data-testid="top-app-bar-bell"]` ein Glocken-Icon das den Zustand `disabled` hat und nicht klickbar ist
  - Test: (populated after /tdd-red)

- **AC-2:** Given die App ist auf mobilem Viewport geöffnet / When der Header sichtbar ist / Then zeigt `[data-testid="top-app-bar-new-trip"]` ein Plus-Icon als Link mit `href="/trips/new"`
  - Test: (populated after /tdd-red)

- **AC-3:** Given der Nutzer ist auf einer beliebigen Seite / When er auf `[data-testid="top-app-bar-new-trip"]` tippt / Then wird er zu `/trips/new` navigiert
  - Test: (populated after /tdd-red)

- **AC-4:** Given `TopAppBar` erhält `darkMode={true}` und `ontoggleDark` als Props / When die Komponente gerendert wird / Then wirft sie keine Prop-Warnings und rendert trotzdem kein MoonIcon/SunIcon
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Desktop-Viewport / When Sidebar.svelte sichtbar ist / Then bleibt der Dark-Mode-Toggle in der Sidebar unverändert funktionsfähig
  - Test: (populated after /tdd-red)

## Known Limitations

- Die Glocke ist ein reiner Placeholder ohne Benachrichtigungs-Backend. Sobald ein Benachrichtigungssystem eingeführt wird, muss `disabled` entfernt und ein Handler ergänzt werden.
- `MIcon` unterstützt `kind="bell"` und `kind="plus"` — vor Implementierung sicherstellen dass beide Werte in der Kind-Union definiert sind.

## Changelog

- 2026-05-31: Initial spec created

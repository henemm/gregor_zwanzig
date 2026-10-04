---
entity_id: mobile_tab_leisten_mtabbar
type: feature
created: 2026-09-23
updated: 2026-10-03
status: implemented
version: "1.0"
tags: [mobile, usability, frontend, tabs, a11y, atomic-design]
---

<!-- Mobile-Usability-Audit (WebKit iPhone 13, 390×844): Fix-Paket 2.
     Verbindlicher Soll: docs/design-requests/mobile_usability_tab_leisten_soll.md
     (Empfehlung Option (a), vom PO nicht beanstandet).
     Mockup: docs/design-requests/mobile-usability-tabs-soll.html
     Audit-Belege: frontend/test-results/mobile-usability/report-iphone13.json
     — trip-detail-tab-list: 874px Scrollbreite bei 356px Sicht;
     compare-detail-tab-list: 654px bei 358px Sicht; aktiver Tab bei
     Deep-Link nicht sichtbar; CompareTabs.svelte ist eine Hand-Kopie des
     TripTabs-Mobil-Musters (AP-006-Drift). -->

# Mobile Usability Paket 2 — Tab-Leisten: aktiver Tab sichtbar + A11y + geteilter MTabBar-Baustein

## Approval

- [x] Approved (PO „approved", 2026-09-25)

## Purpose

Beide Detail-Tab-Leisten (Trip: 7 Tabs, Compare: 6 Tabs) sind auf Mobile
horizontal scrollbar und positionieren den aktiven Tab bei Deep-Links
(`?tab=alarme`, `?tab=vorschau`) außerhalb des sichtbaren Band-Ausschnitts —
ohne jede User-Geste ist der aktive Kontext unsichtbar. Beide Leisten sind
zudem für Screenreader und Tastatur schlecht erschlossen (keine
Tabs-Semantik, keine Pfeiltasten-Bedienung) und unter dem 44px-Touch-Minimum
(Trigger ≈ 31px hoch). Technisch pflegt `CompareTabs.svelte` eine Hand-Kopie
des Mobil-CSS aus `TripTabs.svelte` (AP-006-Drift: zwei Dateien, zwei
Wahrheiten). Die Spec zieht beide Leisten auf **einen** Katalog-Baustein
`MTabBar` (Band + Fade + scrollIntoView + WAI-ARIA-Tabs + 44px-Trigger) —
Desktop-Optiken (Underline Trip / Button-Row Compare) bleiben Varianten und
unverändert.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
  (Mobil-`:global()`-Band-CSS wandert in den Baustein; rendert `<MTabBar>`)
- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
  (`compare-tabs-bar`-Hand-Markup + kopiertes Mobil-CSS ersetzt durch
  denselben `<MTabBar>`-Import)
- **File:** `frontend/src/lib/components/mobile/MTabBar.svelte` (NEU,
  Katalog-Komponente; Kern auf Basis des `<Segmented>`-Atoms)
- **File:** `frontend/src/lib/components/atoms/Segmented.svelte`
  (ggf. optionale `minHeight`/A11y-Ergänzungen)
- **File:** `docs/design-system/COMPONENTS.md` (`<MTab>`-Eintrag §7 konkretisieren)

> **Schicht-Hinweis:** reine Frontend-/User-UI-Änderung (`frontend/src/...`,
> SvelteKit). Kein Go-API-, kein Python-Core-Anteil.

## Affected Files

| Datei | Änderung | Iteration |
|---|---|---|
| `frontend/src/lib/components/mobile/MTabBar.svelte` | NEU: geteilter scrollbarer Tab-Baustein — Band + 16px-Fade + Scroll-Snap, `scrollIntoView({inline:'start'})` beim Mount/Wechsel, `role=tablist/tab`, `aria-selected`, roving `tabindex`, ←/→-Tastatur, Trigger `min-height:44px`, Fokus-Ring | 1 |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Mobil-Overrides aus der Komponenten-`:global()`-CSS entfernen; `<Segmented>`-Markup durch `<MTabBar>` (Variante `underline` für Desktop) ersetzen; URL-Sync/Flush-Logik unverändert | 1 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | `compare-tabs-bar`-Hand-Markup + kopiertes Mobil-CSS ersetzt durch `<MTabBar>` (Variante `buttons` für Desktop); Orte-Badge weiter gereicht | 2 |
| `frontend/src/lib/components/atoms/Segmented.svelte` | Optional: A11y-/minHeight-Props, falls der Kern dort statt in MTabBar landet | 1 |
| `docs/design-system/COMPONENTS.md` | `<MTab>` §7 um `MTabBar` (Props, Verhalten) konkretisieren | 1 |

## Estimated Scope

- **LoC:** Iteration 1 ~180 (Baustein + TripTabs) · Iteration 2 ~100
  (CompareTabs + Badge-Parität)
- **Files:** 4–5
- **Effort:** medium

> **Scope-Guard:** `max_loc_delta: 250` pro Iteration. Die CompareTabs-
> Umstellung ist bewusst Iteration 2: Sie hat eigene Test-IDs
> (`compare-detail-tab-*`) und eine Badge-Sonderlocke (Orte-Zähler), die
> eigenen Adversary-Runden verdient.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `<Segmented>` (`frontend/src/lib/components/atoms/Segmented.svelte`) | component | Basis-Atom (Options/selected/onselect, `data-slot`-Test-IDs) — MTabBar kapselt es, baut es nicht nach |
| `compareTabsResolve.ts` (`COMPARE_TABS`) | constant | Compare-Tab-Definition + Deep-Link-Resolve — unverändert, wird nur an MTabBar durchgereicht |
| `mobile_usability_tabs_soll.html` | mockup | Verbindliche Optik (Band, Fade, Pill, Badge-Stil) |
| `mobile_stages_tab_listen_only` (Spec) | spec | Gleicher Screen, unabhängiger Change — koordinieren, nicht mischen |

## Implementation Details

```
[MTabBar.svelte, Kern]
props: items: Array<{value, label, badge?}>, active, onChange, variant: "underline" | "pills"
- Desktop (>=900px): unveränderte Optik je Variante (Trip: Underline;
  Compare: Button-Row) — kein Scroll-Band.
- Mobile (<900px, Baustein-intern per Media-Query oder Container):
  overflow-x:auto, scrollbar-width:none, scroll-snap-type:x proximity,
  scroll-padding-inline:12px, Fade-Maske 16px (#1231, unverändert)
  Trigger: min-height:44px, padding var(--g-s-2) var(--g-s-3), Pill-Radius
- Positionierung: $effect auf `active` ->
  activeItem.scrollIntoView({ inline:"start", block:"nearest" })
  (beim Mount + bei jedem Wechsel; smooth beim User-Wechsel)
- A11y: role="tablist" / role="tab", aria-selected, roving tabindex
  (aktiv 0, Rest -1), keydown <- / -> aktiviert Nachbarn + Fokus
- Fokus-Ring: --g-accent, 2px, offset 2px

[Badge-Stil (Vorschlag aus Design-Doc, offener Punkt #585)]
inaktiv: --g-paper-deep / --g-ink-3, mono --g-text-xs; aktiv: transluzent auf Accent-Pill
```

- **TripTabs:** behält TABS-Definition, Badges, `handleValueChange` (Flush-Guard,
  `?tab=`-replaceState) vollständig — es wechselt nur das Render-Target der Leiste.
  Test-IDs `trip-detail-tab-*` bleiben (Segmented-`data-slot`-Vertrag).
- **CompareTabs:** `compare-tabs-bar`-Div + Inline-Styles + kopiertes
  `@media (max-width: 899px)`-CSS entfallen; Orte-Badge (Zähler) wird als
  `badge` im Item übergeben. Desktop-Button-Optik = Variante, kein Fork.
- **Keine neuen Tokens** (alles aus `--g-s-*`, `--g-text-*`, `--g-r-pill`,
  Accent/Surface-Bestand).

## Expected Behavior

- **Input:** Tab-Liste (2–7 Items mit optionalen Badges), aktiver Wert
  (inkl. Deep-Link), Viewport-Mobile/Desktop.
- **Output:** Scrollbares Band (nur mobil); aktiver Tab immer vollständig
  sichtbar; Tastatur-/Screenreader-Bedienung.
- **Side effects:** `onChange` pro Tab (URL-Sync bleibt bei den Konsumenten);
  Scroll-Position des Bands beim Wechsel.

## Acceptance Criteria

- **AC-1:** Given ein Deep-Link `?tab=alarme` (Trip) bzw. `?tab=vorschau`
  (Compare) auf 390px / When die Seite geladen wird (keine User-Geste) /
  Then ist der aktive Tab vollständig im sichtbaren Band-Ausschnitt, mit
  12px Abstand zum linken Band-Rand (`scroll-padding-inline`).
  - Test: Playwright Mobil-Viewport — BoundingBox des aktiven Tabs liegt
    innerhalb des sichtbaren Bereichs; Screenshot vor/nach Laden identisch
    (kein Scroll-Eingriff nötig).

- **AC-2:** Given das Band / When der Nutzer einen anderen Tab tippt (oder
  ←/→ drückt) / Then wird der neue Tab aktiv und an den Anfang des sichtbaren
  Bereichs positioniert.
  - Test: Playwright — Tap auf letzten sichtbaren Tab + Pfeiltasten-Pfad;
    aktiver Tab-Trigger-Box.left ≈ Band-Padding (12px).

- **AC-3:** Given Screenreader oder Tastatur / When die Leiste fokussiert
  wird / Then meldet sie sich als `tablist` mit `tab`-Kindern, `aria-selected`
  nur am aktiven Tab, roving `tabindex`, ←/→ wechselt und fokussiert.
  - Test: Playwright/axe — Rollen/Attribute vorhanden; Tastaturdurchlauf
    über alle Tabs ohne Maus; sichtbarer Fokus-Ring.

- **AC-4:** Given das Band auf 390px / When ein Trigger gemessen wird / Then
  ist er mindestens 44px hoch.
  - Test: Playwright — BoundingBox.height ≥ 44 für jeden Trigger.

- **AC-5:** Given Compare-Detail und Trip-Detail nebeneinander auf Mobile /
  When beide Bänder gerendert werden / Then stammen beide aus demselben
  Baustein: identisches Band-/Fade-/Scroll-Verhalten, kein divergierendes
  Mobil-CSS in den Konsumenten (AP-006).
  - Test: Playwright — beide `data-testid`s (`trip-detail-tab-list`,
    `compare-detail-tab-list`) enthalten denselben Baustein-Selektor; Quell-
    check: kein `overflow-x`-/Fade-CSS mehr in `CompareTabs.svelte`/
    `TripTabs.svelte` (nur im Baustein).

- **AC-6:** Given Desktop-Viewport (≥ 900px) / When beide Seiten gerendert
  werden / Then ist die Optik unverändert: Trip = Underline-Leiste mit
  Accent-Unterstrich, Compare = Button-Row; keine Scrollbände.
  - Test: Playwright Desktop-Viewport — Screenshot-Diff gegen Baseline ohne
    Abweichung in der Leiste; kein `overflow-x` aktiv.

- **AC-7:** Given das Band mit mehr Tabs als sichtbar / When der Nutzer
  tippt oder wischt / Then signalisiert die 16px-Fade-Maske weiterhin
  weitere Tabs; der aktive Tab ist nach jedem Wechsel ohne Wischen sichtbar.
  - Test: Playwright — `mask-image` computed vorhanden; nach Wechsel auf
    Tab 1 von Tab 7 steht Tab 1 sichtbar am Anfang.

## Known Limitations

- Tab-Anzahl/Reihenfolge ändern wir nicht (7 bzw. 6 Tabs passen nie ohne
  Scroll auf 356px) — Wrap („Mehr") wurde im Design-Doc verworfen.
- Badge-Stil (neutral statt Accent-Fill) ist Vorschlag mit offenem #585-Punkt;
  im Baustein als isolierte Variante umsetzbar.
- Safari-WebKit-Quirk: `scrollIntoView` mit `scroll-padding` kann 1px
    abweichen — Toleranz im Test auf ±2px.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (AP-006-Anwendung auf bestehenden Katalog, keine neue
  Architektur-Ebene)
- **Rationale:** **AP-006 (kein Drift katalogisierter Komponenten):**
  `CompareTabs.svelte` pflegt heute eine Hand-Kopie des TripTabs-Mobil-Musters
  (Kommentar `CompareTabs.svelte` selbst nennt „Muster 1:1 TripTabs.svelte").
  Zwei Kopien des gleichen Verhaltens sind die identifizierte Drift-Quelle —
  jede Band-Verbesserung (wie diese) müsste sonst doppelt landen. Der
  geteilte `MTabBar`-Kern (Scroll-Band, Fade, Positionierung, A11y) wird
  einmal gebaut und von beiden Konsumenten mit Varianten-Prop (`underline` /
  `buttons`) genutzt; Desktop-Optiken bleiben berührt. Option (a) des
  Design-Docs (Band bleibt + aktiver Tab sichtbar + A11y) gegenüber Wrap und
  „Mehr"-Dropdown — Begründung und Verwerfungs-Gründe:
  `docs/design-requests/mobile_usability_tab_leisten_soll.md` §2/§3.

## Changelog

- 2026-10-03: Umsetzung abgeschlossen und validiert. Iteration 1 (5a94e9fc):
  MTabBar-Baustein + Katalog v1.5 (Band + Fade, scrollIntoView Mount/Wechsel,
  WAI-ARIA roving tabindex, 44px-Trigger, Badges neutral), TripTabs umgestellt,
  lokales Tab-CSS entfernt. Iteration 2 (0c9405d4): CompareTabs auf
  <MTabBar size="sm"> (AP-006-Drift-Behebung), Orte-Badge-Parität, Desktop-Optik
  1:1; neue E2E-Spec compare-tab-bar.spec.ts (5/5), stale Contract-Tests
  (#582 AC-5b, shared_hub overflow-x) auf neue Architektur gezogen, Unit
  3134/0, Bestandssuites 16 passed. Funde: Tarif-Quota max. 2 aktive
  Vergleiche (Spec räumt E2E-GZ-Altbestand bei 409 auf); Panel-Segmented
  rendert ebenfalls role=tab (Tests auf .mtabbar-Scope).
- 2026-09-23: Initial spec created

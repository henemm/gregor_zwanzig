---
entity_id: issue_581_trip_detail_jsx
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [frontend, svelte, trip-detail, design-compliance, jsx-migration, issue-581]
---

# Issue #581 — Trip-Detail 1:1 nach JSX (View + Edit)

## Approval

- [ ] Approved

## Purpose

Beide Trip-Detail-Screens (Ansicht `/trips/[id]` und Bearbeiten `/trips/[id]/edit`) weichen in Layout, Breadcrumb-Struktur, Hero-Typo, Übersichts-Tab-Inhalt und Statistik-Karte deutlich von den verbindlichen JSX-Vorlagen ab. Diese Spec beschreibt den vollständigen Umbau auf 1:1-Konformität mit `screen-trip-detail.jsx` (View) und `screen-trip-edit-tabs.jsx` (Edit), einschließlich aller dafür neu zu erstellenden Svelte-Komponenten.

Die Änderungen sind ausschließlich UI-seitig. Backend-API, Datenmodelle und Routing bleiben unverändert.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)

| Datei | Änderungstyp |
|---|---|
| `frontend/src/routes/trips/[id]/+page.svelte` | Layout-Umbau, Breadcrumb-Bar, TopoBg, Danger-Zone entfernen |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Hero-Anpassung: fontSize 38, StatusBadge inline, Meta-Zeile |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | 6-Tab-Definitionen beibehalten, Badge-Rendering via neues Tab-Schema |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Wird durch `HubOverview.svelte` ersetzt (Wrapper delegiert) |
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | Neu: 2-Spalten-Grid mit FullProfile + StageRows + MetricsPreview (links), 3 Cards (rechts) |
| `frontend/src/lib/components/trip-detail/TripStageRow.svelte` | Neu: klickbare Etappen-Zeile (Code + Name + Meta + Summary + Risiko-Pill) |
| `frontend/src/lib/components/trip-detail/MetricsPreview.svelte` | Neu: Chip-Liste aktiver Metriken (read-only) |
| `frontend/src/lib/components/trip-detail/ReportLine.svelte` | Neu: Briefing-Zeile (Dot + Label + Zeit + ChannelDots) |
| `frontend/src/lib/components/trip-detail/ChannelDot.svelte` | Neu: 18×18px Icon-Square für E-Mail/Signal/etc. |
| `frontend/src/lib/components/trip-detail/HubSchedule.svelte` | Neu: 4 Schedule-Cards mit Switch (Tab-4-Inhalt) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Layout-Umbau, Breadcrumb, Hero, Stats-Karte, Tab-Leiste, Etappen-Tab auf EtappenStrip |

## Estimated Scope

- **LoC:** ~600–800 (inkl. 6 neue Komponenten)
- **Files:** 11 geändert/erstellt
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/TopoBg.svelte` | Atom (vorhanden) | Topografischer Hintergrund, `opacity={0.14}` |
| `frontend/src/lib/components/atoms/Card.svelte` | Atom (vorhanden) | Karten-Container mit `padding`-Prop |
| `frontend/src/lib/components/atoms/Pill.svelte` | Atom (vorhanden) | Risiko-Pill in TripStageRow |
| `frontend/src/lib/components/atoms/Switch.svelte` | Atom (vorhanden) | Toggle in HubScheduleCard |
| `frontend/src/lib/components/atoms/SectionH.svelte` | Atom (vorhanden) | Abschnitts-Header mit Eyebrow + optionalem Right-Slot |
| `frontend/src/lib/components/atoms/Btn.svelte` | Atom (vorhanden) | Alle Action-Buttons |
| `frontend/src/lib/components/atoms/Eyebrow.svelte` | Atom (vorhanden) | Eyebrow-Labels in Hero und HubSchedule |
| `frontend/src/lib/components/molecules/AlertRow.svelte` | Molecule (vorhanden) | Alert-Zeilen in HubOverview rechte Karte |
| `frontend/src/lib/components/trip-detail/FullProfile.svelte` | Molecule (vorhanden) | SVG-Höhenprofil in HubOverview |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | Atom (vorhanden) | Inline-StatusBadge im Hero |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Molecule (vorhanden) | Horizontaler Stage-Strip im Edit-Etappen-Tab |
| `frontend/src/lib/utils/tripStats.ts` | Utility (vorhanden) | `computeTripStats(trip)` für Stats-Karte |
| `frontend/src/lib/utils/rightColumn.ts` | Utility (vorhanden) | `getReportSchedule(trip)` für ReportLine-Daten |
| `frontend/src/lib/types.ts` | TypeScript | `Trip`, `Stage`, `AlertRule` |
| `docs/specs/modules/issue_487_trip_detail_overview_cards.md` | Abgelöste Spec | Vorgänger-Layout (4-Karten), wird durch HubOverview ersetzt |

## Implementation Details

### 1. View-Page `+page.svelte` — Layout-Umbau

**Hauptänderungen:**

- `<main class="container mx-auto max-w-5xl p-4">` → `<main style="position: relative; overflow: hidden;">`
- `TopoBg opacity={0.14}` direkt in `<main>` einfügen (absolut positioniert)
- Neue `div.breadcrumb-bar` oben: `padding: 16px 40px`, `borderBottom: 1px solid var(--g-rule-soft)`, flex space-between
  - Links: mono-Text `Trips / {trip.shortName}` (opacity 0.6 für „Trips", volle Stärke für shortName)
  - Rechts: `Btn variant="ghost" size="sm"` Pausieren + Archivieren + `Btn variant="accent" size="sm"` „Test-Briefing senden"
- Bestehende `<section class="danger-zone">` **entfernen** — Pause/Archiv/Löschen-Logik wandert in die Breadcrumb-Bar-Buttons (Pause und Archiv), Löschen entfällt aus der Top-Bar (bleibt als ConfirmDialog, Trigger-Button kommt raus)
- `TripHeader` und `TripTabs` bleiben eingebunden; Hero-Anpassungen erfolgen in TripHeader

```svelte
<main style="position: relative; overflow: hidden;">
  <TopoBg opacity={0.14}/>
  <div class="breadcrumb-bar" data-testid="trip-detail-breadcrumb">
    <span class="mono breadcrumb-text">...</span>
    <div class="breadcrumb-actions">
      <Btn variant="ghost" size="sm" onclick={handlePauseClick}>Pausieren</Btn>
      <Btn variant="ghost" size="sm" onclick={handleArchiveClick}>Archivieren</Btn>
      <Btn variant="accent" size="sm">Test-Briefing senden</Btn>
    </div>
  </div>
  <TripHeader {trip} {now} .../>
  <TripTabs {initialTab} {trip} badges={tabBadges}/>
</main>
```

### 2. `TripHeader.svelte` — Hero-Anpassung

**Geänderte Werte:**
- H1: `font-size: 38px`, `font-weight: 600`, `letter-spacing: -0.02em`, `line-height: 1.1`
- Hero-Padding: `26px 40px 18px`
- Eyebrow-Text: `"Trip · {trip.region}"` (statt bisherigem Format)
- Meta-Zeile nach H1: StatusBadge inline + mono-Text `{startDate} → {endDate} · {stages.length} Etappen · {totalKm} km · ↑{totalAscent} m`
- Kein max-width-Constraint im Hero selbst; übergeordnetes Layout (max-width: 1480px) kommt von HubOverview/HubSchedule

### 3. `HubOverview.svelte` — neuer Übersichts-Tab-Inhalt (ersetzt TripOverview)

**Props:** `{ trip: Trip, activeStage?: number, onStage?: (i: number) => void, onJump?: (tab: string) => void }`

**Layout:** `display: grid; grid-template-columns: 1fr 380px; gap: 32px; padding: 32px 40px 60px; max-width: 1480px`

**Linke Spalte:**
1. `SectionH eyebrow="Etappen" title="Reihenfolge & Profil"` mit Btn „Im Editor öffnen →" rechts (ruft `onJump("etappen")`)
2. `Card padding={20}` → `FullProfile stages={trip.stages} active={activeStage} onClick={onStage}`
3. Darunter (marginTop: 24): `TripStageRow` für jede Stage (`active` wenn index === activeStage, `onclick` setzt activeStage)
4. `SectionH eyebrow="Wetter-Metriken" title="14 Spalten · Preset Alpen-Trekking"` mit Btn „Bearbeiten →" (ruft `onJump("metriken")`)
5. `MetricsPreview metrics={trip.display_config?.metrics ?? []}`

**Rechte Spalte** (flex-direction: column, gap: 20):
1. Card padding={18}: Eyebrow „Briefings laufen" + ReportLines + Btn „Zeitplan bearbeiten →"
2. Card padding={18}: Eyebrow „Alerts (letzte 7 Tage)" + AlertRows (letzte 2) + Btn „Alle Alerts →"
3. Card padding={18} background=`var(--g-card-alt)`: Eyebrow „Vorschau" + Erklärungstext + Btn primary „Vorschau öffnen"

### 4. `TripStageRow.svelte` — Etappen-Zeile (View-only)

**Props:** `{ stage: Stage, index: number, active?: boolean, onclick?: () => void }`

**Layout:** `display: grid; grid-template-columns: 60px 1fr 280px 100px; gap: 16px; padding: 14px 18px`

| Spalte | Inhalt |
|---|---|
| 1 | `stage.code`, mono, 11px, `var(--g-ink-3)` |
| 2 | Stage-Titel (ohne Präfix vor „:") fett 14px + mono Meta-Zeile: date · km · ↑ascent ↓descent · max elev · WP-Anzahl |
| 3 | `stage.summary`, 12px, kursiv, `var(--g-ink-2)` |
| 4 | `Pill tone={riskTone}` rechtsbündig: high→„Risiko" (bad), med→„Achten" (warn), sonst→„OK" (good) |

Border-left: `3px solid var(--g-accent)` wenn active, sonst transparent. Background: `rgba(196,90,42,0.05)` wenn active.

### 5. `MetricsPreview.svelte` — Metrik-Chip-Liste

**Props:** `{ metrics: MetricConfig[] }`

Rendert eine Chip-Liste aller bekannten Metriken. Aktive Metriken (in `metrics` enthalten und `enabled: true`) erhalten dunklen Hintergrund (`var(--g-ink)`, Text `var(--g-paper)`), inaktive erscheinen mit transparentem Hintergrund und gedämmter Border. Fußzeile: Anzahl aktiver Metriken + Preset-Name (falls vorhanden).

### 6. `ReportLine.svelte` — Briefing-Zeile

**Props:** `{ kind: 'morning' | 'evening' | 'alert', time: string, channels: string[], active?: boolean, alert?: boolean }`

Layout: flex, Dot (6×6px rund, Farbe: active+alert→accent, active→good, sonst→rule) + Label + Zeit + ChannelDot-Reihe. Padding 8px 0, borderBottom rule-soft.

### 7. `ChannelDot.svelte` — Kanal-Icon

**Props:** `{ kind: 'email' | 'signal' | 'telegram' | 'sms' }`

18×18px `<span>`, `border-radius: 3px`, `background: var(--g-paper-deep)`. Icon-Map: email→✉, signal→▲, telegram→✈, sms→·. Font-size 10px, mono, centered.

### 8. `HubSchedule.svelte` — Briefing-Zeitplan-Tab

**Kein Prop** (liest Daten aus Trip via Context oder wird mit `trip`-Prop übergeben).

Layout: `padding: 32px 40px 60px; max-width: 1480px`
- Eyebrow „Briefing-Zeitplan"
- H2 28px: „Wann geht was an welchen Kanal?"
- Erklärungstext 14px, max-width 720px
- 2×2-Grid (`grid-template-columns: 1fr 1fr; gap: 20px; max-width: 980px`) mit 4 `HubScheduleCard`

**HubScheduleCard** (internes Sub-Template):
- Props: `{ title, time, sub, channels: string[], on?: boolean, alert?: boolean }`
- Interner `$state` für `enabled` (initialisiert aus `on`-Prop, kein Backend-Roundtrip)
- Header: Titel + Untertitel links, Switch (tone: alert→accent, sonst→good) rechts
- Footer (padding-top 14px, border-top rule-soft): mono-Zeit links, ChannelDots rechts

### 9. Edit-Screen `TripEditView.svelte` — Umbau

**Layout-Änderungen:**
- `<div class="max-w-5xl mx-auto p-4">` → `<div data-testid="trip-edit-view">` (kein max-w-5xl, kein mx-auto p-4)
- TopoBg entfällt (liegt im `+page.svelte` der Edit-Route, analog View-Screen)

**Breadcrumb:**
- Vorher: „MEINE TRIPS · TRIP BEARBEITEN" (Tailwind-Klassen, uppercase)
- Nachher: mono, 11px, `var(--g-ink-3)`, Format: `Trips / {trip.shortName} / Bearbeiten` (opacity 0.6 für erste zwei Segmente, voll für „Bearbeiten")

**Hero:**
- Vorher: H1 nur `trip.name`, text-2xl
- Nachher: Eyebrow „Trip bearbeiten · {trip.region}", H1 30px fontWeight 600: `<span class="mono">{trip.shortCode}</span> {trip.name}`

**Tab-Leiste:**
- Vorher: `Segmented`-Atom mit Label-Inline-Count (`"Etappen & Wegpunkte 13"`, `"Alarmregeln 2"`)
- Nachher: Underline-Tabs analog View-Screen; Badges als eigene Pill-Spans (analog JSX `TripEditTabBar`); data-testids erhalten

**Stats-Karte** (immer sichtbar):
- Vorher: einzeilig, flex, plain Text
- Nachher: Zwei-Spalten-Header: links „GESAMT" (km + ascent), rechts „ZEITRAUM" (date range + Tage-Anzahl); „REPORTS KONFIGURIERT"-Badge rechtsbündig wenn aktiviert

**Etappen-Tab:**
- Vorher: `EditStagesPanelNew` (vertikale Liste)
- Nachher: `EtappenStrip bind:stages tripId={trip.id}` (horizontal) + Hinweis-Text: „Klicke auf eine Etappe, um Wegpunkte visuell zu bearbeiten."

## Expected Behavior

- **Input:** `trip: Trip`-Objekt (View-Page via `data.trip`, Edit-Page via gleichen Weg)
- **Output:** Korrekt gestaltete Trip-Detail-Seite (View) und Trip-Bearbeiten-Seite (Edit) gemäß JSX-Vorlagen
- **Side effects:** Pause/Archiv-Aktionen verbleiben funktional (PATCH /api/trips/[id]/state), nur die Trigger-Buttons sind visuell verschoben. Löschen bleibt via ConfirmDialog erreichbar (Trigger-Button aus Danger-Zone wird in zukünftigem Issue nachgezogen — explizit Out-of-Scope).

## Acceptance Criteria

**AC-1:** Given die View-Seite `/trips/[id]` wird geladen / When die Seite gerendert ist / Then enthält `[data-testid="trip-detail-breadcrumb"]` links einen mono-Text mit „Trips / {shortName}" und rechts drei Buttons: „Pausieren" (ghost), „Archivieren" (ghost), „Test-Briefing senden" (accent)

**AC-2:** Given die View-Seite mit einem aktiven Trip / When die Seite gerendert ist / Then hat das H1-Element `font-size` 38px und `letter-spacing` -0.02em, und der Eyebrow-Text enthält „Trip ·" gefolgt vom Region-Wert

**AC-3:** Given die View-Seite mit mindestens einer Stage im Trip / When der Übersicht-Tab aktiv ist / Then zeigt `[data-testid="hub-overview"]` links ein Höhenprofil (FullProfile) und darunter Etappen-Zeilen (TripStageRow), rechts drei Cards (Briefings laufen, Alerts, Vorschau)

**AC-4:** Given eine TripStageRow mit `risk="high"` / When die Zeile gerendert wird / Then erscheint eine Pill mit tone="bad" und Label „Risiko"; bei `risk="med"` tone="warn" und Label „Achten"; bei fehlendem risk-Wert tone="good" und Label „OK"

**AC-5:** Given die View-Seite / When der Tab „Briefing-Zeitplan" (Tab 4) geöffnet wird / Then zeigt `[data-testid="hub-schedule"]` genau 4 HubScheduleCards in einem 2×2-Grid, jede Card mit Titel, Untertitel, Switch und mono-Zeitangabe

**AC-6:** Given die Edit-Seite `/trips/[id]/edit` / When die Seite gerendert ist / Then enthält der Breadcrumb „Trips / {shortName} / Bearbeiten" (mono-Format), das H1 enthält den shortCode gefolgt vom trip.name, und die Stats-Karte zeigt GESAMT-Spalte (km + ascent) und ZEITRAUM-Spalte (Datumsbereich + Tage)

**AC-7:** Given die Edit-Seite / When der Tab „Etappen & Wegpunkte" geöffnet wird / Then ist `EtappenStrip` sichtbar (horizontale Darstellung) und der Text „Klicke auf eine Etappe, um Wegpunkte visuell zu bearbeiten." ist unterhalb sichtbar; `EditStagesPanelNew` ist nicht mehr gerendert

**AC-8:** Given die Edit-Seite mit 5 Alarmregeln / When die Tab-Leiste gerendert wird / Then hat der Tab „Alarmregeln" ein separates Badge-Element mit Inhalt „5" und accent-Hintergrund (kein Inline-Text wie „Alarmregeln 5")

**AC-9:** Given die View-Seite / When die bisherige `<section class="danger-zone">` gesucht wird / Then ist kein Element mit `data-testid="danger-zone"` im DOM vorhanden (Danger-Zone ist entfernt)

**AC-10:** Given die View-Seite / When `TopoBg` im Source von `+page.svelte` gesucht wird / Then ist `TopoBg` mit `opacity={0.14}` direkt in `<main>` eingebunden und `max-w-5xl` ist aus dem `<main>`-Element entfernt

## Known Limitations

- Die Löschen-Funktion (bisher Danger-Zone-Button) verliert vorübergehend ihren Trigger-Button auf der View-Page. Der ConfirmDialog-Code bleibt erhalten. Ein separates Issue für den neuen Löschen-Einstiegspunkt ist anzulegen.
- HubSchedule zeigt aktuellen Zustand der Report-Config read-only; Switch-Toggles sind Dummy-State ohne Backend-Anbindung (wie in JSX spezifiziert).
- Tests für `TripOverview.issue487.test.ts` und `TripOverview.issue504.test.ts` müssen aktualisiert werden, da sie das abgelöste 4-Karten-Layout prüfen.
- MetricsPreview zeigt in MVP alle 26 bekannten Metriken mit aktivem/inaktivem Zustand aus `trip.display_config`. Falls `display_config` fehlt, werden alle Metriken als inaktiv dargestellt.

## Changelog

- 2026-06-04: Initial spec created (Issue #581, JSX-Compliance View + Edit)

---
entity_id: bug_271_wizard_mobile_stepper
type: bugfix
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [bugfix, mobile, stepper, wizard, bottom-nav, safe-area, touch-target, frontend, issue-271]
---

<!-- Issue #271 — Bug: Trip-Wizard – Stepper und Labels klippen auf Mobile -->

# Issue #271 — Bug-Fix: Trip-Wizard Stepper und Footer auf Mobile reparieren

## Approval

- [ ] Approved

## Zweck

Auf Viewports ≤ 899 px teilen sich alle vier Wizard-Steps einen Stepper-Bereich von ca. 93 px, wodurch Labels überlappen und abgeschnitten werden. Gleichzeitig überlagert die App-Shell-BottomNav (64 px, `fixed bottom-0`) den Wizard-Footer, sodass die Schaltflächen "Zurück" und "Weiter" verdeckt werden und deren Touch-Targets unter 44 px bleiben. Der Fix ersetzt den Desktop-Stepper auf Mobile durch einen kompakten einzeiligen Fortschrittsindikator, blendet die BottomNav auf der Wizard-Route aus und macht den Footer sticky mit korrektem Safe-Area-Abstand.

Drei unabhängige Ursachen werden zusammen behoben, weil sie gemeinsam die Mobile-Nutzbarkeit des Trip-Wizards blockieren und alle drei Dateien überschneidungsfreie Änderungen von ≤ 28 LoC erfordern.

## Quelle / Source

**Geänderte Dateien:**

- `frontend/src/routes/+layout.svelte` — `isWizard`-Derived ableiten, `<BottomNav>` konditionell ausblenden (Zeile ~61, `isLogin`-Muster)
- `frontend/src/lib/components/trip-wizard/Stepper.svelte` — Desktop-Block mit `class="desktop:block hidden"` markieren; neuen Mobile-Block `class="mobile:block hidden"` mit kompaktem Text-Format ergänzen (Zeile ~19)
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` — Footer-`<div>` um `sticky bottom-0`, `bg-[var(--g-paper)]`, Safe-Area-Padding, `mobile:min-h-[44px]` für Buttons erweitern (Zeile ~106)

**NICHT ändern:**

- `frontend/src/app.css` — keine neuen Varianten nötig; `mobile:` und `desktop:` sind bereits definiert
- `frontend/src/lib/components/trip-wizard/BottomNav.svelte` — wird ausgeblendet, nicht modifiziert
- Alle Step-Komponenten (`Step1.svelte` … `Step4.svelte`) — kein Änderungsbedarf
- `frontend/src/lib/stores/wizardState.svelte.ts` — kein Änderungsbedarf

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/+layout.svelte` | SvelteKit-Layout | Root-Layout, das `BottomNav` rendert; `isLogin`-Derived als Vorlage für `isWizard` |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | Svelte-Komponente | Rendert 4-Step-Indikator; erhält Props `current` (1–4) und `labels: string[]` |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Svelte-Komponente | Wrapper für alle Wizard-Steps; beinhaltet Footer-Div mit Navigations-Buttons |
| `frontend/src/app.css` | CSS-Datei | Definiert Custom Variants `mobile:` (`max-width: 899px`) und `desktop:` (`min-width: 900px`) |
| App-Shell `BottomNav` | Svelte-Komponente | `fixed bottom-0 z-50`, 64 px hoch — überlagert Wizard-Footer ohne Ausblend-Logik |

## Implementation Details

### 1. `frontend/src/routes/+layout.svelte` — BottomNav konditionell ausblenden

Analog zur bestehenden `isLogin`-Derived (Zeile ~61) eine `isWizard`-Derived ergänzen:

```svelte
const isWizard = $derived(page.url.pathname.startsWith('/trips/new'));
```

Im Template `<BottomNav>` nur rendern wenn weder Login noch Wizard aktiv:

```svelte
{#if !isLogin && !isWizard}
  <BottomNav />
{/if}
```

Keine weiteren Änderungen an diesem File. Delta: +3 LoC (1 Derived, 1 Bedingungsklausel angepasst).

### 2. `frontend/src/lib/components/trip-wizard/Stepper.svelte` — Compact Mobile View

Den bestehenden Stepper-Container auf `class="desktop:block hidden"` setzen (er bleibt inhaltlich unverändert).

Darunter einen neuen Mobile-Block einfügen:

```svelte
<!-- Mobile Compact Stepper -->
<div class="mobile:flex hidden items-center gap-2 text-sm font-mono text-[var(--g-ink-faint)]">
  <span class="font-semibold text-[var(--g-ink)]">{current} / {labels.length}</span>
  <span>·</span>
  <span class="text-[var(--g-ink)]">{labels[current - 1]}</span>
</div>
```

Format: `{current} / {labels.length} · {labels[current-1]}`  
Beispiel bei Step 2: `"2 / 4 · GPX-Import"`

Der Mobile-Block referenziert ausschließlich bereits vorhandene Props (`current`, `labels`). Keine neuen Props, kein Zustandsmanagement. Delta: +15 LoC.

### 3. `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` — Sticky Footer + Safe Area

Den Footer-`<div>` (Zeile ~106) um folgende Klassen und das `style`-Attribut erweitern:

```svelte
<div
  class="flex justify-between gap-3 pt-4 border-t border-[var(--g-ink-faint)]
         sticky bottom-0 bg-[var(--g-paper)]
         mobile:py-3 mobile:px-4 mobile:mx-[-1rem]"
  style="padding-bottom: env(safe-area-inset-bottom, 0px);"
>
```

Buttons im Footer erhalten zusätzlich `mobile:min-h-[44px]`, damit iOS-Touch-Targets die HIG-Mindestgröße von 44 × 44 px erreichen:

```svelte
<Button ... class="... mobile:min-h-[44px]">Zurück</Button>
<Button ... class="... mobile:min-h-[44px]">Weiter</Button>
```

`sticky bottom-0` funktioniert korrekt innerhalb des `overflow-auto`-`<main>`-Containers. `bg-[var(--g-paper)]` verhindert, dass scrollender Inhalt unter dem Footer sichtbar ist. `mobile:mx-[-1rem]` hebt das Page-Padding auf und lässt den Footer über die volle Breite ziehen. Delta: +10 LoC.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/routes/+layout.svelte` | +3 | nein (Frontend-Asset) |
| `frontend/src/lib/components/trip-wizard/Stepper.svelte` | +15 | nein (Frontend-Asset) |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | +10 | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Kein Laufzeit-Input — CSS- und Markup-Änderungen; Props `current` (1–4) und `labels: string[]` werden bereits vom Eltern-Komponenten geliefert
- **Output:**
  - Viewport ≤ 899 px: Stepper zeigt einzeiligen Text `"{current} / {labels.length} · {labels[current-1]}"` anstelle der 4-Kreis-Darstellung
  - Viewport ≥ 900 px: Stepper unverändert (4 Kreise + Labels)
  - Viewport ≤ 899 px auf `/trips/new`: App-Shell-BottomNav nicht sichtbar
  - Footer bleibt beim Scrollen am unteren Bildschirmrand sichtbar; Buttons haben Touch-Target ≥ 44 px Höhe; Safe-Area wird auf iPhones mit Home Indicator korrekt berücksichtigt
- **Side effects:** Keine Datenänderungen. Desktop-Layout und alle anderen Routen sind nicht betroffen. Die `isWizard`-Derived gilt nur für Pfade, die mit `/trips/new` beginnen.

## Acceptance Criteria

- **AC-1:** Given Viewport ≤ 899 px und `/trips/new` ist geöffnet, When die Seite lädt (Step 1 aktiv), Then zeigt der Stepper ausschließlich den Text `"1 / 4 · Profil & Eckdaten"` als einzeiligen Fortschrittsindikator — keine 4-Kreis-Darstellung sichtbar
  - Test: (populated after /tdd-red)

- **AC-2:** Given Viewport ≤ 899 px und Schritt 2 ist aktiv, When der Nutzer von Step 1 auf Step 2 navigiert, Then zeigt der Stepper `"2 / 4 · GPX-Import"` — der Label wechselt synchron mit `current`
  - Test: (populated after /tdd-red)

- **AC-3:** Given Viewport ≥ 900 px und `/trips/new` ist geöffnet, When die Seite lädt, Then zeigt der Stepper alle 4 Kreise mit Labels wie bisher — keine Regression auf Desktop
  - Test: (populated after /tdd-red)

- **AC-4:** Given Viewport ≤ 899 px, When der Nutzer `/trips/new` aufruft, Then ist die App-Shell-BottomNav nicht sichtbar (weder gerendert noch durch z-index überlagert)
  - Test: (populated after /tdd-red)

- **AC-5:** Given Viewport ≤ 899 px und der Wizard-Footer ist sichtbar, When der Nutzer auf den Zurück- oder Weiter-Button tippt, Then hat jeder Button eine Touch-Target-Höhe von mindestens 44 px und der Footer wird nicht durch die BottomNav überlagert
  - Test: (populated after /tdd-red)

## Known Limitations

- **`/trips/new`-Pfad-Matching:** `isWizard` prüft `pathname.startsWith('/trips/new')`. Sollte der Wizard auf einem anderen Pfad laufen (z. B. `/trips/:id/edit`), muss das Muster angepasst werden — betrifft diese Spec nicht.
- **Safe-Area nur auf iOS wirksam:** `env(safe-area-inset-bottom, 0px)` ist ein iOS-spezifisches CSS-Feature. Auf Android und Desktop gibt es keinen negativen Effekt — der Fallback `0px` greift automatisch.
- **Kein automatisierter Touch-Target-Größen-Test:** Die 44 px-Anforderung lässt sich mit Playwright über `getBoundingClientRect().height` prüfen, setzt aber einen emulierten Mobile-Viewport im Test voraus.
- **Desktop-Stepper (4 Kreise) bleibt ungeändert:** Etwaige bestehende Darstellungsprobleme auf Desktop sind nicht Gegenstand dieser Spec.

## Out of Scope

- `WizardCancelSheet` (Nice-to-Have, separates Issue)
- Änderungen an Step-Komponenten (`Step1.svelte` … `Step4.svelte`)
- Änderungen an `wizardState.svelte.ts`
- Backend-Änderungen jeglicher Art
- Weitere Wizard-Routen außer `/trips/new`

## Changelog

- 2026-05-21: Initial spec erstellt. Behebt 3 unabhängige Mobile-Ursachen: kompakter Stepper (Stepper.svelte +15 LoC), BottomNav-Ausblendung (+layout.svelte +3 LoC), sticky Footer mit Safe-Area (TripWizardShell.svelte +10 LoC).

---
entity_id: issue_314_ui_state_patterns
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [frontend, ui, empty-state, migration, issue-314]
---

<!-- Issue #314 — UI-Zustandsmuster: EmptyState-Komponente + Migration aller Inline-Leerzustände -->

# Issue #314 — EmptyState-Komponente und Migration aller Inline-Leerzustände

## Approval

- [ ] Approved

## Zweck

Eine gemeinsame `EmptyState.svelte`-Komponente für alle Leerzustände der App schaffen und alle fünf Seiten, die heute dasselbe Inline-Muster duplizieren, auf diese Komponente migrieren. Das beseitigt eine sich wiederholende Kopier-Paste-Struktur an sechs Stellen (5 Seiten + Home) und stellt sicher, dass `data-testid="empty-state"` weiterhin zuverlässig von den E2E-Tests gefunden wird, ohne dass jede Seite die genaue CSS-Klassen-Kombinatorik selbst kennen muss.

## Quelle / Source

**Neue Dateien:**
- `frontend/src/lib/components/ui/empty-state/EmptyState.svelte`
- `frontend/src/lib/components/ui/empty-state/index.ts`

**Geänderte Dateien:**
- `frontend/src/app.css` — neues `[data-slot="empty-state"]`-Rule
- `frontend/src/routes/trips/+page.svelte` — Migration
- `frontend/src/routes/locations/+page.svelte` — Migration
- `frontend/src/routes/subscriptions/+page.svelte` — Migration
- `frontend/src/routes/archiv/+page.svelte` — Migration (Minimalvariante)
- `frontend/src/routes/compare/+page.svelte` — Leerzustand ergänzen
- `frontend/src/routes/_home/EmptyKachel.svelte` — Migration + Style-Block löschen
- `frontend/src/routes/account/+page.svelte` — zwei `window.confirm()` → `Dialog.Root`
- `frontend/e2e/issue-344-wetter-profile.spec.ts` — zwei Assertions anpassen

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit `frontend/src/`). Keine Go/Python-Schicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Token-Quelle | `--g-ink`, `--g-ink-faint`, `--g-ink-muted`, `--g-r-2` für Styling des `[data-slot="empty-state"]`-Rules |
| Lucide Svelte | Externe Bibliothek | Icon-Übergabe via `Component`-Prop; bestehende Icon-Imports in den Seiten bleiben erhalten |
| `$lib/components/ui/` (Btn, Dialog) | UI-Bibliothek intern | Btn für CTA-Slots; `Dialog.Root` als Ersatz für `window.confirm()` in Account |
| `e2e/trips.spec.ts:13` | E2E-Test | Referenziert `data-testid="empty-state"` — darf nach Migration nicht brechen |
| `e2e/locations.spec.ts:12` | E2E-Test | Referenziert `data-testid="empty-state"` |
| `e2e/issue-321-copy-fix-deine-touren.spec.ts:38` | E2E-Test | Referenziert `data-testid="empty-state"` |
| `e2e/issue-344-wetter-profile.spec.ts` | E2E-Test | AC-5/AC-5b nutzen `page.once('dialog')` → auf Dialog.Root umstellen |

## Implementation Details

### 1. CSS-Rule in `app.css`

```css
[data-slot="empty-state"] {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  border: 1px dashed var(--g-ink-faint);
  border-radius: var(--g-r-2);
  padding: 2.5rem;
  gap: 0.5rem;
}
[data-slot="empty-state"] [data-slot="empty-state-icon"] {
  width: 40px;
  height: 40px;
  color: var(--g-ink-faint);
  margin-bottom: 0.25rem;
}
[data-slot="empty-state"] [data-slot="empty-state-title"] {
  font-weight: 500;
  color: var(--g-ink);
}
[data-slot="empty-state"] [data-slot="empty-state-desc"] {
  font-size: 0.875rem;
  color: var(--g-ink-muted);
  margin-top: 0.25rem;
}
```

### 2. `EmptyState.svelte`

Props-Interface:
```typescript
interface EmptyStateProps {
  icon?: Component;       // optionaler Lucide-Icon (svelte Component-Typ)
  title: string;          // Pflicht: Überschrift
  description?: string;   // optional: Hilfstext darunter
  children?: Snippet;     // optional: CTA-Button(s) via Slot
}
```

Render-Struktur:
```svelte
<script lang="ts">
  import type { Component, Snippet } from 'svelte';
  let { icon: Icon, title, description, children }: EmptyStateProps = $props();
</script>

<div data-slot="empty-state" data-testid="empty-state">
  {#if Icon}
    <Icon data-slot="empty-state-icon" />
  {/if}
  <p data-slot="empty-state-title">{title}</p>
  {#if description}
    <p data-slot="empty-state-desc">{description}</p>
  {/if}
  {@render children?.()}
</div>
```

`data-testid="empty-state"` ist hartcodiert (kein Prop), weil drei E2E-Tests davon abhängen.

### 3. `index.ts`

```typescript
export { default as EmptyState } from './EmptyState.svelte';
```

### 4. Migration der 5 Seiten

Alle fünf Seiten ersetzen ihr identisches Inline-Muster durch `<EmptyState ...>`. Der `data-testid="empty-state"` ist bereits in der Komponente; der bestehende wird aus dem Inline-HTML entfernt. Konkrete Belegungen:

| Seite | icon | title | description | children |
|-------|------|-------|-------------|----------|
| `routes/trips/+page.svelte` | `RouteIcon` | "Noch keine Tour." | "Lege deine erste Tour an — Wizard in 4 Schritten." | `<Btn variant="outline" onclick={goto('/trips/new')}>Neue Tour</Btn>` |
| `routes/locations/+page.svelte` | `MapPinIcon` | "Keine Locations vorhanden" | "Fuege Orte hinzu, um Wetter-Daten abzurufen und zu vergleichen." | `<Btn variant="outline" onclick={openCreate()}>Ort hinzufügen</Btn>` |
| `routes/subscriptions/+page.svelte` | `BellIcon` | "Keine Abos vorhanden" | "Erstelle dein erstes Abo fuer automatische Wetter-Vergleiche." | `<Btn variant="outline" onclick={openCreate()}>Abo erstellen</Btn>` |
| `routes/archiv/+page.svelte` | — | "Noch keine abgeschlossenen Touren im Archiv." | — | — |
| `routes/compare/+page.svelte` | `MapPinIcon` | "Keine Orte konfiguriert" | "Füge zuerst einen Ort hinzu, um einen Vergleich zu starten." | `<Btn variant="outline" href="/locations">Zu Locations</Btn>` |

### 5. `EmptyKachel.svelte` (Home)

Bestehenden Rumpf durch EmptyState ersetzen:
```svelte
<EmptyState
  title="Willkommen bei Gregor 20"
  description="Leg deine erste Tour an oder starte einen Orts-Vergleich.">
  <Btn variant="accent" href="/trips/new">+ Neue Tour</Btn>
  <Btn variant="outline" href="/compare">+ Neuer Vergleich</Btn>
</EmptyState>
```
Den gesamten `<style>`-Block in `EmptyKachel.svelte` löschen.

### 6. `account/+page.svelte` — `window.confirm()` → `Dialog.Root` (×2)

**deletePreset (~Zeile 57):**
- Neuer State: `let deletePresetTarget: MetricPreset | null = $state(null)`
- `deletePreset(p)` setzt `deletePresetTarget = p` statt `window.confirm()` inline
- Dialog zeigt `deletePresetTarget.name`, hat "Löschen"- und "Abbrechen"-Button
- "Löschen"-Button ruft die vorhandene API-Lösch-Logik auf, setzt danach `deletePresetTarget = null`

**deleteAccount (~Zeile 200):**
- Neuer State: `let showDeleteAccountDialog = $state(false)`
- "Account löschen"-Button setzt `showDeleteAccountDialog = true`
- Dialog mit Bestätigung, Löschen-Button führt bestehende Lösch-Logik aus

### 7. E2E-Test `issue-344-wetter-profile.spec.ts`

AC-5 und AC-5b nutzen heute `page.once('dialog', d => d.accept())`. Diese Listener entfernen. Stattdessen: `await page.getByRole('button', { name: 'Löschen' }).click()` auf den Dialog-Confirm-Button targeting. Selektoren prüfen ob der Dialog geschlossen ist und die Liste aktualisiert wurde.

## Expected Behavior

- **Input:** Keine Laufzeit-Daten. Komponenten werden bei Bedingung "Liste ist leer" gerendert.
- **Output:** Zentrierter Inhaltsblock mit gestricheltem Rahmen, optionalem Icon (40 px, `--g-ink-faint`), Titel (`--g-ink`, font-weight 500), optionalem Beschreibungstext (`--g-ink-muted`, 14 px), optionalen CTA-Buttons via Slot. `data-testid="empty-state"` ist immer gesetzt.
- **Side effects:** Alle drei E2E-Suiten (`trips`, `locations`, `issue-321`) laufen nach der Migration ohne Anpassung weiter, weil `data-testid` erhalten bleibt. `issue-344-wetter-profile.spec.ts` braucht die zwei Assertion-Korrekturen (Dialog statt `page.once`).

## Acceptance Criteria

- **AC-1:** Given `EmptyState.svelte` in `lib/components/ui/empty-state/` / When die Komponente mit `title`, optionalem `icon`, optionalem `description` und einem `children`-Slot gerendert wird / Then enthält das Root-Element `data-slot="empty-state"` und `data-testid="empty-state"`, das Icon erscheint mit 40-px-Größe in `--g-ink-faint`, der Titel in `--g-ink` font-weight 500, die Beschreibung in `--g-ink-muted` 14 px; fehlendes `icon` oder `description` erzeugt kein leeres Element.
  - Test: `e2e/issue-314-empty-state.spec.ts` — strukturell verifiziert via Adversary (alle data-slot/data-testid-Attribute + optionale Props korrekt abgesichert)

- **AC-2:** Given die 5 Routes `trips`, `locations`, `subscriptions`, `archiv`, `compare` / When eine leere Liste vorliegt / Then rendert jede Seite `<EmptyState>` mit dem korrekten `title`, `description` und CTA-Inhalt gemäß Migrations-Tabelle; kein dupliziertes Inline-`data-testid` mehr im Seiten-HTML.
  - Test: `e2e/issue-314-empty-state.spec.ts` → AC-2a (trips), AC-2b (locations), AC-2c (subscriptions), AC-2d (compare) — prüfen auf `[data-slot="empty-state"]` wenn kein Datenbestand

- **AC-3:** Given `routes/_home/EmptyKachel.svelte` / When die Home-Seite gerendert wird und keine Tour/Vergleich vorhanden ist / Then zeigt `EmptyKachel` den Text "Willkommen bei Gregor 20" sowie die zwei Buttons "Neue Tour" und "Neuer Vergleich" via `EmptyState`; der alte `<style>`-Block existiert nicht mehr in der Datei.
  - Test: `e2e/issue-314-empty-state.spec.ts` → AC-3 — statisch verifiziert: EmptyKachel.svelte hat keinen `<style>`-Block mehr, nutzt EmptyState (Adversary VERIFIED)

- **AC-4:** Given die drei bestehenden E2E-Suites `trips.spec.ts`, `locations.spec.ts`, `issue-321-copy-fix-deine-touren.spec.ts` / When sie nach der Migration laufen / Then finden alle `page.getByTestId('empty-state')`-Selektoren ihr Element ohne Anpassung dieser Testdateien.
  - Test: `e2e/trips.spec.ts`, `e2e/locations.spec.ts`, `e2e/issue-321-copy-fix-deine-touren.spec.ts` — keine Änderungen nötig, `data-testid="empty-state"` vom Component hartcodiert

- **AC-5:** Given `routes/account/+page.svelte` mit dem Preset-Löschen-Workflow / When der Nutzer auf "Profil löschen" klickt / Then öffnet sich ein `Dialog.Root` mit dem Preset-Namen und "Löschen"- + "Abbrechen"-Button; kein `window.confirm()` wird aufgerufen; nach Bestätigung verschwindet der Eintrag aus der Liste.
  - Test: `e2e/issue-314-empty-state.spec.ts` → AC-5 + AC-5b — 2 passed (Dialog erscheint, Abbrechen-Klick klappt ohne window.confirm)

- **AC-6:** Given `routes/account/+page.svelte` mit dem Account-Löschen-Workflow / When der Nutzer auf den Account-Löschen-Button klickt / Then öffnet sich ein separates `Dialog.Root` mit Bestätigung; kein `window.confirm()` wird aufgerufen; `e2e/issue-344-wetter-profile.spec.ts` AC-5/AC-5b interagieren mit Dialog-Buttons statt `page.once('dialog')` und sind grün.
  - Test: `e2e/issue-314-empty-state.spec.ts` → AC-6 (passed); `e2e/issue-344-wetter-profile.spec.ts` → AC-5/AC-5b (9/9 passed nach Dialog-Migration)

## Known Limitations

- `AlertRulesEditor`-Leerzustand (innerhalb Card, andere visuelle Struktur) und Account-Inline-Text "Noch keine Locations" (nur Link, kein Zustandsmuster) sind bewusst nicht migriert.
- Toast-Komponente gehört zu Issue #312 und wird hier nicht angetastet.
- Die Komponente hat kein eigenes `data-testid`-Prop; Tests die spezifischere Selektoren brauchen (z. B. `[data-testid="empty-state-trips"]`) müssen weiterhin über die Seiten-spezifische Umgebung selektieren.

## Changelog

- 2026-05-26: Initial spec created (Issue #314, EmptyState-Komponente + Migration)

---
entity_id: issue_212_216_button_cleanup
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, refactor, cleanup, design-system]
issue: 212
---

<!-- Issues #212 + #216 — Button-Duplikat-Cleanup (Phase B + C) -->

# Issues #212 + #216 — Button-Duplikat-Cleanup

## Approval

- [ ] Approved

## Zweck

Phase B + C der Button-Konsolidierung (Epic #133) abschließen:
- **Phase B (#212):** Letzte 10 `<Button>`-Aufrufe (in 2 Dateien) auf
  `<Btn>` migrieren.
- **Phase C (#216):** `frontend/src/lib/components/ui/button/`-Verzeichnis
  komplett löschen.

Anschließend existiert nur noch **eine Button-Komponente** im Repo.
Stand der Migration: 16 von 18 Dateien nutzen bereits `Btn` — die restlichen
2 Dateien (`EditRouteSection.svelte`, `EditStagesSection.svelte`) sind die
verbleibenden Migrations-Ziele.

**Phantomreferenzen-Check** (siehe Context-Doc): außerhalb der 2 Dateien
keinerlei `import.*Button`-Verwendung; `buttonVariants`, `ButtonProps`,
`ButtonVariant`, `ButtonSize` ebenfalls 0 Treffer. Eliminierung ist sicher.

## Quelle / Source

- `frontend/src/lib/components/edit/EditRouteSection.svelte` — Import + 3 Tags migrieren
- `frontend/src/lib/components/edit/EditStagesSection.svelte` — Import + 7 Tags migrieren
- `frontend/src/lib/components/ui/button/` (Verzeichnis komplett) — entfernen

## Acceptance Criteria

- **AC-1:** Given die zwei Edit-Section-Dateien / When der Build läuft / Then importieren sie `{ Btn }` aus `$lib/components/ui/btn/index.js` (nicht mehr `{ Button }` aus `ui/button/index.js`); alle 10 `<Button>`-Tags sind durch `<Btn>` ersetzt

- **AC-2:** Given das Verzeichnis `frontend/src/lib/components/ui/button/` / When der Build/Repo-Stand geprüft wird / Then existiert es nicht mehr; weder `button.svelte` noch `index.ts` sind im Repo vorhanden

- **AC-3:** Given das gesamte Frontend-Verzeichnis / When `grep -rn "from.*ui/button\|<Button[ />]" frontend/src/` läuft / Then liefert es **0 Treffer**

- **AC-4:** Given svelte-check / When er nach den Edits läuft / Then ist die Error-Anzahl ≤ aktuelle Baseline (23 nach #228) — keine neuen Type-Errors

- **AC-5:** Given `npm run build` / When der Production-Build im Frontend läuft / Then exit 0 — Vite/SvelteKit-Build läuft erfolgreich durch

- **AC-6:** Given die Trip-Edit-Seite im UI / When sie nach dem Deploy aufgerufen wird / Then funktionieren die Buttons (Etappe hinzufügen, Wegpunkt hinzufügen, Manuell anlegen, Entfernen) visuell und funktional analog zum Vorzustand — keine UI-Regression

## Erwartetes Verhalten

### `EditRouteSection.svelte` — Migration

Vorher (Z. 4):
```typescript
import { Button } from '$lib/components/ui/button/index.js';
```

Nachher:
```typescript
import { Btn } from '$lib/components/ui/btn/index.js';
```

Tags-Migration (Z. 193, 200, 226): `<Button ... ` → `<Btn ... `, schließende
Tags `</Button>` → `</Btn>`. Variant-Werte (`"outline"`) bleiben unverändert
— sind in `Btn` vorhanden.

### `EditStagesSection.svelte` — Migration

Vorher (Z. 3):
```typescript
import { Button } from '$lib/components/ui/button/index.js';
```

Nachher:
```typescript
import { Btn } from '$lib/components/ui/btn/index.js';
```

Tags-Migration (Z. 65, 81, 91, 102, 119, 158, 169): 7× `<Button>` → `<Btn>`.
Variant-Werte (`"outline"`, `"ghost"`) und Size-Werte (`"sm"`, `"icon-sm"`)
bleiben unverändert.

### `frontend/src/lib/components/ui/button/` — Löschen

Komplett-Verzeichnis-Löschung via `rm -rf`:
- `frontend/src/lib/components/ui/button/button.svelte`
- `frontend/src/lib/components/ui/button/index.ts`

## Out-of-Scope

- **Btn-Komponente refactorieren** — Btn ist seit #214 stabil.
- **Variants vereinheitlichen** (`primary` vs `default`) — Btn bleibt
  Design-System-konform, kein Touch.
- **Andere UI-Komponenten-Duplikate** — eigene Issues falls vorhanden.
- **Design-System-Doku aktualisieren** — eigener Issue #213.

## Tests / Verifikation

1. **TypeScript:**
   ```bash
   cd frontend && npx svelte-check --output machine 2>&1 | grep -c "ERROR"
   ```
   Erwartung: ≤ 23.

2. **Build:**
   ```bash
   cd frontend && npm run build 2>&1 | tail -10
   ```
   Erwartung: Exit 0, "✓ built" am Ende.

3. **Phantomreferenz-Check:**
   ```bash
   grep -rn "from.*ui/button\|<Button[ />]" frontend/src/ | wc -l
   ```
   Erwartung: 0.

4. **Staging-Manual-Probe:** Nach Deploy auf der Trip-Edit-Seite alle Buttons
   visuell + funktional prüfen (Manuell anlegen, Etappe hinzufügen,
   Wegpunkt hinzufügen, Etappe entfernen, Wegpunkt entfernen).

## Risiken & Migration

- **Risiko gering:** Bereits 16 andere Dateien nutzen `Btn` erfolgreich.
  Btn-API ist Drop-in-Replacement für die in den 2 Dateien verwendeten
  Variants/Sizes.
- **Visuelle Drift möglich:** Btn und Button haben unterschiedliche
  CSS-Classes (Tailwind-bvHF vs Design-System). Auf der Trip-Edit-Seite
  könnten Hover-/Active-Styles sich subtil ändern. Sichtprüfung Pflicht.
- **Keine Backwards-Compat:** Button verschwindet komplett, ist OK weil
  keine Phantomreferenzen.
- **Test-Drift möglich:** Falls `forms-dialogs-btn-migration.spec.ts` o.ä.
  noch alte `Button`-Selektoren prüfen, müssen sie nachgezogen werden.
  Erwartet: 0 Treffer.

# Context: Trips-Liste Redesign (#282 + #295)

## Request Summary

Zwei parallel laufende Issues betreffen denselben Screen (`/trips`):
- **#282**: Visuelle Struktur wiederherstellen — Eyebrow, Status-Dots, Summary-Stats, Mono-Daten
- **#295**: UX-Überarbeitung — 6 Icon-Buttons ersetzen durch 1 Primäraktion + Kebab-Menü, Trip-Name klickbar zur Detail-Seite

Da beide auf `+page.svelte` abzielen, werden sie in einem Workflow zusammengefasst.

## Betroffene Datei

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/trips/+page.svelte` | Hauptdatei, 559 Zeilen — vollständiger Umbau der Desktop-Tabelle + Header |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus()` → liefert `'planned' | 'active' | 'paused' | 'archived'` |
| `frontend/src/lib/types.ts` | `Trip`-Typ mit `paused_at`, `archived_at`, `stages[]` |
| `frontend/src/lib/components/ui/eyebrow/` | Eyebrow-Komponente ✅ vorhanden |
| `frontend/src/lib/components/ui/dot/` | Dot-Komponente ✅ vorhanden (tones: success/warning/danger/info) |
| `frontend/src/app.css` | CSS für `[data-slot="dot"]` und `[data-slot="eyebrow"]` ✅ definiert |

## Vorhandene Komponenten

- **Eyebrow** ✅ `$lib/components/ui/eyebrow` — `data-slot="eyebrow"`, Mono, 0.625rem
- **Dot** ✅ `$lib/components/ui/dot` — tones: success/warning/danger/info, sizes: xs/sm/md
- **Btn** ✅ `$lib/components/ui/btn` — variant: outline/ghost/accent/destructive, size: sm/icon-sm
- **Table** ✅ `$lib/components/ui/table`
- **Dialog** ✅ `$lib/components/ui/dialog`
- **DropdownMenu** ❌ NICHT vorhanden — muss als einfaches natives Popover oder inline implementiert werden

## Kritischer Befund: kein DropdownMenu

Das Kebab-Menü aus #295 setzt `<DropdownMenu>` (shadcn) voraus — diese Komponente existiert NICHT im Projekt. Optionen:
1. **Nativer HTML `<details>`/`<summary>` Popover** — einfach, keine Abhängigkeit
2. **Inline-State-Dropdown** — `showMenu = $state(false)` + absolut-positioniertes `<div>` mit Focusout-Close
3. **DropdownMenu nachinstallieren** (shadcn `bits-ui`) — Aufwand, Risiko für andere Komponenten

**Empfehlung:** Option 2 (Inline-State-Dropdown) — schnell, kontrollierbar, kein Risiko.

## Bestehende TripStatus-Logik

```
deriveTripStatus() → 'planned' | 'active' | 'paused' | 'archived'
```
Issues-Specs nutzen andere Label-Namen (`scheduled`/`completed`/`draft` in #282, `geplant`/`fertig`/`draft` in #295). Die echte Funktion kennt `'planned'`, nicht `'scheduled'` oder `'completed'`. Mapping wird in der Spec geklärt.

## Playwright-Tests (müssen erhalten bleiben)

Aus `trips.spec.ts`:
- `[data-testid="empty-state"]` — bleibt im Empty-State-Block
- `table tbody tr` Selektor — Desktop-Tabelle bleibt, Struktur ändert sich
- Button mit Text "Löschen" — muss im Kebab-Menü erhalten bleiben
- Button mit Text "Neuer Trip" — bleibt im Header-Block

Aus `issue-268-trips-mobile-card-stack.spec.ts`:
- `trip-card-stack`, `trip-card`, `trip-card-menu-btn`, `trip-action-sheet` — Mobile-Bereich UNVERÄNDERT lassen
- Bottom-Sheet mit 6 Aktionen (Report-Konfiguration etc.) — NICHT anfassen

## Was #282 verlangt (Desktop-Header + Tabelle)

1. Eyebrow „WORKSPACE · TOUREN" über H1
2. H1: text-3xl font-semibold tracking-tight
3. Untertitel-Text
4. Summary-Stats-Zeile (Aktiv / Geplant / Abgeschlossen / Drafts) — abgeleitet via `deriveTripStatus()`
5. Status-Dot + Name + Mono-Caption pro Zeile
6. Datumsbereich in Mono + tabular-nums
7. Zebra-Striping alternierend
8. Hairline-Trenner zwischen Edit- und Run-Gruppe (Buttons)
9. Footer „N von M Trips"
10. Search-Input: max-w-[380px], rounded-full

## Was #295 verlangt (Desktop-Tabelle Aktionen)

1. 6 Icon-Buttons RAUS — durch 1 Primärbutton + 1 Kebab-Button ersetzen
2. Trip-Name → klickbarer Link zu `/trips/{id}`
3. Primäraktion kontextabhängig:
   - `active`/`planned` → „Briefing-Vorschau"
   - `paused` → „Reaktivieren" (analog archiviert)
   - `archived` → „Archiviert" (inaktiv oder Dearchivieren)
4. Kebab enthält: Bearbeiten, Test-Briefing (Morgen/Abend), Wetter-Config, Report-Config, Löschen
5. Footer: „N Trips · M versteckt"

## Abhängigkeiten

- **Upstream:** `api.get<Trip[]>('/api/trips')`, `deriveTripStatus()`, `api.post('/api/scheduler/trip-reports')`
- **Downstream:** keine — Seite ist Blatt-Route

## Risiken

1. **trips.spec.ts** — `deleteBtn = firstRow.getByRole('button', { name: 'Löschen' })` sucht einen Button direkt in der Row. Mit Kebab-Menü ist der Löschen-Button erst nach Kebab-Klick sichtbar → Test muss angepasst werden.
2. **issue-268-trips-mobile-card-stack.spec.ts** — Mobile-Bereich darf nicht verändert werden; sorgfältige `desktop:hidden`/`hidden desktop:block` Trennung beibehalten.
3. **Kein DropdownMenu-Primitiv** — Selbstimplementierung nötig.
4. **`deriveTripStatus` kennt kein `'completed'`/`'draft'`** — Issues-Specs beschreiben Status-Labels anders als die echte Funktion → Mapping nötig.

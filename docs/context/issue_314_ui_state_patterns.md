# Context: Issue #314 — UI-Zustandsmuster vereinheitlichen

## Request Summary
Eine gemeinsame `EmptyState.svelte`-Komponente anlegen, alle Seiten, die leere Listen zeigen, auf diese migrieren sowie bestehende inkonsistente Fehler-/Lade-Muster angleichen. Die Verhaltens-Regeln stehen bereits in `sveltekit_best_practices.md`; jetzt kommt die Implementierung.

## Was bereits erledigt ist

### AC-1 — Dokumentation (`sveltekit_best_practices.md`)
Der Abschnitt "UI State Patterns" (ab Zeile 339) existiert bereits und ist vollständig:
- Form-Feld-Fehler: `aria-invalid` + roter Text darunter
- Lade-Seite: Skeleton-Blöcke (`animate-pulse`)
- Lade-Button: Button deaktiviert + `Loader2`-Icon
- Leer-Zustand: `EmptyState` via Shared-Primitive
- API-Fehler: immer sichtbar, inline oder Toast

AC-1 ist **bereits erfüllt**.

## Was noch fehlt

### AC-2 — `EmptyState.svelte` als Primitive + Migration

`EmptyState.svelte` existiert **nirgends** im Frontend (kein `ui/`, kein `atoms/`, kein `molecules/`).

Seiten mit inline Empty States (müssen migriert werden):

| Seite | Datei | Aktueller Zustand |
|-------|-------|-------------------|
| Trips | `routes/trips/+page.svelte` | `data-testid="empty-state"` inline-Block mit RouteIcon |
| Locations | `routes/locations/+page.svelte` | `data-testid="empty-state"` inline-Block mit MapPinIcon |
| Home | `routes/+page.svelte` | `EmptyKachel.svelte` (eigene Komponente, kein Shared-Primitive) |

Seiten ohne Empty State (müssen ergänzt werden):

| Seite | Datei | Was fehlt |
|-------|-------|-----------|
| Compare | `routes/compare/+page.svelte` | Kein empty-state bei `locations.length === 0` — zeigt nur `AutoReportsOverview` |

### AC-3 — API-Fehler immer sichtbar

Die meisten Seiten handhaben Fehler bereits korrekt via `let error = $state()` + inline Text. **Ausnahme:**

- `routes/account/+page.svelte`: Zeile 57 + 200 nutzen `window.confirm()` (native Browser-Dialog, kein Design-System). Diese sollen auf `Dialog.Root` aus dem bestehenden UI-Kit umgestellt werden — wird in dieser Issue aber **nur** für den Metric-Preset-Lösch-Dialog relevant (window.confirm bei deletePreset), da der andere confirm (Zeile 200) für Account-Löschung ist und ein Delete-Confirmation-Dialog mit Dialogs.Root bereits auf /trips existiert als Pattern.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/atoms/index.ts` | Atoms-Barrel — hier wird `EmptyState` NICHT exportiert (Entscheidung: molecules-Ebene) |
| `frontend/src/lib/components/molecules/index.ts` | Molecules-Barrel — hier wird `EmptyState` exportiert (analog zu `Field`) |
| `frontend/src/lib/components/molecules/Field.svelte` | Referenz-Implementierung für Molecules-Pattern + error/hint-Slot |
| `frontend/src/lib/components/mobile/Toast.svelte` | Existierender Toast (mobile-only) — kein Scope für #314 |
| `frontend/src/routes/_home/EmptyKachel.svelte` | Prototype-Empty-State (Home-Seite) — wird durch Shared-Primitive abgelöst |
| `frontend/src/routes/trips/+page.svelte` | Migration: inline empty-state → `<EmptyState>` |
| `frontend/src/routes/locations/+page.svelte` | Migration: inline empty-state → `<EmptyState>` |
| `frontend/src/routes/compare/+page.svelte` | Ergänzung: kein empty-state bei 0 Locations |
| `frontend/src/routes/account/+page.svelte` | window.confirm() → Dialog.Root (nur deletePreset) |
| `docs/reference/sveltekit_best_practices.md` | Verhaltens-Vertrag (bereits vollständig, kein Änderungsbedarf) |

## Existing Patterns

- **Molecules-Pattern:** `Field.svelte` zeigt wie ein Molecule gebaut wird (Props-Interface, Svelte 5 Runes, kein Test-File nötig für reine UI-Primitive)
- **Empty-State-Struktur:** Einheitlich `icon + title + description + optionaler CTA-Slot`
- **Skeleton-Loading:** Schon vorhanden in trips + locations: `{#each Array(3) as _}<div class="h-12 w-full animate-pulse rounded-lg bg-muted">` — kein Änderungsbedarf
- **Error-Pattern:** `let error: string | null = $state(null)` + `{#if error}<p role="alert" ...>{error}</p>` — bereits überall konsistent
- **Dialog-Pattern:** `Dialog.Root` aus `$lib/components/ui/dialog` — Pattern für Bestätigungs-Dialoge bereits vorhanden (`/trips` Delete-Dialog)
- **Icon-Nutzung:** WIcon / Lucide-Icons direkt (`MapPinIcon`, `RouteIcon` aus `@lucide/svelte/icons/...`)

## Dependencies

- **Upstream:** `$lib/components/ui/btn` (CTA-Button im EmptyState), `$lib/types` (keine neuen Typen nötig)
- **Downstream:** `/trips`, `/locations`, `/compare`, `/+page` (Home) nach Migration

## Risks & Considerations

- **EmptyKachel bleibt (Home):** Die Home-Seite zeigt kein echtes "leeres Listenzustand" — sie ist die Willkommens-Seite wenn noch keine Trips vorhanden sind, mit 2 CTAs. EmptyKachel kann auf EmptyState migriert werden, da die Struktur übereinstimmt (2 CTAs = children-Slot).
- **window.confirm-Scope:** Issue sagt "API-Fehler sichtbar" — window.confirm ist kein API-Fehler, sondern Bestätigung. Trotzdem sollte deletePreset (Metric-Preset) auf Dialog.Root migriert werden weil es das einzige window.confirm ist das tatsächlich aus einem catch heraus Fehler anzeigt (über presetError). Account-Lösch-confirm (Zeile 200) ist separates Thema.
- **Kein Toast-Scope:** Der globale Desktop-Toast aus `#312` ist noch nicht implementiert. Das ist explizit außerhalb von #314 (Scope note in sveltekit_best_practices.md). API-Fehler bleiben inline.
- **EmptyState-Ort:** molecules-Ebene (nicht atoms), weil sie aus mehreren Atom-Bausteinen besteht (Btn, WIcon, Text). Consistent mit Field.svelte-Ebene.

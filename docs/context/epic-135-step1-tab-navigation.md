# Context: Issue #155 — Trip-Übersicht: Tab-Navigation

## Request Summary

Erstes Sub-Issue von Epic #135 (Trip-Übersicht). Tab-Navigation mit 6 Tabs (Übersicht / Etappen & Wegpunkte / Wetter-Metriken / Briefing-Zeitplan / Alerts / Vorschau), aktive Unterstreichung in `var(--g-accent)`, Badge-Slots für Alerts-Tab + Metriken-Tab. Da Epic #135 noch keine Trip-Detail-Route hat, müssen wir auch das Wrapper-Setup (`/trips/[id]/+page.svelte` + `+page.server.ts`) als Skelett anlegen — die Tab-Inhalte werden in späteren Sub-Issues #153, #154, #156, #157, #158, #159 inkrementell gefüllt.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/trips/[id]/+page.svelte` | **NEU.** Wrapper-Container, in den die `TripTabs`-Komponente eingehängt wird. |
| `frontend/src/routes/trips/[id]/+page.server.ts` | **NEU.** Trip-Daten via `/api/trips/${id}` laden, 404 bei nicht-gefunden. Pattern existiert 1:1 in `[id]/edit/+page.server.ts`. |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | **NEU.** Tab-Komponente mit 6 Tabs, aktiver Unterstreichung, Badge-Slots. |
| `frontend/src/lib/components/trip-detail/index.ts` | **NEU.** Barrel-Export. |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | Vorbild für Server-Loader. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (Z. 294-298) | Enthält den `TODO(epic-135)`-Marker — nach Abschluss von Epic #135 wird der Fallback `goto('/trips')` durch `goto(/trips/${created.id})` ersetzt. **Nicht in #155 anfassen** — kommt mit dem letzten Sub-Issue. |
| `frontend/src/app.css:33` | Definiert `--g-accent: #c45a2a` — für aktive Tab-Unterstreichung. |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Stil-Vorbild für Monospace-Eyebrows in der Trip-Detail-Bühne (kommt in Sub-Issues). |

## Existing Patterns

- **Server-Loader-Pattern:** `+page.server.ts` lädt Daten via Backend-API mit Session-Cookie (siehe `[id]/edit/+page.server.ts`). Wirft `error(404)` bei `!res.ok`.
- **Svelte-5-Runen für Komponenten:** Props via `$props()`, Reaktivität über `$state`, `$derived`. Vorbild: `EmailPreviewHeader.svelte` (Issue #183).
- **Design-Token-Klassen:** Statt fester Farben werden `var(--g-accent)` etc. genutzt — direkt in `class=`-Attributen via `style=`-Inline oder per Tailwind-Custom-Properties.
- **Test-Pattern:** Playwright-E2E gegen Dev-Server (`localhost:4173`), Auth via `playwright/.auth/admin.json` Storage-State.
- **Tab-Komponente existiert NICHT** — `frontend/src/lib/components/ui/` hat keine `tabs/`. Wir bauen sie als domänen-spezifische Komponente unter `trip-detail/TripTabs.svelte` (nicht generisch — Epic #135 ist der einzige Konsument).

## Dependencies

- **Upstream:**
  - Backend `/api/trips/{id}` — bestehender Endpoint, liefert Trip-JSON oder 404
  - `Trip`-Type aus `frontend/src/lib/types.ts`
  - `--g-accent`-Token aus `app.css`
- **Downstream (was später hier andocken wird):**
  - Sub-Issue #153 (Breadcrumb + Status-Badge) — über den Tabs
  - Sub-Issue #154 (Hero + Stats) — über den Tabs
  - Sub-Issue #156 (Höhenprofil) — unter den Tabs, im aktiven Tab-Panel "Übersicht"
  - Sub-Issue #157 (Stage-Row-Liste) — im Tab "Etappen & Wegpunkte"
  - Sub-Issue #158 (Wetter-Metriken Vorschau) — im Tab "Wetter-Metriken"
  - Sub-Issue #159 (Briefings/Alerts/Vorschau-Cards rechte Spalte) — im Layout
  - Epic #136 / Issue #197 Workaround (Wizard-Save → `/trips` Fallback) — entfällt sobald Epic #135 stabil ist (markiert per `TODO(epic-135)`)

## Existing Specs

- **Master-Spec für Epic #135 existiert NICHT.** Sub-Issues sind aktuell ungespecet. Pragmatisch für #155: keine separate Master-Spec; die Sub-Spec `epic_135_step1_tab_navigation.md` reicht. Wenn die Reihe wächst, kann später eine Master-Spec angelegt werden (analog zu `epic_136_trip_wizard.md`).
- **Relevant außerhalb:** `docs/specs/bugfix/wizard_save_redirect_fallback.md` — beschreibt den #197-Workaround, der nach Epic #135 entfernt werden kann.

## Risks & Considerations

1. **Tab-Inhalte sind Placeholder:** Bis die Sub-Issues #153–#159 implementiert sind, zeigt jedes Tab nur einen Placeholder wie `"Inhalt folgt mit Issue #154"`. Tech-Lead-Entscheidung: bewusst, damit man UI inkrementell sieht, statt am Stück.

2. **URL-Fragment vs. Query-Param vs. Sub-Route?** Drei Wege, den aktiven Tab persistent in der URL zu halten:
   - **Hash-Fragment** (`/trips/abc#stages`) — kein Server-Round-Trip, einfach mit `$page.url.hash`
   - **Query-Param** (`/trips/abc?tab=stages`) — server-side lesbar, aber redundant
   - **Sub-Route** (`/trips/abc/stages`) — SvelteKit-idiomatisch, aber 6 zusätzliche Routen-Verzeichnisse nötig
   
   Pragmatische Empfehlung für #155: **Hash-Fragment**. Klein, schnell, leicht zu testen. Sub-Route-Refactor falls später nötig — Aufwand vorhersehbar.

3. **Badge-Zähler-Quellen fehlen:** Alerts-Tab und Metriken-Tab sollen Zähler-Badges zeigen. API-Endpoints für `active_alerts_count` und `metrics_count` existieren noch nicht. **Pragmatisch:** Komponenten-Prop `badgeCount?: number` — wenn nicht gesetzt, kein Badge. Mock-Daten in der Wrapper-Route bis die Endpoints kommen. Folge-Issue (vermutlich #159) bringt die echten Werte.

4. **#197-Workaround:** Sobald Epic #135 vollständig deployt ist, kann der `goto('/trips')` zurück auf `goto(/trips/${created.id})`. Dieser Cleanup ist NICHT in #155 — sondern wenn das letzte Sub-Issue durch ist. Markiert per `TODO(epic-135)` in `wizardState.svelte.ts:294-297`.

5. **Skelett-Inhalt sichtbar machen:** Tab-Navigation alleine ist nicht sehr aussagekräftig — User sieht 6 Tabs mit leerem Panel. Für Testbarkeit + visuelle Verifikation: jedes Panel rendert seinen Titel + 1-Zeilen-Placeholder mit Issue-Verweis. Macht Fortschritt sichtbar.

6. **Test-Auth:** `/trips/[id]` ist eine geschützte Route (Login-Pflicht über `hooks.server.ts`). Playwright-Test braucht den existierenden Auth-Setup (`global.setup.ts`). Plus: Test braucht einen Trip in den Test-Daten (existierender Pattern: `e2e-cockpit-test`-Trip aus `global.setup.ts`).

7. **6 Tab-Labels — exakter Wortlaut:** Aus Epic #135-Body: `Übersicht / Etappen & Wegpunkte / Wetter-Metriken / Briefing-Zeitplan / Alerts / Vorschau`. Diese Labels sind verbindlich für Spec-AC.

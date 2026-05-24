# Context: Issue #344 — Wetter-Profile-Karte auf /account

## Request Summary

Neue Card **„Wetter-Profile"** auf `/account` (zwischen „Passwort ändern" und „System-Status"),
die die gespeicherten **User-MetricPresets** auflistet, inline umbenennen (PATCH) und löschen
(DELETE, mit Confirm) lässt, plus Leeren-Zustand. Sub-Issue 3 von Epic #304.

## Status der Abhängigkeiten

- **#342** (PATCH-Endpoint + Datenmodell): **CLOSED** ✅ — Blocker aufgelöst.
- **#343** (HorizonChip-UI im Editor): **CLOSED** ✅.
- **#304** (Parent-Epic): OPEN — bleibt nach #344 noch offen für restliche AC (Horizon-Pills etc.).

## Einordnung: reines Frontend-Feature

Alle benötigten Backend-Endpoints **existieren bereits** und sind vollständig
(`internal/handler/metric_preset.go`):

| Methode | Route | Handler | Verhalten |
|---------|-------|---------|-----------|
| GET | `/api/metric-presets` | `ListMetricPresetsHandler` | liefert `[]MetricPreset` |
| POST | `/api/metric-presets` | `CreateMetricPresetHandler` | 201 + Preset |
| PATCH | `/api/metric-presets/{id}` | `PatchMetricPresetHandler` | Read-Modify-Write, 200 + Preset (Name optional) |
| DELETE | `/api/metric-presets/{id}` | `DeleteMetricPresetHandler` | 204, 404 wenn nicht gefunden |

→ **Kein Go-Code nötig.** Die Arbeit liegt komplett in SvelteKit.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/account/+page.svelte` | **Hauptarbeit:** neue Card einfügen (zwischen Card „Passwort ändern" Z.314–368 und `<div id="system-status">` Z.370). Bestehende read-only Card „Wetter-Templates" (Z.500–524) bleibt unverändert darunter. |
| `frontend/src/routes/account/+page.server.ts` | Server-Load erweitern: zusätzlicher `fetch('/api/metric-presets')` neben den 7 bestehenden Promise.all-Calls. |
| `frontend/src/lib/types.ts` | `MetricPreset { id, name, description?, is_default, metrics[], created_at }` (Z.172–179) — **vorhanden**, keine Änderung nötig. Metrik-Anzahl = `metrics.length`. |
| `frontend/src/lib/api.ts` | API-Client hat bereits `patch()` (Z.24) und `del()` (Z.25) — direkt nutzbar. |
| `internal/handler/metric_preset.go` | Backend-Referenz (read-only für uns); PATCH akzeptiert optionalen `name`. |
| `internal/model/metric_preset.go` | `MetricPreset`-Struct + `DisplayMetric` — read-only Referenz. |

## Existing Patterns

- **Account-Karten-Stil:** Die `/account`-Seite nutzt **shadcn-Card** (`Card.Root/Header/Title/Content/Description`),
  `Badge` und **Tailwind-Utility-Klassen** — NICHT die `--g-*`-Brand-Tokens. Buttons sind dort
  `bg-primary`/`bg-red-600` etc. Die bestehende „Wetter-Templates"-Card ist die direkte Stil-Vorlage
  (Name links, `<Badge variant="secondary">{n} Metriken</Badge>` rechts).
- **Preset-Listenzeile (Brand-Token-Variante):** `frontend/src/lib/components/trip-detail/PresetRow.svelte`
  — zeigt Name + „{n} Metriken" + „Standard"-Badge, aber als Auswahl-Button (`onSelect`), nicht zum
  Bearbeiten/Löschen. Pattern-Referenz, nicht 1:1 wiederverwendbar.
- **Preset-API-Nutzung:** `SavePresetDialog.svelte` zeigt `api.post('/api/metric-presets', …)` (client-seitig,
  relativer Pfad, Proxy funktioniert bereits). Analog: `api.patch('/api/metric-presets/'+id, {name})` und
  `api.del('/api/metric-presets/'+id)`.
- **Confirm-Dialog:** `+page.svelte::deleteAccount()` (Z.152) nutzt `window.confirm(...)` — etabliertes
  Pattern auf genau dieser Seite. (Alternativ shadcn-Dialog wie SavePresetDialog.)
- **Inline-Edit + Esc/Enter:** Im Repo noch nicht als wiederverwendbare Komponente vorhanden — neu zu bauen
  (Input mit `onkeydown` für Enter=speichern / Escape=abbrechen).

## Dependencies

- **Upstream (was wir nutzen):** Go-API `/api/metric-presets` (GET/PATCH/DELETE), `api.ts`-Client,
  shadcn `Card`/`Badge`, `MetricPreset`-Typ.
- **Downstream (was uns nutzt):** Nichts — die Card ist additiv auf einer Endbenutzer-Seite.

## Existing Specs

- `docs/specs/modules/epic_138_174_178_metriken_ui.md` — User-Preset-Endpoints (GET/POST/DELETE), §7.
- `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md` — PATCH-Endpoint + Schema (§4–§5).
- `docs/specs/modules/issue_343_horizon_chip_ui.md` — HorizonChip-UI im Editor.
- **Neu anzulegen:** `docs/specs/modules/issue_344_wetter_profile_account.md` (Phase 3) — mit AC-N-Format.

## Risks & Considerations

1. **Stil-Konflikt (wichtig):** Das Issue verlangt „Brand-Token-Styling konsistent mit anderen
   Account-Karten" — aber die anderen Account-Karten nutzen shadcn/Tailwind, NICHT die `--g-*`-Tokens.
   Diese zwei Anforderungen widersprechen sich. Vorab in Phase 2/3 klären: konsequent dem
   **bestehenden Account-Seiten-Stil** (shadcn-Card + Badge) folgen für visuelle Konsistenz auf der
   Seite — sonst sticht eine einzelne Brand-Token-Card heraus. Design-System (`docs/design-system/`)
   gegenchecken.
2. **Default-Badge-Semantik:** `is_default` markiert genau ein Preset als Standard. Badge nur bei
   `is_default === true` anzeigen (Wording: „Standard", konsistent mit PresetRow).
3. **Reaktivität nach Mutation:** Nach PATCH/DELETE muss die client-seitige Liste aktualisiert werden
   (lokale `$state`-Kopie der `data.presets` halten, nicht nur Server-Daten — die werden nur beim
   Load/Reload neu geholt).
4. **Inline-Rename-Edge-Cases:** Leerer Name nach Trim → Speichern blockieren oder alten Namen behalten;
   Esc verwirft; Enter speichert; währenddessen Lade-/Fehlerzustand.
5. **KEINE Mocked Tests:** E2E gegen Staging (Playwright/visuell, frontend-only Scope → keine Mail nötig).
   Backend ist unverändert, daher kein pytest-Bedarf; ggf. Svelte-Komponententest für Inline-Edit-Logik.
6. **Datensicherheit:** Reines additives Frontend, keine Persistenz-Schema-Änderung → `data_schema_backup`
   nicht relevant.

---

## Analyse (Phase 2)

### Datenfluss (verifiziert)

```
Browser fetch('/api/metric-presets/{id}')  [relativer Pfad, Cookie gz_session automatisch]
  → Vite-Proxy (frontend/vite.config.ts:8–12, target localhost:8090)
  → chi-Router (cmd/server/main.go:133–137: Get/Post/Patch/Delete registriert)
  → AuthMiddleware (cmd/server/main.go:60 — gz_session validiert, UserID in Context)
  → Handler (internal/handler/metric_preset.go) → Store (per-User gescoped)
```
PATCH/DELETE brauchen **keine** Sonder-Header — Cookie reicht. Client-Pattern existiert bereits
(`SavePresetDialog.svelte` nutzt `api.post('/api/metric-presets', …)`).

### Wiederverwendbare Muster (mit file:line)

| Bedarf | Vorbild | Übernahme |
|--------|---------|-----------|
| Inline-Edit State-Toggle | `alert-rules-editor/AlertRuleRow.svelte:40,76–119` (`editing = $state`, `startEdit/cancelEdit/saveEdit`) | Pattern, angepasst auf `editingId: string\|null` + `editName` |
| Enter/Escape-Tastatur | `trip-detail/waypoints/ProfileEditor.svelte:85–89` | `onkeydown` Enter=speichern / Escape=abbrechen |
| Löschen mit Confirm | `routes/account/+page.svelte:153` (`window.confirm`) — **seiten-eigenes** Pattern (deleteAccount) | `window.confirm` → minimal & seiten-konsistent. (Alt.: `Dialog.Root` wie `routes/locations/+page.svelte:205–221`) |
| Lucide-Icons | `routes/locations/+page.svelte:14–15` (`@lucide/svelte/icons/pencil`, `…/trash-2`) | Pencil/Trash2/Check/X |
| Badge | `ui/badge/badge.svelte` (variants: default/secondary/destructive/outline/ghost/link) | `variant="secondary"` für „Standard"-Badge (wie Wetter-Templates-Card) |

### Backend-Endpoints (verifiziert vollständig + getestet)

`cmd/server/main.go:133–137` registriert alle vier Routen unter `AuthMiddleware`.
`internal/handler/metric_preset_test.go` deckt u.a. ab: `TestPatchMetricPreset_NameOnly` (PATCH
nur Name, Rest unverändert), `TestDeleteMetricPreset_Success/_NotFound`. **Kein Backend-Bedarf.**
Bestehende E2E: `frontend/e2e/epic-138-block-b.spec.ts:287–361` (AC-6a..AC-7) testet GET/POST/Default —
Referenz für neue E2E-Tests; Seeding erfolgt dynamisch via `request.post/patch/delete`, kein Fixture nötig.

### Stil-Entscheidung (Tech-Lead-Call zum Phase-1-Risiko)

Die scheinbar widersprüchlichen Vorgaben („Brand-Token-Styling" vs. „konsistent mit anderen
Account-Karten") lösen sich so auf: **Primärziel ist die visuelle Einheit der Seite.** Die
Nachbar-Karten laufen auf shadcn-`Card.Root` + Tailwind; die ganze `/account`-Seite auf Brand-Tokens
zu migrieren ist **out of scope** für #344 (würde alle Karten anfassen, Risiko + LoC sprengen).

→ **Entscheidung:** Äußerer Container = shadcn-`Card.Root`/`Card.Header`/`Card.Content` + `Badge`
(wie die „Wetter-Templates"-Karte direkt darunter, Z.500–524), damit sich die neue Karte nahtlos
einfügt. Innen die Design-System-Prinzipien, die NICHT mit den Nachbarn kollidieren: **keine Emojis**
(`no_emoji`), **Inline-Edit statt Modal** (CHARTER Z.98), **Lucide-Icons** für Pencil/Trash.
Eine spätere Voll-Migration der Account-Seite auf Brand-Tokens ist ein separates Issue.

### Scope

| Datei | Änderung | ~LoC |
|-------|----------|------|
| `frontend/src/routes/account/+page.server.ts` | +1 fetch `/api/metric-presets` in `Promise.all`, `metricPresets` ins Return | ~6 |
| `frontend/src/routes/account/+page.svelte` | Neue „Wetter-Profile"-Card zwischen Z.368 und Z.370; lokale `$state`-Kopie der Presets; `startEdit/cancelEdit/saveRename` (PATCH) + `deletePreset` (DELETE+confirm); Leerer-Zustand; Lucide-Imports | ~120 |
| **Summe** | **2 Dateien** | **~126** ✅ unter 250 |

E2E: 1 Playwright-Spec (frontend-only, keine Mail) als Test-Artefakt in Phase 5.

### Offene Detail-Entscheidungen (selbst getroffen, kein User-Blocker)

- **Listen-Reihenfolge:** Speicher-Reihenfolge (`created_at` aufsteigend wie geliefert); Default trägt Badge.
- **Default-Badge:** nur bei `is_default === true` (NICHT wie PresetRow unbedingt).
- **Leerer Name beim Rename:** Speichern blockieren (kein PATCH), Edit bleibt offen.

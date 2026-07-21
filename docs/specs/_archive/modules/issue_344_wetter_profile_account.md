---
entity_id: issue_344_wetter_profile_account
type: module
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [frontend, account, weather, ui, svelte, metric-presets]
parent_epic: 304
predecessor: 342
---

<!-- Issue #344 — Wetter-Profile-Karte auf /account (Sub-Issue 3 von Klammer-Epic #304) -->

# Issue #344 — Wetter-Profile-Karte auf /account

## Approval

- [ ] Approved

## Purpose

Ergänzt die Konto-Seite (`/account`) um eine neue Karte **„Wetter-Profile"**, die die
server-seitig gespeicherten User-`MetricPreset`s auflistet und verwaltet: pro Eintrag Name,
Metrik-Anzahl und (falls gesetzt) eine „Standard"-Markierung; Inline-Umbenennen per Bleistift
(PATCH) und Löschen mit Sicherheitsabfrage (DELETE). Ohne diese Karte können Profile zwar im
Wetter-Editor gespeichert (#343), aber nirgends zentral umbenannt oder gelöscht werden.

## Scope

### In Scope

- Neue Karte „Wetter-Profile" in `frontend/src/routes/account/+page.svelte`, platziert **zwischen**
  der Karte „Passwort ändern" und dem Block `<div id="system-status">`.
- Server-Load `frontend/src/routes/account/+page.server.ts`: zusätzlicher `fetch('/api/metric-presets')`
  im bestehenden `Promise.all`, Ergebnis als `metricPresets` im Return (Fallback `[]`).
- **Auflisten:** pro Preset Name, „{n} Metriken" (`metrics.length`), `Badge variant="secondary"` „Standard"
  nur wenn `is_default === true`.
- **Inline-Umbenennen:** Bleistift-Icon (`@lucide/svelte/icons/pencil`) startet Inline-Edit-Modus
  (lokaler State `editingId`/`editName`); `Enter` speichert via `api.patch('/api/metric-presets/'+id, {name})`,
  `Escape` bricht ab; Check-/X-Icons als Maus-Alternative.
- **Löschen:** Papierkorb-Icon (`@lucide/svelte/icons/trash-2`) → `window.confirm(...)` (seiten-eigenes
  Pattern wie `deleteAccount`) → `api.del('/api/metric-presets/'+id)`; bei Erfolg aus lokaler Liste entfernen.
- **Leerer Zustand:** Text „Du hast noch keine Wetter-Profile angelegt. Speichere ein Profil im
  Trip-Wetter-Tab." wenn keine Presets vorhanden.
- Lokale `$state`-Kopie der Presets, damit Liste nach PATCH/DELETE ohne Page-Reload aktualisiert.
- Bestehende read-only Karte „Wetter-Templates" (Builtins) bleibt **unverändert** darunter sichtbar.
- Playwright-E2E-Test `issue-344-wetter-profile.spec.ts` (Liste, Rename-Roundtrip, Delete, Leerer Zustand).

### Out of Scope

- Backend-Änderungen — GET/POST/PATCH/DELETE `/api/metric-presets` sind aus **#342** fertig, getestet
  und live (`cmd/server/main.go:133–137`, `internal/handler/metric_preset.go`).
- Default-Setzen aus der Karte (`is_default` umschalten) — Issue nennt nur Auflisten/Umbenennen/Löschen.
  Die „Standard"-Markierung wird nur **angezeigt**.
- Metrik-Inhalte eines Presets bearbeiten — das geschieht im Wetter-Editor (#343), nicht auf /account.
- Voll-Migration der `/account`-Seite auf Brand-Tokens (`--g-*`) — separates Design-Issue. Die neue Karte
  übernimmt bewusst den shadcn-`Card`-Stil der Nachbar-Karten zur visuellen Einheit.
- Neuanlage von Presets auf /account (passiert via `SavePresetDialog` im Editor).

## Source

- **File:** `frontend/src/lib/utils/presetCardHelpers.ts` (NEU — **Pure-Logik**, testbar via `node:test`)
- **File:** `frontend/src/lib/utils/presetCardHelpers.test.ts` (NEU — `node --experimental-strip-types --test`)
- **File:** `frontend/src/routes/account/+page.svelte` (modifiziert — neue Karte als **dünner Wrapper** + Edit/Delete-Verdrahtung)
- **File:** `frontend/src/routes/account/+page.server.ts` (modifiziert — `metricPresets`-Load)
- **File:** `frontend/e2e/issue-344-wetter-profile.spec.ts` (NEU — Playwright-E2E)
- **Identifier:** Pure-Funktionen `metricCountLabel`, `showDefaultBadge`, `isValidRename`,
  `applyRename`, `removePreset`, `isEmpty` (in `presetCardHelpers.ts`); Wrapper-Handler `startEdit`,
  `cancelEdit`, `saveRename`, `deletePreset` (in `+page.svelte`)

> **Test-Architektur (Repo-Konvention):** Das Test-Setup (`node --experimental-strip-types --test`)
> kann weder `.svelte` noch SvelteKit-Aliase (`$lib`, `$app`) laden. Deshalb liegt die testbare
> Logik (Label, Badge-Bedingung, Rename-Guard, Listen-Mutation, Leerer-Zustand) in
> `presetCardHelpers.ts`; `+page.svelte` verdrahtet sie nur. Den vollen UI-Fluss prüft die
> Playwright-Spec post-push gegen Remote-Staging (`/e2e-verify`).

> **Schicht-Hinweis:** Diese Spec betrifft **ausschließlich** die Frontend-Schicht (SvelteKit unter
> `frontend/src/`). Die Go-API (`/api/metric-presets` GET/PATCH/DELETE) ist aus #342 live und wird
> NICHT angefasst. Client-seitige Calls laufen über den Vite-Proxy (`frontend/vite.config.ts:8–12`)
> auf Port 8090; die Session geht automatisch per `gz_session`-Cookie mit.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/metric-presets` | Go-API (#342) | Liste der User-Presets laden (Server-Load) |
| `PATCH /api/metric-presets/{id}` | Go-API (#342) | Umbenennen (Read-Modify-Write, nur `name`) |
| `DELETE /api/metric-presets/{id}` | Go-API (#342) | Preset löschen (204; 404 wenn nicht gefunden) |
| `api.ts` (`patch`, `del`, `get`) | Frontend-Client | HTTP-Wrapper, bereits vorhanden |
| `MetricPreset` (types.ts) | TS-Type | `{id, name, description?, is_default, metrics[], created_at}` |
| `$lib/components/ui/card` | shadcn-Wrapper | `Card.Root/Header/Title/Content` — Stil der Nachbar-Karten |
| `$lib/components/ui/badge` | shadcn-Wrapper | „Standard"-Badge (`variant="secondary"`) |
| `@lucide/svelte/icons` | Icon-Lib | `pencil`, `trash-2`, `check`, `x` |

## Implementation Details

**`+page.server.ts`** — `/api/metric-presets` zum bestehenden `Promise.all` hinzufügen:

```ts
const [profile, scheduler, health, apiTemplates, trips, subscriptions, locations, presets] =
  await Promise.all([
    /* … bestehende 7 fetches … */,
    fetch(`${API()}/api/metric-presets`, h).then(r => r.ok ? r.json() : []).catch(() => []),
  ]);
const metricPresets = Array.isArray(presets) ? presets : [];
return { /* … */, metricPresets };
```

**`+page.svelte`** — State + Handler (Enter/Escape-Tastatur-Pattern aus AlertRuleRow/ProfileEditor):

```ts
import PencilIcon from '@lucide/svelte/icons/pencil';
import Trash2Icon from '@lucide/svelte/icons/trash-2';
import CheckIcon from '@lucide/svelte/icons/check';
import XIcon from '@lucide/svelte/icons/x';
import type { MetricPreset } from '$lib/types';

let presets = $state<MetricPreset[]>(data.metricPresets ?? []);
let editingId = $state<string | null>(null);
let editName = $state('');
let presetError = $state<string | null>(null);

function startEdit(p: MetricPreset) { editingId = p.id; editName = p.name; presetError = null; }
function cancelEdit() { editingId = null; editName = ''; }

async function saveRename(id: string) {
  const name = editName.trim();
  if (name === '') return;               // leerer Name → kein PATCH, Edit bleibt offen
  try {
    const updated = await api.patch<MetricPreset>(`/api/metric-presets/${id}`, { name });
    presets = presets.map(p => p.id === id ? updated : p);
    editingId = null;
  } catch (e) { presetError = (e as { error?: string })?.error ?? 'Umbenennen fehlgeschlagen'; }
}

async function deletePreset(p: MetricPreset) {
  if (!window.confirm(`Profil „${p.name}" wirklich löschen?`)) return;
  try {
    await api.del(`/api/metric-presets/${p.id}`);
    presets = presets.filter(x => x.id !== p.id);
  } catch (e) { presetError = (e as { error?: string })?.error ?? 'Löschen fehlgeschlagen'; }
}
```

Markup: `Card.Root` (wie Nachbar-Karten); pro Preset eine `flex items-center justify-between`-Zeile;
im Edit-Modus `<input bind:value={editName} onkeydown={…}>` mit Enter=`saveRename`/Escape=`cancelEdit`;
sonst Name + `{n} Metriken` + „Standard"-Badge + Pencil/Trash-Buttons. Keine Emojis (Charter `no_emoji`).

## Expected Behavior

- **Input:** Server-geladene `metricPresets` (Array); User-Interaktion (Klick Bleistift/Papierkorb,
  Texteingabe, Enter/Escape).
- **Output:** Gerenderte Karte „Wetter-Profile"; PATCH-/DELETE-Requests an die Go-API; aktualisierte
  lokale Liste ohne Page-Reload.
- **Side effects:** Persistente Änderung der `metric_presets.json` des Users server-seitig (durch #342-Handler).

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter User mit zwei gespeicherten MetricPresets / When `/account` geladen wird /
  Then erscheinen beide Presets in der Karte „Wetter-Profile" mit ihrem Namen und der korrekten
  Metrik-Anzahl („{n} Metriken").
  - Test: `presetCardHelpers.test.ts::AC-1 metricCountLabel` (Label) + `issue-344-wetter-profile.spec.ts::AC-1` (E2E, post-push)

- **AC-2:** Given ein Preset mit `is_default === true` und eines mit `is_default === false` / When die Karte
  gerendert wird / Then trägt nur das Default-Preset die „Standard"-Markierung, das andere keine.
  - Test: `presetCardHelpers.test.ts::AC-2 showDefaultBadge` + `issue-344-wetter-profile.spec.ts::AC-2` (E2E, post-push)

- **AC-3:** Given ich klicke das Bleistift-Icon eines Presets, gebe einen neuen Namen ein und drücke Enter /
  When der PATCH `/api/metric-presets/{id}` erfolgreich ist / Then wird der neue Name gespeichert und in
  der Liste sofort ohne Page-Reload angezeigt.
  - Test: `presetCardHelpers.test.ts::AC-3 isValidRename/applyRename` + `issue-344-wetter-profile.spec.ts::AC-3` (E2E, post-push)

- **AC-4:** Given ich bin im Inline-Edit-Modus eines Presets / When ich Escape drücke / Then wird die
  Bearbeitung verworfen und der ursprüngliche Name bleibt unverändert (kein PATCH gesendet).
  - Test: `presetCardHelpers.test.ts::AC-4 isValidRename (leer/whitespace)` + `issue-344-wetter-profile.spec.ts::AC-4` (E2E, post-push)

- **AC-5:** Given ich klicke das Papierkorb-Icon und bestätige die Sicherheitsabfrage / When der DELETE
  `/api/metric-presets/{id}` erfolgreich ist / Then verschwindet das Preset aus der Liste; bei Abbruch
  der Abfrage bleibt es erhalten und es wird kein DELETE gesendet.
  - Test: `presetCardHelpers.test.ts::AC-5 removePreset` + `issue-344-wetter-profile.spec.ts::AC-5 + AC-5b` (E2E, post-push)

- **AC-6:** Given ein eingeloggter User ohne gespeicherte Presets / When `/account` geladen wird / Then zeigt
  die Karte „Wetter-Profile" den Leeren-Zustand-Text „Du hast noch keine Wetter-Profile angelegt.
  Speichere ein Profil im Trip-Wetter-Tab.".
  - Test: `presetCardHelpers.test.ts::AC-6 isEmpty`

- **AC-7:** Given die Karte „Wetter-Profile" ist gerendert / When ich die Seite betrachte / Then bleibt die
  bestehende read-only Karte „Wetter-Templates" (Builtins) unverändert darunter sichtbar, klar von den
  User-Profilen unterscheidbar.
  - Test: `issue-344-wetter-profile.spec.ts::AC-7` (E2E, post-push)

## Known Limitations

- Default-Setzen ist nicht Teil dieser Karte (nur Anzeige der „Standard"-Markierung) — Out of Scope.
- `window.confirm` ist ein nativer Browser-Dialog (kein gestyltes Modal); bewusst gewählt zur
  Konsistenz mit dem bestehenden `deleteAccount`-Pattern auf derselben Seite.
- Bei sehr langen Preset-Namen greift Standard-Text-Wrapping der Card; kein Truncation-Sonderfall.

## Changelog

- 2026-05-24: Initial spec created (Issue #344, Sub-Issue 3 von Epic #304)

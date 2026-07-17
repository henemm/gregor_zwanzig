---
entity_id: feat_1273_s2_compare_hub_name_region_profil
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [frontend, compare, hub, epic-1273, inline-edit]
workflow: epic-1273-s2-hub-fields
---

<!-- Issue #1273 — Epic: Ortsvergleich auf EINE Fläche wie beim Trip. Diese Spec deckt NUR Slice S2 ab
     (Name/Region/Aktivitätsprofil-Parität im Hub). S1 (Save-Chip-Infra) ist bereits live
     (docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md). S3 (Link-Umbiegung + Redirect),
     S4a/S4b (Test-Migration) und S5 (CompareEditor-Löschung) sind eigene, spätere Specs.
     Kontext: docs/context/epic-1273-s2-hub-fields.md. -->

# Spec: #1273 Slice S2 — Compare-Hub: Name/Region/Aktivitätsprofil inline editierbar

## Approval

- [x] Approved — PO Henning, 2026-07-17 (Freigabe "freigabe" nach Vorlage der 7 ACs inkl. Known Limitations)

## Purpose

Der Ortsvergleich-Hub (`/compare/[id]`) bekommt inline editierbare Felder für Name, Region und Aktivitätsprofil — bislang nur über den separaten, veralteten `CompareEditor.svelte` (Route `/compare/[id]/edit`) änderbar. Ohne diese Slice wäre ein späterer Redirect von `/edit` auf den Hub (S3) eine echte Funktionsregression: Nutzer könnten den Vergleich nicht mehr umbenennen oder das Aktivitätsprofil wechseln. Diese Slice schließt exakt diese Feature-Paritäts-Lücke — additiv, ohne den alten Editor anzufassen oder etwas zu entfernen.

## Source

- **File:** `frontend/src/routes/compare/[id]/+page.svelte`
  - **Identifier:** Desktop-Kopfbereich (Z.152-199), Mobile-Kopfbereich (Z.201-246) — beide Blöcke bekommen je drei neue Inline-Edit-Zustände (Name/Region/Aktivitätsprofil) plus zugehörige Save-Handler im `<script>`-Block.

> **PFLICHT — Schicht-Hinweis:** Ausschließlich **Frontend** (`frontend/src/...`, SvelteKit, produktive Oberfläche auf gregor20.henemm.com). Kein Go-API-Endpoint wird neu gebraucht — `PUT /api/compare/presets/{id}` existiert bereits (`internal/handler/compare_preset.go:259-297`, ungeändert). Kein Python-Core betroffen.

## Estimated Scope

- **LoC:** ~150–200 (Produktivcode, ohne Tests). Deckt sich mit der Kontext-Schätzung (~150–220).
- **Files:** 1 geändert (`routes/compare/[id]/+page.svelte`), 0 neu. Dazu 1 neue Playwright-Testdatei.
- **Effort:** low–medium.

LoC-Limit 250/Workflow: knapp, aber voraussichtlich unkritisch. Sollte die Implementierung wegen der drei parallelen Feld-Blöcke (Desktop+Mobile) über 250 laufen, ist ein `loc_limit_override` mit PO-Rückfrage nötig (CLAUDE.md: „Kein LoC-Override ohne Permission").

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/api.ts` (`api.put<T>(path, body)`) | geteilter Baustein, unverändert | HTTP-PUT gegen `/api/compare/presets/{id}` |
| `internal/handler/compare_preset.go:259-297` (`UpdateComparePresetHandler`) | Go-API, unverändert | Nimmt den vollen Round-Trip-Spread-Body entgegen, mergt `display_config` feldweise (Issue #1159), gibt den vollständigen, servergültigen `ComparePreset` als Response zurück |
| `frontend/src/lib/types.ts` (`ACTIVITY_PROFILE_OPTIONS`, `ActivityProfile`) | geteilter Baustein, unverändert | Bereits gemeinsam von `CompareEditor.svelte` genutzte Options-Liste (4 Werte: `allgemein`, `wintersport`, `wandern`, `summer_trekking`) — **keine neue Duplikation**, nur Import in `+page.svelte` |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:33-54,127-163,274-314` | Referenzmuster, unverändert | Stift-Icon-Toggle + lokaler State + eigener `api.put()`-Pfad OHNE `saveController` — UI-Vorbild für Name/Region (nicht direkt wiederverwendbar: andere Datenstruktur `ComparePreset` vs. `Trip`, andere Route) |
| `frontend/src/lib/components/compare/CompareEditor.svelte:1163-1233` | Referenzmuster, unverändert | Zeigt Feld-UI für Name/Region (Text-Input) und Aktivitätsprofil (Auswahl-Kacheln mit `data-selected`) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Referenzmuster, unverändert | Zeigt das etablierte Round-Trip-Spread-Prinzip (`{ ...original, <geändertes Feld> }`) — dieselbe Payload-Strategie wird hier für die drei neuen Inline-Edits übernommen |
| `frontend/src/lib/components/compare/CompareTabs.svelte:807-826` (defensiver `$effect`) | geteilter Baustein, unverändert, **kritisch für Datenverlust-Schutz** | Synchronisiert `currentPreset` (die interne PUT-Baseline für die 5 bestehenden Hub-Commit-Handler), sobald sich die `preset`-Prop-**Referenz** ändert. Das ist die Voraussetzung dafür, dass ein Header-Edit (Name/Region/Profil) nicht von einem nachfolgenden Wertebereiche-/Versand-/Alarme-Commit im selben Seitenaufenthalt zurücküberschrieben wird — s. Implementation Details Punkt 4. |

## Implementation Details

**1. Lokaler State pro Feld (Muster: `TripHeader.svelte:33-38`, dreifach):**

```
// im <script>-Block von routes/compare/[id]/+page.svelte
import { ACTIVITY_PROFILE_OPTIONS, type ActivityProfile } from '$lib/types';
import { api } from '$lib/api';

let editName = $state(data.preset.name);
let nameSaving = $state(false);
let isEditingName = $state(false);
let nameSaveError: string | null = $state(null);

let editRegion = $state(data.preset.display_config?.region ?? '');
let regionSaving = $state(false);
let isEditingRegion = $state(false);
let regionSaveError: string | null = $state(null);

let editProfil = $state<ActivityProfile>((data.preset.profil ?? 'allgemein') as ActivityProfile);
let profilSaving = $state(false);
let isEditingProfil = $state(false);
let profilSaveError: string | null = $state(null);
```

**2. Round-Trip-Spread-Save-Handler pro Feld (NICHT der TripHeader-Minimal-Body — Datenverlust-Risiko, s. u.):**

```
async function saveName(): Promise<void> {
  nameSaving = true;
  nameSaveError = null;
  try {
    const updated = await api.put<ComparePreset>(`/api/compare/presets/${data.preset.id}`, {
      ...data.preset,
      name: editName
    });
    data.preset = updated;           // NEUE Objekt-Referenz aus der API-Response, s. Punkt 4
    isEditingName = false;
  } catch (e: unknown) {
    nameSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
  } finally {
    nameSaving = false;
  }
}

async function saveRegion(): Promise<void> {
  regionSaving = true;
  regionSaveError = null;
  try {
    const updated = await api.put<ComparePreset>(`/api/compare/presets/${data.preset.id}`, {
      ...data.preset,
      display_config: { ...data.preset.display_config, region: editRegion }
    });
    data.preset = updated;
    isEditingRegion = false;
  } catch (e: unknown) {
    regionSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
  } finally {
    regionSaving = false;
  }
}

async function saveProfil(value: ActivityProfile): Promise<void> {
  profilSaving = true;
  profilSaveError = null;
  editProfil = value;
  try {
    const updated = await api.put<ComparePreset>(`/api/compare/presets/${data.preset.id}`, {
      ...data.preset,
      profil: value
    });
    data.preset = updated;
    isEditingProfil = false;
  } catch (e: unknown) {
    profilSaveError = (e as { error?: string })?.error || 'Speichern fehlgeschlagen';
  } finally {
    profilSaving = false;
  }
}
```

**Warum Round-Trip-Spread und nicht der TripHeader-Minimal-Body (`{name: editName}`):** `UpdateComparePresetHandler` (`internal/handler/compare_preset.go:259-297`) dekodiert den Request-Body in ein **frisches** `model.ComparePreset{}` (Zero-Value-Start), nicht in eine Kopie von `original`. Nur explizit gegen Zero-Value abgesicherte Felder (`DisplayConfig`, `PreviousSchedule`, die Alarm-/Zeitplan-Pointer-Felder, `Corridors` u. a., s. Zeile 288-380) überleben einen Teil-PUT. **`Name`, `Profil`, `LocationIds`, `Empfaenger`, `Schedule`, `HourFrom`/`HourTo` haben keinen solchen Schutz.** Ein Body wie `{"name": "..."}` würde `location_ids`/`empfaenger`/`schedule`/`profil` auf Zero-Value zurücksetzen — das BUG-DATALOSS-Muster aus CLAUDE.md. Der Round-Trip-Spread (`{ ...data.preset, name: editName }`) schickt stattdessen den vollständigen, aktuell geladenen Preset mit nur dem geänderten Feld überschrieben — exakt das Prinzip, das `compareEditorSave.ts` bereits für den alten Editor nutzt (Zeile 70-71: „Schluesselprinzip: `{ ...original, <überschriebene Felder> }`").

**3. Aktivitätsprofil als Auswahl-Kacheln (Muster `CompareEditor.svelte:1193-1233`), NICHT Freitext:**

```
{#each ACTIVITY_PROFILE_OPTIONS as opt (opt.value)}
  <button
    type="button"
    data-testid={`compare-hub-profil-option-${opt.value}`}
    data-selected={data.preset.profil === opt.value ? 'true' : 'false'}
    disabled={profilSaving}
    onclick={() => saveProfil(opt.value)}
  >{opt.label}</button>
{/each}
```

Kein separates „Speichern"-Feld nötig — ein Klick auf eine Kachel löst sofort `saveProfil(opt.value)` aus (kein Zwischenzustand „ausgewählt, aber nicht gespeichert"), analog zum sofortigen Commit-Verhalten der bestehenden 5 Hub-Handler (`persistPickedIds`, `handleToggleActive` etc. — kein separater Speichern-Button im Hub, nur in `Name`/`Region`, die textuelle Eingabe brauchen).

**4. KRITISCH — `data.preset = updated` muss eine neue Objekt-Referenz zuweisen, keine In-Place-Mutation:**

`CompareTabs.svelte` hält für seine 5 bestehenden Commit-Handler (Orte, Wertebereiche, Versand, Alarme, Aktivieren/Pausieren) eine eigene, unabhängige Kopie `currentPreset` (`$state<ComparePreset>(snapshotForRollback(preset))`, Zeile 181) — bewusst entkoppelt vom `preset`-Prop, damit ein `invalidateAll()` nicht mit unbestätigten Tab-Edits kollidiert (s. Kommentar Zeile 807-820, „Staging-Fund F004"). Es existiert aber bereits ein **defensiver `$effect`** (Zeile 821-826):

```
$effect(() => {
  currentPreset = snapshotForRollback(preset);
  idealwerteHydrated = false;
  versandHydrated = false;
  alarmeHydrated = false;
});
```

Dieser Effekt reagiert auf einen echten **Referenzwechsel** der `preset`-Prop. Wird `data.preset` nach einem erfolgreichen Header-Edit mit dem **neuen** Objekt aus der API-Response überschrieben (`data.preset = updated`), ändert sich die Referenz, die über `<CompareDetail preset={data.preset} .../>` (Zeile 254-261) nach unten durchgereicht wird — der Effekt feuert, `currentPreset` wird aufgefrischt.

**Ohne diesen Referenzwechsel** (z. B. eine In-Place-Mutation wie `data.preset.name = editName`) würde `currentPreset` in `CompareTabs.svelte` **veraltet bleiben**. Bearbeitet der Nutzer danach — im selben Seitenaufenthalt, ohne Reload — z. B. ein Feld im Wertebereiche- oder Versand-Tab, baut `buildHubPutPayload(currentPreset, ...)` den PUT-Body aus dem veralteten `currentPreset` und würde den gerade geänderten Namen/Region/Profil **stillschweigend auf den alten Wert zurücksetzen** — dieselbe Datenverlust-Klasse wie der bereits behobene „Staging-Fund F004" (Kebab vs. Hub, `probe_kebab_vs_hub_stale_data.mjs`). Diese Slice führt **keine neue Synchronisations-Logik** ein, sondern verlässt sich bewusst auf den bereits vorhandenen Mechanismus — vorausgesetzt, jeder der drei Save-Handler weist `data.preset` das **vollständige API-Response-Objekt** zu (kein Teil-Merge, keine Mutation einzelner Felder).

**5. Kein Verwerfen-Button auf Seitenebene nötig** — jedes Feld hat wie `TripHeader.svelte:156-160` einen lokalen „Abbrechen"-Button, der nur den lokalen Edit-State zurücksetzt (`editName = data.preset.name; isEditingName = false;`), analog zu Name im Trip-Editor. Kein page-weites Verwerfen-Konzept nötig, da jeder Save sofort und isoliert committet (kein mehrstufiges Formular).

## Expected Behavior

| Situation | Verhalten |
|---|---|
| Stift-Icon neben Name/Region/Aktivitätsprofil klicken | Textfeld (Name/Region) bzw. Kachel-Auswahl (Profil) wird editierbar, vorbelegt mit aktuellem Wert |
| Name/Region ändern und „Speichern"/„Umbenennen" klicken | PUT mit Round-Trip-Spread-Body; bei Erfolg schließt sich das Eingabefeld, der neue Wert erscheint sofort im Kopfbereich (kein Reload) |
| Aktivitätsprofil-Kachel anklicken | Sofortiger PUT (kein Zwischenschritt); bei Erfolg wechselt die Markierung auf die neue Kachel |
| „Abbrechen" klicken | Lokaler Edit-State wird verworfen, kein PUT, angezeigter Wert bleibt unverändert |
| PUT schlägt fehl (z. B. Netzwerkfehler) | Fehlermeldung unter dem jeweiligen Feld, Eingabefeld bleibt offen, angezeigter (nicht editierter) Wert im restlichen Hub bleibt der letzte persistierte Stand |
| Name im Header ändern, danach im selben Seitenaufenthalt einen Wert im Wertebereiche-/Versand-/Alarme-Tab ändern | Beide Änderungen bleiben erhalten — der geänderte Name wird vom nachfolgenden Tab-Commit NICHT zurücküberschrieben (s. Implementation Details Punkt 4) |
| Mobile Viewport (≤899px) | Identisches Verhalten wie Desktop — Stift-Icons, Eingabefelder/Kacheln, Speichern/Abbrechen funktionieren gleich |

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Hub eines Ortsvergleichs (Desktop) / When er den Namen über das Stift-Icon ändert und speichert / Then zeigt der Kopfbereich sofort den neuen Namen (ohne Reload), und nach Seiten-Neuladen ist der Name persistiert.
  - Test: Playwright/Staging — eingeloggt `/compare/{id}` öffnen, `[data-testid="compare-hub-name-edit-toggle"]` klicken, Eingabefeld füllen, Speichern klicken, H1-Text sofort geändert prüfen, Seite neu laden, Name bleibt geändert.

- **AC-2:** Given derselbe Hub / When der Nutzer die Region über das Stift-Icon ändert und speichert / Then zeigt die Unterzeile sofort die neue Region, und `display_config.region` ist nach Reload persistiert.
  - Test: Playwright/Staging — Region-Feld analog AC-1 ändern, sichtbaren Unterzeilen-Text prüfen, per `GET /api/compare/presets/{id}` `display_config.region` nach Reload verifizieren.

- **AC-3:** Given derselbe Hub / When der Nutzer eine andere Aktivitätsprofil-Kachel anklickt / Then markiert sich sofort die neue Kachel als ausgewählt, das Profil-Label in der Unterzeile aktualisiert sich, und der Wert ist nach Reload persistiert.
  - Test: Playwright/Staging — `[data-testid="compare-hub-profil-option-wandern"]` klicken, `data-selected="true"` prüfen, GET-Preset nach Reload: `profil === "wandern"`.

- **AC-4 (Datenverlust-Schutz, Teil-Edit):** Given ein bestehender Ortsvergleich mit gesetzten `location_ids` (≥2 Orte), `empfaenger` (≥1 Adresse) und aktivem `schedule` / When der Nutzer NUR den Namen ändert und speichert / Then bleiben `location_ids`, `empfaenger`, `schedule` und `profil` nach dem Save unverändert (per `GET /api/compare/presets/{id}` verifiziert) — kein Zurücksetzen auf leere Arrays/Zero-Values.
  - Test: Playwright/Staging — Preset mit 2 Orten + 1 Empfänger + `schedule=daily` seeden, nur Name im Hub ändern+speichern, anschließend `GET`-Response auf unveränderte `location_ids.length === 2`, `empfaenger.length === 1`, `schedule === 'daily'` prüfen. Reproduziert das BUG-DATALOSS-Muster aus CLAUDE.md, falls der Minimal-Body-Fehler versehentlich doch verwendet würde — Test MUSS vor einem korrekten Fix rot sein.

- **AC-5 (Datenverlust-Schutz, Cross-Tab):** Given der Nutzer hat den Namen im Header geändert und gespeichert / When er danach — im selben Seitenaufenthalt, ohne Reload — einen Wert im Wertebereiche- oder Versand-Tab ändert und dieser automatisch/über den dortigen Speichern-Pfad committet / Then bleibt der zuvor geänderte Name erhalten (wird NICHT auf den alten Wert zurückgesetzt).
  - Test: Playwright/Staging — Namen im Header ändern+speichern, zum Wertebereiche-Tab wechseln, ein Zahlenfeld ändern und `blur()` auslösen (Commit), zurück zur Übersicht/Header, sichtbaren Namen UND per `GET`-Preset den `name` prüfen — beide zeigen den neuen Namen.

- **AC-6 (Mobile-Parität):** Given ein Nutzer öffnet den Hub im Mobile-Viewport (≤899px) / When er Name, Region und Aktivitätsprofil über dieselben Stift-Icon-/Kachel-Interaktionen wie auf Desktop ändert / Then funktioniert jede der drei Änderungen identisch (sofort sichtbar, nach Reload persistiert) — keine Geräte-Parität-Lücke.
  - Test: Playwright/Staging — Viewport auf `375×812` setzen, `/compare/{id}` öffnen, AC-1/AC-2/AC-3 wiederholen gegen die sichtbaren Mobile-Elemente (gleiche `data-testid`s wie Desktop — Sichtbarkeitsfilter nötig, da Desktop-Block per CSS `hidden desktop:block` ausgeblendet, aber im DOM vorhanden bleibt: `page.getByTestId(...).filter({ visible: true })` bzw. `.locator(':visible')`, analog bestehendem Projekt-Muster für `runtime-exceeded-hint`).

- **AC-7 (Fehlerfall):** Given der PUT-Endpunkt schlägt fehl (z. B. simulierter 500er) / When der Nutzer eines der drei Felder ändert und zu speichern versucht / Then zeigt das jeweilige Feld eine Fehlermeldung („Speichern fehlgeschlagen" bzw. Server-Fehlertext), das Eingabefeld bleibt offen (kein stiller Datenverlust der Eingabe), und der im Hub angezeigte (nicht editierte) Wert bleibt der letzte persistierte Stand.
  - Test: Playwright/Staging — `page.route()` auf `PUT /api/compare/presets/{id}` mit Status 500 stubben, Namensänderung versuchen und speichern, `[data-testid="compare-hub-name-save-error"]` sichtbar mit Fehlertext prüfen, H1 zeigt weiterhin den alten Namen.

## Known Limitations

- **Cross-Tab-Datenverlust-Schutz ist strukturell an die bestehende `$effect`-Resync-Logik in `CompareTabs.svelte:821-826` gekoppelt**, nicht an einen neuen, dieser Slice eigenen Mechanismus. Ändert sich diese Logik künftig (z. B. Entkoppelung von Prop-Referenz-Reaktivität), muss AC-5 erneut geprüft werden — kein eigenständiger Schutz in `+page.svelte`.
- **Kein optimistisches Locking / keine ETags.** Header-Edits (Name/Region/Profil) laufen NICHT über die `hubPutQueue`-Serialisierung, die die 5 bestehenden Tab-Handler seriell hält — zwei nahezu zeitgleiche PUTs (Header + Tab) sind zwei unabhängige Requests. Der Server hat kein Konflikterkennungs-Verfahren; „letzter Schreiber gewinnt" ist bestehendes, unverändertes Projektverhalten (nicht neu durch diese Slice) und wird hier nicht behoben.
- **`ACTIVITY_PROFILE_OPTIONS` wird NICHT dupliziert** — die Liste lebt bereits zentral in `$lib/types.ts` und wird von `CompareEditor.svelte` UND (neu) vom Hub importiert. Erfüllt die Trip/Compare-Teilungs-Invariante ohne zusätzliche Abstraktion.
- **Kein page-weites Verwerfen.** Jedes der drei Felder committet isoliert und sofort (analog Trip-Name); es gibt keinen gemeinsamen „alle drei verwerfen"-Zustand — bewusst, da kein mehrstufiges Formular.
- **Testid-Duplikation Desktop/Mobile:** dieselben `data-testid`-Werte erscheinen zweimal im DOM (ein Block ist per CSS ausgeblendet) — etabliertes Projektmuster (z. B. `runtime-exceeded-hint`); Tests müssen mit Sichtbarkeitsfilter arbeiten (s. AC-6-Test-Hinweis).
- **Markup-Duplikation Desktop/Mobile bewusst nicht extrahiert** (YAGNI, Kontext-Dokument-Entscheidung) — beide Blöcke haben ohnehin unterschiedliche Styling-Ansätze (inline `style=""` vs. Tailwind-Utility-Klassen). Bei einer künftigen Slice mit weiteren editierbaren Feldern sollte eine gemeinsame Snippet-/Komponentenlösung erneut geprüft werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Slice führt keine neue Architektur-Entscheidung ein, sondern wendet zwei bereits etablierte, geteilte Prinzipien auf eine dritte Stelle an: (1) Round-Trip-Spread-Payload-Bau (`compareEditorSave.ts`, bereits Prinzip für den alten Editor), (2) den bestehenden defensiven Prop-Referenz-Resync-Effekt in `CompareTabs.svelte` (Staging-Fund F004, bereits gebaut für den Kebab-vs-Hub-Fall). Kein neuer Compare-eigener Baustein, keine neue Synchronisations-Infrastruktur — konsistent mit der Trip/Compare-Teilungs-Invariante (CLAUDE.md) und der ADR-Begründung in S1 (`feat_1273_s1_compare_hub_save_chip.md`, dort ebenfalls „keine").

## Changelog

- 2026-07-17: Erstfassung (Slice S2 von Epic #1273). Basiert auf `docs/context/epic-1273-s2-hub-fields.md`, insbesondere Abschnitt „KRITISCHE KORREKTUR nach Verifikation gegen den echten Go-Handler" (Round-Trip-Spread statt TripHeader-Minimal-Body). Ergänzt gegenüber dem Kontext-Dokument einen bislang nicht dokumentierten Cross-Tab-Datenverlust-Risikofall (Header-Edit vs. `CompareTabs`-internes `currentPreset`) und dessen bereits vorhandene Lösung über den defensiven `$effect` in `CompareTabs.svelte:821-826` — verifiziert per Code-Lesung, nicht nur angenommen. Daraus abgeleitet: AC-5 (Cross-Tab-Datenverlust-Schutz) und die explizite Implementierungs-Pflicht „neue Objekt-Referenz, keine In-Place-Mutation" in Implementation Details Punkt 4.

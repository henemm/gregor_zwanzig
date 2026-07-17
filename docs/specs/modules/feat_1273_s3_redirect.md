---
entity_id: feat_1273_s3_redirect
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [frontend, compare, epic-1273, redirect, ia]
---

# Epic #1273 Slice S3 — Compare-Edit-Route wird reiner Redirect auf den Hub

## Approval

- [x] Approved — PO Henning, 2026-07-17 (Freigabe "Freigabe" nach Vorlage der 7 ACs inkl. Known Limitations)

## Purpose

Die separate Bearbeiten-Seite `/compare/[id]/edit` (CompareEditor) entfällt zugunsten des Hubs `/compare/[id]`, der seit S1 (Save-Chip) und S2 (Name/Region/Profil inline editierbar) die einzige Bearbeiten-Fläche für Orts-Vergleiche ist ("EINE Fläche", Epic #1273). Diese Slice biegt alle 7 externen Linkziele auf den Hub um, macht die alte Route zu einem reinen Redirect (kein 404, kein CompareEditor-Rendering mehr) und entfernt die dadurch redundanten Hub-eigenen Bearbeiten-Affordanzen (Desktop-Button, Mobile-Stift-Icon), analog zum bereits bestehenden Trip-Hub (der ebenfalls keinen "Bearbeiten"-Knopf mehr hat, Präzedenzfall #616).

## Source

- **File:** `frontend/src/routes/compare/[id]/edit/+page.svelte`, `frontend/src/routes/compare/[id]/edit/+page.server.ts`
- **Identifier:** `PageServerLoad` (Redirect-Route), `compareDetailActions()` / `compareLifecycleActions()` (`subscriptionHelpers.ts`)

> **Schicht-Hinweis:** Reines Frontend. Alle Änderungen liegen unter `frontend/src/routes/` und `frontend/src/lib/components/compare/`. Kein Go-API- und kein Python-Core-Code betroffen. Kein Datenmodell-, kein Backend-Vertragswechsel.

## Estimated Scope

- **LoC:** ~100-150 (überwiegend 1-5-Zeilen-Diffs an den 7 Linkstellen + Entfernen von zwei Markup-Blöcken + neue Redirect-Route + Test-Anpassung)
- **Files:** 9 (siehe Implementation Details) + 1 bestehender Unit-Test angepasst
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Epic #1273 S1 (Save-Chip) | Vorbedingung, live | Hub kann Änderungen persistieren, bevor die alte Route stillgelegt wird |
| Epic #1273 S2 (Name/Region/Profil inline editierbar) | Vorbedingung, live | Hub ist feature-vollständig genug, um `/edit` vollständig zu ersetzen |
| #616 (Trip-IA-Redirect-Präzedenz) | Vorbild | `routes/trips/[id]/edit/+page.server.ts` — identisches Redirect-Muster |
| CompareTabs.svelte (`initialTab`-Prop, `resolve()`) | Bestehender Mechanismus | Kein neuer Code nötig — `?tab=idealwerte` / `?tab=versand` werden bereits unterstützt |
| Epic #1273 S4 (Test-Migration) | Downstream, NICHT Teil dieser Slice | ~26 e2e-Specs + weitere Unit-Tests, die noch `/edit` ansteuern, werden durch S3 strukturell rot |
| Epic #1273 S5 (CompareEditor-Löschung) | Downstream, NICHT Teil dieser Slice | `CompareEditor.svelte` bleibt als toter Code liegen, nur unerreichbar |

## Implementation Details

### 1. Redirect-Route (2 Dateien)

`frontend/src/routes/compare/[id]/edit/+page.server.ts` — komplett ersetzen durch Redirect-Load, exaktes Vorbild `frontend/src/routes/trips/[id]/edit/+page.server.ts`:

```ts
import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ params }) => {
	throw redirect(307, `/compare/${params.id}`);
};
```

Die bisherige `+page.server.ts` lädt `preset`/`locations`/`profile` per Fetch gegen die Python-API — das entfällt vollständig, da nichts mehr gerendert wird.

`frontend/src/routes/compare/[id]/edit/+page.svelte` — Inhalt auf eine leere Hülle reduzieren (SvelteKit rendert `+page.svelte` nach einem `redirect()` im `load` nicht mehr, die Datei muss aber weiter existieren, damit die Route matcht). Kein `CompareWizardState`-Setup, kein `CompareEditor`-Import, kein `beforeNavigate`-Flush-Handling mehr — das komplette bisherige Script-Bloc (State-Hydration aus `data.preset.*`, `editorRef`, `beforeNavigate`) entfällt ersatzlos.

Kein `tab`-Query-Passthrough nötig (anders als beim Trip-Vorbild) — die Aufrufer werden in Schritt 2 direkt mit dem korrekten `?tab=`-Ziel verlinkt.

### 2. 7 externe Linkziele umbiegen

| Datei:Zeile | Vorher | Nachher |
|---|---|---|
| `frontend/src/routes/_home/CompareKachel.svelte:20` | `goto('/compare/' + sub.id + '/edit')` | `goto('/compare/' + sub.id)` |
| `frontend/src/routes/compare/+page.svelte:119` (`onCompareAction`, Fall `'setup'`) | `goto('/compare/' + p.id + '/edit')` | `goto('/compare/' + p.id)` |
| `frontend/src/routes/compare/+page.svelte:120` (`onCompareAction`, Fall `'edit'`) | `goto('/compare/' + p.id + '/edit')` | `goto('/compare/' + p.id)` |
| `frontend/src/routes/+page.svelte:97` (`buildCompareCtaHref()`) | `` `/compare/${firstIncomplete.id}/edit` `` | `` `/compare/${firstIncomplete.id}` `` |
| `frontend/src/routes/+page.svelte:560` (Schnellaktion "Orte bearbeiten") | `href="/compare/{compareHero.id}/edit"` | `href="/compare/{compareHero.id}"` |
| `frontend/src/routes/+page.svelte:566` (Schnellaktion "Ideal-Werte ändern") | `href="/compare/{compareHero.id}/edit#idealwerte"` | `href="/compare/{compareHero.id}?tab=idealwerte"` |
| `frontend/src/routes/+page.svelte:572` (Schnellaktion "Briefing-Zeitplan") | `href="/compare/{compareHero.id}/edit#schedule"` | `href="/compare/{compareHero.id}?tab=versand"` |

Die beiden Hash-Anker (`#idealwerte`, `#schedule`) liefen bereits vor dieser Slice ins Leere — es gibt kein DOM-Element mit diesen IDs, der Hub scrollt nicht dorthin. `CompareTabs.svelte` unterstützt bereits `?tab=` über die `initialTab`-Prop und `resolve()` (bestehende Werte: `idealwerte`, `versand`) — kein neuer Mechanismus, nur der Query-Key statt Hash.

**Bewusst NICHT geändert:** `compareActions()` in `subscriptionHelpers.ts:273-292` (Listen-/Home-Kebab) behält die `id: 'edit'` / `id: 'setup'`-Einträge unverändert — das sind externe Einstiege, deren Linkziel bereits durch die Änderungen an `compare/+page.svelte:119-120` und `CompareKachel.svelte:20` auf den Hub zeigt (Punkt 2), nicht durch eine Änderung an der Aktionsliste selbst.

### 3. Hub-interne, jetzt redundante Bearbeiten-Affordanzen entfernen (PO-Entscheid)

`frontend/src/routes/compare/[id]/+page.svelte`:

- **Zeile 334-336** (Desktop-Button): Kompletten `<Btn variant="outline" href="/compare/{currentPreset.id}/edit" data-testid="compare-detail-edit-button">Bearbeiten</Btn>`-Block inkl. Vorgänger-Kommentar entfernen. `<Btn variant="primary" onclick={handleTestSend} ...>`-Block direkt darüber bleibt unverändert.
- **Zeile 377-383** (Mobile Stift-Icon in der TopBar): Kompletten `<a href="/compare/{currentPreset.id}/edit" ... aria-label="Bearbeiten"><PencilIcon size={18} /></a>`-Block entfernen. Der `<button ... aria-label="Weitere Aktionen">` (Kebab-Trigger) direkt danach bleibt unverändert.
- **Zeile 216-219** (`handleAction()`): Den Zweig `if (id === 'edit' || id === 'setup') { window.location.href = ...; }` entfernen — er ist ab jetzt tot, da `compareDetailActions()` (Schritt unten) kein `edit` mehr liefert und kein anderer Aufrufer im Hub `'edit'`/`'setup'` an `handleAction` übergibt. Die restliche `if/else if`-Kette (`pause`/`resume`, `send`, `preview`, `archive`, `delete`/`trash`) bleibt unverändert.

`frontend/src/lib/components/compare/subscriptionHelpers.ts`:

- **`compareDetailActions()` (Zeile 315-322):** Den `editAction`-Aufbau und das Einfügen in die Liste entfernen. Neue Implementierung liefert 1:1 `compareLifecycleActions(status)` durch (keine Sonderbehandlung für `draft` mehr nötig, da `compareLifecycleActions()` bereits alle Status abdeckt):

```ts
export function compareDetailActions(status: CompareStatus): CompareAction[] {
	return compareLifecycleActions(status);
}
```

Der Funktionskopf-Kommentar (Zeile 308-314, referenziert #1261) muss auf die neue Semantik aktualisiert werden: `compareDetailActions()` ist jetzt ein reiner Alias auf `compareLifecycleActions()` — die Trennung existiert nur noch aus Aufrufer-Kompatibilitätsgründen (Desktop-Hub-Kebab, `+page.svelte:338`), nicht mehr aus Verhaltensgründen.

### 4. `compareActions()` bleibt unverändert

`subscriptionHelpers.ts:273-292` — keine Code-Änderung. Bewusst dokumentiert unter Punkt 2 (Bewusst NICHT geändert).

### 5. Bestehenden Unit-Test anpassen

`frontend/src/lib/components/compare/__tests__/compareDetailEditActions.test.ts` (aus #1261): Die beiden AC-2-Tests ("`compareDetailActions('active'|'paused')` enthält `edit`") drehen auf das Gegenteil ("enthält KEINEN `edit`-Eintrag mehr"). AC-4 (Draft ohne edit) und der Regressionstest (`compareLifecycleActions()` nie mit edit) bleiben inhaltlich unverändert — nur die Assertion für `active`/`paused` kehrt sich um. Der Kommentar-Kopf der Datei muss kurz erklären, **warum** sich das #1261-AC-2-Verhalten jetzt umkehrt: S2 (inline editierbares Name/Region/Profil auf dem Hub selbst) macht den separaten "Bearbeiten"-Einstieg im Desktop-Kebab überflüssig — der Hub *ist* jetzt die Bearbeiten-Fläche, ein "Bearbeiten"-Eintrag im eigenen Kebab wäre zirkulär.

## Expected Behavior

- **Input:** Navigation/Klick auf einen der 7 externen Linkziele, direkter Aufruf von `/compare/{id}/edit` (z.B. Altlink, Bookmark), Öffnen des Hub-Kebabs.
- **Output:** Jeder Pfad landet auf `/compare/{id}` (ggf. mit `?tab=`), niemals auf einem gerenderten CompareEditor und niemals auf einer 404-Seite. Hub-Kebab (`compareDetailActions()`) zeigt keinen "Bearbeiten"-Eintrag mehr. Hub-Header (Desktop) zeigt keinen "Bearbeiten"-Button, Mobile-TopBar kein Stift-Icon.
- **Side effects:** Keine Datenänderung. `CompareEditor.svelte` wird nicht mehr erreicht, bleibt aber im Repo (S5-Scope). Listen-/Home-Kebab (`compareActions()`) funktioniert unverändert, landet nur auf einem neuen Ziel.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer ruft `/compare/{id}/edit` direkt auf (z.B. Altlink) / When die Seite lädt / Then er wird per 307-Redirect auf `/compare/{id}` weitergeleitet, ohne dass CompareEditor gerendert wird oder eine 404-Seite erscheint.
  - Test: `+page.server.ts`-Load direkt aufrufen (bzw. per Fetch gegen die Route) und prüfen, dass ein `redirect`-Objekt mit `status: 307` und `location: /compare/{id}` geworfen wird — kein Netzwerk-Fetch gegen `/api/compare/presets/{id}` mehr im Load (Vorbild: analoger Test zu `trips/[id]/edit`, falls vorhanden, sonst neuer minimaler Test).

- **AC-2:** Given die 7 identifizierten externen Linkstellen (Home-Kachel-Kebab, Listen-Kebab `setup`+`edit`, Home-Hero-CTA, 3 Schnellaktionen) / When ein Nutzer eine davon anklickt / Then landet er auf `/compare/{id}` (bzw. mit passendem `?tab=`), nie auf `/compare/{id}/edit`.
  - Test: Für jede der 6 in Svelte-Komponenten codierten Linkziele (Kachel, Liste ×2, Home-CTA, 2 Schnellaktionen ohne Tab) den erzeugten href/goto-Zielstring gegen die neue Erwartung prüfen (echter Funktions-/Komponentenaufruf, kein Datei-Grep).

- **AC-3:** Given die 2 vormals hash-basierten Schnellaktionen ("Ideal-Werte ändern", "Briefing-Zeitplan") / When ein Nutzer klickt / Then landet er auf `/compare/{id}?tab=idealwerte` bzw. `/compare/{id}?tab=versand`, und `CompareTabs` öffnet dort tatsächlich den jeweiligen Tab (nicht nur `uebersicht`).
  - Test: Query-Parameter-Ziel der beiden hrefs prüfen UND `resolve('idealwerte')`/`resolve('versand')` liefert den jeweiligen Tab-Key zurück (CompareTabs-Verhalten, kein neuer Mechanismus, nur Nachweis dass die bestehende Auflösung greift).

- **AC-4:** Given der Hub (`/compare/[id]/+page.svelte`) im Status `active`/`paused` / When die Seite gerendert wird / Then existiert weder der Desktop-"Bearbeiten"-Button (`data-testid="compare-detail-edit-button"`) noch das Mobile-Stift-Icon (`aria-label="Bearbeiten"` in der TopBar).
  - Test: Component-Render (Vitest/Testing-Library oder e2e), Query auf beide Testids/aria-labels liefert kein Treffer.

- **AC-5:** Given `compareDetailActions(status)` für `status ∈ {active, paused, draft}` / When aufgerufen / Then enthält die zurückgegebene Liste keinen Eintrag mit `id === 'edit'` mehr, für keinen Status.
  - Test: Direkter Funktionsaufruf `compareDetailActions('active'|'paused'|'draft')`, `find(a => a.id === 'edit')` ist `undefined` — Umkehrung der bisherigen #1261-AC-2-Assertion in `compareDetailEditActions.test.ts`.

- **AC-6:** Given `compareLifecycleActions(status)` (Mobile-Bottom-Sheet, `MCompareActionSheet.svelte`) / When aufgerufen für beliebigen Status / Then bleibt sie unverändert ohne `edit`-Eintrag (Regressionsschutz #1256 Scheibe 8 AC-23) — diese Funktion wird durch S3 nicht angefasst.
  - Test: Bestehender Regressionstest in `compareDetailEditActions.test.ts` bleibt grün und unverändert (`compareLifecycleActions('active')` ohne `edit`).

- **AC-7:** Given der Listen-Kebab (`routes/compare/+page.svelte`) bzw. der Home-Kachel-Kebab (`CompareKachel.svelte`) mit Aktionen `edit`/`setup` aus `compareActions()` / When ein Nutzer eine davon auswählt / Then führt das weiterhin zum jeweiligen Orts-Vergleich — nur eben zum Hub (`/compare/{id}`) statt zur alten `/edit`-Route. `compareActions()` selbst bleibt dabei unverändert (liefert weiterhin `id: 'edit'`/`id: 'setup'`-Einträge, nur das Linkziel des Aufrufers ändert sich).
  - Test: `onCompareAction('setup', row)` und `onCompareAction('edit', row)` in `compare/+page.svelte` prüfen, dass `goto` mit `/compare/{id}` (ohne `/edit`) aufgerufen wird. `compareActions('active')` liefert weiterhin ein `{id:'edit', label:'Bearbeiten'}`-Element (unverändert, kein Test-Fail hier erwartet).

## Known Limitations

- `CompareEditor.svelte` bleibt vollständig im Repo liegen — nur unerreichbar. Löschung ist explizit **S5**-Scope, nicht Teil dieser Slice.
- Die ~26 e2e-Specs sowie weitere Unit-Tests außerhalb von `compareDetailEditActions.test.ts`, die noch aktiv `/compare/[id]/edit` ansteuern (z.B. `goto()`/`page.goto()` auf die alte Route, Erwartung eines gerenderten CompareEditors dort), werden durch diese Slice **strukturell rot** — die Route liefert jetzt einen Redirect statt der Editor-Seite. Das ist erwartetes, akzeptiertes Verhalten dieser Slice und wird in **S4** (Test-Migration) behoben, **nicht Teil von S3**. `/60-validate` darf diese bekannten Rot-Fälle nicht als S3-Regression werten.
- Kein Tab-Query-Passthrough im Redirect selbst (anders als beim Trip-Vorbild `trips/[id]/edit`, das `?tab=` durchreicht) — nicht nötig, da alle bekannten Aufrufer bereits mit dem korrekten Zielpfad inkl. `?tab=` verlinkt werden. Sollte künftig ein weiterer Aufrufer mit Hash/Tab auf `/edit` verlinken, würde der Tab-Parameter verloren gehen.
- Die Route-Datei `+page.svelte` unter `edit/` bleibt als leere Hülle bestehen (SvelteKit-Routing-Anforderung), auch wenn sie inhaltlich nie mehr gerendert wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Konsolidierung auf bestehende Präzedenz)
- **Rationale:** Das Redirect-Muster ist durch #616 (Trip-IA) bereits etabliert und produktiv bewährt (`trips/[id]/edit/+page.server.ts`). S3 wendet dasselbe Muster 1:1 auf Compare an — keine neue Architekturentscheidung nötig, nur Anwendung eines bestehenden Patterns. Das Entfernen (statt Umleiten) der Hub-eigenen Bearbeiten-Affordanzen ist PO-Entscheid (AskUserQuestion, 2026-07-17), keine technische Architekturfrage.

## Changelog

- 2026-07-17: Initial spec created (Epic #1273 Slice S3)

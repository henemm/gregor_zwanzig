---
entity_id: issue_1259_compare_list_toggle_rmw
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [compare, bugfix, dataloss]
---

<!-- Issue #1259 — Kebab-Toggle in der Vergleichs-LISTE ueberschreibt frische Hub-Aenderungen mit stale Snapshot -->

# Issue 1259 — Vergleichs-Listen-Toggle: Read-Modify-Write statt Voll-Spread aus stale Prop

## Approval

- [ ] Approved

## Purpose

Der Kebab-Toggle "Pausieren/Aktivieren" in der Vergleichs-LISTEN-Ansicht
(`/compare`) baut seinen PUT-Body heute aus dem beim Seitenaufruf geladenen,
potenziell veralteten Listen-Snapshot per Voll-Spread (`{ ...preset, ...next }`).
Sind Liste und Detail-Hub desselben Vergleichs gleichzeitig in zwei
Browser-Tabs offen und aendert der Hub den Vergleich zwischenzeitlich,
ueberschreibt der Listen-Toggle diese Aenderung mit den veralteten
Listen-Feldern — stiller Server-Datenverlust ohne Fehlermeldung. Dieser Fix
macht den Listen-Toggle zu einem GET-vor-PUT (Read-Modify-Write): er liest
vor dem Schreiben den frischen Server-Stand, statt der eingefrorenen
Listen-Prop zu vertrauen. Gleiche Fehlerklasse wie F004/F007 aus Issue #1256
(dort bereits fuer den Hub-eigenen Kebab behoben; #1259 schliesst die
verbleibende Luecke im Listen-Kebab).

## Source

- **File:** `frontend/src/lib/components/compare/CompareGrid.svelte`
- **Identifier:** `async function togglePause(preset)` (Z. 57–71)

> **Schicht-Hinweis:** Reiner Frontend-Bug (SvelteKit, `/compare`-Liste). Kein
> Go-API- oder Python-Core-Code betroffen; der Backend-Handler
> (`internal/handler/compare_preset.go`) bleibt unveraendert (s. Known
> Limitations / Verworfene Alternativen).

### Betroffene Dateien

| File | Change Type | Beschreibung |
|------|-------------|--------------|
| `frontend/src/lib/components/compare/CompareGrid.svelte` | MODIFY | `togglePause` wird zur duennen Delegation: GET frischer Preset, dann Payload-Bau ueber neuen Bridge-Helper, dann PUT, Zeile aus PUT-Response aktualisieren |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | MODIFY | Neuer, injizierbarer Helper (z.B. `buildFreshTogglePutPayload`), der GET-Ergebnis + `computePauseToggle` + bestehendes `buildToggleActivePutPayload` zu einem testbaren Kern-Flow verbindet |
| `frontend/src/lib/components/compare/__tests__/list_toggle_read_modify_write.test.ts` | CREATE | Deterministischer node:test-Kerntest (kein DOM/Browser), beweist Multi-Tab-Verlustfreiheit anhand echter Bridge-Funktionen + simuliertem Server |

## Estimated Scope

- **LoC:** ~30–50
- **Files:** 3
- **Effort:** low–medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `computePauseToggle` (`frontend/src/lib/components/compare/subscriptionHelpers.ts:280`) | Funktion | Ermittelt naechsten `schedule`/`previous_schedule`-Zustand aus einem Preset — wird weiterhin unveraendert wiederverwendet, jetzt mit frischem statt stalem Input |
| `buildToggleActivePutPayload` (`frontend/src/lib/components/compare/compareHubWizardBridge.ts:185`) | Funktion | Baut `{ url, body }` fuer den PUT — bereits geteilter Baustein, heute nur von `CompareTabs.svelte` genutzt; #1259 macht ihn zum EINZIGEN Payload-Bauer fuer BEIDE Kebab-Vorkommen (Hub + Liste) |
| `GET /api/compare/presets/{id}` (`internal/handler/compare_preset.go`, `GetComparePresetHandler`) | Backend-Endpoint | Liefert den frischen Server-Stand vor dem Schreiben — existiert bereits, wird bislang vom Listen-Toggle nicht aufgerufen |
| `PUT /api/compare/presets/{id}` (`internal/handler/compare_preset.go`, `UpdateComparePresetHandler`) | Backend-Endpoint | Nimmt den PUT-Body entgegen; macht serverseitig einen per-Feld nil-Preserve-Merge, der aber nicht greift, wenn der Client (wie bisher) veraltete Werte explizit mitsendet |
| `ComparePreset` Typ (`frontend/src/lib/types.ts`) | Typ | Struktur des Presets, unveraendert |
| `CompareTabs.handleToggleActive` (`frontend/src/lib/components/compare/CompareTabs.svelte:560`) | Referenz-Implementierung | Vorbild fuer frische Baseline vor PUT — loest bisher nur den Ein-Tab-Hub-Fall, nicht den Listen-Fall |

## Implementation Details

Neuer, injizierbarer Helper in `compareHubWizardBridge.ts` (Name exemplarisch,
Signatur ist der bindende Teil der Spec):

```typescript
export async function buildFreshTogglePutPayload(
  presetId: string,
  getPreset: (id: string) => Promise<ComparePreset>
): Promise<{ url: string; body: ComparePreset }> {
  const fresh = await getPreset(presetId);
  const next = computePauseToggle(fresh);
  return buildToggleActivePutPayload(
    fresh,
    next.schedule,
    next.previous_schedule ?? fresh.schedule
  );
}
```

`getPreset` ist injizierbar (kein hartcodiertes `fetch`) — das macht den Flow
im Kern-Test ohne DOM/Browser deterministisch pruefbar, analog zum
bestehenden `simulatedPut`-Muster in
`frontend/src/lib/components/compare/__tests__/kebab_toggle_delegation.test.ts`.

`CompareGrid.svelte` `togglePause` wird zur duennen Delegation (GET → Helper
→ PUT → Zeile aus PUT-Response aktualisieren, NICHT aus dem lokal berechneten
`next`):

```javascript
async function togglePause(preset) {
  error = null;
  try {
    const { url, body } = await buildFreshTogglePutPayload(preset.id, async (id) => {
      const res = await fetch(`/api/compare/presets/${id}`);
      if (!res.ok) throw new Error(`GET failed: ${res.status}`);
      return res.json();
    });
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`PUT failed: ${res.status}`);
    const updated = await res.json();
    presets = presets.map((p) => (p.id === preset.id ? updated : p));
  } catch {
    error = 'Status-Änderung fehlgeschlagen. Bitte versuche es erneut.';
  }
}
```

Wichtig: Die Listen-Zeile wird aus der **PUT-Response** aktualisiert, nicht
aus dem lokal in `CompareGrid` berechneten `next` — sonst wuerde die UI
selbst wieder einen stale-Zustand anzeigen, obwohl der Server bereits den
korrekten (gemergten) Stand haelt.

## Verworfene Alternativen

**Minimal-Body `{ schedule, previous_schedule }` statt GET-vor-PUT:** wurde
verworfen. `name`, `location_ids`, `region` und `weekday` stehen NICHT im
serverseitigen nil-Preserve-Block von `UpdateComparePresetHandler` — ein
Minimal-Body wuerde diese Felder serverseitig leeren bzw. an der Validierung
mit 400 scheitern. Diese Alternative braeuchte zusaetzlichen Backend-Ausbau
(groesserer Blast Radius, Aenderung an einem geteilten Handler, der auch vom
Hub-Pfad genutzt wird). GET-vor-PUT ist rein Frontend-seitig, aendert den
Server-Vertrag nicht und wiederverwendet ausschliesslich bestehende, bereits
geteilte Bausteine.

## Expected Behavior

- **Input:** Klick auf den Kebab-Menuepunkt "Pausieren"/"Aktivieren" in einer
  Vergleichs-Kachel der `/compare`-Liste
- **Output:** Ein `GET /api/compare/presets/{id}` gefolgt von einem
  `PUT /api/compare/presets/{id}`, dessen Body aus dem GET-Ergebnis (nicht
  aus der Listen-Prop) gebaut wird; die Listen-Zeile zeigt danach den
  Server-Antwort-Stand
- **Side effects:** Zwei statt bisher ein Netzwerk-Roundtrip pro Toggle-Klick
  (siehe Known Limitations); kein Aenderung am Backend-Vertrag

## Acceptance Criteria

- **AC-1:** Given ein Vergleich, dessen Detail-Hub serverseitig frische
  Felder gesetzt hat (z.B. Korridore/Idealwerte oder Versand-Konfiguration),
  und eine Listen-Ansicht mit veraltetem Snapshot desselben Vergleichs /
  When der Listen-Kebab "Pausieren"/"Aktivieren" ausgeloest wird / Then
  bleiben die vom Hub gesetzten Felder unveraendert erhalten, weil der
  Toggle vor dem Schreiben den frischen Server-Stand liest.
  - Test: Deterministischer Kern-Test (`node:test`, echte Funktionen aus
    `compareHubWizardBridge.ts`, simulierter Server der PUT-Bodies wie das
    echte Backend mergt) beweist, dass nach dem Listen-Toggle die zuvor
    server-seitig gesetzten Hub-Felder unveraendert im simulierten
    Server-Zustand stehen — rot vor dem Fix (Voll-Spread aus stale Prop
    macht die Hub-Aenderung rueckgaengig), gruen nach dem Fix.

- **AC-2:** Given nur die Vergleichs-Liste ist geoeffnet, kein zweiter Tab
  mit Aenderungen dazwischen / When der Nutzer nacheinander Pausieren, dann
  Aktivieren klickt / Then wechselt `schedule` korrekt manual↔previous und
  der urspruengliche `previous_schedule`-Rhythmus (Issue #631) bleibt
  erhalten — das Ein-Tab-Verhalten ist nach dem Fix identisch zu vorher.
  - Test: Kern-Test ruft den neuen Helper zweimal hintereinander mit
    demselben simulierten Ein-Tab-Server auf und prueft, dass
    `schedule`/`previous_schedule` nach dem zweiten Aufruf wieder dem
    Ausgangszustand entsprechen (z.B. `daily` → `manual` → `daily`).

- **AC-3:** Given der GET- oder der PUT-Aufruf des Toggle-Flows schlaegt fehl
  (z.B. Netzwerkfehler oder Nicht-2xx-Status) / When der Nutzer den Kebab
  bedient / Then erscheint die bestehende Fehlermeldung ("Status-Änderung
  fehlgeschlagen. Bitte versuche es erneut.") und die Listen-Zeile bleibt
  unveraendert beim alten Status — kein stiller Teil-Schreibvorgang, keine
  optimistische UI-Aktualisierung ohne bestaetigten Server-Stand.
  - Test: Kern-Test mit einem simulierten `getPreset`, das rejected (bzw.
    einer simulierten PUT-Funktion, die einen Fehler wirft), prueft, dass
    der Helper die Exception propagiert statt einen Payload zurueckzugeben,
    und dass in `CompareGrid` das reale Klickverhalten (Playwright/E2E
    ausserhalb dieser Spec optional) die Fehlermeldung zeigt und den alten
    Zeilenstatus nicht veraendert.

## Known Limitations

- Zwei Netzwerk-Roundtrips (GET dann PUT) statt bisher einem — minimal
  hoehere Latenz beim Klick, fachlich vernachlaessigbar fuer einen seltenen
  Toggle-Klick.
- Theoretisches Race-Window zwischen GET und PUT bleibt bestehen (ein
  dritter Schreibvorgang koennte exakt in diesem kurzen Fenster passieren);
  dieselbe Restklasse existiert auch nach dem Hub-Fix aus #1256 und ist
  fuer diesen seltenen Bedienfall (manueller Klick, kein Hochfrequenz-Pfad)
  akzeptiert — keine serverseitige Concurrency-Kontrolle (z.B. ETag/If-Match)
  im Scope dieser Spec.
- Der `hubPutQueue`-Mechanismus aus `CompareTabs.svelte` wird bewusst NICHT
  in die Liste uebernommen — die Liste hat pro Zeile hoechstens einen
  aktiven Toggle-Klick, eine Warteschlange waere unnoetige Komplexitaet.
- Andere potenzielle Voll-Spread-aus-stale-Prop-Stellen ausserhalb des
  Listen-Kebabs sind nicht Teil dieser Spec (siehe Referenz-Fixes #1256
  F004/F007 fuer den Hub-Kebab).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix innerhalb einer bestehenden, bereits
  geteilten Architektur (Compare-Payload-Helper in
  `compareHubWizardBridge.ts`). Kein neues Architekturmuster, kein
  Backend-Vertragswechsel, keine neue Abhaengigkeit — daher kein ADR
  erforderlich.

## Changelog

- 2026-07-15: Initial spec created — Issue #1259

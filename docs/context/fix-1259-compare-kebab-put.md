# Context: fix-1259-compare-kebab-put

Issue #1259 · Track: Standard (`feature`) · Kategorie: Datenverlust (Nebenbefund-Triage b)

## Request Summary

Der Kebab-Toggle „Pausieren/Aktivieren" in der Vergleichs-**Listen**-Ansicht
(`/compare`) baut seinen PUT-Body als vollen Spread `{ ...preset, ...next }` aus
dem beim Seitenaufruf geladenen (potenziell veralteten) Listen-Zustand. Sind
Liste und Detail-Hub desselben Vergleichs in zwei Tabs offen, überschreibt ein
Kebab-Toggle in der Liste eine zwischenzeitliche Hub-Änderung mit veralteten
Feldern → stiller Server-Datenverlust. Gleiche Fehlerklasse wie F004/F007 aus
#1256 (dort im Hub bereits behoben).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/CompareGrid.svelte` (`togglePause`, Z. 56–71) | **Bug-Ort.** `fetch` mit `body: JSON.stringify({ ...preset, ...next })` — voller Spread aus stale Prop, kein GET-vor-PUT, keine Queue |
| `frontend/src/routes/compare/+page.server.ts` (Z. 11–20) | Lädt `presets` einmalig beim Navigieren aus `GET /api/compare/presets` → Snapshot, wird bei fremd-Tab-Edit stale |
| `frontend/src/routes/compare/+page.svelte` (Z. 12, 92) | Reicht `bind:presets` an `CompareGrid` durch |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` (`buildToggleActivePutPayload` Z. 185, `createPutQueue` Z. 320) | **Fix-Baustein (geteilt).** Baut Toggle-Payload; heute nur von `CompareTabs` genutzt |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` (`computePauseToggle` Z. 280) | Reine Funktion: liefert `{ schedule, previous_schedule }` beim Toggle. Bereits von `CompareGrid` importiert |
| `frontend/src/lib/components/compare/CompareTabs.svelte` (`handleToggleActive` Z. 560, `hubPutQueue` Z. 164) | **Referenz-Fix (F004/F007):** frische `currentPreset`-Baseline + `hubPutQueue`, delegiert über `buildToggleActivePutPayload` |
| `internal/handler/compare_preset.go` (`UpdateComparePresetHandler` Z. 242–392, `GetComparePresetHandler` Z. 470) | Server-PUT: **per-Feld nil-Preserve-Merge** (fehlendes Feld → Original), aber Voll-Spread mit stale Werten defeatet den Schutz. GET-Endpoint vorhanden |

## Existing Patterns

- **Fresh-Baseline-vor-PUT** (Hub, `CompareTabs.handleToggleActive`): Payload aus
  laufend aufgefrischter `currentPreset`, serialisiert über `hubPutQueue`. Löst
  aber nur den **Ein-Tab**-Fall — eine In-Memory-JS-Queue kennt keinen zweiten
  Browser-Tab.
- **Server-seitiger nil-Preserve-RMW** (`UpdateComparePresetHandler`): jedes
  optionale Feld wird aus dem Original erhalten, *wenn es im Body fehlt* (nil
  nach Decode). Greift NICHT, wenn der Client das Feld mit einem (veralteten)
  Wert mitsendet — genau das tut der Voll-Spread.
- **Geteilter Toggle-Baustein**: `computePauseToggle` (pure) +
  `buildToggleActivePutPayload` (Bridge). Der Fix soll diese wiederverwenden,
  keine Kopie (Trip/Compare-Teilungs-Invariante).

## Dependencies

- **Upstream (nutzt der Fix):** `GET /api/compare/presets/{id}`,
  `PUT /api/compare/presets/{id}`, `computePauseToggle`,
  `buildToggleActivePutPayload`, `api`-Client (`$lib/api.js`).
- **Downstream (nutzt den Bug-Ort):** `/compare`-Übersicht (`CompareTile`-Kebab).

## Existing Specs

- `docs/specs/modules/issue_1256_compare_ui_rewire.md` § Scheibe 7 — F004-Fix im Hub
- `docs/specs/modules/issue_490_compare_grid.md` — CompareGrid-Ursprung
- `docs/specs/modules/issue_631_pause_rhythm.md` (falls vorhanden) — `computePauseToggle`

## Lösungsrichtung (für Phase Spec)

**GET-vor-PUT (Client-RMW) in `CompareGrid.togglePause`** — bevorzugt:
1. Bei Klick frisch `GET /api/compare/presets/{id}` holen (enthält fremd-Tab-Edits).
2. `computePauseToggle(fresh)` → neuer Schedule.
3. `buildToggleActivePutPayload(fresh, schedule, previous_schedule)` → PUT.
4. Lokale Listen-Zeile aus der PUT-Response aktualisieren.

Vorteile: rein Frontend (kleiner Deploy-Scope), kein Backend-Merge-Ausbau nötig,
wiederverwendet die geteilten Bausteine. Der volle Spread bleibt verlustfrei,
weil er auf frischen Server-Werten basiert.

**Verworfen — Minimal-Body `{ schedule, previous_schedule }`:** unsicher, weil
`name`/`location_ids`/`region`/`weekday` NICHT im server-seitigen nil-Preserve-
Block stehen; ein Minimal-Body würde diese leeren (bzw. 400 an der Validierung)
→ bräuchte zusätzlichen Backend-Ausbau, größerer Blast Radius.

## Risks & Considerations

- **Testbarkeit:** `togglePause` ist heute inline im Svelte-Component. Für einen
  deterministischen Kern-Test (node:test, echte Bridge-Funktionen, simulierter
  Server wie in `kebab_toggle_delegation.test.ts`) sollte der GET→compute→PUT-
  Flow in eine testbare Helper-Funktion in der Bridge extrahiert werden. RED:
  zwei „Tabs" (stale Listen-Prop vs. frischer Hub-Server-Stand) — Beweis, dass
  der Toggle den Hub-Edit erhält statt zu überschreiben.
- **Ein-Tab-Verhalten darf sich nicht ändern:** Pause/Aktivieren im Normalfall
  (nur Liste offen) muss weiter funktionieren; `previous_schedule`-Rhythmus
  (#631) bleibt erhalten.
- **Zusätzlicher GET pro Toggle:** minimaler Latenz-Aufschlag, akzeptabel für
  eine seltene, bewusste Nutzeraktion; Fehlerpfad (GET schlägt fehl) muss die
  bestehende `error`-Anzeige nutzen, nicht stumm scheitern.
- **Teilungs-Invariante:** kein Trip-Pendant für diesen Toggle vorhanden — der
  geteilte Baustein ist die Bridge-Funktion, die wiederverwendet wird.

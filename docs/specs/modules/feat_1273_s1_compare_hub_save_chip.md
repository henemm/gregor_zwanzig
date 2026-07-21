---
entity_id: feat_1273_s1_compare_hub_save_chip
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [frontend, compare, save-status, epic-1273, save-indicator]
workflow: epic-1273-compare-one-surface
---

<!-- Issue #1273 — Epic: Ortsvergleich auf EINE Fläche wie beim Trip. Diese Spec deckt NUR Slice S1 ab
     (Save-Chip-Infra). S2 (Name/Region/Aktivitätsprofil-Parität), S3 (Link-Umbiegung + Redirect),
     S4a/S4b (Test-Migration) und S5 (CompareEditor-Löschung) sind eigene, spätere Specs.
     Kontext: docs/context/epic-1273-compare-one-surface.md, Abschnitt "## Analysis". -->

# Spec: #1273 Slice S1 — Compare-Hub: geteilter Save-Chip

## Approval

- [x] Approved — PO Henning, 2026-07-16 (Freigabe "freigabe" nach Vorlage der 4 ACs inkl. Known Limitations)

## Purpose

Der Ortsvergleich-Hub (`CompareTabs.svelte`) bekommt den gleichen „✓ Gespeichert HH:MM"-Anzeige-Chip wie die Tour-Bearbeitung (`SaveIndicator.svelte` + `SaveStatus`), damit der Nutzer beim Bearbeiten eines Ortsvergleichs jederzeit ehrlich sieht, ob eine Änderung tatsächlich zum Server durchgereicht wurde. Diese Slice ist reine additive Infrastruktur: **kein** Redirect, **keine** Feldmigration, **keine** Testlöschung, **keine** Änderung am bestehenden Speicherverhalten selbst (die 5 Commit-Handler bleiben strukturell erhalten). Sie ist die Voraussetzung dafür, dass der Hub in S2–S5 schrittweise zur einzigen Bearbeiten-Fläche werden kann (PO-Entscheid, Prod-Audit Befund 9, 2026-07-16) und erfüllt sofort sichtbar die Trip/Compare-Teilungs-Invariante (CLAUDE.md): kein neuer Compare-eigener Baustein, sondern Verdrahtung des bestehenden geteilten `SaveStatus`/`SaveIndicator`-Paars in eine dritte Fläche.

## Source

- **File:** `frontend/src/routes/compare/[id]/+page.svelte`
  - **Identifier:** neue `const hubSaveCtl = createSaveStatus();`
- **File:** `frontend/src/lib/components/compare/CompareDetail.svelte`
  - **Identifier:** Thin-Shell-Pass-through — neue `saveController`-Prop, unverändert an `CompareTabs` durchgereicht (kein eigenes Verhalten, analog `onScheduleChange`-Präzedenz in derselben Datei)
- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
  - **Identifier:** neue `saveController`-Prop + `<SaveIndicator>`-Render; geänderte Handler `persistPickedIds()`, `handleCorridorCommit()`, `handleVersandCommit()`, `handleAlarmeCommit()`, `handleToggleActive()`

> **PFLICHT — Schicht-Hinweis:** Ausschließlich **Frontend** (`frontend/src/...`, SvelteKit, produktive Oberfläche auf gregor20.henemm.com). Go-API (`internal/handler/compare_preset.go`) und Python-Core sind **nicht betroffen** — es wird kein neuer Endpoint gebraucht, die 5 bestehenden `PUT`-Aufrufe bleiben unverändert in Ziel-URL und Payload-Bau (`buildHubPutPayload`, `flushPendingCorridorSave`, `flushPendingVersandSave`, `flushPendingAlarmSave`, `buildToggleActivePutPayload` — alle unverändert in `compareHubWizardBridge.ts`).

## Estimated Scope

- **LoC:** ~100–150 (Produktivcode, ohne Tests). Bewusst unter der Kontext-Schätzung von ~120–180, da keine neuen Dateien/Bausteine entstehen, nur Verdrahtung.
- **Files:** 3 geändert (`+page.svelte`, `CompareDetail.svelte`, `CompareTabs.svelte`), 0 neu. Dazu 1 neue Playwright-Testdatei.
- **Effort:** low–medium.

LoC-Limit 250/Workflow: unkritisch, kein Override erwartet.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` (`SaveStatus`, `createSaveStatus`, `extractMessage`, `markPristine`) | geteilter Baustein, **unverändert** | Zustandsmaschine für den Chip; `markPristine()` (aus #1269) wird hier zum ersten Mal für einen No-Op-Commit (kein Diff, kein PUT nötig) genutzt — genau der Anwendungsfall, für den sie gebaut wurde |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | geteilter Baustein, **unverändert** | Rendert den Chip; `position: fixed`, daher beliebige Mount-Stelle innerhalb `CompareTabs.svelte` ausreichend |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` (`createPutQueue`/`hubPutQueue`, `buildHubPutPayload`, `flushPending*Save`, `buildToggleActivePutPayload`) | geteilter Compare-Baustein, **unverändert** | Bleibt die Serialisierungs- und Payload-Schicht; wird NICHT durch `saveController.schedule()` ersetzt (Datenverlust-Risiko, s. Implementation Details) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:18,27-31,192-195` | Referenzmuster, **nicht geändert** | Zeigt das etablierte Prop-Muster (`saveController?: SaveStatus`, `{#if saveController}<SaveIndicator .../>{/if}`) |
| `weatherSaveGate.ts` / `compareAutosave.ts` | — | **Nicht relevant für S1.** Die 5 Hub-Handler sind bereits event-diskretisiert (direkte `onclick`/`onchange`/`onfocusout`-Handler, kein Mount-`$effect`, der ungewollt schreiben könnte) — das Schreib-Gate-Problem, das #1234/#1269 für Mount-Effekte lösen, tritt hier strukturell nicht auf. Keine Anbindung nötig. |

## Implementation Details

**1. Instanziierung (Routen-Ebene, analog `tripSaveCtl`):**

```
// frontend/src/routes/compare/[id]/+page.svelte
import { createSaveStatus } from '$lib/stores/saveStatusStore.svelte';
const hubSaveCtl = createSaveStatus();
// ... an <CompareDetail ... saveController={hubSaveCtl} /> durchreichen
```

**2. Pass-through (Thin-Shell, keine eigene Logik):**

```
// frontend/src/lib/components/compare/CompareDetail.svelte
interface Props {
  preset: ComparePreset;
  locations: Location[];
  initialTab?: string;
  onScheduleChange?: (schedule: string) => void;
  saveController?: SaveStatus;   // NEU
}
// <CompareTabs {preset} {locations} {initialTab} {onScheduleChange} {saveController} bind:this={tabs} />
```

**3. Chip-Render + Prop in `CompareTabs.svelte`:**

```
import SaveIndicator from '$lib/components/ui/SaveIndicator.svelte';
import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
import { extractMessage } from '$lib/stores/saveStatusStore.svelte';

interface Props {
  // ...bestehende Felder unverändert...
  saveController?: SaveStatus;   // NEU
}
// im Markup (beliebige Stelle, SaveIndicator ist position:fixed):
// {#if saveController}<SaveIndicator controller={saveController} />{/if}
```

**4. Die 5 Commit-Handler — WICHTIG, zwei strukturell unterschiedliche Fälle:**

**Nicht** `hubPutQueue` durch `saveController.schedule()` ersetzen (Datenverlust-Risiko: `schedule()` hat nur einen Pending-Slot, ein zweiter Aufruf innerhalb der Debounce-Zeit würde einen noch nicht gefeuerten Save eines anderen Tabs ersatzlos verwerfen — exakt das Szenario, vor dem #1269 gerade erst geschützt hat). Stattdessen bleibt `hubPutQueue` unverändert für die Netzwerk-Korrektheit; `saveController` wird manuell getrieben.

**Fall A — `persistPickedIds()` und `handleToggleActive()` (kein No-Op-Pfad, jeder Aufruf versucht immer einen PUT):**

- `persistPickedIds()`: der `try`/`catch` liegt **innerhalb** des `hubPutQueue.enqueue(...)`-Closures und fängt den Fehler dort ab (Rollback, `console.error`, `return null`). Der äußere `await` wirft daher **nie** — ein simples äußeres `try/catch` (wie es die naive Lesart „umschließen" nahelegen könnte) würde `setError()` **nie** erreichen. Notwendig: den gefangenen Fehler in einer außerhalb des Closures deklarierten Variable festhalten:

  ```
  async function persistPickedIds(newIds: string[]): Promise<void> {
    currentLocationIds = newIds;
    let failure: unknown = null;                    // NEU
    saveController?.setSaving();                     // NEU
    const updated = await hubPutQueue.enqueue(async () => {
      try {
        const { url, body } = buildHubPutPayload(currentPreset, { pickedIds: newIds });
        const result = await api.put<ComparePreset>(url, body);
        lastPersistedLocationIds = newIds;
        return result;
      } catch (e) {
        console.error('[CompareTabs] Orte-Persistenz fehlgeschlagen, Rollback:', e);
        currentLocationIds = lastPersistedLocationIds;
        failure = e;                                  // NEU (1 Zeile, kein Verhaltenswechsel)
        return null;
      }
    });
    if (updated) {
      currentPreset = updated;
      saveController?.setSaved();                     // NEU
    } else if (failure) {
      saveController?.setError(extractMessage(failure)); // NEU
    }
  }
  ```

- `handleToggleActive()`: hier liegt der `try`/`catch` bereits **außerhalb** von `hubPutQueue.enqueue(...)` (einziger der 5 Handler mit dieser Struktur) — ein echter Fehler propagiert normal nach außen. Wrapping ist hier direkt:

  ```
  async function handleToggleActive(): Promise<boolean> {
    // ...unverändert bis vor try...
    saveController?.setSaving();                       // NEU
    try {
      currentPreset = await hubPutQueue.enqueue(async () => { /* unverändert */ });
      localSchedule = next;
      onScheduleChange?.(next);
      saveController?.setSaved();                      // NEU
      return true;
    } catch (e) {
      console.error('[CompareTabs] toggleActive failed:', e);
      saveController?.setError(extractMessage(e));      // NEU
      return false;
    }
  }
  ```

**Fall B — `handleCorridorCommit()`, `handleVersandCommit()`, `handleAlarmeCommit()` (haben einen No-Op-Pfad: `if (!payload) return null;` VOR dem try, wenn der Diff-Check keine Änderung findet):**

Hier ist `updated === null` **doppeldeutig** — sowohl „kein Diff, gar kein PUT versucht" (No-Op, z. B. `onfocusout` ohne Wertänderung) als auch „PUT versucht und fehlgeschlagen" führen zu `null`. Ein no-op fälschlich als „Fehler beim Speichern" zu zeigen wäre selbst eine neue Speicher-Anzeige-Lüge (Regression ggü. #1269, AC-3). Dieselbe `failure`-Variable wie in Fall A trennt beide Fälle; der No-Op-Fall bekommt **`markPristine()`** (aus #1269, dirty→idle **ohne** `savedAt` neu zu stempeln — exakt für diesen Fall gebaut):

  ```
  async function handleCorridorCommit(): Promise<void> {
    if (!idealwerteHydrated) return;
    let failure: unknown = null;                       // NEU
    saveController?.setSaving();                        // NEU
    const updated = await hubPutQueue.enqueue(async () => {
      const current = currentCorridorSnapshot();
      const before = lastPersistedCorridorSnapshot ?? current;
      const payload = flushPendingCorridorSave(currentPreset, current, lastPersistedCorridorSnapshot);
      if (!payload) return null;                        // No-Op: failure bleibt null
      try {
        const result = await api.put<ComparePreset>(payload.url, payload.body);
        lastPersistedCorridorSnapshot = current;
        return result;
      } catch (e) {
        console.error('[CompareTabs] Wertebereich-Persistenz fehlgeschlagen, Rollback:', e);
        wizardState.corridors = before.corridors;
        wizardState.idealRanges = before.idealRanges;
        wizardState.activeMetricKeys = before.activeMetricKeys;
        wizardState.metricAlertLevels = before.metricAlertLevels;
        failure = e;                                    // NEU
        return null;
      }
    });
    if (updated) {
      currentPreset = updated;
      saveController?.setSaved();                       // NEU
    } else if (failure) {
      saveController?.setError(extractMessage(failure)); // NEU
    } else {
      saveController?.markPristine();                    // NEU — No-Op, keine Lüge
    }
  }
  ```

  Identisches Muster für `handleVersandCommit()` und `handleAlarmeCommit()` (gleiche Struktur: `if (!payload) return null;` vor `try`, `catch` mit Rollback und `return null`).

**Zusammenfassung der Diff-Regel pro Handler:**

| Handler | No-Op-Pfad? | `updated` truthy | `updated` falsy + `failure` gesetzt | `updated` falsy + `failure` null |
|---|---|---|---|---|
| `persistPickedIds` | nein | `setSaved()` | `setError(...)` | (tritt nicht auf) |
| `handleCorridorCommit` | ja | `setSaved()` | `setError(...)` | `markPristine()` |
| `handleVersandCommit` | ja | `setSaved()` | `setError(...)` | `markPristine()` |
| `handleAlarmeCommit` | ja | `setSaved()` | `setError(...)` | `markPristine()` |
| `handleToggleActive` | nein (eigene try/catch-Struktur) | `setSaved()` | `setError(...)` | (tritt nicht auf) |

**5. `beforeNavigate`-Flush-Guard: ENTSCHEIDUNG — entfällt in S1.**

Offene Frage aus der Analyse-Phase, hier entschieden: Der Trip-Guard (`routes/trips/[id]/+page.svelte:25-34`) existiert, weil `tripSaveCtl.schedule()` einen echten Debounce-Timer setzt, der bei Navigation noch nicht gefeuert haben kann (`hasPending`/`flush()` operieren auf genau diesem Timer). `hubSaveCtl` wird in S1 **nie** über `schedule()` getrieben (s. Punkt 4) — `setSaving()`/`setSaved()`/`setError()`/`markPristine()` setzen keinen Timer. `hubSaveCtl.hasPending` ist damit strukturell **immer `false`**; ein Guard nach Trip-Vorbild wäre toter Code, der nie greift. Die eigentliche Netzwerk-Sicherheit kommt weiterhin von `hubPutQueue`: die 5 Handler sind event-diskretisiert (`onfocusout`/`onclick`/`onchange`, kein Debounce) und `await`en ihren PUT synchron im selben Tick, bevor der Nutzer typischerweise wegnavigiert. Kein Flush-Guard in S1 — falls ein künftiger Slice `schedule()` für den Hub einführt, muss der Guard dann nachgezogen werden (Known Limitation, s. u.).

## Expected Behavior

| Situation | Verhalten |
|---|---|
| Hub-Seite öffnen (`/compare/[id]`) | Chip zeigt sofort „✓ Gespeichert" (kein initialer Zeitstempel nötig — `idle` ohne `savedAt` rendert den Chip ohne Zeit, s. `SaveIndicator.svelte:32-34`) |
| Tab wechseln, nichts ändern | Chip bleibt „✓ Gespeichert" — kein Handler feuert bei reinem Tab-Wechsel (kein Mount-`$effect` treibt `saveController`) |
| Nutzer entfernt einen Ort (Orte-Tab) | Chip-Verlauf „Speichere …" → „✓ Gespeichert HH:MM" (echter PUT über `persistPickedIds`) |
| Nutzer verlässt ein Zahlenfeld im Wertebereiche-/Versand-/Alarme-Tab **ohne** den Wert zu ändern (`onfocusout` ohne Diff) | Chip bleibt „✓ Gespeichert" (oder geht von „Speichere…" zurück auf „✓ Gespeichert" mit **altem** Zeitstempel) — kein PUT, kein neuer Zeitstempel, kein „Fehler" |
| Nutzer ändert einen Wert im Wertebereiche-/Versand-/Alarme-Tab und verlässt das Feld | Chip-Verlauf „Speichere …" → „✓ Gespeichert HH:MM" |
| PUT schlägt fehl (z. B. Netzwerkfehler) bei einem der 5 Handler | Chip zeigt „! Fehler beim Speichern: …"; Rollback der 5 Handler bleibt wie bisher (UI fällt auf den letzten persistierten Stand zurück) |
| Aktivieren/Pausieren (Versand-Tab-Karte **oder** Kebab-Menü, beide über `handleToggleActive`) | Chip-Verlauf identisch zu jedem anderen Commit-Handler |

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet einen Ortsvergleich im Hub (`/compare/[id]`) / When die Seite fertig geladen ist / Then zeigt der Chip „✓ Gespeichert" (kein „● Nicht gespeichert", kein „Speichere…").
  - Test: Playwright/Staging — eingeloggt einen bestehenden Ortsvergleich öffnen, `[data-testid="save-indicator"]` lesen: `data-state="idle"`, Text enthält „Gespeichert".

- **AC-2:** Given der Chip zeigt „✓ Gespeichert" / When der Nutzer eine echte Änderung macht, die einen der 5 Commit-Handler auslöst (z. B. einen Ort im Orte-Tab entfernen) / Then durchläuft der Chip „Speichere…" → „✓ Gespeichert HH:MM", und nach Seiten-Neuladen ist die Änderung persistiert.
  - Test: Playwright/Staging — Ort entfernen, Chip-Zustand direkt danach (`data-state="saving"`) und nach Abschluss (`data-state="idle"` + Zeitstempel sichtbar) prüfen, Seite neu laden, Ort bleibt entfernt.

- **AC-3:** Given der Chip zeigt „✓ Gespeichert" mit einem Zeitstempel `T0` / When der Nutzer nur einen Tab wechselt oder ein Feld fokussiert/verlässt, **ohne** den Wert zu ändern / Then bleibt der Chip auf „✓ Gespeichert" mit **unverändertem** Zeitstempel `T0` — kein „● Nicht gespeichert" (Analogie zu #1269 AC-1) und kein neuer Zeitstempel ohne echten PUT (Analogie zu #1269 AC-2). Regressionsschutz: das Projekt hat #1269 (Speicher-Anzeige-Lüge) erst am selben Tag geschlossen; S1 darf keine neue Variante davon einführen.
  - Test: Playwright/Staging — Netzwerk-Mitschnitt aktiv. Wertebereiche-Tab öffnen, ein Zahlenfeld fokussieren und ohne Änderung wieder verlassen (`blur`/`onfocusout`), 2 s warten: **null** `PUT`-Requests im Mitschnitt, Chip-Zeitstempel identisch zu vorher. Wiederholung für Versand- und Alarme-Tab.

- **AC-4:** Given ein Commit-Handler löst einen echten PUT aus, der fehlschlägt (z. B. simulierter Netzwerkfehler) / When die Rollback-Logik des jeweiligen Handlers greift / Then zeigt der Chip „! Fehler beim Speichern" und der UI-Zustand fällt auf den letzten erfolgreich persistierten Stand zurück (kein stiller Datenverlust) — das bestehende Rollback-Verhalten der 5 Handler bleibt unverändert erhalten.
  - Test: Playwright/Staging — mit `page.route()` einen der 5 PUT-Endpunkte gezielt auf 500 stubben, die zugehörige Aktion auslösen (z. B. Ort entfernen), Chip-Zustand prüfen (`data-state="error"`, Text „Fehler beim Speichern"), UI-Feld zeigt wieder den alten Wert.

## Known Limitations

- **Name/Region/Aktivitätsprofil sind in dieser Slice weiterhin NICHT im Hub editierbar** — diese Felder existieren aktuell nur im separaten `CompareEditor.svelte` (`/compare/[id]/edit`). Das ist explizit **S2**-Scope (Feature-Paritäts-Lücke, Muss-Blocker vor jedem Redirect in S3). S1 rührt daran nicht.
- **Kein `beforeNavigate`-Flush-Guard.** Bewusste Entscheidung (s. Implementation Details Punkt 5): `hubSaveCtl` nutzt in S1 nie `schedule()`, `hasPending` ist strukturell immer `false`. Falls ein späterer Slice `schedule()`-Debouncing für den Hub einführt, muss der Guard dann nachgezogen werden.
- **Schmales Race-Fenster bei zwei nahezu gleichzeitigen Commits aus unterschiedlichen Tabs:** `hubPutQueue` serialisiert die Netzwerk-**Ausführung**, aber jeder Handler ruft `setSaving()` **synchron vor** dem `enqueue()`-Aufruf. Löst ein Nutzer z. B. binnen desselben Ticks einen Alarme-Commit und kurz danach (noch bevor der erste in der Queue abgearbeitet ist) einen Versand-Commit aus, kann der Chip zwischen dem Abschluss des ersten und dem Abschluss des zweiten Commits kurz „✓ Gespeichert" zeigen, während der zweite Commit noch in der Queue wartet. Kein Datenverlust (die Queue garantiert, dass beide PUTs ausgeführt werden), aber der Chip ist für ein schmales Zeitfenster nicht 100 % aktuell. Nicht behoben in S1 (würde einen Pending-Zähler statt eines einzelnen `setSaving()`/`setSaved()`-Paars brauchen — höherer Eingriff als die additive Infra dieser Slice rechtfertigt); als Beobachtungspunkt für einen späteren Slice vermerkt, kein eigenes Issue (LOW/kosmetisch, Nebenbefund-Triage → Sammel-Eintrag #1199 falls in der Praxis beobachtet).
- **Rein clientseitiger Schutz.** Wie bei #1269/#1234: der Chip zeigt ehrlich an, was der Client tut; eine serverseitige Bestätigung ist nicht Teil dieser Slice.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Slice trifft keine neue Architektur-Entscheidung, sondern konsolidiert auf die bestehenden geteilten Bausteine `SaveStatus`/`createSaveStatus`/`markPristine` (#758/#880, um die No-Op-Transition aus #1269 erweitert) und `SaveIndicator.svelte`, die der Trip-Editor bereits vollständig und der Compare-Editor teilweise nutzt. Es entsteht **kein** vierter Sonderweg und **kein** Compare-eigener Baustein — genau die Trip/Compare-Teilungs-Invariante aus CLAUDE.md. Analog zur Begründung in `docs/specs/_archive/modules/issue_1269_save_status_lie.md` (ADR-Nr. dort ebenfalls „keine").

## Changelog

- 2026-07-16: Erstfassung (Slice S1 von Epic #1273). Basiert auf `docs/context/epic-1273-compare-one-surface.md` Abschnitt „Analysis" (Technical Approach — Speicher-Modell: Kombination `hubPutQueue` + manuell getriebener `SaveStatus`, NICHT `schedule()`-Ersatz). Implementation Details löst zusätzlich die im Kontext-Dokument nicht explizit behandelte No-Op-vs-Fehler-Doppeldeutigkeit von `updated === null` in `handleCorridorCommit`/`handleVersandCommit`/`handleAlarmeCommit` auf (via `markPristine()`) und entscheidet die offene Frage zum `beforeNavigate`-Guard (entfällt in S1).

---
entity_id: rework_2276_s3_wertebereiche
type: refactor
created: 2026-09-19
updated: 2026-09-19
status: implemented
version: "1.0"
tags: [compare, trips, wertebereiche, persistenz]
---

# Wertebereiche-Reiter speichert selbst wie bei der Trip (Issue #2276, Scheibe S3, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich-Hub speichert der Wertebereiche-Reiter (Korridore/Idealwerte)
heute über **zwei parallele, sich teilweise überschneidende Wege**: einen
reaktiven Pfad direkt im Editor und einen zweiten über einen Wrapper am
Reiter-Rand, der bei Klick/Fokusverlust/Loslassen der Maus zusätzlich
auslöst. Beide Wege können bei derselben Bedienung feuern — ein bekannter,
bislang bewusst nicht behobener Doppel-Speichervorgang. Diese Scheibe führt
den Wertebereiche-Reiter auf **genau einen** Speicherweg zurück — analog zu
Scheibe S2 (Alarme), aber zusätzlich mit dem Aufräumen des zweiten,
überflüssigen Weges. Nutzersichtbarer Nebeneffekt: schlägt ein
Speichervorgang wegen eines zwischenzeitlichen fremden Änderns fehl
(Speicherkonflikt), zeigt der Ortsvergleich „Nochmal speichern" statt eines
generischen Fehlers — genau wie bei Alarme und bei der Trip. Zusätzlich wird
eine Lücke geschlossen, die durch S3 selbst erst entsteht: wechselt der
Nutzer schnell zwischen Alarme- und Wertebereiche-Reiter, teilen sich beide
künftig denselben Speicher-Platz — ohne Vorkehrung würde die zuerst
eingetragene Änderung von der zweiten überschrieben und ginge verloren. Am
Verhalten der Anlege-Seite (`/compare/new`) und der übrigen vier Reiter
ändert sich nichts.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`
  (analog `CorridorEditorMobile.svelte`),
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare/korridorCommit.ts`,
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts`
- **Identifier:** `CorridorEditor`/`CorridorEditorMobile` (Svelte-Organismen),
  `maybeSchedule()` (:217-235), `handleCorridorCommit`/`baueKorridorCommit`
  (entfällt), `flushPendingCorridorSave`/`snapshotForRollback` (Corridor-Anteil
  wandert nach `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`)

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`, `frontend/src/routes/`, SvelteKit). Kein
Go-API- und kein Python-Core-Code in dieser Scheibe.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | CREATE | Neues Modul (Ordner-Konsistenz mit `corridorEditorState.ts`/`corridorMatch.ts`, bewusst nicht `shared/` Top-Level wie bei Alarme). Enthält `CorridorSnapshot`, `corridorSnapshotAus(ws)`, `baueWertebereichNutzlast(preset, current)` (Voll-Spread, `metricAlertLevels` live aus `current`, nicht aus `preset`), `flushPendingCorridorSave` (neue Fassung), `rollbackCorridorSnapshot`, `erstelleWertebereicheVergleichSpeicherung(opt)` → `{aenderungMelden()}` |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | Neue Props `preset`, `enqueueHubWrite`, `onCompareUpdate` (Signatur wie `AlarmeTab`). `onCompareCommit`-Prop entfällt. `maybeSchedule()`'s vergleich-Zweig (:217-235) ruft nach `syncToWizard()` `vergleichSpeicherung.aenderungMelden()` statt `saveController?.schedule(async (init) => onCompareCommit?.(init))` |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | MODIFY | Identische Änderung zu `CorridorEditor.svelte` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | `.hub-corridor-wrap`-Div mit `onfocusout`/`onclick`/`commitAusGeste` (:1331-1348) entfernt; `<svelte:window onpointerup={handleWindowPointerUp}>` (:450-453) entfernt; `handleCorridorCommit`/`baueKorridorCommit`-Aufruf (:408-435), `currentCorridorSnapshot`/`lastPersistedCorridorSnapshot` (:336-356) entfernt. Mount von `CorridorEditor`/`CorridorEditorMobile` bekommt die neuen Props. `handleValueChange` (:152-159) und der bestehende `sichereAlarmeVorReiterwechsel`-Aufruf werden zu einem **generischen, listenbasierten Flush-Guard** (Trip-Muster `TripTabs.svelte:145-176`) zusammengeführt, der beim Verlassen von `'alarme'` UND `'idealwerte'` flusht. `handleToggleActive()` (:916-935) ruft vorab denselben generischen Flush |
| `frontend/src/lib/components/compare/korridorCommit.ts` | DELETE | Vollständig entfernt, nachdem per `git grep` bestätigt ist, dass `CompareTabs.svelte` der einzige Importeur ist |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | MODIFY | `flushPendingCorridorSave` (alte Fassung) entfernt. `snapshotForRollback`/`hydrateWizardStateFromPreset` bleiben, sofern andere Verwender (Versand/Layout) sie weiterhin brauchen — vor dem Entfernen einzeln geprüft, nicht pauschal gelöscht |
| `frontend/src/lib/components/compare/__tests__/` (Corridor-Bestandstests) | MOVE → `frontend/src/lib/components/shared/corridor-editor/__tests__/` | Import auf `wertebereicheVergleichSpeicherung.ts` umgehängt, Zusicherungen (entfernte Metriken → „off", Datenerhalt bei Pass-Through-Korridoren) unverändert |
| `frontend/e2e/compare-wertebereiche-speichert-selbst.spec.ts` | CREATE | Muster `compare-alarme-speichert-selbst.spec.ts`: Reiterwechsel-Flush, Aktivieren/Pausieren-Flush, „Nochmal speichern" bei 412, EIN PUT pro Geste |
| `frontend/e2e/compare-hub-inline-edit.spec.ts` | KEEP (unverändert) | Muss nach Wrapper-Entfernung ohne Codeänderung weiterhin grün sein (Band-Drag-Release außerhalb des Wrapper-Subtrees, :267-320) |

`compareEditorSave.ts` (`buildComparePresetSavePayload`, Voll-Spread über
`original`) bleibt unverändert und wird vom neuen Wertebereiche-Zweig weiter
als Nutzlast-Baustein verwendet — identische Begründung wie S2 (Go-Merge-
Kernel mergt `display_config` nur auf Ebene 1).

## Estimated Scope

- **LoC:** Quellcode ≈ +250/−230 (inkl. Löschung `korridorCommit.ts` und
  Wrapper-Rückbau in `CompareTabs.svelte`); E2E-Datei zählt laut Konvention
  nicht ins LoC-Limit.
- **Files:** ~8 (3 Produktivdateien inkl. 1 neues Modul, 1 Löschung, 1
  Klebeschicht-Datei, 2 umgehängte Testdateien, 1 neue E2E-Spec).
- **Effort:** high. `loc_limit_override 500` ist zu Workflow-Beginn zu
  setzen (S2 brauchte dieselbe Ausnahme bei ähnlichem Zuschnitt, S3 hat
  zusätzlich zwei Rückbau-Dateien).
- **Risk Level:** HIGH — Persistenzfläche zusätzlich zur Entflechtung zweier
  bestehender Schreibpfade. Ein Mutations-Adversary muss beide historischen
  Pfade (reaktiv UND Wrapper) einzeln reaktivieren und prüfen, dass jeweils
  ein spezifischer Test rot wird.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `createSaveStatus({typ,id})` / `doSave` / `schedule` / `flush` / `retryConflict` (`saveStatusStore.svelte.ts`) | function/class | Geteilter Speicher-Controller der Route; `_pendingFn` ist ein EINZIGER Slot (:184-189) — nicht mehr Annahme, sondern gelesener Quellcode |
| `hubPutQueue` (`createPutQueue`, `CompareTabs.svelte`) | queue | bleibt bestehen für die übrigen vier Reiter; der Wertebereiche-PUT läuft über dieselbe Queue (Prop `enqueueHubWrite`) |
| `buildComparePresetSavePayload` (`compareEditorSave.ts`) | function | liefert weiterhin die Voll-Spread-Basis der Wertebereiche-Nutzlast |
| `alarmeVergleichSpeicherung.ts` / `sichereAlarmeVorReiterwechsel` (S2, live) | pattern/function | Vorbild für Modulform und für den neuen generischen Flush-Guard, der beide Selbst-Speicherer (`'alarme'`, `'idealwerte'`) abdeckt |
| `TripTabs.svelte:145-176` (generischer Flush-Guard über eine Liste von Reiter-Namen) | pattern | Vorbild für den listenbasierten Guard in `CompareTabs.handleValueChange`, statt einer zweiten reiter-spezifischen `sichereWertebereicheVorReiterwechsel`-Funktion |
| `CompareWizardState` (`compareWizardState.svelte.ts`) | type (nur `import type`) | `shared/` importiert weiterhin ausschließlich den **Typ** aus `compare/` — keine neue Laufzeitabhängigkeit |
| `korridorCommit.ts` (#2317) | Vorbild für `init`-Weiterreichung | Die Keepalive-Absicherung aus #2317 (Entladen-Fall) muss in die neue `saveFn`-Signatur übernommen werden, bevor die Datei gelöscht wird |

## Implementation Details

### Design-Entscheidungen

1. **Serialisierung über die bestehende Hub-Queue, kein zweiter Controller**
   — identisch zu S2. Die Wertebereiche-SaveFn läuft über `hubPutQueue.enqueue`
   (Prop `enqueueHubWrite`), setzt nach Erfolg `currentPreset` über
   `onCompareUpdate`.
2. **Nutzlast bleibt Voll-Spread** über `buildComparePresetSavePayload`.
   `metric_alert_levels` MUSS live aus `current.metricAlertLevels` (dem
   aktuellen `ws`-Wert) befüllt werden, nicht aus einer eingefrorenen
   `preset`-Kopie — sonst geht die Zusicherung „entfernte Metrik → aus"
   verloren, sobald eine Alarm-Änderung im selben Hub-Besuch dazwischenkommt.
3. **Genau ein Speicherweg statt zwei.** Der reaktive Pfad im Editor
   (`maybeSchedule()`) wird zum alleinigen Auslöser. Der DOM-Wrapper
   (`.hub-corridor-wrap` mit `onfocusout`/`onclick`) und der
   `<svelte:window onpointerup>`-Handler entfallen ersatzlos — das
   700ms-Debounce-Fenster von `saveController.schedule()` feuert unabhängig
   davon, in welchem DOM-Bereich die Bedienung endet.
4. **Genereller Flush-Guard statt zweiter Einzelreiter-Funktion.** Weil
   künftig zwei Reiter (`alarme`, `idealwerte`) denselben Ein-Platz-
   Speicher-Slot der Route teilen, wird `sichereAlarmeVorReiterwechsel`
   durch einen listenbasierten Guard (Trip-Muster) ersetzt, der beim
   Verlassen JEDES bekannten Selbst-Speicher-Reiters flusht — nicht durch
   eine zweite, fast identische `sichereWertebereicheVorReiterwechsel`.
5. **Rollback nur bei Nicht-412**, diff-basiert: ein Feld wird nur
   zurückgesetzt, wenn `ws` noch exakt den gescheiterten Wert trägt — sonst
   überschreibt ein Rollback einen zwischenzeitlichen Alarme-Edit an
   `metricAlertLevels`.
6. **Hydration-Reihenfolge als Korrektheitsvoraussetzung.** Die
   Orchestrierung wird erst nach abgeschlossener Hydration erzeugt
   (`untrack()`-Konstruktion, Bedingung inkl. `idealwerteHydrated`) — sonst
   diffed die erste Nutzerinteraktion gegen einen leeren Ausgangswert.
7. **`init`-Weiterreichung (Keepalive) bleibt erhalten** — die SaveFn-Signatur
   `(init?: RequestInit) => Promise<void>` reicht `init` an `api.put` durch,
   analog zur bisherigen `korridorCommit.ts`-Lösung aus #2317.
8. **Anlege-Seite bleibt unverändert.** `/compare/new` mountet
   `CorridorEditor` ohne `preset`/`saveController` — der neue Zweig bleibt
   dort strukturell inaktiv, Speichern läuft weiter über
   `wiz.saveNewPreset()`.
9. **Kein Laufzeit-Import aus `compareHubWizardBridge.ts` mehr** (analoge
   Grenze wie S2 AC-9) — ein Laufzeit-Import aus `compareEditorSave.ts` für
   `buildComparePresetSavePayload` ist ausdrücklich erlaubt (wie schon bei
   Alarme), da er nicht aus der Klebeschicht selbst stammt.

## Expected Behavior

- **Input:** Änderung eines Wertebereichs (Korridor/Idealwert) im
  Ortsvergleich-Hub, gleich ob per Zahlenfeld, Slider-Ziehen oder
  Metrik-Auswahl.
- **Output:** genau ein PUT auf `/api/compare/presets/{id}` mit der
  vollständigen, aktuellen Preset-Nutzlast; Anzeige „Gespeichert"; die
  aktualisierte Basis fließt über `onCompareUpdate` in `currentPreset`
  zurück.
- **Side effects:** bei einem Speicherkonflikt (412) wechselt der
  Speicher-Controller in den Zustand `conflict`, die Oberfläche zeigt
  „Nochmal speichern". Wechselt der Nutzer den Reiter oder pausiert/aktiviert
  den Ortsvergleich, während eine Wertebereiche-Änderung noch nicht gesendet
  wurde, wird sie vorher automatisch gesendet — unabhängig davon, ob
  gleichzeitig auch eine Alarm-Änderung aussteht.

## Acceptance Criteria

- **AC-1 (Einmal speichern statt zweimal):** Given der Nutzer öffnet den
  Wertebereiche-Reiter eines Ortsvergleichs und ändert einen Wert (z. B.
  zieht einen Korridor-Regler) / When die Bedienung abgeschlossen ist /
  Then erscheint „Gespeichert" nach genau einem Speichervorgang, nicht nach
  zwei — auch wenn die Maus dabei den Reiter-Bereich verlässt und dort
  losgelassen wird.
  - Test: Unit-Test, der `CorridorEditor` im `vergleich`-Kontext mit
    `saveController`/`enqueueHubWrite`/`onCompareUpdate` mountet, einen Wert
    ändert und am abgefangenen Netzverkehr **genau einen** PUT zählt.
  - Mutations-Gegenprobe: beide historischen Auslöser (reaktiver Pfad UND
    Wrapper-Pfad) einzeln wieder aktivieren ⇒ jeweils muss ein spezifischer
    Test (zweiter PUT gezählt) rot werden.

- **AC-2 (Wrapper und Fenster-Loslassen-Handler sind entfernt):** Given der
  Wertebereiche-Reiter ist umgestellt / When ein Nutzer die Maustaste
  außerhalb des Reiter-Bereichs loslässt, nachdem er dort einen Regler
  gezogen hat / Then wird die Änderung trotzdem gespeichert — aber über
  denselben einen Speicherweg wie jede andere Änderung, nicht über einen
  separaten Fenster-weiten Auffang-Mechanismus.
  - Test: bestehender E2E-Test `compare-hub-inline-edit.spec.ts:267-320`
    (Band-Drag-Release außerhalb des Wrapper-Subtrees) bleibt **ohne
    Codeänderung** grün.
  - Mutations-Gegenprobe: `saveController.schedule()`-Aufruf im reaktiven
    Pfad entfernen (ohne Wrapper-Ersatz) ⇒ Test wird rot, weil der PUT
    ausbleibt.

- **AC-3 (Entfernte Metrik bleibt „aus", auch mit gleichzeitiger
  Alarm-Änderung):** Given der Nutzer entfernt eine Metrikzeile im
  Wertebereiche-Reiter UND ändert im selben Hub-Besuch zusätzlich einen
  Alarm-Wert im Alarme-Reiter / When beide Änderungen gespeichert sind /
  Then bleibt die entfernte Metrik im gespeicherten Stand auf „aus"
  markiert — unabhängig davon, welcher der beiden Reiter zuletzt
  gespeichert hat.
  - Test: Unit-/Integrationstest, der beide Reiter im selben
    Wizard-Zustand mountet, eine Metrik im Wertebereiche-Reiter entfernt,
    dann eine echte Änderung im Alarme-Reiter auslöst, und den Endstand
    von `metric_alert_levels` im letzten PUT-Body prüft.
  - Mutations-Gegenprobe: `metricAlertLevels` aus einer eingefrorenen
    `preset`-Kopie statt live aus `ws` befüllen ⇒ Test wird rot.

- **AC-4 (Reiterwechsel Wertebereiche → Alarme verliert nichts):** Given
  der Nutzer ändert einen Wertebereich und wechselt sofort, vor Ablauf der
  Debounce-Zeit, in den Alarme-Reiter, wo er ebenfalls sofort einen
  Alarm-Wert ändert / When beide Änderungen abgeschlossen sind / Then sind
  **beide** Änderungen gespeichert — die Wertebereiche-Änderung geht nicht
  verloren, obwohl sich beide Reiter denselben Speicher-Platz teilen.
  - Test: Unit-Test/erweiterter `CompareTabs`-Test, der eine
    Wertebereiche-Änderung setzt, `handleValueChange` mit Zielreiter
    `alarme` aufruft, dort eine zweite Änderung setzt und beide PUTs
    (in der richtigen Reihenfolge, beide mit ihrem jeweiligen geänderten
    Wert) nachweist.
  - Mutations-Gegenprobe: den generischen Flush-Guard nur für `'alarme'`
    behalten, für `'idealwerte'` weglassen ⇒ Test wird rot, weil die
    Wertebereiche-Änderung beim Wechsel verloren geht.

- **AC-5 (Speicherkonflikt zeigt „Nochmal speichern", Wiederholen
  gelingt):** Given ein Wertebereiche-Speichervorgang schlägt mit einem
  Speicherkonflikt (412) fehl / When der Nutzer „Nochmal speichern"
  auslöst / Then wird die Änderung erneut gesendet, endet in
  „Gespeichert", und der geänderte Wertebereich bleibt in der Oberfläche
  sichtbar (kein Zurückspringen auf den alten Stand).
  - Test: Erweiterung der bestehenden Konflikt-Suite um einen Fall über
    `CorridorEditor`/`onCompareUpdate` bis zum `retryConflict()`-Aufruf.
  - Mutations-Gegenprobe: Rollback auch bei 412 auslösen (statt nur bei
    Nicht-412) ⇒ Test wird rot, weil die Änderung nach dem Konflikt
    verschwindet statt erhalten zu bleiben.

- **AC-6 (Pausieren/Aktivieren flusht ausstehende Wertebereiche-Änderung):**
  Given der Nutzer ändert einen Wertebereich und pausiert/aktiviert den
  Ortsvergleich sofort danach, vor Ablauf der Debounce-Zeit / When der
  Pausier-/Aktivier-Vorgang abgeschlossen ist / Then ist die
  Wertebereiche-Änderung im gespeicherten Stand enthalten, nicht
  überschrieben durch den Pausier-/Aktivier-PUT.
  - Test: Unit-Test, der eine Wertebereiche-Änderung setzt,
    `handleToggleActive()` sofort danach aufruft und prüft, dass der
    resultierende PUT-Body den geänderten Wertebereich enthält.
  - Mutations-Gegenprobe: den vorab-`flush()`-Aufruf in
    `handleToggleActive()` entfernen ⇒ Test wird rot.

- **AC-7 (Kein Laufzeit-Import der alten Klebeschicht mehr):** Given der
  Wertebereiche-Speicherpfad ist umgestellt / When der Modulgraph geladen
  wird / Then lädt `shared/corridor-editor/CorridorEditor.svelte` zur
  Laufzeit kein Modul aus `compareHubWizardBridge.ts` mehr — die Helfer
  kommen aus `wertebereicheVergleichSpeicherung.ts`. Ein Laufzeit-Import
  von `buildComparePresetSavePayload` aus `compareEditorSave.ts` bleibt
  ausdrücklich zulässig.
  - Test: Ladegraph-Nachweis über `node --test`
    (`--experimental-test-module-mocks`), ein Mock auf
    `compareHubWizardBridge.ts` protokolliert Ladeaufrufe; beim Rendern von
    `CorridorEditor` im `vergleich`-Kontext darf der Mock nicht aufgerufen
    werden.
  - Mutations-Gegenprobe: einen Laufzeit-Re-Import der alten
    `flushPendingCorridorSave`-Fassung aus der Bridge-Datei einfügen ⇒ der
    Mock-Ladenachweis schlägt an, Test wird rot.

- **AC-8 (`korridorCommit.ts` ist gefahrlos gelöscht):** Given
  `korridorCommit.ts` wird entfernt / When der Modulgraph des gesamten
  Frontends gebaut wird / Then gibt es keinen verbleibenden Importeur
  dieser Datei.
  - Test: `git grep -rn "korridorCommit\|baueKorridorCommit"` liefert vor
    dem Löschen ausschließlich `CompareTabs.svelte` als Treffer; nach dem
    Löschen läuft `npm run build`/`svelte-check` ohne Fehler.

- **AC-9 (Anlege-Seite unverändert):** Given der Nutzer legt einen neuen
  Ortsvergleich an und bearbeitet den Wertebereiche-Reiter vor dem ersten
  Speichern / When er die Anlage abschließt / Then läuft der Speicherweg
  weiter ausschließlich über `wiz.saveNewPreset()` (POST), ohne
  zwischenzeitlichen PUT und ohne den neuen `saveController`-Zweig.
  - Test: bestehende Struktur-/Mount-Tests für die Anlege-Seite bleiben
    unverändert grün (Mount ohne `preset`/`saveController` bewirkt, dass
    der neue Zweig inaktiv bleibt).

- **AC-10 (Keepalive-Weiterreichung bleibt erhalten):** Given der Nutzer
  schließt den Tab unmittelbar nach einer Wertebereiche-Änderung / When der
  Browser den Entladen-Vorgang mit Keepalive auslöst / Then wird der
  `init`-Parameter der SaveFn an den `api.put`-Aufruf durchgereicht, statt
  verworfen zu werden.
  - Test: Erweiterung analog zu
    `trip_speicherung_reicht_keepalive_durch.test.ts`, angewandt auf die
    Wertebereiche-SaveFn im `vergleich`-Kontext.
  - Mutations-Gegenprobe: `init` in der SaveFn ignorieren (fester
    `undefined`-Aufruf an `api.put`) ⇒ Test wird rot.

- **AC-11 (Speichern der Wertebereiche verliert keine anderen Daten):**
  Given ein Ortsvergleich mit Orten, Versandzeiten, Kanälen, Alarm-Schwellen
  und Anzeige-Einstellungen / When der Nutzer im Wertebereiche-Reiter einen
  Korridor ändert und die Änderung gespeichert ist / Then sind nach erneutem
  Laden alle übrigen Einstellungen des Vergleichs unverändert erhalten und
  nur der geänderte Wertebereich weicht vom Ausgangsstand ab.
  - Test: Kern-Test auf `baueWertebereicheNutzlast` (Payload enthält alle
    Bestandsfelder aus `preset`, nur die Korridor-Felder sind neu) plus
    E2E-Schritt in der neuen Spec (GET vor/nach, Feldvergleich außer
    Korridor-Feldern).
  - Mutations-Gegenprobe: ein Bestandsfeld (z. B. `display_config.alert_channels`
    oder `schedule`) aus der Payload weglassen ⇒ Test wird rot.

- **AC-12 (Trip-Seite des geteilten Wertebereiche-Editors unverändert):**
  Given ein Trip mit Wertebereichen im Trip-Hub / When der Nutzer dort einen
  Korridor ändert / Then wird die Änderung wie bisher genau einmal über den
  Trip-Speicherweg gespeichert und erscheint nach erneutem Laden — der
  Umbau am Ortsvergleich verändert das Verhalten der Trip-Seite nicht.
  - Test: bestehende Trip-Korridor-Tests (Kern + E2E) bleiben grün; neuer
    Kern-Test, dass der `route`-Zweig von `CorridorEditor(Mobile).svelte`
    die neue Vergleichs-Speicherung nicht aufruft.
  - Mutations-Gegenprobe: Kontext-Prüfung im Editor entfernen, sodass der
    `route`-Zweig die Vergleichs-Speicherung auslöst ⇒ Test wird rot.

## Known Limitations

- **#2366** (Pausieren/Aktivieren überschreibt einen 412-Konflikt mit
  „Gespeichert") wird durch diese Scheibe **nicht** repariert — gehört laut
  Issue-Kommentar zur Aktiv-Schalter-Scheibe. AC-6 stellt nur sicher, dass
  S3 denselben Fehler nicht zusätzlich für Wertebereiche neu einführt.
- **#1199 F008–F010** (doppelte Feldliste, Nachspeicher-Schleife ohne
  Obergrenze, kurzzeitig falscher `hasPending`) bleiben im Sammel-Issue —
  S3 löst sie nicht mit, führt sie aber auch nicht neu für den
  Wertebereiche-Pfad ein, wenn die Vorlage 1:1 übernommen wird.
- **`hubPutQueue` bleibt bis S6.** Die übrigen vier Hub-Handler
  (Versand, Wetter-Metriken, Layout, Kopfzeile) rufen weiterhin
  `setSaving()`/`setSaved()`/`setError()` direkt — gemischter
  Controller-Betrieb bleibt bis alle Reiter umgestellt sind (jetzt: 2
  Selbst-Speicherer, 4 direkte Aufrufer).
- **Reine Layout-/Anlege-Seite (`/compare/new`) bleibt unberührt** — dort
  mountet `CorridorEditor` ohne `preset`/`saveController`.
- **Vollständige Tilgung der Klebeschicht ist Epic-DoD, nicht
  Scheiben-AC** — Anlege-Pfad (#2277) und Listenseite (#2278) bleiben
  unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe wendet das in S2 bereits etablierte Muster
  (Hub-Queue bleibt bis S6, Voll-Spread-Nutzlast wegen
  `display_config`-Ebene-1-Merge, `shared/` importiert nur Typen aus
  `compare/`) auf einen zweiten Reiter an und verallgemeinert zusätzlich
  den Flush-Guard beim Reiterwechsel von einer reiter-spezifischen auf eine
  listenbasierte Form (Trip-Muster) — das ist eine Anwendung bestehender
  Entscheidungen, keine neue Entscheidungsfläche.

## Changelog

- 2026-09-19: Initial spec created
- 2026-09-19: Implementierung abgeschlossen. Neues Modul
  `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`
  ersetzt `compare/korridorCommit.ts` (gelöscht) als alleinigen Speicherweg für den
  Wertebereiche-Reiter. `.hub-corridor-wrap`-Wrapper und `<svelte:window onpointerup>` in
  `CompareTabs.svelte` entfernt; `flushPendingCorridorSave`/`shouldFlushOnWindowPointerUp` aus
  `compareHubWizardBridge.ts` entfernt. `sichereAlarmeVorReiterwechsel` durch generischen,
  listenbasierten `sichereSelbstSpeichererVorReiterwechsel` ersetzt
  (`SELBST_SPEICHERNDE_VERGLEICH_REITER = ['alarme','idealwerte']`), der beim Verlassen jedes
  bekannten Selbst-Speicher-Reiters flusht. Neue E2E-Spec
  `frontend/e2e/compare-wertebereiche-speichert-selbst.spec.ts` belegt die Verdrahtung
  (Reiterwechsel-Flush, Aktivieren/Pausieren-Flush, „Nochmal speichern" bei 412, ein PUT pro
  Geste) und ist in `.github/ci_e2e_specs.txt` aufgenommen (`E2E_MIN_SPECS` entsprechend
  erhöht). Zugehörige Docs aktualisiert: `docs/features/architecture.md`,
  `docs/features/epic-1273-compare-one-surface.md`.

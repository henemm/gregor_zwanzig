# Context: feat-1256-s6-hub-idealwerte-inline

## Request Summary

Scheibe 6 von #1256: Der Hub-Orte-Tab wird editierbar (Drag-Reorder,
Ort-Entfernen, Inline-„Ort hinzufügen") und der Hub-Idealwerte-Tab stellt auf
die Einbettung des geteilten `CorridorEditor context="vergleich"` um —
Inline-Edit-Parität statt Read-only + Editor-Redirect. ACs: AC-14, AC-15,
AC-16, AC-31, AC-32, AC-33, AC-34 der Programm-Spec.

## Programm-Rahmen

- Programm-Spec: `docs/specs/modules/issue_1256_compare_ui_rewire.md` (v1.3,
  PO-go pauschal 2026-07-13). S6-Definition Z.438-460, ACs Z.793-844,
  KL-6 Z.992-1000 (Einbettung statt Bespoke, Restrisiko Integration),
  Edge Cases Z.1019-1020 (2-Orte-Drag, PUT-Fehler → Rollback).
- ~240 LoC, **LoC-Override-Kandidat** — Ankündigung beim Scheiben-Start ist
  laut Spec Pflicht; Limit 250 wird nur nach PO-Rückfrage überschritten.
- Abhängigkeiten S3 (Hub-Kebab, gleiche Datei) und S4 (Einbettungs-Muster)
  sind beide live.

## Design-Antwort 2026-07-14 (Issue-Kommentar) — Randbedingungen

Das verbindliche Übergabedokument liegt seit Handoff-5 (2026-07-14, während
der S6-Adversary-Phase nachgereicht) im Repo:
`claude-code-handoff/issue-bodies/body-1256-compare-ui-fragen.md`.
Abgleich ergab: KEIN Widerspruch zur S6-Umsetzung — Alarme-Tab/officialWarnings/
Tab-Reihenfolge betreffen den Editor und sind als Folge-Arbeit in **#1258**
erfasst ([triage:po]). Ursprüngliche Randbedingungen (mit Kommentar-
Zusammenfassung gestartet):

- **P5 revidiert: eigener Alarme-Tab analog Trip** (statt „notify in
  Wertebereiche/Versand"). S6 fasst den Alarme-Tab NICHT an. Der
  `CorridorEditor` enthält heute „Warnen"/„Markieren"-Toggles pro Metrik —
  S6 mountet ihn im Hub exakt so, wie ihn der Editor zeigt (Konsistenz).
  Eine etwaige Verlagerung der notify-Toggles in den künftigen Alarme-Tab
  ist Folgearbeit NACH Eintreffen des verbindlichen Dokuments, kein
  S6-Scope.
- P3 (Mobile-Suchfeld raus), P4 (Mobile=Desktop-Kacheln): S8-Scope.
- P6 bestätigt (keine Best-Value-Hervorhebung): betrifft Vorschau/S7.
- Tab-Reihenfolge + officialWarnings-Datenmodell stehen im fehlenden
  Dokument → bei Eintreffen gegen S6-Ergebnis abgleichen (Nacharbeit
  möglich, bewusst akzeptiert).

## Soll (Handoff-4, JSX = Wahrheit)

`screen-compare-detail.jsx` (Scratchpad `handoff4/gregor-zwanzig/project/`):

- **Orte-Tab** (Z.193-218): Sektion „Verglichene Orte", Hint „Reihenfolge =
  Spalten im Briefing · ziehen zum Sortieren"; je Zeile 6-Punkt-Drag-Griff +
  `CompareLocationRow` + Entfernen-X (32×32, ghost); Footer ghost-Btn
  „Ort hinzufügen". Zebra-Streifen (`--g-paper-deep` bei ungeraden Zeilen).
- **Idealwerte-Tab** (Z.220-243): Sektion „Was ‚gut' bedeutet", Hint „wird
  im Briefing markiert · kein Score, kein Ranking"; je Zeile
  `CompareIdealRow` + Edit-Stift; Footer „Metrik hinzufügen".
  → Per KL-6-Entscheid wird das über den geteilten `CorridorEditor`
  realisiert, nicht als Nachbau der JSX-Stiftzeilen.

## Ist (Erkundung 2026-07-14, Worktree intake-1194)

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Hub. `TABS` Z.63-70 (6 Tabs: uebersicht·orte·idealwerte„Wertebereiche"·layout·versand·vorschau). Orte-Tab Z.340-355: Read-only `CompareLocationRow`-Zeilen, „Ort hinzufügen"-Btn OHNE Handler. Idealwerte-Tab Z.357-376: Read-only `CompareIdealRow` aus `preset.display_config.ideal_ranges` (Z.118-122), „Metrik hinzufügen"-Btn OHNE Handler. Einziger Edit-Pfad heute: Versand-Stift → Redirect `/compare/{id}/edit?tab=versand` (Z.211-215, 396-404) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | Geteilter Organism. Props Z.33-39: `context: 'route'\|'vergleich'`, `trip`, `onTripUpdate`, `saveController` — **kein dense-Prop**. Im Compare-Modus State via `getContext('compare-wizard-state')` (Z.41), schreibt reaktiv in Wizard-Runen (`syncToWizard()` Z.102-113). Enthält min/max-Slider + Number-Inputs UND notify-Toggles „Warnen"/„Markieren" (Z.281-291) + „✕ entfernen"; Neutralitäts-Copy „kein Score · kein Rang" (Z.316) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | Mobile-Variante, existiert |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Referenz-Mount: Desktop Z.1074-1085 `<CorridorEditor context="vergleich"/>`, Mobile Z.1248-1256 `<CorridorEditorMobile/>` — ohne weitere Props; Persistenz über Editor-Dirty-/Speichern-Flow |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload(original, edits)` → PUT `/api/compare/presets/{id}` (Z.75). `location_ids`=`edits.pickedIds` (Z.119), `corridors` top-level (Z.157-158), `ideal_ranges`/`active_metrics`/`metric_alert_levels` in `display_config` (Z.82-84). Spread `{...original}` schützt fremde Felder (Read-Modify-Write) |
| `frontend/src/lib/components/compare/locationHelpers.ts` | Pure Helpers (`toKebabCase`, `filterLocations`, `groupLocations`, `isCoordsValid`) — Reorder-Helfer käme hier dazu |
| `frontend/src/lib/components/molecules/CompareIdealRow.svelte`, `CompareLocationRow.svelte` | Read-only-Zeilen des Ist-Hubs; CompareIdealRow wird durch CorridorEditor-Einbettung ersetzt, CompareLocationRow bleibt (Soll nutzt sie in der Drag-Zeile) |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte` | DnD-Vorbild: `svelte-dnd-action` (`dndzone`, `handleDndConsider`/`Finalize`, Z.51-55, 79-81); Bibliothek ^0.9.69 bereits in package.json |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Gegen-Vorbild: HTML5-Drag statt dndzone (Z.5-6), weil dndzone Nicht-Item-Kinder entfernt — Muster-Wahl in Analyse entscheiden |
| `frontend/e2e/layout-tab-route.spec.ts` | Einziges E2E-Drag-Muster: `source.dragTo(target)` (Z.160) |
| `frontend/e2e/compare-flow-navigation.spec.ts` + `frontend/playwright.1256-s2.staging.config.ts` | Scheiben-Suite (17 Tests) — wird je Scheibe erweitert (AC-14/15/31/32/33/34-Klickpfade) |

## Existing Patterns

- **S4-Muster „geteilten Organism in Compare einbetten":** LayoutTab wurde in
  S4 direkt verdrahtet; Lehre F001: Lifecycle/Timing prüfen — lazy
  Tab-Mount, KEIN unbedingter Fetch/Rewrite beim Seiten-Mount (falsches
  Dirty + Extra-Fetches). Für S6 gilt dasselbe: CorridorEditor erst beim
  Tab-Besuch mounten.
- **S5-Muster:** lazy Fetch beim ersten Tab-Besuch mit eigenem
  Wächter-Test (4-Test-Wächter für groups-Fetch) — neu gebaute Gates
  brauchen SOFORT einen Wächter-Test.
- **PUT-Persistenz Hub:** CompareTabs nutzt heute `api.put` nur für
  schedule/send; Orte-/Korridor-Persistenz aus dem Hub ist NEU — Payload
  über `buildComparePresetSavePayload` wiederverwenden (kein neuer
  Endpoint, Read-Modify-Write-Pflicht).

## Dependencies

- Upstream: `svelte-dnd-action`, `CorridorEditor(+Mobile)`,
  `compareEditorSave.ts`, PUT `/api/compare/presets/{id}` (Go-Handler,
  unverändert), `GET /api/groups` (S5, für Inline-Orts-Bibliothek).
- Downstream: Compare-EDITOR nutzt denselben `CorridorEditor` — jede
  Organism-Änderung muss `context="route"` (Trip-Metrics) UND den Editor
  unangetastet lassen (**C0: Trip-Seite 0 Zeilen Diff bzw. nur additive
  Props, Trip-Suiten grün**). S7 (VersandTab-Einbettung) und S8 (Mobile)
  bauen auf dem S6-Einbettungsmuster auf.

## Risks & Considerations

1. **State-Brücke (Hauptrisiko, konkretisiert KL-6):** `CorridorEditor`
   erwartet im vergleich-Kontext `getContext('compare-wizard-state')` —
   den gibt es nur im Editor. Der Hub muss diesen Context bereitstellen
   (Wizard-State aus `preset` hydratisieren) ODER der Organism bekommt
   einen additiven Props-Pfad. Entscheidung in der Analyse; LoC-Abweichung
   von ~240 hier eskalieren (Spec-Vorgabe KL-6).
2. **#1234-Falle (Issue-Kommentar 2026-07-14 04:38): KEIN Debounce-Auto-Save
   in den vergleich-Zweig einführen.** Persistenz in S6 = expliziter PUT
   pro abgeschlossener Nutzeraktion (Drag-Finalize, Inline-Speichern,
   Entfernen) — kein `schedule()` ohne Hydration-Gate; Baseline-JSON-Diff
   aus Prop-Rohwert ist die bekannte Fehlerklasse (löscht via
   `SyncAlertRules` sogar Alarm-Regeln).
3. **PUT-Fehler → Rollback** (Edge Case Spec Z.1020): alter Zustand muss
   wiederherstellbar sein, kein stiller Datenverlust.
4. **notify-Toggles im Hub sichtbar** (P5-Randbedingung, s.o.) — bewusst
   konsistent zum Editor, keine Sonderbehandlung in S6.
5. **dndzone vs. HTML5-Drag:** Orte-Zeilen haben Nicht-Item-Kinder-Risiko
   (Zebra-Wrapper) — Muster-Wahl anhand EtappenStrip-Erfahrung prüfen;
   E2E-Drag gegen Staging muss mit dem gewählten Muster testbar sein
   (`dragTo`-Muster aus layout-tab-route.spec.ts).
6. **#1257 (Alarm-Regeln app-weit tot, Katalog `gust` ≠ `wind_gust`):**
   berührt `SyncAlertRules`-Umfeld; S6 ändert dort nichts, aber
   Adversary-Punkt: S6 darf über den PUT-Payload keine Alert-Regeln
   verlieren (metric_alert_levels unverändert durchreichen, wenn nicht
   editiert).
7. **Known Limitation F006 (Adversary Fix-Loop 1/2/3, Runde 3+4, MEDIUM,
   bleibt bewusst offen):** Der fensterweite Pointerup-Flush-Mechanismus
   (`<svelte:window onpointerup={handleWindowPointerUp}>`, CompareTabs.svelte)
   fängt Band-Drag-Commits ab, die außerhalb von `.hub-corridor-wrap` enden
   (F002-Fix). Diese Restfläche — die `svelte:window`-Bindungszeile selbst
   plus die 1-Zeilen-Delegation `handleWindowPointerUp` → `shouldFlushOn-
   WindowPointerUp`/`flushPendingCorridorSave` — ist mit der Repo-Konvention
   (kein `@testing-library/svelte`, keine DOM-Rendering-Tests im Kern) lokal
   nicht abdeckbar: eine Sabotage-Gegenprobe (Handler auf No-Op gesetzt) ließ
   in allen drei Fix-Loop-Runden 0 von 632-640 lokalen Tests rot werden. Der
   kompensierende Wächter ist ausschließlich Live-E2E: `F002: Band-Handle-
   Drag mit Release über dem Seiten-Header` in
   `frontend/e2e/compare-hub-inline-edit.spec.ts` (echter PUT-Request-Abfang
   + echter `page.reload()`-Wertevergleich) muss bei JEDEM Staging-Lauf
   dieser Scheibe mitlaufen — nicht nur einmalig nach Deploy.

## Existing Specs

- `docs/specs/modules/issue_1256_compare_ui_rewire.md` — Programm-Spec (S6-Quelle)
- `docs/specs/modules/issue_1231_korridor_editor.md` — CorridorEditor-Organism
- `docs/specs/modules/issue_1234_autosave_hydration_gate.md` — Auto-Save-Fehlerklasse

## Analysis

### Type
Feature (Scheibe 6 des PO-freigegebenen Programms #1256)

### Entscheidungen (strategische Bewertung, Plan-Agent 2026-07-14)

1. **State-Brücke = Option (c), eigene kleine Bridge-Datei.**
   `CorridorEditor` liest im vergleich-Kontext via
   `getContext('compare-wizard-state')` nur 6 der 30 Wizard-Felder
   (`isEditMode`, `corridors`, `activityProfile`, `idealRanges`,
   `activeMetricKeys`, `metricAlertLevels`; CorridorEditor.svelte:41-113).
   Der Context wird heute NICHT in CompareEditor erzeugt, sondern inline in
   `routes/compare/[id]/edit/+page.svelte:19-86` — es gibt KEINE extrahierte
   Hydration-Funktion. Der Hub bekommt daher eine kleine Bridge
   (`compareHubWizardBridge.ts`): Teil-Hydration der 6 Felder aus `preset`
   (inkl. `rehydrateActiveMetrics()` aus `compareEditorLoad.ts:23-30`,
   #1191-Semantik), `setContext`, Persistenz-Übersetzung. 0 Zeilen Diff im
   Organism, `context="route"` und Editor-Mount unberührt (C0). Props-Pfad
   (b) verworfen (Kern-Umbau = C0-Verstoß); Voll-Hydration (a) verworfen
   (Over-Engineering, keine wiederverwendbare Funktion vorhanden).

2. **Drag = svelte-dnd-action (`dndzone`).** Das EtappenStrip-Gegenargument
   (dndzone entfernt Nicht-Item-Kinder) greift nicht: „Ort hinzufügen" ist
   Footer AUSSERHALB der Zeilenliste (Soll), analog Vorbild
   `BucketSection.svelte:75-81`. E2E-Testbarkeit belegt:
   `layout-tab-route.spec.ts:146-180` zieht per `dragTo()` echte
   dndzone-Zeilen inkl. Reload-Persistenz-Beweis. `CompareLocationRow` hat
   bereits `alt`-Prop für Zebra.

3. **Persistenz = expliziter PUT pro abgeschlossener Nutzeraktion** über
   `buildComparePresetSavePayload(original, edits)` (Read-Modify-Write:
   `display_config` wird aus `original` gespreadet — Pflicht, denn der
   Go-Handler `UpdateComparePresetHandler` ersetzt geliefertes
   `display_config` KOMPLETT ohne Key-Merge; compare_preset.go:275-277).
   6 required-Felder der edits (`name`, `activityProfile`, `pickedIds`,
   `region`, `idealRanges`, `channelLayouts`) aus `preset` hydratisieren.
   **KEIN schedule()/Debounce (#1234).** Neuer Reibungspunkt: CorridorEditor
   feuert `syncToWizard()` per `oninput` PRO TASTENANSCHLAG (Z.126-128,
   266, 274) → Bridge diskretisiert event-getrieben (blur an Zahlenfeldern,
   pointerup am Fenster analog CorridorEditors eigenem
   `svelte:window onpointerup` Z.178, click an ✕/Warnen/Markieren/+Metrik) —
   kein Timer. **Rollback neu bauen** (kein Repo-Vorbild): Snapshot vor
   Aktion, Restore bei PUT-Fehler (Edge Case Spec Z.1020).
   **SyncAlertRules-Risiko geprüft: keins** — Compare-PUT-Handler ruft
   SyncAlertRules nirgends auf (nur Trip-Pfad, weather_config.go:72).

4. **CSS: kein Eingriff nötig** — CorridorEditor ist self-contained
   (`max-width:1040px`, Z.323), Hub-Container ist mit 1320px breiter.

5. **Lazy Mount: bereits gegeben** — CompareTabs rendert Tabs via echter
   `{#if activeTab === …}`-Blöcke (Z.340, 357); S4-F001-Lehre strukturell
   erfüllt. Ergänzend Wächter-Test wie in S5.

6. **Step2Orte wird NICHT eingebettet** für „Ort hinzufügen" im Hub:
   mutiert `ws.pickedIds` still ohne Aktions-Callback (Step2Orte.svelte:
   133-178) → kein sauberer PUT-Punkt ohne C0-Diff oder Diff-Watch nahe am
   verbotenen Debounce. Stattdessen schlankes bespoke Inline-Panel
   (dokumentierte Ausnahme zur Teilungs-Invariante: Hub-Add-Picker hat kein
   Trip-Pendant; Orte-Domäne ist laut Programm-Spec Z.430-432 bewusst
   compare-eigen).

### Affected Files (with changes)
| File | Change Type | Description | LoC |
|------|-------------|-------------|-----|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Orte-Tab: dndzone-Wiring, Entfernen, Add-Picker-Toggle, optimistisches `$state` + Rollback; Idealwerte-Tab: CorridorEditor-Mount via Bridge | +140…170 |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | CREATE | Teil-Hydration (6 Felder), Persistenz-Bridge (Event-Diskretisierung → PUT → Rollback) | +55…70 |
| `frontend/src/lib/components/compare/locationHelpers.ts` | MODIFY | pure `reorderLocationIds()` | +12 |
| Inline-Add-Panel (in CompareTabs oder kleine Komponente) | CREATE | Bibliotheks-Picker mit explizitem PUT | +40…55 |
| `frontend/e2e/compare-flow-navigation.spec.ts` + S6-Config | MODIFY | Klickpfade AC-14/15/31/32/33/34 | zählt nicht |

### Scope Assessment
- Files: 4 Produktiv + Tests
- Estimated LoC: **+247…307 — über dem 250-Limit → PO-Override nötig (vor Implementierung erfragt)**
- Risk Level: MEDIUM (PUT-Diskretisierung + neu zu bauendes Rollback-Muster; Rest LOW)

### Open Questions
- [x] AC-33 „Edit-Stift": im Hub KEIN Pencil-Gate — Organism wird exakt wie im Editor gemountet (Context-Doc-Randbedingung, entschieden)
- [ ] LoC-Override 250→500 (PO-Frage, gestellt 2026-07-14)

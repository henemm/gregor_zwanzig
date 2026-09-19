---
entity_id: rework_2276_s4_wetter_metriken
type: refactor
created: 2026-09-19
updated: 2026-09-19
status: implemented
version: "1.0"
tags: [compare, trips, wetter-metriken, layout, persistenz]
---

# Wetter-Metriken/Layout-Reiter speichert selbst wie bei der Tour (Issue #2276, Scheibe S4, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich-Hub bedient der Reiter „Wetter-Metriken" heute **zwei
fachlich unabhängige Datendomänen** (Metrikauswahl/Kanäle/Amtliche-Warnungen/
Tagesfenster einerseits, Stundenverlauf/Ausblick andererseits — Issue #1360
hat den vormals eigenen „Layout"-Reiter hier hineingezogen, ohne die
Commit-Pfade zu verschmelzen) über **zwei separate Commit-Funktionen**, die an
einem gemeinsamen DOM-Wrapper-Paar hängen und deshalb bei fast jeder Geste
gemeinsam feuern. Diese Scheibe führt beide Domänen auf **genau eine**
kombinierte Selbst-Speicherung zurück — analog zu S2 (Alarme) und S3
(Wertebereiche), aber mit einem wichtigen Unterschied: anders als bei S2/S3
reicht hier **kein** einfaches 1:1-Übertragen des Musters auf jede Domäne
einzeln, weil zwei unabhängige Selbst-Speicherer auf demselben Reiter, von
derselben Geste ausgelöst, sich in derselben Event-Tick gegenseitig
überschreiben würden (Abschnitt „Implementation Details", Risiko 1). S4 muss
deshalb **eine** Orchestrierung über beide Domänen bauen, nicht zwei. Analog
zu S3 zeigt ein Speicherkonflikt (412) künftig „Nochmal speichern" statt eines
generischen Fehlers. Am Verhalten der Anlege-Seite (`/compare/new`) und der
Trip-Seite ändert sich nichts.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`,
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`,
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts`
- **Identifier:** `handleWetterMetrikenCommit`/`handleLayoutCommit` (entfallen),
  `flushPendingWeatherMetricsSave`/`flushPendingLayoutSave`/
  `rollbackLayoutSnapshot` (wandern/werden ersetzt), neue kombinierte
  Orchestrierung `erstelleWetterMetrikenVergleichSpeicherung()` in
  `weatherMetricsCompareSave.ts`

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`, `frontend/src/routes/`, SvelteKit). Kein
Go-API- und kein Python-Core-Code in dieser Scheibe.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY (erweitern) | `flushPendingWeatherMetricsSave` auf `buildComparePresetSavePayload` (`compare/compareEditorSave.ts`, Voll-Spread) umgestellt — der Laufzeit-Import von `buildHubPutPayload` aus `compareHubWizardBridge.ts` entfällt. `LayoutSnapshot`/`hydrateLayoutFieldsFromPreset`/`flushPendingLayoutSave`/`rollbackLayoutSnapshot` ziehen hierher um (aus `compareHubWizardBridge.ts`), ebenfalls auf `buildComparePresetSavePayload` umgestellt. Neu: kombinierter Snapshot-Typ `WetterMetrikenLayoutSnapshot` über BEIDE Domänen, `baueWetterMetrikenNutzlast()` (Voll-Spread), `flushPendingWetterMetrikenSave` (ein Diff-Guard über den kombinierten Snapshot), `erstelleWetterMetrikenVergleichSpeicherung(opt)` → `{aenderungMelden()}` (Signatur wie `erstelleAlarmeVergleichSpeicherung`/`erstelleWertebereicheVergleichSpeicherung`). `activeMetricKeys` in der kombinierten Nutzlast wird live aus `wiz` gelesen, nie aus einer eingefrorenen `preset`-Kopie |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Props `onCompareCommit`/`onHourlyCommit`/`onOutlookCommit` entfallen, ersetzt durch `preset`, `enqueueHubWrite`, `onCompareUpdate` (Signatur wie `AlarmeTab`). Ein reaktiver `$effect` (AlarmeTab-Muster) beobachtet einen kombinierten Snapshot aller acht persistenzrelevanten Felder und ruft bei Diff `vergleichSpeicherung.aenderungMelden()` — ersetzt sowohl die drei expliziten Commit-Calls (Kanal-Reihenfolge-Drag, Stundenverlauf-Drag, Ausblick-Drag/-Auswahl) als auch die bisherige Wrapper-Abhängigkeit der drei stillen Mutationsstellen (`toggleCompareMetric`, `onToggleVergleichOfficialAlerts`, `DayWindowCard`-Handler). `CompareHourlyLayoutControls`/`CompareOutlookLayoutControls`-Props `onHourlyCommit`/`onOutlookCommit` bleiben unverändert bestehen (ihr Entfernen ist optionale Anschluss-Aufräumung, kein S4-Muss) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | `handleWetterMetrikenCommit`/`handleLayoutCommit`, `currentWetterMetrikenSnapshot`/`lastPersistedWetterMetrikenSnapshot`/`lastPersistedLayoutSnapshot` entfallen. Die beiden separaten Hydrations-Effekte (`hydrateWetterMetrikenTab()`/`hydrateLayoutTab()`, je eigenes Abschluss-Flag) werden zu EINER Hydration mit EINEM gemeinsamen Abschluss-Flag zusammengeführt — die kombinierte Orchestrierung wird erst per `untrack()`-Konstruktion erzeugt, NACHDEM beide Katalog-Ladevorgänge fertig sind. Wrapper-Divs `.hub-layout-hourly-wrap`/`.hub-wetter-metriken-wrap` entfallen. Mount von `WeatherMetricsTab` bekommt die neuen Props. `SELBST_SPEICHERNDE_VERGLEICH_REITER` (`wertebereicheVergleichSpeicherung.ts`) wird um `'wetter-metriken'` ergänzt — `handleValueChange`/`handleToggleActive` sind bereits generisch und brauchen keine weitere Anpassung |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | MODIFY | `LayoutSnapshot`/`hydrateLayoutFieldsFromPreset`/`flushPendingLayoutSave`/`rollbackLayoutSnapshot` entfernt (nach `weatherMetricsCompareSave.ts` umgezogen). `hydrateWeatherMetricsFromPreset`-Nutzung durch `hydrateAlarmFieldsFromPreset` bleibt unverändert bestehen |
| ~7 umgehängte Kern-Tests (`compare/__tests__/compare_hub_layout_save.test.ts`, `compare_hub_layout_rollback.test.ts`, `compare_layout_tab_dissolution.test.ts`, `compare_outlook_metric_formats_persistenz.test.ts`, `outlookMetricIdSelection.test.ts`, `compareActiveMetricsStorageFormat.test.ts`, `compare_hub_wizard_bridge.test.ts`) | MOVE/ANPASSUNG | Import auf die erweiterte `weatherMetricsCompareSave.ts` umgehängt, Zusicherungen unverändert |
| `frontend/e2e/compare-wetter-metriken-speichert-selbst.spec.ts` | CREATE | Muster `compare-wertebereiche-speichert-selbst.spec.ts`: ein PUT pro Geste, Intra-Gesture-Kollision (beide Domänen in einer Geste), Reiterwechsel-Flush, Aktivieren/Pausieren-Flush, „Nochmal speichern" bei 412 |
| `.github/ci_e2e_specs.txt` | MODIFY | neue Spec aufnehmen, `E2E_MIN_SPECS` entsprechend anheben — nur diese eine neue Spec wird geratscht, NICHT die fünf bereits bestehenden, nicht geratschten Compare-E2E-Specs (Scope-Disziplin, s. Known Limitations) |

`compareEditorSave.ts` (`buildComparePresetSavePayload`, Voll-Spread über
`original`) bleibt unverändert und wird vom neuen kombinierten Zweig weiter
als Nutzlast-Baustein verwendet — identische Begründung wie S2/S3 (Go-Merge-
Kernel mergt `display_config` nur auf Ebene 1).

## Estimated Scope

- **LoC:** Kern-Quellcode ≈ +355/−285 (ohne E2E); liegt über dem 250er-Limit
  und über S3s ≈480 Gesamtdiff, weil zwei Domänen zusammengeführt werden UND
  das Wirtsfile (`WeatherMetricsTab.svelte`, 2081 Zeilen) mehr verstreute
  Anpassungsstellen hat als `CorridorEditor`. E2E-Datei (~+160) zählt laut
  Konvention nicht ins LoC-Limit. **`loc_limit_override 500` ist zu
  Workflow-Beginn zu setzen** (wie S2/S3) — eine Aufteilung in S4a/S4b würde
  einen Zwischenzustand erzeugen, in dem zwei Domänen desselben Reiters auf
  unterschiedlichen Speichermechanismen laufen (mehr Risiko als eingesparte
  LoC rechtfertigen).
- **Files:** ~5 Produktivdateien (1 erweitertes Modul, 1 Svelte-Komponente,
  2 Hub-Klebeschicht-Dateien, 1 CI-Ratschen-Datei) + ~7 umgehängte Kern-Tests
  + 1 neue E2E-Spec.
- **Effort:** high — größtes Wirtsfile der Etappe, zusätzlich der
  Intra-Gesture-Kollisionsfall, der in S2/S3 keine Entsprechung hatte.
- **Risk Level:** HIGH. Ein Mutations-Adversary muss insbesondere die
  Zusammenführung zu EINER Orchestrierung gezielt wieder in zwei getrennte
  `schedule()`-Aufrufe aufteilen und nachweisen, dass ein spezifischer Test
  (Datenverlust bzw. zweiter PUT) rot wird.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `createSaveStatus({typ,id})` / `doSave` / `schedule` / `flush` / `retryConflict` (`saveStatusStore.svelte.ts`) | function/class | Geteilter Speicher-Controller der Route; `_pendingFn` ist ein EINZIGER Slot (:184-189) — Grund, warum S4 EINE kombinierte Orchestrierung braucht statt zwei paralleler |
| `hubPutQueue` (`createPutQueue`, `CompareTabs.svelte`) | queue | bleibt bestehen für die übrigen Reiter; der Wetter-Metriken/Layout-PUT läuft über dieselbe Queue (Prop `enqueueHubWrite`) |
| `buildComparePresetSavePayload` (`compareEditorSave.ts`) | function | liefert weiterhin die Voll-Spread-Basis der kombinierten Nutzlast |
| `erstelleAlarmeVergleichSpeicherung`/`erstelleWertebereicheVergleichSpeicherung` (S2/S3, live) | pattern | Vorbild für Modulform und Aufruf-Signatur der neuen kombinierten Funktion |
| `AlarmeTab.svelte` reaktiver `$effect` (S2) | pattern | Vorbild für den reaktiven Ersatz der drei stillen Mutationsstellen — Wetter-Metriken ist architektonisch näher an Alarme (viele verstreute Mutationsstellen) als an `CorridorEditor` (zentrales `patch()`) |
| `SELBST_SPEICHERNDE_VERGLEICH_REITER` / `sichereSelbstSpeichererVorReiterwechsel` (`wertebereicheVergleichSpeicherung.ts:205`, S3) | function/list | wird um `'wetter-metriken'` ergänzt, kein neuer Guard nötig |
| `CompareHourlyLayoutControls`/`CompareOutlookLayoutControls` | component | ihre `onHourlyCommit`/`onOutlookCommit`-Props bleiben strukturell bestehen (Anschluss-Aufräumung außerhalb S4) |
| `CompareNewEditor.svelte` (Anlege-Seite) | component | mountet `WeatherMetricsTab` weiterhin ohne `preset`/`saveController` — Aktivierungsbedingung der neuen Orchestrierung bleibt dort strukturell falsch, Speichern läuft über `wiz.saveNewPreset()` |
| `CompareWizardState` (`compareWizardState.svelte.ts`) | type (nur `import type`) | `shared/` importiert weiterhin ausschließlich den **Typ** aus `compare/` — keine neue Laufzeitabhängigkeit |

## Implementation Details

### Design-Entscheidungen

1. **Eine kombinierte Orchestrierung statt zwei paralleler
   Selbst-Speicherer (KRITISCH, neu gegenüber S2/S3).** Ein einziger Klick im
   Reiter löst historisch beide Commit-Funktionen im selben synchronen Tick
   aus (Wrapper-Bubble). Würden beide unabhängig auf `saveController.schedule()`
   umgestellt, überschriebe der zweite Aufruf den `_pendingFn`-Einzel-Slot des
   ersten NOCH BEVOR das Debounce-Fenster abläuft — die soeben geänderte
   Metrikauswahl ginge beim einzigen tatsächlich ausgeführten (Layout-)PUT
   stillschweigend verloren, weil dessen Payload die Wetter-Metriken-Felder
   unverändert aus der eingefrorenen Server-Baseline rundtrippt. Lösung: EIN
   Snapshot-Typ über beide Domänen, EINE `aenderungMelden()`-Funktion, EIN
   `schedule()`-Aufruf pro Geste.
2. **Reaktiver `$effect` statt Wrapper und statt sechs benannter Call-Sites.**
   Drei Gesten (Metrik-Checkbox, Amtliche-Warnungen-Toggle,
   Tagesfenster-Von/Bis) haben historisch KEINEN expliziten Commit-Call und
   verlassen sich vollständig auf den Wrapper; drei weitere (Kanal-Drag,
   Stundenverlauf-Drag, Ausblick-Drag/-Auswahl) rufen explizit, weil der
   Browser nach einer Ziehgeste das nachfolgende `click` oft unterdrückt. Ein
   `$effect`, der über die acht persistenzrelevanten Felder reagiert, deckt
   alle sechs Gesten einheitlich ab und ist gegen das Drag-Problem immun (er
   reagiert auf State-Änderungen, nicht auf DOM-Ereignisse).
3. **`activeMetricKeys` MUSS live aus `wiz` gelesen werden**, nie aus einer
   eingefrorenen `preset`-Kopie — `display_config.active_metrics` wird auch
   vom Wertebereiche-Reiter (S3) geschrieben; sicher ist die Überschneidung
   nur, wenn beide Schreiber den Wert live zum Ausführungszeitpunkt lesen
   (analog zur `metric_alert_levels`-Überschneidung aus S3).
4. **Hydration erst nach BEIDEN Katalog-Ladevorgängen abgeschlossen.** Die
   zwei bisher unabhängigen Hydrations-Effekte werden zu einer Hydration mit
   einem gemeinsamen Abschluss-Flag zusammengeführt; die Orchestrierung wird
   per `untrack()`-Konstruktion erst danach erzeugt — sonst diffed sie gegen
   eine unvollständige Baseline, und die später eintreffende Hydration löst
   einen PUT ohne Nutzergeste aus.
5. **Nutzlast bleibt Voll-Spread** über `buildComparePresetSavePayload` — wie
   S2/S3, wegen des Go-Merge-Kernels, der `display_config` nur auf Ebene 1
   mergt.
6. **`LayoutSnapshot.outlookMetricFormats` bleibt optional**, seine
   Geschwister-Felder Pflichtfelder — der kombinierte `norm()`-Vergleich
   behält die `== null ? null : {...}`-Semantik bei, sonst entsteht ein
   Scheindiff zwischen „Schlüssel fehlt" und „Schlüssel ist null".
7. **Rollback nur bei Nicht-412**, diff-basiert — analog S2/S3.
8. **`init`-Weiterreichung (Keepalive) bleibt erhalten** — die SaveFn-Signatur
   reicht `init` an `api.put` durch.
9. **Anlege-Seite und Trip-Seite bleiben unverändert** — die neue
   Orchestrierung ist bewusst NUR für den `vergleich`-Zweig aktiv (Trip nutzt
   weiterhin `scheduleAutoSave`/`scheduleReportConfigOnlySave`); kein Verstoß
   gegen die Pendant-Sperre, weil `WeatherMetricsTab` bereits der geteilte
   Baustein ist, den Trip und Vergleich gemeinsam nutzen.
10. **Kein Laufzeit-Import aus `compareHubWizardBridge.ts` mehr** — weder
    `WeatherMetricsTab.svelte` noch `weatherMetricsCompareSave.ts` laden zur
    Laufzeit ein Modul aus der Klebeschicht; ein Laufzeit-Import von
    `buildComparePresetSavePayload` aus `compareEditorSave.ts` bleibt
    ausdrücklich erlaubt.

## Expected Behavior

- **Input:** Änderung einer Einstellung im Wetter-Metriken-Reiter des
  Ortsvergleich-Hubs — gleich ob Metrikauswahl, Kanal-Reihenfolge,
  Amtliche-Warnungen-Schalter, Tagesfenster, Stundenverlauf- oder
  Ausblick-Konfiguration.
- **Output:** genau EIN PUT auf `/api/compare/presets/{id}` mit der
  vollständigen, aktuellen Preset-Nutzlast (beide Domänen kombiniert);
  Anzeige „Gespeichert"; die aktualisierte Basis fließt über
  `onCompareUpdate` in `currentPreset` zurück.
- **Side effects:** bei einem Speicherkonflikt (412) wechselt der
  Speicher-Controller in den Zustand `conflict`, die Oberfläche zeigt
  „Nochmal speichern". Wechselt der Nutzer den Reiter oder pausiert/aktiviert
  den Ortsvergleich, während eine Wetter-Metriken/Layout-Änderung noch nicht
  gesendet wurde, wird sie vorher automatisch gesendet.

## Acceptance Criteria

- **AC-1 (Ein PUT statt bis zu zwei):** Given der Nutzer öffnet den
  Wetter-Metriken-Reiter eines Ortsvergleichs und ändert eine Einstellung
  (z. B. eine Metrik-Checkbox) / When die Geste abgeschlossen ist / Then
  erscheint „Gespeichert" nach genau einem Speichervorgang — auch wenn
  historisch sowohl die Wetter-Metriken- als auch die Layout-Domäne an
  derselben Geste hängen.
  - Nachweisschicht: Kern (Unit-Test zählt PUTs am abgefangenen
    Netzverkehr).
  - Mutations-Gegenprobe: kombinierten Snapshot wieder in zwei getrennte
    `schedule()`-Aufrufe aufteilen ⇒ zwei PUTs bzw. Datenverlust ⇒ Test rot.

- **AC-2 (Intra-Gesture-Kollision — beide Domänen überleben eine gemeinsame
  Geste):** Given der Nutzer ändert eine Metrikauswahl UND — innerhalb
  desselben Debounce-Fensters — eine Stundenverlauf-/Ausblick-Einstellung /
  When beide Änderungen abgeschlossen sind / Then landet GENAU EIN PUT,
  dessen Body BEIDE Änderungen trägt — keine überschreibt die andere.
  - Nachweisschicht: Kern (Unit-/Integrationstest auf den kombinierten
    Snapshot).
  - Mutations-Gegenprobe: kombinierten Snapshot in zwei separate
    `schedule()`-Aufrufe aufteilen ⇒ die zuerst geplante Änderung geht
    verloren (Einzel-Slot-Überschreibung) ⇒ Test rot.

- **AC-3 (Hydration vollständig vor der ersten Baseline):** Given die beiden
  Katalog-Ladevorgänge (Wetter-Metriken-Auswahl, Stundenverlauf/Ausblick)
  schließen zu unterschiedlichen Zeitpunkten ab / When der zweite abschließt
  / Then entsteht dadurch KEIN Speichervorgang ohne vorausgehende
  Nutzergeste.
  - Nachweisschicht: Kern (Unit-Test, beide Hydrationen zeitlich versetzt
    abschließen lassen).
  - Mutations-Gegenprobe: Orchestrierung nur an die erste Hydration binden
    (`wetterMetrikenHydrated` statt `wetterMetrikenHydrated && layoutHydrated`)
    ⇒ ein PUT ohne Nutzergeste ist nachweisbar ⇒ Test rot.

- **AC-4 (`activeMetricKeys` wird live gelesen, auch mit gleichzeitiger
  Wertebereiche-Änderung):** Given der Nutzer ändert die Metrikauswahl im
  Wetter-Metriken-Reiter UND im selben Hub-Besuch zusätzlich einen
  Wertebereich im Idealwerte-Reiter / When beide gespeichert sind / Then
  trägt der gespeicherte Stand die AKTUELLE Metrikauswahl, unabhängig davon,
  welcher der beiden Reiter zuletzt gespeichert hat.
  - Nachweisschicht: Kern (Integrationstest über beide Reiter im selben
    Wizard-Zustand).
  - Mutations-Gegenprobe: `activeMetricKeys` aus einer eingefrorenen
    `preset`-Kopie statt live aus `wiz` befüllen ⇒ Test rot.

- **AC-5 (Drei bisher stille Gesten bleiben wirksam):** Given der Nutzer (a)
  wechselt eine Metrik-Checkbox, (b) den Amtliche-Warnungen-Schalter, oder
  (c) das Tagesfenster Von/Bis, OHNE eine Ziehgeste zu verwenden / When die
  Änderung abgeschlossen ist / Then wird sie gespeichert — obwohl der
  bisherige Wrapper-Mechanismus entfällt.
  - Nachweisschicht: Kern (drei separate Unit-Test-Fälle, je Geste ein
    eigener Nachweis).
  - Mutations-Gegenprobe je Geste: den Ersatzweg (reaktiver Effect) für
    genau diese eine Geste entfernen ⇒ der zugehörige Test wird rot, die
    anderen beiden bleiben grün (Isolationsnachweis).

- **AC-6 (Reiterwechsel verliert nichts):** Given der Nutzer ändert eine
  Wetter-Metriken-Einstellung und wechselt sofort, vor Ablauf der
  Debounce-Zeit, in den Alarme- oder Idealwerte-Reiter, wo er ebenfalls
  sofort eine Änderung vornimmt / When beide Änderungen abgeschlossen sind /
  Then sind BEIDE gespeichert.
  - Nachweisschicht: Kern (erweiterter `CompareTabs`-Test).
  - Mutations-Gegenprobe: `'wetter-metriken'` nicht in
    `SELBST_SPEICHERNDE_VERGLEICH_REITER` aufnehmen ⇒ Test rot.

- **AC-7 (Speicherkonflikt zeigt „Nochmal speichern"):** Given ein
  Wetter-Metriken/Layout-Speichervorgang schlägt mit einem Speicherkonflikt
  (412) fehl / When der Nutzer „Nochmal speichern" auslöst / Then wird die
  Änderung erneut gesendet, endet in „Gespeichert", der geänderte Stand
  bleibt sichtbar.
  - Nachweisschicht: Kern (Erweiterung der bestehenden Konflikt-Suite) +
    E2E (neue Spec, echter 412 gegen Staging).
  - Mutations-Gegenprobe: Rollback auch bei 412 auslösen ⇒ Test rot.

- **AC-8 (Pausieren/Aktivieren flusht ausstehende Änderung):** Given der
  Nutzer ändert eine Wetter-Metriken/Layout-Einstellung und pausiert/
  aktiviert den Ortsvergleich sofort danach / When der Vorgang abgeschlossen
  ist / Then ist die Änderung im gespeicherten Stand enthalten.
  - Nachweisschicht: Kern (Unit-Test auf `handleToggleActive()`).
  - Mutations-Gegenprobe: den vorab-`flush()`-Aufruf entfernen ⇒ Test rot.

- **AC-9 (Kein Laufzeit-Import der alten Klebeschicht mehr):** Given der
  Wetter-Metriken/Layout-Speicherpfad ist umgestellt / When der Modulgraph
  geladen wird / Then lädt weder `WeatherMetricsTab.svelte` noch
  `weatherMetricsCompareSave.ts` zur Laufzeit ein Modul aus
  `compareHubWizardBridge.ts` — `buildComparePresetSavePayload` aus
  `compareEditorSave.ts` bleibt ausdrücklich erlaubt.
  - Nachweisschicht: Kern (Ladegraph-Nachweis über `node --test`
    `--experimental-test-module-mocks`, analog S3 AC-7).
  - Mutations-Gegenprobe: `buildHubPutPayload`-Re-Import einfügen ⇒
    Ladegraph-Nachweis schlägt an, Test rot.

- **AC-10 (Anlege-Seite unverändert):** Given der Nutzer legt einen neuen
  Ortsvergleich an und bearbeitet den Wetter-Metriken-Reiter vor dem ersten
  Speichern / When er die Anlage abschließt / Then läuft der Speicherweg
  weiter ausschließlich über `wiz.saveNewPreset()` (POST), ohne
  zwischenzeitlichen PUT.
  - Nachweisschicht: Kern (bestehende Struktur-/Mount-Tests bleiben grün).
  - Mutations-Gegenprobe: Aktivierungs-Bedingung der neuen Orchestrierung
    entfernen ⇒ Anlege-Seite löst einen PUT aus ⇒ Test rot.

- **AC-11 (Keepalive-Weiterreichung):** Given der Nutzer schließt den Tab
  unmittelbar nach einer Wetter-Metriken/Layout-Änderung / When der Browser
  Keepalive auslöst / Then wird `init` an den PUT durchgereicht.
  - Nachweisschicht: Kern (analog `trip_speicherung_reicht_keepalive_durch.test.ts`).
  - Mutations-Gegenprobe: `init` in der SaveFn ignorieren ⇒ Test rot.

- **AC-12 (Speichern verliert keine anderen Daten):** Given ein
  Ortsvergleich mit Orten, Versandzeiten, Kanälen, Alarm-Schwellen und
  Wertebereichen / When der Nutzer im Wetter-Metriken-Reiter etwas ändert
  und speichert / Then bleiben alle übrigen Einstellungen nach erneutem
  Laden unverändert.
  - Nachweisschicht: Kern (Payload-Test auf `baueWetterMetrikenNutzlast`) +
    E2E (neue Spec, GET vor/nach, Feldvergleich).
  - Mutations-Gegenprobe: ein Bestandsfeld aus der Payload weglassen ⇒ Test
    rot.

- **AC-13 (Trip-Seite unverändert):** Given ein Trip mit
  Wetter-Metriken-Konfiguration / When der Nutzer dort etwas ändert / Then
  läuft die Speicherung weiterhin über `scheduleAutoSave`/
  `scheduleReportConfigOnlySave`, unverändert durch den Umbau am
  Ortsvergleich.
  - Nachweisschicht: Kern (bestehende Trip-Tests bleiben grün, neuer
    Kern-Test, dass der `route`-Zweig die Vergleichs-Orchestrierung nicht
    aufruft).
  - Mutations-Gegenprobe: Kontext-Prüfung entfernen, sodass der route-Zweig
    die Vergleichs-Orchestrierung auslöst ⇒ Test rot.

## Known Limitations

- **Fünf nicht geratschte Compare-E2E-Specs** (`compare-metric-order.spec.ts`,
  `compare-hourly-metric-order.spec.ts`, `compare-layout-tab-dissolution.spec.ts`,
  `compare-hub-fidelity-s8c.spec.ts`, `compare-editor-fidelity-s8d.spec.ts`)
  bleiben außerhalb von `ci_e2e_specs.txt` — S4 validiert sie als
  Regressionsnetz (lokal/Staging vor Abschluss grün), ratscht aber NUR die
  eine neue, eigene Spec (S2/S3-Präzedenz — Aufnahme aller fünf wäre Scope
  Creep dieser Scheibe).
- **Bis zu zwei PUTs → höchstens einer** ist ein Verhaltens-Delta, kein
  Verhaltensneutralitäts-Bruch (nicht nutzersichtbar), aber ein bestehender
  Test, der eine Layout-only-Payload OHNE `active_metrics`-Schlüssel
  erwartet, ändert sich legitim (Voll-Spread trägt jetzt immer beide
  Domänen) — vorab benannt, nicht erst bei der Implementierung zu entdecken.
- **„Toter Zweig" `WeatherMetricsTab.svelte` (Katalog-Guard mit tautologischer
  Oder-Bedingung)** ist reine Boilerplate-Vereinfachung ohne
  Persistenz-Auswirkung — kann bei der Implementierung mitgenommen werden,
  ist aber keine Pflicht für S4s Kern-AC.
- **Entfernen der `onHourlyCommit`/`onOutlookCommit`-Props** aus
  `CompareHourlyLayoutControls`/`CompareOutlookLayoutControls` ist optionale
  Anschluss-Aufräumung, NICHT Teil von S4 (Verhaltensneutralität vor
  Code-Kosmetik, analog S2s Umgang mit `official_alerts_enabled`).
- **`hubPutQueue` bleibt bis S6.** Die verbleibenden Hub-Handler (Versand,
  Kopfzeile) rufen weiterhin `setSaving()`/`setSaved()`/`setError()` direkt
  — gemischter Controller-Betrieb bleibt bis alle Reiter umgestellt sind
  (nach S4: 3 Selbst-Speicherer, 2 direkte Aufrufer).
- **Vollständige Tilgung der Klebeschicht ist Epic-DoD, nicht Scheiben-AC**
  — Anlege-Pfad (#2277) und Listenseite (#2278) bleiben unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe wendet das in S2/S3 etablierte Muster (Hub-
  Queue bleibt bis S6, Voll-Spread-Nutzlast wegen `display_config`-Ebene-1-
  Merge, `shared/` importiert nur Typen aus `compare/`, listenbasierter
  Flush-Guard) auf einen dritten Reiter an — allerdings mit der zusätzlichen,
  durch die Analyse belegten Notwendigkeit, zwei bislang getrennte
  Commit-Funktionen zu EINER Orchestrierung zusammenzuführen, weil ein
  1:1-Übertragen des S2/S3-Musters (zwei unabhängige Selbst-Speicherer auf
  demselben Reiter) einen neuen, in S2/S3 nicht aufgetretenen
  Datenverlust-Pfad einführen würde (Intra-Gesture-Kollision). Das ist eine
  Anwendung und notwendige Erweiterung bestehender Entscheidungen, keine neue
  Entscheidungsfläche.

## Changelog

- 2026-09-19: Initial spec created
- 2026-09-19: Implementierung abgeschlossen. Kombinierte Orchestrierung
  `erstelleWetterMetrikenVergleichSpeicherung()` in
  `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`
  löst `handleWetterMetrikenCommit`/`handleLayoutCommit` als alleinigen
  Speicherweg für den Reiter ab (EIN Snapshot-Typ über beide Domänen, EIN
  `schedule()`-Aufruf pro Geste — schließt den Intra-Gesture-Datenverlustpfad,
  s. Risiko 1). `LayoutSnapshot`/`hydrateLayoutFieldsFromPreset`/
  `flushPendingLayoutSave`/`rollbackLayoutSnapshot` aus
  `compare/compareHubWizardBridge.ts` hierher umgezogen; Wrapper-Divs
  `.hub-layout-hourly-wrap`/`.hub-wetter-metriken-wrap` und die beiden
  getrennten Hydrations-Effekte in `CompareTabs.svelte` entfernt/zusammengeführt.
  `SELBST_SPEICHERNDE_VERGLEICH_REITER` (`wertebereicheVergleichSpeicherung.ts`)
  um `'wetter-metriken'` ergänzt. Neue E2E-Spec
  `frontend/e2e/compare-wetter-metriken-speichert-selbst.spec.ts` belegt die
  Verdrahtung (Ein-PUT-pro-Geste, Intra-Gesture-Kollision, Reiterwechsel-Flush,
  Aktivieren/Pausieren-Flush, „Nochmal speichern" bei 412) und ist in
  `.github/ci_e2e_specs.txt` aufgenommen (`E2E_MIN_SPECS` entsprechend erhöht).
  Zugehörige Docs aktualisiert: `docs/features/architecture.md`,
  `docs/features/epic-1273-compare-one-surface.md`.

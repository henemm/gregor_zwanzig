---
entity_id: rework_2276_s6g_wetter_metriken_wertprops
type: refactor
created: 2026-09-24
updated: 2026-09-24
status: draft
version: "1.0"
tags: [compare, wetter-metriken, wertprops, ratsche, refactor]
---

# Wetter-Metriken-Reiter des Ortsvergleichs auf Wertprops (Issue #2276, Scheibe S6g, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Scheibe **S6g** von #2276 (Epic #2345) stellt den größten geteilten Organismus
`WeatherMetricsTab.svelte` (WMT, 2123 Zeilen, `context="route"|"vergleich"`) im
**Vergleichs-Zweig** vom Prop `wiz: CompareWizardState` auf reine **Wertprops +
Änderungs-Rückrufe** um — nach dem in S6b (`CompareHourlyLayoutControls`, live
`8207c157`), S6c (`AlarmeTab`, live `c737159e`), S6d (`CorridorEditor(Mobile)`,
live `930ccdc0`) und S6e (`VersandTab`, Spec `rework_2276_s6e_versand.md`)
erprobten Muster. Der `wiz`-Zugriff verschwindet aus `shared/WeatherMetricsTab.svelte`
und wandert zu den Elternteilen hoch: eine neue Bündel-Funktion
`wetterMetrikenPropsAus(wiz)` (`compare/wetterMetrikenPropsAus.ts`) baut das
Prop-Bündel, das alle **drei** Vergleichs-Mounts (Hub `CompareTabs.svelte`,
Anlege-Desktop/-Mobil `CompareNewEditor.svelte`) identisch einspeisen. Verhalten
bleibt unverändert.

Anders als S6c/S6d/S6e hat diese Scheibe **genau EINE Feldklasse** (Design-
Entscheidung 2): alle zehn Felder der bestehenden kombinierten Orchestrierung
(`WetterMetrikenLayoutSnapshot`, `weather-metrics-tab/weatherMetricsCompareSave.ts:291-302`)
sind Snapshot-Felder (Klasse A in S6e-Terminologie) — keine eigenständigen,
keine toten Legacy-Restfelder. Die Neuerung dieser Scheibe ist stattdessen eine
**gekoppelte Schreibung**: `toggleCompareMetric` schreibt `activeMetricKeys`
UND `channelActiveMetricKeys` in einem Funktionsdurchlauf — dafür bündelt das
Prop-Interface einen gemeinsamen Rückruf `onVergleichsMetrikenChange(active,
channelActive)`, damit Snapshot/Rollback nie einen Zwischenzustand sieht, in
dem nur eines der beiden Felder aktualisiert ist.

Diese Scheibe ist ein **Re-Cut** gegenüber dem ursprünglichen Issue-Kommentar
„S6g = WMT, Hub-Klasse, AC-2": Von den 14 verbleibenden HERKUNFT-Ratschen-
Einträgen liegen nur 5 in WMT/WMT-Save, die übrigen 9 in Corridor/Versand/
Wertebereiche. Die Hub-Klasseninstanz `new CompareWizardState()` ist **kein**
Ticket-AC (S6f-Spec) und bleibt in dieser Scheibe bestehen. Die AC-2-Endbilanz
aller 14 HERKUNFT-Einträge, der Ratschen-Endzustand und der Konflikt AC-2 ↔ S4
AC-13 gehen an die Folgescheibe **S6h**, die #2276 schließt (siehe „Nicht in
dieser Scheibe").

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`,
  `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`,
  `frontend/src/lib/components/compare/wetterMetrikenPropsAus.ts` (neu),
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`,
  `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`,
  `frontend/src/lib/components/shared/__tests__/weatherMetricsTabSharing.test.ts`,
  `frontend/src/lib/components/compare/__tests__/compare_wetter_metriken_wertprops.test.ts` (neu)
- **Identifier:** `WeatherMetricsTab` (Props im Vergleichs-Zweig: zehn
  Wertprops `activeMetricKeys`/`channelActiveMetricKeys`/`officialAlertsEnabled`/
  `dayWindowStartHour`/`dayWindowEndHour`/`hourlyMetricKeys`/`hourlyEnabled`/
  `outlookMetricKeys`/`outlookMetricFormats`/`outlookEnabled` + neun Rückrufe
  `onVergleichsMetrikenChange`/`onOfficialAlertsEnabledChange`/
  `onDayWindowStartHourChange`/`onDayWindowEndHourChange`/
  `onHourlyMetricKeysChange`/`onHourlyEnabledChange`/`onOutlookMetricKeysChange`/
  `onOutlookMetricFormatsChange`/`onOutlookEnabledChange`; unveränderte Props
  `context`/`trip`/`createMode`/`onChannelsChange`/`onWeatherMetricsChange`/
  `onDayWindowChange`/`onTripUpdate`/`saveController`/`preset`/`onCompareUpdate`/
  `enqueueHubWrite`), `wetterMetrikenPropsAus(wiz)`
  (`compare/wetterMetrikenPropsAus.ts`, neu), `wetterMetrikenZustandsBruecke(werte,
  setzen)` (`weather-metrics-tab/weatherMetricsCompareSave.ts`, neu), Mount (B,
  Hub) `CompareTabs.svelte:1004-1011`, Mount (C, Anlegen Desktop)
  `CompareNewEditor.svelte:382`, Mount (D, Anlegen Mobil)
  `CompareNewEditor.svelte:483`, Mount (A, Trip) `TripTabs.svelte:224`,
  `TripEditView.svelte:201`, `TripNewEditor.svelte:881/:1113` (alle unverändert,
  kein `wiz`)

Betroffene Schicht: ausschließlich **Frontend** (`frontend/src/lib/components/`).
Kein Go-API- und kein Python-Core-Code in dieser Scheibe.

Zeilenangaben Stand `84b50d72` (S6f live). Wo sich eine Zeile durch diese
Scheibe selbst verschiebt, ist das ausdrücklich vermerkt — die Ratsche trägt
die in GREEN gemessenen neuen Zeilennummern nach (siehe Implementation
Details, Design-Entscheidung 8).

## Nicht in dieser Scheibe

- **Die Hub-Klasseninstanz `new CompareWizardState()` (`CompareTabs.svelte:328`)
  bleibt bestehen.** Sie wird weiterhin als Hydrationsziel gebraucht
  (`hydrateWetterMetrikenTab`/`hydrateLayoutTab`) und als Quelle, die
  `wetterMetrikenPropsAus(wizardState)` liest — die Hydration schreibt in
  dasselbe Objekt, aus dem das Bündel liest. Eine Umstellung auf Plain-`$state`
  ist **kein** Ticket-AC (S6f-Spec, Abschnitt „Nicht in dieser Scheibe") und
  geht an S6h.
- **`/compare/new` (Issue #2277) wird nicht neu gebaut.** `CompareNewEditor.svelte`
  und `Step2Orte.svelte` bleiben in ihrer heutigen Struktur — nur die beiden
  WMT-Mounts wechseln von `{wiz}` auf `{...wetterMetrikenPropsAus(wiz)}`.
- **AC-2-Endbilanz der 14 verbleibenden HERKUNFT-Einträge** (Speicherweg-
  Prädikate in `versandVergleichSpeicherung.ts:221`/
  `wertebereicheVergleichSpeicherung.ts:200`/`weatherMetricsCompareSave.ts:534`,
  Corridor-Katalog-Guards, `maybeSchedule`, `VersandTab.svelte:348`, WMT
  `:545`/`:560`/`:589`/`:602` als Ladepfad-Zwillinge) wird **NICHT** in dieser
  Scheibe gezogen — sie hängt an Corridor/Versand-Zweigen, die S6g nicht
  anfasst, und gehört zu **S6h**.
- **Kein Ratschen-Rückbau.** `EINGEFROREN_SOLL_ANZAHL` bleibt **47** — S6g
  streicht keinen Eintrag, sie führt fünf Einträge auf neue Zeilennummern nach
  (siehe Implementation Details).
- **Konflikt AC-2 ↔ S4 AC-13** (drei Speicherweg-Prädikate sind laut AC-2-
  Wortlaut HERKUNFT, `weatherMetricsCompareSave.ts:534` ist zugleich die
  freigegebene S4-AC-13-„zweite Barriere") wird in dieser Scheibe **nur
  umbenannt, nicht aufgelöst** — ADR-Bedarf bzw. AC-2-Abweichung geht an S6h
  (siehe Known Limitations).
- **`createMode`-Anlegelogik** (23 Treffer, Trip-Anlege-Pfad) ist im
  Vergleichszweig ungenutzt — nicht Gegenstand dieser Scheibe.
- **`weatherMetricsTabSections.ts:72/73`** (fachliche Abschnittswahl
  route/vergleich) bleibt unverändert — echter Sachunterschied.
- **`WeatherMetricsTab.svelte:1323`** (Markup-Gabelung der Metrik-Übersicht)
  bleibt inhaltlich unverändert — sie verschiebt sich nur durch die neuen
  Prop-Zeilen oberhalb (siehe Ratschen-Nachführung), ihre Bedingung selbst
  ändert sich nicht.
- **Tote Prop `onOutlookCommit`** (`CompareOutlookLayoutControls.svelte`, WMT
  übergibt sie nie) und **`flushPendingLayoutSave`/`flushPendingWeatherMetricsSave`**
  (`weatherMetricsCompareSave.ts`, ohne Produktiv-Aufrufer) werden **nicht**
  bereinigt — Checkbox-Zeile in #1199, kein eigenes Issue (Nebenbefund-Triage).
- **Kein neuer CI-E2E-Test.** `compare-wetter-metriken-speichert-selbst.spec.ts`
  und `compare-stundenverlauf-wertprops.spec.ts` (beide bereits in
  `.github/ci_e2e_specs.txt`) decken den Hub-Speicherweg (Mount B) bereits
  ab. Für den Wetter-Metriken-Reiter auf der Anlege-Seite (`/compare/new`,
  Mounts C/D) existiert **keine** CI-E2E-Abdeckung: `layout-tab-vergleich.spec.ts`
  und `compare-hourly-metric-order.spec.ts` üben genau diesen Reiter auf
  `/compare/new` aus, sind aber nicht in der CI-Ampel. `compare-editor-slice3.spec.ts`
  IST in `.github/ci_e2e_specs.txt` und läuft ebenfalls gegen `/compare/new`
  — deckt dort aber nur Orte/Idealwerte-Fidelity ab (eigener Spec-Titel
  „Orte + Idealwerte Fidelity"), nicht den Wetter-Metriken-Reiter; ihr Erfolg
  ist kein Beleg für diese Scheibe. Deshalb trägt AC-5 den Nachweis über
  einen manuellen Staging-Durchklick, keine neue Spec-Datei.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/compare/wetterMetrikenPropsAus.ts` | **CREATE** | Bündel: zehn Werte (Design-Entscheidung 1, Feldtabelle) + neun Gesten-Rückrufe, strukturelle Quellen-Schnittstelle `WetterMetrikenZustandsQuelle` (kein `CompareWizardState`-Import, Muster `VersandZustandsQuelle` in `versandPropsAus.ts`). Liegt in `compare/`, nicht `shared/` (gz-eigenständig, kein Trip-Pendant) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | `wiz`→`zustand` **vollständig, kein Bezeichner `wiz` bleibt in der Datei** (Tech-Lead-Entscheid, Design-Entscheidung 4): Prädikat `wetterMetrikenVergleichSpeicherungAktiv` (`:530`/`:534`, gleiche Zeile, Text ändert sich zu `!!p.zustand`); `erstelleWetterMetrikenVergleichSpeicherung`s Optionsfeld (`:440`) + Destrukturierung + interne Verwendungen (`:468`/`:469`/`:476`/`:486`/`:496`); die drei internen/positionell aufgerufenen Funktionen `felder(wiz)`→`felder(zustand)` (`:308-309`), `wetterMetrikenSnapshotAus(wiz)`→`wetterMetrikenSnapshotAus(zustand)` (`:317-318`), `rollbackWetterMetrikenSnapshot(wiz, …)`→`rollbackWetterMetrikenSnapshot(zustand, …)` (`:413-418`) — Parameter-Umbenennung ohne Auswirkung auf externe Aufrufer (positionelle Aufrufe). Zugehörige Prosakommentare (`:312`, `:409`, `:454`) zeilenneutral mitgezogen. Neue Funktion `wetterMetrikenZustandsBruecke(werte, setzen)` **unterhalb Zeile 534** (Muster `versandZustandsBruecke`); Kommentar `:290` „(9 Felder)"→„(10 Felder)" UND Kommentar `:339` „die neun eigenen Felder"→„die zehn eigenen Felder" (beide Textänderungen an Ort und Stelle, zeilenneutral, beide liegen oberhalb `:534`). Ratschen-Prüfung: `:534` ist in `context_herkunft_zweige_eingefroren.test.ts` nur positionsbasiert gelistet, in keinem `BLEIBT_MIT_INHALT`-Eintrag inhaltlich gefesselt — die Umbenennung hat keine Ratschen-Auswirkung (Design-Entscheidung 4) |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts` | MODIFY | Alle acht Aufrufe von `wetterMetrikenVergleichSpeicherungAktiv({context, wiz, ...})` (`:42`-`:86`) auf den Schlüssel `zustand` umgestellt — **PFLICHT im selben Commit wie die Umbenennung**, sonst wird das Prädikat für diesen Test dauerhaft vakuum-falsch (`p.zustand` bliebe `undefined`, weil der Test weiterhin `wiz:` übergibt, und `!!p.zustand` wäre immer `false`, unabhängig von `context` — die S4-AC-13-Mutations-Gegenprobe würde nicht mehr fangen) |
| Elf Testdateien mit `erstelleWetterMetrikenVergleichSpeicherung({…, wiz: …})`: `weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts` (`:199`/`:247`), `wetter_metriken_und_wertebereiche_teilen_active_metric_keys.test.ts` (`:78`), `wetter_metriken_vergleich_speichert_einmal.test.ts` (`:64`), `wetter_metriken_intra_gesture_kollision.test.ts` (`:59`), `wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts` (`:55`), `wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts` (`:44`), `wetter_metriken_vergleich_flush_vor_pausieren.test.ts` (`:51`), `wetter_metriken_reiterwechsel_verliert_nichts.test.ts` (`:78`), `wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts` (`:137`), `wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts` (`:48`) | MODIFY | Schlüssel `wiz:` → `zustand:` mechanisch umgestellt, keine Assertion ändert sich inhaltlich (Grep-Ersetzung, Muster S6e) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Typ-Import `:92` + Prop `wiz` (`:169`/`:178`) entfallen; zehn optionale Wertprops + neun Rückrufe kommen rein; alle Lese-/Schreibzugriffe `:1096`-`:1520` (`toggleCompareMetric`, `materializedActiveMetricKeys`, `editCompareChannel`, `compareChannelPrimary`, `onCompareOutlook*`, `onToggleVergleichOfficialAlerts`, `DayWindowCard`-Mount, `CompareHourlyLayoutControls`-Mount, `CompareOutlookLayoutControls`-Mount, `officialAlertsToggle`-Aufruf) auf die neuen Props/Rückrufe umverdrahtet; Selbst-Speicher-Effekt `:1260`-`:1281` baut `wetterMetrikenZustandsBruecke(werte, setzen)` lokal und übergibt sie als `zustand`-Argument an **beide** `wetterMetrikenVergleichSpeicherungAktiv` UND `erstelleWetterMetrikenVergleichSpeicherung` (Design-Entscheidung 4 — beide Funktionen sind jetzt auf `zustand` umbenannt, kein Bezeichner `wiz` bleibt), Präsenz-Prüfung per Prop-da-Guard (Muster S6b DE-2) statt `!!wiz`. **Neue Prop-Zeilen liegen oberhalb `:545` ⇒ verschieben fünf eingefrorene Ratschen-Einträge (`:545`/`:560`/`:589`/`:602`/`:1323`)** |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount `:1004`-`:1011`: `wiz={wizardState}` → `{...wetterMetrikenPropsAus(wizardState)}` inline im Markup-Ausdruck (Aufrufform-Pflicht, Auflage A-Form wie S6e), übrige Props (`preset`/`saveController`/`enqueueHubWrite`/`onCompareUpdate`) unverändert; `let localSchedule = $state<string>(...)` (`:630`) VOR ihre erste Nutzung in `status = $derived(...)` (`:162`) gezogen (svelte-check-Fehler-Behebung, Mitbereinigung) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | beide Mounts `:382` (Desktop) + `:483` (Mobil): `{wiz}` → `{...wetterMetrikenPropsAus(wiz)}` |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Neuer 🔴 STAND-S6g-Absatz (viertes Beispiel nach S6c/S6d/S6e): der Zeilenzahl-Vertrag gilt zusätzlich NICHT für `WeatherMetricsTab.svelte` — **0** Einträge gestrichen, **5** auf neue Zeilennummern nachgeführt (`:545`/`:560`/`:589`/`:602`/`:1323`), per `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext gefesselt. `EINGEFROREN_SOLL_ANZAHL` bleibt **47**. `weather-metrics-tab/weatherMetricsCompareSave.ts:534` bleibt unverändert an seiner Position (alter, positionsbasierter Vertrag, Auflage A1 analog S6e DE-4/6) |
| `frontend/src/lib/components/shared/__tests__/weatherMetricsTabSharing.test.ts` | MODIFY | `:69` prüft heute explizit `wiz?: CompareWizardState` an WMT (`assert.match(code, /wiz\??\s*:\s*CompareWizardState/, ...)`) — Assertion im selben Commit auf die neue Prop-Schnittstelle umgestellt (Saat-Anpassung) |
| Tests mit `wiz` an WMT (grober Vorbefund aus dem Kontextdokument, verbindliche Zählung erst in `/40` per Grep auf `wiz={`/`{wiz}` gegen `WeatherMetricsTab`): `shared/__tests__/compare_stundenverlauf_wertprops.test.ts`, `metricKuerzelLegende.test.ts`, `weatherMetricsTabDayWindowSave.test.ts`; `shared/weather-metrics-tab/__tests__/wetter_metriken_laedt_keine_compare_klebeschicht.test.ts`, `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts`, `wetter_metriken_vergleich_speichert_einmal.test.ts` (+ übrige `wetter_metriken_*`), `compare_hourly_layout_controls_structure.test.ts`, `weather_metrics_tab_compare_catalog_fetch.test.ts` | MODIFY | Mounts von `wiz={...}` auf die neuen Wertprops/das Bündel umgestellt, keine Assertion ändert sich inhaltlich |
| `frontend/src/lib/components/compare/__tests__/compare_wetter_metriken_wertprops.test.ts` | **CREATE** | AST-Wächter analog `compare_versand_wertprops.test.ts`: AC-1 (kein `wiz`/`CompareWizardState`-Identifier mehr im Instanz-Skript von WMT), AC-2 (alle drei Vergleichs-Mounts streuen `wetterMetrikenPropsAus(...)` identisch, Aufrufform Markup-Ausdruck), AC-3 (Wirkort-Guard über `effekteVon()`/`umgebungFuer()`), AC-9 (gekoppelter Rückruf `onVergleichsMetrikenChange` setzt beide Felder atomar) |
| Trip-Mounts (`trip-detail/TripTabs.svelte:224`, `edit/TripEditView.svelte:201`, `trip-new/TripNewEditor.svelte:881/:1113`) | — | unverändert; die zehn neuen Wertprops sind optional, kein Trip-Mount übergibt sie |

**6 produktive Dateien** (2 CREATE: `wetterMetrikenPropsAus.ts`,
`compare_wetter_metriken_wertprops.test.ts` zählt als Testdatei, nicht produktiv; 4 MODIFY:
`WeatherMetricsTab.svelte`, `weatherMetricsCompareSave.ts`, `CompareTabs.svelte`,
`CompareNewEditor.svelte`) + **~12-15 Testdateien** (Mount-Umstellung) + 1 dedizierte
Prädikat-Testdatei (`wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts`) + **11
Fabrik-Testdateien** (Schlüssel-Rename `wiz:`→`zustand:`, Tech-Lead-Entscheid) + 1 neue
Kern-Testdatei (`compare_wetter_metriken_wertprops.test.ts`) + 1 Ratschen-Nachführung.

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. **+220 / −70** (Kontextdokument-Schätzung) —
  der Großteil ist der neue AST-Wächter (`compare_wetter_metriken_wertprops.test.ts`),
  `wetterMetrikenPropsAus.ts` und die Umverdrahtung der ~15 Lese-/Schreibstellen
  in `WeatherMetricsTab.svelte` (größter Organismus, 2123 Zeilen, markup-verzahnt).
- **Files:** 6 produktiv (2 CREATE, 4 MODIFY) + eine unbekannte, aber
  wahrscheinlich zweistellige Zahl an Testdateien, die `wiz={...}`/`{wiz}` auf
  `WeatherMetricsTab` mounten (Saat-Anpassung, verbindliche Zählung in `/40`)
  + **12 bereits verifizierte** Testdateien mit `wiz:`-Schlüssel-Rename (1
  Prädikat-Test, 11 Fabrik-Tests, Tech-Lead-Entscheid).
- **Effort:** medium–high.
- **Risk Level: MEDIUM.** Nach unten: das Muster ist zum vierten Mal erprobt
  (S6b/c/d/e), kein Speicherweg-Vertrag ändert sich inhaltlich, keine neue
  Pflicht-Prop an Trip-Mounts. Nach oben: `WeatherMetricsTab` ist der größte
  Organismus im Umbau bisher, die zehn Felder sind markup-verzahnt über
  ~15 Zeilen verteilt, und der Selbst-Speicher-Effekt ist Speicherweg-Kern
  (der Wirkort, den die SSR-Harness nie sieht).
- 🔴 **LoC-Limit 250/Workflow wird voraussichtlich überschritten** —
  `workflow.py set-field loc_limit_override 500` vor `/40` einplanen, nach
  `/50` per `workflow.py status` den tatsächlichen Delta-Wert gegenlesen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `versandPropsAus.ts`/`versandZustandsBruecke` (S6e, Spec `rework_2276_s6e_versand.md`) | module | Direkter Präzedenzfall für Bündel-Modul UND Proxy-Adapter — hier mit vereinfachter EINER Feldklasse statt drei |
| `alarmePropsAus.ts`/`corridorPropsAus.ts` (S6c/S6d) | module | Weitere Präzedenzfälle für das Bündel-Muster an allen drei Vergleichs-Mounts |
| `CompareOutlookLayoutControls.svelte` (#1720 S1) / `CompareHourlyLayoutControls.svelte` (S6b) | component | Lebende Kind-Präzedenzfälle für „Prop da → Bedienelement da" innerhalb von WMT selbst — WMT mountet beide bereits wertprop-rein |
| `frontend/src/lib/components/shared/__tests__/svelteInstanzPruefstand.ts` | Prüfstand | `umgebungFuer()`/`effekteVon()` — führt den Selbst-Speicher-`$effect`-Rumpf wirklich aus |
| `context_herkunft_zweige_eingefroren.test.ts` | test | Die 47er-Ratsche selbst; enthält heute fünf positionsstrikte `WeatherMetricsTab.svelte`-Einträge + einen unveränderten `weatherMetricsCompareSave.ts:534`-Eintrag |
| `docs/specs/modules/rework_2276_s6b_wetter_metriken.md` | spec | Begründet, warum `weatherMetricsCompareSave.ts:534` (Prädikat #67) bewusst bestehen bleibt — S4 AC-13, zweite Barriere |
| `docs/specs/modules/rework_2276_s4_wetter_metriken.md` (AC-13) | spec | Ursprüngliche Freigabe der „zweiten Barriere" im Prädikat — Konflikt mit AC-2 geht an S6h |
| `docs/specs/modules/rework_2276_s6f_bridge_umzug.md` | spec | Hält fest, dass die Hub-Klasseninstanz für WMT gebraucht wird und in S6g bestehen bleibt |
| `docs/context/refactor-2276-s6g-wmt-wertprops.md` | context | Analyse dieser Scheibe inkl. Schnitt-Entscheid (Re-Cut gegenüber „S6g = WMT, Hub-Klasse, AC-2") |

## Implementation Details

### Design-Entscheidungen

1. **`wetterMetrikenPropsAus(wiz)` statt dreifacher Inline-Glasur (Muster
   `versandPropsAus`).** Bei drei Mounts × zehn Werten + neun Rückrufen wären
   Inline-Adapter dreifache Gelegenheit zur Drift. Eine Funktion in
   `compare/wetterMetrikenPropsAus.ts` baut das komplette Bündel gegen eine
   strukturelle Quellen-Schnittstelle `WetterMetrikenZustandsQuelle` (kein
   Laufzeit-Import von `CompareWizardState`, Muster `VersandZustandsQuelle`).
   🔴 **Form-Auflage (prüfbar, kein Prosa-Wunsch):** `wetterMetrikenPropsAus(wiz)`
   wird an **allen drei** Vergleichs-Mounts **im Markup-Ausdruck selbst**
   aufgerufen — `{...wetterMetrikenPropsAus(wiz)}` — **niemals** in eine
   Skript-Variable gehoben (Begründung identisch zu S6c/S6d/S6e: ein
   eingefrorenes Objekt bestünde SSR-Prüfstand und AST-Wächter, fiele erst im
   Browser auf).

   | Wert | Typ | Default (falls Feld leer) |
   |---|---|---|
   | `activeMetricKeys` | `string[] \| null` | `null` (WMT materialisiert selbst über `materializeActiveMetricKeys`) |
   | `channelActiveMetricKeys` | `CompareChannelActiveMetrics` | `{ email: null, telegram: null, sms: null }` |
   | `officialAlertsEnabled` | `boolean` | `true` |
   | `dayWindowStartHour` | `number` | `DEFAULT_DAY_WINDOW_START_HOUR` |
   | `dayWindowEndHour` | `number` | `DEFAULT_DAY_WINDOW_END_HOUR` |
   | `hourlyMetricKeys` | `string[] \| null` | `null` |
   | `hourlyEnabled` | `boolean` | `true` |
   | `outlookMetricKeys` | `string[] \| null` | `null` |
   | `outlookMetricFormats` | `Record<string, boolean> \| null` | `null` |
   | `outlookEnabled` | `boolean` | `true` |

   Defaults sind identisch zu den bereits bestehenden Defaults in
   `wetterMetrikenSnapshotAus()` (`weatherMetricsCompareSave.ts:317-334`) —
   keine neue Fallback-Entscheidung, nur eine zweite Anwendungsstelle desselben
   Vokabulars.

2. **Genau EINE Feldklasse — die Vereinfachung dieser Scheibe gegenüber
   S6c/S6d/S6e.** Alle zehn Felder sind Snapshot-Felder (Klasse A in
   S6e-Terminologie): Wertprop + eigener oder gemeinsamer Rückruf, UND
   Mitgliedschaft in `wetterMetrikenZustandsBruecke`s `werte()` (der
   Speicherweg braucht den frischen Wert für Snapshot/Payload/Rollback). Es
   gibt weder ein persistenzloses Feld außerhalb der Brücke (wie `sendEmail`
   in S6e) noch tote Legacy-Restfelder ohne Bedienelement (wie die drei
   Alarm-Zustellungsfelder in S6e) — verifiziert gegen die vollständige
   Feldliste der bestehenden kombinierten Orchestrierung
   (`WetterMetrikenLayoutSnapshot`, zehn Felder, Kommentar dort sagt
   fälschlich „9 Felder" — wird in derselben Scheibe korrigiert).

3. **Gekoppelter Rückruf `onVergleichsMetrikenChange(active, channelActive)`
   für die einzige Zwei-Felder-Schreibung dieser Scheibe.** `toggleCompareMetric`
   (`WeatherMetricsTab.svelte:1095-1117`) schreibt heute `wiz.activeMetricKeys`
   UND — wenn eine globale Abwahl bereits vorhandene Kanal-Overrides durchschreibt
   (ADR-0050 Regel 3) — `wiz.channelActiveMetricKeys` in einem
   Funktionsdurchlauf. Ein 1:1-Rückruf je Feld würde diese Kopplung in zwei
   unabhängige, nacheinander feuernde Zuweisungen zerlegen — ein dazwischen
   lesender Snapshot (der Selbst-Speicher-Effekt liest beide Felder als
   Dependencies) sähe einen inkonsistenten Zwischenzustand. Deshalb bündelt
   das Prop-Interface **einen gemeinsamen** Rückruf, der beide Felder im
   selben synchronen Aufruf übergibt. `editCompareChannel` (kanal-lokale
   Umsortierung, `:1183-1188`, sowie `onCompareDndReorder`/`onCompareRemove`/
   `onCompareRestore`) schreibt nur `channelActiveMetricKeys` — auch dort wird
   derselbe gemeinsame Rückruf verwendet, mit dem unveränderten
   `activeMetricKeys`-Wert als erstem Argument (kein zweiter,
   feld-eigener Rückruf nötig, keine zweite Gelegenheit zur Drift zwischen
   zwei Schreibwegen desselben Feldpaars).

4. **Tech-Lead-Entscheid (revidiert): die Orchestrierungs-Fabrik wird EBENSO
   wie das Prädikat von `wiz` auf `zustand` umbenannt — wie in S6e, kein
   Restbestand des Begriffs `wiz` in `weatherMetricsCompareSave.ts`.**
   Ursprünglich war erwogen, nur das Prädikat umzubenennen und die Fabrik
   `wiz` behalten zu lassen (kleinerer Testfußabdruck). Das widerspricht
   jedoch dem Ziel der Scheibe: Ein `wiz`-Schlüssel bliebe genau der Begriff
   der Klasseninstanz im geteilten Baustein stehen, den AC-1 gerade entfernt
   — ein Restbestand, den S6h wieder aufräumen müsste. Die Umbenennung folgt
   deshalb **vollständig** dem S6e-Muster (`versandVergleichSpeicherung.ts`,
   Options-Feld `wiz`→`zustand`, Destrukturierung `const { client, zustand,
   … } = opt;`, alle internen Verwendungen `zustand`):
   - **Optionsfeld `WetterMetrikenVergleichSpeicherungOptionen.wiz` (`:440`)**
     → `zustand`; Destrukturierung `const { client, wiz, enqueueHubWrite,
     saveController } = opt;` (`:468`) → `const { client, zustand, … } =
     opt;`; alle internen Verwendungen (`:469`/`:476`/`:486`/`:496`) → `zustand`.
   - **Prädikatfeld (`:530`/`:534`)** wie zuvor beschrieben (Design-
     Entscheidung 6) → `zustand`.
   - **Zusätzlich, für vollständige Konsistenz innerhalb der Datei** (kein
     Bezeichner `wiz` soll irgendwo in `weatherMetricsCompareSave.ts`
     verbleiben): die private Hilfsfunktion `felder(wiz: WetterMetrikenZustand)`
     (`:308-309`) → `felder(zustand: WetterMetrikenZustand)`; die exportierte
     Funktion `wetterMetrikenSnapshotAus(wiz: WetterMetrikenZustand)`
     (`:317-318`) → `wetterMetrikenSnapshotAus(zustand: WetterMetrikenZustand)`;
     die exportierte Funktion `rollbackWetterMetrikenSnapshot(wiz: …, before,
     attempted)` (`:413-418`) → Parameter `zustand`. Alle drei sind reine,
     **positionell** aufgerufene Funktionen (`wetterMetrikenSnapshotAus(x)`,
     `felder(x)`, `rollbackWetterMetrikenSnapshot(x, before, current)`) — JS/TS
     kennt keine Schlüsselwort-Argumente für gewöhnliche Funktionen, eine
     Parameter-Umbenennung ändert daher **keinen** Aufrufer außerhalb dieser
     Datei (verifiziert: `WeatherMetricsTab.svelte`,
     `wetter_metriken_nutzlast_verliert_keine_daten.test.ts` und
     `compare_stundenverlauf_wertprops.test.ts` rufen alle drei nur
     positionell auf). Zugehörige Prosakommentare (`:312`, `:409`) werden an
     Ort und Stelle mitgezogen (`wiz`→`zustand`), zeilenneutral.
   - **NICHT angefasst:** das Wort „Wizard"/„wizard" in Prosa oder
     Bezeichnern wie `compare-wizard-state`/`compare_hub_wizard_bridge.test.ts`
     (Kommentar `:111`) — das ist eine Substring-Übereinstimmung mit „wiz",
     kein Bezeichner `wiz` selbst, und liegt außerhalb dieser Scheibe.
   - **Testfußabdruck:** `erstelleWetterMetrikenVergleichSpeicherung` hat elf
     direkte Testaufrufer, die je 1-2 literale `wiz:`-Schlüssel übergeben
     (`wetter_metriken_nutzlast_verliert_keine_daten.test.ts` ×2,
     `wetter_metriken_und_wertebereiche_teilen_active_metric_keys.test.ts`,
     `wetter_metriken_vergleich_speichert_einmal.test.ts`,
     `wetter_metriken_intra_gesture_kollision.test.ts`,
     `wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts`,
     `wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts`,
     `wetter_metriken_vergleich_flush_vor_pausieren.test.ts`,
     `wetter_metriken_reiterwechsel_verliert_nichts.test.ts`,
     `wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts`,
     `wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts`) — alle
     elf werden mechanisch auf `zustand:` umgestellt (Grep-Ersetzung, keine
     Assertion ändert sich inhaltlich; Testdateien zählen nicht gegen das
     LoC-Limit). Zusammen mit der bereits vorgesehenen Umstellung von
     `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts` (acht
     Prädikat-Aufrufe) sind das **zwölf** Testdateien mit Schlüssel-Rename.
   - **Ratschen-Prüfung (Auftrag des PO/Tech-Lead):** `weather-metrics-tab/weatherMetricsCompareSave.ts:534`
     steht in `context_herkunft_zweige_eingefroren.test.ts`s `EINGEFROREN`-Liste
     nur als reiner `Datei:Zeile`-Eintrag, NICHT in `BLEIBT_MIT_INHALT` — kein
     gefesselter Eintrag der Ratsche referenziert `wiz`/`!!p.wiz` als
     geschützten Inhalt. Der eingefrorene Zählbefehl matcht ausschließlich auf
     `context ===`/`context !==`, nicht auf `wiz`. Die Umbenennung ändert
     weder die Zeilenposition (Brücke bleibt unterhalb `:534`) noch den
     `context ===`-Teil der Zeile — **Folge: keine Ratschen-Anpassung
     notwendig**, weder Streichung noch neue `BLEIBT_MIT_INHALT`-Fesselung,
     über die bereits in Design-Entscheidung 9 beschriebene hinaus.

5. **`wetterMetrikenZustandsBruecke(werte, setzen)` als Proxy-Adapter (Muster
   `versandZustandsBruecke`, keine Namensumleitung).**
   `weatherMetricsCompareSave.ts` braucht für den Selbst-Speicher-Effekt und
   die Fabrik eine lebendige, mutierbare Referenz mit denselben Feldnamen wie
   `WetterMetrikenLayoutSnapshot` — die bestehende Rollback-Funktion
   (`:270-280`) schreibt `state.<feld> = before.<feld>` direkt, die Fabrik
   hält die Referenz in einer Closure. `WeatherMetricsTab.svelte` baut die
   Brücke lokal: `werte()` liest bei jedem Zugriff frisch aus den zehn
   aktuellen Props, `set` reicht den geänderten Wert an den passenden
   Rückruf weiter — bei `activeMetricKeys`/`channelActiveMetricKeys` an
   `onVergleichsMetrikenChange` (konstruiert aus dem geänderten Feld + dem
   jeweils anderen, frisch aus `werte()` gelesenen Feld, damit auch ein
   Rollback, der beide Felder nacheinander über zwei `set`-Aufrufe
   zurückschreibt, am Ende einen konsistenten Endzustand erzeugt), bei den
   acht übrigen Feldern an den jeweiligen `onXChange`-Rückruf. Snapshot- und
   Prop-Namen sind identisch (`activeMetricKeys`, `officialAlertsEnabled`, …)
   — keine `PROP_JE_FELD`-Namensumleitung nötig (wie S6d/S6e).
   **Platzierung ist Pflicht, keine Vorliebe (Auflage A1):** die Brücke steht
   **unterhalb Zeile 534** — an einer früheren Position verschöbe sie den
   eingefrorenen Eintrag `weatherMetricsCompareSave.ts:534` und machte die
   Ratsche grundlos rot.

6. **Aktiv-Prädikat `wiz` → `zustand` — Zeile 534 bleibt an Position, nur ihr
   Text ändert sich (Auflage A1, analog S6e DE-4).**
   `wetterMetrikenVergleichSpeicherungAktiv`s Parameterfeld `wiz` wird zu
   `zustand` umbenannt. Zeile 534
   (`return p.context === 'vergleich' && !!p.wiz && !!p.preset && !!p.saveController;`)
   **bleibt auf ihrer Position**, ihr **Text** ändert sich zu `!!p.zustand`.
   Weil diese Zeile heute **keine** `BLEIBT_MIT_INHALT`-Fesselung trägt und
   ihre Position stabil bleibt, gilt für sie weiterhin der **alte,
   positionsbasierte Vertrag** — wie `versandVergleichSpeicherung.ts:221` in
   S6e. Die Kontext-Prüfung `p.context === 'vergleich'` selbst — die
   freigegebene S4-AC-13-„zweite Barriere" — wird **nicht** entfernt, nur
   umbenannt. `WeatherMetricsTab.svelte` konstruiert die Brücke, die es als
   `zustand` übergibt, nur wenn die Wertprops tatsächlich gesetzt sind
   (Präsenz-Prüfung, s. Design-Entscheidung 7).

7. **Prop-da-Guard ersetzt `&& wiz`/`wiz?.` — JE BLOCK gegen SEIN EIGENES
   Feld geprüft, nicht gegen einen einzigen globalen Marker (Muster S6b
   DE-2, „Prop da → Bedienelement da").** Vier Stellen in
   `WeatherMetricsTab.svelte` nutzen heute die Präsenz von `wiz` als
   De-facto-Kontext-Diskriminator, obwohl die zugehörigen Abschnitte
   (`tagesfenster`/`stundenverlauf`/`ausblick`/`official_alerts`) laut
   `weatherMetricsTabSections.ts` für BEIDE Kontexte in der Sections-Liste
   stehen — WMT trägt für Route und Vergleich getrennte Markup-Zweige, und
   `&& wiz` verhindert heute das Doppel-Rendern:
   - `:1445` `{#if sections.includes('tagesfenster') && wiz}` (DayWindowCard,
     Vergleich) → `dayWindowStartHour !== undefined` (das für diesen Block
     einschlägige Feld; ein zweiter, route-eigener DayWindowCard-Block liegt
     an anderer Stelle der Datei, z. B. `:1651`, unverändert)
   - `:1466` `{#if sections.includes('stundenverlauf') && wiz}`
     (`CompareHourlyLayoutControls`) → `hourlyMetricKeys !== undefined`
   - `:1495` `{#if sections.includes('ausblick') && wiz && compareCatalogLoaded}`
     (`CompareOutlookLayoutControls`) → `outlookMetricKeys !== undefined && compareCatalogLoaded`
   - `:1520` `{@render officialAlertsToggle(wiz?.officialAlertsEnabled ?? true, onToggleVergleichOfficialAlerts)}`
     → `{@render officialAlertsToggle(officialAlertsEnabled ?? true, onToggleVergleichOfficialAlerts)}`
     (dieselbe `officialAlertsToggle`-Snippet-Definition wird an anderer
     Stelle der Datei für den Route-Zweig mit einem eigenen, lokalen
     Boolean aufgerufen — dieser Aufruf ist NICHT Gegenstand dieser
     Scheibe und bleibt unangetastet)

   Da Trip-Mounts **keinen** der zehn Wertprops jemals übergeben (sie bleiben
   dort strukturell `undefined`), ist jede der vier `!== undefined`-Prüfungen
   für sich genommen ein korrekter Ersatz — unabhängig davon, welches der
   zehn Felder gewählt wird. 🔴 **Pflicht für `/50`:** vor dem Umbau jedes
   der vier Guards den zugehörigen ROUTE-seitigen Markup-Zweig identifizieren
   und mit einem lokalen Prüflauf (Trip-Mount rendert, Vergleich-Mount
   rendert) bestätigen, dass kein Block doppelt oder gar keiner rendert —
   diese Spec benennt die Ersatz-Bedingung je Block, verifiziert aber nicht
   den vollständigen Route-seitigen Gegenpart (jenseits der gelesenen
   Zeilenbereiche dieser Analyse), siehe Known Limitations.

8. **Zeilenzahl-Vertrag wird für `WeatherMetricsTab.svelte` ausgesetzt —
   viertes Beispiel nach S6c/S6d/S6e, Bilanz wie S6e: 0 gestrichen, 5
   nachgeführt.** Der Kommentarblock von
   `context_herkunft_zweige_eingefroren.test.ts` sagt heute: „Fuer alle
   Dateien AUSSERHALB von `AlarmeTab.svelte`, den beiden Corridor-Bausteinen
   UND `VersandTab.svelte` gilt der alte Vertrag unveraendert weiter." Diese
   Ausnahme wird für S6g um `WeatherMetricsTab.svelte` erweitert — die zehn
   neuen Wertprops + neun Rückrufe im Script-Teil liegen alle **oberhalb**
   der eingefrorenen Zeilen `:545`/`:560`/`:589`/`:602`/`:1323`, ihre
   Verschiebung nach unten ist eine reine Positionsfolge, kein
   Verhaltensbefund. `/50` schreibt einen neuen Absatz nach dem S6e-Muster:
   „🔴 STAND S6g: der Zeilenzahl-Vertrag gilt zusätzlich NICHT für
   `WeatherMetricsTab.svelte` — dort werden **0** Einträge gestrichen und
   **5** auf neue Zeilennummern nachgeführt, per `BLEIBT_MIT_INHALT`
   inhaltlich gefesselt." Die neuen Zeilennummern werden **in GREEN
   gemessen, nicht in dieser Spec vorweggenommen** (Muster S6d/S6e: RED setzt
   nur die Vertragserweiterung, GREEN trägt die gemessenen Nummern samt
   `BLEIBT_MIT_INHALT`-Bedingungstext nach). Die fünf Bedingungstexte selbst
   ändern sich **nicht** (`context === 'route'`/`context === 'vergleich'` an
   `:545`/`:560`/`:589`/`:602`, die Markup-Gabelung an `:1323`) — nur ihre
   Zeilennummer.

9. **`weather-metrics-tab/weatherMetricsCompareSave.ts:534` bekommt bewusst
   KEINE neue `BLEIBT_MIT_INHALT`-Fesselung** (siehe Design-Entscheidung 9) —
   Parallel-Entscheidung zu `versandVergleichSpeicherung.ts:221` in S6e und
   `wertebereicheVergleichSpeicherung.ts:200` in S6d: die Datei ist nicht in
   der Ausnahmeliste, ihre eine geänderte Zeile bleibt an Position, der alte
   positionsbasierte Vertrag genügt.

10. **`localSchedule`-Mitbereinigung in `CompareTabs.svelte` (svelte-check-Fund,
   nicht WMT-spezifisch, aber im selben Commit wie der Mount-Umbau).**
   `let localSchedule = $state<string>(preset.schedule ?? 'manual')` steht
   heute an Zeile 630, wird aber bereits in `const status = $derived(...)` an
   Zeile 162 gelesen — ein svelte-check-Fehler (Nutzung vor Deklaration im
   Modul-Scope der Instanz). Die Deklaration wird vor ihre erste Nutzung
   gezogen; Verhalten von `status`/`statusInfo` bleibt unverändert (reine
   Reihenfolge-Korrektur, kein Logikwechsel).

### Wirkort je Zusicherung

| Zusicherung | Wirkort | Warum |
|---|---|---|
| AC-1 (kein `wiz`/`CompareWizardState` mehr in WMT) | Kern — AST/Compile | Statischer Fakt |
| AC-2 (alle drei Mounts speisen dasselbe Bündel ein, Aufrufform) | Kern — AST-Wächter | Mounts C/D sind in der CI-Ampel strukturell unbewacht für diesen Reiter (`layout-tab-vergleich.spec.ts` ist NICHT in `.github/ci_e2e_specs.txt`) |
| AC-3 (Wirkort-Guard: Selbst-Speicher-Effekt wirkt nur an Fläche B) | Kern — `effekteVon()`/`umgebungFuer()` | `$effect`-Rumpf, den SSR sonst verwirft |
| AC-4 (Speichern im Hub unverändert) | bestehende E2E, unverändert grün | `compare-wetter-metriken-speichert-selbst.spec.ts` + `compare-stundenverlauf-wertprops.spec.ts` decken bereits alle relevanten Abläufe ab |
| AC-5 (/compare/new zeigt/speichert dieselben Werte) | Staging (manuell) + Kern-AST-Wächter als struktureller Ersatznachweis | Keine CI-E2E-Abdeckung für den Wetter-Metriken-Reiter an Mounts C/D — `compare-editor-slice3.spec.ts` ist zwar in CI, deckt dort aber nur Orte/Idealwerte |
| AC-6 (Trip-Mounts unverändert) | bestehende E2E (Trip-Regressionsnetz) + Kern (Typecheck) | Reiner Regressionsschutz, keine neue Spec nötig |
| AC-7 (Prädikat UND Fabrik umbenannt, Barriere bleibt, Datei `wiz`-frei) | Kern — `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts` + elf Fabrik-Testdateien (Schlüssel `wiz`→`zustand` im selben Commit umgestellt) + Datei-weiter Grep-Check | Ohne die Testanpassung würde die Umbenennung das Prädikat vakuum-falsch machen (`p.zustand` immer `undefined`), nicht vakuum-grün; ohne den Grep-Check bliebe ein versehentlich stehengelassener `wiz`-Schlüssel unentdeckt, weil `--experimental-strip-types` nicht type-checkt |
| AC-8 (Ratsche bleibt bei 47, fünf Einträge nachgeführt) | Kern — `node --test` | Struktur-, kein Verhaltensnachweis |
| AC-9 (gekoppelter Rückruf atomar) | Kern — dedizierter Test in `compare_wetter_metriken_wertprops.test.ts` (Spy auf `onVergleichsMetrikenChange`) | Kein bestehender Test prüft Anzahl/Form der ausgelösten Rückrufe, nur den sichtbaren Endzustand |
| AC-10 (`localSchedule` vor Nutzung, svelte-check-Fehlerzahl sinkt) | Kern — lokaler `svelte-check`-Lauf + abgesenkte CI-Baseline (`BASELINE_ERRORS` 36→35) | Der CI-Job ist ein „darf nur besser werden"-Baseline-Gate, kein Null-Toleranz-Gate — ohne die Baseline-Absenkung im selben Commit würde eine Rückverschiebung den Job NICHT rot machen |

### Reihenfolge (Implementation Note)

1. `wetterMetrikenPropsAus.ts` und `wetterMetrikenZustandsBruecke` zuerst
   (sonst kompiliert der Baustein-Umbau nicht).
2. Dann `WeatherMetricsTab.svelte`: Props umstellen, alle ~15 Lese-/
   Schreibzugriffe umverdrahten, Selbst-Speicher-Block auf die Brücke
   umstellen, Prop-da-Guard statt `!!wiz`.
3. Dann die drei Elternteile: `CompareTabs.svelte` (Mount-Umbau +
   `localSchedule`-Reihenfolge-Fix), `CompareNewEditor.svelte` (beide Mounts).
4. Zuletzt die Ratschen-Nachführung — braucht die endgültigen Zeilennummern
   (RED schreibt die Vertragserweiterung, GREEN misst und trägt die fünf
   neuen Zeilennummern samt `BLEIBT_MIT_INHALT` nach) und die
   Kommentar-Korrektur „9 Felder"→„10 Felder".
5. Parallel/danach: Testdatei-Saatanpassung (Grep-Liste aus `/40`), neuer
   AST-Wächter, `weatherMetricsTabSharing.test.ts:69`-Anpassung, Staging-
   Durchklick `/compare/new`.

Die Scheibe bleibt unteilbar: die Brücke von den `WeatherMetricsTab.svelte`-
Änderungen zu trennen hinterließe einen nicht kompilierenden Zwischenstand.

## Expected Behavior

- **Input:** Im Reiter „Wetter-Metriken" des Ortsvergleichs (Hub `/compare/[id]`
  sowie Anlege-Desktop/-Mobil `/compare/new`) werden Metriken aus-/abgewählt,
  Kanal-Overrides pro Reihenfolge bearbeitet, der Amtliche-Warnungen-Schalter,
  das Tagesfenster, der Stundenverlauf und der 3-Tages-Ausblick bedient — wie
  heute.
- **Output:** Dieselbe sichtbare Auswahl, derselbe Speicherweg im Hub (eine
  kombinierte Orchestrierung über beide Domänen, eine `aenderungMelden()` pro
  Geste, Diff-Gate, Rollback), derselbe Dual-Write in den Wizard-Zustand beim
  Anlegen; keine nutzer-sichtbare Verhaltensänderung. Intern liest/schreibt
  `WeatherMetricsTab` im Vergleichs-Zweig keine `wiz`-Referenz mehr, sondern
  ausschließlich Wertprops und Rückrufe; `wiz` und der Aufbau des Prop-Bündels
  liegen jetzt in den Elternteilen (`CompareTabs.svelte`,
  `CompareNewEditor.svelte` über `wetterMetrikenPropsAus`).
- **Side effects:** `wetterMetrikenVergleichSpeicherungAktiv({context, zustand,
  preset, saveController})` prüft die Vergleichs-Bedingung nicht mehr über
  `!!wiz`, sondern über die Präsenz der Wertprops (Prop-da-Guard) — semantisch
  identisch, weil kein Trip-Mount und keine Anlege-Seite ohne `preset`/
  `saveController` die Wertprops jemals mit definierten Werten übergibt.

## Acceptance Criteria

- **AC-1 (`WeatherMetricsTab` ist im Vergleichs-Zweig wertprop-rein):** Im
  Reiter „Wetter-Metriken" des Ortsvergleichs ändert sich für Nutzerinnen und
  Nutzer nichts — technisch verliert die Komponente intern jeden direkten
  Zugriff auf das Wizard-Zustandsobjekt. Given
  `WeatherMetricsTab.svelte` importiert heute den Typ `CompareWizardState`
  (`:92`) und hat eine Prop `wiz?: CompareWizardState` (`:169`/`:178`) mit
  rund fünfzehn Lese-/Schreibzugriffsstellen (`:1096`-`:1520`) / When der
  Vergleichs-Zweig auf zehn Wertprops (`activeMetricKeys`,
  `channelActiveMetricKeys`, `officialAlertsEnabled`, `dayWindowStartHour`,
  `dayWindowEndHour`, `hourlyMetricKeys`, `hourlyEnabled`, `outlookMetricKeys`,
  `outlookMetricFormats`, `outlookEnabled`) + neun Rückrufe umgestellt wird /
  Then enthält die Datei keinen `wiz`-Zugriff und keinen
  `CompareWizardState`-Typ-Import mehr.
  - Test: Kern — AST-Scan in `compare_wetter_metriken_wertprops.test.ts`
    (Muster AC-1 aus `compare_versand_wertprops.test.ts`): kein `wiz`- und
    kein `CompareWizardState`-Identifier mehr im Instanz-Skript — geprüft
    werden sowohl freistehende Bezeichner (`wiz`, `wiz!`, `wiz?.`) als auch
    `wiz` als Objekt-Schlüssel in einem Funktionsaufruf (z. B. versehentlich
    `erstelleWetterMetrikenVergleichSpeicherung({ wiz: bruecke, … })` statt
    `{ zustand: bruecke, … }`); die Prop-Schnittstelle bindet alle 19
    freigegebenen Namen (10 Werte + 9 Rückrufe).
  - Mutations-Gegenprobe: einen `wiz`-Zugriff versehentlich im
    Selbst-Speicher-Effekt stehen lassen ⇒ der AST-Scan wird rot; Typecheck
    allein erkennt eine noch vorhandene optionale Prop nicht als Fehler.
    Zweite Mutation: `zustand:` beim Aufruf von
    `erstelleWetterMetrikenVergleichSpeicherung`/`wetterMetrikenVergleichSpeicherungAktiv`
    versehentlich wieder zu `wiz:` ändern ⇒ derselbe AST-Scan wird rot, weil
    er auch Objekt-Schlüssel erfasst, nicht nur freistehende Bezeichner —
    `--experimental-strip-types` type-checkt nicht, ein falscher Schlüssel
    wäre sonst erst zur Laufzeit (oder gar nicht, da `WetterMetrikenZustand`
    lose typisiert ist) sichtbar.

- **AC-2 (alle drei Vergleichs-Mounts speisen dasselbe Bündel ein,
  Aufrufform geprüft):** Egal ob im Ortsvergleich-Hub oder beim Neuanlegen
  (Desktop und Mobil) — der Wetter-Metriken-Reiter bekommt an allen drei
  Stellen exakt dieselben Werte und Bedienmöglichkeiten. Given Mount (B)
  `CompareTabs.svelte:1006` (`wiz={wizardState}`), Mount (C)
  `CompareNewEditor.svelte:382` (`{wiz}`), Mount (D)
  `CompareNewEditor.svelte:483` (`{wiz}`) übergeben heute `wiz` / When alle
  drei Mounts auf `{...wetterMetrikenPropsAus(wiz)}` umgestellt werden /
  Then rendern an allen drei Mounts weiterhin alle Bedienelemente, für die
  `wetterMetrikenPropsAus` einen Rückruf liefert, UND
  `wetterMetrikenPropsAus(wiz)` steht im Markup-Ausdruck selbst (nicht in
  einer Skript-Variable gehoben).
  - Test: Kern — AST-Wächter in `compare_wetter_metriken_wertprops.test.ts`,
    der über alle drei Vergleichs-Mounts prüft, dass `wetterMetrikenPropsAus(wiz)`
    als Spread-Ausdruck im Markup-Knoten selbst aufgerufen wird und keine der
    19 Prop-Bindungen fehlt.
  - Mutations-Gegenprobe: `{...wetterMetrikenPropsAus(wiz)}` in eine
    Skript-Variable heben und diese spreaden ⇒ dieser Wächter wird rot (ein
    reines Werte-Diff bliebe grün, weil die Werte selbst korrekt sind — nur
    ihre Reaktivität bricht, was erst im Browser sichtbar würde).

- **AC-3 (Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Fläche B):**
  Automatisches Speichern beim Bearbeiten darf ausschließlich im
  Ortsvergleich-Hub passieren — auf der Tour und beim Neuanlegen eines
  Vergleichs darf nie im Hintergrund gespeichert werden. Given
  `vergleichSpeicherung` entsteht nur, wenn
  `wetterMetrikenVergleichSpeicherungAktiv({context, zustand, preset,
  saveController})` wahr ist, wobei `zustand` jetzt aus der Prop-Präsenz
  (Prop-da-Guard) statt aus `!!wiz` abgeleitet wird / When der Effekt-Rumpf
  über `effekteVon()` an den negativen Orten (Trip, Anlegen ohne
  `preset`/`saveController`) wirklich ausgeführt wird / Then bleibt der
  Rumpf dort wirkungslos (kein `aenderungMelden()`-Aufruf), und am positiven
  Ort (Fläche B, `preset`+`saveController` gesetzt) wirkt er.
  - Test: Kern — `compare_wetter_metriken_wertprops.test.ts`, Muster
    `compare_versand_wertprops.test.ts` AC-2 (`umgebungFuer()`/`effekteVon()`).
  - Mutations-Gegenprobe: `wetterMetrikenVergleichSpeicherungAktiv` auf
    `() => false` verfälschen ⇒ der Effekt wirkt nirgends mehr, auch nicht am
    positiven Ort (Positiv-Gegenprobe); auf `() => true` verfälschen ⇒ der
    Effekt wirkt an den negativen Orten weiter (Negativ-Gegenprobe). Kein
    E2E-Test fängt diese Mutation, weil nur der Hub browserseitig geprüft
    wird und dort die Bedingung strukturell immer erfüllt ist.

- **AC-4 (Speichern im Hub bleibt unverändert — eine PUT je Geste, gleicher
  Payload, Rollback bei Fehler):** Wer im Ortsvergleich-Hub eine Metrik
  auswählt, den Stundenverlauf einstellt oder den Ausblick anpasst, sieht
  die Änderung sofort gespeichert — wie bisher, ohne Speichern-Knopf. Given
  `compare-wetter-metriken-speichert-selbst.spec.ts` (Grundauswahl,
  Amtliche-Warnungen-Schalter, Tagesfenster, Ausblick, Konflikt/Rollback)
  und `compare-stundenverlauf-wertprops.spec.ts` (Stundenverlauf-Auswahl,
  Ein/Aus-Schalter) decken diese Abläufe heute ab / When `WeatherMetricsTab`
  im Hub-Mount auf `wetterMetrikenPropsAus(wizardState)` umgestellt wird /
  Then bleiben beide Specs ohne inhaltliche Änderung grün — jede
  Nutzergeste löst weiterhin genau eine PUT-Anfrage mit demselben
  Voll-Spread-Payload aus, ein gescheiterter PUT stellt den vorherigen
  Zustand wieder her.
  - Test: Live-E2E — `frontend/e2e/compare-wetter-metriken-speichert-selbst.spec.ts`
    und `frontend/e2e/compare-stundenverlauf-wertprops.spec.ts` (beide
    bereits in `.github/ci_e2e_specs.txt`), keine neue Datei.

- **AC-5 (`/compare/new` zeigt und speichert dieselben Werte —
  Staging-Durchklick, weil der Wetter-Metriken-Reiter dort in keiner
  CI-E2E-Spec hängt):** Wer einen neuen Vergleich anlegt, kann die
  Wetter-Metriken-Auswahl genauso treffen wie bisher, und sie landet
  unverändert im fertig gespeicherten Vergleich. Given
  `layout-tab-vergleich.spec.ts` und `compare-hourly-metric-order.spec.ts`
  (beide üben WMT auf `/compare/new` aus) sind heute NICHT in
  `.github/ci_e2e_specs.txt`; `compare-editor-slice3.spec.ts` ist zwar in
  der CI-Ampel, deckt auf `/compare/new` aber nur Orte/Idealwerte ab, nicht
  den Wetter-Metriken-Reiter / When Mounts (C)/(D) auf
  `{...wetterMetrikenPropsAus(wiz)}` umgestellt werden / Then zeigt ein neu
  angelegter Vergleich im Hub (`/compare/[id]`) nach Abschluss des
  Anlege-Assistenten dieselben, während des Anlegens gewählten
  Metrik-/Stundenverlauf-/Ausblick-/Tagesfenster-Werte wie vor dieser
  Scheibe.
  - Test: manueller Staging-Durchklick `/compare/new` (mit
    `layout-tab-vergleich.spec.ts`/`compare-hourly-metric-order.spec.ts` als
    Klick-Leitfaden, kein automatisierter CI-Lauf) + Kern-AST-Wächter aus
    AC-2 als struktureller Ersatznachweis der Verdrahtung.
  - Mutations-Gegenprobe: einen Rückruf (z. B. `onHourlyMetricKeysChange`) im
    Mount weglassen ⇒ AC-2-Wächter wird rot (fehlende Prop-Bindung), der
    Staging-Durchklick bestätigt zusätzlich den sichtbaren Ausfall im
    Browser.

- **AC-6 (Trip-Mounts bleiben vollständig unverändert):** Der
  Wetter-Metriken-Reiter einer einzelnen Tour verhält sich exakt wie vorher
  — diese Scheibe betrifft ausschließlich den Ortsvergleich. Given
  `TripTabs.svelte:224`, `TripEditView.svelte:201`,
  `TripNewEditor.svelte:881/:1113` mounten `WeatherMetricsTab` heute ohne
  `wiz`, mit `context="route"` (Default) / When die zehn neuen Wertprops als
  optional deklariert werden, ohne dass ein Trip-Mount sie übergibt / Then
  bleibt das Verhalten der Tour identisch — kein Trip-Mount wird angefasst.
  - Test: bestehendes Trip-E2E-Regressionsnetz bleibt ohne Änderung grün +
    Kern (Typecheck bleibt grün, ohne dass Trip-Mounts angepasst werden
    müssen).

- **AC-7 (Prädikat UND Fabrik umbenannt, S4-AC-13-Barriere bleibt scharf,
  kein Bezeichner `wiz` bleibt in `weatherMetricsCompareSave.ts`):** Die
  Regel „automatisches Speichern nur im Ortsvergleich-Hub, nie auf der Tour"
  bleibt technisch genauso hart durchgesetzt wie vor dieser Scheibe — nur
  interne Namen ändern sich, und der Begriff der alten Klasseninstanz
  (`wiz`) verschwindet aus der gesamten Speicherweg-Datei. Given
  `weatherMetricsCompareSave.ts:534` lautet heute `return p.context ===
  'vergleich' && !!p.wiz && !!p.preset && !!p.saveController;`, geschützt
  durch die freigegebene S4-AC-13 als zweite Barriere; `erstelleWetterMetrikenVergleichSpeicherung`s
  Optionsfeld heißt heute ebenfalls `wiz` (`:440`); der zugehörige
  Prädikat-Test `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts`
  ruft das Prädikat an acht Stellen mit dem Schlüssel `wiz` auf, elf weitere
  Testdateien rufen die Fabrik mit dem Schlüssel `wiz` auf / When BEIDE
  Funktionen im selben Commit auf `zustand` umbenannt werden (Prädikat-Zeile
  bleibt an Position, Text ändert sich zu `!!p.zustand`; Fabrik-Optionsfeld,
  Destrukturierung und interne Verwendung ändern sich zu `zustand`; die drei
  positionell aufgerufenen Helfer `felder`/`wetterMetrikenSnapshotAus`/
  `rollbackWetterMetrikenSnapshot` ebenso) UND alle 19 betroffenen
  Testaufrufe (8 Prädikat + 11 Fabrik) im selben Commit auf den Schlüssel
  `zustand` umgestellt werden / Then bleibt das Prädikat funktional
  identisch (die „Positivfall"-Prüfung liefert weiterhin `true`), die
  Kontext-Prüfung bleibt erhalten, `weatherMetricsCompareSave.ts:534`
  bekommt bewusst keine neue `BLEIBT_MIT_INHALT`-Fesselung (alter
  positionsbasierter Vertrag, Auflage A1 analog S6e DE-4/6), und in der
  gesamten Datei kommt der Bezeichner `wiz` an keiner Stelle mehr vor.
  - Test: Kern — `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts`
    (nach der Schlüssel-Umstellung), insbesondere die „Positivfall"-Prüfung
    (`:42`) und die AC-13-Prüfung „die Kontext-Prüfung allein entscheidet"
    (`:78-82`); die elf Fabrik-Testdateien bleiben nach der Schlüssel-
    Umstellung inhaltlich unverändert grün; zusätzlich ein Datei-weiter
    Grep-Check in `compare_wetter_metriken_wertprops.test.ts` (analog dem
    HERKUNFT-Ratschen-Muster, relativ zur Testdatei aufgelöst) auf `\bwiz\b`
    in `weather-metrics-tab/weatherMetricsCompareSave.ts` — erwartet: 0
    Treffer außerhalb von Kommentaren, die das Wort „Wizard" enthalten.
  - Mutations-Gegenprobe: die Umbenennung an `:534` durchführen, den
    Testaufruf-Schlüssel dabei versehentlich bei `wiz` belassen ⇒ die
    „Positivfall"-Prüfung wird fälschlich rot, weil `p.zustand` immer
    `undefined` bleibt — dieser Fehlerzustand selbst ist der Beleg, dass die
    Umbenennung ohne die Testanpassung das Prädikat unbemerkt lahmlegen
    würde (vakuum-falsch statt vakuum-grün). Zusätzlich, nach korrekter
    Testanpassung: die Kontext-Prüfung `p.context === 'vergleich'` aus dem
    Prädikat entfernen ⇒ die AC-13-Prüfung wird rot wie schon in S4
    dokumentiert. Dritte Mutation: die Fabrik-Umbenennung an `:440`
    rückgängig machen (Optionsfeld wieder `wiz`), Testaufrufe aber bei
    `zustand:` belassen ⇒ TypeScript-Build bricht (Pflichtfeld `zustand`
    fehlt), UND der Datei-weite Grep-Check wird rot — zwei unabhängige
    Wirkorte fangen dieselbe Regression.

- **AC-8 (Ratsche bleibt bei 47, fünf Einträge bewusst nachgeführt):** Ein
  automatisierter Wächter, der zählt, wie viele Programmstellen noch
  „Tour oder Vergleich?" unterscheiden, meldet nach dieser Scheibe weiterhin
  dieselbe Zahl — die fünf betroffenen Stellen rutschen nur nach unten,
  keine verschwindet und keine neue kommt hinzu. Given
  `context_herkunft_zweige_eingefroren.test.ts` hält heute
  `WeatherMetricsTab.svelte:545/560/589/602/1323` als fünf positionsstrikte
  Einträge, `EINGEFROREN_SOLL_ANZAHL = 47` / When im selben Commit wie der
  Umbau die fünf Einträge auf ihre neu gemessenen Zeilennummern nachgeführt
  und per `BLEIBT_MIT_INHALT` mit wortgleichem Bedingungstext gefesselt
  werden, der Kommentarblock um die S6g-Ausnahme erweitert wird / Then ist
  der Ratschen-Test grün, `EINGEFROREN_SOLL_ANZAHL` bleibt bei 47, und
  `weather-metrics-tab/weatherMetricsCompareSave.ts:534` bleibt unverändert
  an seiner Position (ohne neue Fesselung).
  - Test: Kern — `node --test` auf
    `context_herkunft_zweige_eingefroren.test.ts`.
  - Mutations-Gegenprobe: einen der fünf nachgeführten Einträge zusätzlich
    aus `EINGEFROREN` streichen, ohne die zugehörige Bedingung im Quelltext
    zu entfernen ⇒ der reale Zählbefehl liefert den Eintrag weiterhin, der
    Mengenvergleich schlägt fehl (Ist-Menge enthält einen Eintrag, der nicht
    in der Soll-Liste steht). Zusätzlich: einen `BLEIBT_MIT_INHALT`-Eintrag
    auf eine fremde, tatsächlich existierende Zeile im 8-Zeilen-Fenster
    setzen, ohne den Bedingungstext anzupassen ⇒ die `zeile`-Prüfung schlägt
    fehl.

- **AC-9 (gekoppelter Rückruf setzt `activeMetricKeys` und
  `channelActiveMetricKeys` atomar):** Wenn eine Metrik in der Grundauswahl
  abgewählt wird und dabei automatisch aus vorhandenen Kanal-Ausnahmen
  entfernt wird, geschieht das als EIN Schreibvorgang — nie als zwei
  getrennte, von denen der zweite verlorengehen könnte. Given
  `toggleCompareMetric` schreibt heute beide Felder direkt auf `wiz` in
  einem Funktionsdurchlauf (`WeatherMetricsTab.svelte:1095-1117`) / When
  beide Felder nur noch über EINEN Rückruf
  `onVergleichsMetrikenChange(active, channelActive)` geschrieben werden,
  der beide Werte im selben synchronen Aufruf übergibt / Then setzt ein
  einziger Aufruf des von `wetterMetrikenPropsAus` gebauten Rückrufs beide
  Felder der zugrunde liegenden Quelle korrekt, und ein Rollback nach
  gescheitertem PUT (über die Proxy-Brücke) findet nach einer Abwahl mit
  Kanal-Durchschreibung beide Felder auf ihrem vorherigen Stand vor —
  unabhängig davon, ob der Snapshot mitten im Schreiben gelesen würde.
  - Test: Kern — dedizierter Test in `compare_wetter_metriken_wertprops.test.ts`
    mountet `WeatherMetricsTab` im Prüfstand mit einem Spy anstelle von
    `onVergleichsMetrikenChange`, wählt eine Metrik mit bestehendem
    Kanal-Override ab (Aufruf von `toggleCompareMetric` über das
    entsprechende Bedienelement) und prüft: genau EIN Aufruf des Spys,
    dessen zwei Argumente die neue `activeMetricKeys`- UND die bereits
    durchgeschriebene `channelActiveMetricKeys`-Auswahl tragen.
  - Mutations-Gegenprobe: `onVergleichsMetrikenChange` in zwei separate
    Rückrufe (`onActiveMetricKeysChange`, `onChannelActiveMetricKeysChange`)
    aufteilen, `toggleCompareMetric` entsprechend auf zwei Aufrufe umstellen
    ⇒ der dedizierte Test wird rot, weil der Spy jetzt zweimal statt einmal
    aufgerufen wird bzw. keiner der beiden Einzelaufrufe beide Felder trägt.
    Kein anderer Test im Bestand sieht diese Regression: die bestehenden
    E2E-Specs prüfen nur den sichtbaren Endzustand nach der Geste, nicht
    die Anzahl oder Form der intern ausgelösten Rückrufe.

- **AC-10 (`localSchedule`-Deklaration vor Nutzung, svelte-check-Fehlerzahl
  sinkt messbar):** Ein internes Code-Qualitäts-Werkzeug meldet für diese
  Datei einen Fehler weniger als vorher — sichtbares Verhalten des
  Aktiv/Pausiert-Status im Hub ändert sich nicht. Given `CompareTabs.svelte`
  nutzt `localSchedule` heute in `const status = $derived(...)` an Zeile
  162, deklariert wird die Variable aber erst an Zeile 630
  (svelte-check-Fehler „Nutzung vor Deklaration", eingeschlossen in der
  heutigen CI-Baseline `BASELINE_ERRORS: 36`, `.github/workflows/ci.yml:133`
  — die Baseline ist ein „darf nur besser werden"-Gate, kein
  Null-Toleranz-Gate, weshalb dieser eine Fehler den PR #2411-Merge nicht
  blockiert hat) / When die Deklaration vor ihre erste Nutzung gezogen und
  im selben Commit `BASELINE_ERRORS` in `.github/workflows/ci.yml` von 36
  auf 35 abgesenkt wird (Konvention der Datei, Kommentar `:160-162`
  „Besser als Baseline — BASELINE_ERRORS/BASELINE_WARNINGS absenken") /
  Then meldet ein lokaler `npx svelte-check`-Lauf keinen
  „Nutzung-vor-Deklaration"-Fund mehr für `CompareTabs.svelte`, und das
  Verhalten von `status`/`statusInfo` (Aktiv/Pausiert-Anzeige im Hub) bleibt
  unverändert.
  - Test: Kern — lokaler `npx svelte-check --tsconfig ./tsconfig.json
    --output machine`-Lauf (dieselbe Befehlsform wie der CI-Job), Prüfung
    auf einen um 1 gesunkenen `ERRORS`-Wert; zusätzlich der abgesenkte
    `BASELINE_ERRORS`-Wert im CI-Job als Regressionsschutz.
  - Mutations-Gegenprobe: die Deklaration wieder hinter die Nutzung
    verschieben, OHNE `BASELINE_ERRORS` wieder anzuheben ⇒ der
    `svelte-check`-CI-Job schlägt jetzt fehl (`ERRORS` 36 > abgesenkte
    Baseline 35) — VOR der Baseline-Absenkung hätte dieselbe
    Rückverschiebung den Job NICHT rot gemacht, weil 36 ≤ 36 die
    ursprüngliche Baseline erfüllt. Die Baseline-Absenkung im selben Commit
    ist deshalb kein kosmetischer Zusatz, sondern der Teil, der die
    Mutations-Gegenprobe erst scharf macht.

## Known Limitations

- **Doppelquelle als Dauerzustand ist verboten.** „Wertprop wenn da, sonst
  `wiz`" ist genau das Anti-Muster, das S6 beseitigen soll. Die Umstellung
  ist an allen drei Vergleichs-Mounts vollständig oder unterbleibt.
- **AC-2-Endbilanz der 14 verbleibenden HERKUNFT-Einträge, Ratschen-
  Endzustand und der Konflikt AC-2 ↔ S4 AC-13 sind NICHT Teil dieser
  Scheibe.** Sie gehen an S6h, die #2276 schließt — Empfehlung dort: ADR
  „eine Barriere je Speicherweg, gebunden an Wertprop-Präsenz statt
  `context`" ODER eine explizite AC-2-Abweichung zur PO-Freigabe.
- **Die Hub-Klasseninstanz `new CompareWizardState()` bleibt bestehen** —
  eine Umstellung auf Plain-`$state` ist kein Ticket-AC und geht an S6h
  (nach S6g ist sie ein reiner Feldcontainer ohne WMT-Abhängigkeit mehr,
  aber `/compare/new` nutzt sie weiterhin für `saveNewPreset()`).
- **Mounts C/D sind in der CI-Ampel strukturell unbewacht für diesen Reiter**
  (`layout-tab-vergleich.spec.ts`, `compare-hourly-metric-order.spec.ts`
  nicht in `.github/ci_e2e_specs.txt`) — deshalb trägt AC-5 den Nachweis über
  einen manuellen Staging-Durchklick statt einer weiteren CI-E2E-Spec.
- **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`
  zurück** — `/70-deploy` überspringt dann die gesamte
  Staging-Validierung. Nach **jedem** Commit dieser Scheibe gegenlesen.
- **`weather-metrics-tab/weatherMetricsCompareSave.ts:534` behält seine
  Position ohne neue `BLEIBT_MIT_INHALT`-Fesselung** (Design-Entscheidung
  6/9) — ihr Schutz bleibt der alte, positionsbasierte Vertrag. Eine
  künftige Scheibe, die diese Zeile erneut inhaltlich ändert, MUSS erneut
  prüfen, ob eine Fesselung inzwischen nötig geworden ist.
- **Die vier `&& wiz`/`wiz?.`-Markup-Guards (`:1445`/`:1466`/`:1495`/`:1520`)
  werden durch je EIN feldspezifisches `!== undefined` ersetzt (Design-
  Entscheidung 7).** Diese Spec benennt die Ersatzbedingung je Block, hat
  aber den vollständigen route-seitigen Markup-Gegenpart nicht Zeile für
  Zeile gegengelesen (jenseits der für diese Analyse gelesenen Bereiche).
  `/50` MUSS vor dem Umbau jedes einzelnen Guards durch einen lokalen
  Render-Vergleich (Trip-Mount vs. Vergleich-Mount) bestätigen, dass kein
  Block doppelt oder gar nicht rendert.
- **Die konkreten neuen Zeilennummern für
  `WeatherMetricsTab.svelte:545/560/589/602/1323`-Nachfolger stehen erst
  nach GREEN fest** — diese Spec legt nur die Vertragserweiterung und die
  Bilanz (0/5) fest, wie bei S6d/S6e.
- **Tote Prop `onOutlookCommit` und `flushPendingLayoutSave`/
  `flushPendingWeatherMetricsSave` bleiben bestehen** — Checkbox in #1199,
  kein eigenes Issue (Nebenbefund-Triage, keines der drei
  Eigenschaftskriterien erfüllt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Wertprops + Rückrufe statt `wiz` ist mit
  `CompareOutlookLayoutControls` (#1720 S1), `CompareHourlyLayoutControls`
  (S6b, live `8207c157`), `AlarmeTab` (S6c, live `c737159e`),
  `CorridorEditor(Mobile)` (S6d, live `930ccdc0`) und `VersandTab` (S6e)
  bereits entschieden und produktiv erprobt — diese Scheibe wendet dasselbe,
  bereits akzeptierte Muster auf den letzten geteilten Reiter-Organismus an
  und trifft keine neue Architekturentscheidung. Die Bündel-Funktion
  `wetterMetrikenPropsAus(wiz)`, der Proxy-Adapter
  `wetterMetrikenZustandsBruecke` und der gekoppelte Rückruf
  `onVergleichsMetrikenChange` (Design-Entscheidung 3) sind lokale
  Umsetzungsentscheidungen innerhalb dieses Musters, kein Architekturwechsel.
  Der Konflikt AC-2 ↔ S4 AC-13 (Design-Entscheidung 6, Known Limitations)
  könnte in S6h ein eigenes ADR auslösen — das ist explizit NICHT Teil
  dieser Scheibe.

## Changelog

- 2026-09-24: Initial spec created (Scheibe S6g von #2276, Epic #2345)
- 2026-09-24: Tech-Lead-Revision DE-4 — `erstelleWetterMetrikenVergleichSpeicherung`
  wird wie in S6e EBENFALLS von `wiz` auf `zustand` umbenannt (nicht nur das
  Prädikat), inkl. der drei internen Helfer `felder`/`wetterMetrikenSnapshotAus`/
  `rollbackWetterMetrikenSnapshot`, damit in `WeatherMetricsTab.svelte` UND
  `weatherMetricsCompareSave.ts` kein Bezeichner `wiz` mehr vorkommt (AC-1
  geschärft, AC-7 erweitert, elf zusätzliche Fabrik-Testdateien in Affected
  Files aufgenommen, Known-Limitation-Eintrag zur vormaligen Abweichung
  entfernt). Ratschen-Prüfung ergab: keine Auswirkung, da
  `weatherMetricsCompareSave.ts:534` nur positionsbasiert in `EINGEFROREN`
  steht und in keinem `BLEIBT_MIT_INHALT`-Eintrag inhaltlich gefesselt ist.

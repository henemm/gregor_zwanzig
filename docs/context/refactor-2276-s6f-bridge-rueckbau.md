# Context: refactor-2276-s6f-bridge-rueckbau

Issue #2276 (Epic #2345, Etappe P1) — Scheibe **S6f**: Bridge-Rückbau im Ortsvergleich-Hub,
AC-2/AC-4-Bilanz, Schlangen-Entscheid dokumentieren. Stand `origin/main` `d14e7750`
(S1–S6e live). Planungsgrundlage: `docs/context/rework-2276-s6-rueckbau.md` (Tabelle ~:471,
F1 :335-364, F4 :320-333, AC-Neufassung :382-410).

## Request Summary
Die Compare-Klebeschicht `compare/compareHubWizardBridge.ts` (455 Z.) verliert jeden
produktiven Importeur (AC-4), die Hub-Instanz von `CompareWizardState` fällt aus
`CompareTabs.svelte`, und die verbleibenden `context ===`-Verzweigungen in `shared/` werden
mit fachlichem Grund bilanziert (AC-2). Die Schreibschlange bleibt erhalten.

## 🔴 Blockierender Befund: Voraussetzung „kein shared/-Baustein hängt am Wizard" ist NICHT erfüllt
- `shared/WeatherMetricsTab.svelte:92` importiert noch `type CompareWizardState`, Prop
  `:169 wiz?`, rund 40 `wiz`-Zugriffe (`:1096-1187` activeMetricKeys/channelActiveMetricKeys,
  `:1226-1238` outlook*, `:1247` officialAlertsEnabled, `:1261-1279` Speicherweg,
  `:1445-1451` dayWindow, `:1466-1510` hourly/outlook-Mounts).
- Gemountet mit `wiz` in `CompareTabs.svelte:1008` und `CompareNewEditor.svelte:382/483`.
- S6b-Spec (`rework_2276_s6b_wetter_metriken.md:26/48`): „WeatherMetricsTab behält wiz —
  andere Scheibe". Die Aussage der S6e-Spec (`:33`), S6e sei die letzte wiz-Abbau-Scheibe, stimmt nicht.
- ⇒ S6f muss WeatherMetricsTab auf Wertprops umstellen (Bündel `wetterMetrikenPropsAus`
  nach Muster alarme/corridor/versandPropsAus) — oder eine Vor-Scheibe wird geschnitten.
  **Schnitt-Frage für `/20-analyse`.**
- `setContext('compare-wizard-state', …)` in `CompareTabs.svelte:330` hat im Hub keinen Leser
  (nur `/compare/new`: `Step2Orte.svelte:30`, `CompareNewEditor.svelte:67`) ⇒ toter Code.

## ACs von #2276 (maßgeblich für S6f)
- **AC-2 (Ticket):** nur fachliche `context ===`-Zweige (Orte/Etappen, Radar, Laufzeit) in
  `shared/`, Liste mit Grund je Zweig in der Spec. **Neufassung** (S6a-Spec :90-98):
  „keine HERKUNFT-Verzweigung; verbleibende FACHLICH oder DARSTELLEND, einzeln begründet".
- **AC-4:** `git grep compareHubWizardBridge` ⇒ kein produktiver Importeur. Achtung:
  wörtliches grep trifft auch Kommentare (VersandTab:27, versandVergleichSpeicherung:10,
  alarmeVergleichSpeicherung:9, wertebereicheVergleichSpeicherung:10,
  weatherMetricsCompareSave:5/12/129/184, CompareTabs:207) — Messverfahren in der Spec festlegen.
- AC-1/AC-3/Datenerhalt: bereits durch S2–S6e getragen; darf nicht regressieren.

## Related Files
| File | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | Klebeschicht, Exporte s.u. |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Klasse (191 Z.), bleibt für `/compare/new` bis #2277 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` (1.461 Z.) | einziger Hub-Nutzer von Bridge + wizardState |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | hängt noch an `wiz` (s.o.) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | Speicherweg WMT, Prädikat :534 (`!!p.wiz`), `flushPendingLayoutSave` :231 ohne Produktiv-Aufrufer |
| `frontend/src/routes/compare/+page.svelte:26/133-152` | Listen-Toggle via `buildFreshTogglePutPayload`, rohes `fetch` ohne If-Match |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts:17` | `import type { AlarmHydrationTarget }` aus Bridge |
| `frontend/src/lib/components/compare/{alarme,corridor,versand}PropsAus.ts` | Wertprops-Bündel, strukturell typisiert (Plain-`$state` genügt) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`, `compare/steps/Step2Orte.svelte`, `routes/compare/new/+page.svelte` | `/compare/new` — Scope #2277, E2E-unbewacht |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | HERKUNFT-Ratsche, Soll **47** (:224), Prüfdatum 2026-12-19 |
| `frontend/src/routes/compare/[id]/+page.svelte:49/166/193/210` | Kopf-Edits mit eigenem `currentPreset` außerhalb der Schlange (#2381, nicht Scope) |

### Bridge-Exporte → produktive Nutzer
| Export | Produktiv |
|---|---|
| `hydrateWizardStateFromPreset` :53 | CompareTabs:342 |
| `buildHubPutPayload` :138 | CompareTabs:267 (Orte) |
| `snapshotForRollback` :230 | CompareTabs:200, :713 |
| `buildToggleActivePutPayload` :244 | CompareTabs:660 + intern von :264 |
| `buildFreshTogglePutPayload` :264 | `routes/compare/+page.svelte:136` |
| `hubActivationBanner` :288 | CompareTabs:1087 |
| `createPutQueue` :340 | CompareTabs:208 (29 Test-Prüfstände importieren es) |
| `AlarmHydrationTarget` :360 (Typ) | `shared/alarmeVergleichSpeicherung.ts:17` |
| `hydrateAlarmFieldsFromPreset` :408 | CompareTabs:425 |
| `HubWizardFields`/`HubEdit`/`PutQueue` (Typen) | 0 extern; angeheftet in `totcode_rueckbau_speicherweg.test.ts:180-181` |

Kein Laufzeit-Export ist heute tot ⇒ AC-4 heißt **umziehen**, nicht nur löschen.

### wizardState-Nutzung in CompareTabs
Context :330 (tot im Hub) · Hydration Wertebereiche :343-348 · Versand :383-393 · Alarme :425 ·
Wetter-Metriken :461-479 · Layout :505-510 · Mounts: `WeatherMetricsTab wiz=` :1008,
`corridorPropsAus` :1026/1029, `alarmePropsAus` :1050, `versandPropsAus` :1073.
Ohne wiz: Orte-Tab (:252-286, `buildHubPutPayload`), Aktiv-Schalter (:638), Banner.
Name/Region/Profil liegen in `routes/compare/[id]/+page.svelte`, nicht in CompareTabs.

## Existing Patterns
- **Wertprops statt `wiz`** (S6c/S6d/S6e, Präzedenz `CompareOutlookLayoutControls` #1720 S1):
  Elternteil bündelt per `xxxPropsAus(zustand)`, Kind kennt keinen Wizard. Kind+Eltern sind
  kleinste sinnvolle Einheit.
- **AST-Wächter** `*_laedt_keine_compare_klebeschicht.test.ts` (vier Stück) — werden fortgeschrieben.
- **Trip-Pendant:** `TripTabs.svelte` reicht `{trip} {onTripUpdate} {saveController}`, Organismen
  speichern Teil-Bodies via `saveController.schedule()`; Netz-Serialisierung `api.ts:184-186` →
  `enqueueTripWrite` (`etagRegistry.ts:151`). Listen-Pause Trip: `PATCH /api/trips/{id}/state`
  (`routes/trips/+page.svelte:210-223`); Compare-`PATCH …/state` kennt nur `archived_at`.

## Dependencies
- Upstream: `api.ts` (ETag/If-Match, `serializedWrite`), `etagRegistry.ts`, Go-PUT
  `/api/compare/presets/{id}` (Voll-Dekodierung; Patch-DTO kam mit #2285), `mergeConfigMap` (eine Ebene tief).
- Downstream: Hub `/compare/[id]`, Liste `/compare`, `/compare/new` (über WMT + Klasse), 29
  `createPutQueue`-Prüfstände, 12 Testdateien mit Typ `CompareWizardState`.

## Existing Specs
- `docs/specs/modules/rework_2276_s1…s6e_*.md` (bes. S6a: Ratsche + AC-2-Neufassung + Anhang
  :334-411 Einstufung; S6b: WMT behält wiz; S6e: Versand-Wertprops).
- `docs/reference/gates_und_ratschen.md:325-370` (Ratsche, Prüfdatum).

## Risks & Considerations
1. **Schreibschlange `hubPutQueue` darf NICHT ersatzlos fallen** (F1): sie hält den Payload-Bau
   im `enqueue()`-Closure; ETag serialisiert nur das Netz. Ohne sie: 200 OK mit veraltetem Body
   (Orte↔Reiter, Toggle↔Reiter, Orte↔Toggle, Orte↔Orte). Bei Verschiebung: 29 Test-Importe
   mitziehen — Planung rät, Schlangen-Umzug und Test-Massenänderung nicht zu vermischen.
2. **Voll-Spread-Payload bleibt** (F4) — kein Minimal-Body.
3. **Hydration + Rollback** (`snapshotForRollback`, Reset-Effekt :712-719, Lazy-Hydrationsflags,
   F005 Hydration aus `currentPreset`) müssen beim Ersatz der Klasseninstanz erhalten bleiben.
4. **WMT-Umbau trifft `/compare/new`**, das in CI keine E2E-Abdeckung hat → Staging-Durchklick
   von `/compare/new` Pflicht, sobald WMT angefasst wird.
5. **AC-2-Spannung:** 14 ursprünglich als HERKUNFT eingestufte Einträge stehen noch in der
   Ratsche — Speicherweg-Prädikate `versandVergleichSpeicherung.ts:221`,
   `wertebereicheVergleichSpeicherung.ts:200`, `weatherMetricsCompareSave.ts:534` (S4 AC-13
   „zweite Barriere", Abbau bräuchte ADR), Guard `VersandTab.svelte:348`, WMT-Ladepfade
   :545/:560/:589/:602, Corridor-Katalog-Guards CE:184/216 + CEM:172/197, maybeSchedule
   CE:285/CEM:252 („fällt frühestens in S6f zur erneuten Prüfung an"). Spec muss je Eintrag
   abbauen oder begründet umklassifizieren.
6. **Ratsche nie nachziehen**, Zeilennummern in `shared/` nicht verschieben (Kommentare nur
   an Ort und Stelle ersetzen). Mit S6f ist der Rückbau der Ratsche vorgesehen.
7. **Listen-Toggle** (`routes/compare/+page.svelte`) nutzt rohes `fetch` ohne If-Match — beim
   Umzug von `buildFreshTogglePutPayload`/`buildToggleActivePutPayload` beide zusammen.
8. LoC: WMT-Umbau + Umzüge sprengen voraussichtlich 250 → `loc_limit_override` früh setzen oder schneiden.

## Nebenbefunde zum Mitbereinigen
- `compareHubWizardBridge.ts:114-115` nennt entferntes `saveComparePreset()` (#1199).
- `flushPendingLayoutSave` (`weatherMetricsCompareSave.ts:231`) ohne Produktiv-Aufrufer (#1199);
  veraltete Kommentare `CompareTabs.svelte:1039`, `compareHubWizardBridge.ts:451`.
- Nicht in CI: compare-hub-versand-inline, compare-hub-save-chip, compare-hub-name-region-profil,
  compare-editor-autosave.

## Analysis

### Type
Feature/Refactor (Rückbau, keine nutzersichtbare Verhaltensänderung)

### 🔴 Schnitt-Entscheid (Tech-Lead, 2026-09-22) — Reihenfolge gegenüber S6a-Tabelle präzisiert
Messung widerlegt die Annahme „Bridge-Rückbau geht erst, wenn kein shared/-Baustein am Wizard hängt":
- `compareHubWizardBridge.ts` importiert `CompareWizardState` **nicht** (nur Kommentar-Treffer :36/:356);
  alle Exporte sind reine Funktionen bzw. mutieren ein strukturelles Ziel.
- Produktive Importeure sind genau drei: `CompareTabs.svelte:81-88`, `routes/compare/+page.svelte:26`,
  `shared/alarmeVergleichSpeicherung.ts:17` (Typ). `/compare/new` importiert die Bridge **nicht**
  (Plan-Agent-Aussage „hydrateWizardStateFromPreset bleibt für /compare/new" ist falsch).
- Am WMT-Umbau hängt nur der Wegfall der **Hub-Klasseninstanz** (Prop `wiz?: CompareWizardState` in
  WMT :169 ist klassentypisiert → Plain-`$state` scheitert an `svelte-check`), **nicht** AC-4.

Daher:
- **S6f (dieser Workflow)** = Bridge-Umzug (AC-4) + toter `setContext('compare-wizard-state')` CompareTabs:330
  + F1-Schlangenentscheid dokumentieren. Berührt **keine** Ratschen-Datei und **nicht** `/compare/new`.
- **S6g (Folge-Workflow)** = WMT auf Wertprops (`wetterMetrikenPropsAus`), Hub-Klasseninstanz
  `new CompareWizardState()` → Plain-`$state`, AC-2-Endbilanz (14 HERKUNFT-Einträge abbauen/umklassifizieren),
  Ratschen-Rückbau. Fachlich zusammengehörig (alles hängt an WMT + Ratsche).
- S6e-Spec `:33` („letzte wiz-Abbau-Scheibe") ist damit überholt; S6f-Spec vermerkt das.

### Affected Files (S6f)
| File | Change | Description |
|---|---|---|
| `compare/compareHubWizardBridge.ts` | DELETE (Umzug + Split) | Klebeschicht entfällt |
| `compare/compareHubPersistenz.ts` (Name in Spec festlegen) | CREATE | `buildHubPutPayload`, `HubEdit`, `snapshotForRollback`, `buildToggleActivePutPayload`, `buildFreshTogglePutPayload`, `hubActivationBanner`, `createPutQueue`, `PutQueue` |
| `compare/compareHubHydration.ts` (oder im selben Modul) | CREATE | `hydrateWizardStateFromPreset`/`HubWizardFields` (entwizardisiert benennen, z. B. `hydrateHubFieldsFromPreset`), `hydrateAlarmFieldsFromPreset` |
| `shared/alarmeVergleichSpeicherung.ts` | MODIFY | `AlarmHydrationTarget` hier definieren (Muster `VersandHydrationTarget` :52), Import dreht sich um → shared/ importiert nichts mehr aus compare/ |
| `compare/CompareTabs.svelte` | MODIFY | Importpfade :81-88; `setContext` :41/:330 entfernen; Kommentar :207 |
| `routes/compare/+page.svelte` | MODIFY | Importpfad :26 |
| 32 Testdateien (~29× `createPutQueue`) | MODIFY | nur Importpfade, mechanisch |
| Kommentar-Treffer (VersandTab:27, versandVergleichSpeicherung:10, alarmeVergleichSpeicherung:9, wertebereicheVergleichSpeicherung:10, weatherMetricsCompareSave:5/12/129/184) | MODIFY | Kommentare **an Ort und Stelle** ersetzen, Zeilenzahl in shared/ NICHT verändern (Ratsche Datei:Zeile) |
| 4 Wächter `*_laedt_keine_compare_klebeschicht.test.ts` | MODIFY | auf neue Module fortschreiben (shared/-Organismen laden keine Hub-Orchestrierung) |
| `compare_hub_wizard_bridge.test.ts` | MODIFY/RENAME | nach Verhalten benennen |

### Scope Assessment
- Produktiv: ~5 Dateien + 1–2 neue Module; fast ausschließlich Umzug (455 Z. verschoben, netto nahe 0)
- Tests: ~36 Dateien, nur Importpfade
- LoC-Delta: **unbelegt** — wie `workflow.py status` einen Split-Umzug zählt, nach `/50` messen; bei >250 `loc_limit_override 500` (Umzug, keine neue Logik)
- Risk Level: **LOW–MEDIUM** (mechanisch, aber Speicherweg-Kernmodul; Schlange/Hydration dürfen sich nicht verändern)

### Technical Approach
1. Erst reiner Umzug (Funktionskörper byte-identisch, nur Modul/Name) + Test-Importpfade, **keine** inhaltliche
   Änderung an Payload-Bau/Schlange im selben Schritt. Kein Re-Export-Shim (würde AC-4 aushebeln).
2. `hubPutQueue` (F1) bleibt unverändert aktiv; Payload-Bau bleibt im `enqueue()`-Closure. Spec zitiert F1 als
   dokumentierten Entscheid („Schlange bleibt; wer sie anfasst, muss Payload-Bau bis Ausführungszeit verzögern").
3. Voll-Spread-Payload (F4) bleibt.
4. AC-4-Messverfahren: wörtliches Suchen nach `compareHubWizardBridge` unter `frontend/src` ⇒ **0 Treffer**
   (Kommentare werden mit umgeschrieben, Datei gelöscht) — strenger und einfacher als ein Kommentarfilter.
5. Zusätzlicher Wächter: kein Modul unter `shared/` importiert aus den neuen Hub-Modulen (Richtung shared ← compare).
6. Nebenbefunde: veralteter Kommentar `saveComparePreset()` (Bridge :114-115) und :451 fallen mit dem Umzug.
   `flushPendingLayoutSave` (WMT-Save :231) gehört zu S6g.

### Dependencies
- Upstream unverändert: `api.ts`, `etagRegistry.ts`, Go-PUT `/api/compare/presets/{id}`.
- Downstream: Hub `/compare/[id]` (CompareTabs), Liste `/compare` (Toggle), Alarme-Speicherweg (Typ).
- S6g hängt an S6f nur weich (Import-/Kommentarlage), nicht umgekehrt.

### Randbedingungen für S6g (festgehalten, damit nichts verloren geht)
- Ratsche: WMT braucht eine eigene Vertragsausnahme im Stil der S6c/S6d/S6e-Blöcke
  (`context_herkunft_zweige_eingefroren.test.ts` Kopf :22-50): RED setzt nur die Vertragserweiterung,
  GREEN trägt gemessene neue Zeilennummern mit `BLEIBT_MIT_INHALT`-Fesselung nach — das ist **kein** Nachziehen.
  Betroffen: WMT :545/:560/:589/:602/:1323, `weatherMetricsCompareSave.ts:534`, `weatherMetricsTabSections.ts:72/73`.
- WMT schreibt 10 Felder direkt (activeMetricKeys, channelActiveMetricKeys, outlookMetricKeys/-Formats/-Enabled,
  officialAlertsEnabled, dayWindowStart/EndHour, hourlyMetricKeys/-Enabled) ⇒ 10 `on*Change` + Rollback-Senke,
  Proxy nach `versandZustandsBruecke` (`versandVergleichSpeicherung.ts:331-338`).
- Trip-Mount von WMT reicht kein `wiz` ⇒ neue Props optional, Trip-Verhalten unverändert.
- Verdrahtungs-Lücke: Unit-Tests von `weatherMetricsCompareSave` bekommen das Zustandsobjekt direkt und bleiben
  grün bei falscher Proxy-Verdrahtung in WMT oder falschem Spread in `CompareNewEditor` — S6g braucht einen
  Test am Mount; `/compare/new` hat keine CI-E2E ⇒ Staging-Durchklick Pflicht.
- Ratschen-Prüfdatum ist 2026-12-19.

### Open Questions
- [ ] Modulnamen/Aufteilung (ein oder zwei Zielmodule) — entscheidet die Spec (Tech-Lead, keine PO-Frage).
- [ ] LoC-Zählung des Umzugs — nach `/50` per `workflow.py status` prüfen.
- [ ] S6g als eigener Workflow nach S6f-Deploy anlegen (Issue #2276 bleibt offen bis S6g live).

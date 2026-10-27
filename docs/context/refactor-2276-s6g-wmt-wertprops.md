# Context: refactor-2276-s6g-wmt-wertprops

Issue #2276 (Epic #2345), letzte Scheibe **S6g**. Basis: `84b50d72` (S6f live).
Vorgänger-Analyse mit Schnitt-Entscheid: `docs/context/refactor-2276-s6f-bridge-rueckbau.md` § Analysis
(„Randbedingungen für S6g").

## Request Summary
Der Wetter-Metriken-Reiter (`WeatherMetricsTab`, WMT) bekommt im Vergleichskontext Wertprops statt der
Klasseninstanz `wiz` (Muster S6c/S6d/S6e). Danach Hub-Klasseninstanz `new CompareWizardState()` in
`CompareTabs` → Plain-`$state`, AC-2-Endbilanz (jede verbleibende `context ===`-Verzweigung in `shared/`
mit fachlichem Grund) und Rückbau/Abschluss der HERKUNFT-Ratsche.

Alle Pfade relativ zu `frontend/src/lib/components/`.

## Related Files
| File | Relevance |
|---|---|
| `shared/WeatherMetricsTab.svelte` (2123 Z.) | Typ-Import `CompareWizardState` :92 (**einziger** Import aus `shared/`), Prop `wiz?` :169, Destrukturierung :178. Lese-/Schreibzugriffe :1096–1520 (s. u.). `context ===` :545/:560/:589/:602/:1323 |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | Snapshot/Payload/Rollback/Fabrik. :534 Aktiv-Prädikat `p.context === 'vergleich' && !!p.wiz && …` (Param `wiz` :530). `flushPendingLayoutSave` :231 + `flushPendingWeatherMetricsSave` :138 nur Test-Aufrufer. Kommentar :291ff sagt „9 Felder", gelistet sind 10 |
| `shared/weather-metrics-tab/weatherMetricsTabSections.ts:72/73` | fachliche Abschnittswahl route/vergleich — bleibt |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | Ratsche, `EINGEFROREN_SOLL_ANZAHL = 47` (:228), Liste :157-224, Ausnahme-Blöcke S6c :22-25/:107-118, S6d :27-31/:120-137, S6e :33-48/:138-151, Regel :153-155, `BLEIBT_MIT_INHALT` :242-402 + Prüfung :490-525 (`FENSTER` 8, :405), Zählbefehl :91-93. Prüfdatum 2026-12-19 |
| `compare/CompareTabs.svelte` (1459 Z.) | `new CompareWizardState()` :328, Typ-Import :79, WMT-Mount :1004-1011 in `{#if wetterMetrikenLayoutHydrationBereit}` (:996) mit `wiz={wizardState} preset saveController enqueueHubWrite onCompareUpdate`. Hydration :459-477/:502-508. Bündel-Spreads :1024/1027/1048/1071. **svelte-check-Fehler:** `localSchedule` benutzt :162, deklariert :630 |
| `compare/CompareNewEditor.svelte` | WMT-Mounts :382/:483 (`context="vergleich" {wiz}`, ohne preset/saveController). `getContext` :67, Bündel-Spreads :391/400/408/487/491/494 |
| `routes/compare/new/+page.svelte` | instanziiert `CompareWizardState` :19 und reicht per Context durch |
| `compare/compareWizardState.svelte.ts` (191 Z.) | Klasse, ~45 `$state`-Felder, `saveNewPreset()` :125. Typ-Importe produktiv: CompareTabs :79, WMT :92, Step2Orte :13, CompareNewEditor :28, routes/compare/new :15 |
| `compare/versandPropsAus.ts` / `corridorPropsAus.ts` / `alarmePropsAus.ts` | Präzedenz-Bündel (strukturelle Quellen-Schnittstelle, kein Browser-Import, Spread im Markup) |
| `shared/versandVergleichSpeicherung.ts:331-342` | `versandZustandsBruecke(werte, setzen?)` — Proxy-Vorbild für Rollback-Senke |
| `compare/CompareOutlookLayoutControls.svelte` :58/:88/:179/:192/:204 | tote optionale Prop `onOutlookCommit` (WMT übergibt sie nicht) — Mitbereinigung |
| `trip-detail/TripTabs.svelte:224`, `edit/TripEditView.svelte:201`, `trip-new/TripNewEditor.svelte:881/:1113` | Trip-Mounts ohne `wiz` — müssen unverändert bleiben |

### WMT: `wiz`-Zugriffe (Stand 84b50d72)
- Lesen: :1096/:1184/:1247 (`if (!wiz) return`), :1097, :1098, :1108, :1122, :1168, :1185, :1187, :1261 (Prädikat), :1264 (`wiz!` in Fabrik), :1279 (`wetterMetrikenSnapshotAus(wiz!)`), :1445/:1466/:1495 (`&& wiz`-Guards), :1448/:1449, :1478, :1480, :1504/:1508/:1510, :1520.
- Schreiben: :1098 activeMetricKeys, :1116/:1187 channelActiveMetricKeys, :1226 outlookMetricKeys, :1234 outlookMetricFormats, :1238 outlookEnabled, :1248 officialAlertsEnabled, :1450/:1451 dayWindowStart/EndHour, :1479 hourlyMetricKeys, :1481 hourlyEnabled.
- **Genau 10 Felder**, lesend und schreibend = Snapshot-Menge von `weatherMetricsCompareSave.ts:291-302`.
- `createMode` (23 Treffer) ist reine Trip-Anlegelogik, im Vergleichszweig ungenutzt — nicht Gegenstand.

## Existing Patterns
- **Bündel-Funktion je Organismus** (`xPropsAus(quelle)`), Aufruf ausschließlich als `{...xPropsAus(wiz)}` im Markup, an **allen** Vergleichs-Mounts (Hub + beide Anlege-Mounts). „Wertprop, sonst `wiz`" als Doppelquelle ist verboten (S6e Known Limitation).
- **Feldklassen** (S6e DE-2): Snapshot-Felder über Brücke, Eigenständige Felder außerhalb, Legacy über Rollback-Senke.
- **Proxy-Brücke** `werte`/`setzen` (S6e DE-3) für Rollback, platziert unterhalb eingefrorener Zeilen.
- **Umbenennung** `wiz` → `zustand` im Aktiv-Prädikat an gleicher Zeile (S6e DE-4) — hier `weatherMetricsCompareSave.ts:530/534`.
- **Ratschen-Ausnahme** (S6e DE-5): RED setzt nur die Vertragserweiterung, GREEN trägt gemessene neue Zeilennummern mit `BLEIBT_MIT_INHALT`-Fesselung nach — kein „Nachziehen".
- **AST-Wächter** (S6e AC-1/AC-3): kein `wiz`/`CompareWizardState` im Baustein, Bündel an allen Mounts; Wirkort-Guard per `effekteVon()`/`umgebungFuer()` (AC-2).

## Dependencies
- Upstream unverändert: `api.ts` (ETag bei Abfeuern), `hubPutQueue`/`createPutQueue` (**bleibt**, F1), Voll-Spread-Payload (F4), Go-PUT `/api/compare/presets/{id}`.
- Downstream: Hub `/compare/[id]`, Anlege-Seite `/compare/new` (CompareNewEditor), Trip-Mounts (unverändert), Ratsche.

## Existing Specs
- `docs/specs/modules/rework_2276_s6b_wetter_metriken.md` — :48-51 WMT-`wiz` vertagt; :52-73 welche `context ===` bleiben (545/560/589/602 Zwillinge, :534 zweite Barriere via S4 AC-13 — Entfernung braucht ADR; 1323 + Sections fachlich); :74 `/compare/new`-Speicherweg nicht anfassen (#2277); :159-171 Mount-AST-Wächter (`catalog={compareCatalog}`, genau eine Einbettung).
- `docs/specs/modules/rework_2276_s6e_versand.md` — DE-1…DE-5, AC-1/2/3/5/7/8 als Vorlage.
- `docs/specs/modules/rework_2276_s6f_bridge_umzug.md`, `rework_2276_s6a_totcode_und_ratsche.md` (Ratsche, AC-2-Neufassung „keine HERKUNFT-Zweige").

## Tests
- Unit mit `wiz` an WMT: `shared/__tests__/` compare_stundenverlauf_wertprops, metricKuerzelLegende, weatherMetricsTabDayWindowSave, weatherMetricsTabSharing, versand_speicherung_nur_im_vergleich_hub, versand_tab_meldet_aenderungen_reaktiv; `weather-metrics-tab/__tests__/` wetter_metriken_laedt_keine_compare_klebeschicht, wetter_metriken_speicherung_nur_im_vergleich_hub, wetter_metriken_vergleich_speichert_einmal (+ übrige `wetter_metriken_*`), compare_hourly_layout_controls_structure, weather_metrics_tab_compare_catalog_fetch.
- E2E in CI (`.github/ci_e2e_specs.txt`): compare-wetter-metriken-speichert-selbst, compare-stundenverlauf-wertprops, compare-editor-slice3.
- E2E **nicht** in CI, aber WMT auf `/compare/new`: layout-tab-vergleich.spec.ts:33/:120, compare-hourly-metric-order.spec.ts:331-352.

## Risks & Considerations
- **Verdrahtungs-Lücke:** Unit-Tests von `weatherMetricsCompareSave` bekommen das Zustandsobjekt direkt ⇒ grün bei falscher Proxy-Verdrahtung in WMT oder falschem Spread in CompareNewEditor. Test am Mount + Staging-Durchklick `/compare/new` Pflicht (SSR-Harness führt `$effect` nie aus).
- **Ratsche:** WMT hat heute keine Ausnahme und keine `BLEIBT_MIT_INHALT`-Fesselung; jede neue Prop-Zeile oberhalb :545 verschiebt 5 Einträge ⇒ neuer S6g-Ausnahmeblock nötig. Liste nie bei Rot „nachziehen".
- **Hub-Klasse → Plain-`$state`:** `routes/compare/new` + CompareNewEditor + Step2Orte nutzen die Klasse (inkl. `saveNewPreset()`) weiter — Anlege-Seite ist #2277, nicht S6g. Abgrenzen: nur die **Hub**-Instanz fällt.
- **:534 zweite Barriere** darf nur umbenannt, nicht entfernt werden (sonst ADR).
- **AC-2-Endbilanz:** 47 Einträge ⇒ Liste mit fachlichem Grund je verbleibender Verzweigung (AC-2 Neufassung aus S6a). Unklar, ob Ratsche am Ende bleibt (als Wächter mit festem Soll) oder zurückgebaut wird — entscheidet `/20-analyse`.
- **Datenerhalt:** Read-Modify-Write/Voll-Spread bleibt; Schlange bleibt.
- **Mitbereinigung:** `localSchedule`-svelte-check-Fehler (CompareTabs :162/:630), tote `onOutlookCommit`-Prop, `flushPendingLayoutSave`/`flushPendingWeatherMetricsSave` ohne Produktiv-Aufrufer (#1199), Kommentar „9 Felder".
- **LoC:** WMT-Umbau + Hub-Umstellung + Tests wahrscheinlich > 250 ⇒ nach Messung `loc_limit_override 500`.

## Analysis

### Type
Feature (Refactoring, Scheibe von Epic #2345 / Issue #2276) — kein nutzersichtbares Verhalten ändert sich.

### Ticket-Schließkriterien (gegen `gh issue view 2276 --json body` geprüft)
Ticket-ACs: AC-1 (Alarme persistiert selbst), **AC-2** (nur fachliche `context ===` in `shared/`, Liste mit Grund je Eintrag; Neufassung S6a-Spec :90-98: keine HERKUNFT-Verzweigung, Rest FACHLICH/DARSTELLEND begründet), AC-3 (zwei Reiter, keine verlorene Änderung), AC-4 (kein Importeur `compareHubWizardBridge`, erfüllt seit S6f).
**Die Hub-Klasseninstanz `new CompareWizardState()` → Plain-`$state` ist KEIN Ticket-AC** (S6f-Spec :66-69 hielt die Instanz nur *für* WMT). Ratschen-Rückbau ist ebenfalls kein Ticket-AC.

### Schnitt-Entscheid (Tech Lead) — Re-Cut gegenüber Issue-Kommentar „S6g = WMT, Hub-Klasse, AC-2"
Befund: Von den **14 noch als HERKUNFT eingestuften Ratschen-Einträgen** (Liste s. u.) liegen nur 5 in WMT/WMT-Save; 9 liegen in Corridor/Versand/Wertebereiche. „AC-2 hängt am WMT-Umbau" stimmt nur teilweise. WMT-Umbau allein ist geschätzt produktiv ~+220/−70 plus Tests ⇒ S6g + AC-2-Endbilanz + Hub-Klasse sprengt auch 500 LoC und mischt drei Risiko-Profile.

- **S6g (dieser Workflow):** WMT auf Wertprops (`wetterMetrikenPropsAus`), `wiz`→`zustand` im Aktiv-Prädikat `weatherMetricsCompareSave.ts:530/534` (nur Umbenennung, Barriere bleibt), WMT-Ratschen-Ausnahmeblock (S6e-Muster DE-5), Mitbereinigung `localSchedule` (CompareTabs) + Kommentar „9 Felder"→10.
- **S6h (Folge-Workflow, schließt #2276):** AC-2-Endbilanz aller 14 HERKUNFT-Einträge (je Eintrag REMOVE / RECLASSIFY mit Grund / KEEP per ADR bzw. AC-Abweichung), Entscheid Ratschen-Endzustand (Rückbau ODER Umbau auf reinen Inhaltswächter ohne Zeilennummern — Zeilennummern-Gate dauerhaft wäre Lärm für jede künftige `shared/`-Session), optional Hub-Klasse → Plain-`$state` (nach S6g reiner Feldcontainer, Nutzen gering, kein AC).
- **Nicht in #2276:** tote Prop `onOutlookCommit` (`CompareOutlookLayoutControls.svelte`, hängt an fremder AST-Allowlist `outlook_restore_schreibt_nur_outlook_metrics.test.ts:201`) und `flushPendingLayoutSave`/`flushPendingWeatherMetricsSave` (0 Produktiv-, ≥6 Test-Aufrufer) → Checkbox in #1199.
- Beim S6g-Abschluss-Kommentar im Issue den Re-Cut öffentlich nachziehen („offen: S6h").

### Die 14 HERKUNFT-Einträge (Übergabe an S6h; S6g fasst davon nur :534 per Umbenennung an)
| Eintrag | Art | Vorläufige Einschätzung |
|---|---|---|
| `versandVergleichSpeicherung.ts:221`, `wertebereicheVergleichSpeicherung.ts:200`, `weatherMetricsCompareSave.ts:534` | Speicherweg-Prädikat (Vergleich vs. `saveController.schedule`) | Laut AC-2-Wortlaut **definitionsgemäß HERKUNFT**, nicht umklassifizierbar. :534 ist zugleich freigegebene S4 AC-13 „zweite Barriere" (Test `wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts:74-82`). **Konflikt zweier freigegebener ACs** ⇒ S6h braucht ADR (alle drei Barrieren einheitlich) oder explizite AC-2-Abweichung zur PO-Freigabe in `/30`. |
| `VersandTab.svelte:348` | Guard | S6h prüfen |
| WMT `:545`/`:560` (trip-seitig) + `:589`/`:602` (vergleich-seitig) | Ladepfad (Katalog/Symbole, `catalog` aus zwei Quellen) | S6b-Spec :52-60: Zwillinge, fallen nur gemeinsam; Abbau-Route = Elternteil reicht Katalog in beiden Kontexten (fasst Trip-Mounts an) ⇒ S6h, nicht S6g |
| Corridor-Katalog-Guards CE:184/216, CEM:172/197 | Guard | S6h |
| `maybeSchedule` CE:285 / CEM:252 | Speicherweg | wie Prädikate: HERKUNFT per Definition ⇒ S6h |
(Zeilennummern Stand S6f-Kontext; S6h misst neu.)
Fachlich/bleibend unstrittig: WMT `:1323` (Markup-Gabelung), `weatherMetricsTabSections.ts:72/73`.

### Affected Files (S6g)
Pfade relativ zu `frontend/src/lib/components/`.
| File | Change | Description |
|---|---|---|
| `compare/wetterMetrikenPropsAus.ts` | CREATE | Bündel: 10 Snapshot-Felder + `on*Change`-Rückrufe + Rollback-Senke; strukturelle Quellen-Schnittstelle (kein `CompareWizardState`-Import), Muster `versandPropsAus.ts` |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | `wiz`→`zustand` an :530/:534 (gleiche Zeile), Proxy-Brücke `wetterMetrikenZustandsBruecke` **unterhalb** :534 (Muster `versandZustandsBruecke`), Kommentar :291 „9"→„10 Felder" |
| `shared/WeatherMetricsTab.svelte` | MODIFY | Typ-Import :92 + Prop `wiz` :169/:178 raus; 10 optionale Wertprops + Rückrufe; alle Lese-/Schreibzugriffe :1096–:1520 umverdrahten; Selbst-Speicher-Effekt :1261/:1264/:1279 über Brücke. **Neue Prop-Zeilen liegen oberhalb :545 ⇒ verschieben 5 eingefrorene Einträge** |
| `compare/CompareTabs.svelte` | MODIFY | WMT-Mount :1004-1011 `wiz={wizardState}` → `{...wetterMetrikenPropsAus(wizardState)}`; `localSchedule`-Deklaration vor Nutzung (:162/:630) |
| `compare-new/CompareNewEditor.svelte` | MODIFY | beide WMT-Mounts :382/:483 auf Spread |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | S6g-Ausnahmeblock für WMT (+ ggf. `weatherMetricsCompareSave.ts`) mit `BLEIBT_MIT_INHALT`-Fesselung; RED nur Vertragserweiterung, GREEN trägt gemessene Zeilen nach. Soll bleibt 47 (S6g entfernt keinen Eintrag) |
| `shared/__tests__/weatherMetricsTabSharing.test.ts` | MODIFY | :69 prüft heute explizit `wiz?: CompareWizardState` an WMT — Saat-Anpassung im selben Commit |
| Tests mit `wiz` an WMT (Liste in `## Tests` oben) | MODIFY | Mounts auf Wertprops/Bündel umstellen |
| `compare/__tests__/compare_wetter_metriken_wertprops.test.ts` (Name nach Verhalten, in Spec fixieren) | CREATE | AST-Wächter: kein `wiz`/`CompareWizardState` in WMT; Bündel-Spread an **allen drei** Vergleichs-Mounts; Wirkort-Guard per `effekteVon()`/`umgebungFuer()` |
| Trip-Mounts (`TripTabs:224`, `TripEditView:201`, `TripNewEditor:881/:1113`) | — | unverändert; neue Props optional |

### Scope Assessment
- Produktiv: 5 Dateien (1 neu). Tests: ~12–15 Dateien.
- LoC geschätzt produktiv +220/−70 ⇒ `loc_limit_override 500` nach Messung in `/50`.
- Risk Level: **MEDIUM** — WMT ist der größte Organismus (2123 Z.), Zugriffe markup-verzahnt; Speicherweg-Kern.

### Technical Approach
1. Bündel + Brücke zuerst (S6e DE-1…DE-4 übertragen). Alle 10 Felder sind Snapshot-Felder (Klasse A, S6e DE-2) — keine Eigenständigen/Legacy-Felder erwartet; Spec bestätigt per Feldtabelle.
2. **Keine Doppelquelle** „Wertprop, sonst `wiz`" (S6e Known Limitation). An allen drei Vergleichs-Mounts Spread.
3. `toggleCompareMetric` schreibt `activeMetricKeys` **und** `channelActiveMetricKeys` gemeinsam ⇒ Rückrufe nicht naiv 1:1; Spec legt fest, ob zwei Rückrufe nacheinander oder ein kombinierter Rückruf (Snapshot/Rollback muss beide Felder atomar sehen).
4. Hub-Hydration (`hydrateWetterMetrikenTab` :459-477, `hydrateLayoutTab` :502-508) schreibt dieselben 10 Felder in `wizardState`, das Bündel liest daraus ⇒ beide müssen auf **dasselbe** Objekt zeigen (Reaktivität über das Klassen-`$state` bleibt, Hub-Instanz bleibt in S6g).
5. :534 nur umbenennen, Barriere bleibt (S4 AC-13).
6. Ratsche: Ausnahmeblock im S6c/S6d/S6e-Stil, nie bei Rot nachziehen.
7. Nachweis Verdrahtung: Mount-Test (SSR-Harness führt `$effect` nicht aus ⇒ reicht nicht allein) + CI-E2E `compare-wetter-metriken-speichert-selbst`, `compare-stundenverlauf-wertprops`, `compare-editor-slice3` + **Staging-Durchklick `/compare/new`** (keine CI-E2E dort).

### Dependencies
- Upstream unverändert: `api.ts`, `hubPutQueue`/`createPutQueue` (F1), Voll-Spread-Payload (F4), Go-PUT `/api/compare/presets/{id}`.
- `CompareWizardState` bleibt bestehen (Hub-Instanz + `/compare/new` via `routes/compare/new/+page.svelte`, `CompareNewEditor`, `Step2Orte`; #2277).
- S6h hängt an S6g (WMT-Zeilen gemessen), nicht umgekehrt.

### Open Questions
- [ ] (S6h, nicht S6g) Konflikt AC-2 ↔ S4 AC-13 bei den drei Speicherweg-Barrieren: Empfehlung ADR „eine Barriere je Speicherweg, gebunden an Wertprop-Präsenz statt `context`" ODER AC-2-Abweichung mit Begründung — Entscheid in S6h-Spec zur PO-Freigabe.
- [ ] (Spec S6g) Rückruf-Form für die gekoppelte Schreibung `activeMetricKeys`+`channelActiveMetricKeys` — Tech-Lead-Entscheid in `/30`.

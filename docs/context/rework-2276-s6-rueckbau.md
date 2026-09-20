# Context: #2276 S6 — Rückbau und Bilanz

> Erstellt 2026-09-20, Phase 1 des Workflows `rework-2276-s6-rueckbau`.
> Basis: `73f504c9` (= `origin/main` nach PR #2379). Vorgänger-Kontext: `docs/context/rework-2276-compare-speicherweg.md`.

## Request Summary

Letzte Scheibe von #2276 (Epic #2345, Etappe P1). Der Auftrag aus dem Scheiben-Plan
(`rework-2276-compare-speicherweg.md`, E4): **Klebeschicht im Hub entfernen, Schreibschlange
abbauen (E2), Zweig-Bilanz für die Issue-ACs AC-2 und AC-4 liefern.**

## Ausgangslage nach S1–S5

| Scheibe | Stand |
|---|---|
| S1 Netz und Fundament | live `58eb84c4` |
| S2 Alarme | live `37ff58da` |
| S3 Wertebereiche | live `70078059` |
| S4 Wetter-Metriken + Layout | live `3c14e6e7` |
| S5 Versand | live `73f504c9` |

Alle fünf ursprünglich in S1 umwickelten Commit-Handler sind weg; jeder der vier Reiter
persistiert über den geteilten `saveController`. **Nicht** umgestellt wurde, woher die Reiter
ihren Bearbeitungsstand **lesen** — das ist weiterhin der Wizard-Zustand.

Abhängigkeit geklärt: **#2285 ist seit 18.09. live** (`applyComparePresetPatch`, EIN Merge-Kern
für beide Vergleichs-Schreibwege). Ob damit die heute verlangte Voll-Spread-Nutzlast entfallen
darf, ist offen (s. Frage F4).

## Befund 1 — Zweig-Inventar (Grundlage für AC-2)

Vollständige Auszählung aller produktiven `context ===` / `context !==`-Stellen unter
`frontend/src/lib/components/shared/` (Tests ausgeschlossen): **69 Fundstellen / 64
Entscheidungspunkte**.

| Kategorie | Anzahl | Bedeutung |
|---|---|---|
| **HERKUNFT** | **45** | unterscheidet NUR, woher gelesen / wohin geschrieben wird (`wiz`/`ws` vs. `trip`-Prop, Vergleichs-Speicherweg vs. `saveController.schedule`) |
| **FACHLICH** | **12** | echter Sachunterschied |
| **DARSTELLUNG** | **11** | nur Beschriftung/Sichtbarkeit, kein Datenweg-Unterschied |
| tote Bedingung | 1 | `WeatherMetricsTab.svelte:577` — für beide Werte des Union-Typs wahr, ersatzlos streichbar |

Rechenweg (tragend für die AC-2-Bilanz, damit er nicht neu hergeleitet werden muss):
45 + 12 + 11 + 1 = **69 Fundstellen** (Zeilen). Daraus **64 Entscheidungspunkte**, weil drei
`{#if}/{:else if}`-Ketten je eine Entscheidung sind: `VersandTab:294`/`:330` (2 Zeilen → 1),
`CorridorEditor:302`/`:315`/`:318` (3 → 1), `CorridorEditorMobile:297`/`:310`/`:313` (3 → 1).

Die zwölf fachlichen Zweige: Beispielwarnung mit Ort- statt Etappen-Subjekt (`AlarmeTab:482`) ·
Radar-Abschnitt nur im Vergleich (`alarmeTabSections.ts:27`) · nicht-alarmfähige Größen, im Trip
strukturell leer weil es dort keine Metrik-Auswahl gibt (`AlarmeTab:199`, #1435 AC-7) · die
beiden Versand-Markup-Bäume mit Premium-SMS/Mehrtages-Trend/Laufzeit (`VersandTab:294`/`:330`,
Begründung im Detail in `rework_2276_s5_versand.md` Punkt 4) · Mehrtages-Trend-Karte
(`VTSchedulePlan:55`) · Metrik-Markup-Baum (`WeatherMetricsTab:1323`) · SMS-Schwellen/Report-Config
nur im Trip und Stundenverlauf nur im Vergleich (`weatherMetricsTabSections.ts:72/73`) ·
unterschiedliche **persistierte** Startwerte neuer Zeilen (`CorridorEditor:268`,
`CorridorEditorMobile:234`) · Markieren-Schalter bei Tages-Summen nur im Trip gesperrt
(`corridorEditorState.ts:297`).

**Konsequenz für die AC-Formulierung:** Die Ticket-Fassung von AC-2 („es verbleiben nur
fachliche Verzweigungen") ist so **nicht erfüllbar** — elf Zweige sind reine Beschriftungs-/
Sichtbarkeitsunterschiede ohne Datenweg und fallen bei diesem Umbau nicht weg. Die prüfbare
Zusicherung muss lauten: **keine HERKUNFT-Zweige mehr**, Darstellung und Fachlogik bleiben,
je mit Begründung in der Liste.

**Konzentration:** 28 der 69 Fundstellen (41 %) stammen aus **einer** gespiegelten Logik —
`CorridorEditor.svelte` und `CorridorEditorMobile.svelte` sind über alle 14 Stellen paarweise
identisch verzweigt. Beide müssen zwingend zeitgleich fallen (Doppel-Mount Desktop/Mobil).

Nicht im Grep-Raster, aber fachlich verzweigend: `versand-tab/VTAlertSample.svelte:44-46`
(Record-Lookups `SAMPLES[context]` ohne Vergleichsoperator).

## Befund 2 — Landkarte der Klebeschicht

| Datei | Zeilen | Produktive Konsumenten |
|---|---|---|
| `compare/compareHubWizardBridge.ts` | 455 | **9 von 12 Exporten ausschließlich `CompareTabs.svelte`**; `buildFreshTogglePutPayload` nur `routes/compare/+page.svelte:136`; `AlarmHydrationTarget` (Typ) nur `shared/alarmeVergleichSpeicherung.ts` |
| `compare/compareEditorSave.ts` | 460 | `buildComparePresetSavePayload` von 6 Modulen — **alle Hub-Pfad**; `buildNewComparePresetPayload` nur vom Anlege-Pfad |
| `compare/compareWizardState.svelte.ts` | 246 | 2 Instanziierungen: `CompareTabs.svelte:325` (Hub) und `routes/compare/new/+page.svelte:19` (Anlege) |
| `compare/compareEditorLoad.ts` | 46 | `rehydrateActiveMetrics` von Bridge + `weatherMetricsCompareSave.ts` |
| `compare/CompareTabs.svelte` | 1457 | Hub |

**Der Anlege-Pfad hängt NICHT am Hub-Speicherweg.** `CompareNewEditor` speichert ausschließlich
über `buildNewComparePresetPayload` (EIN POST, dann Redirect) und übergibt den geteilten
Organismen **weder `preset` noch `saveController`** — deren Selbst-Speicher-Zweige sind dort
inaktiv. Damit ist `buildComparePresetSavePayload` faktisch Hub-Infrastruktur.

**`compare/steps/Step2Orte.svelte` ist aus dem Hub nicht erreichbar** — einziger Importeur ist
`CompareNewEditor.svelte:39`, einzige Route `/compare/new`. Fällt aus dem Umfang von S6.

## Befund 3 — Der Wizard ist ein reiterübergreifender Bus (zentrale Blockade)

Drei Felder werden von **mehreren** Reitern zugleich gelesen und geschrieben:

| Feld | schreibt | liest |
|---|---|---|
| `activeMetricKeys` | WeatherMetricsTab, CorridorEditor(+Mobile) | AlarmeTab, WeatherMetricsTab, CorridorEditor(+Mobile) |
| `metricAlertLevels` | CorridorEditor(+Mobile), AlarmeTab | AlarmeTab, CorridorEditor(+Mobile) |
| `corridors` | CorridorEditor(+Mobile) | CorridorEditor(+Mobile), Re-Hydration in der Bridge |

`preset` ist dagegen eine **pro-Reiter eingefrorene Momentaufnahme** (`preset: () => preset!`).
Der diff-basierte Rollback aller vier Speicher-Module ist auf die **lebende** Teilung
ausdrücklich angewiesen: zurückgesetzt wird nur, wenn der Wizard noch exakt den Wert trägt, den
der gescheiterte Vorgang gesendet hat — ein zwischenzeitlicher Nachbar-Edit überlebt. Eine
Einzel-Umstellung eines Reiters kappt diese Verbindung, **ohne dass ein Test der umgestellten
Datei das bemerkt**.

**Zweite Blockade:** Die Anlege-Seite mountet dieselben sechs Bausteine mit `wiz`, aber **ohne
Preset** — die Kennung entsteht erst beim Speichern. Solange `/compare/new` so gebaut ist, kann
`wiz` nicht ersatzlos aus `shared/` verschwinden. Vier Auswege, keiner davon heute entschieden:

- **(a) Doppelquelle** „`preset` wenn vorhanden, sonst `wiz`" — genau das Anti-Muster, das S6
  beseitigen soll, nur unter neuem Namen. Sollte ausscheiden.
- **(b) Preset-Entwurf:** ComparePreset-förmiges `$state` ohne Kennung in `CompareNewEditor`;
  `shared/` liest dann nur noch aus `preset`. Berührt die Anlege-Seite.
- **(c) Wertprops statt Zustandsobjekt** — der aussichtsreichste Weg, **weil die Vorlage schon im
  selben Elternteil steht:** `shared/CompareOutlookLayoutControls.svelte` nimmt seit #1720 S1
  **kein `wiz`**, sondern reine Wertprops + Änderungs-Rückrufe und wird von
  `WeatherMetricsTab:1496-1502` genau so bedient. Dieser Weg braucht **weder Preset noch
  Kennung**: die Anlege-Seite speist dieselben Wertprops auf ihrer Ebene aus `wiz`, während
  `shared/` den Wizard nicht mehr kennt. Er löst damit die HERKUNFT-Zweige auf, **ohne** den
  Speicherweg von `/compare/new` anzufassen — greift also #2277 nicht vor.
  **Probe vor Verallgemeinerung:** `CompareHourlyLayoutControls` (der billigste der sechs, 2
  Felder, 3 Schreibstellen, struktureller Zwilling der Vorlage) zuerst umstellen. Verschwindet
  dort die `wiz`-Abhängigkeit verhaltensneutral, skaliert das Muster; geht es nicht, reduziert
  sich F2 tatsächlich auf (b) oder (d).
- **(d) Verschiebung:** die 45 HERKUNFT-Zweige fallen erst mit #2277.

Einstiegswege heute: `AlarmeTab`/`VersandTab`/`WeatherMetricsTab`/`CompareHourlyLayoutControls`
per Prop `wiz`; **`CorridorEditor` + `CorridorEditorMobile` per `getContext`** (unsichtbar in der
Aufrufer-Signatur, gesetzt an zwei Orten: `CompareTabs.svelte:326`, `routes/compare/new/+page.svelte:20`).

### Felder ohne Preset-Pendant (die teuren Stellen)

| Feld | Lage |
|---|---|
| `sendEmail` | **kein `send_email` auf `ComparePreset`**; Hydration setzt hart `true`. In `VersandTab` 2× gelesen. Braucht Backend-Feld oder bewusst fixierte Ableitung. |
| `isEditMode` | UI-Zustand, steuert die Profil-Vorbefüllung in beiden Corridor-Editoren. Im Hub strukturell tot, auf der Anlege-Seite nötig. Braucht Ersatz-Prop. |
| `metricsManuallyEdited`, `saveStatus`, `saveError` | UI-Zustand, gehört nicht ins Preset (`saveStatus`/`saveError` gehören in den `saveController`). |

Alle übrigen Wizard-Felder haben ein Pendant — 9 davon nur untypisiert in
`display_config: Record<string, unknown>` (Cast + Normalisierung + Default je Zugriff), vier
davon mit der Dreiwertigkeit `null` ≠ `[]` ≠ Werte (#1366/#1191). Die Abbildungstabellen
existieren bereits in den vier `*VergleichSpeicherung`-Modulen und in der Bridge — die
Umstellung muss sie nicht erfinden, nur umdrehen (Preset → Anzeige).

Sonderfall `schedule`: Wizard `daily_morning|daily_evening|weekly` vs. Preset
`daily|weekly|manual` — die Abbildung in `compareEditorSave.ts:368-372` ist einseitig, kein
verlustfreier Rückweg. Keiner der sechs Bausteine liest `schedule`; relevant nur, falls die
Umstellung bis zur Zeitplan-Fläche reicht.

## Befund 4 — Schreibschlange (E2): Messstand

`hubPutQueue = createPutQueue()` (`CompareTabs.svelte:204`) serialisiert heute alle Hub-PUTs.
Gemessen am aktuellen Stand:

- **Reiterwechsel wartet ab:** `handleValueChange` (`CompareTabs.svelte:148`) ruft
  `await sichereSelbstSpeichererVorReiterwechsel(...)` → `await saveController.flush()` **vor**
  dem Wechsel (`wertebereicheVergleichSpeicherung.ts:219-227`).
- **Pausieren/Aktivieren wartet ab:** `handleToggleActive` (`:641`) ruft bedingungslos
  `await saveController?.flush()` vor dem eigenen PUT.
- **Orte-Pfad wartet NICHT ab:** `persistPickedIds` (`:248`) speichert ohne vorherigen Flush.

🔴 **Nicht gemessen, nur gefolgert — nicht als Beweis zitieren:** die naheliegende Entlastung
„der Orte-Pfad ist nur vom Orte-Reiter aus erreichbar, und der Wechsel dorthin flusht" ist
**nicht belegt**. Der Flush-Guard kehrt früh zurück, wenn der **verlassene** Reiter nicht in
`SELBST_SPEICHERNDE_VERGLEICH_REITER` steht — das Verlassen des Übersicht-Reiters flusht also
nichts, und dass zu diesem Zeitpunkt keine ausstehende Speicherung existieren kann, ist offen.
Gehört zu F1.

⇒ Die ursprüngliche F002-Begründung („Versand-Änderung gefolgt vom Aktivieren-Klick") ist durch
den Flush-Guard abgedeckt. **Ob ein unabgedeckter Fall bleibt** (zweiter Speichervorgang, während
der erste noch im Netz ist; Kopf-Inline-Edits in `routes/compare/[id]/+page.svelte`, die nicht in
der Schlange liegen; der Orte-Pfad oben), ist die offene Messung F1.

**Einordnung:** Die Schlange ist **kein** `context ===`-Zweig — sie zu behalten kostet AC-2
nichts, und ~30 Testdateien benutzen sie als Prüfstand. F1 ist damit eine Frage von **geringem
Einsatz**; die Scheibe entscheidet sich an F2 und F3, nicht hier.

## Befund 5 — Totcode (Rückbau ohne Verhaltensrisiko)

| Fundstelle | Lage |
|---|---|
| `CompareWizardState.saveComparePreset()` (Z. 194-235) | null Aufrufer; einziger Grund, warum der Anlege-Zustand den Hub-Nutzlastbauer importiert. **Festgenagelt** von `compare/__tests__/wizard_state_no_legacy_save.test.ts:47` („muss erhalten bleiben") — der Test muss mitgeändert werden |
| `compareWizardState.svelte.ts:12 export type SaveStatus` | null externe Importeure, kollidiert namentlich mit der Store-Klasse `SaveStatus` |
| `includeHourly`, `subscriptionId`, `subscriptionEnabled`, `existingDisplayConfig` | nur Deklaration, nirgends referenziert (Legacy `/api/subscriptions`, seit #1250 stillgelegt) |
| `WeatherMetricsTab.svelte:577` | Bedingung für beide Werte des Union-Typs wahr |
| 9 Kommentar-Nennungen von `buildHubPutPayload` in den vier `shared/*Speicherung`-Modulen | 0 Aufrufe, mehrere sagen selbst „entfällt" — Doku-Schuld |
| `HubWizardFields`, `HubEdit`, `PutQueue`, `CompareEditorEdits`, `NewComparePresetFields`, `RehydratedActiveMetrics` | nur dateiinterne Signaturtypen — un-exportierbar, nicht löschbar |

## Befund 6 — Testkopplung (Umbau-Kosten)

| Kopplung | Dateien |
|---|---|
| benutzen `createPutQueue` (meist als Prüfstand für `enqueueHubWrite`) | **~30** |
| importieren aus `compareHubWizardBridge` | **~48** |

Das ist das Hauptargument dafür, den Schlangen-Abbau **nicht** in dieselbe Scheibe zu legen wie
den Eigentums-Umbau: ein Verhaltensrisiko würde sich mit einer Massenänderung an Tests
vermischen.

**Durchsetzungsmuster existiert bereits:** vier AST-Wächter `*_laedt_keine_compare_klebeschicht.test.ts`
(Alarme, Versand, Wetter-Metriken, Corridor) — für AC-4 fortschreibbar statt neu zu erfinden.

## Regressionsnetz (E2E-Ratsche, `.github/ci_e2e_specs.txt`)

`compare-alarme-speichert-selbst` · `compare-wertebereiche-speichert-selbst` ·
`compare-wetter-metriken-speichert-selbst` · `compare-versand-speichert-selbst` ·
`compare-hub-inline-edit` · `compare-legacy-fields-survive-save` ·
`compare-cross-user-write-block` · `compare-editor-autosave-user-isolation` ·
`compare-radar-toggle` · `compare-detail-edit-entry` · `compare-editor-slice1`/`-slice3`.

**Aus S5 mitgenommen:** Die Unit-Harness ist SSR-only (`generate: 'server'`, kein DOM) —
reaktive Effekte und Prop-Verdrahtung laufen dort **nie**. Jede Zusicherung, die an einem
`$effect`-Wirkort hängt, braucht eine E2E-Spec, die **zusammen mit** der AC bestellt wird.

## Risiken

1. **Stiller Verlust der Reiter-Teilung.** Wird ein Reiter einzeln auf `preset` umgestellt,
   verliert der Rollback der Nachbarn seine Grundlage, ohne dass ein Test der umgestellten Datei
   rot wird. Mutations-Gegenprobe muss genau hier ansetzen.
2. **Doppelquelle als Dauerzustand.** Ein „`preset` wenn da, sonst `wiz`"-Fallback wäre genau
   das Anti-Muster aus dem Ticket-Befund — nur unter neuem Namen.
3. **Datenerhalt.** Voll-Spread-Nutzlast bleibt Pflicht, solange nicht belegt ist, dass der neue
   Merge-Kern (#2285) auch verschachtelte `display_config`-Schlüssel zusammenführt. Sonst nullt
   ein Reiter-PUT Felder eines Nachbarreiters (BUG-DATALOSS-Klasse).
4. **AC-2 unerfüllbar formuliert** (s. Befund 1) — ohne Korrektur blockiert die Scheibe an ihrer
   eigenen Zusicherung.
5. **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`** zurück; `/70-deploy`
   überspringt dann die gesamte Staging-Validierung (2× in S5 passiert). Nach **jedem** Commit
   gegenlesen.
6. **LoC-Limit.** Der Umbau überschreitet 250 sicher; `workflow.py status` vor der
   Override-Ankündigung fragen, nicht aus der Ausschlussliste ableiten.

## Offene Fragen für `/20-analyse`

**Reihenfolge ist Absicht: F2 und F3 entscheiden die Scheibe, F1 ist nachrangig.**

| # | Frage | Entscheidet |
|---|---|---|
| **F2** | Trägt die Wertprop-Umstellung (Weg (c), Vorlage `CompareOutlookLayoutControls`)? Probe an `CompareHourlyLayoutControls`, bevor verallgemeinert wird. | ob die 45 HERKUNFT-Zweige in S6 überhaupt fallen können, ohne #2277 vorzugreifen |
| **F3** | Wie wird die reiterübergreifende Teilung von `activeMetricKeys`/`metricAlertLevels`/`corridors` ersetzt, ohne den diff-basierten Rollback zu verlieren? | Reihenfolge und Unteilbarkeit der Umstellung |
| **F5** | Wie lautet die prüfbare Fassung von AC-2 und AC-4, die S6 erfüllen kann, ohne #2277 vorzugreifen? | Abnahmefähigkeit der Scheibe |
| **F4** | Mergt `applyComparePresetPatch` (#2285, live seit 18.09.) auch verschachtelte `display_config`-Schlüssel? | ob die Voll-Spread-Nutzlast und die drei toten Legacy-Felder im Versand-Payload fallen dürfen |
| **F6** | Braucht S6 Unter-Scheiben? Kandidaten: (a) Totcode + Bilanz, (b) Schlangen-Entscheidung, (c) Eigentums-Umbau | Schnitt der Spec — folgt aus F2 + F3 |
| **F1** | *(geringer Einsatz)* Bleibt ein Fall, in dem zwei Hub-PUTs ohne Schlange überholen könnten (Orte-Pfad, Kopf-Inline-Edits außerhalb `CompareTabs`)? | ob die Schlange fällt oder mit dokumentiertem Grund bleibt; wo F002/F003 künftig geprüft werden |

## Bezüge

- Issue #2276 · Epic #2345 (Etappe P1) · Dach-Epic #1374
- Vorgänger-Kontext: `docs/context/rework-2276-compare-speicherweg.md` (Scheiben-Plan E2/E3/E4)
- Specs S1–S5: `docs/specs/modules/rework_2276_s1_netz_und_fundament.md` … `_s5_versand.md`
  (S5 Punkt 4 enthält die fertige Zweig-Begründung für `VersandTab`, S5 Punkt 6 die Lage der
  drei toten Legacy-Felder)
- Nachfolger: #2277 (Anlege-Editor, Etappe P2) — darf nicht vorgegriffen werden
- Sammel-Issues für Nebenbefunde: #1199 (allgemein), #1196/#1197 (Test-/Gate-Befunde)

---

# Analysis

> Phase 2, 2026-09-20. Alle sechs offenen Fragen aus Phase 1 sind hier entschieden —
> keine davon geht an den PO, alle waren technisch am Code messbar.

## Type

**Rework** (strukturell, verhaltensneutral) — kein Bug, kein neues Feature.

## Antwort auf F2 — Weg (c) trägt, belegt statt vermutet

`shared/CompareOutlookLayoutControls.svelte` ist **kein Gedankenspiel, sondern lebender
Präzedenzfall seit #1720 S1**: flache Wertprops + Änderungs-Rückrufe
(`metricKeys`/`onMetricKeys` · `metricFormats`/`onMetricFormats` · `enabled`/`onEnabledChange`
· `catalog` · `grundauswahl` · `smsSymbols`), **null `context ===`**, **null `wiz`-Zugriff im
Rumpf** — und derselbe Baustein bedient damit Trip **und** Ortsvergleich. Der Kommentar in der
Datei benennt die Invariante ausdrücklich: „geteilt ist die Steuerung, nicht der Speicher-Weg."

Die Aufrufstelle `WeatherMetricsTab.svelte:1495-1504` zeigt zugleich die **Mechanik**: der
`wiz`-Zugriff verschwindet nicht, er **wandert eine Ebene nach oben** zum Elternteil. Daraus
folgt die tragende Erkenntnis für den Schnitt:

> Weg (c) ist keine Einzelmaßnahme, sondern eine **Kette**. Sie endet erst, wenn der
> Elternteil `compare/CompareTabs.svelte` bzw. `compare-new/CompareNewEditor.svelte` heißt —
> dort **darf** der Wizard stehen, denn beide sind compare-eigen und liegen nicht in
> `shared/`. Ein einzeln umgestellter Blatt-Baustein verschiebt nur, er gewinnt nichts.

F2 ist damit **mit Ja beantwortet**; (a) Doppelquelle und (b) Preset-Entwurf scheiden aus,
(d) Verschiebung auf #2277 ist unnötig.

## Antwort auf F3 — der Rollback überlebt, weil das geteilte Objekt nur umzieht

`rollbackAlarmSnapshot` (`shared/alarmeVergleichSpeicherung.ts:135-160`) mutiert
`target[field]` auf einem **lebenden, reiterübergreifend geteilten** Objekt und setzt ein Feld
nur zurück, wenn dort noch exakt der gesendete Wert steht. Diese Zusicherung hängt **an der
Objektidentität**, nicht daran, dass das Objekt `wiz` heißt.

Der Hub hält bereits ein solches Objekt: `let currentPreset = $state<ComparePreset>(…)`
(`CompareTabs.svelte:196`), fortgeschrieben durch `uebernehmeHubAntwort` (`:363`). Die Reiter
bekommen es schon heute als Getter-Prop (`preset={currentPreset}`, `:1005/:1022/:1025/:1048/
:1071`) — es ist also **nicht** eingefroren, sondern lebt. Wird der Wizard als Anzeigequelle
durch `currentPreset` ersetzt, bleibt genau eine lebende geteilte Instanz; der diff-basierte
Rollback behält seine Grundlage, sein Ziel heißt nur anders.

**Und die Abbildung muss nicht erfunden werden:** die Richtung Preset → Anzeige ist vollständig
gebaut und läuft heute schon bei jedem Reiterwechsel — `hydrateWizardStateFromPreset` (`:338`),
`hydrateVersandFieldsFromPreset` (`:378`), `hydrateAlarmFieldsFromPreset` (`:421`),
`hydrateWeatherMetricsFromPreset` (`:457`), `hydrateDayWindowFromPreset` (`:473`),
`hydrateLayoutFieldsFromPreset` (`:500`). Sie schreibt ihr Ergebnis nur ins falsche Ziel
(`wizardState`). Der Umbau leitet sie um, er dreht nichts um.

Ausgenommen bleiben die drei Felder ohne Preset-Pendant (`sendEmail`, `isEditMode`,
`metricsManuallyEdited`) — UI-Zustand, gehört in den lokalen `$state` des Elternteils.

## Antwort auf F4 — tief genug, aber der Voll-Spread bleibt trotzdem

Gemessen an `internal/handler/compare_preset.go:279-301`: `applyComparePresetPatch` ruft
`mergeBriefingPatch`, der **preserve-by-default** arbeitet; verschachtelte JSON-Objekte
(`display_config`, `official_warnings`, `alert_channel_thresholds`) werden über
`mergeConfigMap` **eine Ebene tief feldweise gemergt**. Ein Teil-Payload würde flache
`display_config`-Schlüssel eines Nachbarreiters also nicht nullen; Regressionsschutz liegt in
`internal/handler/put_partial_body_preserves_all_fields_test.go`.

**Entscheidung trotzdem: Voll-Spread-Nutzlast bleibt in dieser Etappe unangetastet.**
Begründung: „eine Ebene tief" deckt nicht zu, was zwei Ebenen tief in `display_config` liegt,
und der Umbau ist ohne diesen Zusatz schon groß genug. Eine Payload-Schlankheitskur mit
Datenverlust-Risiko (BUG-DATALOSS-GR221) gehört nicht in dieselbe Scheibe wie ein
Eigentums-Umbau. F4 wandert als Nebenbefund nach #1199.

## Antwort auf F1 — die Schreibschlange bleibt, und der Grund ist ein anderer als gedacht

Phase 1 stufte F1 als „geringen Einsatz" ein und vermutete, der Flush-Guard decke den Fall
bereits ab. **Das ist widerlegt.** Die Schlange ist kein Komfort-Mechanismus, sondern der
einzige Schutz gegen eine Klasse von stillem Datenverlust, die der ETag **strukturell nicht
fangen kann**:

> `hubPutQueue` hält den **Payload-Bau** im `enqueue()`-Closure — `buildXxxPayload(currentPreset,
> …)` liest also erst zur tatsächlichen Ausführungszeit, nach Abschluss des vorherigen Eintrags
> (`CompareTabs.svelte:198-203`, `:256-259`). Der ETag-Mechanismus serialisiert dagegen nur die
> **Netzwerk-Ausführung**: `api.ts:88` schlägt `getKnownEtag(tripId)` bewusst **erst beim
> Losschicken** innerhalb der Warteschlange nach (ausdrücklich so gebaut in #1395 S3, um falsche
> 412 zu vermeiden). Der Request-**Body** ist zu diesem Zeitpunkt längst eingefroren.
>
> **Folge:** Zwei kurz nacheinander ausgelöste Hub-Schreibvorgänge ohne `hubPutQueue` bauen
> beide ihren Body aus demselben, noch nicht aktualisierten `currentPreset`. Der zweite wird mit
> **gültigem** `If-Match` abgefeuert, bekommt **200 OK** — und setzt die Felder des ersten,
> bereits erfolgreichen PUTs still zurück. Kein 412, keine Konflikt-Anzeige, kein Hinweis.

Gemessene ungeschützte Paare (alle `CompareTabs.svelte`): Orte-PUT `:261` gegen jeden der vier
selbst speichernden Reiter (`:1007`/`:1022`/`:1025`/`:1050`/`:1073`) — denn `orte` steht **nicht**
in `SELBST_SPEICHERNDE_VERGLEICH_REITER` (`wertebereicheVergleichSpeicherung.ts:207-212`), beim
Verlassen wird also nie geflusht · `handleToggleActive` `:655` gegen dieselben vier · Orte gegen
ToggleActive · Orte gegen sich selbst (zwei schnelle ✕-Klicks, keine UI-Sperre während des Flugs).

**Entscheidung: die Schlange bleibt — und zwar als Schutzmechanismus, nicht als Altlast.** Sie
darf auch in S6f **nicht ersatzlos** fallen; wer sie anfasst, muss den Payload-Bau anderweitig
bis zur Ausführungszeit verzögern. Das gehört als Warnung in die S6f-Spec. Nebenbei gilt
weiterhin: sie ist kein `context ===`-Zweig, kostet AC-2 also nichts, und ~30 Testdateien nutzen
sie als Prüfstand.

**Nebenbefund mit eigenem Gewicht (kein Sammel-Eintrag):** `routes/compare/[id]/+page.svelte:49`
hält eine **zweite, unabhängige** `currentPreset`-Instanz und speichert Name/Region/Profil per
Voll-Body-PUT (`:166`/`:193`/`:210`) komplett außerhalb der Schlange. Einen Rückkanal nach
Hub-PUTs gibt es nicht — `invalidateAll()` wird ausweislich der Kommentare (`:106-112`,
`CompareTabs.svelte:187/662/697`) **bewusst** nur im Kebab-Pfad gerufen. Wer also einen Ort
entfernt und danach oben den Namen ändert, schickt die **alten** `location_ids` zurück und macht
die Orte-Änderung rückgängig. Nutzersichtbar **und** Datenverlust ⇒ nach der Triage-Regel ein
eigenes Issue: **#2381** (angelegt 2026-09-20). Der Befund ist von `hubPutQueue` unabhängig und
liegt außerhalb des Umfangs von #2276.

## Antwort auf F5 — die prüfbare Fassung von AC-2 und AC-4

Die Ticket-Fassung von AC-2 („es verbleiben nur fachliche Verzweigungen") ist **nicht
erfüllbar** (Befund 1): elf Zweige sind reine Beschriftungs-/Sichtbarkeitsunterschiede ohne
Datenweg und fallen bei diesem Umbau nicht weg. Prüfbare Fassung:

> **AC-2 (neu):** Nach dem Umbau enthält `frontend/src/lib/components/shared/` **keine
> HERKUNFT-Verzweigung** mehr — keine Stelle, die allein danach unterscheidet, woher ein Wert
> gelesen oder wohin er geschrieben wird. Verbleibende Verzweigungen sind ausschließlich
> FACHLICH oder DARSTELLEND und in der Spec einzeln mit Grund gelistet. Der Nachweis ist
> mechanisch reproduzierbar über den eingefrorenen Zählbefehl.

Zählbefehl, in der Spec festzuschreiben — der Kommentarfilter gehört **in den Befehl**, nicht
in die Prosa, sonst ist der Nachweis nicht mechanisch reproduzierbar:

```
cd frontend/src/lib/components/shared && \
  grep -rn 'context ===\|context !==' . --include='*.svelte' --include='*.ts' \
  | grep -v __tests__ | grep -vE ':\s*(\*|//|/\*)'
```

**Messung beim Stand `73f504c9`: 71 Roh-Treffer, davon 2 Kommentarzeilen**
(`WeatherMetricsTab.svelte:1258`, `layout-tab/LayoutTab.svelte:37` — beides historische
Notizen ohne Verzweigung) ⇒ **69 produktive Verzweigungsstellen**. Das deckt sich **exakt** mit
Phase 1; die vermeintliche Differenz war ein Zählfehler beim Filtern, keine Drift.

**Bezugsgröße ist die eingefrorene `Datei:Zeile`-Liste, nicht die Zahl.** Die Ratsche hält die
69 Fundstellen namentlich; eine Zahl allein sagt nicht, ob eine gefallene Verzweigung durch eine
neue ersetzt wurde.

> **AC-4** ist so, wie es im Ticket steht, korrekt und bleibt: kein produktiver Importeur von
> `compare/compareHubWizardBridge.ts` mehr. Vollständigkeit verlangt, die **zwei
> Nicht-`CompareTabs`-Konsumenten** mitzunehmen: `buildFreshTogglePutPayload` →
> `routes/compare/+page.svelte:136` und den Typ `AlarmHydrationTarget` →
> `shared/alarmeVergleichSpeicherung.ts`. Ohne deren Umzug ist AC-4 nicht erreichbar.

Durchsetzung über die **bereits existierende** Mechanik statt einer neuen: vier Wächter
`*_laedt_keine_compare_klebeschicht.test.ts` (Alarme, Versand, Corridor, Wetter-Metriken)
messen den **echten Ladegraphen** per `module.registerHooks` — kein Grep, kein
Dateiinhalt-Check. Sie werden fortgeschrieben, nicht ersetzt.

## Antwort auf F6 — ja, S6 braucht Unter-Scheiben; Schnitt wie S2–S5

**Der Umfang, gemessen.** `wiz`-Referenzen bzw. `context`-Verzweigungen je Baustein:

| Baustein | `wiz`-Refs | `context`-Zweige | Mounts im Vergleich |
|---|---|---|---|
| `WeatherMetricsTab.svelte` | 38 | 8 | 3 (Hub + 2× Anlege) |
| `AlarmeTab.svelte` | 36 | 18 | 3 |
| `VersandTab.svelte` | 27 | 3 | 3 |
| `CorridorEditor.svelte` | 4 (+`getContext`) | 14 | 2 |
| `CorridorEditorMobile.svelte` | 1 (+`getContext`) | 14 | 2 |
| `CompareHourlyLayoutControls.svelte` | 7 ¹ | 0 | 1 |

¹ Rohe Grep-Zahl wäre 10; tatsächliche Zugriffsstellen sind **7** — Bindung `:61`, lesend `:82`,
`:98`, `:194`, schreibend `:97`, `:108`, `:176` (2 Felder: `hourlyMetricKeys`, `hourlyEnabled`).
Die übrigen Treffer sind Interface-Deklaration und Kommentare. Bei allen anderen Zeilen der
Tabelle ist die rohe Grep-Zahl angegeben — vor Gebrauch in einer Spec je Datei nachzählen.

**Die Mount-Falle:** `compare-new/CompareNewEditor.svelte` mountet jeden der großen Organismen
**zweimal** (Desktop-Block ~:378-404, Mobile-Block ~:479-490), der Hub einmal — also **drei
Compare-Mounts je Organismus**. Weg (c) verlangt, dass **jede** dieser Stellen die Wertprops
liefert. Der Speicherweg von `/compare/new` bleibt dabei unangetastet; die Anlege-Seite speist
dieselben Props auf ihrer Ebene aus ihrem eigenen `wiz`. Das ist **kein** Vorgriff auf #2277,
sondern die zwingende Gegenseite derselben Prop-Signatur.

`CorridorEditor` + `CorridorEditorMobile` sind über alle 14 Stellen paarweise identisch
verzweigt und kommen per `getContext` an den Zustand — unsichtbar in der Aufrufer-Signatur.
Sie müssen **zwingend zeitgleich** fallen.

**Schnitt.** Das Muster „eine Scheibe je Organismus, jede in sich verhaltensneutral, mit den
Hub-E2E-Specs als Netz" hat in S1–S5 fünfmal getragen. Es wird fortgesetzt:

**Die in Phase 1 vorgeschlagene „Probe" an `CompareHourlyLayoutControls` entfällt — sie wäre
zirkulär.** Phase 1 wollte sie, weil F2 offen war. F2 ist jetzt durch einen **live laufenden**
Präzedenzfall beantwortet: `CompareOutlookLayoutControls`, seit #1720 S1 in Produktion, wird vom
**selben Elternteil 22 Zeilen tiefer** gemountet und nennt den Probanden im eigenen Kopf seinen
„strukturellen Zwilling". Den Zwilling eines bereits umgestellten Bausteins umzustellen, um zu
beweisen, dass Umstellen funktioniert, beweist nichts.

Entscheidender noch: `CompareHourlyLayoutControls` hat **0 `context`-Verzweigungen**. Eine
Scheibe, die nur ihn umstellt, bewegt AC-2 um null und AC-4 um null — die 10 `wiz`-Referenzen
wandern lediglich in `WeatherMetricsTab`, das bereits 38 trägt. Das ist genau das, was oben
unter F2 als wertlos benannt ist: „Ein einzeln umgestellter Blatt-Baustein verschiebt nur, er
gewinnt nichts." Kind **und** Elternteil zusammen sind die kleinste Einheit, die wirklich
HERKUNFT-Zweige fallen lässt — und weil das Kind genau **eine** Mount-Stelle hat
(`WeatherMetricsTab:1473`), kostet es die Wetter-Metriken-Scheibe fast nichts, es mitzunehmen.

| Scheibe | Inhalt | Warum hier |
|---|---|---|
| **S6a** | Totcode aus Befund 5 · `Datei:Zeile`-Ratsche für AC-2 einfrieren | das Messfundament, auf dem AC-2 ruht. Rührt keinen `$effect`-Wirkort an, braucht deshalb **keine** E2E-Spec und voraussichtlich **keinen** LoC-Override. Eigenständiger Wert, minimales Risiko |
| **S6b** | Wetter-Metriken + Layout, **einschließlich `CompareHourlyLayoutControls`** | größter `wiz`-Block, die Layout-Vorlage sitzt schon darin; das Kind fällt hier mit dem Elternteil zusammen |
| **S6c** | Alarme | 18 Zweige, geteilte Felder `metricAlertLevels` |
| **S6d** | Wertebereiche: `CorridorEditor` **+** `CorridorEditorMobile` gemeinsam | Doppel-Mount, paarweise identisch — unteilbar |
| **S6e** | Versand | wenigste Zweige, aber zwei Markup-Bäume |
| **S6f** | `compareWizardState` + Bridge aus dem Hub entfernen · AC-2/AC-4-Bilanz · Schlangen-Entscheid dokumentieren | geht erst, wenn kein `shared/`-Baustein mehr am Wizard hängt. **Warnung in die Spec:** `hubPutQueue` darf nicht ersatzlos fallen (s. F1) |

**Diese Spec beschreibt S6a.** Die übrigen folgen als eigene Scheiben derselben Etappe.

## Affected Files (S6a)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `compare/compareWizardState.svelte.ts` | MODIFY | Totcode: `saveComparePreset()` (:194-235, null Aufrufer), `export type SaveStatus` (:12, null externe Importeure, kollidiert namentlich mit der Store-Klasse), `includeHourly`/`subscriptionId`/`subscriptionEnabled`/`existingDisplayConfig` (Legacy `/api/subscriptions`, seit #1250 stillgelegt) |
| `compare/__tests__/wizard_state_no_legacy_save.test.ts` | MODIFY | nur der **dritte** Test (Gegenprobe, :47) nennt `saveComparePreset` „muss erhalten bleiben" — s. Punkt 2 unten |
| `shared/WeatherMetricsTab.svelte` | MODIFY | tote Bedingung `:577` ersatzlos streichen (für beide Werte des Union-Typs wahr) |
| vier `shared/*Speicherung`-Module | MODIFY | 9 Kommentar-Nennungen von `buildHubPutPayload` ohne Aufruf bereinigen (Doku-Schuld) |
| `shared/__tests__/…_herkunft_zweige_ratsche.test.ts` | CREATE | friert die 69 Fundstellen als `Datei:Zeile`-Liste ein |

## Scope Assessment

- Dateien: ~8
- Geschätzte LoC: **+70 / −120** ⇒ das Limit 250 wird voraussichtlich **nicht** überschritten.
  Falls doch: vor der Override-Ankündigung `workflow.py status` fragen, nicht aus der
  Ausschlussliste ableiten.
- Risiko: **NIEDRIG** — kein `$effect`-Wirkort berührt, keine Prop-Verdrahtung geändert, kein
  Datenweg angefasst. Reiner Rückbau von nachweislich unerreichtem Code plus ein Messwerkzeug.

## Technical Approach (S6a)

1. **Totcode-Rückbau** genau im Umfang von Befund 5, jeder Posten mit belegtem „null Aufrufer".
   Die **nicht** löschbaren Posten (`HubWizardFields`, `HubEdit`, `PutQueue`,
   `CompareEditorEdits`, `NewComparePresetFields`, `RehydratedActiveMetrics` — dateiinterne
   Signaturtypen) bleiben ausdrücklich stehen.
2. **Der Legacy-Save-Wächter wird nicht umgedreht, sondern präzisiert.** Sein Schutzziel liegt
   in Test 1 und 2 (`save()`/`toggleEnabled()` dürfen nicht zurückkehren — sie schrieben in den
   mit #1250 abgeschafften Store `/api/subscriptions`); der dritte Test ist ausweislich seines
   eigenen Kommentars nur eine **Gegenprobe** („darf durch Scheibe 0 NICHT rot werden"). Die
   Zusicherung von #1250 bleibt also **vollständig erhalten**: Test 1+2 unangetastet, im dritten
   Test entfällt allein `saveComparePreset`, `saveNewPreset` bleibt gefordert (Anlege-Pfad).
3. **Die Ratsche hält die Liste, nicht die Zahl** — 69 `Datei:Zeile`-Einträge, im Wächter
   eingefroren, **nicht** zur Laufzeit aus dem Verzeichnis berechnet. Sonst macht das Leeren der
   Liste den Test vakuum-grün. Rückdreh-Gegenprobe ist Pflicht: eine Zeile künstlich entfernen
   ⇒ der Wächter muss rot werden, und zwar **dieser** Wächter.
4. Totcode-Rückbau und Ratsche in getrennten Commits.

## Dependencies

- #2285 (`applyComparePresetPatch`) live seit 18.09. — für S6a nicht auf dem Pfad.
- #2277 (Anlege-Editor, Etappe P2) darf nicht vorgegriffen werden: S6a ändert an
  `/compare/new` **nichts**.
- Keine E2E-Spec nötig, damit auch kein Eintrag in `.github/ci_e2e_specs.txt`. Ab S6b ändert
  sich das: jede Prop-Verdrahtung braucht eine E2E-Spec, die **zusammen mit** der AC bestellt
  wird — die SSR-Harness (`generate: 'server'`, kein DOM) sieht `$effect`-Wirkorte prinzipiell
  nie.

## Risiken

1. **Vakuum-grüne Ratsche** — die Hauptgefahr dieser Scheibe. Zielliste einfrieren,
   Rückdreh-Gegenprobe ist Pflicht.
2. **Schutzverlust beim Legacy-Wächter**, falls Test 1+2 versehentlich mit angefasst werden.
   Die Mutations-Gegenprobe muss zeigen: `save()` wieder einführen ⇒ rot.
3. **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`** — nach **jedem**
   Commit gegenlesen. Bei S6a ist der Scope tatsächlich klein, das entschuldigt aber kein
   ungeprüftes Feld.
4. **Testkopplung**: ~48 Dateien importieren aus `compareHubWizardBridge`, ~30 nutzen
   `createPutQueue`. S6a rührt beides nicht an — das bleibt S6f vorbehalten.

## Open Questions

Keine. F1–F6 sind oben entschieden; die Neufassung von AC-2 geht mit ihrer Begründung in die
Spec und wird dort in Phase 3 freigegeben.

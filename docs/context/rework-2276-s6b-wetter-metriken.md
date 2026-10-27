# Context: #2276 S6b — Wetter-Metriken auf Wertprops

> Scheibe **S6b** von Issue #2276 (Epic #2345). Der Gesamt-Kontext und die
> Analyse-Antworten F1–F6 für S6 stehen in
> [`rework-2276-s6-rueckbau.md`](rework-2276-s6-rueckbau.md) — dieses Dokument
> wiederholt sie **nicht**, sondern schneidet sie auf S6b zu und ergänzt, was
> seit S6a neu gemessen ist.

## Request Summary

> 🔴 **Von `/20-analyse` am 2026-09-20 korrigiert.** Die ursprüngliche Fassung
> dieses Abschnitts ist durch die Messungen im Abschnitt `## Analysis` widerlegt
> und steht unten als Fußnote. Es gilt ausschließlich der folgende Text.

**`CompareHourlyLayoutControls.svelte`** wird vom Zustandsobjekt `wiz`
(Compare-Wizard-Bus) auf reine **Wertprops + Änderungs-Rückrufe** umgestellt
(Weg (c) der S6-Analyse), exakt nach dem Muster des unmittelbar daneben
montierten Geschwisters `CompareOutlookLayoutControls`. **`WeatherMetricsTab`
behält `wiz`** — die Umstellung des Elternteils ist eine andere Scheibe (dort
liegen ~30 `wiz`-Zugriffe über fünf Belange, siehe `## Analysis`).

Zusätzlich fällt **eine** HERKUNFT-Verzweigung (`WeatherMetricsTab.svelte:1273`)
als nachgelagerte Redundanz; die Ratsche geht damit von **68 auf 67**. Die
übrigen fünf HERKUNFT-Zweige bleiben, jeder mit belegtem Grund. Die drei
fachlichen Verzweigungen bleiben ohnehin. Der Speicherweg von `/compare/new`
wird nicht angefasst (kein Vorgriff auf #2277).

<details><summary>Ursprüngliche, widerlegte Fassung (Stand `/10-context`)</summary>

> `WeatherMetricsTab.svelte` und sein Kind `CompareHourlyLayoutControls.svelte`
> werden vom Zustandsobjekt `wiz` auf reine Wertprops + Änderungs-Rückrufe
> umgestellt. Dadurch fallen die **sechs HERKUNFT-Verzweigungen** dieses
> Bereichs. — Widerlegt: vier der sechs hängen nicht am Eigentum (zwei
> trip-seitig, zwei Ladepfad), einer ist durch die freigegebene AC-13 aus S4
> geschützt.

</details>

## Ausgangslage

| Fakt | Stand |
|---|---|
| Basis-Commit | `a1007c11` (S6a live, Staging VERIFIED, Selftest PASS) |
| Ratsche `shared/` | **68** eingefrorene `Datei:Zeile`-Fundstellen |
| Vorgänger-Scheiben | S1–S5 + S6a live; Muster „eine Scheibe je Organismus" hat sechsmal getragen |
| Präzedenzfall für Weg (c) | `shared/CompareOutlookLayoutControls.svelte`, live seit #1720 S1 |

## Betroffene Fundstellen der 68er-Ratsche

Kategorien aus dem Anhang der S6a-Spec
(`docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md:365-411`):

| # | Fundstelle | Kategorie | Quelltext (gekürzt) | Was ihr Fallen erfordert |
|---|---|---|---|---|
| 23 | `WeatherMetricsTab.svelte:545` | HERKUNFT | `context === 'route' && trip && catalogLoaded && !isDirty` | **Trip**-seitige Vorbefüllung — fällt nur, wenn auch der Trip-Zweig umgestellt wird |
| 24 | `WeatherMetricsTab.svelte:560` | HERKUNFT | `context === 'route' && Object.keys(catalog).length === 0` | **Trip**-seitiger Katalog-Fetch — dito |
| 26 | `WeatherMetricsTab.svelte:589` | HERKUNFT | `context === 'vergleich' && !smsSymbols` | Vergleich-seitiger Fetch — ersetzbar durch „Prop da → laden" |
| 27 | `WeatherMetricsTab.svelte:602` | HERKUNFT | `context === 'vergleich' && Object.keys(catalog).length === 0` | dito |
| 28 | `WeatherMetricsTab.svelte:1273` | HERKUNFT | `$effect`-Guard `context !== 'vergleich' \|\| !wiz \|\| !vergleichSpeicherung` | hängt an der **Speicher**-Verdrahtung, nicht am Eigentum — Mechanismus offen |
| 67 | `weatherMetricsCompareSave.ts:534` | HERKUNFT | `p.context === 'vergleich' && !!p.wiz && !!p.preset && !!p.saveController` | reine Prädikatfunktion; `preset`+`saveController` allein könnten schon unterscheiden — Mechanismus offen |
| 29 | `WeatherMetricsTab.svelte:1323` | FACHLICH — Markup-Gabelung | `{#if context === 'vergleich'}` | **bleibt** |
| 68 | `weatherMetricsTabSections.ts:72` | FACHLICH | SMS-Schwellen/Report-Config nur im Trip | **bleibt** |
| 69 | `weatherMetricsTabSections.ts:73` | FACHLICH | Stundenverlauf nur im Vergleich | **bleibt** |

🔴 **Die Zielzahl steht noch nicht fest und darf in der Spec nicht geraten
werden.** Keiner der sechs HERKUNFT-Zweige fällt allein dadurch, dass `wiz`
durch Wertprops ersetzt wird:

- `:589`/`:602` sind vergleich-seitige Ladevorgänge — sie lassen sich am
  ehesten auf „Prop vorhanden → laden" umstellen (Muster des Präzedenzfalls).
- `:545`/`:560` sind **trip**-seitig. Sie fallen nur, wenn S6b auch die
  Trip-Hälfte anfasst — was die Scheibe erheblich vergrößert (F-S6b-5).
- `:1273` und `:534` hängen an der Speicher-Verdrahtung, nicht am Eigentum.

Die Spanne reicht damit von **68 − 2 = 66** bis **68 − 6 = 62**. `/20-analyse`
legt die Zahl fest und benennt für jeden Zweig den Mechanismus; eine Spec, die
62 zusichert und bei 66 landet, scheitert an ihrer eigenen Zusicherung.

`CompareHourlyLayoutControls.svelte` steht in der Liste **nicht** — er hat null
`context`-Verzweigungen. Er kommt trotzdem mit, weil ein allein umgestellter
Blatt-Baustein nur verschiebt statt zu gewinnen und seine einzige Mount-Stelle
im Elternteil liegt.

## Related Files

| Datei | Zeilen | Relevanz |
|---|---|---|
| `shared/WeatherMetricsTab.svelte` | 2115 | Hauptziel: ~24 `wiz`-Zugriffsstellen, 5 HERKUNFT-Zweige, mountet das Kind |
| `shared/CompareHourlyLayoutControls.svelte` | 284 | Kind: **5** `wiz`-Zugriffsstellen (`:82` L, `:97-98` S, `:108` S, `:176` S, `:194` L), 2 Felder (`hourlyMetricKeys`, `hourlyEnabled`), 0 Zweige |
| `shared/CompareOutlookLayoutControls.svelte` | 272 | **Vorlage** — lebender Präzedenzfall für Weg (c) |
| `shared/weather-metrics-tab/DayWindowCard.svelte` | 149 | **zweiter, bereits fertiger Wertprop-Präzedenzfall** (`startHour`/`endHour` + Rückrufe) |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | 535 | Speicher-Modul, 1 HERKUNFT-Zweig (`:534`). **Bereits vom Wizard-Typ entkoppelt** — s.u. |
| `shared/weather-metrics-tab/weatherMetricsTabSections.ts` | 76 | 2 fachliche Zweige — bleiben unberührt |
| `compare/CompareTabs.svelte` | 1457 | Hub-Mount `:1002-1009` — muss die Wertprops liefern |
| `compare-new/CompareNewEditor.svelte` | 573 | Anlege-Seite, **2 Mounts** (`:378` Desktop, `:479` Mobil) |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | 260 | Die Ratsche selbst |

### Mount-Stellen, frisch gezählt

`CompareHourlyLayoutControls` hat **genau eine** Aufrufstelle
(`WeatherMetricsTab.svelte:1473-1476`) — deshalb kostet es fast nichts, das
Kind in dieser Scheibe mitzunehmen.

`WeatherMetricsTab` dagegen hat **sieben**, davon nur drei im Vergleich:

| Aufrufstelle | Seite | übergibt heute |
|---|---|---|
| `compare/CompareTabs.svelte:1002-1009` | Vergleich (Hub) | `context="vergleich" wiz={wizardState} preset={currentPreset} saveController enqueueHubWrite onCompareUpdate` |
| `compare-new/CompareNewEditor.svelte:378` | Vergleich (Anlegen, Desktop) | `context="vergleich" {wiz}` — **kein** `preset`/`saveController` |
| `compare-new/CompareNewEditor.svelte:479` | Vergleich (Anlegen, Mobil) | dito |
| `trip-detail/TripTabs.svelte:224` | Trip | `{trip} {onTripUpdate} {saveController}` |
| `edit/TripEditView.svelte:201` | Trip | `{trip}` |
| `trip-new/TripNewEditor.svelte:881` | Trip (Anlegen, Desktop) | `trip={stubTrip} createMode={true}` + 3 Rückrufe |
| `trip-new/TripNewEditor.svelte:1113` | Trip (Anlegen, Mobil) | dito |

🔴 **Jede Änderung an der Prop-Signatur von `WeatherMetricsTab` berührt auch die
vier Trip-Mounts** — nicht nur die drei Compare-Mounts. Das ist in der
S6-Gesamtanalyse so nicht ausgewiesen.

### Was der Präzedenzfall wirklich kostet

`CompareOutlookLayoutControls` ist innen sauber: reine Wertprops
(`metricKeys`, `catalog`, `grundauswahl`, `enabled`, `metricFormats`,
`smsSymbols`, `title`, `showEmailOnlyHint`) plus Rückrufe
(`onMetricKeys`, `onEnabledChange`, `onMetricFormats`) — **kein `wiz`, kein
`$bindable`, kein `context`-Zweig**. Zwei Kunstgriffe tragen das:

- **„Prop da → Bedienelement da"** statt Herkunfts-Zweig: fehlt
  `onEnabledChange`, wird der Ein/Aus-Schalter gar nicht gerendert
  (`:220-227`); fehlt `onMetricFormats`, entfällt der Roh/Einfach-Umschalter
  (`:211-213`).
- **Vokabular-Normalisierung im Inneren** (`grundauswahlKennungen` `:138-153`)
  übersetzt Compare-Katalogschlüssel (`temp_max_c`) und Trip-Kennungen
  (`temperature`) auf dieselbe Kennung. Das ist der eigentliche Trick, der den
  `context`-Zweig überflüssig macht.

🔴 **Der Preis steht im Elternteil.** Nur zur Bedienung dieses einen Mounts
liegen in `WeatherMetricsTab` drei Adapterfunktionen (`:1225-1227`, `:1233-1235`,
`:1237-1239`, je `if (wiz) wiz.xyz = …`), drei `wiz`-Lesezugriffe im
Montage-Block (`:1496`, `:1500`, `:1502`) und ein `&& wiz`-Guard (`:1487`). Der
Präzedenzfall hat den `wiz`-Zugriff **verschoben, nicht beseitigt** — genau wie
die S6-Analyse es vorhergesagt hat. Für S6b heißt das: die Adapter wandern nach
`CompareTabs` und `CompareNewEditor`, und dort misst die 68er-Ratsche nicht.

### Zwei Entlastungen

- **`weatherMetricsCompareSave.ts` hängt gar nicht am Wizard-Typ.** `wiz` ist
  dort nur ein Parametername, typisiert als `export type WetterMetrikenZustand =
  object` (`:306`), Zugriff strukturell über `felder(wiz)` (`:308-309`). Kein
  Import von `CompareWizardState` im ganzen Verzeichnis. Die Datei braucht nur
  ein Objekt mit den richtigen Feldnamen — der Umbau ist dort billig.
- **Zwei tote Rückruf-Props nicht mitschleppen:** `onOutlookCommit`
  (`CompareOutlookLayoutControls:58`) und `onHourlyCommit`
  (`CompareHourlyLayoutControls:59`) werden von **keiner** Aufrufstelle
  übergeben — S4 hat sie ersetzt (`WeatherMetricsTab:171-172`).

### Der strukturelle Brocken

`WeatherMetricsTab.svelte:1323` (`{#if context === 'vergleich'}`) ist die
**Top-Level-Markup-Gabelung**: `{:else}` bei `:1526`, Ende bei `:1948`. Sie
teilt das halbe Template in zwei Hälften. Sie ist als FACHLICH eingestuft und
**bleibt** — S6b stellt das Eigentum um, nicht den Markup-Baum.

## Bestehendes Regressionsnetz

In der CI-Ratsche (`.github/ci_e2e_specs.txt`) und damit wirksam:
`compare-wetter-metriken-speichert-selbst.spec.ts` (aufgenommen 19.09. mit S4),
`compare-hub-inline-edit`, `compare-legacy-fields-survive-save`,
`compare-editor-slice1`/`-slice3`, `compare-detail-edit-entry`,
`compare-cross-user-write-block`, `compare-editor-autosave-user-isolation`,
`issue-682-compare-editor-mobile`.

🔴 **Nicht in der Ratsche und damit in der CI wirkungslos:**
`compare-hourly-metric-order.spec.ts`, `compare-metric-order.spec.ts`,
`compare-layout-tab-dissolution.spec.ts`, `layout-tab-vergleich.spec.ts`,
`layout-tab-route.spec.ts`. Genau diese decken das Layout-Verhalten des Kindes
ab. Wer sich in S6b auf sie verlässt, verlässt sich auf Tests, die nicht laufen.

## Risiken

1. **🔴 Die Ratsche misst nur `shared/` — Zweige, die zum Elternteil hochwandern, sieht sie nicht.**
   Der Zählbefehl läuft mit `SHARED` als cwd. `compare/` und `compare-new/` liegen
   außerhalb. Eine Verzweigung, die aus `WeatherMetricsTab` nach `CompareTabs`
   umzieht, liest sich in der Ratsche als **entfernt**. **Gegenmessung ist
   Pflicht** — Baseline heute, frisch gemessen:
   `context ===`/`context !==` außerhalb `shared/` im gesamten `frontend/src`:
   **3 Fundstellen, alle in `lib/components/organisms/MetricsEditorContextBar.svelte`**;
   in `compare/` und `compare-new/` **null**. S6b darf diese Null nicht anheben.

2. **🔴 Die Zeilennummern-Regel von S6a kollidiert mit einem echten Umbau.**
   Für die **beseitigten** Zeilen ist der Weg klar und dokumentiert:
   `docs/reference/gates_und_ratschen.md:326-330` — „Jede Folgescheibe muss die
   von ihr beseitigten Zeilen **bewusst** aus der eingefrorenen Liste streichen;
   ein automatischer Nachzug ist kein Bugfix, sondern zerstört die
   Schutzwirkung." Nicht geregelt ist der andere Fall: S6b entfernt Code und
   verdrahtet Props neu, die Länge von `WeatherMetricsTab.svelte` **wird** sich
   ändern, und damit verrutscht der **überlebende** fachliche Eintrag `:1323`
   (steht unterhalb aller fünf fallenden Zweige). Für ihn gilt „verschobene
   Zeilennummer ist ein Befund, kein Nachtrag" — was hier aber kein Befund,
   sondern die unvermeidliche Folge des beabsichtigten Umbaus ist.

   **Arbeitsfassung der Regel für S6b** (in `/20-analyse` zu bestätigen, damit
   `/50` sie nicht mitten im GREEN improvisieren muss): entfernte Einträge
   streichen **und** `:1323` im **selben** Commit neu verankern, sodass der Diff
   beide Bewegungen nebeneinander zeigt und die Commit-Nachricht sie begründet.
   Das ist **kein** „Nachziehen" — Nachziehen wäre, die Liste aus dem
   Verzeichnis neu zu erzeugen. **Offene Frage F-S6b-1** (unten).

3. **Stiller Verlust der Reiter-Teilung.** `activeMetricKeys` wird von
   `WeatherMetricsTab` **und** `CorridorEditor(+Mobile)` geschrieben und von
   `AlarmeTab` gelesen. Der diff-basierte Rollback der Nachbar-Module setzt
   voraus, dass der Wizard noch exakt den gesendeten Wert trägt. Wird die
   Wetter-Metrik-Seite einzeln umgestellt, kann diese Verbindung kappen, **ohne
   dass ein Test der umgestellten Datei rot wird**. Hier muss die
   Mutations-Gegenprobe ansetzen.

4. **Doppelquelle als Dauerzustand.** „Wertprop wenn da, sonst `wiz`" ist genau
   das Anti-Muster, das S6 beseitigen soll — nur unter neuem Namen.

5. **SSR-Harness sieht `$effect`-Wirkorte nie** (`generate: 'server'`, kein DOM).
   In S5 brauchten vier Akzeptanzkriterien zwingend den Staging-Browserlauf.
   Jede Zusicherung an einem `$effect`- oder Prop-Verdrahtungs-Wirkort braucht
   eine E2E-Spec, die **zusammen mit** der AC bestellt und in
   `.github/ci_e2e_specs.txt` eingetragen wird.

6. **`e2e_scope` fällt im Worktree bei jedem Commit still auf `docs-only`.**
   `/70-deploy` überspringt dann die gesamte Staging-Validierung. In S5 zweimal
   passiert. Nach **jedem** Commit gegenlesen.

7. **LoC-Limit.** 250 wird sicher überschritten. `workflow.py status` vor der
   Override-Ankündigung fragen — es zählt nur produktive Spec-Dateien, nicht
   Testdateien.

8. **Datenerhalt.** Voll-Spread-Nutzlast bleibt Pflicht (BUG-DATALOSS-Klasse),
   `hubPutQueue` bleibt — sie ist Schutzmechanismus, nicht Altlast, und fällt
   frühestens in S6f, dort nicht ersatzlos.

## Offene Fragen für `/20-analyse`

| # | Frage | Entscheidet |
|---|---|---|
| **F-S6b-1** | Wie wird die 68er-Ratsche gepflegt, wenn ein echter Umbau die Zeilennummer des **überlebenden** fachlichen Eintrags `:1323` verschiebt? Nachtrag mit Belegkette, oder zweite Verankerung über den Quelltext des Zweigs statt über die Zeile? | ob die Ratsche ihre Beweiskraft behält oder stillschweigend nachgezogen wird |
| **F-S6b-2** | Entstehen bei der Umstellung **neue** `context ===`-Stellen an den Mount-Stellen? Der Präzedenzfall verschiebt nachweislich `wiz`-Zugriffe nach oben, aber **keine** `context`-Verzweigung. Zu messen, nicht zu schließen. | ob die Außen-Baseline (3 gesamt, null in `compare*`) hält — und ob AC-2 überhaupt erfüllt ist |
| **F-S6b-3** | Wie bleibt die reiterübergreifende Teilung von `activeMetricKeys` intakt, wenn nur die Wetter-Metrik-Seite umgestellt wird? Mit welcher Mutation weist der Adversary das nach? | Unteilbarkeit der Scheibe — notfalls muss S6b enger oder weiter geschnitten werden |
| **F-S6b-4** | Welche E2E-Specs deckt S6b ab, und welche der heute **nicht** in der Ratsche stehenden Layout-Specs müssen aufgenommen werden? | ob das Regressionsnetz unter dem Kind überhaupt trägt |
| **F-S6b-5** | **Die Scope-Frage, und sie entscheidet die Scheibe.** Arbeitshypothese aus dem Präzedenzfall: Das Kind bekommt Wertprops, die **Vergleich-Hälfte** des Elternteils baut sie aus `wiz`, die **Trip-Hälfte bleibt unberührt** — genau wie bei `CompareOutlookLayoutControls`, wo jede Hälfte der Gabelung ihre eigene Quelle speist (`wiz.*` vs. lokales `$state`). Trägt sie, bleiben die vier Trip-Mounts signaturfrei, weil `wiz?` ohnehin optional ist (`:169`) und die neuen Props vergleich-intern sind. **Gegen `CompareTabs.svelte:1002-1009` zu prüfen:** Geht die Umstellung ohne **neue Pflicht-Prop** an der öffentlichen Schnittstelle von `WeatherMetricsTab`? | ob die Scheibe klein bleibt (nur Vergleich-Hälfte) oder auf sieben Mount-Stellen aufgeht — und damit auch, welche der sechs HERKUNFT-Zweige überhaupt erreichbar sind |
| **F-S6b-6** | Werden `wiz.hourlyMetricKeys` / `wiz.hourlyEnabled` außerhalb dieses Pfads gelesen oder geschrieben (Hydration in `CompareTabs`/`CompareNewEditor`, Bridge)? **Ungeprüft.** | ob das Kind wirklich isoliert umstellbar ist |

## Nebenbefunde (nicht Teil der Scheibe)

- `CompareOutlookLayoutControls.svelte:13-15` — der Kopfkommentar behauptet
  noch „hier wird nur der `wiz`-State mutiert". Das ist seit #1720 S1 falsch und
  widerspricht dem eigenen Kommentar `:34-38`. Wer den Präzedenzfall liest,
  bekommt zuerst die falsche Geschichte. → Sammel-Issue #1199, oder als
  Ersetzung an Ort und Stelle in S6b mitnehmen (Zeilenzahl erhalten!).
- Tote Rückruf-Props `onOutlookCommit` / `onHourlyCommit` (s.o.) — fallen mit S6b.

## Noch nicht gemessen (erledigt — Ergebnisse im Abschnitt `# Analysis`)

> Beide Punkte sind am 2026-09-20 gemessen: die Testbruch-Erhebung ergab
> **einen** betroffenen Test, F-S6b-6 ist beantwortet. Der folgende Text ist
> der Stand vor der Messung.

- Welche der Testdateien unter `shared/__tests__/` und `compare/__tests__/`
  beim Umbau brechen. Stichprobe
  `shared/__tests__/compare_hourly_layout_controls_structure.test.ts`: prüft
  `groupCompareCatalog`, Katalog-Prop-Weitergabe, Toggle-Existenz und die
  Einmaligkeit von `WeatherV2Reihenfolge` — **keine** Assertion, die `wiz`
  festschreibt. Die übrigen sind ungelesen.
- F-S6b-6 (Hydration der beiden Hourly-Felder).

## Bezüge

- `docs/context/rework-2276-s6-rueckbau.md` — S6-Gesamtkontext + Analyse F1–F6
- `docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md` — Ratschen-Vertrag, Zweig-Anhang mit Kategorien
- `docs/specs/modules/rework_2276_s4_wetter_metriken.md` — Speicherweg derselben Fläche (S4)
- `docs/reference/gates_und_ratschen.md` — Prüfdatum der Ratsche: 2026-12-19

---

# Analysis

> Ergebnis von `/20-analyse` am **2026-09-20**, Basis `a1007c11`. Alle Zahlen
> sind an der Arbeitskopie gemessen, nicht aus dem S6-Gesamtkontext
> übernommen. Wo eine Messung eine Annahme des Kontext-Teils widerlegt, steht
> das ausdrücklich dabei.

## Type

**Feature** (Refactoring ohne Verhaltensänderung), Scheibe eines Epics.

## Die Zielzahl: 68 → 67

Die Kontext-Fassung nannte eine Spanne von 66–62. **Beide Enden sind
widerlegt.** Zweig für Zweig, mit dem jeweiligen Mechanismus:

| # | Fundstelle | fällt in S6b? | Mechanismus / Grund |
|---|---|---|---|
| 23 | `WeatherMetricsTab.svelte:545` | **nein** | Trip-seitige Vorbefüllung (`context === 'route' && trip && …`). Hängt am Trip-Ladepfad, nicht am Eigentum von `wiz`. Fällt nur mit der Trip-Hälfte. |
| 24 | `WeatherMetricsTab.svelte:560` | **nein** | Trip-seitiger Katalog-Fetch `load()`. Zwillingsstelle zu #27 — siehe dort. |
| 26 | `WeatherMetricsTab.svelte:589` | **nein** | `context === 'vergleich' && !smsSymbols` ist ein **Ladepfad**-Zweig, kein Eigentums-Zweig: im Trip lädt `load()` dieselben Kürzel. Ein herkunftsfreier Guard (`!smsSymbols`) würde im Trip einen zweiten Abruf auslösen. Rückbau erfordert die Vereinheitlichung beider Ladepfade — andere Scheibe. |
| 27 | `WeatherMetricsTab.svelte:602` | **nein** | `context === 'vergleich' && Object.keys(catalog).length === 0` füllt `catalog` aus `/api/metrics`; das trip-seitige Gegenstück #24 füllt dasselbe Feld aus `load()`. Die beiden sind ein **Paar**. Eines allein zu entfernen ändert Verhalten; beide zu vereinheitlichen fasst die Trip-Hälfte an. |
| 28 | `WeatherMetricsTab.svelte:1273` | **JA** | `if (context !== 'vergleich' \|\| !wiz \|\| !vergleichSpeicherung) return;` — `vergleichSpeicherung` ist ausschließlich über das Prädikat #67 entstanden und ist `null`, sobald eine seiner Bedingungen fehlt. Der Guard prüft die Kontext-Entscheidung damit ein **zweites Mal, stromabwärts**. `if (!vergleichSpeicherung) return;` ist semantisch identisch. Das ist Totcode der S6a-Klasse, keine Aufhebung einer Entscheidung. |
| 67 | `weatherMetricsCompareSave.ts:534` | **nein — bewusst** | siehe „Warum #67 bleibt" |
| 29 | `WeatherMetricsTab.svelte:1323` | nein (FACHLICH) | Markup-Gabelung, bleibt laut Kategorisierung |
| 68/69 | `weatherMetricsTabSections.ts:72/73` | nein (FACHLICH) | bleiben |

**68 − 1 = 67.**

### Warum #67 bleibt (🔴 der Befund, der die Scheibe umschreibt)

Die Arbeitshypothese des Kontext-Teils war: `!!preset && !!saveController`
unterscheidet den Hub schon allein, also kann `context === 'vergleich'` aus dem
Prädikat fallen. **Die Messung stützt die Prämisse und widerlegt trotzdem die
Folgerung:**

- Prämisse bestätigt: von sieben Mount-Stellen übergibt **nur**
  `compare/CompareTabs.svelte:1005` ein `preset`. Kein Trip-Mount tut es
  (`TripTabs:224`, `TripEditView:201`, `TripNewEditor:881/1113` — alle
  nachgelesen).
- **Aber:** `weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts:74-82`
  sichert als **freigegebene AC-13 aus S4** genau den Gegenfall zu: mit
  *vollständigen* Props und `context: 'route'` muss das Prädikat `false`
  liefern — Testname wörtlich: „die Kontext-Prüfung allein entscheidet".
  `docs/specs/modules/rework_2276_s4_wetter_metriken.md:296-305` nennt dazu als
  Mutations-Gegenprobe: „Kontext-Prüfung entfernen ⇒ Test rot".

Die Kontext-Prüfung im Prädikat ist also **keine Redundanz, sondern eine
bewusst gesetzte zweite Barriere** gegen kontextfremde Speicherung — dieselbe
Risikoklasse, die CLAUDE.md unter Mandanten-/Datenisolation führt. Sie
abzuräumen hieße, eine freigegebene Entscheidung für einen einzigen
Ratschen-Punkt still zurückzunehmen. **S6b tut das nicht.** Wer sie später
aufheben will, braucht ein Nachfolge-ADR bzw. eine ersetzende AC, keinen
Refactoring-Nebeneffekt.

🔴 **Zwei getrennte Wirkungen, zwei getrennte ACs.** Die Umstellung des Kindes
auf Wertprops bewegt die Ratsche **um null** (das Kind hat null
`context`-Zweige). Der Rückbau von #28 bewegt sie um eins und wirkt unabhängig
von der Umstellung. Eine AC, die beides verknüpft („die Umstellung senkt die
Ratsche auf 67"), ist falsch und bricht im Adversary.

## Scheiben-Zuschnitt (Entscheidung)

**S6b = Kind auf Wertprops + Rückbau der stromabwärts liegenden Redundanz.
`WeatherMetricsTab` behält `wiz`.**

Begründung: `WeatherMetricsTab` hält ~30 `wiz`-Zugriffe über **fünf** Belange —
`activeMetricKeys` (`:1096-1122`, `:1168`, `:1184-1187`), `outlook*`
(`:1226-1238`, `:1496-1502`), `officialAlertsEnabled` (`:1247-1248`, `:1512`),
`dayWindow*` (`:1448-1451`) und den Speicherweg (`:1261-1279`). Alle fünf
zugleich zu heben ist keine Scheibe, sondern das Epic. Der Präzedenzfall
`CompareOutlookLayoutControls` (#1720 S1) hat genau denselben Schnitt gefahren
und ist seitdem live.

Die Umstellung ist **signaturneutral nach außen**: alle Wertprops sind
compare-intern (das Elternteil baut sie aus dem eigenen `wiz`), keine neue
Pflicht-Prop an `WeatherMetricsTab`. Die vier Trip-Mounts bleiben damit
unangetastet — der 🔴-Hinweis aus dem Kontext-Teil („jede Signaturänderung
berührt auch die vier Trip-Mounts") entschärft sich unter diesem Zuschnitt.

## Antworten auf die offenen Fragen

**F-S6b-1 — Ratschen-Pflege bei verschobenem `:1323`: stellt sich nicht.**
Der Ratschen-Test (`context_herkunft_zweige_eingefroren.test.ts:160-231`)
vergleicht reine `Datei:Zeile`-Mengen ohne Quelltext-Anker — eine Verschiebung
**wäre** ein Problem. Unter diesem Zuschnitt verschiebt sich aber nichts:
`:1261` und `:1273` sind je **eine Zeile → eine Zeile** (Ersetzung an Ort und
Stelle, S6a-Vertrag), der Mount-Block `:1466-1476` liegt **unterhalb** von
`:1323` und kann ihn nicht bewegen, und in `weatherMetricsCompareSave.ts` ist
`:534` der **einzige** eingefrorene Eintrag der Datei (nachgezählt) — dort ist
Längenänderung folgenlos. **Keine neue Regel, keine zweite Verankerung.** Der
Kommentarblock `:1255-1259` wird, falls er angefasst wird, zeilentreu ersetzt.

**F-S6b-2 — neue `context`-Stellen außerhalb `shared/`: dürfen nicht
entstehen; Baseline ist reproduzierbar.** Gemessener Befehl (aus der
Repo-Wurzel, Ergebnis heute **3**, alle in
`lib/components/organisms/MetricsEditorContextBar.svelte:53/60/94`, **null** in
`compare/` und `compare-new/`):

```bash
grep -rn 'context ===\|context !==' frontend/src \
  --include='*.svelte' --include='*.ts' \
  | grep -v '/shared/' | grep -v __tests__ | grep -vE ':\s*(\*|//|/\*)'
```

Weil das Kind compare-intern parametrisiert wird und das Elternteil seine
Werte aus dem eigenen `wiz` baut, entsteht an den Mount-Stellen **keine**
Herkunfts-Abfrage. Die AC formuliert das als Zusicherung an genau diesem
Befehl: null Treffer in `compare/` und `compare-new/`.

**F-S6b-3 — `activeMetricKeys`-Teilung: unter diesem Zuschnitt nicht
berührt.** Der Mount `WeatherMetricsTab.svelte:1473-1476` übergibt dem Kind nur
`{wiz} catalog={compareCatalog} smsSymbols={metricSymbols}` — **kein**
`grundauswahl`, anders als der Outlook-Mount `:1496-1502`. Das Kind liest und
schreibt ausschließlich `hourlyMetricKeys` und `hourlyEnabled`. Die
reiterübergreifende Teilung von `activeMetricKeys` (Risiko 3) liegt damit
außerhalb der Scheibe; es wird **keine** Mutation dafür erfunden.

**F-S6b-4 — E2E: genau EINE neue Spec, die fünf Altbestände bleiben außen
vor.** Belegt, nicht geschätzt: `compare-hourly-metric-order:411` trägt
`page.waitForTimeout` (Filter-A-Verstoß), `compare-metric-order` ist in
**beiden** Fällen rot (AC-13-Vorbedingung), `compare-layout-tab-dissolution` in
2 von 6 — alles gemessen und in der CI-Positivliste dokumentiert, Buchung in
#1196. Präzedenz S2/S3/S4/S5 ist ausdrücklich: **nur die eine neue, eigene Spec
der Scheibe wird geratscht.** S6b bestellt daher eine neue E2E-Spec für die
Wertprop-Verdrahtung des Stundenverlaufs (Risiko 5: der SSR-Harness sieht
`$effect`- und Prop-Wirkorte nicht) und trägt **nur diese** mit
Filter-B-Beleg in die CI-Positivliste ein.

**F-S6b-5 — Scope: Vergleich-Hälfte, und zwar nur das Kind.** Siehe
„Scheiben-Zuschnitt". Keine neue Pflicht-Prop, vier Trip-Mounts unberührt.

**F-S6b-6 — Hydration der beiden Hourly-Felder: geklärt, spricht für den
Zuschnitt.** `compare/CompareTabs.svelte:501-502` hydratisiert
`hourlyMetricKeys`/`hourlyEnabled` in **derselben** Funktion
(`hydrateLayoutTab`), in der `:503-506` die bereits umgestellten
`outlook*`-Felder hydratisiert werden. `compare-new/CompareNewEditor.svelte`
hydratisiert sie **nicht**. Beide Felder sind `$state`-Felder von
`CompareWizardState` (`compareWizardState.svelte.ts:46/72`) und werden von den
Speicher-/Bridge-Modulen gelesen. **Folge:** Die Felder bleiben im `wiz`; nur
die Bedienfläche wird davon entkoppelt — exakt die Lage, die beim
Outlook-Präzedenzfall vorlag und dort getragen hat.

## Affected Files

| Datei | Change Type | Beschreibung |
|---|---|---|
| `shared/CompareHourlyLayoutControls.svelte` | MODIFY | `wiz` raus, Wertprops + Rückrufe rein (`metricKeys`, `enabled`, `onMetricKeys`, `onEnabledChange`); tote Prop `onHourlyCommit:59` entfällt |
| `shared/WeatherMetricsTab.svelte` | MODIFY | Mount-Block `:1466-1476` liefert die Wertprops aus `wiz` (Adapter analog `:1226-1238`); `$effect`-Guard `:1273` auf `!vergleichSpeicherung` verkürzt (zeilentreu); Prädikat-Aufruf `:1261` unverändert |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | `WeatherMetricsTab.svelte:1273` **bewusst** aus der eingefrorenen Liste streichen, Soll-Anzahl 68 → 67, Begründung im Commit |
| `frontend/e2e/<neue Spec>.spec.ts` | CREATE | Wertprop-Verdrahtung des Stundenverlaufs im Browser (Risiko 5) |
| CI-Positivliste `ci_e2e_specs.txt` | MODIFY | Aufnahme **nur** der neuen Spec, mit Filter-B-Beleg |
| `shared/__tests__/metricKuerzelLegende.test.ts` | MODIFY | Zeile 1084-1093: einzige `wiz`-Fixture des Kindes, auf die neuen Wertprops umstellen (gemessen, siehe Testbruch-Erhebung) |
| `docs/specs/modules/rework_2276_s6b_*.md` | CREATE | Spec (Phase 3) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Ratschen-Zahl 68 → 67 nachführen (dokumentarisch) |

## Scope Assessment

- Produktive Dateien: **2 Svelte** + 1 Ratschen-Test + 1 CI-Liste
- Geschätztes LoC-Delta: **+120 / −60** (Kind ~60 Zeilen Umbau, Elternteil
  ~30 Adapter/Mount, Ratsche 2)
- **LoC-Limit:** wird voraussichtlich gerissen. Vor der Override-Ankündigung
  `workflow.py status` fragen (es zählt nur produktive Spec-Dateien).
- **Risiko: MITTEL.** Nach unten: exakter, lebender Präzedenzfall im selben
  Block derselben Datei; kein Speicherweg, kein Datenmodell, keine
  Mandantentrennung berührt; keine Signaturänderung nach außen. Nach oben: die
  Wirkorte sind `$effect`/Prop-Verdrahtung, die der SSR-Harness nicht sieht —
  ohne die bestellte E2E-Spec wäre die Scheibe nur scheinbar bewiesen.

## Technische Umsetzung (Empfehlung)

1. `CompareHourlyLayoutControls` nach dem Muster von
   `CompareOutlookLayoutControls` auf Wertprops heben; die beiden Kunstgriffe
   des Präzedenzfalls übernehmen: **„Prop da → Bedienelement da"** statt
   Herkunfts-Zweig und die Vokabular-Normalisierung im Inneren.
2. Im Elternteil die zwei Adapterfunktionen ergänzen (Muster `:1226-1238`) und
   den Mount-Block `:1466-1476` auf die Bauform des Outlook-Blocks
   `:1487-1505` bringen. Das `&& wiz` im `{#if}` wird zum Prop-da-Guard.
3. Erst danach, als **eigener** Schritt mit eigener AC: `:1273` verkürzen und
   die Ratsche von 68 auf 67 nachführen — im **selben** Commit, mit
   Begründung in der Nachricht (Streichen eines beseitigten Eintrags ist
   vorgesehen, automatisches Nachziehen bleibt verboten,
   `docs/reference/gates_und_ratschen.md:326-330`).

**Mutations-Gegenprobe (Pflicht), Vorschlag an den Adversary:**
- Rückruf `onEnabledChange` im Mount weglassen ⇒ der Ein/Aus-Schalter des
  Stundenverlaufs verschwindet. Fängt das kein Test, ist die
  Prop-da-Zusicherung unbewacht.
- `:1273` auf `if (false) return;` verfälschen ⇒ muss rot werden (die
  Zusicherung wirkt im Speicherpfad, nicht im Guard-Quelltext).
- Einen Eintrag aus der 67er-Liste entfernen ⇒ nur die Ratsche darf rot
  werden, kein anderer Test (Rückdreh-Gegenprobe, S6a-Muster).

## Testbruch-Erhebung (Ergebnis, nachgetragen 2026-09-20)

Erhoben über `shared/__tests__/` (47 Dateien), `compare/__tests__/` (56) und
`compare-new/__tests__/` (2) — **105 Dateien**, davon unter diesem Zuschnitt
**eine** betroffen. Die genannten Zeilen sind eigenhändig gegengelesen.

| Testdatei | betroffen? | Befund |
|---|---|---|
| `metricKuerzelLegende.test.ts:1084-1093` | **JA** | einzige Stelle, die eine `wiz`-Fixture für das Kind baut (`wiz: { hourlyMetricKeys: null }`). Muss auf die neuen Wertprops umgestellt werden. |
| `weatherMetricsTabSharing.test.ts:67-70` | **nein** | prüft per Regex `wiz\|?\s*:\s*CompareWizardState` in **`WeatherMetricsTab`**. Bleibt grün, **weil das Elternteil `wiz` behält** — unter dem weiteren Zuschnitt wäre dieser Test gebrochen. |
| `versand_speicherung_nur_im_vergleich_hub.test.ts` | nein | betrifft den Versand-Reiter, nicht diese Fläche |
| `versand_tab_meldet_aenderungen_reaktiv.test.ts` | nein | dito |
| `totcode_rueckbau_speicherweg.test.ts` (compare) | nein | prüft die `CompareWizardState`-Klasse selbst; die bleibt |
| `compare_hourly_layout_controls_structure.test.ts` | nein | keine `wiz`-Assertion (gegengelesen) |

🔴 **Zwei AST-Wächter über dem Mount-Block — Randbedingung für `/50`, vom
Agenten nicht als solche benannt:**

- `compare_hourly_layout_controls_structure.test.ts:458-474` fordert **genau
  eine** Einbettung von `CompareHourlyLayoutControls` in `WeatherMetricsTab`
  **und** das Attribut `compareCatalog`.
- `weather_metrics_tab_compare_catalog_fetch.test.ts:196-210` fordert
  ebenfalls das `catalog`-Attribut am Mount.

Der Umbau des Mount-Blocks `:1466-1476` muss also `catalog={compareCatalog}`
erhalten und darf keine zweite Einbettung erzeugen. Beide Wächter bleiben
grün, wenn die Adapter-Props **zusätzlich** treten — was der Outlook-Mount
`:1496-1505` genau so vormacht.

**Der Testbruch-Befund stützt den Zuschnitt zusätzlich:** unter dem weiteren
Schnitt (Elternteil mit umgestellt) wären **vier** Tests gebrochen, darunter
`weatherMetricsTabSharing.test.ts`, das die Prop-Signatur von
`WeatherMetricsTab` festschreibt. Unter dem gewählten Schnitt ist es **einer**.

## `activeMetricKeys`-Aufrufgraph (Ergebnis, nachgetragen 2026-09-20)

**F-S6b-3 bestätigt: `CompareHourlyLayoutControls` fasst `activeMetricKeys`
nirgends an.** Die Komponente berührt ausschließlich `hourlyMetricKeys`
(`:82`, `:97-98`, `:176`) und `hourlyEnabled` (`:108`, `:194`).

Der Graph zur Einordnung (nicht Teil der Scheibe):

| Rolle | Ort |
|---|---|
| SCHREIBEN | `WeatherMetricsTab.svelte:1098` · `CorridorEditor.svelte:225` · `CorridorEditorMobile.svelte:200` · `CompareTabs.svelte:343/457` (Hydration) · `compareHubWizardBridge.ts:438` |
| LESEN | `AlarmeTab.svelte:188/201` · `wertebereicheVergleichSpeicherung.ts:47/71` · `weatherMetricsCompareSave.ts:321-322` |
| Diff-/Rollback-Gate | `wertebereicheVergleichSpeicherung.ts:115` |
| **kein Zugriff** | **`CompareHourlyLayoutControls.svelte`** |

**Folge:** Risiko 3 („stiller Verlust der Reiter-Teilung") trifft diese Scheibe
nicht. Es wird dafür **keine** Mutation erfunden; der Adversary prüft
stattdessen die drei oben genannten Mutationen.

## Keine Fragen an den PO

Alle sechs offenen Fragen sind technisch und in dieser Phase entschieden. Es
geht keine davon an Henning.

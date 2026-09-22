# Context: rework-2276-s6c-alarme

**Issue:** #2276 (Epic #2345) · **Scheibe:** S6c — Alarme-Fläche des Ortsvergleichs auf Wertprops
**Erhoben:** 2026-09-21 · Basis `8207c157` (== `origin/main`, S6b live)

## Request Summary

Die geteilte Alarme-Fläche (`AlarmeTab.svelte`, `context="route"|"vergleich"`) liest und
schreibt im Vergleichs-Zweig direkt auf dem Wizard-Store `wiz`. S6c stellt diese Fläche —
nach dem in S6b erprobten Muster — auf explizite Wertprops plus Callbacks um; der
`wiz`-Zugriff verschwindet dabei nicht, er **wandert zum Elternteil hoch**. Verhalten bleibt
unverändert.

## Ticket-Zusicherungen (Fassung #2276)

- **AC-1** ist wörtlich am Alarme-Reiter formuliert: Änderung im Hub ⇒ der Organismus
  persistiert selbst (ein PUT, `SaveIndicator`), ohne `compare-wizard-state`-Context.
- **AC-2** (Zahl der `context ===`-Zweige) ist in der Ticket-Fassung unerfüllbar; prüfbare
  Neufassung seit S6a: „keine HERKUNFT-Zweige", Darstellung/Fachlogik bleiben.
- **AC-3** Zwei Reiter kurz nacheinander ⇒ keine Änderung geht verloren.
- **AC-4** `compareHubWizardBridge` ohne produktiven Importeur (Bilanz erst in S6f).

## Die vier Einbettungen — drei im Vergleichs-Zweig

| Mount | Datei:Zeile | Fläche | Props heute | Speicherweg aktiv? |
|---|---|---|---|---|
| (A) Route | `trip-detail/AlarmeScheduleTab.svelte:60-69` | Trip-Detail | trip-basiert, kein `wiz` | ja (Trip-Weg) |
| (B) Hub | `compare/CompareTabs.svelte:1044-1054` | `/compare/[id]` | `wiz`, `catalog`, `preset`, `saveController`, `enqueueHubWrite`, `onCompareUpdate` | **ja — einziger** |
| (C) Anlegen Desktop | `compare-new/CompareNewEditor.svelte:396` | `/compare/new` | nur `wiz`, `catalog` | nein |
| (D) Anlegen Mobil | `compare-new/CompareNewEditor.svelte:487` | `/compare/new` | nur `wiz`, `catalog` | nein |

**Kernbefund für den Schnitt:** Die Verdrahtung ist dreifach, der Speicherweg einfach.
(C)/(D) übergeben weder `preset` noch `saveController`; der Guard
`AlarmeTab.svelte:366-367` lässt `erstelleAlarmeVergleichSpeicherung` dort nie entstehen,
der Save-`$effect` (`:378-384`) bricht sofort ab. In (C)/(D) kommt `wiz` aus
`getContext('compare-wizard-state')` (`CompareNewEditor.svelte:63`), in (B) aus einer
lokalen Instanz (`CompareTabs.svelte:325`). Persistenz der Anlege-Seite läuft gesammelt
über `wiz.saveNewPreset()`, ausserhalb von `AlarmeTab`.

## `wiz`-Zugriffe in `AlarmeTab.svelte` — alle im Baustein selbst

Kein Kind-Baustein (`ChannelToggle`, `AlertMetricLevelTable`, `AlertChannelPicker`,
`TelegramKurzstilToggle`, `AlertCooldownCard`, `AlertQuietHoursCard`, `VTAlertSample`,
`AlertPreviewCard`) kennt `wiz` — sie bekommen bereits primitive Werte. Die Umstellung
betrifft also **den Elternteil-Übergang**, nicht die Blätter.

| Feld | Lesen | Schreiben |
|---|---|---|
| `officialWarningsEnabled` | :171 | :175 |
| `activeMetricKeys` | :188, :201 | — |
| `metricAlertLevels` | :217 | :222 |
| `sendTelegram`/`sendSms`/`sendPremiumSms` | :245-248 | :255, :256, :257 |
| `channelThresholds` | :281 | :286-296 |
| `telegramStyle` | :450 | :453 |
| `alertCooldownMinutes` | `bind:` :460 | `bind:` :460 |
| `alertQuietFrom`/`alertQuietTo` | `bind:` :468 | `bind:` :468 |
| `radarAlertEnabled` | :475 | :477 |
| Snapshot (ganzes Objekt) | :382 (Tracking im `$effect`) | — |

**Zwei `bind:`-Stellen** (:460 Cooldown, :468 Quiet-Hours) schreiben zweiwegig direkt auf
`wiz!` — sie brauchen bei der Umstellung einen Callback statt `bind:`, sonst bleibt ein
versteckter Schreibweg zurück.

### HERKUNFT-Zweige im Baustein (Stand heute, am Zählbefehl der Ratsche gemessen)

**18 Treffer** in `AlarmeTab.svelte`:
`:171, :174, :186, :199, :216, :221, :243, :253, :280, :285, :345, :367, :379, :424, :443,
:459, :467, :482` — deckungsgleich mit der eingefrorenen Liste (siehe unten). Der Gate des
Speicherwegs steht auf **`:367`** (nicht `:366`) — das ist die Zeile, die im Zweifel
wiederhergestellt werden muss. `alarmeTabSections(context)` (`:152`) ist **kein** Treffer des
Zählbefehls; die drei Zweige dieser Funktion stehen in
`alarme-tab/alarmeTabSections.ts:27, :38, :42` und steuern Reihenfolge/Sichtbarkeit der
Abschnitte (fachlich, bleibt).

## Schreibweg im Hub (Mount B)

`AlarmeTab.svelte:366` baut beim Mount `erstelleAlarmeVergleichSpeicherung(...)`
(`shared/alarmeVergleichSpeicherung.ts:185-235`) · `$effect` `:378-384` liest
`alarmSnapshotAus(wiz)` und meldet Änderungen · `aenderungMelden` vergleicht gegen
`zuletztGespeichert` und ruft `saveController.schedule(saveFn)` · `saveFn` läuft durch
`enqueueHubWrite` = `hubPutQueue.enqueue` (`compareHubWizardBridge.ts:340-352`) ·
Payload über `buildComparePresetSavePayload` (`compare/compareEditorSave.ts`) ·
`client.put` · Erfolg ⇒ `onCompareUpdate` ⇒ `currentPreset = updated` · Fehler ≠ 412 ⇒
`rollbackAlarmSnapshot` (diff-basiert, schützt Nachbar-Reiter). Baseline stammt aus
`hydrateAlarmFieldsFromPreset` (`compareHubWizardBridge.ts:408-444`), aufgerufen vor dem
Mount (`CompareTabs.svelte:421`, Gate `alarmeHydrated` `:1041`).

Die Schreibschlange `hubPutQueue` **bleibt** — sie hält den Payload-Bau im `enqueue()`-Closure;
ohne sie bauen zwei PUTs aus demselben stalen `currentPreset` und der zweite bekommt
**200 OK mit veraltetem Body** (kein 412, stiller Datenverlust).

## Das S6b-Muster (Präzedenz, live seit heute)

Kind `CompareHourlyLayoutControls.svelte` wurde wertprop-rein: `metricKeys`/`enabled` rein,
`onMetricKeys`/`onEnabledChange` raus, tote Prop `onHourlyCommit` entfallen. Regel
**„Prop da → Bedienelement da"**: der Schalter rendert nur unter `{#if onEnabledChange}`
(Vorbild `CompareOutlookLayoutControls`, #1720 S1). Der Elternteil reicht die Werte im
Mount-Block über **inline** Pfeilfunktions-Adapter aus `wiz` durch
(`WeatherMetricsTab.svelte:1466-1476`) — reine Prop-Durchreichung beim Rendern, kein
`$effect`. Benannte Adapter-Funktionen wären zeilenverschiebend und deshalb bewusst
vermieden (Zeilenzahl-Vertrag der Ratsche).

**Design-Entscheidung, die S6c übernimmt:** `wiz`→Wertprops und HERKUNFT-Abbau sind **zwei
getrennte Wirkungen, die nie gekoppelt werden**. S6b hat genau **einen** Ratschen-Eintrag
fallen lassen (`WeatherMetricsTab.svelte:1273`, Guard zeilentreu von
`if (context !== 'vergleich' || !wiz || !vergleichSpeicherung) return;` auf
`if (!vergleichSpeicherung) return;` verkürzt) und das im Commit begründet.

### Neues Werkzeug aus S6b-F001: Wirkort-Prüfung im Kern

Der Adversary zeigte, dass der SSR-Prüfstand `$effect`-Rückrufe verwarf (`u.$effect = () => {}`)
und die E2E-Spec nur im Hub lief, wo `vergleichSpeicherung` strukturell immer wahr ist — die
Mutation `if (false) return;` war dort **unbeobachtbar**. Seither sammelt
`svelteInstanzPruefstand.ts:188` (`effekteVon()`) die Effekt-Rückrufe ein, und
`compare_stundenverlauf_wertprops.test.ts` (ab ~:410) führt den Effekt-Rumpf an den
**negativen** Wirkorten wirklich aus: Trip (`context: 'route'`) und `/compare/new`
(`preset: null`, `saveController: null`), plus positive Gegenprobe.
⇒ **Für S6c steht dieses Werkzeug bereit** — ein Wirkort-Guard lässt sich damit im Kern
bewachen, ohne auf eine E2E-Spec am schwer erreichbaren Mount angewiesen zu sein.

## Ratschen-Lage: 21 der 67 eingefrorenen Zeilen liegen in der Alarme-Fläche

`shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`, `EINGEFROREN_SOLL_ANZAHL = 67`
(`:163`). Zählbefehl (`:61-64`, wörtlich):

```
grep -rn 'context ===\|context !==' . --include='*.svelte' --include='*.ts' | grep -v __tests__ | grep -vE ':\s*(\*|//|/\*)'
```

Alarme-Einträge: `AlarmeTab.svelte:171, 174, 186, 199, 216, 221, 243, 253, 280, 285, 345,
367, 379, 424, 443, 459, 467, 482` (18) · `alarme-tab/alarmeTabSections.ts:27, 38, 42` (3).

**Folge für den Schnitt:** Die Alarme-Fläche ist ratschenseitig um ein Vielfaches grösser als
die S6b-Kind-Fläche. Jede Skriptzeile, die in `AlarmeTab.svelte` oberhalb eines eingefrorenen
Eintrags hinzukommt, verschiebt dessen Zeilennummer und macht die Ratsche rot. In der Spec
muss deshalb vorab festgelegt werden, **wie viele Einträge S6c bewusst fallen lässt** — alles
andere ist Zeilenzahl wiederherstellen, nicht Liste nachziehen.

## Prüfstrecken-Abdeckung heute

| Prüfstrecke | Mount / Route | in CI-Ampel (`ci_e2e_specs.txt`)? |
|---|---|---|
| `compare-alarme-speichert-selbst.spec.ts` | Hub `/compare/[id]` | **ja** (`:227`) |
| `compare-alarm-config.spec.ts` | Hub `/compare/[id]` | nein — wegen `waitForTimeout` bewusst ausgeschlossen (#1196) |
| `compare-flow-navigation.spec.ts` | Anlegen `/compare/new`, klickt Alarme-Reiter | nein — nicht in der Positivliste |
| `compare-neu-kanal-anlegen.staging.spec.ts` | Anlegen `/compare/new` | nein — `.staging.spec.ts` ist strukturell aus dem Kandidatenpool |
| `speicherung-ueberlebt-neuladen.spec.ts`, `versand-tab.spec.ts` | Trip `/trips/[id]` | ja — aber Trip-Zusicherungen, nicht Compare |
| ~19 Kern-Tests `shared/__tests__/alarme_*`, `compare_*alarme*` | kein DOM, kein `$effect` | laufen immer |

Aus den Kern-Tests sind drei für S6c besonders zu prüfen — bei jedem ist in `/20-analyse` die
Frage zu stellen, ob er nach der Umstellung **rot**, **grün** oder **vakuum-grün** wird:
`alarme_tab_laedt_keine_compare_klebeschicht.test.ts` (nahe an AC-4: importiert der Baustein
die Klebeschicht?) · `alarme_save_single_writer.test.ts` (genau ein Schreiber) ·
`alarme_vergleich_speichert_selbst.test.ts` (der Speicherweg, den S6c anfasst).

🔴 **Der Anlege-Mount ist in der CI-Ampel unbewacht.** Keine gelistete Spec berührt
`/compare/new` im Alarme-Reiter. Eine S6c-Prüfstrecke, die nur den Hub durchläuft, würde
den F001-Blindspot exakt wiederholen.

## Risiken & Beachtenswertes

- **Mount-Falle (aus S6b gelernt):** Eine Prüfstrecke, die nur den Hub durchläuft, kann eine
  Zusicherung, die am Anlege-Mount wirkt, strukturell nie bewachen — eine Mutation dort ist
  unbeobachtbar. Bei drei Mounts ist die falsche Mount-Wahl der Normalfall, nicht der Rand.
- **SSR-Harness beweist keine Verdrahtung:** Die Unit-Harness ist SSR-only (`generate: 'server'`,
  kein DOM); reaktive Effekte laufen dort nie. Jeder `$effect`-Wirkort braucht eine E2E-Spec.
- **Ratsche nicht nachziehen:** Wird `context_herkunft_zweige_eingefroren.test.ts` rot, ist das
  die Messung. Entweder ein Eintrag fiel bewusst (streichen + im Commit begründen) oder eine
  Zeilennummer ist verrutscht (Zeilenzahl der Quelldatei wiederherstellen).
- **`e2e_scope` im Worktree** fällt bei jedem Commit still auf `docs-only` zurück — nach jedem
  Commit gegenlesen, sonst überspringt `/70-deploy` die Staging-Validierung.
- **Datenerhalt:** Read-Modify-Write bleibt Pflicht; der Voll-Spread-Payload darf nicht durch
  einen Minimal-Body ersetzt werden.

---

# Analysis

**Erstellt:** 2026-09-21 · Phase 2 · Basis `8207c157`

## Type

**Feature / Rework** (verhaltensneutraler Umbau) — kein Bug. Die Alarme-Fläche des
Ortsvergleichs wird vom Wizard-Store `wiz` auf explizite Wertprops + Rückrufe umgestellt,
nach dem in S6b erprobten Muster. AC-1 des Tickets (Organismus persistiert selbst) ist
**seit S2 live** und durch `compare-alarme-speichert-selbst.spec.ts` (in der CI-Ampel,
`ci_e2e_specs.txt:227`) bewacht — S6c zahlt auf **AC-2** (HERKUNFT-Abbau) und **AC-4**
(Klebeschicht ohne Importeur) ein.

## Geklärte Vorfragen (in dieser Phase gemessen, nicht angenommen)

1. **Die beiden `bind:`-Kinder sind `$bindable`-only.** `AlertCooldownCard.svelte:5`
   (`cooldown_minutes = $bindable(...)`) und `AlertQuietHoursCard.svelte:10-11`
   (`quiet_from`/`quiet_to = $bindable(...)`) bieten **keinen** Änderungs-Rückruf.
   **Folge:** Ohne Gegenmaßnahme würde S6c in die Kind-Bausteine und deren Tests wachsen.
   **Ausweg, der das verhindert:** Svelte ist auf `^5.55.2` (`frontend/package.json:27`),
   damit sind **Funktions-Bindungen** verfügbar (`bind:x={() => wert, (v) => rueckruf(v)}`,
   Svelte >= 5.9). Die Kinder bleiben damit **unverändert**; der Schnitt bleibt in
   `AlarmeTab.svelte` + den drei Mount-Blöcken. Der Trip-Zweig (`:462`, `:470`) bindet an
   lokale `$state`-Variablen und wird nicht angefasst.
2. **Die Kategorisierung der 18 Ratschen-Einträge steht bereits im S6a-Anhang**
   (`docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md:343-360`) — 14x HERKUNFT,
   `:199` und `:482` FACHLICH, `:424`/`:443` waren unzugeordnet und sind hier am Quelltext
   nachgetragen (siehe Schicksals-Tabelle).

## Affected Files (with changes)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | 13 `wiz`-Felder an 21 Stellen -> Wertprops + Rückrufe; 14 HERKUNFT-Zweige fallen; 2 `bind:` -> Funktions-Bindung; neue Prop `zonenBezug` |
| `frontend/src/lib/components/compare/alarmePropsAus.ts` | CREATE | Eine Stelle, die aus `wiz` das Prop-Bündel (Werte + Rückrufe) baut — von allen drei Vergleichs-Mounts benutzt |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount (B) `:1044-1054` auf das Prop-Bündel |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Mounts (C) `:396` und (D) `:487` auf dasselbe Prop-Bündel — **sonst verlieren sie ihre Bedienelemente** |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Ratsche 67 -> 53; 14 Einträge gestrichen, 4 Überlebende auf neue Zeilennummern |
| `frontend/src/lib/components/shared/__tests__/compare_alarme_wertprops.test.ts` | CREATE | Wirkort-Guard im Kern über `effekteVon()` + Prop-Verdrahtung aller drei Mounts (AST) |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_laedt_keine_compare_klebeschicht.test.ts` | MODIFY | Saat auf die neue Prop-Form; Gegenprobe ergänzen (Bridge-Import einschleusen => muss rot werden) |
| `frontend/e2e/compare-alarme-wertprops.spec.ts` | CREATE | Verhaltensgleichheit im Browser am Hub-Mount |
| `.github/ci_e2e_specs.txt` | MODIFY | Genau **eine** neue Spec aufnehmen (Scheiben-Disziplin S2/S3/S4/S5/S6b), Schwellen `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` exakt nachziehen |

Zu prüfen, ob Saat-Anpassung nötig (alle fahren den Vergleichs-Pfad):
`alarme_vergleich_flush_beim_reiterwechsel.test.ts`, `alarme_vergleich_kein_zurueckschreiben.test.ts`,
`alarme_vergleich_konflikt_nochmal_speichern.test.ts`, `alarme_vergleich_ruecknahme_waehrend_put.test.ts`,
`compare_hub_alarme_bridge.test.ts`, `compare_alarme_channel_threshold_save.test.ts`,
`alarme_tab_catalog_prop_structure.test.ts`, `alarme_tab_unalertable_hint_structure.test.ts`.

## Ratsche: Schicksal je Eintrag (Kern der Spec)

**Die S6b-Regel „zeilentreu, nur ein Eintrag fällt" ist in S6c nicht haltbar** — und das muss
die Spec als bewusste Abweichung benennen. Grund: ~24 neue Prop-Zeilen entstehen im
`interface Props` (`:73-95`) und im `let {…}`-Block (`:96-125`), also **oberhalb aller 18
Einträge**. Jede Zeilennummer verschiebt sich zwangsläufig. Zeilenzahl-Wiederherstellung wäre
Verrenkung, nicht Sorgfalt.

Weil Mengengleichheit auf `Datei:Zeile` ihre Beweiskraft verliert, sobald 14 Einträge fallen
und 4 neu eintragen werden (ein **neuer** Zweig könnte eine frei gewordene Nummer besetzen),
hält die Spec **je Eintrag Schicksal UND Bedingungstext** fest — prüfbar am Inhalt, nicht an
der Position.

| alt | Bedingung (wörtlich) | Schicksal | Grund |
|---|---|---|---|
| `:171` | `context === 'vergleich' ? (wiz?.officialWarningsEnabled ?? false) : …` | **FÄLLT** | reine Quellenwahl |
| `:174` | `if (context === 'vergleich') {` (Schreiben `officialWarningsEnabled`) | **FÄLLT** | reine Zielwahl |
| `:186` | `context === 'vergleich'` (Lesen `activeMetricKeys`) | **FÄLLT** | reine Quellenwahl |
| `:199` | `context === 'vergleich'` (nicht-alarmfähige Größen) | **BLEIBT** | FACHLICH, route strukturell leer (#1435 AC-7) |
| `:216` | `context === 'vergleich'` (Lesen `metricAlertLevels`) | **FÄLLT** | reine Quellenwahl |
| `:221` | `if (context === 'vergleich') {` (Schreiben `metricAlertLevels`) | **FÄLLT** | reine Zielwahl |
| `:243` | `context === 'vergleich'` (Lesen Kanäle) | **FÄLLT** | reine Quellenwahl |
| `:253` | `if (context === 'vergleich') {` (Schreiben Kanäle) | **FÄLLT** | reine Zielwahl |
| `:280` | `context === 'vergleich'` (Lesen `channelThresholds`) | **FÄLLT** | reine Quellenwahl |
| `:285` | `if (context === 'vergleich') {` (Schreiben `channelThresholds`) | **FÄLLT** | reine Zielwahl |
| `:345` | `if (context !== 'route') return;` | **FÄLLT** | zeilentreu -> `if (!trip) return;` — siehe Entscheidung unten |
| `:367` | `context === 'vergleich' && wiz && preset && saveController` | **FÄLLT** | nennt `wiz`; wird Fähigkeits-Gate |
| `:379` | `if (context !== 'vergleich' \|\| !wiz \|\| !vergleichSpeicherung) return;` | **FÄLLT** | zeilentreu -> `if (!vergleichSpeicherung) return;` (S6b AC-4-Muster) |
| `:424` | `{#if context === 'vergleich' && unalertableSelectedMetricNames.length > 0}` | **BLEIBT** | Markup ohne `wiz`; hängt an der fachlichen Zusicherung `:199` |
| `:443` | `{#if context === 'vergleich'}` (Kurzstil-Schalter) | **BLEIBT** | DARSTELLUNG — im Trip steht derselbe Schalter im Versand-Reiter (#1260 S5) |
| `:459` | `{#if context === 'vergleich'}` (Cooldown-Karte) | **FÄLLT** | beide Zweige rendern dieselbe Karte, nur die Quelle unterscheidet sich |
| `:467` | `{#if context === 'vergleich'}` (Stille Stunden) | **FÄLLT** | dito; der einzige echte Unterschied `zonen_bezug` wird Prop |
| `:482` | `{#if context === 'vergleich'}` (Beispielwarnung) | **BLEIBT** | FACHLICH — Ort- statt Etappen-Subjekt |

**Bilanz: 14 fallen, 4 bleiben (mit neuen Zeilennummern). Ratsche 67 -> 53.**
Die drei Einträge `alarme-tab/alarmeTabSections.ts:27, :38, :42` werden **nicht** angefasst;
ihre Zeilennummern dürfen sich nicht verschieben.

### Entscheidung zu `:345` (bewusst, begründungspflichtig im Commit)

`:345` ist der **Trip**-Speicherweg, gehört also nicht zur Wirkung „Vergleichs-Zweig auf
Wertprops". Die S6b-Regel „`wiz`->Wertprops und HERKUNFT-Abbau nie koppeln" spräche dafür,
ihn liegen zu lassen. **Dagegen und entscheidend:** S6c ist die **einzige** verbleibende
Scheibe, die `AlarmeTab.svelte` öffnet (S6d Wertebereiche, S6e Versand, S6f Bilanz). Bliebe
`:345` stehen, wäre er ein Waisenkind gegen die S6-AC-2 („keine HERKUNFT-Zweige in
`shared/`") und fiele erst in der Bilanz-Scheibe unangenehm auf.

Deshalb: `:345` fällt **zeilentreu** (eine Zeile -> eine Zeile) zu `if (!trip) return;` —
genau die Bauart, die S6b in AC-4 einmalig und begründet angewandt hat. Äquivalenz ist
beweispflichtig: In den drei Vergleichs-Mounts ist `trip` nie gesetzt, im Trip-Mount
(`AlarmeScheduleTab.svelte:60-69`) immer. Ein Wirkort-Test muss das bewachen; lässt sich die
Äquivalenz in `/40` nicht sauber zeigen, **bleibt** `:345` und die Ratsche endet bei 54.

## Technical Approach

1. **`AlarmeTab.svelte`** bekommt für jedes der 13 Felder eine Wertprop und — wo geschrieben
   wird — einen Rückruf `on…`. `wiz`, und damit der Typ-Import von `CompareWizardState`,
   verschwindet aus dem Baustein. Die zwei `bind:`-Stellen werden zu Funktions-Bindungen, die
   Kinder bleiben unangetastet. `zonen_bezug` wird zur Prop `zonenBezug`.
2. **Ein Prop-Bündel statt dreifacher Inline-Glasur.** S6b hat inline-Pfeilfunktionen gewählt,
   *weil benannte Adapter zeilenverschiebend gewesen wären* — dieses Argument trägt hier nicht
   mehr (die Zeilen verschieben sich ohnehin, siehe Ratsche). Bei **drei** Mounts x 13 Feldern
   wären inline-Adapter rund 60 Zeilen fast gleiche Glasur an drei Stellen — dreifache
   Gelegenheit zur Drift, genau das Anti-Pattern, das #2276 abbaut. Stattdessen **eine**
   Funktion `alarmePropsAus(wiz)`, an jedem Mount als `{...alarmePropsAus(wiz)}` gespreizt.
   **Reaktivitäts-Auflage:** Der Spread muss im Markup (oder in einem `$derived`) stehen,
   damit die `$state`-Lesezugriffe beim Rendern registriert werden — ein einmal berechnetes
   Objekt in einem nicht-reaktiven Bereich würde einfrieren. Die Abweichung von S6b gehört
   begründet in die Spec, sonst fragt der Adversary danach.
3. **Speicherweg bleibt unverändert:** `erstelleAlarmeVergleichSpeicherung`, `hubPutQueue`,
   Voll-Spread-Payload, Rollback. Read-Modify-Write bleibt Pflicht.

## Testabdeckung — was wo bewacht wird

| Zusicherung | Prüfstrecke | Warum dort |
|---|---|---|
| Verhalten im Browser unverändert (Hub) | **neu** `compare-alarme-wertprops.spec.ts`, in die CI-Ampel | Prop-Verdrahtung und `$effect` sieht der SSR-Prüfstand nicht |
| Wirkort-Guard (Effekt rührt den Speicherweg an den **negativen** Orten nicht an) | **Kern**, `effekteVon()` (`svelteInstanzPruefstand.ts:188`), Muster aus `compare_stundenverlauf_wertprops.test.ts:410-522` | Am `/compare/new`-Mount ist eine Mutation im Browser strukturell unbeobachtbar (F001-Lehre) |
| `/compare/new` behält seine Bedienelemente | **Kern**, AST-Wächter über alle drei Vergleichs-Mounts | Keine gelistete E2E-Spec berührt `/compare/new` im Alarme-Reiter — eine Regression dort führe grün durch |
| Keine Klebeschicht geladen (AC-4) | `alarme_tab_laedt_keine_compare_klebeschicht.test.ts`, Saat angepasst **+ Gegenprobe** | Ohne Gegenprobe kann der Ladetest nach dem Umbau vakuum-grün werden |

**Bewusst KEINE zweite E2E-Spec für `/compare/new`:** Das bräche die Scheiben-Disziplin
(eine Spec je Scheibe, S2–S6b) und landet in der dokumentierten `global.setup`-ENOENT-Klasse
(`ci_e2e_specs.txt:185-187`). Der Anlege-Mount wird stattdessen im Kern bewacht.

## Scope Assessment

- **Dateien:** 4 produktiv (1 neu) + 5 Test/Ratsche/CI-Liste
- **LoC (produktiv, geschätzt):** ca. +170 / -60 — unter 250, aber **nicht komfortabel**.
  Vor einer Override-Ankündigung `workflow.py status` fragen, nicht aus der Ausschlussliste
  ableiten.
- **Risk Level: MITTEL–HOCH.** Der Wirkort liegt in Prop-Verdrahtung und `$effect`; zwei der
  drei Mounts sind in der CI-Ampel unbewacht; die Ratschen-Umschreibung ist die größte
  Einzeländerung an diesem Wächter seit seiner Einführung.
- **Kein Sub-Scheiben-Schnitt.** Eine Aufteilung nach Feldgruppen würde die Ratschen-Umstellung
  mehrfach durchlaufen — genau den teuren, riskanten Teil. Eine Scheibe, ein Übergang 67 -> 53.
  Wächst der Schnitt über 250 LoC, ist `loc_limit_override` der Weg, nicht das Teilen.

## Dependencies

- Reihenfolge: nach S6b (live, `8207c157`), vor S6d/S6e/S6f.
- Zusicherungen aus S2, die S6c nicht brechen darf: AC-1 (genau ein PUT je Änderung),
  AC-4 (412 => „Nochmal speichern"), AC-8 (Radar/Schwellen/Kurzstil landen im Stand),
  AC-9 (`AlarmeTab` importiert die Bridge nicht zur Laufzeit).
- Unberührt: `hydrateAlarmFieldsFromPreset`, `wiz.saveNewPreset()` auf der Anlege-Seite,
  `alert_channels`-Struktur (#2293).

## Open Questions

- [ ] Keine für den PO. Die einzige noch offene technische Frage — Äquivalenz von
      `context !== 'route'` und `!trip` bei `:345` — wird in `/40` durch einen Wirkort-Test
      beantwortet; scheitert der Beweis, bleibt `:345` stehen und die Ratsche endet bei 54
      statt 53. Beide Ausgänge sind oben festgehalten.

## Nachtrag zur Schicksals-Tabelle: `:459` und `:467` einzeln begründet

Bei allen übrigen Zeilen folgt das Schicksal mechanisch aus dem Bedingungstext (nennt die
Bedingung `wiz`/`trip`, ist sie HERKUNFT und fällt zwangsläufig). `:459` und `:467` sind die
**einzigen zwei Ausnahmen** — Markup-Wächter, deren Bedingung `wiz` nicht nennt. Sie brauchen
darum eine eigene Begründung, sonst greift der Adversary genau hier an.

- **`:459` (Cooldown).** Beide Zweige rendern dieselbe Komponente mit demselben einzigen
  Attribut; der Unterschied ist ausschliesslich das Bindungsziel (`wiz!.alertCooldownMinutes`
  vs. lokale `cooldownMinutes`). Mit einer Wertprop + Funktions-Bindung bleibt **ein** Mount
  übrig, der Wächter hat nichts mehr zu unterscheiden. **FÄLLT.**
- **`:467` (Stille Stunden).** Hier unterscheiden sich die Zweige zusätzlich in
  `zonen_bezug` (`"des ersten Orts"` vs. `"der Tour"`) — eine **Darstellungs**-Unterscheidung,
  die nicht einfach mitverschwindet. Sie wandert an die Aufrufstelle: neue Prop `zonenBezug`
  mit **Vorgabewert `'der Tour'`**. **Gemessen:** Der Trip-Mount
  (`trip-detail/AlarmeScheduleTab.svelte:60-69`) übergibt heute **kein** `zonen_bezug`; der
  Vorgabewert deckt ihn also vollständig ab, die Datei bleibt **unangetastet**. Die drei
  Vergleichs-Mounts bekommen `zonenBezug: 'des ersten Orts'` aus `alarmePropsAus(wiz)`.
  Damit bleibt ein Mount übrig. **FÄLLT.**

Wäre der Vorgabewert nicht tragfähig gewesen, hätte `AlarmeScheduleTab.svelte` in die
Datei-Tabelle gemusst — er ist es, deshalb nicht.

## Nachtrag: ein weiterer Test in die Prüfliste

`alarme_save_single_writer.test.ts` Teil (a) (`:40-52`) behauptet textuell, dass
`trip-detail/AlarmeScheduleTab.svelte` **kein** `saveController.schedule(` und kein
`void doSave(` enthält. Solange die `:345`-Umstellung — wie geplant — vollständig **in**
`AlarmeTab.svelte` bleibt, bleibt dieser Test grün. Er gehört trotzdem auf die Prüfliste:
Er ist der einzige Test, dessen Grün von der erst nachträglich getroffenen `:345`-Entscheidung
abhängt, und er würde aus **richtigem** Grund rot, falls Speicher-Verdrahtung in den
Trip-Container wanderte.

## Nachtrag: die Reaktivitäts-Auflage muss prüfbar formuliert werden

„Der Spread muss im Markup oder in einem `$derived` stehen" ist Prosa — ein einmal berechnetes,
eingefrorenes Prop-Objekt besteht den SSR-Prüfstand und die AST-Prüfung anstandslos und fällt
erst im Browser auf. Am Hub fängt das die neue E2E-Spec; an den Mounts (C)/(D) fängt es
**niemand** (keine E2E, Kern ist SSR-only).

**Folge für die Spec:** Die Auflage ist als prüfbare Form zu schreiben — `alarmePropsAus(wiz)`
wird an allen drei Vergleichs-Mounts **im Markup-Ausdruck selbst** aufgerufen
(`{...alarmePropsAus(wiz)}`), nicht in eine Variable im Instanz-Skript gehoben. Diese Form kann
der AST-Wächter tatsächlich messen; „ist reaktiv" kann er nicht.

---

## Nachtrag aus dem PO-Briefing (21.09., vor der Freigabe)

Das unabhängige PO-Briefing (`docs/briefings/rework-2276-s6c-alarme.md`, Anmerkung 3) hat
eine Lücke benannt, die **nicht** in die Spec eingearbeitet wurde (das hätte das
SHA-gebundene Briefing entwertet) und die deshalb hier festgehalten wird, damit sie einen
`/clear` überlebt:

**Benannte Mutations-Familie für `/40` und den Adversary:
„Herkunfts-Verzweigung durch Ersatzwert-Fallback ersetzt".**

AC-1 („kein `wiz`-Symbol mehr in `AlarmeTab.svelte`") und AC-6 (Ratsche auf
`context ===`/`context !==`) schlagen **beide grün** aus, wenn eine Herkunfts-Verzweigung
lediglich **umbenannt** statt entfernt wird. Die Known Limitations der Spec verbieten
ausdrücklich nur `Wertprop ?? wiz`. Nicht erfasst ist die Form

```ts
const wert = neueProp !== undefined ? neueProp : lokalerErsatz;
```

— dieselbe doppelte Quelle, nur ohne die Wörter `context` und `wiz`. Das ist genau die
Projekt-Fehlerklasse „Misst der Test die Zusicherung?".

**Auflage:** In `/40-tdd-red` gehört diese Mutation auf die Liste der Gegenproben, und der
`implementation-validator` muss sie in Step 3b ausdrücklich fahren — nicht erst entdecken.

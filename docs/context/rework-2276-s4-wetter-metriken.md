# Kontext: Issue #2276 Scheibe S4 — Wetter-Metriken/Layout-Reiter speichert selbst

> Analyse-Dokument fuer `/30-write-spec`. Keine Implementierung, keine Spec-Datei.
> Workflow: `rework-2276-s4-wetter-metriken` (Epic #2345, Issue #2276 bleibt offen bis S6).
> Erhoben 2026-09-19 im Worktree `stateless-tumbling-sutherland`.

## 0. Wichtigste Abweichung von der Auftragsannahme

Der Auftrag ging (wie E4 im Gesamtschnitt-Dokument) davon aus, S4 sei ein Repeat
von S2/S3 auf einen dritten Reiter. **Das stimmt nur teilweise.** Der Reiter
„Wetter-Metriken" bedient heute **zwei fachlich unabhaengige Datendomaenen**
mit **zwei separaten Commit-Funktionen** (`handleWetterMetrikenCommit` fuer
Metrikauswahl/Kanaele/Amtliche-Warnungen/Tagesfenster,
`handleLayoutCommit` fuer Stundenverlauf/Ausblick — Issue #1360 hat den
vormals eigenen „Layout"-Reiter in diesen Reiter hineingezogen, der
Commit-Pfad ist NICHT mitverschmolzen). Beide haengen an EINEM Wrapper-Paar
(`.hub-layout-hourly-wrap` aussen, `.hub-wetter-metriken-wrap` innen) und
feuern deshalb bei **fast jeder Geste im Reiter gemeinsam** (Bubble durch
beide DOM-Ebenen). Eine 1:1-Uebertragung des S2/S3-Musters („ein Reiter → ein
Selbst-Speicherer") auf ZWEI unveraendert getrennte Domaenen fuehrt zu einem
neuen, in S2/S3 nicht aufgetretenen Datenverlust-Pfad (Abschnitt 1.7). S4 muss
die beiden Domaenen deshalb zu EINER Orchestrierung zusammenfuehren, nicht zu
zweien.

## 1. Ist-Zustand (Datei:Zeile, Stand `70078059`)

### 1.1 Zwei Commit-Funktionen, ein Wrapper-Paar, eine gemeinsame Hub-Queue

`frontend/src/lib/components/compare/CompareTabs.svelte`:

- `handleWetterMetrikenCommit` (:593-625) — Snapshot `activeMetricKeys`,
  `channelActiveMetricKeys`, `officialAlertsEnabled`, `dayWindowStartHour/EndHour`
  (Typ `WeatherMetricsSnapshot`, importiert aus
  `shared/weather-metrics-tab/weatherMetricsCompareSave.ts`). Diff-Guard
  `flushPendingWeatherMetricsSave`, PUT ueber `hubPutQueue.enqueue`, Rollback
  bei Fehler, `saveController` wird nur MANUELL bedient (`setSaving`/`setSaved`/
  `setError`/`markPristine`), NICHT ueber `schedule()`.
- `handleLayoutCommit` (:669-716) — Snapshot `hourlyMetricKeys`, `hourlyEnabled`,
  `outlookMetricKeys`, `outlookMetricFormats`, `outlookEnabled` (Typ
  `LayoutSnapshot`, `compare/compareHubWizardBridge.ts:513-531`). Gleiches
  Muster: Diff-Guard `flushPendingLayoutSave`, `hubPutQueue.enqueue`, Rollback
  `rollbackLayoutSnapshot`, manuelle `saveController`-Bedienung.
- Markup (:1213-1241): `.hub-layout-hourly-wrap` (onchange/onfocusout/onclick
  → `handleLayoutCommit`) umschliesst `.hub-wetter-metriken-wrap`
  (onchange/onfocusout/onclick → `handleWetterMetrikenCommit`), darin
  `<WeatherMetricsTab context="vergleich" wiz={wizardState}
  onCompareCommit={handleWetterMetrikenCommit}
  onHourlyCommit={handleLayoutCommit} onOutlookCommit={handleLayoutCommit} />`.
  Ein Bubble-Ereignis aus dem inneren Wrapper durchlaeuft **beide** Handler in
  derselben Event-Tick — heute unschaedlich, weil beide seriell durch
  `hubPutQueue` laufen und der jeweils andere Diff-Guard `null` liefert, wenn
  seine eigene Domaene unveraendert ist.

### 1.2 Zwei getrennte Hydrationen, ein gemeinsames Mount-Gate

- `hydrateWetterMetrikenTab()` (:555-583) setzt `wetterMetrikenHydrated = true`
  nach eigenem `loadCompareSelectionEntries()`-Abschluss; Baseline
  `lastPersistedWetterMetrikenSnapshot`.
- `hydrateLayoutTab()` (:644-655) setzt **unabhaengig** `layoutHydrated = true`
  nach seinem eigenen Aufruf derselben (gecachten) Katalogfunktion; eigene
  Baseline `lastPersistedLayoutSnapshot`.
- Beide `$effect`s haengen an `activeTab === 'wetter-metriken'` (:585-591,
  :657-663) und laufen **parallel**, nicht sequenziell.
- Das Render-Gate im Markup (:1193, `{#if wetterMetrikenHydrated}`) prueft
  **nur** `wetterMetrikenHydrated` — `layoutHydrated` kann beim ersten Mount
  noch ausstehen. `WeatherMetricsTab` wird dann mit noch nicht hydrierten
  `wiz.hourlyMetricKeys`/`outlookMetricKeys` gemountet; sobald
  `hydrateLayoutTab()` kurz danach fertig wird, schreibt sie diese Felder
  NACHTRAEGLICH in den bereits gemounteten `wiz`-State.

### 1.3 `weatherMetricsCompareSave.ts` liegt bereits in `shared/` — mit einer Laufzeit-Bruchstelle

`frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`
(153 Zeilen) enthaelt bereits `hydrateWeatherMetricsFromPreset`,
`hydrateChannelActiveMetricsFromPreset`, `hydrateDayWindowFromPreset`,
`WeatherMetricsSnapshot`, `flushPendingWeatherMetricsSave` — anders als bei
Alarme/Wertebereiche liegt die Wetter-Metriken-Haelfte des Speicherwegs also
schon **im geteilten Ordner**, nicht in `compare/`. Der Haken:
`flushPendingWeatherMetricsSave` importiert und ruft **zur Laufzeit**
`buildHubPutPayload` aus `../../compare/compareHubWizardBridge.ts`
(`:10`, `:145`) — ein Funktions-, kein Typ-Import. Das ist exakt die
Grenzverletzung, die S2 (AC-9) und S3 (AC-7) fuer Alarme/Wertebereiche
geschlossen haben, hier aber vorher unbemerkt bestehen blieb (das
Gesamtschnitt-Dokument fuehrte diese Datei nicht als eigenen Regelverstoss).
`hydrateWeatherMetricsFromPreset` selbst hat **keine** Laufzeitabhaengigkeit
zu `compare/` und wird von `compareHubWizardBridge.ts:499`
(`hydrateAlarmFieldsFromPreset`) importiert — diese Nutzung bleibt unabhaengig
von S4 bestehen (Alarme braucht die Funktion fuer die Empfindlichkeits-Tabelle
als Erst-Tab-Hydration).

Die Layout-Haelfte (`LayoutSnapshot`, `hydrateLayoutFieldsFromPreset`,
`flushPendingLayoutSave`, `rollbackLayoutSnapshot`) liegt dagegen noch
vollstaendig in `compare/compareHubWizardBridge.ts:511-633` und hat denselben
`buildHubPutPayload`-Aufruf (`:601`).

### 1.4 `context ===`-Verzweigungen in `WeatherMetricsTab.svelte` (2081 Zeilen)

Deutlich weniger als die im Gesamtschnitt-Dokument genannten „41/38" (jene
Zahl zaehlte vermutlich `wiz`/`trip`-Vorkommen, nicht reine
`context ===`-Bedingungen). Tatsaechliche `context ===`-Stellen heute: 6
(:545, :560, :577, :589, :602, :1288). Davon:

- **FACHLICH, bleibt bestehen:** :545/:560 (Trip-Katalog-Ladepfad, route-only),
  :589 (SMS-Kuerzel-Ladepfad, vergleich-only), :602 (Stundenverlauf-Katalog,
  vergleich-only), :1288 (Markup-Weiche Trip-Speichern-Leiste vs.
  Vergleich-Snippets — bleibt, weil sie KEINE Persistenz-Verzweigung ist,
  sondern echte Layout-Unterscheidung Save-Button vs. `wiz`-Anzeige).
- **„Toter Zweig" :577 — bestaetigt, aber kein Persistenz-Pfad:**
  `if ((context === 'vergleich' || context === 'route') && !compareCatalogLoaded)`.
  `WeatherMetricsContext` kennt nur diese zwei Werte — die Oder-Bedingung ist
  fuer jeden gueltigen `context`-Wert tautologisch wahr, der einzige wirksame
  Guard ist `!compareCatalogLoaded`. Kein Speicherweg-Unterschied, reines
  Boilerplate-Aufraeumen (kann in der Spec als Mini-Vereinfachung mitgenommen
  werden, ist aber keine S4-Kernaenderung).
- **Persistenz-Verzweigung, faellt NICHT unter S4:** keine — `scheduleAutoSave`/
  `scheduleReportConfigOnlySave`/`handleSave` (:927-1006) sind ausschliesslich
  ueber `context === 'route'`-exklusive Abschnitte (`report_config`,
  `sms_schwellen`, s. `weatherMetricsTabSections.ts`) erreichbar — der
  Vergleich rendert `EditReportConfigSection` gar nicht, `reportConfig`
  aendert sich im vergleich-Kontext praktisch nie. Diese drei Funktionen sind
  fuer S4 irrelevant, kein Anfassen noetig.

Die eigentliche „Persistenzflaeche" des Vergleich-Zweigs liegt NICHT in
`context ===`-Verzweigungen, sondern in verstreuten `wiz.*`-Mutationsstellen
(Abschnitt 1.5) plus den drei expliziten Commit-Props
(`onCompareCommit`/`onHourlyCommit`/`onOutlookCommit`, :167-176).

### 1.5 Mutationsstellen im vergleich-Zweig — explizite Commit-Calls vs. reine Wrapper-Abhaengigkeit

| Geste | Zeile | Ruft Commit-Prop direkt? |
|---|---|---|
| Metrik-Checkbox an/aus (`toggleCompareMetric`) | :1095-1117 | **Nein** — nur Wrapper-Bubble |
| Kanal-Reihenfolge Drag-Ende (`editCompareChannel`/`onCompareDndReorder`) | :1183-1196 | Ja, `onCompareCommit?.()` (:1188) |
| Amtliche-Warnungen-Toggle (`onToggleVergleichOfficialAlerts`) | :1243-1246 | **Nein** — nur Wrapper-Bubble |
| Tagesfenster Von/Bis (`DayWindowCard` `onStartHour`/`onEndHour`) | :1415-1416 | **Nein** — nur Wrapper-Bubble |
| Stundenverlauf Drag-Ende (`CompareHourlyLayoutControls`, :172/:181) | extern | Ja, `onHourlyCommit?.()` |
| Ausblick Auswahl/Reihenfolge/Schalter (`CompareOutlookLayoutControls`, :179/:192/:204) | extern | Ja, `onOutlookCommit?.()` |

Die Drag-Ende-Faelle rufen explizit, weil Browser nach einer Ziehgeste das
nachfolgende `click` oft unterdruecken (Kommentar :161-166) — der Wrapper
wuerde dann NICHT feuern. Checkbox-/Toggle-/Input-Gesten lösen dagegen
regulaere `change`/`click`-Ereignisse aus und verlassen sich VOLLSTAENDIG auf
den Wrapper. **Fuer S4 wichtig:** faellt der Wrapper weg (wie bei S3s
`.hub-corridor-wrap`), muessen genau diese drei Stellen (`toggleCompareMetric`,
`onToggleVergleichOfficialAlerts`, `DayWindowCard`-Handler) einen Ersatzweg
bekommen — das ist der direkte Analogfall zu S3s Risiko „beide historischen
Ausloeser einzeln pruefen".

### 1.6 `saveStatusStore.svelte.ts` — Einzel-Slot-Bestaetigung (bereits durch S3 belegt, hier erneut relevant)

`schedule(saveFn)` (:184-189) ueberschreibt `_pendingFn` **unbedingt** bei
jedem Aufruf, unabhaengig davon, ob der vorherige Eintrag schon feuerte. Durch
S3 bereits als Cross-Tab-Risiko dokumentiert (Alarme vs. Wertebereiche beim
Reiterwechsel) und dort mit `sichereSelbstSpeichererVorReiterwechsel` +
`SELBST_SPEICHERNDE_VERGLEICH_REITER` geloest (Abschnitt 1.7 dort). Fuer S4
gilt diese Absicherung nur, WENN Wetter-Metriken als drittes Element in dieser
Liste ergaenzt wird (trivial) — sie loest aber NICHT das im naechsten
Abschnitt beschriebene Problem, das INNERHALB desselben Reiters entsteht.

## 1.7 Neues Risiko durch S4: zwei Selbst-Speicherer AUF DEMSELBEN REITER, ausgeloest von DERSELBEN Geste (kritischer als S3s Cross-Tab-Fall)

S2/S3 behandelten jeweils GENAU EINEN Reiter mit GENAU EINER Domaene. Wuerde
S4 dasselbe Muster 1:1 auf `handleWetterMetrikenCommit` UND `handleLayoutCommit`
getrennt anwenden (zwei unabhaengige `erstelleXVergleichSpeicherung()`-Module,
je eines pro historischer Commit-Funktion), entstuende ein **neuer**
Datenverlust-Pfad, den es bei Alarme/Wertebereiche nicht gab:

- Heute feuert **ein einziger Klick** im Reiter (z. B. eine Metrik-Checkbox)
  durch die verschachtelten Wrapper **beide** Commit-Funktionen im selben
  synchronen Tick (Bubble: `.hub-wetter-metriken-wrap` zuerst, dann
  `.hub-layout-hourly-wrap`). Heute harmlos, weil beide seriell durch
  `hubPutQueue` laufen (zwei PUTs, der zweite meldet sich per Diff-Guard als
  No-Op, wenn seine Domaene unveraendert ist).
- Wuerden beide auf `saveController.schedule()` umgestellt (S2/S3-Muster),
  wuerde der ZWEITE `schedule()`-Aufruf (Layout) den `_pendingFn`-Slot des
  ERSTEN (Wetter-Metriken) **kommentarlos ueberschreiben** — noch BEVOR das
  700ms-Debounce-Fenster ablaeuft, in DERSELBEN Event-Tick.
- Die Layout-SaveFn liest die Wetter-Metriken-Felder NICHT live nach — ihr
  Payload-Bau rundtrippt `activeMetricKeys`/`channelActiveMetricKeys`/
  `officialAlertsEnabled`/`dayWindowStart/EndHour` unveraendert aus der
  **eingefrorenen Server-Baseline** (`preset.display_config`), nicht aus dem
  live `wiz`-State. Die soeben angeklickte Metrik-Checkbox wuerde beim
  einzigen tatsaechlich ausgefuehrten PUT (Layout) **stillschweigend
  verloren gehen** — kein Fehler, keine Fehlermeldung, einfach ein PUT, der
  den alten Metrik-Stand bestaetigt.
- **Unterschied zu S3s Risiko 9 (Cross-Tab):** dort schuetzt ein Flush-Guard
  beim Reiterwechsel, weil zwischen den beiden Aenderungen ein Tab-Wechsel
  liegt. Hier liegt **kein** Tab-Wechsel zwischen den beiden Aufrufen — sie
  passieren in DERSELBEN Millisekunde, ein Flush-Guard kann nichts abfangen,
  das noch gar nicht als „ausstehend" markiert war, bevor es ueberschrieben
  wurde.

**Konsequenz fuer das Zielbild:** S4 darf NICHT zwei getrennte
Selbst-Speicherer bauen. Es braucht **eine** kombinierte Orchestrierung
(ein Snapshot-Typ ueber BEIDE Domaenen, eine `aenderungMelden()`-Funktion,
ein `schedule()`-Aufruf pro Geste), analog zu `erstelleAlarmeVergleichSpeicherung`/
`erstelleWertebereicheVergleichSpeicherung`, aber mit einem breiteren
Snapshot. Das ist zugleich eine Verbesserung gegenueber dem heutigen Zustand
(bis zu zwei PUTs pro Geste → hoechstens einer) und strukturell konsistent
mit dem in S2/S3 etablierten Zielbild „genau ein Speicherweg".

## 1.8 E3-Pruefung (PFLICHT laut Gesamtschnitt-Dokument) — Ergebnis: ECHTE Ueberschneidung, sicher nur bei Live-Read

**`display_config.active_metrics` wird von ZWEI Reitern geschrieben:**
`wertebereicheVergleichSpeicherung.ts:71` sendet
`activeMetricKeys: current.activeMetricKeys` (live aus `ws`, S3 AC-3) — UND
die neue Wetter-Metriken-Orchestrierung wuerde denselben Schluessel aus
`wiz.activeMetricKeys` senden. Das ist strukturell **identisch** zur bereits
bekannten `metric_alert_levels`-Ueberschneidung (Alarme/Wertebereiche, S3
Abschnitt 1.4) — sicher, WEIL beide Schreiber den Wert **live bei Ausfuehrung**
lesen (nicht aus einer beim Planen eingefrorenen Kopie). **Das muss als
eigene Pflicht-AC in die S4-Spec** (Analog zu S3 AC-3): „`activeMetricKeys`
MUSS live aus `wiz` zum Ausfuehrungszeitpunkt gelesen werden, nie aus einer
eingefrorenen `preset`-Kopie" — Mutations-Gegenprobe: Befuellung aus
`preset.display_config.active_metrics` statt aus `wiz` ⇒ Test muss rot werden.

Sekundaer (nur als bekannte Wechselwirkung dokumentieren, kein Bau-Auftrag):
Wertebereiche sendet `channelActiveMetricKeys: undefined` (Round-Trip,
`wertebereicheVergleichSpeicherung.ts:72`), waehrend `toggleCompareMetric`
sowohl `activeMetricKeys` ALS AUCH `channelActiveMetricKeys` mutiert. Eine
Wertebereiche-Speicherung, die eine noch ausstehende Wetter-Metriken-Aenderung
ueberholt, wuerde kurzzeitig neue `active_metrics` mit alten
`channel_active_metrics` kombinieren. Der Reiterwechsel-Flush-Guard macht das
im gemeinsamen Ablauf praktisch unerreichbar (kein Tab-Wechsel ohne Flush) —
keine Massnahme in S4 noetig, nur zu benennen.

**Sonstige Ebene-1-Schluessel der neuen Orchestrierung** (`channel_active_metrics`,
`hourly_metrics`, `outlook_metrics`, `outlook_metric_formats`) werden von
KEINEM anderen Reiter geschrieben — keine weitere Ueberschneidung.
`official_alerts_enabled`/`hourly_enabled`/`outlook_enabled`/
`day_window_start_hour`/`day_window_end_hour` liegen TOP-LEVEL im
`ComparePreset` (nicht unter `display_config`), fuer sie gilt die
Ebene-1-Merge-Regel des Go-Kernels ohnehin nicht — reines Scalar-Overwrite,
unproblematisch bei Live-Read.

`official_alerts_enabled` wird zusaetzlich vom Alarme-Reiter mitgesendet
(S2 Known Limitation: „bleibt Legacy-Restfeld"). Da es ein Top-Level-Scalar
ist und beide Schreiber live lesen, ist auch das unproblematisch (gleiche
Situation wie bei S2 dokumentiert, keine neue Massnahme fuer S4).

## 2. Zielbild fuer S4

1. **Ein neues/erweitertes Modul** — Empfehlung: bestehendes
   `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`
   erweitern (nicht umbenennen — es ist bereits der richtige Ort und wird
   bereits von `compareHubWizardBridge.ts` fuer `hydrateWeatherMetricsFromPreset`
   importiert, ein Umzug wuerde unnoetig einen zweiten Importpfad erzeugen):
   - `flushPendingWeatherMetricsSave` wird auf `buildComparePresetSavePayload`
     (aus `compare/compareEditorSave.ts`, Voll-Spread) umgestellt, der
     Laufzeit-Import von `buildHubPutPayload` entfaellt (schliesst die in 1.3
     gefundene Bruchstelle).
   - `LayoutSnapshot`/`hydrateLayoutFieldsFromPreset`/`flushPendingLayoutSave`/
     `rollbackLayoutSnapshot` ziehen aus `compare/compareHubWizardBridge.ts`
     hierher um (analog zur S2/S3-Modulverschiebung), ebenfalls auf
     `buildComparePresetSavePayload` umgestellt.
   - **Neuer, kombinierter Snapshot-Typ** ueber BEIDE Domaenen (Arbeitsname
     `WetterMetrikenLayoutSnapshot`), **eine** `baueWetterMetrikenNutzlast()`
     (Voll-Spread), **ein** `flushPendingWetterMetrikenSave` (Diff-Guard ueber
     den kombinierten Snapshot), **ein** `erstelleWetterMetrikenVergleichSpeicherung()`
     (Signatur wie `erstelleAlarmeVergleichSpeicherung`/
     `erstelleWertebereicheVergleichSpeicherung`: `{client, wiz, preset: () => …,
     enqueueHubWrite, onCompareUpdate, saveController}` → `{aenderungMelden()}`).
   - `activeMetricKeys` in der kombinierten Nutzlast MUSS live aus `wiz`
     kommen (E3-Pflicht-AC, Abschnitt 1.8).
2. **`WeatherMetricsTab.svelte`**: Props `onCompareCommit`/`onHourlyCommit`/
   `onOutlookCommit` entfallen, ersetzt durch `preset`, `enqueueHubWrite`,
   `onCompareUpdate` (Signatur wie `AlarmeTab`/`CorridorEditor`). Empfehlung
   (Begruendung Abschnitt 3): **ein reaktiver `$effect`** (AlarmeTab-Muster)
   ersetzt sowohl die drei expliziten Commit-Calls (:1188, extern in
   `CompareHourlyLayoutControls`/`CompareOutlookLayoutControls`) als auch die
   Wrapper-Abhaengigkeit der drei stillen Mutationsstellen (Abschnitt 1.5) —
   der Effect beobachtet einen kombinierten Snapshot aller acht Felder und
   ruft bei Diff `vergleichSpeicherung.aenderungMelden()`. Die
   `CompareHourlyLayoutControls`/`CompareOutlookLayoutControls`-Props
   `onHourlyCommit`/`onOutlookCommit` koennen unveraendert bestehen bleiben
   (intern auf eine No-Op-oder-weiterhin-nuetzliche Callback-Kette
   umgeleitet) — ihr Entfernen ist eine optionale Anschluss-Aufraeumung,
   kein S4-Muss.
3. **`CompareTabs.svelte`**: `handleWetterMetrikenCommit`/`handleLayoutCommit`,
   `currentWetterMetrikenSnapshot`/`lastPersistedWetterMetrikenSnapshot`,
   `lastPersistedLayoutSnapshot` entfallen. Die beiden Hydrations-Effekte
   (:585-591, :657-663) werden zu EINER Hydration mit EINEM Abschluss-Flag
   zusammengefuehrt (Pflicht, Abschnitt 1.2/4.2) — die kombinierte
   Orchestrierung darf erst NACH Abschluss BEIDER Katalog-Ladevorgaenge
   erzeugt werden (`untrack()`-Konstruktion wie bei Alarme/Wertebereiche).
   Wrapper-Divs (:1213-1241) entfallen, Mount von `WeatherMetricsTab` bekommt
   die neuen Props. `SELBST_SPEICHERNDE_VERGLEICH_REITER`
   (`wertebereicheVergleichSpeicherung.ts:205`) wird um `'wetter-metriken'`
   ergaenzt — `handleValueChange` und `handleToggleActive` sind bereits
   generisch (Abschnitt 1.6/1.9) und brauchen keine weitere Anpassung.
4. **Anlege-Seite unveraendert**: `compare-new/CompareNewEditor.svelte:378/479`
   mountet `WeatherMetricsTab` weiterhin nur mit `context="vergleich"`
   `{wiz}`, ohne `preset`/`saveController` — die Aktivierungsbedingung der
   neuen Orchestrierung (Analog `wertebereicheVergleichSpeicherungAktiv`)
   bleibt dort strukturell falsch.

## 3. Reaktiver `$effect` statt Wrapper — Begruendung

Die Wrapper existieren, weil mehrere Mutationsstellen (Abschnitt 1.5) KEINEN
expliziten Commit-Call haben. Ein `$effect`, der ueber die acht
persistenzrelevanten `wiz`/lokalen Felder reagiert, ist gegen genau die
Ursache immun, die die expliziten Drag-Ende-Calls noetig machte („Browser
unterdrueckt das nachfolgende `click`") — ein `$effect` reagiert auf
**State-Aenderungen**, nicht auf DOM-Ereignisse, das Drag-Problem betrifft nur
den Wrapper-Pfad. Dieses Muster ist bereits etabliert (`AlarmeTab.svelte`,
S2) und dort explizit gewaehlt, WEIL Alarme wie Wetter-Metriken viele
verstreute Mutationsfunktionen hat (anders als `CorridorEditor`, das ueber ein
zentrales `patch()/add()/remove()` faechert und deshalb mit einem
imperativen `maybeSchedule()` auskommt). Wetter-Metriken ist architektonisch
naeher an Alarme als an Wertebereiche — der reaktive Weg ist damit nicht nur
sicherer, sondern auch der bereits vorhandene Präzedenzfall.

## 4. Risiken (Delta zu S2/S3)

1. **Intra-Gesture-Kollision (Abschnitt 1.7, KRITISCH, NEU in S4).** Zwei
   unabhaengige Selbst-Speicherer auf demselben Reiter wuerden sich in
   DERSELBEN Event-Tick gegenseitig ueberschreiben — schaerfer als S3s
   Cross-Tab-Risiko, weil kein Reiterwechsel dazwischenliegt, den ein
   Flush-Guard abfangen koennte. Loesung: EINE kombinierte Orchestrierung
   (Abschnitt 2 Punkt 1), kein Flush-Guard-Workaround.
2. **Zwei-Hydrationen-eine-Baseline (Abschnitt 1.2, HOCH, NEU in S4).** Wird
   die Orchestrierung erzeugt, bevor BEIDE Katalog-Ladevorgaenge fertig sind,
   diffed sie gegen eine unvollstaendige Baseline — die SPAETER eintreffende
   Hydration (z. B. `hourlyMetricKeys`) erscheint dem Diff-Gate als
   Nutzeraenderung und loest einen PUT OHNE Nutzergeste aus. Pflicht-Test:
   beide Hydrationen zu unterschiedlichen Zeitpunkten abschliessen lassen,
   pruefen, dass VOR Abschluss BEIDER kein `schedule()`-Aufruf stattfindet.
   Mutations-Gegenprobe: nur `wetterMetrikenHydrated` statt
   `wetterMetrikenHydrated && layoutHydrated` als Gate verwenden ⇒ Test wird
   rot (PUT ohne Geste nachweisbar).
3. **`activeMetricKeys`-Ueberschneidung mit Wertebereiche (Abschnitt 1.8,
   E3-Pflicht).** Live-Read ist die einzige Absicherung — Mutations-Gegenprobe
   Pflicht (Payload aus `preset.display_config.active_metrics` statt `wiz`
   befuellen ⇒ Test rot).
4. **Drei stumme Mutationsstellen (Abschnitt 1.5).** Fallen die Wrapper weg,
   ohne dass `toggleCompareMetric`/`onToggleVergleichOfficialAlerts`/
   `DayWindowCard`-Handler einen Ersatzweg bekommen (expliziter Call ODER
   reaktiver Effect deckt sie ab), verstummt die Persistenz fuer genau diese
   drei Gesten lautlos. Je Geste ein eigener Regressionstest, analog S3s
   „beide historischen Ausloeser einzeln pruefen".
5. **Anlege-Seite (AC-7-Analog, Abschnitt 2 Punkt 4).** `CompareNewEditor`
   mountet `WeatherMetricsTab` mit einem LIVE `wiz` (anders als bei
   Alarme/Wertebereiche, wo die Anlege-Seite dieselbe Aktivierungsbedingung
   nutzt) — nur das Fehlen von `preset`/`saveController` verhindert einen PUT.
   Mutations-Gegenprobe: Aktivierungs-Guard entfernen ⇒ Anlege-Seite muesste
   einen PUT ausloesen ⇒ Test wird rot.
6. **`LayoutSnapshot.outlookMetricFormats` ist optional, seine Geschwister
   sind Pflichtfelder** (`compareHubWizardBridge.ts:529`). Der kombinierte
   `norm()`-Vergleich muss `== null ? null : {...}`-Semantik beibehalten,
   sonst entsteht ein Scheindiff zwischen „Schluessel fehlt" und „Schluessel
   ist null" (bestehender Test `compare_outlook_metric_formats_persistenz.test.ts`
   deckt das auf, wenn die Umstellung diese Nuance verliert).
7. **Bis zu zwei PUTs → hoechstens einer (Verhaltens-Delta, nicht
   -Neutralitaet-Bruch).** Nicht nutzersichtbar (kein zusaetzlicher Klick,
   keine andere Anzeige), aber ein bestehender Test, der eine
   Layout-only-Payload OHNE `active_metrics`-Schluessel erwartet, aendert sich
   legitim (Voll-Spread traegt jetzt immer beide Domaenen). Vorab in der Spec
   benennen, nicht erst in `/40` entdecken.
8. **Pendant-Frage (geteilter Baustein).** `WeatherMetricsTab` wird von Trip
   UND Vergleich geteilt, die neue Orchestrierung ist wie bei Alarme/
   Wertebereiche bewusst NUR fuer den vergleich-Zweig (Trip-Zweig nutzt
   weiterhin `scheduleAutoSave`/`scheduleReportConfigOnlySave`, unveraendert)
   — kein Verstoss gegen die Pendant-Sperre, in der Spec analog zu S2/S3 zu
   begruenden.
9. **Cross-User/Mandantentrennung:** unveraendert gegenueber S2/S3 (kein
   neuer Endpoint) — mit zwei Nutzern gegenzupruefen, falls unerwartet ein
   neuer Endpoint-Zweig entstuende (nicht erwartet).

## 5. Regressionsnetz

| Ebene | Datei | Status |
|---|---|---|
| Kern (Unit) | `compare/__tests__/compare_hub_layout_save.test.ts`, `compare_hub_layout_rollback.test.ts`, `compare_layout_tab_dissolution.test.ts`, `compare_outlook_metric_formats_persistenz.test.ts`, `outlookMetricIdSelection.test.ts`, `compareActiveMetricsStorageFormat.test.ts`, `compare_hub_wizard_bridge.test.ts` | umzuhaengen/anzupassen (Import-Ziel wechselt) |
| Kern (Unit) | `shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts`, `weatherMetricsTabDayWindowSave.test.ts`, `compareMetricOrder.test.ts`, `compare_hourly_layout_controls_structure.test.ts`, `weather_metrics_tab_create_mode_callback.test.ts`, `weather_metrics_tab_vergleich_uebersicht_kanal_tabs.test.ts` | bleiben, Verhalten unveraendert zu pruefen |
| E2E in Ratsche | `issue-344-wetter-profile.spec.ts`, `issue-690-custom-metrics-persist.spec.ts` (Trip-fokussiert), `compare-alarme-speichert-selbst.spec.ts`, `compare-wertebereiche-speichert-selbst.spec.ts` (Muster fuer den neuen Test) | bleiben gruen |
| E2E NICHT in Ratsche (S4-Regressionsnetz, MUSS gruen bleiben, Aufnahme in Ratsche NICHT Teil dieser Scheibe) | `compare-metric-order.spec.ts`, `compare-hourly-metric-order.spec.ts`, `compare-layout-tab-dissolution.spec.ts`, `compare-hub-fidelity-s8c.spec.ts`, `compare-editor-fidelity-s8d.spec.ts` | vor Abschluss lokal/Staging gegenlaufen lassen, NICHT zusaetzlich ratschen (Scope-Disziplin, s. Abschnitt 6) |
| E2E NEU | `frontend/e2e/compare-wetter-metriken-speichert-selbst.spec.ts` (Muster `compare-wertebereiche-speichert-selbst.spec.ts`) | anlegen, in `.github/ci_e2e_specs.txt` aufnehmen |

## 6. Scoping

| Datei | Aenderungsart | Grobschaetzung |
|---|---|---|
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | ERWEITERN (Layout-Funktionen rein, `buildHubPutPayload`-Import raus, kombinierte Orchestrierung neu) | +160/-15 |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | AENDERN (Props, reaktiver `$effect`, 3 stille Mutationsstellen, Aktivierungsbedingung) | +50/-20 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | AENDERN (2 Handler + Snapshot-Funktionen raus, Hydration zusammengefuehrt, Wrapper raus, `SELBST_SPEICHERNDE_VERGLEICH_REITER` +1 Zeile) | +25/-140 |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | AENDERN (`LayoutSnapshot`/`hydrateLayoutFieldsFromPreset`/`flushPendingLayoutSave`/`rollbackLayoutSnapshot` raus) | -110 |
| ~7 umgehaengte Kern-Tests (`compare/__tests__/` → `shared/`-Pendants bzw. Import-Anpassung) | UMZUG/ANPASSUNG | +120 |
| `frontend/e2e/compare-wetter-metriken-speichert-selbst.spec.ts` | NEU | +160 (zaehlt nicht ins LoC-Limit) |

**Kern-LoC-Schaetzung (ohne E2E):** ≈ +355/-285 — liegt ueber dem 250er-Limit
und tendenziell ueber S3s ≈480 Gesamtdiff, weil zwei Domaenen zusammengefuehrt
werden UND das Wirtsfile (2081 Zeilen) mehr verstreute Anpassungsstellen hat
als `CorridorEditor`. **Empfehlung: `loc_limit_override 500` gleich zu
Workflow-Beginn setzen** (wie S2/S3), NICHT die Scheibe in S4a/S4b aufteilen —
ein Domaenen-Split wuerde einen Zwischenzustand erzeugen, in dem zwei
Domaenen desselben Reiters auf unterschiedlichen Speichermechanismen laufen,
was mehr Risiko traegt als die eingesparten LoC rechtfertigen (das genau
begruendet Abschnitt 1.7 — der Domaenen-Split IST das Risiko). Ueberschreitet
der tatsaechliche Diff 500 spuerbar, gilt dieselbe Regel wie ueberall:
`loc_limit_override` erneut anheben, NICHT die RED-Abdeckung eigenmaechtig
verengen.

**Effort/Risk: HIGH, hoeher als S2/S3** — groesstes Wirtsfile der Etappe
(E4-Einschaetzung „Groesster Brocken" bestaetigt), zusaetzlich der
Intra-Gesture-Kollisionsfall (Abschnitt 1.7), der in S2/S3 keine Entsprechung
hatte und ein eigenes, sorgfaeltig gefuehrtes Mutations-Paar braucht (kombiniert
vs. getrennt geschedult).

## 7. Offene Punkte — mitnehmen oder bewusst nicht

- **Entfernen der `onHourlyCommit`/`onOutlookCommit`-Props aus
  `CompareHourlyLayoutControls`/`CompareOutlookLayoutControls`** — optionale
  Anschluss-Aufraeumung (die Props wuerden nach dem reaktiven `$effect` toten
  Code darstellen), NICHT Teil von S4 (Verhaltensneutralitaet vor
  Code-Kosmetik, analog S2s Umgang mit `official_alerts_enabled`).
- **„Toter Zweig" `:577`** (Abschnitt 1.4) — reine Boilerplate-Vereinfachung,
  keine Persistenz-Auswirkung, kann in der Spec als Mini-Punkt mitgenommen
  werden, ist aber keine Pflicht fuer S4s Kern-AC.
- **Fuenf nicht geratschte Compare-E2E-Specs** (`compare-metric-order` u. a.)
  bleiben ausserhalb von `ci_e2e_specs.txt` — S4 validiert sie als
  Regressionsnetz, ratscht aber NUR die eine neue, eigene Spec (S2/S3-Praezedenz,
  Advisor-bestaetigt: Aufnahme aller fuenf waere Scope Creep dieser Scheibe).
- **Vollstaendige Tilgung der Klebeschicht ist Epic-DoD, nicht Scheiben-AC**
  (E1, Gesamtschnitt-Dokument) — Anlege-Pfad (#2277) und Listenseite (#2278)
  bleiben unberuehrt.

## 8. Angenommene, nicht durch PO bestaetigte Entscheidungen

- **Modulort:** bestehendes `shared/weather-metrics-tab/weatherMetricsCompareSave.ts`
  wird erweitert statt ein neues Modul danebengestellt (Begruendung: es ist
  bereits der Ort, an dem die Haelfte der Funktionen liegt UND bereits von
  `compareHubWizardBridge.ts` importiert wird — ein neues Modul wuerde einen
  zweiten Importpfad fuer verwandte Funktionen schaffen). Kann in der
  Spec-Phase korrigiert werden.
- **Reaktiver `$effect` statt drei expliziter Commit-Calls plus drei
  nachgeruesteter Calls an den stillen Mutationsstellen.** Fachlich
  gleichwertig zur imperativen Variante, aber robuster (Abschnitt 3) —
  Entscheidung liegt beim Spec-Writer/Adversary, ob der reaktive Weg oder ein
  imperativer mit sechs benannten Call-Sites gewaehlt wird.
- **Kombinierter Snapshot statt zwei paralleler Selbst-Speicherer** ist KEINE
  offene Frage, sondern eine durch Abschnitt 1.7 belegte Notwendigkeit — hier
  nur der Vollstaendigkeit halber aufgefuehrt, falls der Spec-Writer die
  Begruendung erneut nachvollziehen muss.

## Offene Fragen fuer den PO

Keine — alle offenen Punkte dieser Analyse sind technischer Natur (Modulzuschnitt,
imperativ vs. reaktiv, LoC-Override) und werden in der Spec-Phase entschieden,
nicht vom PO.

## Entwurf Acceptance Criteria (Given/When/Then, fuer `/30-write-spec`)

- **AC-1 (Ein PUT statt bis zu zwei):** Given der Nutzer oeffnet den
  Wetter-Metriken-Reiter eines Ortsvergleichs und aendert eine Einstellung
  (z. B. eine Metrik-Checkbox) / When die Geste abgeschlossen ist / Then
  erscheint „Gespeichert" nach genau einem Speichervorgang — auch wenn
  historisch sowohl die Wetter-Metriken- als auch die Layout-Domaene an
  derselben Geste haengen.
  - Mutations-Gegenprobe: kombinierten Snapshot wieder in zwei getrennte
    `schedule()`-Aufrufe aufteilen ⇒ zwei PUTs bzw. Datenverlust ⇒ Test rot.

- **AC-2 (Intra-Gesture-Kollision — beide Domaenen ueberleben eine
  gemeinsame Geste):** Given der Nutzer aendert eine Metrikauswahl UND —
  innerhalb desselben Debounce-Fensters — eine Stundenverlauf-/Ausblick-
  Einstellung / When beide Aenderungen abgeschlossen sind / Then landet
  GENAU EIN PUT, dessen Body BEIDE Aenderungen traegt — keine ueberschreibt
  die andere.
  - Mutations-Gegenprobe: kombinierten Snapshot in zwei separate
    `schedule()`-Aufrufe aufteilen ⇒ die zuerst geplante Aenderung geht
    verloren (Einzel-Slot-Ueberschreibung) ⇒ Test rot.

- **AC-3 (Hydration vollstaendig vor der ersten Baseline):** Given die beiden
  Katalog-Ladevorgaenge (Wetter-Metriken-Auswahl, Stundenverlauf/Ausblick)
  schliessen zu unterschiedlichen Zeitpunkten ab / When der zweite
  abschliesst / Then entsteht dadurch KEIN Speichervorgang ohne
  vorausgehende Nutzergeste.
  - Mutations-Gegenprobe: Orchestrierung nur an die erste Hydration binden
    (`wetterMetrikenHydrated` statt `wetterMetrikenHydrated && layoutHydrated`)
    ⇒ ein PUT ohne Nutzergeste ist nachweisbar ⇒ Test rot.

- **AC-4 (`activeMetricKeys` wird live gelesen, auch mit gleichzeitiger
  Wertebereiche-Aenderung):** Given der Nutzer aendert die Metrikauswahl im
  Wetter-Metriken-Reiter UND im selben Hub-Besuch zusaetzlich einen
  Wertebereich im Idealwerte-Reiter / When beide gespeichert sind / Then
  traegt der gespeicherte Stand die AKTUELLE Metrikauswahl, unabhaengig
  davon, welcher der beiden Reiter zuletzt gespeichert hat.
  - Mutations-Gegenprobe: `activeMetricKeys` aus einer eingefrorenen
    `preset`-Kopie statt live aus `wiz` befuellen ⇒ Test rot.

- **AC-5 (Drei bisher stille Gesten bleiben wirksam):** Given der Nutzer (a)
  wechselt eine Metrik-Checkbox, (b) den Amtliche-Warnungen-Schalter, oder
  (c) das Tagesfenster Von/Bis, OHNE eine Ziehgeste zu verwenden / When die
  Aenderung abgeschlossen ist / Then wird sie gespeichert — obwohl der
  bisherige Wrapper-Mechanismus entfaellt.
  - Test: drei separate Faelle, je Geste ein eigener Nachweis.
  - Mutations-Gegenprobe je Geste: den Ersatzweg (reaktiver Effect oder
    expliziter Call) fuer genau diese eine Geste entfernen ⇒ der zugehoerige
    Test wird rot, die anderen beiden bleiben gruen (Isolationsnachweis).

- **AC-6 (Reiterwechsel verliert nichts):** Given der Nutzer aendert eine
  Wetter-Metriken-Einstellung und wechselt sofort, vor Ablauf der
  Debounce-Zeit, in den Alarme- oder Idealwerte-Reiter, wo er ebenfalls
  sofort eine Aenderung vornimmt / When beide Aenderungen abgeschlossen sind
  / Then sind BEIDE gespeichert.
  - Mutations-Gegenprobe: `'wetter-metriken'` nicht in
    `SELBST_SPEICHERNDE_VERGLEICH_REITER` aufnehmen ⇒ Test rot.

- **AC-7 (Speicherkonflikt zeigt „Nochmal speichern"):** Given ein
  Wetter-Metriken/Layout-Speichervorgang schlaegt mit einem Speicherkonflikt
  (412) fehl / When der Nutzer „Nochmal speichern" ausloest / Then wird die
  Aenderung erneut gesendet, endet in „Gespeichert", der geaenderte Stand
  bleibt sichtbar.
  - Mutations-Gegenprobe: Rollback auch bei 412 ausloesen ⇒ Test rot.

- **AC-8 (Pausieren/Aktivieren flusht ausstehende Aenderung):** Given der
  Nutzer aendert eine Wetter-Metriken/Layout-Einstellung und pausiert/
  aktiviert den Ortsvergleich sofort danach / When der Vorgang abgeschlossen
  ist / Then ist die Aenderung im gespeicherten Stand enthalten.
  - Mutations-Gegenprobe: den vorab-`flush()`-Aufruf entfernen ⇒ Test rot.

- **AC-9 (Kein Laufzeit-Import der alten Klebeschicht mehr):** Given der
  Wetter-Metriken/Layout-Speicherpfad ist umgestellt / When der Modulgraph
  geladen wird / Then laedt weder `WeatherMetricsTab.svelte` noch
  `weatherMetricsCompareSave.ts` zur Laufzeit ein Modul aus
  `compareHubWizardBridge.ts` — `buildComparePresetSavePayload` aus
  `compareEditorSave.ts` bleibt ausdruecklich erlaubt.
  - Mutations-Gegenprobe: `buildHubPutPayload`-Re-Import einfuegen ⇒
    Ladegraph-Nachweis schlaegt an, Test rot.

- **AC-10 (Anlege-Seite unveraendert):** Given der Nutzer legt einen neuen
  Ortsvergleich an und bearbeitet den Wetter-Metriken-Reiter vor dem ersten
  Speichern / When er die Anlage abschliesst / Then laeuft der Speicherweg
  weiter ausschliesslich ueber `wiz.saveNewPreset()` (POST), ohne
  zwischenzeitlichen PUT.
  - Mutations-Gegenprobe: Aktivierungs-Bedingung der neuen Orchestrierung
    entfernen ⇒ Anlege-Seite loest einen PUT aus ⇒ Test rot.

- **AC-11 (Keepalive-Weiterreichung):** Given der Nutzer schliesst den Tab
  unmittelbar nach einer Wetter-Metriken/Layout-Aenderung / When der Browser
  Keepalive ausloest / Then wird `init` an den PUT durchgereicht.
  - Mutations-Gegenprobe: `init` in der SaveFn ignorieren ⇒ Test rot.

- **AC-12 (Speichern verliert keine anderen Daten):** Given ein
  Ortsvergleich mit Orten, Versandzeiten, Kanaelen, Alarm-Schwellen und
  Wertebereichen / When der Nutzer im Wetter-Metriken-Reiter etwas aendert
  und speichert / Then bleiben alle uebrigen Einstellungen nach erneutem
  Laden unveraendert.
  - Mutations-Gegenprobe: ein Bestandsfeld aus der Payload weglassen ⇒ Test
    rot.

- **AC-13 (Trip-Seite unveraendert):** Given ein Trip mit Wetter-Metriken-
  Konfiguration / When der Nutzer dort etwas aendert / Then laeuft die
  Speicherung weiterhin ueber `scheduleAutoSave`/
  `scheduleReportConfigOnlySave`, unveraendert durch den Umbau am
  Ortsvergleich.
  - Mutations-Gegenprobe: Kontext-Pruefung entfernen, sodass der route-Zweig
    die Vergleichs-Orchestrierung ausloest ⇒ Test rot.

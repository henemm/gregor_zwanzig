# Kontext: Issue #2276 Scheibe S5 — Versand-Reiter speichert selbst

> Analyse-Dokument fuer `/30-write-spec`. Keine Implementierung, keine Spec-Datei.
> Workflow: `rework-2276-s5-versand` (Epic #2345, Issue #2276 bleibt offen bis S6).
> Erhoben 2026-09-20 im Worktree `rework-2276-s5`, Stand `3c14e6e7`.

## 0. Wichtigste Abweichung von der Auftragsannahme

Der Auftrag warnte (aus der S4-Erfahrung) ausdruecklich vor der Moeglichkeit, dass
der Versand-Reiter — wie Wetter-Metriken — **zwei** Domaenen bedient und deshalb
eine kombinierte Orchestrierung braucht. **Das trifft hier NICHT zu.** Der
Versand-Reiter ist architektonisch der **einfachste** der verbleibenden Faelle:
**genau eine** Domaene, **eine** Commit-Funktion (`handleVersandCommit`,
`CompareTabs.svelte:422-468`), **ein** Snapshot-Typ (`VersandSnapshot`,
`compareHubWizardBridge.ts:279-290`) mit 10 Feldern. `VTLaufzeitVergleich`
mutiert zwar `wiz.endDate` per reinem Klick (kein change-/focusout-Event, s.
Abschnitt 1.3) — aber `endDate` ist bereits Teil DESSELBEN `VersandSnapshot`,
keine zweite Domaene. S5 ist damit strukturell naeher an S2 (Alarme,
Ein-Domaene-Fall) als an S4.

## 1. Ist-Zustand (Datei:Zeile, Stand `3c14e6e7`)

### 1.1 Eine Commit-Funktion, ein Wrapper, eine Hub-Queue

`frontend/src/lib/components/compare/CompareTabs.svelte`:

- `currentVersandSnapshot()` (:374-387) liest alle 10 Felder live aus
  `wizardState` (`sendTelegram`, `sendSms`, `morningEnabled`, `morningTime`,
  `eveningEnabled`, `eveningTime`, `endDate`, `alertCooldownMinutes`,
  `alertQuietFrom`, `alertQuietTo`).
- `handleVersandCommit()` (:422-468) — Diff-Guard gegen
  `lastPersistedVersandSnapshot`, PUT ueber `hubPutQueue.enqueue`, Rollback bei
  Fehler (siehe 1.4), `saveController` wird ausschliesslich MANUELL bedient
  (`setSaving`/`setSaved`/`setError`/`markPristine`), NICHT ueber `schedule()`.
- Markup (:1136-1157): `.hub-versand-wrap` (onchange/onfocusout/onclick →
  `handleVersandCommit`) umschliesst `<VersandTab context="vergleich"
  wiz={wizardState} activation={hubActivationCard} />`. Kommentar :1139-1146
  (Staging-Fund SF-1) begruendet `onchange` statt `onchangecapture` — Capture
  liefe vor der eigenen Checkbox-Mutation.
- Kommentar :414-421 (Fix-Loop 1, F001) begruendet zusaetzlich `onclick` am
  Wrapper: `VTLaufzeitVergleich` mutiert `wiz.endDate` bei „Bis auf Weiteres"
  per reinem Button-Klick, der weder `change` noch garantiert `focusout`
  ausloest (WebKit fokussiert Buttons nicht per Klick). Das ist der EINZIGE
  Grund fuer das dritte Wrapper-Event — es handelt sich weiterhin um dasselbe
  `VersandSnapshot`, keine zweite Domaene.

### 1.2 Eine Hydration, kein Doppel-Flag-Problem (Unterschied zu S4)

`hydrateVersandFieldsFromPreset(currentPreset)` (aufgerufen in einem einzigen
`$effect`, :389-407) hydriert alle 10 Felder in EINEM Durchlauf aus EINEM
Katalog-losen Preset-Read (kein async Katalog-Fetch wie bei Wetter-Metriken/
Layout) — es gibt kein Wettlauf-Risiko zwischen zwei Hydrationen. `sendEmail`
ist laut Kommentar (`compareHubWizardBridge.ts:296-298`) IMMER `true`
(`ComparePreset` kennt kein `send_email`-Feld — vorbestehende, dokumentierte
Luecke, nicht Teil dieser Scheibe). Render-Gate im Markup ist ein einzelnes
`{#if versandHydrated}` (:1138) — unproblematisch.

### 1.3 `compareHubWizardBridge.ts` — die Bruchstelle liegt in `buildHubPutPayload`

`VersandSnapshot`/`hydrateVersandFieldsFromPreset`/`flushPendingVersandSave`
liegen komplett in `compare/compareHubWizardBridge.ts:277-343`.
`flushPendingVersandSave` (:324-343) ruft `buildHubPutPayload` (:138-223) —
einen duennen Adapter um `buildComparePresetSavePayload`
(`compare/compareEditorSave.ts:115`), der alle HubEdit-Felder 1:1 durchreicht.
Das ist exakt dieselbe Grenzverletzung, die S2 (AC-9), S3 (AC-7) und S4 (AC-9)
fuer ihre jeweiligen Reiter geschlossen haben — fuer Versand bisher unbemerkt
bestehen geblieben, weil dieser Reiter bislang der einzige verbliebene
Wrapper-Nutzer neben dem laengst aufgeloesten Layout-Halb-Reiter war.

### 1.4 Rollback ist HEUTE unconditioned (kein Diff-Gate wie S2/S3)

`handleVersandCommit` (:444-457) setzt bei einem PUT-Fehler ALLE 10 Felder
bedingungslos auf `before` zurueck — anders als `rollbackAlarmSnapshot`
(`alarmeVergleichSpeicherung.ts:135-160`), das je Feld nur zuruecksetzt, wenn
der State noch exakt den zuletzt GESENDETEN Wert traegt (schuetzt einen
zwischenzeitlichen Edit eines Nachbar-Reiters an einem geteilten Feld). Das
ist fuer S5 relevant, WEIL zwei der zehn Versand-Felder (`sendTelegram`,
`sendSms`) auch vom Alarme-Reiter geschrieben werden (Abschnitt 1.6) — ein
unconditioned Rollback koennte nach einem gescheiterten Versand-PUT eine
zwischenzeitliche Alarme-Aenderung an genau diesen zwei Feldern
stillschweigend zuruecknehmen. Empfehlung: beim Umbau denselben
diff-basierten Rollback wie S2/S3 uebernehmen (echte Verbesserung, nicht nur
Verhaltensneutralitaet).

### 1.5 `saveController`-Prop von `VersandTab.svelte` ist bereits deklariert, aber TOT

`frontend/src/lib/components/shared/VersandTab.svelte:37,56` deklariert
`saveController?: SaveStatus` als Prop, referenziert sie aber NIRGENDS im
Skript-Koerper (verifiziert per Grep — kein zweiter Treffer ausser
Deklaration/Destrukturierung). Der route-Zweig speichert weiterhin ueber den
Eltern-Mechanismus (`BriefingScheduleTab.svelte` → `scheduleAutoSave`/
`scheduleReportConfigOnlySave`, analog S4 AC-13). Fuer S5 heisst das: die neue
Selbst-Speicherung im vergleich-Zweig kann diese bereits vorhandene Prop
tatsaechlich in Betrieb nehmen, ohne ein neues Interface-Feld einzufuehren —
lediglich `preset`/`enqueueHubWrite`/`onCompareUpdate` fehlen noch als Props
(Signatur wie `AlarmeTab`).

### 1.6 Echte Feld-Ueberschneidung: `sendTelegram`/`sendSms` werden von ZWEI Reitern geschrieben

`frontend/src/lib/components/shared/AlarmeTab.svelte:252-263`
(`handleChannelToggle`, vergleich-Zweig) mutiert `wiz.sendTelegram`/
`wiz.sendSms`/`wiz.sendPremiumSms` DIREKT — dieselben Felder, die
`VersandTab.svelte:296-298` (`makeWizChannelHandler`, vergleich-Zweig) fuer
die Briefing-Kanal-Checkboxen mutiert. Das ist eine bewusste, bereits in S2
etablierte Produktentscheidung (Kommentar `AlarmeTab.svelte:230-234`: „vergleich:
bindet an bestehende send_telegram/send_sms" — EIN Kanal-Set fuer Briefing
UND Alarm-Zustellung im Ortsvergleich, anders als beim Trip mit getrennten
`report_config`- und `alert_channels`-Feldern). Strukturell identisch zur
`activeMetricKeys`-Ueberschneidung aus S3/S4: sicher, WEIL `alarmSnapshotAus`
(Alarme-Selbstspeicherer, bereits live) UND die neue Versand-Snapshot-Funktion
BEIDE `wiz.sendTelegram`/`wiz.sendSms` live zum Ausfuehrungszeitpunkt lesen
muessen, nie aus einer eingefrorenen Kopie. `sendPremiumSms` selbst ist KEINE
Ueberschneidung — `VersandTab.svelte` rendert im vergleich-Zweig gar keine
Premium-SMS-Checkbox (:289-302, nur email/telegram/sms; ADR-0049, Premium-SMS
ist im Ortsvergleich kein Versandkanal).

### 1.7 Drei Legacy-Restfelder in `VersandSnapshot`: `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo`

`VersandSnapshot` (`compareHubWizardBridge.ts:279-290`) und
`currentVersandSnapshot()` fuehren zusaetzlich drei Alarm-Zustellungsfelder
mit, obwohl `VersandTab.svelte` seit Issue #1258 Scheibe S4 (Kommentar
:332-334) KEINE UI mehr fuer sie rendert — die komplette
Alert-Zustellungs-Sektion (Cooldown, Stille Stunden) wanderte in
`AlarmeTab.svelte` ab. Diese drei Felder sind im heutigen `VersandSnapshot`
also **tote Rueckreise-Felder**: kein Kontrollelement im Versand-Tab mutiert
sie, sie werden nur zur Round-Trip-Vollstaendigkeit mitgefuehrt (genau wie
`official_alerts_enabled` bei S2, dort als „Legacy-Restfeld" dokumentiert).
Sie werden bereits vom Alarme-Selbstspeicherer exklusiv geschrieben
(`alarmeVergleichSpeicherung.ts:35-37,56-58`). **Empfehlung fuer S5:** aus dem
neuen Versand-Snapshot ENTFERNEN. Der Diskriminator, der das (anders als
`sendTelegram`/`sendSms`, Abschnitt 1.6) unbedenklich macht: KEIN Kontrollelement
im Versand-Tab mutiert diese drei Felder, sie koennen dort also NIE einen Diff
erzeugen — ihr Entfernen aendert nichts an dem, was der Versand-Diff-Guard je
ausloest. Ein theoretisches Restrisiko bleibt trotzdem benennbar: wuerde eine
noch nicht gesendete Alarme-Aenderung an diesen Feldern zufaellig mit einem
Versand-PUT ueberholt, entfiele mit dem Feld auch das (bisher zufaellige)
Mit-Transportieren dieses Zwischenstands — der Reiterwechsel-Flush-Guard
(`sichereSelbstSpeichererVorReiterwechsel`) macht dieses Fenster praktisch
unerreichbar (kein Tab-Wechsel ohne Flush), genau wie S4 das fuer die
sekundaere `channelActiveMetricKeys`-Ueberschneidung dokumentiert hat (S4-Kontext
Abschnitt 1.8) — optionale, aber saubere Aufraeumung, KEIN Pflichtteil.

## 2. Antworten auf die vier Leitfragen

### Frage 1 — Wie viele Domaenen, welche Orchestrierung?

**Genau EINE Domaene.** Alle 10 Felder von `VersandSnapshot`
(`compareHubWizardBridge.ts:279-290`) haengen an EINER Commit-Funktion
(`handleVersandCommit`, `CompareTabs.svelte:422`), die von EINEM
Wrapper-Div ausgeloest wird. `VTLaufzeitVergleich`s `endDate`-Mutation
(`CompareTabs.svelte:414-421`) ist bereits Teil DIESES EINEN Snapshots — das
dritte Wrapper-Event (`onclick`) ist nur ein zusaetzlicher AUSLOESER fuer
denselben Diff-Guard, keine zweite Domaene. S5 braucht folglich **eine**
schlanke `erstelleVersandVergleichSpeicherung()` nach dem S2-Muster
(`erstelleAlarmeVergleichSpeicherung`), KEINE S4-artige
Mehr-Domaenen-Zusammenfuehrung. Der reaktive `$effect`-Ansatz (statt Wrapper)
loest das Button-Klick-Problem aus 1.1 GLEICH mit, weil er auf
State-Aenderungen reagiert, nicht auf DOM-Events — das Fix-Loop-1-Workaround
(`onclick` am Wrapper) entfaellt ersatzlos.

### Frage 2 — Echte Fachunterschiede Trip vs. Vergleich, bleiben die Zweige stehen?

Vier echte, produktiv gewollte Unterschiede bleiben unangetastet, weil S5
NUR den Speicherweg aendert, nicht die Feldauswahl:

1. **Premium-SMS** — nur route-Zweig rendert die Checkbox
   (`VersandTab.svelte:259,266`), ADR-0049.
2. **Mehrtages-Trend** (`multi_day_trend_morning/evening`) — nur route-Zweig
   (:275-276,281-282), kein Vergleichs-Pendant.
3. **Laufzeit-Control**: `VTLaufzeitRoute` (schreibgeschuetzt, aus Etappen
   berechnet, :285) vs. `VTLaufzeitVergleich` (editierbares Enddatum, :325-330).
4. **`activation`-Snippet** (Aktivierungs-Karte) — nur vergleich-Zweig
   (:336-338).

**Empfehlung (begruendet, keine offene Frage): die beiden Markup-Baeume
(:251/:287) bleiben UNVERAENDERT bestehen.** Das sind reine
Fachlichkeits-Verzweigungen (Kanalsatz, Laufzeit-Anzeige,
Aktivierungs-Banner), keine Persistenz-Verzweigungen — identisch zur
Bewertung von `WeatherMetricsTab.svelte`s :1288 in der S4-Analyse
(„Markup-Weiche ... bleibt, weil sie KEINE Persistenz-Verzweigung ist"). Der
einzige Persistenz-relevante Unterschied ist, dass der route-Zweig ueber
`bind:reportConfig` + eigenem `$effect`/`mergeReportConfig` (:130-163)
schreibt, waehrend der vergleich-Zweig direkt in `wiz.*` schreibt — das ist
bereits heute so und bleibt es, S5 aendert nur, WIE der vergleich-Zweig seinen
Zustand persistiert (Wrapper → Selbst-Speicherung), nicht WAS er anzeigt.
Damit ist AC-2 (nur fachliche `context===`-Verzweigungen) fuer S5
strukturell bereits erfuellt, ohne dass eine der vier Weichen angefasst
werden muss.

### Frage 3 — Konkurrenz-Schreibwege im Versand-Tab

1. **Kebab Pausieren/Aktivieren** (`handleToggleActive`,
   `CompareTabs.svelte:711-750`) ruft bereits VOR dem eigenen PUT
   `await saveController?.flush()` (:718) — das ist der GENERISCHE
   Controller-Flush, unabhaengig davon, WELCHER Reiter gerade etwas
   Ausstehendes im Einzel-Slot geplant hat. **Sobald Versand ueber
   `saveController.schedule()` selbst speichert, ist dieser Pfad AUTOMATISCH
   abgedeckt — keine Aenderung an `handleToggleActive` noetig.** Der im
   Auftrag zitierte Kommentar „Race mit handleVersandCommit" (:727,:731)
   bezieht sich auf den HEUTIGEN Zustand (manuelle Controller-Bedienung ohne
   `schedule()`) und wird durch die Umstellung automatisch entschaerft statt
   zusaetzlicher Handarbeit zu brauchen.
2. **Hub-PUT-Queue** (`hubPutQueue`, :203) — die neue Orchestrierung MUSS ihre
   `enqueueHubWrite`-Option auf `(fn) => hubPutQueue.enqueue(fn)` setzen
   (identisches Verdrahtungsmuster wie Alarme/Wertebereiche/Wetter-Metriken),
   damit Versand-PUTs weiterhin mit Orte-/Idealwerte-/Toggle-Active-PUTs
   serialisiert bleiben.
3. **`SELBST_SPEICHERNDE_VERGLEICH_REITER`** (`wertebereicheVergleichSpeicherung.ts:206-210`)
   — **JA, `'versand'` MUSS ergaenzt werden.** Der Reiterwechsel-Guard
   `sichereSelbstSpeichererVorReiterwechsel` (aufgerufen in
   `CompareTabs.svelte:147`, JEDEM Tab-Wechsel) prueft ausschliesslich gegen
   diese Liste — ohne den Eintrag wuerde ein Wechsel WEG vom Versand-Reiter
   eine ausstehende Aenderung NICHT vorab flushen (Datenverlust-Pfad, direktes
   S4-AC-6-Analogon).

### Frage 4 — Umfang/LoC

Siehe Abschnitt 6 (Scoping) unten. Kern-Schaetzung inkl. der drei real
betroffenen Testdateien (Abschnitt 5/6 — zwei davon bauen die alte
`handleVersandCommit`-Logik NACH, nicht nur Import-Swap) liegt spuerbar ueber
dem 250er-Limit. Empfehlung: **`loc_limit_override 500`** (S4-Praezedenz)
gleich zu Workflow-Beginn setzen — ein Domaene-Fall wie S5 braucht zwar
weniger Produktivcode als S4, aber die Testdatei-Rework-Last liegt in
derselben Groessenordnung, ein knapperer Override wuerde die Ueberschreitung
nur mitten in `/50-implement` erneut auf den Tisch bringen.

## 3. Zielbild fuer S5

1. **Neues Modul** `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`
   (Ablage-Empfehlung: direkt in `shared/`, wie `alarmeVergleichSpeicherung.ts`
   — es gibt hier kein bereits existierendes Teil-Modul wie bei S4s
   `weather-metrics-tab/`-Unterordner, das den Ort vorgibt):
   - `VersandSnapshot` (ohne die drei toten Alarm-Restfelder, Abschnitt 1.7 —
     Empfehlung, kein Muss) umgezogen aus `compareHubWizardBridge.ts:279-290`.
   - `versandSnapshotAus(wiz)` (JSON-Rundreise-Kopie, analog `alarmSnapshotAus`).
   - `baueVersandNutzlast(preset, current)` — Voll-Spread ueber
     `buildComparePresetSavePayload` (nicht mehr `buildHubPutPayload`), analog
     `baueAlarmNutzlast`.
   - `flushPendingVersandSave(preset, current, before)` — Diff-Guard,
     umgezogen und auf `baueVersandNutzlast` umgestellt.
   - `rollbackVersandSnapshot(state, before, attempted)` — NEU, diff-basiert
     wie `rollbackAlarmSnapshot` (Abschnitt 1.4 — Verhaltensverbesserung).
   - `erstelleVersandVergleichSpeicherung(opt)` — Signatur wie
     `erstelleAlarmeVergleichSpeicherung`/`erstelleWertebereicheVergleichSpeicherung`:
     `{client, wiz, preset: () => …, enqueueHubWrite, onCompareUpdate,
     saveController} → {aenderungMelden()}`.
   - `hydrateVersandFieldsFromPreset` zieht ebenfalls hierher um (reiner
     Read-Helfer, keine Laufzeitabhaengigkeit zu `compare/` noetig).
2. **`compareHubWizardBridge.ts`**: `VersandSnapshot`/
   `hydrateVersandFieldsFromPreset`/`flushPendingVersandSave` (:277-343)
   entfallen (nach `versandVergleichSpeicherung.ts` umgezogen).
   `buildHubPutPayload` bleibt unveraendert bestehen (wird von Orte-/
   Toggle-Active-Pfaden weiterhin gebraucht).
3. **`VersandTab.svelte`**: neue Props `preset`, `enqueueHubWrite`,
   `onCompareUpdate` (Signatur wie `AlarmeTab`) ergaenzen die bereits
   vorhandene, bisher tote `saveController`-Prop. Ein reaktiver `$effect`
   (Alarme-Muster, `AlarmeTab.svelte:378-389`) ersetzt die Notwendigkeit des
   Wrapper-Divs komplett — er beobachtet alle 10 `wiz.*`-Felder (inkl.
   `endDate`) und deckt damit AUCH den Button-Klick-Fall (`VTLaufzeitVergleich`)
   ab, ohne einen dritten Event-Typ zu brauchen. Die Orchestrierung wird per
   `untrack()`-Konstruktion erzeugt (Aktivierungsbedingung: `context ===
   'vergleich' && wiz && preset && saveController`, identisch zu Alarme).
4. **`CompareTabs.svelte`**: `handleVersandCommit`/`currentVersandSnapshot`/
   `lastPersistedVersandSnapshot` entfallen. Die Hydrations-`$effect`
   (:389-407) bleibt strukturell bestehen (liest weiterhin
   `hydrateVersandFieldsFromPreset` aus `currentPreset`, jetzt aus dem neuen
   Modul importiert) — sie ist der Ort, an dem `wizardState` VOR dem Mount von
   `VersandTab` mit den Preset-Werten befuellt wird, das bleibt unabhaengig
   vom Speicherweg noetig. Wrapper-Div `.hub-versand-wrap` (:1147-1154)
   entfaellt, Mount von `VersandTab` bekommt die drei neuen Props.
5. **`wertebereicheVergleichSpeicherung.ts:206-210`**:
   `SELBST_SPEICHERNDE_VERGLEICH_REITER` um `'versand'` ergaenzen (1 Zeile).
6. **Anlege-Seite unveraendert**: `compare-new/CompareNewEditor.svelte:404,490`
   mountet `VersandTab` weiterhin nur mit `context="vergleich"` `{wiz}`, ohne
   `preset`/`saveController`/`enqueueHubWrite` — Aktivierungsbedingung bleibt
   dort strukturell falsch, Speichern laeuft weiter ueber
   `wiz.saveNewPreset()`.
7. **Trip-Seite unveraendert**: `BriefingScheduleTab.svelte` mountet
   `VersandTab` weiterhin mit `context="route"`, `trip`, `bind:reportConfig`
   — der route-Zweig nutzt die neuen Props gar nicht (sie sind `undefined`),
   die Aktivierungsbedingung der neuen Orchestrierung greift dort strukturell
   nicht (`context !== 'vergleich'`).

## 4. Risiken

1. **`sendTelegram`/`sendSms`-Ueberschneidung mit Alarme (Abschnitt 1.6,
   E3-Pflicht, analog S3/S4).** Live-Read ist die einzige Absicherung fuer
   BEIDE Selbstspeicherer — Mutations-Gegenprobe Pflicht (Versand-Snapshot aus
   einer eingefrorenen `preset`-Kopie statt live aus `wiz` befuellen ⇒ Test
   rot).
2. **Nicht-diff-basierter Rollback heute (Abschnitt 1.4).** Bleibt der
   Rollback beim unconditioned Full-Overwrite (keine Uebernahme des
   S2/S3-Musters), kann ein gescheiterter Versand-PUT eine zwischenzeitliche,
   erfolgreiche Alarme-Aenderung an `sendTelegram`/`sendSms` zuruecknehmen.
   Empfehlung: `rollbackVersandSnapshot` diff-basiert wie `rollbackAlarmSnapshot`
   bauen (Design-Entscheidung, kein Bug-Nachweis noetig, da der heutige
   Wrapper-Pfad denselben Fehler bereits traegt — S5 ist die Gelegenheit, ihn
   mitzunehmen).
3. **`SELBST_SPEICHERNDE_VERGLEICH_REITER` vergessen (Abschnitt Frage 3
   Punkt 3).** Ohne den Eintrag `'versand'` verliert ein Reiterwechsel weg vom
   Versand-Tab eine ausstehende Aenderung lautlos. Mutations-Gegenprobe:
   Eintrag weglassen ⇒ Test rot (direktes S4-AC-6-Analogon).
4. **Drei tote Legacy-Felder (Abschnitt 1.7).** Werden sie NICHT entfernt,
   ist das kein Fehler (Round-Trip bleibt korrekt), aber ein vermeidbarer
   Verwirrungsfaktor im neuen Modul — Empfehlung zur Bereinigung, kein
   Pflicht-AC.
5. **`compare-hub-versand-inline.spec.ts` als vorbestehendes, NICHT
   geratschtes Regressionsnetz (Abschnitt 5).** Es traegt bereits einen
   dokumentierten Lost-Update-Nachweis (F004) und deckt AC-35/36/37/17/18/19
   der urspruenglichen S7-Freigabe (Issue #1256) ab — es MUSS vor
   Spec-Abschluss manuell gegen Staging laufen (eigene Config,
   `playwright.1256-s7.staging.config.ts`, eigener storageState), darf aber
   NICHT blind in die Ratsche aufgenommen werden (ENOENT-Fehler im geteilten
   `global.setup.ts`, dieselbe Klasse wie `issue-579-home-fidelity`,
   dokumentiert in `ci_e2e_specs.txt`).
6. **Anlege-Seite (Abschnitt 3 Punkt 6).** `CompareNewEditor` mountet
   `VersandTab` mit einem LIVE `wiz`, aber ohne `preset`/`saveController` —
   nur deren Fehlen verhindert einen PUT. Mutations-Gegenprobe:
   Aktivierungs-Guard entfernen ⇒ Anlege-Seite muesste einen PUT ausloesen ⇒
   Test wird rot.
7. **Pendant-Frage (geteilter Baustein).** `VersandTab` wird von Trip UND
   Vergleich geteilt, die neue Orchestrierung ist wie bei Alarme/
   Wertebereiche/Wetter-Metriken bewusst NUR fuer den vergleich-Zweig aktiv
   (Trip-Zweig nutzt weiterhin `scheduleAutoSave`/
   `scheduleReportConfigOnlySave` via `BriefingScheduleTab.svelte`,
   unveraendert) — kein Verstoss gegen die Pendant-Sperre.
8. **Cross-User/Mandantentrennung:** unveraendert gegenueber S2/S3/S4 (kein
   neuer Endpoint, derselbe `/api/compare/presets/{id}`-PUT) — nicht
   erwartungswidrig, trotzdem mit zwei Nutzern gegenzupruefen, falls
   unerwartet ein neuer Endpoint-Zweig entstuende (nicht erwartet).
9. **Nicht-Ziel #2275 (Premium-SMS-Versand im Ortsvergleich):** S5 aendert
   NUR den Speicherweg der bestehenden 10 Versand-Felder. Es gibt KEINEN
   Premium-SMS-Kanal im Versand-Tab des Ortsvergleichs (Abschnitt 1.6), S5
   fuehrt keinen ein und verdrahtet keinen Versand fuer #2275.

## 5. Regressionsnetz

**Korrektur gegenueber der ersten Kandidatensuche:** ein Grep auf
`flushPendingVersandSave|VersandSnapshot|hydrateVersandFieldsFromPreset`
liefert fuenf Treffer-Dateien, davon sind aber nur DREI echte Importeure —
`compare_hub_layout_save.test.ts` und `compare_hub_alarme_bridge.test.ts`
erwaehnen diese Namen nur in Kommentaren/Describe-Titeln (Analogie-Referenz),
haben aber KEINEN echten Import und sind daher NICHT betroffen.

| Ebene | Datei | Status |
|---|---|---|
| Kern (Unit) | `compare/__tests__/hub_versand_inline.test.ts` (241 Zeilen) | umzuhaengen (Import-Ziel wechselt auf `versandVergleichSpeicherung.ts`; `hubActivationBanner`-Describe-Block bleibt unveraendert, da diese Funktion in `compareHubWizardBridge.ts` verbleibt) |
| Kern (Unit) | `compare/__tests__/hub_put_queue.test.ts` (235 Zeilen) | ECHTES Rework, kein Import-Swap — baut `handleVersandCommit`/`lastPersistedVersandSnapshot` intern NACH (:121-197), um die Hub-Queue-Serialisierung zu pruefen; muss auf `erstelleVersandVergleichSpeicherung()` umgestellt werden |
| Kern (Unit) | `shared/__tests__/alarme_vergleich_kein_zurueckschreiben.test.ts` (223 Zeilen) | ECHTES Rework, kein Import-Swap — baut denselben `handleVersandCommit`-Ablauf NACH (:134-150), um zu pruefen, dass Alarme- und Versand-Speicherung sich nicht gegenseitig zurueckschreiben (direkt relevant fuer AC-2/AC-3 unten) |
| E2E in Ratsche | `compare-alarme-speichert-selbst.spec.ts`, `compare-wertebereiche-speichert-selbst.spec.ts`, `compare-wetter-metriken-speichert-selbst.spec.ts` (Muster fuer den neuen Test), `versand-tab.spec.ts` (verifiziert: ausschliesslich `context="route"`, keine `vergleich`-Referenz — bleibt unberuehrt) | bleiben gruen |
| E2E NICHT in Ratsche (S5-Regressionsnetz, MUSS vor Abschluss manuell gegen Staging gruen laufen, Aufnahme NICHT Teil dieser Scheibe) | `compare-hub-versand-inline.spec.ts` (eigene Config `playwright.1256-s7.staging.config.ts`, eigener storageState, traegt den F004-Lost-Update-Nachweis) | vor Abschluss gegen Staging gegenlaufen lassen, NICHT zusaetzlich ratschen (dieselbe ENOENT-Klasse wie `issue-579-home-fidelity`, s. `ci_e2e_specs.txt`) |
| E2E NEU | `frontend/e2e/compare-versand-speichert-selbst.spec.ts` (Muster `compare-alarme-speichert-selbst.spec.ts` — EIN Domaene-Fall, kein Intra-Gesture-Test noetig) | anlegen, in `.github/ci_e2e_specs.txt` aufnehmen (nutzt das GETEILTE `global.setup.ts`, KEINE Telegram-chat-id-Vorbedingung — Tests ueber Uhrzeit/Enddatum/SMS-Kanal statt Telegram, um die Staging-Sonderbehandlung aus `compare-hub-versand-inline.spec.ts:17-22` zu vermeiden) |

## 6. Scoping

| Datei | Aenderungsart | Grobschaetzung |
|---|---|---|
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | NEU | +170 |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | AENDERN (VersandSnapshot/hydrateVersandFieldsFromPreset/flushPendingVersandSave raus) | -65 |
| `frontend/src/lib/components/shared/VersandTab.svelte` | AENDERN (3 neue Props, reaktiver `$effect`, Orchestrierungs-Erzeugung) | +40/-3 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | AENDERN (Commit-Funktion + Snapshot-Funktion raus, Wrapper-Div raus, Mount-Props) | +12/-70 |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | AENDERN (+1 Zeile Liste) | +1 |
| `compare/__tests__/hub_versand_inline.test.ts` | UMZUG/ANPASSUNG (Import-Pfad + neue Assertions fuer `rollbackVersandSnapshot`) | +25/-10 |
| `compare/__tests__/hub_put_queue.test.ts` | ECHTES REWORK (Nachbau von `handleVersandCommit` auf `erstelleVersandVergleichSpeicherung()` umstellen) | +35/-45 |
| `shared/__tests__/alarme_vergleich_kein_zurueckschreiben.test.ts` | ECHTES REWORK (dito, plus AC-2/AC-3-Faelle fuer Live-Read/diff-Rollback) | +40/-40 |
| `frontend/e2e/compare-versand-speichert-selbst.spec.ts` | NEU | +220 (zaehlt nicht ins LoC-Limit) |
| `.github/ci_e2e_specs.txt` | AENDERN | +1 Zeile + Kommentarblock (zaehlt nicht) |

**Kern-LoC-Schaetzung (ohne E2E):** ≈ +338/-243 ≈ 581 Summe — hoeher als in
der ersten Einschaetzung, weil zwei der drei betroffenen Testdateien
(`hub_put_queue.test.ts`, `alarme_vergleich_kein_zurueckschreiben.test.ts`)
die alte `handleVersandCommit`-Logik intern nachbauen und deshalb ECHT
umgeschrieben werden muessen, nicht nur ihren Import-Pfad aendern.
Produktivcode bleibt zwar kleiner als bei S4 (ein Domaene-Fall statt zwei),
aber die Testdatei-Last liegt in vergleichbarer Groessenordnung.
**Empfehlung: `loc_limit_override 500`** (S4-Praezedenz, s. Frage 4).
Ueberschreitet der tatsaechliche Diff das spuerbar, gilt dieselbe Regel wie
ueberall: `loc_limit_override` erneut anheben, NICHT die RED-Abdeckung
eigenmaechtig verengen.

**Effort/Risk: MEDIUM** — kleiner als S2/S3/S4 im Codeumfang, aber mit einer
echten Cross-Reiter-Feld-Ueberschneidung (`sendTelegram`/`sendSms` mit
Alarme, Abschnitt 1.6) und einem vorbestehenden, nicht trivial ratschbaren
Regressionsnetz (`compare-hub-versand-inline.spec.ts`), das sorgfaeltig
gegen Staging nachvollzogen werden muss.

## 7. Offene Punkte — mitnehmen oder bewusst nicht

- **Drei tote Alarm-Restfelder aus `VersandSnapshot` entfernen** (Abschnitt 1.7)
  — empfohlene Aufraeumung, KEIN Pflicht-AC (round-trip-neutral so oder so).
- **Diff-basierter Rollback statt Full-Overwrite** (Abschnitt 1.4/Risiko 2) —
  empfohlene Verhaltensverbesserung, sollte in der Spec als Design-Entscheidung
  festgehalten werden (nicht nur optionale Kosmetik, weil sie den
  Cross-Reiter-Datenverlustpfad aus Abschnitt 1.6 schliesst).
- **`compare-hub-versand-inline.spec.ts` in die Ratsche aufnehmen** — NICHT
  Teil von S5 (dieselbe Scope-Disziplin wie S4s fuenf unratschte Specs), aber
  als manueller Staging-Nachweis vor Abschluss zwingend.

## 8. Angenommene, nicht durch PO bestaetigte Entscheidungen

- **Modulort:** neues `shared/versandVergleichSpeicherung.ts` (analog
  `alarmeVergleichSpeicherung.ts`), nicht ein Unterordner wie bei S4 — es gibt
  hier keine bereits existierende Teil-Datei, die den Ort vorgibt. Kann in der
  Spec-Phase korrigiert werden.
- **Reaktiver `$effect` statt explizitem Commit-Call an den drei
  Auslöse-Events.** Fachlich gleichwertig, aber robuster und loest das
  Button-Klick-Sonderproblem strukturell (Abschnitt 3 Punkt 3) — Entscheidung
  liegt beim Spec-Writer/Adversary.
- **Entfernen der drei toten Legacy-Felder** — Empfehlung, kein Muss
  (Abschnitt 7).

## Offene Fragen fuer den PO

Keine — alle offenen Punkte dieser Analyse sind technischer Natur
(Modulzuschnitt, Rollback-Strategie, LoC-Override) und werden in der
Spec-Phase entschieden, nicht vom PO. Insbesondere ist #2275 (Premium-SMS-
Versand im Ortsvergleich) explizit NICHT Gegenstand dieser Scheibe — das ist
bereits durch Epic #2345 entschieden, keine erneute Vorlage noetig.

## Entwurf Acceptance Criteria (Given/When/Then, fuer `/30-write-spec`)

- **AC-1 (Speicherweg laeuft ueber den Controller, nicht mehr ueber den
  Wrapper):** Given der Versand-Reiter ist auf die neue Selbst-Speicherung
  umgestellt (kein `.hub-versand-wrap` mehr im Markup) / When der Nutzer eine
  Einstellung aendert (z. B. den Telegram-Kanal-Schalter) / Then durchlaeuft
  der Speichervorgang nachweislich `saveController.schedule()` (Zustandsuebergang
  `idle → saving → saved` am Controller) und NICHT ein `onchange`/`onfocusout`/
  `onclick`-Ereignis eines umschliessenden Wrapper-Divs — ein Test, der nur
  „irgendein PUT feuert", waere unscharf, weil er auch dann gruen bliebe, wenn
  der alte Wrapper zusaetzlich stehen bliebe.
  - Nachweis: Unit-Test ruft die neue Orchestrierung OHNE das umgebende
    Svelte-Markup auf (reiner Funktionsaufruf auf `wiz`-Mutation +
    `aenderungMelden()`) und prueft den PUT sowie die Controller-Zustaende.
  - Mutations-Gegenprobe: `aenderungMelden()` durch einen No-Op ersetzen ⇒
    Test rot (keine Persistenz mehr) — UND zusaetzlich: wuerde `.hub-versand-wrap`
    versehentlich wieder eingefuehrt, muss ein separater struktureller Test
    (Markup-Assertion „kein Wrapper-Div im Versand-Panel") das fangen, weil
    der reine PUT-Zaehl-Test das nicht unterscheiden kann.

- **AC-2 (`sendTelegram`/`sendSms` werden live gelesen, auch mit
  gleichzeitiger Alarme-Aenderung auf ANDEREN Feldern):** Given der Nutzer
  schaltet im Alarme-Reiter den Telegram-Kanal EIN (`wiz.sendTelegram = true`)
  und speichert / When er DANACH, im selben Hub-Besuch, im Versand-Reiter nur
  die Morgen-Uhrzeit aendert (OHNE den Kanal-Schalter dort erneut zu
  beruehren) und speichert / Then traegt der Versand-PUT-Body weiterhin
  `send_telegram: true` — der vom Alarme-Reiter gesetzte Wert geht NICHT
  verloren, obwohl der Versand-Selbstspeicherer ihn nie selbst geaendert hat.
  - Begruendung fuer diese Formulierung (statt „beide aendern denselben
    Kanal"): ein zweifaches Umschalten DESSELBEN Booleans kehrt zum
    Ausgangswert zurueck und waere am Ergebnis nicht beobachtbar — der Test
    muss auf zwei VERSCHIEDENEN Feldern (hier: `sendTelegram` vs.
    `morning_time`) ansetzen, um den Live-Read tatsaechlich zu pruefen.
  - Mutations-Gegenprobe: `sendTelegram`/`sendSms` im Versand-Snapshot aus
    einer beim Erzeugen der Orchestrierung eingefrorenen Kopie statt live aus
    `wiz` zum Ausfuehrungszeitpunkt befuellen ⇒ Test rot (Versand-PUT
    ueberschreibt `send_telegram` mit dem VOR der Alarme-Aenderung
    eingefrorenen `false`).

- **AC-3 (Diff-basierter Rollback schuetzt Nachbar-Reiter):** Given ein
  Versand-PUT schlaegt fehl, NACHDEM zwischenzeitlich eine
  Alarme-Kanal-Aenderung an `sendTelegram` erfolgreich gespeichert wurde /
  When der Rollback ausgefuehrt wird / Then bleibt die erfolgreich
  gespeicherte Alarme-Aenderung an `sendTelegram` erhalten (wird NICHT auf den
  Versand-Vor-Zustand zurueckgesetzt).
  - Mutations-Gegenprobe: unconditioned Full-Overwrite-Rollback statt
    diff-basiertem Rollback ⇒ Test rot.

- **AC-4 (Reiterwechsel verliert nichts):** Given der Nutzer aendert eine
  Versand-Einstellung und wechselt sofort, vor Ablauf der Debounce-Zeit, in
  den Alarme- oder Idealwerte-Reiter, wo er ebenfalls sofort eine Aenderung
  vornimmt / When beide Aenderungen abgeschlossen sind / Then sind BEIDE
  gespeichert.
  - Mutations-Gegenprobe: `'versand'` nicht in
    `SELBST_SPEICHERNDE_VERGLEICH_REITER` aufnehmen ⇒ Test rot.

- **AC-5 (Button-Klick „Bis auf Weiteres" bleibt wirksam ohne Wrapper):**
  Given der Nutzer klickt im Laufzeit-Control auf „Bis auf Weiteres" (loescht
  ein gesetztes Enddatum), OHNE dass ein `change`- oder `focusout`-Ereignis
  ausgeloest wird / When die Aenderung abgeschlossen ist / Then wird sie
  gespeichert — obwohl der bisherige Wrapper-`onclick`-Mechanismus entfaellt.
  - Mutations-Gegenprobe: den reaktiven Effect so einschraenken, dass er
    `endDate` nicht beobachtet ⇒ Test rot.

- **AC-6 (Speicherkonflikt zeigt „Nochmal speichern"):** Given ein
  Versand-Speichervorgang schlaegt mit einem Speicherkonflikt (412) fehl /
  When der Nutzer „Nochmal speichern" ausloest / Then wird die Aenderung
  erneut gesendet, endet in „Gespeichert", der geaenderte Stand bleibt
  sichtbar.
  - Mutations-Gegenprobe: Rollback auch bei 412 ausloesen ⇒ Test rot.

- **AC-7 (Pausieren/Aktivieren flusht ausstehende Aenderung):** Given der
  Nutzer aendert eine Versand-Einstellung und pausiert/aktiviert den
  Ortsvergleich sofort danach (Aktivierungs-Karte ODER Header-Kebab) / When
  der Vorgang abgeschlossen ist / Then ist die Aenderung im gespeicherten
  Stand enthalten.
  - Mutations-Gegenprobe: den generischen `saveController.flush()`-Aufruf in
    `handleToggleActive` entfernen ⇒ Test rot.

- **AC-8 (Kein Laufzeit-Import der alten Klebeschicht mehr):** Given der
  Versand-Speicherpfad ist umgestellt / When der Modulgraph geladen wird /
  Then laedt weder `VersandTab.svelte` noch `versandVergleichSpeicherung.ts`
  zur Laufzeit ein Modul aus `compareHubWizardBridge.ts` —
  `buildComparePresetSavePayload` aus `compareEditorSave.ts` bleibt
  ausdruecklich erlaubt.
  - Mutations-Gegenprobe: `buildHubPutPayload`-Re-Import einfuegen ⇒
    Ladegraph-Nachweis schlaegt an, Test rot.

- **AC-9 (Anlege-Seite unveraendert):** Given der Nutzer legt einen neuen
  Ortsvergleich an und bearbeitet den Versand-Reiter vor dem ersten Speichern
  / When er die Anlage abschliesst / Then laeuft der Speicherweg weiter
  ausschliesslich ueber `wiz.saveNewPreset()` (POST), ohne zwischenzeitlichen
  PUT.
  - Mutations-Gegenprobe: Aktivierungs-Bedingung der neuen Orchestrierung
    entfernen ⇒ Anlege-Seite loest einen PUT aus ⇒ Test rot.

- **AC-10 (Keepalive-Weiterreichung):** Given der Nutzer schliesst den Tab
  unmittelbar nach einer Versand-Aenderung / When der Browser Keepalive
  ausloest / Then wird `init` an den PUT durchgereicht.
  - Mutations-Gegenprobe: `init` in der SaveFn ignorieren ⇒ Test rot.

- **AC-11 (Speichern verliert keine anderen Daten):** Given ein
  Ortsvergleich mit Orten, Wetter-Metriken, Alarm-Schwellen und
  Wertebereichen / When der Nutzer im Versand-Reiter etwas aendert und
  speichert / Then bleiben alle uebrigen Einstellungen nach erneutem Laden
  unveraendert.
  - Mutations-Gegenprobe: ein Bestandsfeld aus der Payload weglassen ⇒ Test
    rot.

- **AC-12 (Trip-Seite unveraendert):** Given ein Trip mit
  Versand-Konfiguration (Briefing-Kanaele/-Zeitplan) / When der Nutzer dort
  etwas aendert / Then laeuft die Speicherung weiterhin ueber
  `scheduleAutoSave`/`scheduleReportConfigOnlySave`, unveraendert durch den
  Umbau am Ortsvergleich.
  - Mutations-Gegenprobe: Kontext-Pruefung entfernen, sodass der route-Zweig
    die Vergleichs-Orchestrierung ausloest ⇒ Test rot.

---
entity_id: rework_2276_s2_alarme
type: refactor
created: 2026-09-19
updated: 2026-09-19
status: draft
version: "1.0"
tags: [compare, trips, alarme, persistenz]
---

# Alarme-Reiter speichert selbst wie bei der Trip (Issue #2276, Scheibe S2, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich-Hub speichert der Alarme-Reiter heute NICHT für sich selbst,
sondern meldet jede Änderung an einen Sammel-Mechanismus der Seite
(„Wrapper" + `handleAlarmeCommit`), der die Änderung zusammen mit allen
anderen Reitern verwaltet. Bei einer Trip speichert dagegen jeder Reiter
direkt und unabhängig — das ist das Zielbild, auf das der Ortsvergleich
Schritt für Schritt umgestellt wird (Epic #2345). Diese Scheibe stellt den
Alarme-Reiter als ersten von sechs Reitern um. Nutzersichtbarer Nebeneffekt:
schlägt ein Speichervorgang wegen eines zwischenzeitlichen fremden Änderns
fehl (Speicherkonflikt), zeigt der Ortsvergleich künftig „Nochmal speichern"
statt eines generischen Fehlers — genau wie bei der Trip. Am Verhalten der
Anlege-Seite (`/compare/new`) und der übrigen fünf Reiter ändert sich nichts.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/AlarmeTab.svelte`
  (Trip-Speicherweg-Vorbild `buildAlarmeSaveFn()` :302-317, `$effect`
  :331-346),
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts`,
  `frontend/src/routes/compare/[id]/+page.svelte`
- **Identifier:** `AlarmeTab` (Svelte-Organismus), `handleAlarmeCommit`
  (entfällt), `flushPendingAlarmSave`/`rollbackAlarmSnapshot`/`AlarmSnapshot`
  (wandern nach `shared/alarmeVergleichSpeicherung.ts`)

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`, `frontend/src/routes/`, SvelteKit). Kein
Go-API- und kein Python-Core-Code in dieser Scheibe.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/routes/compare/[id]/+page.svelte:59` | MODIFY | `createSaveStatus()` → `createSaveStatus({typ:'vergleich', id})` — Kennung wird übergeben, nie aus der ID abgeleitet (S1-Muster) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Vergleich-Zweig speichert selbst: neue Props `preset`, `onCompareUpdate`, `enqueueHubWrite`; interne Baseline `lastPersistedAlarmSnapshot`; `$effect` mit Diff-Gate vor `saveController.schedule()`, analog zum bestehenden Trip-Zweig (`buildAlarmeSaveFn()` :302-317, `$effect` :331-346) |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | CREATE | Neues Modul unter `shared/`. Übernimmt Snapshot/Diff/Rollback-Logik, die heute als `flushPendingAlarmSave` (`compareHubWizardBridge.ts:613-641`), `rollbackAlarmSnapshot` (`:662-690`) und Typ `AlarmSnapshot` (`:562`) in der Compare-Klebeschicht liegt, plus **eine** Funktion als alleinige Erzeugerin der Alarm-Teilnutzlast (`send_telegram`, `send_sms`, `send_premium_sms`, `alert_channel_thresholds`) — das ist die Nahtstelle, die #2293 austauschen wird, ohne den Rest des Moduls anzufassen |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts:562-690` | MODIFY | `AlarmSnapshot`, `flushPendingAlarmSave`, `rollbackAlarmSnapshot` entfernen (verlagert nach `alarmeVergleichSpeicherung.ts`). **Ausdrücklich unverändert:** `hydrateAlarmFieldsFromPreset` (`:519-555`) bleibt hier — sie setzt neben Alarmfeldern auch `corridors`/`activeMetricKeys` für andere Reiter mit (Deep-Link #1320, Risk 10) und gehört nicht zum Alarm-Speicherpfad |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Drei benannte Entfernungen (kein zusammenhängender Bereich): `currentAlarmSnapshot` (`:566-591`), `handleAlarmeCommit` (`:648-678`), Wrapper-`div` mit change/focusout/click-Handhabung (`:1445-1451`). **Ausdrücklich unverändert:** die Hydrations-`$effect` (`:604-622`) bleibt bestehen — sie speist `hydrateAlarmFieldsFromPreset` und wirkt über den Alarm-Reiter hinaus. Mount des `AlarmeTab` bekommt die neuen Props. `handleValueChange` (`:152-159`, heute kein `flush`) ruft beim Verlassen des Reiters `alarme` `saveController.flush()` (TripTabs-Muster). `handleToggleActive` (`:1014`) ruft `flush()` vorab |
| `frontend/src/lib/components/compare/__tests__/compare_hub_alarme_bridge.test.ts` | MOVE → `frontend/src/lib/components/shared/__tests__/compare_hub_alarme_bridge.test.ts` | Import auf `alarmeVergleichSpeicherung.ts` umgehängt, Zusicherungen unverändert (Radar-Schalter im Body, No-Op-Fall) |
| `frontend/src/lib/components/compare/__tests__/compare_alarme_channel_threshold_save.test.ts` | MOVE → `frontend/src/lib/components/shared/__tests__/compare_alarme_channel_threshold_save.test.ts` | Import umgehängt, Zusicherung (Kanal-Schwellen aller vier Kanäle) unverändert |
| `frontend/src/lib/components/shared/__tests__/telegram_kurzstil_shared_toggle.test.ts` | MODIFY | Kommentar-Referenz auf `flushPendingAlarmSave` folgt dem Modulumzug |
| `frontend/e2e/feat-1745-a-alarm-premium-sms.spec.ts` | MODIFY | Kommentar-Referenz; die Datei läuft laut Kontextdokument (`## Existing Tests`, Stand `58eb84c4`) weiterhin außerhalb der CI-Ratsche, das ändert diese Scheibe nicht |
| neue Unit-Tests (Orchestrierung, s. Test-Plan) | CREATE | Einmal-Speichern, Kein-Zurückschreiben, Lesen-bei-Ausführung, 412-Konflikt/Wiederholen, No-Op, Reiterwechsel-Flush, `init`-Weiterreichung |

`compareEditorSave.ts` (`buildComparePresetSavePayload`, Voll-Spread über
`original`) bleibt unverändert und wird vom neuen Alarm-Zweig weiter als
Nutzlast-Baustein verwendet (s. Design, Punkt 2).

## Estimated Scope

- **LoC:** Quellcode ≈ +150/−120; Tests ≈ +200 (neue Orchestrierungstests
  plus zwei umgehängte Bestandsdateien).
- **Files:** ~10 (4 Produktivdateien inkl. 1 neues Modul, 2 umgehängte
  Testdateien, 2 Kommentarkorrekturen, mehrere neue Testfälle in
  bestehenden/neuen Dateien).
- **Effort:** high. `loc_limit_override 500` ist einzuplanen — Persistenz-
  und Lost-Update-Fläche, kein Nachschneiden der Scheibe.
- **Risk Level:** HIGH (Persistenz, Lost-Update-Fläche, Confirmed durch
  Risiken 1-3 und 5-8 im Kontextdokument).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `createSaveStatus({typ,id})` / `doSave` / `schedule` / `flush` / `retryConflict` (`saveStatusStore.svelte.ts`) | function/class | Speicher-Controller, den der Hub bereits erzeugt (`compare/[id]/+page.svelte:59`) — S2 verdrahtet ihn erstmals wirksam für den Konfliktfall (S1 hat ihn nur entitätsneutral gemacht) |
| `hubPutQueue` (`createPutQueue`, `CompareTabs.svelte:208`) | queue | bleibt bestehen für die übrigen fünf Reiter; der Alarm-PUT läuft über dieselbe Queue (Prop `enqueueHubWrite`), damit sich Alarm- und Nachbar-PUTs nicht überholen (E2, Queue fällt erst in S6) |
| `buildComparePresetSavePayload` (`compareEditorSave.ts:115-270`) | function | liefert weiterhin die Voll-Spread-Basis der Alarm-Nutzlast |
| `applyComparePresetPatch` (Go, `internal/handler/compare_preset.go:292-354`) | function | Merge-Kernel — durch S1 mit Minimal-PUT-Test belegt; hier nicht verändert |
| `NachladeKennung` (`frontend/src/lib/pwa/geraetespeicher.ts:104-105`) | type | Diskriminierungstyp `{typ:'trip'\|'vergleich'; id}`, seit S1 von `createSaveStatus`/`refreshResourceEtag` genutzt |
| `CompareWizardState` (`compareWizardState.svelte.ts`) | type (nur `import type`) | `shared/` importiert weiterhin ausschließlich den **Typ** aus `compare/` (6 Bestandsstellen) — keine neue Laufzeitabhängigkeit; das neue Modul `alarmeVergleichSpeicherung.ts` hält sich an dieselbe Regel |
| `TripTabs.svelte:145-182` (`handleValueChange`, `flush()` beim Reiterwechsel) | pattern | Vorbild für den neuen `flush()`-Aufruf in `CompareTabs.handleValueChange` |

## Implementation Details

### Design-Entscheidungen (Empfehlung Plan-Agent, Advisor-korrigiert)

1. **Serialisierung über die bestehende Hub-Queue (Option A), kein zweiter
   Controller.** Die Alarm-SaveFn läuft über `hubPutQueue.enqueue` (Prop
   `enqueueHubWrite`, kein zweites `createPutQueue`) und setzt nach Erfolg
   `currentPreset` über die neue Prop `onCompareUpdate` — in derselben
   Kette. Damit bleibt die F002/F003-Zusicherung („Basis wird erst bei
   Ausführung gelesen") gültig; die Queue fällt erst in S6 (E2,
   Kontextdokument). Präzedenz: `CorridorEditor.svelte:229`
   (`saveController?.schedule(async (init) => …)`). Ein Alarm-PUT am
   Queue vorbei (Option B) würde sich mit den Voll-Spread-PUTs der
   übrigen fünf Reiter überholen.
2. **Nutzlast bleibt Voll-Spread** (`buildComparePresetSavePayload`), wie
   alle übrigen fünf Hub-Handler. Der Go-Merge-Kernel merged
   `display_config` nur auf Ebene 1 (Kontextdokument, Risiko 2/E3) — ein
   Teil-PUT, das nur die Alarm-Unterschlüssel von `display_config` sendet,
   würde bei gleichzeitiger Existenz eines zweiten Reiters, der denselben
   Ebene-1-Schlüssel (`metric_alert_levels`) schreibt, einen echten
   Verlustpfad öffnen. Voll-Spread macht diesen Verlustpfad in S2
   strukturell unerreichbar, statt ihn nur unwahrscheinlich zu machen —
   das ist der tragende Grund, nicht nur „zwei Konventionen im selben Hub
   erhöhen das Risiko ohne Gewinn". `metric_alert_levels` und
   `telegram_style` werden vollständig gesendet (E3 erfüllt für diesen
   Reiter).
3. **No-Op-Entscheid VOR `schedule()`.** `doSave()` ruft nach der SaveFn
   unbedingt `setSaved()` — ein `markPristine()` innerhalb der SaveFn wäre
   wirkungslos. Der `$effect` prüft den Diff gegen
   `lastPersistedAlarmSnapshot` (nicht gegen einen reinen
   Effekt-Zuletzt-Wert — beide divergieren nach einem Fehlschlag oder
   einer Nachbar-Bearbeitung an geteilten Feldern); ohne Diff wird
   `markPristine()` aufgerufen, `schedule()` bleibt aus.
4. **Rollback nur bei Nicht-412.** Bei einem Speicherkonflikt (412) bleibt
   `wiz` unverändert stehen, sonst würde `retryConflict()` eine leere
   Differenz senden und fälschlich „Gespeichert" melden.
5. **Flush beim Reiterwechsel** (TripTabs-Muster, `handleValueChange`) und
   zusätzlich vor `handleToggleActive` (`:1014`) — beide Stellen können
   sonst eine noch nicht gesendete Alarm-Änderung verlieren.
6. **Anlege-Seite bleibt unverändert.** `/compare/new`
   (`CompareNewEditor.svelte:412/499`) mountet `AlarmeTab` ohne `preset`
   und ohne `saveController` — der neue Speicherzweig bleibt dort
   strukturell inaktiv, Speichern läuft weiter über
   `wiz.saveNewPreset()` (POST).
7. **`init`-Weiterreichung (Keepalive, Risiko 12).** Die SaveFn-Signatur
   ist wie beim Trip-Vorbild `(init?: RequestInit) => Promise<void>` — der
   `init`-Parameter (Entladen-Fall, `sendBeacon`/Keepalive) MUSS an den
   `api.put`-Aufruf durchgereicht werden, sonst bricht ein Alarm-Save beim
   Schließen des Tabs lautlos ab. Vorbild:
   `trip_speicherung_reicht_keepalive_durch.test.ts`.

### Modul-Verschiebung `shared/alarmeVergleichSpeicherung.ts`

Die Alarm-Helfer (`flushPendingAlarmSave`, `rollbackAlarmSnapshot`,
`AlarmSnapshot`, heute in `compare/compareHubWizardBridge.ts:562-690`)
ziehen in ein neues Modul unter `frontend/src/lib/components/shared/`.
Begründung: `shared/` hat heute nur **Typ**-Importe aus `compare/`
(`CompareWizardState`, 6 Stellen) — keine Laufzeitabhängigkeit auf die
Compare-Klebeschicht. Ein Alarm-Organismus unter `shared/`, der zur
Laufzeit ein Modul aus `compare/` importiert, würde diese Grenze zum
ersten Mal durchbrechen. Die beiden Bestandstests
(`compare_hub_alarme_bridge.test.ts`,
`compare_alarme_channel_threshold_save.test.ts`) ziehen mit um nach
`shared/__tests__/` und werden dort umbenannt — ihre Zusicherungen bleiben
unverändert, nur der Import zeigt neu auf `alarmeVergleichSpeicherung.ts`.
`frontend-test` läuft über `npm test` ohne feste Dateiliste (`node --test`,
`package.json:13`) — das Verschieben/Umbenennen von Testdateien kostet
keine CI-Konfigurationsänderung.

### Annahme mit Test, nicht Behauptung

**Annahme:** Die Alarm-SaveFn liest die Basis (`preset`-Prop bzw.
`currentPreset`) erst bei **Ausführung** in der Queue, nicht beim
Einreihen — weil Svelte-5-Props als Getter durchgereicht werden und die
Closure den aktuellen Wert zum Ausführungszeitpunkt liest. Diese Annahme
wird durch einen eigenen Test bewiesen (s. Test-Plan, Fall „Lesen erst bei
Ausführung"), nicht vorausgesetzt. **Fallback, falls der Test das
Gegenteil zeigt:** Sollte sich zeigen, dass die Basis beim Einreihen
einfriert (z. B. weil `preset` an einer Stelle destrukturiert statt als
Prop-Zugriff gehalten wird), wird die Basis stattdessen über einen
expliziten Getter (`() => preset`) statt eines direkten Werts
weitergegeben — die betroffene Acceptance Criteria (AC-3) und ihr Test
bleiben davon unberührt, nur die interne Umsetzung ändert sich.

## Expected Behavior

- **Input:** Änderung eines Alarm-Feldes im Ortsvergleich-Hub (z. B.
  Radar-Schalter, Kanal-Schwelle, Kurzstil-Schalter, Ruhezeiten).
- **Output:** genau ein PUT auf `/api/compare/presets/{id}` mit der
  vollständigen, aktuellen Preset-Nutzlast; Anzeige „Gespeichert"; die
  aktualisierte Basis fließt über `onCompareUpdate` in `currentPreset`
  zurück, sodass der nächste PUT eines anderen Reiters die neuen
  Alarmwerte trägt.
- **Side effects:** bei einem Speicherkonflikt (412) wechselt der
  Speicher-Controller in den Zustand `conflict`, die Oberfläche zeigt
  „Nochmal speichern"; ein Klick darauf sendet die unveränderte
  Alarm-Änderung erneut und endet in „Gespeichert". Ohne inhaltliche
  Änderung (reines Öffnen/Schließen des Reiters, Wert hin und zurück)
  entsteht kein PUT und keine neue „Gespeichert"-Meldung.

## Acceptance Criteria

- **AC-1 (Einmal speichern, ohne Wrapper):** Given der Nutzer öffnet den
  Alarme-Reiter eines Ortsvergleichs und ändert einen Alarm-Wert / When die
  Änderung abgeschlossen ist / Then erscheint „Gespeichert" nach genau
  einem PUT, ohne dass der Wrapper (`hub-alarme-wrap`) oder
  `handleAlarmeCommit` beteiligt sind.
  - Test: neuer Unit-Test, der `AlarmeTab` im `vergleich`-Kontext mit
    `saveController`/`enqueueHubWrite`/`onCompareUpdate` mountet, einen
    Alarm-Wert ändert und am abgefangenen Netzverkehr **genau einen** PUT
    auf `/api/compare/presets/{id}` mit dem geänderten Wert zählt; der
    Controller-Zustand endet in `saved`.
  - Mutations-Gegenprobe: `saveController.schedule(...)` im
    Vergleich-Zweig entfernen ⇒ kein PUT ⇒ rot; SaveFn zweimal auslösen
    ⇒ zwei PUTs ⇒ rot.

- **AC-2 (Kein Zurückschreiben alter Alarmwerte):** Given eine
  Alarm-Änderung wurde soeben gespeichert / When danach ein anderer Reiter
  (Versand oder Wertebereiche) ebenfalls einen PUT auslöst / Then trägt
  der abgefangene Request-Body dieses **zweiten** PUT die neuen
  Alarmwerte, nicht die alten.
  - Test: Assertion auf den tatsächlich abgefangenen Body des zweiten
    PUT gegen einen Ersatz-Server, der den Stand **ersetzt statt zu
    mergen** (`fakeTripServer.ts:150`) — der Servergleichsstand allein
    beweist nichts, weil der Fake ohnehin jedes Feld annimmt.
  - Mutations-Gegenprobe: `onCompareUpdate` weglassen ⇒ dieser Test wird
    rot.

- **AC-3 (Basis wird bei Ausführung gelesen, nicht beim Einreihen):**
  Given zwei Alarm-Speichervorgänge werden kurz hintereinander in die
  Queue eingereiht / When die Basis (`preset`) zwischen dem Einreihen des
  ersten und der Ausführung des zweiten geändert wird / Then sieht die
  zweite Closure den neuen Wert der Basis.
  - Test: neuer Unit-Test mit zwei eingereihten Schreibvorgängen und
    einer Basis-Änderung dazwischen, Assertion auf den Inhalt des zweiten
    PUT-Bodys.
  - Mutations-Gegenprobe: Basis beim Einreihen kopieren (statt per
    Getter/Prop-Zugriff zu lesen) ⇒ Test wird rot.

- **AC-4 (Speicherkonflikt zeigt „Nochmal speichern", Wiederholen
  gelingt):** Given ein Alarm-Speichervorgang schlägt mit einem
  Speicherkonflikt (412) fehl / When der Nutzer „Nochmal speichern"
  auslöst / Then wird die Änderung erneut gesendet, endet in
  „Gespeichert", und die geänderten Alarm-Werte bleiben in der Oberfläche
  sichtbar (kein Zurückspringen auf den alten Stand).
  - Test: Erweiterung der bestehenden Konflikt-Suite (S1-Fundament) um
    einen Fall, der über `AlarmeTab`/`onCompareUpdate` bis zum
    `retryConflict()`-Aufruf durchgeht. Geprüft wird: (a) nach dem 412 steht
    der Controller auf `conflict` (nicht `error`) — das ist nur mit der
    Kennung `{typ:'vergleich', id}` aus `routes/compare/[id]/+page.svelte`
    möglich; (b) der Body des Wiederholungs-PUT enthält den geänderten Wert;
    (c) Endzustand `saved`.
  - Mutations-Gegenprobe (zusätzlich): Controller wieder ohne Kennung
    erzeugen ⇒ Zustand `error` statt `conflict` ⇒ rot.
  - Mutations-Gegenprobe: Rollback auch bei 412 auslösen (statt nur bei
    Nicht-412) ⇒ Test wird rot, weil die Änderung nach dem Konflikt
    verschwindet statt erhalten zu bleiben.

- **AC-5 (No-Op stempelt kein „Gespeichert"):** Given der Nutzer öffnet
  den Alarme-Reiter, ändert nichts oder ändert einen Wert und dann wieder
  zurück auf den Ausgangswert / When der `$effect` läuft / Then entsteht
  kein PUT und keine neue „Gespeichert"-Meldung mit neuem Zeitstempel.
  - Test: neuer Unit-Test, der nach No-Op-Interaktion die Abwesenheit
    eines PUT-Aufrufs und eine unveränderte `savedAt`-Markierung prüft.
  - Mutations-Gegenprobe: `schedule()` ohne vorheriges Diff-Gate gegen
    `lastPersistedAlarmSnapshot` aufrufen ⇒ Test wird rot.

- **AC-6 (Reiterwechsel flusht ausstehende Änderung):** Given der Nutzer
  ändert einen Alarm-Wert und wechselt sofort, vor Ablauf der
  Debounce-Zeit, in den Versand-Reiter / When der Reiterwechsel
  stattfindet / Then wird die Alarm-Änderung vor dem Wechsel gesendet,
  nicht verloren.
  - Test: neuer Unit-Test/erweiterter `CompareTabs`-Test, der eine
    Änderung setzt, `handleValueChange` mit Zielreiter `versand` aufruft
    und die vorherige Ausführung der Alarm-SaveFn prüft.
  - Mutations-Gegenprobe: `flush()`-Aufruf beim Reiterwechsel entfernen
    ⇒ Test wird rot.

- **AC-7 (Anlege-Seite unverändert):** Given der Nutzer legt einen neuen
  Ortsvergleich an und bearbeitet den Alarme-Reiter vor dem ersten
  Speichern / When er die Anlage abschließt / Then läuft der Speicherweg
  weiter ausschließlich über `wiz.saveNewPreset()` (POST), ohne
  zwischenzeitlichen PUT und ohne den neuen `saveController`-Zweig.
  - Test: bestehende Struktur-/Mount-Tests für die Anlege-Seite bleiben
    unverändert grün (Mount ohne `preset`/`saveController` bewirkt, dass
    der neue Zweig inaktiv bleibt).

- **AC-8 (Bestandsverhalten der umgehängten Tests bleibt erhalten):**
  Given Radar-Schalter, Kanal-Schwellen und Kurzstil-Schalter werden im
  Ortsvergleich gesetzt / When gespeichert wird / Then landen sie im
  gespeicherten Stand wie vor dieser Scheibe.
  - Test: die beiden nach `shared/__tests__/` umgezogenen Bestandstests
    (`compare_hub_alarme_bridge.test.ts`,
    `compare_alarme_channel_threshold_save.test.ts`) laufen unverändert
    grün, nur mit neuem Import.

- **AC-9 (Kein Laufzeit-Importeur der alten Klebeschicht mehr):** Given
  der Alarm-Speicherpfad ist umgestellt / When der Modulgraph geladen wird
  / Then lädt `shared/AlarmeTab.svelte` zur Laufzeit kein Modul aus
  `compare/` (die Alarm-Helfer kommen aus
  `shared/alarmeVergleichSpeicherung.ts`). Dass der Hub nicht mehr über
  `handleAlarmeCommit`/`hub-alarme-wrap` speichert, belegt AC-1 (genau ein
  PUT) — hier wird es nicht erneut geprüft.
  - Test: Ladegraph-Nachweis über `node --test`
    (`--experimental-test-module-mocks`, `package.json:13`) — ein Mock auf
    `compareHubWizardBridge.ts`, der einen Ladeaufruf protokolliert, plus
    ein Render von `AlarmeTab` im `vergleich`-Kontext; der Mock darf beim
    Rendern nicht aufgerufen werden. Ein reiner Dateiinhalt-/Grep-Check
    ist als Nachweis ausgeschlossen (CLAUDE.md-Verbot). `import type
    { CompareWizardState }`-Stellen bleiben zulässig — die Regel betrifft
    ausschließlich Laufzeitabhängigkeiten.
  - Mutations-Gegenprobe: einen Laufzeit-Re-Import von
    `flushPendingAlarmSave` aus der alten Bridge-Datei in `AlarmeTab.svelte`
    einfügen ⇒ der Mock-Ladenachweis schlägt an, Test wird rot.

- **AC-10 (Keepalive-Weiterreichung):** Given der Nutzer schließt den Tab
  unmittelbar nach einer Alarm-Änderung / When der Browser den
  Entladen-Vorgang mit Keepalive auslöst / Then wird der `init`-Parameter
  der SaveFn an den `api.put`-Aufruf durchgereicht, statt verworfen zu
  werden.
  - Test: Erweiterung analog zu
    `trip_speicherung_reicht_keepalive_durch.test.ts`, angewandt auf die
    Alarm-SaveFn im `vergleich`-Kontext.
  - Mutations-Gegenprobe: `init` in der SaveFn ignorieren (fester
    `undefined`-Aufruf an `api.put`) ⇒ Test wird rot.

## Bewusste Abweichungen / Known Limitations

- **`official_alerts_enabled` wird weiter mitgesendet.** Das Feld bedient
  `AlarmeTab` seit D2 fachlich nicht mehr, der Hub-Stand sendet es aber
  weiterhin — Verhaltensneutralität geht in dieser Scheibe vor; Rückbau
  ist für S4/S6 vorgesehen (widerspricht bewusst dem Wunsch nach sofortiger
  Bereinigung aus Risiko 7 des Kontextdokuments, wird dort aber
  ausdrücklich zurückgestellt).
- **Gemischter Controller-Betrieb bis S3–S6.** Die übrigen fünf
  Hub-Handler (Korridor, Versand, Wetter-Metriken, Layout, Kopfzeile
  Name/Region/Profil) rufen `setSaving()`/`setSaved()`/`setError()`
  weiterhin direkt statt über `doSave()`/`schedule()` — ein ausstehendes
  `schedule()` des Alarm-Zweigs kann optisch von einem direkten Aufruf
  eines anderen Reiters überdeckt werden (Risiko 6, Kontextdokument),
  bis alle Reiter umgestellt sind.
- **Kopfzeile (Name/Region/Profil) bleibt außen vor.**
  `routes/compare/[id]/+page.svelte` schreibt sie per eigenem
  Voll-Spread aus dem seiteneigenen `currentPreset` — vorbestehend, nicht
  durch diese Scheibe verursacht, wird durch die Umstellung aber
  sichtbarer (Risiko 11).
- **`alert_channels` kommt erst mit #2293.** Bis dahin sendet der
  Alarm-Zweig weiterhin die flachen `send_telegram`/`send_sms`/
  `send_premium_sms`-Felder; die Nutzlast-Bildung ist so geschnitten
  (eine einzelne Funktion in `alarmeVergleichSpeicherung.ts`), dass #2293
  ausschließlich diese Funktion ersetzt.
- **F004-Lost-Update-E2E bleibt außerhalb der CI-Ratsche.** Laut
  Kontextdokument (`## Existing Tests`, Stand `58eb84c4`) ist
  `compare-hub-versand-inline` (trägt F004) nicht in
  `.github/ci_e2e_specs.txt` — S1 hat das nicht aufgenommen, S2 ändert
  daran nichts; der Nachweis für den Alarm-Reiter läuft ausschließlich
  über die Kern-Unit-Tests dieser Spec.
- **`hydrateAlarmFieldsFromPreset` bleibt in der Compare-Klebeschicht.**
  Sie setzt neben Alarmfeldern auch `corridors`/`activeMetricKeys` für
  andere Reiter (Deep-Link #1320) und wird deshalb bewusst NICHT nach
  `shared/` verschoben — nur der reine Speicherpfad (Snapshot/Flush/
  Rollback) zieht um.
- **Vollständige Tilgung der Klebeschicht ist Epic-DoD, nicht Scheiben-AC**
  (E1, Kontextdokument): Anlege-Pfad (#2277) und Listenseite (#2278)
  bleiben unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe setzt die in E2/E3 des Kontextdokuments
  bereits getroffenen Entscheidungen um (Hub-Queue bleibt bis S6, Voll-
  Spread-Nutzlast wegen `display_config`-Ebene-1-Merge) und verallgemeinert
  keinen neuen Diskriminierungstyp — sie nutzt `NachladeKennung` und die
  in S1 bereitgestellte, entitätsneutrale `refreshResourceEtag`/
  `createSaveStatus`-Kennung. Die Modulverschiebung nach `shared/` ändert
  keine Entscheidungsfläche, sondern verschärft eine bestehende Regel
  (nur Typ-Importe aus `compare/` in `shared/`).

## Changelog

- 2026-09-19: Initial spec created
- 2026-09-19: Implementierung + Adversary-Fix-Loop abgeschlossen. F005 (Nachspeicher-Schleife nach erfolgreichem PUT, falls waehrend des Requests eine weitere Aenderung eingetroffen ist) behoben; neue E2E-Spec `frontend/e2e/compare-alarme-speichert-selbst.spec.ts` belegt die Verdrahtung (Reiterwechsel-Flush, Aktivieren/Pausieren-Flush, „Nochmal speichern" bei 412) und ist in der CI-E2E-Ratsche aufgenommen. F006 als Folgebefund an #2366 uebergeben (nicht Teil dieser Scheibe).

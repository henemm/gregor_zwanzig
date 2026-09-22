---
entity_id: rework_2276_s5_versand
type: refactor
created: 2026-09-20
updated: 2026-09-20
status: draft
version: "1.0"
tags: [compare, trips, versand, persistenz]
---

# Versand-Reiter speichert selbst wie bei der Tour (Issue #2276, Scheibe S5, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich-Hub speichert der Versand-Reiter heute nicht für sich
selbst, sondern meldet jede Änderung an einen Sammel-Mechanismus der Seite
(Wrapper-Div `.hub-versand-wrap` + `handleVersandCommit`), der die Änderung
zusammen mit allen anderen Reitern verwaltet. Bei einer Tour speichert
dagegen jeder Reiter direkt und unabhängig — das ist das Zielbild, auf das
der Ortsvergleich Schritt für Schritt umgestellt wird (Epic #2345). Diese
Scheibe stellt den Versand-Reiter als vierten von sechs Reitern um.
Architektonisch ist S5 der **einfachste** verbleibende Fall: genau **eine**
Domäne, eine Commit-Funktion, ein Snapshot-Typ — S5 ist damit strukturell
näher an S2 (Alarme) als an S4 (Wetter-Metriken/Layout, zwei kombinierte
Domänen). Nutzersichtbarer Nebeneffekt: schlägt ein Speichervorgang wegen
eines zwischenzeitlichen fremden Änderns fehl (Speicherkonflikt), zeigt der
Ortsvergleich künftig „Nochmal speichern" statt eines generischen Fehlers —
genau wie bei der Tour. Zusätzlich wird der bisher unbedingte
(„unconditioned") Rollback bei einem fehlgeschlagenen Versand-PUT durch einen
diff-basierten Rollback ersetzt (Abschnitt „Implementation Details", Punkt
3) — eine bewusste Verhaltensänderung, kein reines Verschieben von Code. Am
Verhalten der Anlege-Seite (`/compare/new`) und der Trip-Seite ändert sich
nichts.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/VersandTab.svelte`,
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts`
- **Identifier:** `handleVersandCommit`/`currentVersandSnapshot` (entfallen),
  `VersandSnapshot`/`hydrateVersandFieldsFromPreset`/
  `flushPendingVersandSave` (wandern nach
  `shared/versandVergleichSpeicherung.ts`), neue Orchestrierung
  `erstelleVersandVergleichSpeicherung()`

Betroffene Schicht: ausschließlich **Frontend**
(`frontend/src/lib/components/`, `frontend/src/routes/`, SvelteKit). Kein
Go-API- und kein Python-Core-Code in dieser Scheibe.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | CREATE | Neues Modul unter `shared/` (analog `alarmeVergleichSpeicherung.ts` — kein bereits existierendes Teil-Modul wie bei S4 gibt hier den Ort vor). Enthält `VersandSnapshot` (10 Felder, umgezogen aus `compareHubWizardBridge.ts:279-290`, **inklusive** der drei Legacy-Restfelder `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` — Nicht-Ziel, siehe Implementation Details Punkt 6), `versandSnapshotAus(wiz)` (JSON-Rundreise-Kopie), `baueVersandNutzlast(preset, current)` (Voll-Spread über `buildComparePresetSavePayload`, `compare/compareEditorSave.ts`, NICHT mehr über `buildHubPutPayload`), `flushPendingVersandSave(preset, current, before)` (Diff-Guard), `rollbackVersandSnapshot(state, before, attempted)` (NEU, diff-basiert wie `rollbackAlarmSnapshot` — Verhaltensänderung, s. Implementation Details Punkt 3), `erstelleVersandVergleichSpeicherung(opt)` (Signatur wie `erstelleAlarmeVergleichSpeicherung`: `{client, wiz, preset: () => …, enqueueHubWrite, onCompareUpdate, saveController} → {aenderungMelden()}`), `hydrateVersandFieldsFromPreset` (reiner Read-Helfer, zieht ebenfalls hierher um) |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | Drei neue Props `preset`, `enqueueHubWrite`, `onCompareUpdate` (Signatur wie `AlarmeTab`) ergänzen die bereits deklarierte, bisher tote `saveController`-Prop (`:37,56` — verifiziert per Grep, keine zweite Verwendung außer Deklaration/Destrukturierung). Ein reaktiver `$effect` (Alarme-Muster, `AlarmeTab.svelte:378-389`) beobachtet alle 10 `wiz.*`-Felder (inklusive `endDate`) und ruft bei Diff `aenderungMelden()` — ersetzt den Wrapper-Div vollständig UND deckt den Button-Klick-Sonderfall von `VTLaufzeitVergleich` ab (kein `change`-/`focusout`-Ereignis bei „Bis auf Weiteres"), ohne einen dritten Event-Typ zu brauchen. Aktivierungsbedingung der Orchestrierungs-Erzeugung (per `untrack()`-Konstruktion): `context === 'vergleich' && wiz && preset && saveController`, identisch zu `AlarmeTab`. Beide Markup-Bäume (`:251`/`:287`) bleiben strukturell unverändert — Branch-Liste s. Implementation Details Punkt 4 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | `handleVersandCommit` (:422-468), `currentVersandSnapshot` (:374-387), `lastPersistedVersandSnapshot` entfallen. Die Hydrations-`$effect` (:389-407) bleibt strukturell bestehen (liest weiterhin `hydrateVersandFieldsFromPreset`, jetzt aus dem neuen Modul importiert) — sie befüllt `wizardState` vor dem Mount, das bleibt unabhängig vom Speicherweg nötig. Wrapper-Div `.hub-versand-wrap` (:1136-1157, inkl. Kommentare zu SF-1 und F001) entfällt vollständig. Mount von `VersandTab` bekommt die drei neuen Props. `SELBST_SPEICHERNDE_VERGLEICH_REITER` (`wertebereicheVergleichSpeicherung.ts:206-210`) wird um `'versand'` ergänzt — `handleToggleActive` (:711-750) ruft bereits generisch `saveController?.flush()` vor dem eigenen PUT und braucht keine Anpassung, sobald Versand über `schedule()` läuft |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | MODIFY | `VersandSnapshot`/`hydrateVersandFieldsFromPreset`/`flushPendingVersandSave` (:277-343) entfernt (nach `versandVergleichSpeicherung.ts` umgezogen). `buildHubPutPayload` (:138-223) bleibt unverändert bestehen — wird von Orte-/Toggle-Active-Pfaden weiterhin gebraucht |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | `SELBST_SPEICHERNDE_VERGLEICH_REITER` um `'versand'` ergänzt (1 Zeile) |
| `frontend/src/lib/components/compare/__tests__/hub_versand_inline.test.ts` | MOVE/ANPASSUNG | Import-Ziel wechselt auf `versandVergleichSpeicherung.ts`, neue Assertions für `rollbackVersandSnapshot` (diff-basiert). `hubActivationBanner`-Describe-Block bleibt unverändert (Funktion verbleibt in `compareHubWizardBridge.ts`) |
| `frontend/src/lib/components/compare/__tests__/hub_put_queue.test.ts` | ECHTES REWORK, kein Import-Swap | Baut heute `handleVersandCommit`/`lastPersistedVersandSnapshot` intern nach (:121-197), um die Hub-Queue-Serialisierung zu prüfen — wird auf `erstelleVersandVergleichSpeicherung()` umgestellt |
| `frontend/src/lib/components/shared/__tests__/alarme_vergleich_kein_zurueckschreiben.test.ts` | ECHTES REWORK, kein Import-Swap | Baut heute denselben `handleVersandCommit`-Ablauf intern nach (:134-150), um zu prüfen, dass Alarme- und Versand-Speicherung sich nicht gegenseitig zurückschreiben — wird umgestellt UND um die Fälle Live-Read (AC-2) und diff-basierter Rollback (AC-3) erweitert |
| `frontend/e2e/compare-versand-speichert-selbst.spec.ts` | CREATE | Muster `compare-alarme-speichert-selbst.spec.ts` — ein Domäne-Fall, kein Intra-Gesture-Test nötig. Läuft über das geteilte `global.setup.ts`, testet über Uhrzeit/Enddatum/SMS-Kanal statt Telegram (keine chat-id-Sonderbehandlung nötig). Für den 412-Konflikt-Fall (AC-6) speichert die Spec zuerst selbst einmal erfolgreich, bevor sie den Konflikt provoziert — der erste PUT nach SSR läuft ohne `If-Match` (#2375), ein Konflikt-Test direkt danach würde einen Effekt messen, der nicht am Versand-Speicherweg liegt |
| `.github/ci_e2e_specs.txt` | MODIFY | neue Spec aufnehmen, `E2E_MIN_SPECS` entsprechend anheben — nur diese eine neue Spec wird geratscht, NICHT `compare-hub-versand-inline.spec.ts` (s. Known Limitations) |

`compareEditorSave.ts` (`buildComparePresetSavePayload`, Voll-Spread über
`original`) bleibt unverändert und wird vom neuen Versand-Zweig weiter als
Nutzlast-Baustein verwendet — identische Begründung wie S2/S3/S4 (Go-Merge-
Kernel mergt `display_config` nur auf Ebene 1).

## Estimated Scope

- **LoC:** Kern-Quellcode (ohne E2E) ≈ +338/−243 ≈ 581 Summe — höher als der
  Produktivcode-Umfang allein vermuten ließe, weil zwei der drei betroffenen
  Testdateien (`hub_put_queue.test.ts`,
  `alarme_vergleich_kein_zurueckschreiben.test.ts`) die alte
  `handleVersandCommit`-Logik intern nachbauen und deshalb echt umgeschrieben
  werden müssen, nicht nur ihren Import-Pfad ändern. E2E-Datei (~+220) zählt
  laut Konvention nicht ins LoC-Limit. **`loc_limit_override 500` ist zu
  Workflow-Beginn zu setzen** (S2/S4-Präzedenz).
- **Files:** ~6 Produktivdateien (1 neues Modul, 1 Svelte-Komponente, 2
  Hub-Klebeschicht-/Compare-Dateien, 1 Guard-Liste, 1 CI-Ratschen-Datei) + 3
  umgehängte/umgebaute Kern-Tests + 1 neue E2E-Spec.
- **Effort:** medium — kleiner als S4 (eine Domäne statt zwei), aber die
  Testdatei-Rework-Last liegt in vergleichbarer Größenordnung wie bei S2/S4.
- **Risk Level:** MEDIUM. Kleiner im Codeumfang als S2/S3/S4, aber mit einer
  echten Cross-Reiter-Feld-Überschneidung (`sendTelegram`/`sendSms` mit
  Alarme) und einem vorbestehenden, nicht trivial ratschbaren
  Regressionsnetz (`compare-hub-versand-inline.spec.ts`), das sorgfältig
  gegen Staging nachvollzogen werden muss (Pflichtschritt, s. Known
  Limitations).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `createSaveStatus({typ,id})` / `doSave` / `schedule` / `flush` / `retryConflict` (`saveStatusStore.svelte.ts`) | function/class | Geteilter Speicher-Controller der Route; wird für den Versand-Reiter erstmals wirksam verdrahtet |
| `hubPutQueue` (`createPutQueue`, `CompareTabs.svelte:203`) | queue | bleibt bestehen für die übrigen Reiter; der Versand-PUT läuft über dieselbe Queue (Prop `enqueueHubWrite`), damit sich Versand- und Nachbar-PUTs nicht überholen |
| `buildComparePresetSavePayload` (`compareEditorSave.ts:115`) | function | liefert weiterhin die Voll-Spread-Basis der Versand-Nutzlast |
| `erstelleAlarmeVergleichSpeicherung`/`erstelleWertebereicheVergleichSpeicherung`/`erstelleWetterMetrikenVergleichSpeicherung` (S2/S3/S4, live) | pattern | Vorbild für Modulform und Aufruf-Signatur der neuen Orchestrierung — S5 folgt strukturell dem EIN-Domäne-Muster von S2, nicht der Mehr-Domäne-Zusammenführung aus S4 |
| `AlarmeTab.svelte` reaktiver `$effect` (S2) | pattern | Vorbild für den reaktiven Ersatz des Wrapper-Divs; deckt auch den Button-Klick-Sonderfall von `VTLaufzeitVergleich` ab, weil er auf State-Änderungen reagiert, nicht auf DOM-Ereignisse |
| `rollbackAlarmSnapshot` (`alarmeVergleichSpeicherung.ts:135-160`) | function | Vorbild für `rollbackVersandSnapshot` — diff-basiert statt unconditioned, schützt Nachbar-Reiter-Änderungen an geteilten Feldern |
| `SELBST_SPEICHERNDE_VERGLEICH_REITER` / `sichereSelbstSpeichererVorReiterwechsel` (`wertebereicheVergleichSpeicherung.ts:206-210`) | function/list | wird um `'versand'` ergänzt, kein neuer Guard nötig |
| `AlarmeTab.svelte:252-263` (`handleChannelToggle`, vergleich-Zweig) | component | schreibt DIREKT auf `wiz.sendTelegram`/`wiz.sendSms` — dieselben Felder, die `VersandTab` für die Briefing-Kanal-Checkboxen mutiert (Abschnitt „Cross-Reiter-Überschneidung", s. Implementation Details Punkt 2) |
| `CompareWizardState` (`compareWizardState.svelte.ts`) | type (nur `import type`) | `shared/` importiert weiterhin ausschließlich den **Typ** aus `compare/` — keine neue Laufzeitabhängigkeit |
| `CompareNewEditor.svelte` (Anlege-Seite) | component | mountet `VersandTab` weiterhin ohne `preset`/`saveController`/`enqueueHubWrite` — Aktivierungsbedingung der neuen Orchestrierung bleibt dort strukturell falsch, Speichern läuft über `wiz.saveNewPreset()` |
| `BriefingScheduleTab.svelte` (Trip-Seite) | component | mountet `VersandTab` weiterhin mit `context="route"`, `trip`, `bind:reportConfig` — nutzt die neuen Props nicht, Aktivierungsbedingung greift dort strukturell nicht |

## Implementation Details

### Design-Entscheidungen

1. **Eine schlanke Orchestrierung, keine Mehr-Domänen-Zusammenführung wie
   S4.** Alle 10 Felder von `VersandSnapshot` hängen an EINER
   Commit-Funktion, ausgelöst von EINEM Wrapper. `VTLaufzeitVergleich`s
   `endDate`-Mutation ist bereits Teil DIESES EINEN Snapshots — das dritte
   Wrapper-Event (`onclick`, Fix-Loop 1/F001) war nur ein zusätzlicher
   Auslöser für denselben Diff-Guard, keine zweite Domäne. S5 braucht
   folglich **eine** `erstelleVersandVergleichSpeicherung()` nach dem
   S2-Muster. Der reaktive `$effect`-Ansatz löst das Button-Klick-Problem
   strukturell mit, weil er auf State-Änderungen reagiert statt auf
   DOM-Ereignisse — das Wrapper-`onclick`-Workaround entfällt ersatzlos.
2. **`sendTelegram`/`sendSms` MÜSSEN live aus `wiz` gelesen werden, nie aus
   einer eingefrorenen `preset`-Kopie.** `AlarmeTab.svelte:252-263`
   (vergleich-Zweig) mutiert dieselben zwei Felder direkt — eine bewusste,
   bereits in S2 etablierte Produktentscheidung (EIN Kanal-Set für Briefing
   UND Alarm-Zustellung im Ortsvergleich, anders als beim Trip mit
   getrennten `report_config`-/`alert_channels`-Feldern). Sicher ist die
   Überschneidung nur, wenn BEIDE Selbstspeicherer (Alarme UND Versand) den
   Wert live zum Ausführungszeitpunkt lesen — strukturell identisch zur
   `activeMetricKeys`-Überschneidung aus S3/S4. `sendPremiumSms` ist KEINE
   Überschneidung, weil `VersandTab` im vergleich-Zweig keine Premium-SMS-
   Checkbox rendert (ADR-0049, Premium-SMS ist im Ortsvergleich kein
   Versandkanal).
3. **Diff-basierter Rollback ersetzt den heutigen Full-Overwrite-Rollback —
   entschiedene Verhaltensänderung, nicht Verhaltensneutralität.**
   `handleVersandCommit` setzt heute bei einem PUT-Fehler bedingungslos ALLE
   10 Felder auf den Vor-Zustand zurück, unabhängig davon, ob sich ein Feld
   zwischenzeitlich anderswo geändert hat. Weil `sendTelegram`/`sendSms`
   auch vom Alarme-Reiter geschrieben werden (Punkt 2), könnte ein
   unconditioned Rollback nach einem gescheiterten Versand-PUT eine
   zwischenzeitliche, erfolgreiche Alarme-Änderung an genau diesen zwei
   Feldern stillschweigend zurücknehmen (Datenverlust-Klasse
   BUG-DATALOSS-GR221). `rollbackVersandSnapshot` wird deshalb wie
   `rollbackAlarmSnapshot` gebaut: je Feld nur zurücksetzen, wenn der State
   noch exakt den zuletzt GESENDETEN Wert trägt. Grund für die Aufnahme in
   diese Scheibe statt Rückstellung: der heutige Wrapper-Pfad trägt denselben
   Fehler bereits, S5 ist die Gelegenheit, ihn beim ohnehin fälligen Umbau
   mitzunehmen, statt ihn unter neuem Namen weiterzutragen.
4. **Beide Markup-Bäume (`VersandTab.svelte:251`/`:287`) bleiben
   unverändert — vier fachliche `context===`-Verzweigungen, keine
   Persistenz-Verzweigung.** Verifiziert per Grep: genau zwei
   `context ===`-Bedingungen im Skript (`:251` `'route'`, `:287`
   `'vergleich'`), keine weitere. Die vier fachlichen Unterschiede
   innerhalb dieser zwei Bäume, mit Begründung (Branch-Liste für Issue-AC-2 /
   Epic-DoD-1, damit S6 kein unbegrenztes Audit erbt):
   1. **Premium-SMS-Kanal** (`:259,266`, nur route-Zweig) — ADR-0049, im
      Ortsvergleich existiert kein Premium-SMS-Versandkanal.
   2. **Mehrtages-Trend** (`multi_day_trend_morning`/`_evening`, `:275-276,
      281-282`, nur route-Zweig) — kein Vergleichs-Pendant, weil der
      Ortsvergleich keinen mehrtägigen Trip-Verlauf kennt.
   3. **Laufzeit-Control**: `VTLaufzeitRoute` (`:285`, schreibgeschützt, aus
      Etappen berechnet) vs. `VTLaufzeitVergleich` (`:325-330`, editierbares
      Enddatum) — unterschiedliche fachliche Datenquelle für dieselbe
      Anzeigefläche.
   4. **`activation`-Snippet** (`:336-338`, nur vergleich-Zweig) —
      Aktivierungs-Karte existiert nur im Ortsvergleich-Hub, nicht auf der
      Trip-Seite.

   Der einzige persistenz-relevante Unterschied ist, dass der route-Zweig
   über `bind:reportConfig` + eigenem `$effect`/`mergeReportConfig` schreibt,
   während der vergleich-Zweig direkt in `wiz.*` schreibt — das ist bereits
   heute so und bleibt es; S5 ändert nur, WIE der vergleich-Zweig seinen
   Zustand persistiert (Wrapper → Selbst-Speicherung), nicht WAS er anzeigt.
5. **Nutzlast bleibt Voll-Spread** über `buildComparePresetSavePayload` —
   wie S2/S3/S4, wegen des Go-Merge-Kernels, der `display_config` nur auf
   Ebene 1 mergt.
6. **Die drei toten Legacy-Felder `alertCooldownMinutes`/`alertQuietFrom`/
   `alertQuietTo` bleiben im `VersandSnapshot` UND im Payload — explizites
   Nicht-Ziel, nicht optionale Bereinigung.** Kein Kontrollelement im
   Versand-Tab mutiert diese drei Felder (die Alert-Zustellungs-Sektion
   wanderte in Issue #1258 Scheibe S4 vollständig nach `AlarmeTab.svelte`
   ab); sie werden bereits vom Alarme-Selbstspeicherer exklusiv geschrieben
   (`alarmeVergleichSpeicherung.ts:35-37,56-58`). Solange der Go-Handler ein
   PUT ins volle Modell dekodiert (ein Patch-DTO ist erst mit #2285
   vorgesehen), würde ein Versand-PUT, der diese drei Felder aus der
   Nutzlast entfernt, sie bei einem Bestands-Preset auf den Server-Default
   NULLEN — ein Datenverlustpfad an Alarm-Zustellungsfeldern, ausgelöst
   durch einen Speichervorgang, der mit Alarm-Zustellung fachlich nichts zu
   tun hat. Entfernung dieser Felder gehört an S6/#2285, sobald das
   Patch-DTO existiert.
7. **`init`-Weiterreichung (Keepalive) bleibt erhalten** — die SaveFn-
   Signatur reicht `init` an `api.put` durch, analog S2/S3/S4.
8. **Anlege-Seite und Trip-Seite bleiben unverändert** — die neue
   Orchestrierung ist bewusst NUR für den `vergleich`-Zweig aktiv (Trip nutzt
   weiterhin `scheduleAutoSave`/`scheduleReportConfigOnlySave` über
   `BriefingScheduleTab.svelte`); kein Verstoß gegen die Pendant-Sperre,
   weil `VersandTab` bereits der geteilte Baustein ist, den Trip und
   Vergleich gemeinsam nutzen.
9. **Nicht-Ziel #2275 (Premium-SMS-Versand im Ortsvergleich).** S5 ändert
   nur den Speicherweg der bestehenden 10 Versand-Felder. Es gibt keinen
   Premium-SMS-Kanal im Versand-Tab des Ortsvergleichs (Punkt 2), S5 führt
   keinen ein und verdrahtet keinen Versand für #2275 — bereits durch Epic
   #2345 entschieden, keine erneute Vorlage nötig.
10. **Kein Laufzeit-Import aus `compareHubWizardBridge.ts` mehr** — weder
    `VersandTab.svelte` noch `versandVergleichSpeicherung.ts` laden zur
    Laufzeit ein Modul aus der Klebeschicht; ein Laufzeit-Import von
    `buildComparePresetSavePayload` aus `compareEditorSave.ts` bleibt
    ausdrücklich erlaubt.

## Expected Behavior

- **Input:** Änderung einer Einstellung im Versand-Reiter des
  Ortsvergleich-Hubs (Briefing-Kanal-Checkbox, Uhrzeit, Mehrtages-Trend
  entfällt hier — nur route; Laufzeit-Enddatum).
- **Output:** genau EIN PUT auf `/api/compare/presets/{id}` mit der
  vollständigen, aktuellen Preset-Nutzlast (inklusive der drei
  Legacy-Restfelder, Punkt 6); Anzeige „Gespeichert"; die aktualisierte
  Basis fließt über `onCompareUpdate` in `currentPreset` zurück.
- **Side effects:** bei einem Speicherkonflikt (412) wechselt der
  Speicher-Controller in den Zustand `conflict`, die Oberfläche zeigt
  „Nochmal speichern". Schlägt ein Versand-PUT aus einem anderen Grund fehl,
  werden nur die Felder zurückgesetzt, die noch exakt den zuletzt gesendeten
  Wert tragen (diff-basierter Rollback, Punkt 3) — eine zwischenzeitlich
  erfolgreich gespeicherte Alarme-Änderung an `sendTelegram`/`sendSms` bleibt
  erhalten. Wechselt der Nutzer den Reiter oder pausiert/aktiviert den
  Ortsvergleich, während eine Versand-Änderung noch nicht gesendet wurde,
  wird sie vorher automatisch gesendet.

## Acceptance Criteria

- **AC-1 (Speicherweg läuft über den Controller, nicht mehr über den
  Wrapper):** Given der Versand-Reiter ist auf die neue Selbst-Speicherung
  umgestellt (kein `.hub-versand-wrap` mehr im Markup) / When der Nutzer eine
  Einstellung ändert (z. B. den Telegram-Kanal-Schalter) / Then durchläuft
  der Speichervorgang nachweislich `saveController.schedule()`
  (Zustandsübergang `idle → saving → saved` am Controller) und nicht ein
  `onchange`-/`onfocusout`-/`onclick`-Ereignis eines umschließenden
  Wrapper-Divs.
  - Nachweisschicht: Kern (Unit-Test ruft die neue Orchestrierung ohne das
    umgebende Svelte-Markup auf — reiner Funktionsaufruf auf
    `wiz`-Mutation + `aenderungMelden()` — und prüft PUT sowie
    Controller-Zustände; zusätzlich ein struktureller Markup-Test „kein
    Wrapper-Div im Versand-Panel").
  - Mutations-Gegenprobe: `aenderungMelden()` durch einen No-Op ersetzen ⇒
    Test rot (keine Persistenz mehr); würde `.hub-versand-wrap` versehentlich
    wieder eingeführt, fängt das der separate Markup-Test.

- **AC-2 (`sendTelegram`/`sendSms` werden live gelesen, auch mit
  gleichzeitiger Alarme-Änderung auf demselben Feld):** Given der Nutzer
  schaltet im Alarme-Reiter den SMS-Kanal ein (`wiz.sendSms = true`) und
  speichert / When er danach, im selben Hub-Besuch, im Versand-Reiter nur
  die Morgen-Uhrzeit ändert (ohne den Kanal-Schalter dort erneut zu
  berühren) und speichert / Then trägt der Versand-PUT-Body weiterhin
  `send_sms: true` — der vom Alarme-Reiter gesetzte Wert geht nicht
  verloren, obwohl der Versand-Selbstspeicherer ihn nie selbst geändert hat.
  - Nachweisschicht: Kern (Integrationstest über beide Reiter im selben
    Wizard-Zustand, `alarme_vergleich_kein_zurueckschreiben.test.ts`).
  - Mutations-Gegenprobe: `sendSms`/`sendTelegram` im Versand-Snapshot aus
    einer beim Erzeugen der Orchestrierung eingefrorenen Kopie statt live aus
    `wiz` zum Ausführungszeitpunkt befüllen ⇒ Test rot (Versand-PUT
    überschreibt `send_sms` mit dem vor der Alarme-Änderung eingefrorenen
    `false`).

- **AC-3 (Diff-basierter Rollback schützt Nachbar-Reiter):** Given ein
  Versand-PUT schlägt fehl, nachdem zwischenzeitlich eine
  Alarme-Kanal-Änderung an `sendTelegram` erfolgreich gespeichert wurde /
  When der Rollback ausgeführt wird / Then bleibt die erfolgreich
  gespeicherte Alarme-Änderung an `sendTelegram` erhalten (wird nicht auf
  den Versand-Vor-Zustand zurückgesetzt).
  - Nachweisschicht: Kern (Unit-Test auf `rollbackVersandSnapshot`).
  - Mutations-Gegenprobe: unconditioned Full-Overwrite-Rollback statt
    diff-basiertem Rollback ⇒ Test rot.

- **AC-4 (Reiterwechsel verliert nichts):** Given der Nutzer ändert eine
  Versand-Einstellung und wechselt sofort, vor Ablauf der Debounce-Zeit, in
  den Alarme- oder Idealwerte-Reiter, wo er ebenfalls sofort eine Änderung
  vornimmt / When beide Änderungen abgeschlossen sind / Then sind beide
  gespeichert.
  - Nachweisschicht: Kern (erweiterter `CompareTabs`-Test).
  - Mutations-Gegenprobe: `'versand'` nicht in
    `SELBST_SPEICHERNDE_VERGLEICH_REITER` aufnehmen ⇒ Test rot.

- **AC-5 (Button-Klick „Bis auf Weiteres" bleibt wirksam ohne Wrapper):**
  Given der Nutzer klickt im Laufzeit-Control auf „Bis auf Weiteres"
  (löscht ein gesetztes Enddatum), ohne dass ein `change`- oder
  `focusout`-Ereignis ausgelöst wird / When die Änderung abgeschlossen ist /
  Then wird sie gespeichert — obwohl der bisherige Wrapper-`onclick`-
  Mechanismus entfällt.
  - Nachweisschicht: Kern (Unit-Test auf den reaktiven `$effect` mit
    `endDate`-Mutation ohne begleitendes DOM-Ereignis).
  - Mutations-Gegenprobe: den reaktiven Effect so einschränken, dass er
    `endDate` nicht beobachtet ⇒ Test rot.

- **AC-6 (Speicherkonflikt zeigt „Nochmal speichern"):** Given ein
  Versand-Speichervorgang schlägt mit einem Speicherkonflikt (412) fehl /
  When der Nutzer „Nochmal speichern" auslöst / Then wird die Änderung
  erneut gesendet, endet in „Gespeichert", der geänderte Stand bleibt
  sichtbar.
  - Nachweisschicht: Kern (Erweiterung der bestehenden Konflikt-Suite) + E2E
    (`compare-versand-speichert-selbst.spec.ts`, echter 412 gegen Staging;
    die Spec speichert zuvor selbst einmal erfolgreich, weil der erste PUT
    nach SSR ohne `If-Match` läuft, #2375 — ein Konflikt-Test unmittelbar
    nach SSR würde sonst einen Effekt messen, der nicht am
    Versand-Speicherweg liegt).
  - Mutations-Gegenprobe: Rollback auch bei 412 auslösen ⇒ Test rot.

- **AC-7 (Pausieren/Aktivieren flusht ausstehende Änderung):** Given der
  Nutzer ändert eine Versand-Einstellung und pausiert/aktiviert den
  Ortsvergleich sofort danach (Aktivierungs-Karte oder Header-Kebab) / When
  der Vorgang abgeschlossen ist / Then ist die Änderung im gespeicherten
  Stand enthalten.
  - Nachweisschicht: Kern (Unit-Test auf `handleToggleActive()`).
  - Mutations-Gegenprobe: den generischen `saveController.flush()`-Aufruf in
    `handleToggleActive` entfernen ⇒ Test rot.

- **AC-8 (Kein Laufzeit-Import der alten Klebeschicht mehr):** Given der
  Versand-Speicherpfad ist umgestellt / When der Modulgraph geladen wird /
  Then lädt weder `VersandTab.svelte` noch `versandVergleichSpeicherung.ts`
  zur Laufzeit ein Modul aus `compareHubWizardBridge.ts` —
  `buildComparePresetSavePayload` aus `compareEditorSave.ts` bleibt
  ausdrücklich erlaubt.
  - Nachweisschicht: Kern (Ladegraph-Nachweis über `node --test`
    `--experimental-test-module-mocks`, analog S2 AC-9/S4 AC-9).
  - Mutations-Gegenprobe: `buildHubPutPayload`-Re-Import einfügen ⇒
    Ladegraph-Nachweis schlägt an, Test rot.

- **AC-9 (Anlege-Seite unverändert):** Given der Nutzer legt einen neuen
  Ortsvergleich an und bearbeitet den Versand-Reiter vor dem ersten
  Speichern / When er die Anlage abschließt / Then läuft der Speicherweg
  weiter ausschließlich über `wiz.saveNewPreset()` (POST), ohne
  zwischenzeitlichen PUT.
  - Nachweisschicht: Kern (bestehende Struktur-/Mount-Tests bleiben grün).
  - Mutations-Gegenprobe: Aktivierungs-Bedingung der neuen Orchestrierung
    entfernen ⇒ Anlege-Seite löst einen PUT aus ⇒ Test rot.

- **AC-10 (Keepalive-Weiterreichung):** Given der Nutzer schließt den Tab
  unmittelbar nach einer Versand-Änderung / When der Browser Keepalive
  auslöst / Then wird der `init`-Parameter der SaveFn an den `api.put`-
  Aufruf durchgereicht, statt verworfen zu werden.
  - Nachweisschicht: Kern (analog
    `trip_speicherung_reicht_keepalive_durch.test.ts`).
  - Mutations-Gegenprobe: `init` in der SaveFn ignorieren (fester
    `undefined`-Aufruf an `api.put`) ⇒ Test rot.

- **AC-11 (Speichern verliert keine anderen Daten, inklusive der drei
  Legacy-Restfelder):** Given ein Ortsvergleich mit Orten, Wetter-Metriken,
  Alarm-Schwellen, Wertebereichen und gesetzten Werten für
  `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` / When der Nutzer im
  Versand-Reiter etwas ändert und speichert / Then bleiben alle übrigen
  Einstellungen einschließlich dieser drei Legacy-Restfelder nach erneutem
  Laden unverändert (kein Nullen durch den Versand-PUT).
  - Nachweisschicht: Kern (Payload-Test auf `baueVersandNutzlast`) + E2E
    (GET vor/nach, Feldvergleich).
  - Mutations-Gegenprobe: `alertCooldownMinutes`/`alertQuietFrom`/
    `alertQuietTo` aus `baueVersandNutzlast` entfernen ⇒ Test rot (Felder
    werden im Payload-Vergleich vermisst bzw. nullen sich im
    Round-Trip-Test).

- **AC-12 (Trip-Seite unverändert):** Given ein Trip mit
  Versand-Konfiguration (Briefing-Kanäle/-Zeitplan) / When der Nutzer dort
  etwas ändert / Then läuft die Speicherung weiterhin über
  `scheduleAutoSave`/`scheduleReportConfigOnlySave`, unverändert durch den
  Umbau am Ortsvergleich.
  - Nachweisschicht: Kern (bestehende Trip-Tests bleiben grün, neuer
    Kern-Test, dass der route-Zweig die Vergleichs-Orchestrierung nicht
    aufruft).
  - Mutations-Gegenprobe: Kontext-Prüfung entfernen, sodass der route-Zweig
    die Vergleichs-Orchestrierung auslöst ⇒ Test rot.

## Known Limitations

- **`compare-hub-versand-inline.spec.ts` als Pflicht-Staging-Nachweis, kein
  Ratschen-Kandidat.** Diese vorbestehende Spec bewacht AC-35/36/37/17/18/19
  der ursprünglichen S7-Freigabe (Issue #1256) samt dokumentiertem
  Lost-Update-Nachweis (F004), ist aber nicht in `.github/ci_e2e_specs.txt`
  ratschbar (ENOENT im geteilten `global.setup.ts`, dieselbe Fehlerklasse
  wie `issue-579-home-fidelity`). Da S5 den Speicherweg unter ihr wegbaut,
  ist ein manueller Lauf dieser Spec gegen Staging (eigene Config
  `playwright.1256-s7.staging.config.ts`, eigener storageState) **Pflicht
  vor Spec-/Scheiben-Abschluss**, nicht optional. Die ENOENT-Ursache selbst
  ist ein Sammel-Befund (#1199), nicht Teil dieser Scheibe.
- **Drei tote Legacy-Felder bleiben bewusst erhalten** (Implementation
  Details Punkt 6) — Nicht-Ziel dieser Scheibe, Entfernung gehört an
  S6/#2285, sobald der Go-Handler ein Patch-DTO statt Voll-Dekodierung
  verwendet.
- **Nicht-Ziel #2275 (Premium-SMS-Versand im Ortsvergleich)** — S5 ändert
  nur den Speicherweg, führt keinen neuen Versandkanal ein.
- **Gemischter Controller-Betrieb bis S6.** Die verbleibende
  Hub-Kopfzeile (Name/Region/Profil) ruft weiterhin `setSaving()`/
  `setSaved()`/`setError()` direkt statt über `doSave()`/`schedule()` — nach
  S5 sind 4 von 6 Reitern auf Selbst-Speicherung umgestellt (Alarme,
  Wertebereiche, Wetter-Metriken/Layout, Versand).
- **Vollständige Tilgung der Klebeschicht ist Epic-DoD, nicht Scheiben-AC**
  — Anlege-Pfad (#2277) und Listenseite (#2278) bleiben unberührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe wendet das in S2/S3/S4 etablierte Muster
  (Hub-Queue bleibt bis S6, Voll-Spread-Nutzlast wegen
  `display_config`-Ebene-1-Merge, `shared/` importiert nur Typen aus
  `compare/`, listenbasierter Flush-Guard) auf den vierten Reiter an —
  strukturell näher an S2 (eine Domäne) als an S4 (zwei kombinierte
  Domänen). Die Entscheidung, den Rollback von unconditioned auf
  diff-basiert umzustellen, ist eine Anwendung des bereits in S2/S3
  etablierten Rollback-Musters auf einen Reiter, der bisher davon
  abgewichen ist — keine neue Entscheidungsfläche. Die Entscheidung, die
  drei Legacy-Restfelder NICHT zu entfernen, ist durch die bestehende
  Persistenz-Regel „Read-Modify-Write mit Merge, niemals Replace"
  (CLAUDE.md, BUG-DATALOSS-GR221) bereits gedeckt, solange der Go-Handler
  kein Patch-DTO verwendet.

## Changelog

- 2026-09-20: Initial spec created

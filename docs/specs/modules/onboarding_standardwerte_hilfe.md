---
entity_id: onboarding_standardwerte_hilfe
type: module
created: 2026-10-17
updated: 2026-10-17
status: draft
version: "1.0"
workflow: feat-2521-s3-standardwerte-hilfe
tags: [frontend, python-test, onboarding, standardwerte, hilfe, hilfeseite, anlegeLockEngine, i18n, textkatalog, issue-2521, s3]
---

# Mit Standardwerten speichern und Hilfeseite (Onboarding S3)

## Approval

- [ ] Approved (PO-Freigabe ausstehend: ACs auf Deutsch lesen, dann `approved` bzw. `freigabe`)

## Purpose

Letzte Scheibe von Issue #2521. Teil A: In den Anlege-Editoren für Trip (`/trips/new`) und Ortsvergleich (`/compare/new`) gibt es einen zusätzlichen Knopf „Mit Standardwerten speichern", sobald die Pflichtangaben da sind. Heute muss ein neuer Nutzer jeden hinteren Reiter einmal öffnen, bevor er speichern kann. Der neue Knopf erzeugt exakt dieselben Daten wie das unveränderte Durchklicken aller Reiter. Teil B: Eine Hilfeseite `/hilfe` „So funktioniert Gregor" erklärt Briefing-Zeiten, Alarme und die vier gleichrangigen Kanäle; die Antwort-Befehle stehen nachrangig dort. Die Seite ist aus der Startklar-Checkliste, der Seitenleiste und dem Konto-Menü erreichbar. S1 (Erklär-Hinweise) und S2 (Willkommen, Checkliste, Testmail) sind live; diese Spec ersetzt die S3-Punkte des Gesamtentwurfs `onboarding_hilfe_2521.md` (siehe „Abweichungen von der Gesamt-Spec").

## Source

- **File:** `frontend/src/lib/components/shared/anlegeLockEngine.ts`, `frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte` (neu), `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `frontend/src/lib/components/trip-new/tripNewLogic.ts`, `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`, `frontend/src/routes/hilfe/+page.svelte` (neu), `frontend/src/routes/_home/StartklarCheckliste.svelte`, `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`, `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte`, `frontend/src/lib/i18n/messages/de.json`
- **Identifier:** `canFinishMitStandardwerten`, `StandardwerteSpeichernKnopf`, `ergaenzeStandardwerteReportConfig` (reiner Ergänzer in `tripNewLogic.ts`), `baueReportConfigPayload`, `ladeReportZustand`, `ladeMailZustand`, `buildComparePrefillRows`, `buildCompareCorridorSavePayload`, `command_rows`

> **Schicht-Hinweis:** Reine Frontend-Scheibe (SvelteKit) plus ein Python-Drift-Test, der `src/services/trip_command_processor.py` nur liest. Es entsteht kein neuer Endpoint. Der Speicherweg läuft über die bestehenden `POST /api/trips` und `POST /api/compare/presets` mit der `user_id` aus dem Auth-Kontext (Go-API), nie `"default"`. Die Hilfeseite zeigt keine nutzerbezogenen Daten.

## Estimated Scope

- **Files:** ca. 10 produktiv (2 neu: `StandardwerteSpeichernKnopf.svelte`, `routes/hilfe/+page.svelte`) plus ca. 7 neue bzw. angepasste Testdateien
- **LoC (produktiv, ohne Tests/Katalog/docs):** ca. +325 (Teil A ca. +175 inkl. Compare-Vorbelegung, Teil B ca. +150). Über 250: `workflow.py set-field loc_limit_override 500`. Der Scope wird nicht verengt (Epic-Regel).
- **Risiko:** MEDIUM (Teil A berührt die Speicherpfade beider Anlege-Editoren; Teil B risikoarm)

### Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/anlegeLockEngine.ts` | MODIFY | Neue kind-neutrale Gate-Funktion `canFinishMitStandardwerten({pflichtErfuellt, defaultsBereit, bestandFrei})` neben `canFinish`; `canFinish` bleibt unverändert |
| `frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte` | CREATE | EIN geteilter Knopf (Props `enabled`, `saving`, `onclick`, `testid`); keine `context`-Verzweigung |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | Reiner, ohne Mount testbarer Ergänzer, der fehlende `reportConfig`-Felder aus `baueReportConfigPayload(ladeReportZustand(undefined))` und `ladeMailZustand(undefined)` ergänzt; `multi_day_trend_reports=[]` wie der Versand-Reiter |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Knopf im Desktop-Footer und mobil; Gate aus `etDone`, Name, Startdatum, `catalogLoaded`; Speichern über denselben `buildAndSave`-Weg; `beforeNavigate`-Autosave bleibt an `ready` |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Knopf in der Desktop-Kopfzeile und mobil im StickyFooter auf allen Reitern; Katalog-Laden von `GET /api/compare/metrics`; Wertebereiche über `buildComparePrefillRows` + `buildCompareCorridorSavePayload` |
| `frontend/src/routes/hilfe/+page.svelte` | CREATE | Hilfeseite (Briefing-Zeiten, Alarme, Kanäle, nachrangig Antwort-Befehle); alle Texte über `t(key)` |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | MODIFY | Hilfelink |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte`, `KontoSheet.svelte` | MODIFY | Navigationslink auf `/hilfe` (BottomNav bleibt unverändert) |
| `frontend/src/lib/i18n/messages/de.json` | MODIFY | Knopf-, Hilfe-, Link-Texte, Befehlstabelle; Korrektur `info.wertebereiche.vergleich` |
| `docs/specs/modules/onboarding_hilfe_2521.md` | MODIFY | Verweis „S3 spezifiziert in onboarding_standardwerte_hilfe.md"; AC-15..17 und Hilfe-AC-2 als überholt markiert |
| Neue Tests (siehe „Test Plan") | CREATE | zu den ACs |
| Bestehende Gate-Tests (siehe „Test Plan") | MODIFY | nur um den neuen Knopf erweitert, nie stillgelegt |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `anlegeLockEngine.ts` (`canFinish`, `tailUnlocked`, `tailDone`) | module | Geteilter Kern der Anlege-Editoren; die neue Gate-Funktion kommt dorthin |
| `reportConfigPayload.ts` (`ladeReportZustand`, `baueReportConfigPayload`), `mailInhaltZustand.ts` (`ladeMailZustand`) | function | Dieselben reinen Bausteine, die Versand-Reiter und Mail-Inhalt-Karte beim Mount nutzen; kein zweites Regelwerk |
| `corridorEditorState.ts` (`buildComparePrefillRows`, `buildCompareCorridorSavePayload`) | function | Dieselbe Kette wie `CorridorEditor` beim Reiter-Besuch |
| `GET /api/metrics` (Trip-Katalog, `trip_default_enabled`), `GET /api/compare/metrics` (Vergleichs-Katalog) | endpoint | Voraussetzung `defaultsBereit` |
| `POST /api/trips`, `POST /api/compare/presets` | endpoint | Bestehende Speicherwege, `user_id` aus Auth-Kontext |
| `alertChannelState.ts` | module | Alarm-Kanal-Default E-Mail + Telegram (#2518) |
| `src/services/trip_command_processor.py` (`_COMMAND_SPECS`, `command_rows()`, `hilfe_kurzform()`) | module | Einzige Quelle der Antwort-Befehle; nur für den Drift-Test gelesen |
| `t(key)` / `MessageKey` / `de.json` (#2520) | module | Einziger Ort für Texte; unbekannter Schlüssel ist ein TypeScript-Fehler |
| `frontend/src/hooks.server.ts` (`publicPaths`) | module | `/hilfe` steht nicht in `publicPaths` und ist damit nur für Eingeloggte erreichbar |
| `StartklarCheckliste.svelte` (S2), `Sidebar.svelte`, `KontoSheet.svelte` | module | Orte der Hilfelinks |
| ADR-0032 (Editor-Paradigma) | adr | Editor-Aufbau bleibt unverändert; der Knopf ist eine Ergänzung |

## Implementation Details

### Teil A: Mit Standardwerten speichern

**Leitprinzip.** Der Knopf erzeugt exakt dieselbe Speicher-Nutzlast wie das unveränderte Durchklicken aller Reiter (Deep-Equal). Dafür baut er die fehlenden Teile beim Klick aus denselben reinen Funktionen, die die Reiter beim Öffnen nutzen. Verworfen: Versand- und Mail-Reiter dauerhaft versteckt mounten (Nebenwirkungen auf Testmail, Abrufe, Infobox; bewusstes Entweder-oder im Editor).

**Bestandsknopf unverändert.** `canSave` (Trip) und `canFinish` (beide) bleiben wie sie sind. Der neue Knopf ist zusätzlich und hat ein eigenes Gate. Er verschwindet, sobald der Bestandsknopf frei ist (`bestandFrei`).

**Gate.** EINE kind-neutrale Funktion in `anlegeLockEngine.ts`: `canFinishMitStandardwerten({pflichtErfuellt, defaultsBereit, bestandFrei})` liefert wahr, wenn Pflichtangaben erfüllt und Standardwerte bereit sind und der Bestandsknopf noch nicht frei ist. Keine neuen `context`-Verzweigungen; Trip und Ortsvergleich unterscheiden sich nur in den übergebenen Werten.

| | Trip (`/trips/new`) | Ortsvergleich (`/compare/new`) |
|---|---|---|
| Pflichtangaben | Name + Startdatum + alle Etappen mit GPX (`etDone`) | Name + mindestens 2 Orte |
| `defaultsBereit` | Metrik-Katalog geladen (`catalogLoaded`) | `GET /api/compare/metrics` erfolgreich geladen; bei Fehler bleibt der Knopf gesperrt |

**Trip-Nutzlast.** Der Ergänzer in `tripNewLogic.ts` ist eine reine Funktion: Er nimmt die bisherige Nutzlast und ergänzt `report_config` um die Felder, die sonst erst der Versand-Reiter und die Mail-Inhalt-Karte beim Mount schreiben (`enabled`, Morgen-/Abend-Zeiten, Trend, `telegram_style`, `send_*`, `email_format`, `show_*` u. a.), über `baueReportConfigPayload(ladeReportZustand(undefined))` und `ladeMailZustand(undefined)`. `multi_day_trend_reports=[]` wie im Versand-Reiter. Wurde ein Reiter bereits besucht, gewinnt dessen Wert; es wird nie etwas Gesetztes überschrieben. Der Klick speichert über denselben `buildAndSave`-Weg wie „Anlegen".

**Compare-Nutzlast.** Der Wizard-State hält Versand- und Alarm-Defaults bereits. Die Wertebereiche werden beim Klick wie beim Reiter-Besuch vorbelegt: `buildComparePrefillRows` + `buildCompareCorridorSavePayload` mit demselben Profil, das `CorridorEditor` beim Besuch verwendet. Der Rückfall auf `'wandern'` aus dem Speicher-Payload darf auf diesem Weg keine abweichenden Werte erzeugen. Hat der Nutzer den Wertebereiche-Reiter schon besucht, gelten dessen Werte.

**Autosave.** Die `beforeNavigate`-Speicherung im Trip-Editor bleibt an `ready` (nicht am neuen Gate). `savedTripId` verhindert einen zweiten POST, wenn nach dem Klick weg navigiert wird.

**Platzierung.** Trip: Desktop im `EditorStickyFooter` neben `trip-new-save-btn`, mobil neben `tn-mobile-save`. Ortsvergleich: Desktop in der Breadcrumb-Kopfzeile neben `compare-editor-activate` (dort gibt es keinen Footer), mobil im StickyFooter auf allen Reitern (der Bestandsknopf `cm-mobile-activate` erscheint nur auf dem Versand-Reiter). Nach dem Speichern landet der Nutzer wie beim Bestandsknopf auf der Detailseite.

**Textkatalog-Korrektur.** `info.wertebereiche.vergleich`: sagt heute „Standard: keine Wertebereiche"; nach dieser Scheibe werden sie vorbelegt, der Text nennt den tatsächlichen Standard. `info.alarme.vergleich` bleibt unverändert: Der Satz „amtliche Warnungen aus" beschreibt korrekt den im Alarme-Reiter sichtbaren Schalter (`officialWarningsEnabled`, Standard aus). Die beiden anderen Flags (`officialAlertsEnabled` = amtliche Warnungen im Briefing-Inhalt, `officialAlertTriggersEnabled`) sind andere Schalter; der bestehende Test `infobox_standards_stimmen_mit_den_quellen.test.ts` bewacht diese Zuordnung bereits. Die wörtlichen Textkopien in `shared/__tests__/infoboxTexte.ts` werden für `info.wertebereiche.vergleich` mitgezogen.

### Teil B: Hilfeseite `/hilfe`

`frontend/src/routes/hilfe/+page.svelte` nach dem Muster der statischen Seite `routes/archiv/`. Abschnitte in dieser Reihenfolge: Briefing-Zeiten (morgens, abends), Alarme, Kanäle, danach untergeordnet Antwort-Befehle.

- **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS (Garmin inReach) stehen als gleichrangige Wege nebeneinander. SMS und Premium-SMS tragen den Zusatz „je nach Tarif". Kein Text nennt einen Kanal „Hauptkanal" oder sagt, ein Kanal ersetze einen anderen. Signal gibt es nicht (seit #610 entfernt).
- **Antwort-Befehle:** nachrangiger Abschnitt, statisch im Textkatalog. Kein neuer Endpoint (drei Stacks für einen nachrangigen Abschnitt wären unverhältnismäßig). Drift-Schutz: ein Python-Test vergleicht `command_rows()` aus `src/services/trip_command_processor.py` mit den Katalogeinträgen und wird rot, sobald ein Befehl hinzukommt, wegfällt oder anders heißt.
- **Texte:** ausschließlich `t(key)` aus `de.json`, durchgehend „Trip", keine Handlungsempfehlungen (die Seite beschreibt, was Gregor tut, nicht was der Nutzer tun soll), Kontrast mindestens 4,5:1, nie `--g-ink-4`.
- **Zugriff:** Route nur für Eingeloggte, über `hooks.server.ts` (kein Eintrag in `publicPaths`).
- **Links:** `StartklarCheckliste.svelte` (Kopf oder nach den Hinweisen), `Sidebar.svelte`, `KontoSheet.svelte`. `BottomNav.svelte` bleibt unverändert (Slots knapp).

## Expected Behavior

- **Input:** Klick auf „Mit Standardwerten speichern" in `/trips/new` oder `/compare/new`; Aufruf von `/hilfe` über Checkliste, Seitenleiste oder Konto-Menü.
- **Output:** Gespeicherter Trip bzw. Ortsvergleich, identisch zum Durchklicken aller Reiter; Hilfeseite mit den vier Abschnitten.
- **Side effects:** Je Klick genau ein `POST` (kein Doppel-POST durch Autosave). Keine Änderung an Bestandsdaten. Python-Lese-Default `multi_day_trend_reports=["evening"]` für Altdaten ohne `report_config` bleibt unberührt.

## Acceptance Criteria

- **AC-1:** Given ich bin im Trip-Editor auf `/trips/new`, der Metrik-Katalog ist geladen, und ich habe Name, Startdatum und für alle Etappen eine GPX-Datei angegeben, den Versand-Reiter aber noch nie geöffnet / When ich die Fußzeile ansehe / Then ist „Mit Standardwerten speichern" aktiv; fehlt Name, Startdatum oder bei einer Etappe die GPX-Datei, ist der Knopf deaktiviert.
  - Test: Gate-Wahrheitstabelle in `node --test`; Mutation „`etDone` aus den Pflichtangaben entfernt" muss rot werden.

- **AC-2:** Given ich bin im Ortsvergleich-Editor auf `/compare/new` und der Vergleichs-Metrik-Katalog ist geladen / When ich Name und mindestens zwei Orte angegeben habe / Then ist „Mit Standardwerten speichern" aktiv; bei nur einem Ort oder ohne Namen ist er deaktiviert.
  - Test: Gate-Wahrheitstabelle in `node --test`; Mutation `>= 1` statt `>= 2` bei Orten muss rot werden.

- **AC-3:** Given der Metrik-Katalog des Trip-Editors ist noch nicht geladen, obwohl alle Pflichtangaben erfüllt sind / When ich die Fußzeile ansehe / Then ist „Mit Standardwerten speichern" deaktiviert und wird erst aktiv, wenn der Katalog da ist; ein Klick vorher speichert nichts.
  - Test: `node --test` Gate mit `defaultsBereit=false`; Mutation „`catalogLoaded` ignoriert" muss rot werden.

- **AC-4:** Given der Abruf des Vergleichs-Metrik-Katalogs schlägt fehl, Name und zwei Orte sind angegeben / When ich den Editor ansehe / Then bleibt „Mit Standardwerten speichern" gesperrt, der Bestandsweg über die Reiter bleibt unverändert nutzbar.
  - Test: `node --test` Zustand „Katalog-Fehler" ergibt gesperrt; Mutation „Fehler zählt als bereit" muss rot werden.

- **AC-5:** Given der Bestandsknopf („Anlegen" im Trip bzw. „Aktivieren" im Ortsvergleich) wird frei, weil ich alle Reiter besucht habe / When ich die Fußzeile bzw. die Kopfzeile ansehe / Then ist „Mit Standardwerten speichern" nicht mehr da; solange der Bestandsknopf gesperrt ist, sind beide Knöpfe nie gleichzeitig aktiv.
  - Test: `node --test` Gate mit `bestandFrei=true` ergibt falsch; Mutation „`bestandFrei` ignoriert" muss rot werden.

- **AC-6:** Given ein Trip mit Name, Startdatum und GPX-Etappen / When ich einmal mit „Mit Standardwerten speichern" speichere und einmal denselben Trip anlege, nachdem ich alle Reiter unverändert durchgeklickt habe / Then sind die beiden gespeicherten Trips inhaltlich gleich (gleiche Metriken, gleiche Briefing-Einstellungen, gleiche Mail-Einstellungen, gleiche Alarm-Kanäle, kein Mehrtages-Trend im Abend-Briefing).
  - Test: Vergleichsmaßstab ist das, was die Reiter beim Durchklicken tatsächlich in den Editor-Zustand schreiben (die `$effect`s von VersandTab und MailInhaltCard), NICHT ein erneuter Aufruf derselben Builder, die der Ergänzer nutzt (sonst tautologisch). Entweder Mount-/SSR-Harness, das die echten Reiter rendert und deren geschriebenen Zustand aufzeichnet, oder Staging-E2E: zwei Trips anlegen (Standardwerte-Knopf vs. unverändertes Durchklicken), beide per GET lesen und ohne `id`/Name/Zeitstempel vergleichen. Mutationen, die nur den Ergänzer-Pfad treffen: „Ergänzer lässt den Mail-Baustein weg" und „Ergänzer setzt `multi_day_trend_reports` nicht" müssen rot werden.

- **AC-7:** Given ein Ortsvergleich mit Name und zwei Orten / When ich mit „Mit Standardwerten speichern" speichere und einmal denselben Ortsvergleich nach unverändertem Besuch des Wertebereiche-Reiters speichere / Then sind die Wertebereiche, aktiven Metriken und Alarmstufen in beiden gleich (vorbelegt aus dem Profil), nicht leer.
  - Test: Vergleichsmaßstab ist das, was `CorridorEditor` beim unveränderten Besuch tatsächlich über `syncToWizard` in den Wizard-Zustand schreibt, NICHT ein erneuter Aufruf derselben Builder-Kette (sonst tautologisch). Entweder Mount-/SSR-Harness mit echtem `CorridorEditor` oder Staging-E2E: zwei Ortsvergleiche anlegen (Standardwerte-Knopf vs. unveränderter Wertebereiche-Besuch), beide per GET lesen und ohne `id`/Name/Zeitstempel vergleichen. Mutationen nur im Standardwerte-Pfad: „Profil-Rückfall `'wandern'` statt Prefill-Profil" und „Vorbelegung übersprungen" müssen rot werden.

- **AC-8:** Given ich habe im Ortsvergleich-Editor den Wertebereiche-Reiter geöffnet und dort einen Wertebereich geändert, den Versand-Reiter aber noch nicht geöffnet (Bestandsknopf gesperrt) / When ich mit „Mit Standardwerten speichern" speichere / Then bleibt mein geänderter Wertebereich erhalten und wird nicht durch die Profil-Vorbelegung überschrieben. (Im Trip kann dieser Fall nicht eintreten: Der Besuch des Versand-Reiters gibt dort bereits den Bestandsknopf frei, und Metriken, Wertebereiche und Alarme sind dauerhaft eingebunden.)
  - Test: `node --test` Standardwerte-Pfad mit bereits besuchtem, geändertem Wertebereiche-Zustand liefert die Nutzerwerte; Mutation „Vorbelegung immer anwenden" muss rot werden.

- **AC-9:** Given ich habe mit „Mit Standardwerten speichern" gespeichert und verlasse danach den Editor / When die Navigation weggeht / Then ist genau ein Trip entstanden, nicht zwei.
  - Test: Staging-Playwright: nach dem Standardwerte-Speichern weg navigieren, danach enthält die Trip-Liste genau einen neuen Trip (`beforeNavigate` lebt in der Komponente; ein Test nur auf die Variable `savedTripId` reicht nicht). Mutation „`savedTripId` nicht gesetzt" muss rot werden.

- **AC-10:** Given ich verlasse den Trip-Editor mit Name und Startdatum, ohne den Standardwerte-Knopf zu nutzen / When die Navigation weggeht / Then verhält sich der Autosave wie bisher (gebunden an `ready`) und wird durch das neue Gate nicht ausgelöst oder blockiert.
  - Test: `node --test` bestehender Autosave-Test bleibt grün; Mutation „Autosave an das neue Gate gebunden" muss rot werden.

- **AC-11:** Given ich habe in `/trips/new` bzw. `/compare/new` mit „Mit Standardwerten speichern" gespeichert / When das Speichern erfolgreich war / Then lande ich auf der Detailseite dieses Trips bzw. Ortsvergleichs und sehe dort die Standardwerte (Metriken, Versand, Alarm-Kanäle), und der Eintrag gehört nur meinem Konto.
  - Test: Staging-Playwright „Pflichtangaben, Standardwerte, Detailseite" für Trip und Ortsvergleich, jeweils mit zwei verschiedenen Nutzern (Nutzer B sieht den Eintrag von A nicht).

- **AC-12:** Given ich öffne den Trip- bzw. Ortsvergleich-Editor am Handy (375 px Breite) / When die Pflichtangaben erfüllt sind / Then ist „Mit Standardwerten speichern" in der unteren Leiste erreichbar, im Ortsvergleich auf jedem Reiter (nicht nur auf Versand).
  - Test: Staging-Playwright mobil; `node --test` Render-Test Platzierung; Paritätstest der Reiterleiste Trip/Vergleich um den neuen Knopf erweitert.

- **AC-13:** Given Trip- und Ortsvergleich-Editor / When ich den Knopf in beiden ansehe / Then ist es derselbe Baustein mit identischer Beschriftung, Optik und Sperrverhalten, und es gibt keine zweite, compare-eigene Knopf-Komponente.
  - Test: `node --test` beide Editoren binden `StandardwerteSpeichernKnopf` ein; Pendant-Sperre am Commit bleibt grün.

- **AC-14:** Given ich lese den Erklär-Hinweis zu Wertebereichen im Ortsvergleich-Editor / When ich ihn öffne / Then nennt er, dass Wertebereiche aus dem Aktivitätsprofil vorbelegt werden (nicht mehr „keine Wertebereiche"); der Alarm-Hinweis bleibt unverändert, weil er den sichtbaren Schalter „amtliche Warnungen" (Standard aus) bereits richtig beschreibt.
  - Test: `node --test` Katalogtest auf `info.wertebereiche.vergleich`; Mutation „alter Wortlaut" muss rot werden; bestehender Test `infobox_standards_stimmen_mit_den_quellen.test.ts` bleibt grün.

- **AC-15:** Given ich bin eingeloggt / When ich `/hilfe` öffne / Then sehe ich die Abschnitte Briefing-Zeiten (morgens, abends), Alarme, Kanäle und zuletzt, deutlich nachrangig, die Antwort-Befehle.
  - Test: `node --test` Render-Test der Seite gegen den Textkatalog; Staging-Playwright (Seite lädt, vier Abschnitte in dieser Reihenfolge).

- **AC-16:** Given die Hilfeseite / When ich den Abschnitt Kanäle lese / Then stehen E-Mail, Telegram, SMS und Premium-SMS gleichrangig nebeneinander, SMS und Premium-SMS mit „je nach Tarif", und kein Text nennt einen Kanal „Hauptkanal" oder sagt, ein Kanal ersetze einen anderen.
  - Test: `node --test` Katalog- und Render-Test (alle vier Kanalnamen vorhanden; Gegenprobe: ein Satz mit „Hauptkanal" im Katalog macht den Test rot).

- **AC-17:** Given die Antwort-Befehle auf der Hilfeseite / When im Python-Code ein Befehl hinzukommt, wegfällt oder umbenannt wird, ohne dass der Textkatalog nachgezogen wird / Then schlägt der Drift-Test fehl; stimmen beide überein, ist er grün.
  - Test: pytest `command_rows()` gegen die Befehlseinträge in `de.json`; Mutation „einen Befehl aus dem Katalog löschen" muss rot werden.

- **AC-18:** Given ich bin auf der Startklar-Checkliste / When ich den Hilfelink wähle / Then öffne ich `/hilfe`.
  - Test: `node --test` Render-Test Link auf `/hilfe`; Staging-Playwright.

- **AC-19:** Given ich bin eingeloggt am Desktop bzw. am Handy / When ich die Seitenleiste bzw. das Konto-Menü öffne / Then finde ich dort einen Link „Hilfe", der auf `/hilfe` führt, und die untere Navigationsleiste (BottomNav) ist unverändert.
  - Test: `node --test` Render-Tests `Sidebar` und `KontoSheet`; Gegenprobe: BottomNav-Einträge unverändert.

- **AC-20:** Given ich bin nicht eingeloggt / When ich `/hilfe` aufrufe / Then werde ich wie bei jeder anderen geschützten Seite zur Anmeldung geleitet und sehe den Hilfeinhalt nicht.
  - Test: Staging-Playwright ohne Sitzung; `node --test` `/hilfe` ist nicht in `publicPaths`.

- **AC-21:** Given die neuen Knopf-, Hilfe- und Link-Texte / When der Quelltext kompiliert und der Katalog geprüft wird / Then stehen alle sichtbaren deutschen Texte in `de.json` und werden über `t(key)` geladen (ein unbekannter Schlüssel ist ein Compilerfehler), durchgehend „Trip", ohne Handlungsempfehlungen, Textfarben mit mindestens 4,5:1 und nie `--g-ink-4`.
  - Test: `svelte-check`; bestehende Katalogtests `textkatalog.test.ts` und `onboarding_textkatalog.test.ts` laufen über die neuen Schlüssel; Gegenprobe mit einem Handlungs-Satz oder dem Wort „Tour" im Katalog.

## Test Plan

Frontend-Tests laufen über `node --test` (kein Vitest), Python über pytest. Dateien sind nach Verhalten benannt, nicht nach Issue-Nummer. Kein Mock-Theater: reine Funktionen, echte Katalogdateien und die echte Befehlsquelle.

| Testdatei (neu) | Deckt |
|---|---|
| `standardwerte_gate.test.ts` | AC-1 bis AC-5, AC-10 (Gate Trip/Compare, Katalog nicht geladen, Compare-Katalogfehler, Knopf weg bei freiem Bestandsknopf) |
| `standardwerte_payload_paritaet_trip.test.ts` | AC-6 (Ergänzer gegen den von den echten Reitern geschriebenen Zustand, per Mount-Harness; alternativ im Staging-E2E) |
| `standardwerte_payload_paritaet_compare.test.ts` | AC-7, AC-8 (gegen den von `CorridorEditor` geschriebenen Zustand, Profil-Rückfall, kein Überschreiben besuchter Wertebereiche) |
| `standardwerte_knopf_geteilt.test.ts` | AC-12, AC-13 (ein Baustein, Platzierung) |
| `hilfe_seite_inhalt.test.ts` | AC-15, AC-16, AC-18, AC-19, AC-21 |
| `test_hilfe_befehle_drift.py` | AC-17 (`command_rows()` gegen `de.json`) |
| Staging-Playwright `standardwerte-und-hilfe.spec.ts` | AC-6/AC-7 (GET-Vergleich, falls kein Mount-Harness), AC-9, AC-11, AC-12, AC-15, AC-18, AC-20 (nur `/e2e-verify`) |

Bestehende Tests, die das alte Gate festhalten, bleiben gültig und werden nur um den neuen Knopf erweitert (nie stillgelegt): `tripNewLogic.test.ts`, `trip_new_reiterleiste_besuchs_flags.test.ts`, `anlege_lock_engine.test.ts`, `compare_new_lock_engine_wirkstelle.test.ts`, `compare_anlege_freischaltung.test.ts`, `anlege_reiterleiste_trip_vergleich_paritaet.test.ts`, `infobox_nur_beim_anlegen.test.ts`; E2E `compare-editor-slice4.spec.ts`. Der Katalogtest für AC-14 liegt in den bestehenden Katalogtests.

## Abweichungen von der Gesamt-Spec

Diese Spec ersetzt in `onboarding_hilfe_2521.md` den S3-Absatz, AC-15 bis AC-17 und Hilfe-AC-2. Korrekturen:

1. **Alarm-Kanal:** Die Gesamt-Spec sagt „Alarm nur E-Mail". Seit #2518 sind E-Mail und Telegram der Alarm-Standard (`alertChannelState.ts`).
2. **Platzierung:** Die Gesamt-Spec sagt „Knopf im `EditorStickyFooter`" für beide. Im Ortsvergleich-Desktop gibt es keinen Footer; der Knopf sitzt dort in der Kopfzeile, mobil im StickyFooter auf allen Reitern.
3. **Pflichtangabe Etappe:** `stages.length >= 1` ist immer wahr (der Editor startet mit zwei leeren Etappen). Maßgeblich ist `etDone` (alle Etappen mit GPX), wie beim heutigen Speicher-Gate.
4. **Gate-Funktion:** Statt `canSaveWithDefaults(pflichtErfuellt)` gilt `canFinishMitStandardwerten({pflichtErfuellt, defaultsBereit, bestandFrei})`.
5. **Nutzlast:** Statt `buildDefaultsPayload(catalog)` mit eigenem Regelwerk werden die vorhandenen Reiter-Bausteine wiederverwendet (Leitprinzip: gleiche Daten wie Durchklicken). Es entsteht kein zweites Regelwerk.
6. **Ortsvergleich wird vorbelegt (PO-Entscheid 2026-10-17):** Wertebereiche werden wie beim Reiter-Besuch aus dem Profil vorbelegt, nicht leer gelassen. Daraus folgt `defaultsBereit` = Vergleichs-Metrik-Katalog geladen, und die Infobox `info.wertebereiche.vergleich` wird korrigiert.
7. **Kanäle auf der Hilfeseite:** Die Formulierung „E-Mail als Hauptkanal" entfällt. Alle vier Kanäle sind gleichrangig (PO-Vorgabe).
8. **Hilfelinks:** Zusätzlich zum Link aus der Checkliste Navigationslinks in Seitenleiste und Konto-Menü; die Gesamt-Spec nannte nur „Navigation bzw. Footer".

## Bewusst nicht Teil dieser Scheibe

- **Kanal-Uneinheitlichkeit im Trip:** `display_config.channels.telegram=true`, `report_config.send_telegram=false` und `alert_channels.telegram=true` stehen nebeneinander. Das entsteht schon beim Durchklicken; der Standardwerte-Knopf bildet das Durchklicken nach und ändert es nicht. Vermerk im Sammel-Issue #1199.
- **Python-Lese-Default `multi_day_trend_reports=["evening"]`** (`src/app/loader.py`, `src/app/models.py`) für Altdaten ohne `report_config`: bleibt unberührt und ist nur dokumentiert. Der Standardwerte-Weg schreibt ausdrücklich `[]`, damit er dem Durchklicken entspricht.
- Kein neuer Endpoint für die Befehlsliste; kein Umbau der Bestandsknöpfe oder der Reiter-Freischaltung (ADR-0032).

## Known Limitations

- Die Antwort-Befehle der Hilfeseite sind eine statische Kopie im Textkatalog; Aktualität sichert nur der Drift-Test, nicht die Laufzeit.
- Antwort-Befehle sind eine kurze Übersicht, keine vollständige Befehlsreferenz.
- Nur Deutsch; Texte im Katalog, keine Sprachumschaltung.
- Auf Staging ist das Mail-Ergebnis eines mit Standardwerten angelegten Trips nur über einen Wegwerf-Nutzer prüfbar; ist ein Teil nicht messbar, wird er als `NOT_MEASURABLE_ON_STAGING` ausgewiesen, nie als PASS.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** ADR-0032 (Editor-Paradigma) bleibt unberührt: der neue Knopf ergänzt, ersetzt keinen Bestandsweg und führt keinen Wizard ein. Kein neuer Kanal, Provider oder Datenmodell-Eintrag; die Hilfeseite beschreibt vorhandenes Verhalten. Die Vorbelegung der Compare-Wertebereiche ist PO-Entscheid vom 2026-10-17 (Leitprinzip „Standardwerte = unverändertes Durchklicken") und eine Auslegung der vorhandenen Reiter-Logik, kein neuer Grundsatz.

## Changelog

- 2026-10-17: AC-14 korrigiert — Alarm-Hälfte gestrichen; „amtliche Warnungen aus" im Alarm-Hinweis ist korrekt (sichtbarer Schalter `officialWarningsEnabled`, Standard aus); die Analyse hatte das Briefing-Flag `officialAlertsEnabled` verwechselt (Befund aus /40)
- 2026-10-17: Initial spec created (Issue #2521, Scheibe S3); Varianten V1 (Defaults beim Klick aus den Reiter-Bausteinen), PO-Entscheid „Ortsvergleich wird vorbelegt", Hilfeseite mit statischem Befehlskatalog und Drift-Test

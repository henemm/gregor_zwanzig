---
entity_id: fix_2999_datumfeld_tag_31
type: bugfix
created: 2026-11-14
updated: 2026-11-14
status: draft
version: "1.0"
workflow: fix-2999-datumfeld-tag-31
tags: [frontend, datumfeld, bugfix, i18n]
---

# Datumsfeld: getippter Tag 29-31 bleibt unveraendert, ungueltiges Datum wird gemeldet

## Approval

- [ ] Approved

## Purpose

Der Baustein `DatumFeld` darf ein vollstaendig getipptes Datum (TT.MM.JJJJ) nie still veraendern: 31.03.2027 muss unabhaengig vom heutigen Monat genau so im Feld und im Speicher ankommen. Ein Datum, das es nicht gibt (31.04.2027, 29.02.2027), wird dem Nutzer gemeldet und nicht gespeichert, statt es still auf einen anderen Tag zu verschieben (Issue #2999).

## Source

- **File:** `frontend/src/lib/components/molecules/DatumFeld.svelte`
- **Identifier:** `DatumFeld` (Komponente) plus neue reine Logik `DatumTipp` / `pruefeTipp`

> Schicht: ausschliesslich Frontend (SvelteKit). Kein Go-/Python-Code, keine Nutzerdaten-Endpoints neu; Mandantentrennung und Kanaele sind nicht beruehrt. Der Baustein hat kein Trip/Ortsvergleich-Pendant, er wird von beiden Kontexten gemeinsam genutzt (Verwender erben das Verhalten).

## Estimated Scope

- **LoC:** ca. +250/-5
- **Files:** 6
- **Effort:** medium (Risiko MEDIUM: zentraler Baustein in Trip anlegen, Etappe, Orts-Briefing-Laufzeit, Anpassen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| bits-ui 2.17.3 (`DatePicker`, `date-field`) | library | Segmentfeld und Kalender; Verhalten bleibt, wird NICHT hochgestuft (eigenes Issue) |
| `molecules/segmentFeldMeldung.ts` | module | Nachbar-Logik (Tipp-Zaehler, Melderegel); `DatumTipp` entsteht im neuen `datumTipp.ts` daneben |
| `molecules/UhrzeitFeld.svelte` | component | Schwesterbaustein, bleibt unveraendert (Stunde/Minute fest begrenzt) |
| i18n-Katalog (ADR-0104) | module | neue Meldung `bausteine.datum.ungueltig` DE/EN |
| `TripNewEditor.svelte` (leerMelden), `edit/StageDateField.svelte`, `zustellung-tab/LaufzeitKarte.svelte`, `shared/versand-tab/VTLaufzeitVergleich.svelte`, `wetter-tab/AnpassenKarte.svelte` | components | Verwender, erben das Verhalten ohne eigenen Code |
| `frontend/e2e/helpers.ts` (`tippeDatum`) | test helper | Tippen von TTMMJJJJ im Browser |
| `rework_2881_design_system_bereinigung` (AC-1..3 DatumFeld) | spec | Bestehendes Verhalten bleibt gueltig |

## Implementation Details

Ursache (bits-ui 2.17.3, `date-field.svelte.js`): Die Tages-Obergrenze richtet sich nach dem Bezugsmonat (heute bzw. Monat des gespeicherten Werts). Im November (Max 30) wird aus "3","1" ein "01"; im Februar (Max 28) rutscht die "1" ins Monatssegment. Wird der Monat nach dem Tag getippt, klemmt bits-ui den Tag auf die Monatslaenge im Jahr des Placeholders (31.04. wird 30.04., 29.02.2028 wird 28.02.). Auch das Zusammensetzen klemmt (29.02.2027 wird 28.02.2027).

Loesung V2 (Tech-Lead-Entscheidung): ein eigenes Tipp-Protokoll im Baustein.

- Reine TS-Logik `DatumTipp`: fuehrt je Fokus einen segmentuebergreifenden Ziffernstrom. Reset bei Backspace, Pfeiltaste, Tab, Nicht-Ziffer, Fokuswechsel und Klick. Segmentreihenfolge wird aus den `[data-segment]`-Elementen im DOM gelesen.
- `pruefeTipp(ziffern, reihenfolge)` liefert `{ok, iso}` oder `{ungueltig}` (echte Monatslaenge inkl. Schaltjahr).
- `DatumFeld.svelte`: Der Strom laeuft im `onkeydowncapture` (vor bits-ui). Solange ein Strom laeuft, wird nach aussen nichts gemeldet (keine geklemmten Zwischenstaende, wichtig fuer das gefuellte Etappenfeld). Mit der 8. Ziffer steht die Absicht fest:
  - gueltig: getippte Absicht melden (bits-ui-Wert ignorieren), Feld per `aufbau++` neu aufbauen, Fokus per `tick()` zurueck auf das letzte Segment;
  - ungueltig: Meldung unter dem Feld, nichts speichern, Feld zeigt den Modellwert (gespeichert bzw. leer). Bei `leerMelden` keine Doppelmeldung mit "Startdatum fehlt".
- Meldung `bausteine.datum.ungueltig`: DE "Dieses Datum gibt es nicht." / EN "This date does not exist."; `role="alert"`, per `aria-describedby` am Feld verknuepft, direkt unter dem Feld.
- Kalenderklick und Pfeiltasten bleiben unveraendertes bits-ui-Verhalten. Kein bits-ui-Upgrade in diesem Fix.

## Expected Behavior

- **Input:** Nutzer tippt acht Ziffern TTMMJJJJ in das Datumsfeld.
- **Output:** Existiert das Datum, steht es unveraendert im Feld und wird gemeldet/gespeichert; sonst erscheint "Dieses Datum gibt es nicht." und nichts wird gespeichert.
- **Side effects:** Nach gueltiger Eingabe wird das Feld neu aufgebaut, der Fokus bleibt im Feld.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/datumTipp.ts` | CREATE | `DatumTipp`, `pruefeTipp` (ca. 70 LoC) |
| `frontend/src/lib/components/molecules/DatumFeld.svelte` | MODIFY | Strom, Zurueckhalten, Neuaufbau, Meldungselement (ca. 40 LoC) |
| `frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts` | CREATE | node --test Kernlogik (ca. 80 LoC) |
| `frontend/src/lib/i18n/messages/de/bausteine.json`, `.../en/bausteine.json` | MODIFY | `bausteine.datum.ungueltig` |
| `frontend/e2e/s2999-datumfeld-tag-31.spec.ts` | CREATE | Playwright mit `page.clock.setFixedTime` (ca. 60 LoC) |
| `frontend/e2e/helpers.ts` | MODIFY (falls noetig) | Hilfsfunktion fuers Tippen/Pruefen |

### Estimated Changes

- Files: 6
- LoC: +250/-5

## Test Plan

### Automated Tests (TDD RED)

- [ ] node --test `datum_tipp.test.ts`: GIVEN Ziffernstrom WHEN 31032027, 29022028, 31122026, 01012027 THEN `ok` mit passendem ISO-Datum
- [ ] node --test: GIVEN 31042027, 29022027, 30022028, 00012027, 32012027 THEN `ungueltig`
- [ ] node --test: GIVEN halber Strom WHEN Backspace, Pfeil, Fokuswechsel oder Nicht-Ziffer THEN Strom beginnt neu
- [ ] Playwright (Staging), Uhr per `page.clock.setFixedTime` auf 2026-11-14 (Tages-Max 30) und 2027-02-10 (Tages-Max 28, haertester Fall): leeres Feld 31.03.2027 und 29.02.2028 kommen an; 31.04.2027 und 29.02.2027 zeigen Meldung und speichern nichts
- [ ] Playwright: gefuelltes Etappenfeld 15.04.2027 auf 31.05.2027 ohne geklemmten Zwischen-PUT
- [ ] Playwright: Meldung auf Englisch bei Sprache EN
- [ ] Playwright: Regression Kalenderklick und Backspace
- [ ] Bestehende AC-10 in `frontend/e2e/s3b2795-zustellung-laufzeit.spec.ts` bleibt gruen
- [ ] node --test `uhrzeit_feld_leeren.test.ts` und bestehende `segment_feld_meldung.test.ts` unveraendert gruen

## Acceptance Criteria

- **AC-1:** Given die Systemuhr steht im November (Monat mit 30 Tagen) und das Datumsfeld ist leer / When der Nutzer 31032027 tippt / Then zeigt das Feld 31.03.2027 und genau dieses Datum wird gemeldet und gespeichert, nicht 01.03.2027.
  - Test: Playwright mit `page.clock.setFixedTime` auf 2026-11-14, Ziffern tippen, Feldanzeige und gemeldeten Wert pruefen.

- **AC-2:** Given die Systemuhr steht im Februar (Monat mit 28 Tagen) und das Datumsfeld ist leer / When der Nutzer 31032027 tippt / Then steht 31.03.2027 im Feld, kein Segment ist verrutscht und der gespeicherte Wert ist 31.03.2027.
  - Test: Playwright mit `page.clock.setFixedTime` auf 2027-02-10, alle drei Segmente und gespeicherten Wert pruefen.

- **AC-3:** Given das Datumsfeld ist leer, die Systemuhr steht im Jahr 2026 / When der Nutzer das Schaltjahr-Datum 29022028 tippt / Then kommt 29.02.2028 unveraendert an und wird nicht auf 28.02. verschoben.
  - Test: Playwright, Uhr 2026-11-14 und 2027-02-10, Feld und Speicher pruefen.

- **AC-4:** Given das Datumsfeld ist leer / When der Nutzer das nicht existierende Datum 31042027 tippt / Then erscheint unter dem Feld die Meldung "Dieses Datum gibt es nicht.", es wird nichts gespeichert und das Feld zeigt wieder leer statt 30.04.2027.
  - Test: Playwright, Meldung sichtbar (`role="alert"`), kein Speichervorgang, Feld leer.

- **AC-5:** Given das Datumsfeld ist leer / When der Nutzer 29022027 tippt (2027 ist kein Schaltjahr) / Then erscheint dieselbe Meldung "Dieses Datum gibt es nicht." und es wird weder 28.02.2027 noch 01.03.2027 gespeichert.
  - Test: Playwright, Meldung sichtbar, kein Speichervorgang.

- **AC-6:** Given ein Feld mit "Startdatum fehlt"-Pflichtmeldung (leerMelden, Trip anlegen) ist leer / When der Nutzer ein ungueltiges Datum tippt / Then erscheint nur die Meldung "Dieses Datum gibt es nicht." und nicht zusaetzlich "Startdatum fehlt".
  - Test: Playwright im Trip-Anlegen-Dialog, nur ein Meldungselement sichtbar.

- **AC-7:** Given ein Etappenfeld enthaelt 15.04.2027 / When der Nutzer 31052027 darueber tippt / Then steht am Ende 31.05.2027 im Feld, und waehrend des Tippens wird kein Zwischenstand (z. B. 30.04. oder 01.05.) gespeichert; es gibt genau einen Speichervorgang mit 31.05.2027.
  - Test: Playwright mit Netzwerkbeobachtung, es darf nur ein einziger PUT mit 31.05.2027 erfolgen.

- **AC-8:** Given der Nutzer hat ein ungueltiges Datum getippt und die Meldung wird angezeigt / When er danach ein gueltiges Datum tippt / Then verschwindet die Meldung und das gueltige Datum wird wie gewohnt uebernommen.
  - Test: Playwright, erst 31042027, dann 30042027, Meldung weg und Wert gespeichert.

- **AC-9:** Given die Oberflaeche steht auf Englisch / When der Nutzer 31042027 tippt / Then lautet die Meldung "This date does not exist." und ist fuer Screenreader per `role="alert"` ansagbar und mit dem Feld verknuepft.
  - Test: Playwright mit Sprache EN, Text und `aria-describedby`-Verknuepfung pruefen.

- **AC-10:** Given ein Datumsfeld mit Wert / When der Nutzer ein Datum im Kalender anklickt oder mit Backspace ein Segment loescht / Then verhaelt sich das Feld wie bisher (Kalenderklick uebernimmt den Tag, Backspace leert das Segment, nichts wird neu gemeldet bis das Datum vollstaendig ist).
  - Test: Playwright, Kalenderklick und Backspace-Regression gegen den bisherigen Stand.

- **AC-11:** Given die bestehende Laufzeit-Pruefung AC-10 aus `s3b2795-zustellung-laufzeit.spec.ts` / When sie nach dem Fix laeuft / Then ist sie unabhaengig vom heutigen Monat gruen.
  - Test: Playwright, bestehende Spec unveraendert, einmal mit eingefrorener Uhr Nov und einmal Feb.

- **AC-12:** Given das Uhrzeitfeld (`UhrzeitFeld`) / When der Nutzer Stunde und Minute tippt oder loescht / Then ist das Verhalten unveraendert, bestehende Uhrzeit-Tests bleiben gruen und es erscheint keine Datumsmeldung.
  - Test: bestehende node --test `uhrzeit_feld_leeren.test.ts` und Uhrzeit-E2E gruen.

## Definition of Done

- AC-1 bis AC-12 grün: node --test der Kernlogik und die neue Playwright-Spec mit eingefrorener Uhr (14.11.2026 und 10.02.2027) gegen Staging.
- Bestehende AC-10 in `s3b2795-zustellung-laufzeit.spec.ts` grün, unabhängig vom aktuellen Monat; `segment_feld_meldung.test.ts` und `uhrzeit_feld_leeren.test.ts` unverändert grün.
- Adversary VERIFIED inkl. Mutations-Gegenprobe (Prüfung Monatslänge/Schaltjahr, Zurückhalten der Zwischenstände, Meldung ohne Speichern).
- PR mit allen 6 CI-Checks grün gemergt, Staging-Nachweis, Prod-Deploy mit Selftest Exit 0.

## Known Limitations

- Pfeiltasten klemmen weiterhin im Bezugsmonat (bits-ui-Verhalten), kein Teil dieses Issues.
- Kalenderklick bleibt bits-ui-Verhalten.
- bits-ui-Upgrade 2.17 auf 2.21 ist bewusst getrennt (eigenes Issue), damit ein Upgrade-Regress vom Fix unterscheidbar bleibt.
- Die Tipp-Logik nimmt an, dass Tag zuerst steht (de und en-GB heute); sie liest die Reihenfolge aus dem DOM.
- bits-ui 2.17.3 leert bei der zweiten Rücktaste im Tag-Segment alle Segmente (bisheriges Verhalten, unverändert, `date-field.svelte.js` ca. Z. 203). Ist das Datum beim Verlassen unvollständig, bleibt der gespeicherte Wert erhalten und das Feld zeigt ihn.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Lokale Fehlerbehebung im Baustein; keine Entscheidungsflaeche (Kanaele, Provider, Datenmodell, Auth) beruehrt. Meldetext folgt ADR-0104 (nur ueber Katalog).

## Changelog

- 2026-11-14: Initial spec created
- 2026-11-14: Known Limitations ergänzt (bits-ui leert bei der zweiten Rücktaste alle Segmente; unvollständig verlassen ⇒ gespeicherter Wert bleibt), ACs unverändert
- 2026-11-14: Nachtrag Umsetzung (Freigabe-Teil unverändert): `TripNewEditor.svelte` für AC-6 angepasst (+4/-2: Zustand `datumUngueltig`, `bind:ungueltig` am `DatumFeld`, blendet „Startdatum fehlt" aus). Zusätzlich Staging-Config `frontend/playwright.2999-datumfeld.staging.config.ts` für die Playwright-Prüfung gegen Staging. Doku-Nachzug: `docs/reference/design_system.md` (Eingabefelder).

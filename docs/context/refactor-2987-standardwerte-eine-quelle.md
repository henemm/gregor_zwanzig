# Context: refactor-2987-standardwerte-eine-quelle

## Request Summary
Issue #2987 (Paar P09 / NEU-6 aus der Bestandsaufnahme #1986): Standardwerte beim Anlegen nicht per Hand nachbauen, sondern aus den Reiter-Vorbelegungen ableiten. Der bewachende Paritätstest wird überflüssig oder bleibt als Regressionswächter. Intake: Summe 3 (Scope 1, Blast Radius 1, Unsicherheit 1), voller Prozess.

## Befund (Stand origin/main 2026-11-25, ab 323c46e37): Prämisse teils überholt
1. **Vergleichs-Seite ist erledigt:** Die Wertebereiche-Vorbelegung ist seit #2794 S3a eine Funktion (`shared/wetter-tab/anlegeVorbelegung.ts`, `vergleichVorbelegung`); Zustellung kommt über `standAusPreset`/`mitZustellungVergleich` (#3333).
2. **Der Reiter, der als Maßstab dient, wird nicht mehr gezeigt:** `WetterMetrikenVersandPanel` hat keinen produktiven Import mehr; `VersandTab`, `BriefingScheduleTab`, `MailInhaltCard` hängen nur daran (bzw. an `WeatherMetricsTab`). Sichtbar ist `ZustellungTab` (Start aus `standAusTrip`). Der Paritätstest vergleicht also gegen unsichtbaren Code. Löschen der Alt-Bausteine gehört zu **#3020** (PO-freigegeben), NICHT hierher.
3. **Verbleibende Doppelung Trip:**
   - Lesen der Briefing-Startwerte (Slots, Zeiten 07:00/18:00, Kanäle: E-Mail an, Rest aus) zweimal: `zustellungModell.ts` `standAusTrip` (sichtbarer Reiter) und `reportConfigPayload.ts` `ladeReportZustand` (schreibt beim Anlegen-POST).
   - `ergaenzeStandardwerteReportConfig` (`tripNewLogic.ts:412-435`) trägt einen von Hand gefüllten Schein-`zustand` (07:00/18:00, send_email true ...), nur weil `baueReportConfigPayload` ihn verlangt; wortgleich in `MailInhaltCard.svelte`.
   - Zeit-Literale 07:00/18:00 außerdem in `compareEditorSave.ts:578/580`, `versandVergleichSpeicherung.ts:92`, `versandPropsAus.ts:74/76`, Python `loader.py:649-650`.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | `ergaenzeVersandStandard` (:395), `ergaenzeStandardwerteReportConfig` (:412), `mitZustellung` (:362) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Aufrufer im Speicherweg (:580), `zustellungAnlegeTrip` |
| `frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts` | `ladeReportZustand`, `baueReportConfigPayload` (Pflichtfeld `zustand`) |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` | `standAusTrip`, `MORGEN_STANDARD`/`ABEND_STANDARD` (:59) |
| `frontend/src/lib/components/shared/mailInhaltZustand.ts` | `ladeMailZustand` (eine Quelle, nur noch vom Ergänzer sichtbar wirksam) |
| `frontend/src/routes/_home/cockpitHelpers.ts`, `shared/zustellung-tab/kanalStilSpeicherung.ts` | weitere produktive Leser von `ladeReportZustand` |
| `frontend/src/lib/components/trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts` | Wächter, Maßstab = unsichtbare Reiter |
| `frontend/src/lib/components/trip-new/__tests__/trip_anlegen_zustellung_payload_3332.test.ts` | Anlege-POST mit Reiter Zustellung |
| `frontend/src/lib/components/shared/versand-tab/__tests__/report_config_serialisierung_golden.test.ts` | Golden für Payload-Bau |

## Existing Patterns
- Reine Funktionen neben den Komponenten, node:test, AST-Auswertung echter Svelte-Skripte (`svelteInstanzPruefstand.ts`).
- Slot-Regel `reportSlotAktiv` ist bereits EINE Quelle (gemeinsame Fixture TS/Python/Go).
- Vorbelegung als eine Funktion plus ein Effekt je Editor (`anlegeVorbelegung.ts`).

## Dependencies
- Upstream: `reportSlotAktiv`, `toHHMMSS`, `mergeReportConfig`, `DEFAULT_DAILY_SUMMARY_METRICS`.
- Downstream: `POST /api/trips` (`report_config`), Startseite (`cockpitHelpers`), Reiter Zustellung (Trip + Orte).

## Existing Specs
- `docs/specs/modules/onboarding_standardwerte_hilfe.md` (Ergänzer-Vertrag, AC-6 bis AC-8)
- `docs/specs/modules/feat_3332_zustellung_anlegen_trip.md`, `feat_3333_zustellung_anlegen_orte.md` (Anlege-Modus Zustellung)
- `docs/specs/modules/feat_2277_s5_reportconfig_rueckbau.md`, ADR-0124

## Risks & Considerations
- **POST-Körper muss bitgleich bleiben** (keine sichtbare Verhaltensänderung, kein Datenverlust; Read-Modify-Write, unbekannte Felder bleiben).
- Abweichung prüfen: `hhmm()` in `standAusTrip` vs. `slice(0,5)` in `ladeReportZustand` bei ungültigen/null-Werten; nicht geprüft, in der Analyse klären.
- `standAusPreset` hat andere Slot-Vorgaben (Abend aus): fachlich gewollt, nicht angleichen.
- Nicht löschen, was #3020 gehört; umgekehrt darf der Wächter danach nicht an `VersandTab`/`MailInhaltCard` hängen (sonst bricht er mit #3020). Rund 40 Tests lesen die Alt-Bausteine, nicht anfassen.
- Scope-Vorschlag: nur Trip-Briefing-Startwerte auf eine Quelle, Schein-`zustand` entfernen, Wächter an `ZustellungTab`/`standAusTrip` hängen. Python-/Vergleichs-Literale nur nach Prüfung in der Analyse.

## Analysis

### Type
Feature (reiner Umbau, keine sichtbare Änderung)

### Affected Files (with changes)
Pfade unter `frontend/src/lib/components/`.

| File | Change Type | Description |
|------|-------------|-------------|
| `shared/briefingStartwerte.ts` | CREATE (~35) | EINE reine Lesefunktion der Trip-Briefing-Startwerte (Slots über `reportSlotAktiv`, Zeiten, vier Kanäle) plus Konstanten 07:00/18:00 und `hhmm`. Importiert nur `utils/reportSlotAktiv` |
| `shared/versand-tab/reportConfigPayload.ts` | MODIFY (~-8/+6) | `ladeReportZustand` = Lesefunktion + `telegram_style`; Signatur bleibt |
| `shared/zustellung-tab/zustellungModell.ts` | MODIFY (~-12/+10) | `standAusTrip` nutzt die Lesefunktion; `standAusPreset` nur die Konstanten/`hhmm`, Slot-Vorgaben (Abend aus) bleiben |
| `trip-new/tripNewLogic.ts` | MODIFY (~-18/+5) | Schein-`zustand` weg: `mergeReportConfig({snapshot: basis, live: nachVersand, own: mail})` statt `baueReportConfigPayload` |
| `trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts` | MODIFY | Maßstab `durchgeklickt()` (VersandTab/MailInhaltCard) durch feste Erwartungswerte ersetzen; siehe Wächter |
| `shared/__tests__/briefing_startwerte.test.ts` | CREATE (~60) | Lesefunktion mit Randfällen; `standAusTrip` und `ladeReportZustand` gegen dieselbe Fallliste mit festen Werten |

### Scope Assessment
- Files: 4 Produktion, 2 Tests
- Estimated LoC: Produktion ca. +55/-40; Tests ca. +130/-80 (knapp an ±250: Testumbau klein halten)
- Risk Level: LOW

### Technical Approach
1. Lesefunktion + Test, dann beide Leser umstellen, dann Schein-`zustand` entfernen, dann Wächter umbauen.
2. **Eine Zeit-Regel: `hhmm`** (ungültiger Text -> Standard; so zeigt es der sichtbare Reiter).
3. `baueReportConfigPayload` bleibt unverändert (`zustand` Pflichtfeld): `ergaenzeVersandStandard`, VersandTab und MailInhaltCard brauchen es. MailInhaltCard behält ihr Schein-Objekt bis #3020.
4. **Wächter:** Fälle #3155 AC-7/AC-13, F001/F002, Reinheit, Klick im echten Editor bleiben. Vergleiche gegen `durchgeklickt` werden feste Erwartungswerte. Nicht doppelt bauen: `trip_anlegen_zustellung_verdrahtung_3332.test.ts` (:181-209) prüft bereits POST == feste Fixture UND Startstand des echten Reiters Zustellung == POST.
   Mutationen, die rot werden müssen: Abend-Slot-Vorgabe aus, 07:00/18:00 geändert bzw. vertauscht, Kanal-Vorgabe geändert/vertauscht, `hhmm` durch `slice` ersetzt, Mail-Baustein weggelassen, `multi_day_trend_reports` falsch, `standAusPreset` mit Trip-Slot-Regel.

### Verifiziert (am Code bzw. per Lauf)
- **Schein-`zustand` ersetzbar, Ergebnis zeichengleich inkl. Schlüsselreihenfolge:** Probe mit 9 Blobs (leer, undefined, `enabled:false`, unbekannte Felder, Kurzform, `null`, '' und 'abc') 9/9 gleich; Probe wieder entfernt. Alle Ausgangstests grün (65/65: Paritätstest, 3332 Payload + Verdrahtung, Infobox, Golden).
- **`hhmm` statt `slice`: beim Anlegen nicht erreichbar.** `reportConfig` im Anlege-Editor entsteht nur aus Tagesfenster, Karte und `mitZustellung` (rasterfremde Zeiten werden verworfen; `seed` ist nur Teststartwert). Der POST-Körper bleibt auf jedem Bedienweg bitgleich. Go prüft Zeiten in Anlage und Änderung (`internal/handler/trip.go:238, :516`), lässt nur '' durch. Übrige Leser von `ladeReportZustand` (`cockpitHelpers`, `kanalStilSpeicherung`) lesen keine Zeiten; VersandTab ist nicht sichtbar.
- Keine Importzyklen, da das neue Modul nur `utils/` importiert; `zustellungModell` (i18n, Stores) wird von niemandem zusätzlich gezogen.
- Korrektur zur Gegenprüfung: beim Trip sind Vorgabe BEIDE Slots an; „Abend aus“ gilt nur für Orte-Briefings.

### Nicht geprüft
- Ob Bestandsdaten eine leere Zeit tragen (berührt den Umbau nicht, nur den Anlege-Weg).
- Der Compare-Paritätstest ist nicht Teil des Umfangs.

### Befunde gegen den Plan
- Das Issue ist nach #2794/#3332/#3333 großteils überholt; der Gewinn ist klein (eine Doppelung, ein toter Parameter). Es lohnt trotzdem, weil der Wächter sonst mit #3020 bricht.
- Der zweite Teil der Doppelung (`MailInhaltCard`-Schein-Objekt, VersandTab-Literale) fällt erst mit #3020.

### Dependencies
- Reihenfolge: #2987 vor #3020 (macht den Wächter unabhängig). #3020 nicht vorwegnehmen.
- Tests brauchen `npm ci` im Worktree (in diesem erledigt).

### Out of Scope
Python-Literale (`loader.py:649-650`), Vergleichs-Literale (`compareEditorSave.ts:578/580`, `versandVergleichSpeicherung.ts:92`, `versandPropsAus.ts:74/76`), Löschen der Alt-Bausteine.

### Open Questions
- keine

## RED-Stand (Phase 5)
- Neu `shared/__tests__/briefing_startwerte.test.ts`, umgebaut `trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts`: 95 Tests, 24 rot (20 Lesefunktion fehlt, 2 Zeitregel `ladeReportZustand`, 2 Zeitregel Ergänzer); 71 grün sichern den Bestand (Bitgleichheit, AC-4).
- Schnittstelle: `leseBriefingStartwerte(rc)` aus `shared/briefingStartwerte.ts` liefert `ReportZustand` ohne `telegram_style` (snake_case, Zeiten 'HH:MM').
- AC-6 vorgeprüft: in einer Kopie ohne `VersandTab.svelte`/`MailInhaltCard.svelte` fallen im Wächter nur die 2 Zeitregel-Fälle (dieselben wie mit).
- Zeilenbudget: Tests 229 geändert; für die Produktion bleiben 91 von 320.
- `svelte-check`: 33 Bestandsfehler, keiner in den beiden Testdateien (nur dort gesucht).
- **RED-Tests sind NICHT committed** (liegen im Arbeitsbaum; Kopie `docs/artifacts/refactor-2987-standardwerte-eine-quelle/red-tests.patch`): `touched_tests_gate.py` liest TAP, lokales Node v26.10.0 gibt ohne `--test-reporter=tap` das spec-Format aus, daher nur Ersatzname „frontend: rot“ und die RED-Ausnahme (#2503) greift nicht. Gate nicht in diesem Ticket ändern (eigenes Issue angelegt, Titel beginnt mit „touched_tests_gate“). **Commit-Reihenfolge in Phase 6:** erst Umsetzung grün machen, dann zwei Commits (Produktion, dann Tests), so bleibt jeder Commit grün und unter 250 Zeilen. Beim Produktions-Commit laufen die Testdateien des Arbeitsbaums mit, die dann grün sind.

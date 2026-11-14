# Context: fix-2999-datumfeld-tag-31

## Request Summary
Issue #2999: Im Baustein `DatumFeld` wird ein eingetippter Tag 29–31 still verändert, wenn der
Bezugsmonat (heutiger Monat bzw. Monat des gespeicherten Werts) weniger Tage hat
(31.03.2027 → 01.03.2027). Erwartung: vollständig getipptes TT.MM.JJJJ landet unverändert im Feld
und im Speicher; ein wirklich ungültiges Datum (31.04.) wird gemeldet, nie still verändert.

## Ursache (belegt im Bibliothekscode, bits-ui 2.17.3 installiert)
- `node_modules/bits-ui/dist/bits/date-field/date-field.svelte.js:19-27` — `SEGMENT_CONFIGS.day.max`:
  ohne getippten Monat `getDaysInMonth(value ?? placeholder)`. Placeholder = heute (kein `placeholder`
  gesetzt in `DatumFeld.svelte`). Im November: max 30 ⇒ „3“+„1“ = 31 > 30 ⇒ „1“ beginnt neu ⇒ „01“.
  Betrifft auch GEFÜLLTE Felder: dort zählt der Monat des gespeicherten Werts (Etappe am 15.04.,
  Nutzer tippt 31.05. ⇒ 01.05.).
- Zweite stille Veränderung (bleibt auch in neuer Version): `date-field.svelte.js:434-447` /
  `:510-516` — wird der Monat NACH dem Tag getippt, klemmt bits-ui den Tag auf die Tageszahl
  dieses Monats im Jahr des **Placeholders** (`dateRef = this.placeholder.current`):
  31 + 04 ⇒ 30.04. still; 29 + 02 bei Placeholder-Jahr 2026 ⇒ 28.02., auch wenn danach 2028 getippt
  wird (gültiges Schaltjahr-Datum wird verfälscht).
- Zusammensetzen am Ende: `getValueFromSegments(... dateRef: placeholder)` ⇒ `CalendarDate.set`
  klemmt ebenfalls (29.02.2027 ⇒ 28.02.2027).

## Upstream-Stand
- bits-ui 2.21.0 (aktuell, 11.11.2026): `getDaySegmentMaxValue` liefert ohne Monat
  `MAX_DAYS_IN_MONTH` (31) und korrigiert die Anzeige während der Eingabe ⇒ behebt den
  Hauptfehler des Issues. Die Monats-Klemmung (`prev.day = daysInMonth`, Zeile 447/527) besteht
  weiter ⇒ 31.04. / 29.02.<Schaltjahr> bleiben still verändert.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/molecules/DatumFeld.svelte | Baustein, `DatePicker.Root` ohne `placeholder`; `geaendert()` meldet Wert, `verlassen()` |
| frontend/src/lib/components/molecules/segmentFeldMeldung.ts | `SegmentFeldMeldung`, `TippZaehler` (Tastendruck-Zählung, Melde-Regel) — reine TS-Logik, per node --test testbar |
| frontend/src/lib/components/molecules/UhrzeitFeld.svelte | Schwesterbaustein (Stunde/Minute fest begrenzt ⇒ kein analoges Problem erwartet) |
| frontend/package.json | `bits-ui ^2.17.3` |
| frontend/e2e/helpers.ts:1151 | `tippeDatum` (Klick ins Tag-Segment, tippt TTMMJJJJ) |
| frontend/e2e/s3b2795-zustellung-laufzeit.spec.ts AC-10 | Staging-Nachweis aus Nutzersicht, datumsabhängig rot |

## Verwender (Dependents)
- Trip anlegen: `TripNewEditor.svelte:698,1040` (Startdatum, `leerMelden`)
- Etappen-Datum: `edit/StageDateField.svelte:42,52` (gefülltes Feld, kompakt)
- Orts-Briefing Laufzeit: `zustellung-tab/LaufzeitKarte.svelte:66`, `shared/versand-tab/VTLaufzeitVergleich.svelte:71`
- `wetter-tab/AnpassenKarte.svelte`

## Existing Patterns
- Bausteinverhalten als reine TS-Logik in `segmentFeldMeldung.ts` + node --test
  (`molecules/__tests__/segment_feld_meldung.test.ts`, `uhrzeit_feld_leeren.test.ts`).
- Browser-Nachweis per Playwright gegen Staging; Uhr lässt sich mit `page.clock.setFixedTime`
  einfrieren ⇒ datumsunabhängiger RED-Test (z. B. Uhr auf 14.11.2026 bzw. Februar).
- Nutzermeldungen nur über i18n-Katalog (ADR-0104), Schlüssel `bausteine.datum.*`.

## Existing Specs
- docs/specs/modules/rework_2881_design_system_bereinigung.md (AC-1..3 DatumFeld, Lieferung B)

## Risks & Considerations
- bits-ui-Upgrade 2.17 → 2.21 betrifft alle bits-ui-Bausteine (Select, Popover, Kalender, Uhrzeit):
  Changelog prüfen, svelte-check + frontend-test + E2E müssen grün bleiben.
- Placeholder steuert auch den Monat, auf dem der Kalender öffnet ⇒ ein fester „Tipp-Placeholder“
  würde den Kalender verschieben.
- Ungültiges Datum melden: neue Meldung (DE/EN) im Baustein, Feld darf nicht still klemmen;
  Verhalten beim Verlassen (zurück auf gespeicherten Wert / leer) mit `leerMelden` abstimmen.
- Schaltjahr-Fall 29.02.2028 muss ankommen.

## Analysis

### Type
Bug

### Ergänzende Befunde (bits-ui 2.17.3, `date-field.svelte.js`)
- Bei Tag-Max 30 (Bezugsmonat November) bleibt „3“ stehen, „1“ ⇒ 31 > 30 ⇒ Segment wird „01“ und springt zum Monat (Z. 828-833).
- Bei Tag-Max 28 (Bezugsmonat Februar) wird „3“ sofort zu „03“ und springt (Z. 805-808): die „1“ landet im Monat, alle Folgeziffern rutschen ein Segment ⇒ Zählung pro Segment ist falsch, nötig ist ein **segmentübergreifender Ziffernstrom**.
- Gefülltes Feld: bits-ui setzt `placeholder` auf den Wert (Z. 184-190) ⇒ ein fester Placeholder greift dort nie.
- Monat nach Tag getippt: Klemmung mit Jahr aus `placeholder.current` (Z. 434-447) ⇒ 31.04. → 30.04., 29.02.2028 → 28.02. still; am Ende zusätzlich `CalendarDate.set`-Klemmung.
- Pfeiltasten klemmen ebenfalls im Bezugsmonat (Z. 745ff) — Randfall, nicht Teil des Issues.
- Gefülltes Feld (Etappe, `StageDateField`) meldet Zwischenstände beim Tippen ⇒ nach „31“ könnte bereits ein geklemmter Zwischenwert gespeichert werden; muss zurückgehalten werden.

### Variantenvergleich
| Variante | 31.03. (Hauptfall) | 31.04. melden | 29.02.2028 | Befund |
|---|---|---|---|---|
| V1 bits-ui 2.21 | gelöst (lt. Upstream) | nein, still 30.04. | verfälscht | allein unzureichend |
| V2 Tipp-Protokoll im Baustein | ja (auch Max 28) | ja | ja | trägt |
| V3 V1+V2 | ja | ja | ja | Upgrade getrennt halten |
| V4 Placeholder dynamisch | teils | nein | teils | trägt nicht (gefülltes Feld, End-Klemmung, Kalendermonat verschoben) |
| V5 eigenes Segmentfeld | ja | ja | ja | Overkill, verwirft #2881 Lieferung B |

### Technical Approach (Entscheidung Tech Lead)
V2 in diesem Fix; bits-ui-Upgrade NICHT gebündelt (sonst ist ein Upgrade-Regress nicht vom Fix trennbar; der RED-Test beweist, dass der Fix unabhängig vom bits-ui-Stand trägt).
- Reine TS-Logik (neben `segmentFeldMeldung.ts`): `DatumTipp` führt je Fokus einen Ziffernstrom; Reset bei Backspace/Pfeil/Tab/Nicht-Ziffer/Fokuswechsel/Klick. Segmentreihenfolge aus den `[data-segment]`-Elementen im DOM (de und en-GB heute beide Tag zuerst). `pruefeTipp(ziffern, reihenfolge)` ⇒ `{ok, iso}` | `{ungueltig}` (Monatslänge + Schaltjahr).
- `DatumFeld.svelte`: Strom im `onkeydowncapture` (läuft vor bits-ui). Solange ein Strom läuft, keine Meldung nach außen (Zwischenstände zurückhalten). Beim 8. Ziffer-Tastendruck steht die Absicht fest:
  - gültig ⇒ getippte Absicht melden (bits-ui-Wert ignorieren), danach Feld neu aufbauen (`aufbau++`), Fokus per `tick()` zurück aufs letzte Segment;
  - ungültig ⇒ Meldung `bausteine.datum.ungueltig` (DE/EN, `role="alert"`, `aria-describedby`) unter dem Feld, nichts speichern, Feld zeigt den Modellwert (gespeichert bzw. leer; bei `leerMelden` keine Doppelmeldung mit „Startdatum fehlt“).
- Kalenderklick und Pfeiltasten unverändert bits-ui.
- `UhrzeitFeld`: Stunde/Minute fest begrenzt ⇒ kein analoges Problem.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/molecules/segmentFeldMeldung.ts (oder neues `datumTipp.ts`) | MODIFY/CREATE | `DatumTipp`, `pruefeTipp` (~70 LoC) |
| frontend/src/lib/components/molecules/DatumFeld.svelte | MODIFY | Strom, Zurückhalten, Neuaufbau, Meldungselement (~40 LoC) |
| frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts | CREATE | node --test Kernlogik (~80 LoC) |
| frontend/src/lib/i18n/messages (de, en) | MODIFY | `bausteine.datum.ungueltig` |
| frontend/e2e/ (neue Spec, ggf. helpers.ts) | CREATE | Playwright mit `page.clock.setFixedTime` (~60 LoC) |

### Scope Assessment
- Files: ~5-6
- Estimated LoC: +~250/-~5
- Risk Level: MEDIUM (zentraler Baustein in Trip-Anlegen, Etappe, Orts-Briefing-Laufzeit, Anpassen; Fokus nach Neuaufbau; Etappen-Zwischenstände)

### Testplan
- node --test: gültig 31.03.2027, 29.02.2028, 31.12.2026, 01.01.2027; ungültig 31.04.2027, 29.02.2027, 30.02.2028, 00.01.2027, 32.01.2027; Strom-Reset (Backspace, Pfeil, Fokuswechsel, Nicht-Ziffer).
- Playwright gegen Staging, Uhr eingefroren auf 2026-11-14 (Max 30) und 2027-02-10 (Max 28, härtester Fall): leeres Feld 31.03.2027 und 29.02.2028 kommen an; 31.04.2027 und 29.02.2027 zeigen Meldung und speichern nichts; gefülltes Etappenfeld 15.04.2027 → 31.05.2027 ohne geklemmten Zwischen-PUT; Meldung auf Englisch; Kalenderklick/Backspace-Regression; bestehende AC-10 in `s3b2795-zustellung-laufzeit.spec.ts` grün.

### Dependencies
Verwender (erben das Verhalten, kein eigener Code): `TripNewEditor.svelte` (leerMelden), `edit/StageDateField.svelte`, `zustellung-tab/LaufzeitKarte.svelte`, `shared/versand-tab/VTLaufzeitVergleich.svelte`, `wetter-tab/AnpassenKarte.svelte`.

### Open Questions
- Keine Produktfrage offen; Meldetext und Platz unter dem Feld werden in der Spec festgelegt und mit ihr freigegeben.
- Nebenbefund: bits-ui-Upgrade 2.17 → 2.21 als eigenes Issue (getrennt vom Fix).

# Adversary Dialog — fix-2999-datumfeld-tag-31
Spec: docs/specs/modules/fix_2999_datumfeld_tag_31.md
Datum: 2026-11-14 12:21

## Checkliste
- [x] **Input:** Nutzer tippt acht Ziffern TTMMJJJJ in das Datumsfeld.
- [x] **Output:** Existiert das Datum, steht es unveraendert im Feld und wird gemeldet/gespeichert; sonst erscheint "Dieses Datum gibt es nicht." und nichts wird gespeichert.
- [x] **Side effects:** Nach gueltiger Eingabe wird das Feld neu aufgebaut, der Fokus bleibt im Feld.
- [x] **AC-1:** Given die Systemuhr steht im November (Monat mit 30 Tagen) und das Datumsfeld ist leer / When der Nutzer 31032027 tippt / Then zeigt das Feld 31.03.2027 und genau dieses Datum wird gemeldet und gespeichert, nicht 01.03.2027.
- [x] **AC-2:** Given die Systemuhr steht im Februar (Monat mit 28 Tagen) und das Datumsfeld ist leer / When der Nutzer 31032027 tippt / Then steht 31.03.2027 im Feld, kein Segment ist verrutscht und der gespeicherte Wert ist 31.03.2027.
- [x] **AC-3:** Given das Datumsfeld ist leer, die Systemuhr steht im Jahr 2026 / When der Nutzer das Schaltjahr-Datum 29022028 tippt / Then kommt 29.02.2028 unveraendert an und wird nicht auf 28.02. verschoben.
- [x] **AC-4:** Given das Datumsfeld ist leer / When der Nutzer das nicht existierende Datum 31042027 tippt / Then erscheint unter dem Feld die Meldung "Dieses Datum gibt es nicht.", es wird nichts gespeichert und das Feld zeigt wieder leer statt 30.04.2027.
- [x] **AC-5:** Given das Datumsfeld ist leer / When der Nutzer 29022027 tippt (2027 ist kein Schaltjahr) / Then erscheint dieselbe Meldung "Dieses Datum gibt es nicht." und es wird weder 28.02.2027 noch 01.03.2027 gespeichert.
- [x] **AC-6:** Given ein Feld mit "Startdatum fehlt"-Pflichtmeldung (leerMelden, Trip anlegen) ist leer / When der Nutzer ein ungueltiges Datum tippt / Then erscheint nur die Meldung "Dieses Datum gibt es nicht." und nicht zusaetzlich "Startdatum fehlt".
- [x] **AC-7:** Given ein Etappenfeld enthaelt 15.04.2027 / When der Nutzer 31052027 darueber tippt / Then steht am Ende 31.05.2027 im Feld, und waehrend des Tippens wird kein Zwischenstand (z. B. 30.04. oder 01.05.) gespeichert; es gibt genau einen Speichervorgang mit 31.05.2027.
- [x] **AC-8:** Given der Nutzer hat ein ungueltiges Datum getippt und die Meldung wird angezeigt / When er danach ein gueltiges Datum tippt / Then verschwindet die Meldung und das gueltige Datum wird wie gewohnt uebernommen.
- [x] **AC-9:** Given die Oberflaeche steht auf Englisch / When der Nutzer 31042027 tippt / Then lautet die Meldung "This date does not exist." und ist fuer Screenreader per `role="alert"` ansagbar und mit dem Feld verknuepft.
- [x] **AC-10:** Given ein Datumsfeld mit Wert / When der Nutzer ein Datum im Kalender anklickt oder mit Backspace ein Segment loescht / Then verhaelt sich das Feld wie bisher (Kalenderklick uebernimmt den Tag, Backspace leert das Segment, nichts wird neu gemeldet bis das Datum vollstaendig ist).
- [x] **AC-11:** Given die bestehende Laufzeit-Pruefung AC-10 aus `s3b2795-zustellung-laufzeit.spec.ts` / When sie nach dem Fix laeuft / Then ist sie unabhaengig vom heutigen Monat gruen.
- [x] **AC-12:** Given das Uhrzeitfeld (`UhrzeitFeld`) / When der Nutzer Stunde und Minute tippt oder loescht / Then ist das Verhalten unveraendert, bestehende Uhrzeit-Tests bleiben gruen und es erscheint keine Datumsmeldung.

## Dialog

### Runde 1
**Adversary:**
Testlauf (benannte Dateien, Ausgabe in `docs/artifacts/fix-2999-datumfeld-tag-31/adversary-test-output-fixloop.txt`): 718 pass, 0 fail (bausteine_waechter, bausteine_waechter_wirkort, deutsch_unveraendert, reaktivitaet_waechter, keine_hartkodierten_nutzertexte, trip_hub_sprache, versand_tab_sprache, datum_tipp, segment_feld_meldung, uhrzeit_feld_leeren).

Pruefpunkt 1 (Rücknahme nur bei ungültigem Ende, nur wenn etwas hinausging): `ruecknahmeNachUngueltig` wird in DatumFeld.svelte nur im else-Zweig des ungültigen Ergebnisses gerufen; sie liefert null bei gleichem Wert oder unbekanntem Start. Gültiges Ende (`ergebnis.ok`) und DS-2 (`widerspricht`/`geaendert`) sind im Diff unberührt. Mutation M8 (Rücknahme zusätzlich im ok-Zweig) bleibt gruen in Node, ist also nur Playwright-bewacht (siehe F006).

Pruefpunkt 2 (AC-6, leerMelden): bei leerem Start ist `wertVorStrom === ''`; ein leeres bits-ui-Feld meldet bei Teil-Eingabe kein vollständiges Datum, es geht also nichts hinaus und `ruecknahmeNachUngueltig('', '')` ist null (Test "gleicher Wert … → null"). `ungueltig = true` wird vor dem onchange gesetzt, TripNewEditor.svelte:729 blendet „Startdatum fehlt" damit aus. Die Rücknahme auf '' (Anlegen mit gefülltem Startdatum) setzt nur `startDate = ''` (makeDateHandler, :357), kein Zusatztext. Keine Doppelmeldung.

Pruefpunkt 3 (Wettlauf): Der Zwischenstand wird in `geaendert` per `tick().then` gemeldet und trägt die Folgenummer `folge`; die 8. Ziffer erhöht `folge` synchron (taste: `folge += 1`), ein noch unterwegs befindlicher Zwischenstand wird dadurch verworfen (`nr !== folge`). Ist er schon hinausgegangen, geschah das synchron (`SegmentFeldMeldung.aendern` ruft `melde` direkt) und der Elternwert ist beim Lesen von `value` in `taste` bereits aktuell (StageDateField.handleChange setzt `value` synchron), die Rücknahme sieht also die Abweichung. Microtasks laufen zwischen zwei echten Tastenereignissen, ein Überholen ist nur bei im selben Task synthetisch abgesetzten Tasten denkbar. Gegenprobe: `if (nr !== folge) return;` entfernt: 718 grün, die Folge-Prüfung ist also in Node nicht bewacht (F006).

Mutations-Gegenprobe (String-Ersetzung, Sicherungskopie im Scratchpad, danach `cmp` identisch):
- M1 ruecknahmeNachUngueltig immer null: 3 rot. M2 Gleich-Prüfung entfernt: 2 rot. M3 Startwert bei jeder Ziffer neu gemerkt: 4 rot.
- M4 null-Prüfung entfernt: 0 rot, äquivalenter Mutant (null !== Wert liefert ohnehin null zurück).
- M5 `modellwert ?? null` -> `?? ''`: 0 rot (F007, LOW).
- M6 Rücknahme-Aufruf in DatumFeld.svelte entfernt, M7 Modellwert nicht an `taste` übergeben, M8 Rücknahme im ok-Zweig, M9 Rücknahme ohne Prüfung gegen Modell, M10 Rücknahme nur bei nichtleerem Wert: je 0 rot (F006).

Finding:
  ID: F006
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:144
  Description: Die Verdrahtung der Rücknahme (Übergabe von `value` an `tipp.taste` :144, Aufruf von `ruecknahmeNachUngueltig` und `onchange` :157-158) und die Folge-Prüfung `nr !== folge` (:101) werden von keinem Node-Test bewacht (Mutationen M6-M10 und Entfernen der Folge-Prüfung: 718 grün). Nur der Staging-Fall `AC-5 langsam` in frontend/e2e/s2999-datumfeld-tag-31.spec.ts:235 bewacht sie, und der lief lokal nicht.
  Spec requirement: AC-5 — kein Zwischenstand (31.05.) bleibt nach ungültigem Datum gespeichert
  Conflict: Die Wirkung (Rücknahme am Ort, den der Nutzer erreicht) ist bis zum Staging-Lauf in /e2e-verify unbewiesen.
  Remediation: Staging-Lauf der Spec in /e2e-verify ist Pflicht-Nachweis; kein Merge/Deploy ohne grünen Fall `AC-5 langsam`.

Finding:
  ID: F007
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:73
  Description: `this.#wertVorStrom = modellwert ?? null` — das Verhalten bei nicht übergebenem Modellwert (null statt '') ist nur über die reine Funktion getestet, nicht über `taste` ohne dritten Parameter.
  Spec requirement: AC-5 — keine unbeabsichtigte Rücknahme
  Conflict: Mutation `?? ''` bleibt grün; DatumFeld übergibt immer `value`, daher kein Nutzerpfad, aber der Vertrag "null = unbekannt" ist ungeschützt.
  Remediation: Ein Test `new DatumTipp().taste('3')` -> `wertVorStrom === null`.

**Implementierer:**
Einverstanden: F006 ist im Design-Rahmen (Node-Suite bewacht die reine Logik, Wirkung an der Verdrahtung steht in der Playwright-Spec). F007 wird als LOW notiert, kein Nutzerpfad.

### Runde 2
**Adversary:**
Nachbohren am Nutzerort: (a) Etappe 15.05.2027, 31062027 langsam: nach „31" geht 31.05. hinaus (DS-2 unverändert), die 8. Ziffer ergibt `{ok:false}`, `ungueltig = true`, Rücknahme meldet 15.05.2027; `neuAufbauen('erstes')` zeigt den Modellwert, `bautNeu` unterdrückt das Echo von bits-ui. Nach dem Verlassen bleibt `iso === value` und es geht nichts mehr hinaus. (b) Nicht ungültig, sondern gültig mit Wert gleich Zwischenstand (31052027 über 15.04.): `ergebnis.iso !== value` verhindert eine zweite Meldung, AC-7 (genau ein Speichervorgang) unberührt. (c) Strom, der durch Nicht-Ziffer abbricht, nachdem ein Zwischenstand hinausging: keine Rücknahme (bewusst, ausserhalb AC-5, gleiches Verhalten wie vorher/DS-2). (d) Neuer Strom überschreibt `wertVorStrom` erst bei leerem Ziffernpuffer (Test :222), Folgeziffern nicht. (e) Mobil: TripNewEditor.svelte:1042 bindet `ungueltig` nicht, Pflichthinweis dort bereits vor diesem Fix ohne Ausblendung (nicht Teil der Fix-Änderung, AC-6 nennt das Desktop-Feld und der Spec-Fall nutzt `trip-new-date-input-desktop`).

AC-Abdeckung: AC-1 bis AC-4 und AC-6 bis AC-12 unverändert (Diff berührt nur den ungültigen Zweig und das Merken; `pruefeTipp`, `widerspricht`, `geaendert`, Uhrzeitfeld, Kalender-Pfad nicht). AC-5: reine Logik in frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts:179-235 (6 Fälle) belegt; Browserwirkung über Staging-Fall e2e/s2999-datumfeld-tag-31.spec.ts:235 (Stabilitätsfenster 2 s, danach Stand per API = 2027-05-15) ausstehend. Die Staging-Config frontend/playwright.2999-datumfeld.staging.config.ts:19-37 ist unverändert und erfasst die Spec über `testMatch`.

Confirmation:
  AC: AC-1 / AC-2 / AC-3 / AC-4 / AC-7 / AC-8
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:27
  Evidence: `pruefeTipp` klemmt nie und ist im Diff unverändert; `ergebnis.ok`-Zweig DatumFeld.svelte:151-153 unberührt, eine Meldung je gültigem Datum.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:53
  Evidence: `ruecknahmeNachUngueltig` gibt den Startwert zurück, wenn er vom Modellwert abweicht (Mutationen M1-M3 rot); aufgerufen im ungültigen Zweig DatumFeld.svelte:155-158; Browserwirkung nur per Staging-Fall bewacht.
  Status: CONFIRMED (Vorbehalt F006)

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:155
  Evidence: `ungueltig = true` vor der Rücknahme; Rücknahme auf '' erzeugt keinen zweiten Text, TripNewEditor.svelte:729 blendet „Startdatum fehlt" bei `datumUngueltig` aus.
  Status: CONFIRMED

Confirmation:
  AC: AC-9 / AC-10 / AC-11 / AC-12
  Code reference: frontend/e2e/s2999-datumfeld-tag-31.spec.ts:235
  Evidence: Meldung/role=alert (DatumFeld.svelte:265), Kalender- und Backspace-Pfad (`geaendert`) und UhrzeitFeld im Diff unberührt; uhrzeit_feld_leeren und Wächter grün (718/0).
  Status: CONFIRMED

Confirmation:
  AC: AC-11 (Staging-Lauf)
  Code reference: frontend/playwright.2999-datumfeld.staging.config.ts:19
  Evidence: Config unverändert seit Runde 3, erfasst die 2999-Spec über `testMatch` (Zeilen 19-37); Prüfer-Bericht Runde 4.
  Status: CONFIRMED

**Implementierer:**
Keine weiteren Einwände; Staging-Lauf folgt in /e2e-verify.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Vorbedingungen stammen aus der Spec (Systemuhr eingefroren per `page.clock.setFixedTime`, Seed-Etappe 15.05.2027, Standardsprache de) und den Node-Tests; keine Werte aus Fremdquellen.

## Verdict

VERDICT: VERIFIED

Begründung: 718 Node-Tests grün; die Rücknahme wirkt nur im ungültigen Zweig und nur bei Abweichung vom Startwert, gültiges Ende, DS-2 und Anlegen/AC-6 sind unverändert, der Wettlauf ist durch `folge` und synchrone Meldung ausgeschlossen. Mutationen an `ruecknahmeNachUngueltig` und am Merken des Startwerts werden rot (M1-M3). Offen und ehrlich ausgewiesen: Verdrahtung in DatumFeld.svelte (M6-M10) und die Folge-Prüfung sind nur durch den Staging-Playwright-Fall bewacht, der lokal nicht lief (F006, MEDIUM, Pflicht-Nachweis in /e2e-verify); F007 LOW.

## Geprüfte Dateien

- sha256:41643079ad8593bdb1de470b297eb5019dab1abdc96a197379c8cbf5bd29ed05  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- sha256:2f3abfd281364691f5860b2b12c6628feba324b84ec3ffac0f055ed0bab9b898  frontend/playwright.2999-datumfeld.staging.config.ts
- sha256:e55f5dded768256c1186e232f6b91cac4b8558a6ce3e98e11f5dc9189109e465  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:26008fbf582d4b87305b0b1e58b644e0de8c44870e8df8831e645e902a8bb25f  frontend/src/lib/components/molecules/datumTipp.ts

## Prüfbasis

- base: 7e5bb6440a923b336e4586ac0b5866af6c70cd11
- blob:bba25eb0ae004a393d89addf52d0bd45d42269cd  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- blob:352a7111b7fbcc89849cb7b96d5762f12d20e30b  frontend/playwright.2999-datumfeld.staging.config.ts
- blob:a6df1850f986e0db874f99eae6b52fda62c8c902  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:138636cfedfb2e4b8ee3f78f529398bd56b8993a  frontend/src/lib/components/molecules/datumTipp.ts

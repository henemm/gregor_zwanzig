# Adversary Dialog — fix-2999-datumfeld-tag-31
Spec: docs/specs/modules/fix_2999_datumfeld_tag_31.md
Datum: 2026-11-14 09:39

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
**Adversary:** Unit 47/47 gruen (adversary-test-output.txt). Code gelesen und Randfaelle sondiert.
Code reference: frontend/src/lib/components/molecules/datumTipp.ts:21 (Monatslaenge/Schaltjahr), frontend/src/lib/components/molecules/datumTipp.ts:39 (Gueltigkeit, nie klemmen), frontend/src/lib/components/molecules/datumTipp.ts:51 (Ziffernstrom).
Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:114 (taste, Strom vor bits-ui), frontend/src/lib/components/molecules/DatumFeld.svelte:95 (Zurueckhalten), frontend/src/lib/components/molecules/DatumFeld.svelte:72 (bautNeu), frontend/src/lib/components/molecules/DatumFeld.svelte:135 (nur gueltig melden), frontend/src/lib/components/molecules/DatumFeld.svelte:248 (role=alert).
Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:128 (datumUngueltig), frontend/src/lib/components/trip-new/TripNewEditor.svelte:700 (bind:ungueltig), frontend/src/lib/components/trip-new/TripNewEditor.svelte:729 (Startdatum fehlt entfaellt).
Code reference: frontend/src/lib/i18n/messages/de/bausteine.json:114, frontend/src/lib/i18n/messages/en/bausteine.json:114 (Katalog DE/EN).
Code reference: frontend/e2e/s2999-datumfeld-tag-31.spec.ts:70 (AC-1/2/3/11), frontend/e2e/s2999-datumfeld-tag-31.spec.ts:141 (AC-6), frontend/e2e/s2999-datumfeld-tag-31.spec.ts:224 (AC-10), frontend/playwright.2999-datumfeld.staging.config.ts:14 (Staging-Config).
Mutations-Gegenprobe datumTipp.ts (16 Verfaelschungen, Sicherungskopie im Scratchpad, danach diff identisch): 15 gefangen (Feb immer 28/29, Jahrhundertregel, 400er-Regel, 30-Tage-Monate, Tag>31 statt Monatslaenge, Monat 13, Tag 0, Strom-Reset bei Nicht-Ziffer, Reset nach 8. Ziffer, ISO-Reihenfolge, feste Segmentreihenfolge, laeuft=false, zuruecksetzen no-op, 7 statt 8 Ziffern). 1 ueberlebt: `jahr < 1000` entfernen (F001).
Svelte-Mutationen sind nur per E2E fangbar (kein Unit-Test deckt DatumFeld.svelte); ich konnte E2E nicht gegen Staging laufen lassen. Gedanklich zugeordnet: bautNeu-Guard entfernen -> AC-1/2/3 (Feb); tipp.laeuft aus `zurueck` entfernen -> AC-7 (PUT-Liste); ungueltig-Zweig ruft onchange -> AC-4/5 (nichts gespeichert); bind:ungueltig entfernen -> AC-6; aria-describedby entfernen -> AC-9; neuAufbauen-Fokus -> AC-1 (Fokus bleibt). Erst auf Staging bewiesen.
Spec-Test-Kritik AC-10-Anpassung: die Backspace-Pruefung ist ehrlich genug (Segment leer, keine Meldung, kein neuer PUT, Anzeige=Speicher nach Verlassen), aber sie belegt "wie bisher" nur durch Behauptung, nicht durch Lauf gegen den Altstand. Die Spec sagt "Backspace leert das Segment"; bits-ui leert beim 2. Rueckschritt alle Segmente. Vertretbar, als F003 vermerkt.
**Implementierer:** keine Gegenrede in dieser Runde (Prueflauf ohne Rueckkanal).

### Runde 2
**Adversary:** Vertiefung. Randfaelle: (a) Strg/Alt/Meta+Ziffer zaehlt im Strom mit (frontend/src/lib/components/molecules/DatumFeld.svelte:116-126, keine ctrlKey-Pruefung) -> F002. (b) Mobiles Startdatum-Feld ohne bind:ungueltig (frontend/src/lib/components/trip-new/TripNewEditor.svelte:1042): Meldung erscheint, Knopftext bleibt "Datum waehlen" (frontend/src/lib/components/trip-new/TripNewEditor.svelte:1267) - kein "Startdatum fehlt"-Text, AC-6 nennt nur diesen; F004 (LOW, AMBIGUOUS-nah). (c) Wird mit weniger als 8 Ziffern verlassen (Etappe, Tag+Monat getippt), meldet verlassen() den von bits-ui geklemmten Stand (frontend/src/lib/components/molecules/DatumFeld.svelte:167); ausserhalb der Spec-Absicht (8. Ziffer). (d) Meldung bleibt nach Verlassen stehen (frontend/src/lib/components/molecules/DatumFeld.svelte:166 nur bei offen); von AC-6-Test so erwartet, daher gewollt. (e) Gueltig-Pfad: onchange synchron, neuAufbauen wartet tick; Race mit asynchronem Eltern-Wert nicht auszuschliessen, E2E AC-7 deckt reale Eltern ab (Staging). (f) svelte-check: 0 Fehler in DatumFeld/datumTipp/TripNewEditor (83 Altfehler anderswo). (g) Regressionen: Verwender StageDateField, VTLaufzeitVergleich, LaufzeitKarte, TripNewEditor erben; neue Huelle `datum-huelle` aendert Layout (inline-flex bei kompakt) - nur visuell auf Staging pruefbar.
Mutationen wiederhergestellt: diff gegen Sicherungskopie identisch fuer datumTipp.ts und DatumFeld.svelte.
**Implementierer:** keine Gegenrede in dieser Runde.

### Runde 3
**Adversary:** Nachbesserung geprueft. Unit 49/49 gruen (adversary-test-output.txt neu).
- F001 behoben: Code reference frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts:67 (01010000, 01010999). Mutation `jahr < 1000` entfernen in frontend/src/lib/components/molecules/datumTipp.ts:39 wird jetzt gefangen (Test "Daten, die es nicht gibt, sind ungueltig"); Sicherungskopie-diff identisch. Alle 16 Mutationen jetzt gefangen.
- F002 behoben im Code: frontend/src/lib/components/molecules/DatumFeld.svelte:119 (ctrl/alt/meta -> Strom zurueck, return, bits-ui unberuehrt). Kein eigener Test; Svelte-Pfad, nur E2E-Regression (Tippen in s2999-Spec frontend/e2e/s2999-datumfeld-tag-31.spec.ts:70 ueberlebt es nicht stoeren). Bewertung: Randfall LOW, Absicherung ohne eigenen Test akzeptabel, Browser-Nachweis in /e2e-verify.
- F004 akzeptiert: frontend/src/lib/components/trip-new/TripNewEditor.svelte:1267 ist die Beschriftung des gesperrten Weiter-Knopfs (trip.anlegen.datum_waehlen), keine Fehlermeldung; AC-6 meint die Pflichtmeldung "Startdatum fehlt" (TripNewEditor.svelte:729, Desktop, gebunden in :700). Kein Widerspruch.
- F003: Spec Known Limitations und Changelog ergaenzt (ACs unveraendert), Spec-Datei docs/specs/modules/fix_2999_datumfeld_tag_31.md:144-160. Akzeptiert.
- Katalog frontend/src/lib/i18n/messages/de/bausteine.json:114 und en/bausteine.json:114 unveraendert gueltig; Staging-Config frontend/playwright.2999-datumfeld.staging.config.ts:14 unveraendert.
- F005 strukturell: Browser-Zusicherungen werden in /e2e-verify auf Staging bewiesen (Hard Gate vor Prod-Deploy).
**Implementierer:** Nachbesserungen wie beschrieben.

Einzelzeilen je geprueftem File (Runde 3):
Code reference: frontend/src/lib/components/molecules/datumTipp.ts:39
Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:119
Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:700
Code reference: frontend/src/lib/i18n/messages/de/bausteine.json:114
Code reference: frontend/src/lib/i18n/messages/en/bausteine.json:114
Code reference: frontend/e2e/s2999-datumfeld-tag-31.spec.ts:70
Code reference: frontend/playwright.2999-datumfeld.staging.config.ts:14
Code reference: frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts:67

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

VERDICT: VERIFIED

Unit 49/49 gruen, 16/16 Mutationen an datumTipp.ts gefangen, F001/F002/F003/F004 erledigt oder akzeptiert. Offen ist nur die strukturelle E2E-Abhaengigkeit (F005, MEDIUM): Der Browser-Nachweis fuer DatumFeld.svelte erfolgt in /e2e-verify auf Staging (Hard Gate vor Prod-Deploy), nicht durch diesen Adversary-Lauf.

## Geprüfte Dateien

- sha256:8287ac7849be2b88a94d9574476c846a8a5edf9af685ca2cccb922b89f1aa4d8  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- sha256:f49dd64e2cb68596f788c295a13b673d4f25ecb3e1b3872f822e036829bd23af  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:8e23a68fc95d2fbef2b50532d14e606a5ee54abc4969cee2e9286d8de21b2372  frontend/src/lib/components/molecules/datumTipp.ts
- sha256:94af5c4b785420ae17441fae0967a9240834081cb2ac88ce3793c1d83fd94837  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:6e27519ec3d23cf94cc7393830ed3f4f646457ccbed86719197de0f8d4c76c65  frontend/src/lib/i18n/messages/de/bausteine.json

## Prüfbasis

- base: f360ae8b475aeec1c568558f604a6a0558638a45
- blob:a72aa0bcdbec0af347ea017c69640753eb3b2ad9  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- blob:ef15b56e9bdd1a7cead94be9b5f1d5cc4fe59c90  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:e61c4449ae076e2b7f41e0f683ae4d35eb8d288a  frontend/src/lib/components/molecules/datumTipp.ts
- blob:e50104be46874d648bb8b244e16baeff8ea7140e  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:79574aec4a4c9dab3638bcde039cf815ce65d0e7  frontend/src/lib/i18n/messages/de/bausteine.json

## Geprüfte Dateien

- sha256:8287ac7849be2b88a94d9574476c846a8a5edf9af685ca2cccb922b89f1aa4d8  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- sha256:2f3abfd281364691f5860b2b12c6628feba324b84ec3ffac0f055ed0bab9b898  frontend/playwright.2999-datumfeld.staging.config.ts
- sha256:f49dd64e2cb68596f788c295a13b673d4f25ecb3e1b3872f822e036829bd23af  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:76c7b4fe7bb0dd987760c69dcb15b8faa471acba1969049329bce68c32c654c9  frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts
- sha256:8e23a68fc95d2fbef2b50532d14e606a5ee54abc4969cee2e9286d8de21b2372  frontend/src/lib/components/molecules/datumTipp.ts
- sha256:94af5c4b785420ae17441fae0967a9240834081cb2ac88ce3793c1d83fd94837  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:6e27519ec3d23cf94cc7393830ed3f4f646457ccbed86719197de0f8d4c76c65  frontend/src/lib/i18n/messages/de/bausteine.json
- sha256:8e124f1c281eb6e74bc584e6bc86481221afd32c923a64572b110a012b73fec5  frontend/src/lib/i18n/messages/en/bausteine.json

## Prüfbasis

- base: f360ae8b475aeec1c568558f604a6a0558638a45
- blob:a72aa0bcdbec0af347ea017c69640753eb3b2ad9  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- blob:352a7111b7fbcc89849cb7b96d5762f12d20e30b  frontend/playwright.2999-datumfeld.staging.config.ts
- blob:ef15b56e9bdd1a7cead94be9b5f1d5cc4fe59c90  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:995e5922e677f2a6e5791f9caf1084f41c784df1  frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts
- blob:e61c4449ae076e2b7f41e0f683ae4d35eb8d288a  frontend/src/lib/components/molecules/datumTipp.ts
- blob:e50104be46874d648bb8b244e16baeff8ea7140e  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:79574aec4a4c9dab3638bcde039cf815ce65d0e7  frontend/src/lib/i18n/messages/de/bausteine.json
- blob:d86111c6e40ae229b6379e4df7ffc9b3ad555052  frontend/src/lib/i18n/messages/en/bausteine.json

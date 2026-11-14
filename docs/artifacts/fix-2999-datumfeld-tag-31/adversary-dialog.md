# Adversary Dialog — fix-2999-datumfeld-tag-31
Spec: docs/specs/modules/fix_2999_datumfeld_tag_31.md
Datum: 2026-11-14 10:10

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
Testlauf (benannte Dateien, volle Ausgabe in `docs/artifacts/fix-2999-datumfeld-tag-31/adversary-test-output.txt`): 595 pass, 0 fail (bausteine_waechter, deutsch_unveraendert, versand_tab_sprache, trip_hub_sprache, datum_tipp, segment_feld_meldung, uhrzeit_feld_leeren). Die drei Regressionen der Validierung sind behoben: keine Huelle um DatumFeld mehr, eigener Zaehler im module-Script statt der props-id, Schluessel `bausteine.datum.ungueltig` in NEU_IN_FOLGEPAKETEN.

Confirmation:
  AC: AC-1 / AC-2 / AC-3
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:27
  Evidence: `pruefeTipp` prueft die 8 Ziffern gegen `tageImMonat` (Schaltjahr inkl. :19-24) und klemmt nie; der Tipp-Strom in `DatumFeld.svelte:136-151` faengt die 8. Ziffer per preventDefault vor bits-ui ab, die Monatslaenge des Bezugsmonats spielt keine Rolle mehr. Mutation `tag > 31` -> 10 Tests rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-4 / AC-5
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:39
  Evidence: ungueltiges Datum liefert `{ ok: false }`; `DatumFeld.svelte:149` setzt `ungueltig = true`, `onchange` wird nicht gerufen (:145-147), `neuAufbauen('erstes')` zeigt das Feld leer.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:700
  Evidence: `bind:ungueltig={datumUngueltig}` am Desktop-Feld; Zeile 729 `{:else if !startDate && !datumUngueltig}` blendet "Startdatum fehlt" aus. Das mobile Feld (TripNewEditor.svelte:1042) ist nicht gebunden, siehe F004.
  Status: CONFIRMED

Confirmation:
  AC: AC-7 / AC-8 / AC-10
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:99
  Evidence: Zurueckhalten waehrend des Ziffernstroms (`tipp.laeuft`), Folgenummer `folge` verwirft Altmeldungen; `ungueltig = false` bei gueltigem Datum (:103, :146). Backspace setzt den Strom zurueck (datumTipp.ts:52-55).
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:256
  Evidence: Meldung mit `id={meldungId}` und `role="alert"`, Text aus dem Katalog; `aria-describedby` an Eingabe (:209) und an jedem Segment (:212). Die id ist je Instanz eindeutig (`++meldungZaehler`, :48); die Meldung liegt im selben Element wie die Segmente, auch bei mehreren Feldern (Etappenliste, mobile Karten) keine Doppel-id. Die Geometriepruefung der e2e (`s2999-datumfeld-tag-31.spec.ts:116-119`) misst gegen `[data-testid]` = `.datum-feld`; die absolut positionierte Meldung vergroessert dessen Box nicht, `top:100%` plus margin liegt >= Unterkante: Pruefung bleibt gueltig. Der AC-9-Selektor (Spec :215) trifft die Segmente innerhalb des Felds: gueltig.
  Status: CONFIRMED

Confirmation:
  AC: AC-11 / AC-12
  Code reference: frontend/playwright.2999-datumfeld.staging.config.ts:19
  Evidence: Staging-Config (workers 1, Basic-Auth, Setup-Login) fuer die Spec; Uhr eingefroren (Spec :17-20), daher monatsunabhaengig. UhrzeitFeld unveraendert, uhrzeit_feld_leeren.test gruen.
  Status: CONFIRMED

SSR/Hydration: `meldungId` wird nur gerendert, wenn `ungueltig` wahr ist; das entsteht erst durch Tippen im Browser, im SSR-Markup fehlt das Attribut. Server-Zaehler (waechst pro Anfrage) und Client-Zaehler (beginnt bei 1) gleichen daher nie ein gerendertes Attribut ab: kein Mismatch, keine Kollision (je Prozess strikt monoton). Anders als die props-id verschiebt der Zaehler keine bits-Kennungen (Golden-Markup gruen).

Abschneiden: Die Meldung ist `position:absolute; white-space:nowrap` (ca. 160 px) und ragt im kompakten Feld (ca. 110 px) nach rechts heraus. Geprueft: StageDateField `.stage-date`/`.box` (kein overflow), `.stage-header-fields` (inline-flex, kein overflow), LaufzeitKarte `.zt-karte` (kein overflow), TripNewEditor `main` (`overflow-x: clip`, nur horizontal am Seitenrand, Z. 632), StageCardM (overflow:hidden nur auf `.title`/`.meta`, nicht auf dem Datumsbereich). `.editor-card` (EditStagesPanelNew.svelte:992, overflow:hidden) enthaelt kein DatumFeld. Kein Abschneiden festgestellt. Die Meldung ueberdeckt (z-index 1, Kartenhintergrund) das Startzeit-Feld neben dem Etappen-Datum (`.stage-header-fields`, EditStagesPanelNew.svelte:944) bzw. die Zeile darunter in StageCardM, solange sie steht (LOW, bewusst laut Kommentar DatumFeld.svelte:266-267).

Mutations-Gegenprobe datumTipp.ts (Zielsuite plus Waechter, 121 Tests): `tag > 31` -> 10 rot; Schaltjahrregel `j % 4 === 0` -> 1 rot; `monat > 13` -> 1 rot; `jahr < 0` -> 2 rot; Schwelle 7 statt 8 Ziffern -> 16 rot; Monatslaenge immer 31 -> 7 rot; Nicht-Ziffer setzt Strom nicht zurueck -> 11 rot; ISO-Zusammenbau vertauscht -> 21 rot. UEBERLEBT: `pruefeTipp(this.#ziffern, reihenfolge)` ohne `reihenfolge` (0 rot).

Mutations-Gegenprobe DatumFeld.svelte (String-Ersetzung, danach `cmp` identisch zur Sicherungskopie): ALLE 10 ueberleben die Node-Suite (0 rot): Ziel-Segment-Pruefung `ziel !== segmente[0]` entfernt; `ungueltig = true` -> false; `role="alert"` -> `role="status"`; feste statt eindeutige Meldungs-id; `preventDefault/stopPropagation` entfernt; `onchange` bei gueltigem Datum entfernt; `folge`-Pruefung entfernt; `top:100%` -> `top:0`; `zurueck = false`; `bautNeu`-Sperre entfernt. Die Komponente hat keinen Node-Test; der Schutz liegt ausschliesslich in `frontend/e2e/s2999-datumfeld-tag-31.spec.ts` (nur Staging, Config `playwright.2999-datumfeld.staging.config.ts`). Nach Code-Lesen der Spec decken AC-1..AC-9 die meisten ab (`top:0` die Geometriepruefung :118-119), die Ausnahmen stehen in den Findings.

Finding:
  ID: F001
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:121
  Description: Die gesamte Tipp-/Melde-Verdrahtung der Komponente (taste, geaendert, neuAufbauen, verlassen, Meldung/aria) ist nur durch die Staging-e2e bewacht; in der Node-Kernsuite bleiben alle 10 Mutationen ohne roten Test. Die Kernlogik in datumTipp.ts ist dagegen gut bewacht.
  Spec requirement: AC-1..AC-9 — Verhalten muss nachweisbar sein
  Conflict: Ein Regress in der Verdrahtung (Meldung nie angezeigt, falsche role, onchange fehlt) faellt erst im Staging-Lauf auf, nicht in der CI-Kernschicht.
  Remediation: `/e2e-verify` gegen Staging ist Pflicht-Gate und muss laufen; optional ein Quelltext-Test (`# doc-compliance-test`) fuer role="alert" und aria-describedby.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:58
  Description: Die Uebergabe von `reihenfolge` an `pruefeTipp` ist durch keinen Test bewacht (0 rot). Fuer de/en-GB ist die Reihenfolge Tag-Monat-Jahr, daher heute folgenlos; ein kuenftiges Format wuerde still falsch pruefen.
  Spec requirement: AC-1 — Datum unveraendert uebernehmen
  Conflict: Bewacht nichts, was ein Nutzer heute erreicht.
  Remediation: Testfall `DatumTipp.taste` mit Reihenfolge month/day/year in datum_tipp.test.ts.

Finding:
  ID: F003
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:48
  Description: Eindeutigkeit der Meldungs-id bei mehreren Feldern wird nirgends getestet (feste id ueberlebt; die e2e nutzt nur ein Feld). Die Implementierung ist korrekt (Zaehler), die Zusicherung ungeschuetzt.
  Spec requirement: AC-9 — mit dem Feld verknuepft
  Conflict: Doppel-id machte aria-describedby mehrdeutig, ohne dass ein Test rot wird.
  Remediation: e2e-Zusatz mit zwei Feldern (Etappenliste) auf Eindeutigkeit der id.

### Runde 2
**Implementierer:** Developer-Fix (Huelle entfernt, Meldung per if-Block im `.datum-feld`, Zaehler im module-Script) liegt vor; keine Rueckfrage zu F001-F003.
**Adversary:** Zweite Pruefung gezielt gegen die Fix-Aenderungen. (1) Sichtbarkeit/aria wie in Runde 1 bestaetigt; `getByRole('alert')` findet das absolut positionierte Element (sichtbar, Groesse > 0). (2) SSR: kein gerendertes Attribut haengt am Zaehler, kein Mismatch. (3) Bindung: `bind:ungueltig` nur am Desktop-Feld des Anlegens (TripNewEditor.svelte:700); das mobile Feld (:1042) zeigt die Datumsmeldung, haelt die Pflichtmeldung aber nicht aktiv zurueck; in der Staging-Spec nur mit DESKTOP-Viewport belegt (F004).
Edge Cases: 8. Ziffer bei Fokus im Monats-/Jahr-Segment startet keinen Strom (bewusst, DatumFeld.svelte:136); Strg+V setzt den Strom zurueck (:126-129); Fokuswechsel in den Kalender gilt nicht als Verlassen (:176).

Finding:
  ID: F004
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:1042
  Description: Das mobile Startdatumfeld (`groesse="gross"`) bindet `ungueltig` nicht; ob dort "Startdatum fehlt" zusaetzlich erscheint, ist per e2e nicht belegt (AC-6 nur Desktop). Nicht reproduziert.
  Spec requirement: AC-6 — keine Doppelmeldung
  Conflict: Moegliche Doppelmeldung im mobilen Anlegen.
  Remediation: `bind:ungueltig` auch am mobilen Feld und dessen Ausblendzweig, oder Staging-Spec mit Mobile-Viewport.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Vorbedingungen (Systemuhr Nov./Feb., Sprache en/de, leeres bzw. gefuelltes Feld) stammen aus der Spec und der Staging-Spec (`page.clock.setFixedTime`, Profil-PUT); nichts davon lief lokal.

## Verdict

VERDICT: VERIFIED

Begruendung: Alle 12 ACs sind durch Code (datumTipp.ts:27-41, DatumFeld.svelte:121-152 und :256) und die Spec-Pruefungen nachvollziehbar belegt; 595 Node-Tests gruen, die drei Regressionen der Validierung sind behoben. Absolut positionierte Meldung: Geometrie- und Selektorpruefung der Staging-e2e bleiben gueltig, id eindeutig, kein overflow:hidden-Elternelement im Weg. Mutationen an datumTipp.ts werden gefangen (eine folgenlose Ausnahme F002); die Verdrahtung in DatumFeld.svelte ist nur durch die Staging-e2e bewacht (F001, MEDIUM, `/e2e-verify` ist Pflicht-Gate). Keine Findings ab HIGH. Die Staging-e2e wurde nicht ausgefuehrt.

## Geprüfte Dateien

- sha256:2f3abfd281364691f5860b2b12c6628feba324b84ec3ffac0f055ed0bab9b898  frontend/playwright.2999-datumfeld.staging.config.ts
- sha256:ef6750ba051da2542f23fbda4979f914967f973beb283a47275aba7f56699a03  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:8e23a68fc95d2fbef2b50532d14e606a5ee54abc4969cee2e9286d8de21b2372  frontend/src/lib/components/molecules/datumTipp.ts
- sha256:94af5c4b785420ae17441fae0967a9240834081cb2ac88ce3793c1d83fd94837  frontend/src/lib/components/trip-new/TripNewEditor.svelte

## Prüfbasis

- base: f360ae8b475aeec1c568558f604a6a0558638a45
- blob:352a7111b7fbcc89849cb7b96d5762f12d20e30b  frontend/playwright.2999-datumfeld.staging.config.ts
- blob:a4a2749f9a1a3a1b3bd25e37de2ff7fa0920bf5f  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:e61c4449ae076e2b7f41e0f683ae4d35eb8d288a  frontend/src/lib/components/molecules/datumTipp.ts
- blob:e50104be46874d648bb8b244e16baeff8ea7140e  frontend/src/lib/components/trip-new/TripNewEditor.svelte

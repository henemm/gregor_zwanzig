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

### Runde 3
**Implementierer:** Fix-Loop nach CI-Rot (3 DS-2-Tests in `design-system-trip-vergleich.spec.ts`): `DatumTipp.widerspricht`, `geaendert()` nutzt `tipp.widerspricht(iso) || zaehler.unfertig(feld)`, `taste()` startet bei angefangenem Tag-Segment keinen neuen Strom, +6 Unit-Tests, +2 Playwright-Tests „AC-7 langsam".
**Adversary:** Tests (benannte Dateien, Ausgabe `docs/artifacts/fix-2999-datumfeld-tag-31/adversary-test-output.txt`): 712 pass, 0 fail (datum_tipp, segment_feld_meldung, uhrzeit_feld_leeren, bausteine_waechter, bausteine_waechter_wirkort, deutsch_unveraendert, reaktivitaet_waechter, keine_hartkodierten_nutzertexte, trip_hub_sprache, versand_tab_sprache). Kein lokaler E2E-Stack (Ports 8197/8107 nicht belegt): Playwright-Spec und DS-2 sind **in CI/Staging zu belegen**, nicht von mir ausgefuehrt. `s2999-datumfeld-tag-31.spec.ts` laeuft nur ueber `playwright.2999-datumfeld.staging.config.ts` (nicht im CI-e2e); DS-2 laeuft im CI-e2e.

Analyse (Code gelesen, nicht im Browser reproduziert):
- (a) AC-7 (Etappe 15.04., 31052027, Verzoegerung 1 s): Ziffer „3" -> bits-ui meldet 03.04., `widerspricht` wahr (Tag „03" beginnt nicht mit „3"), zurueckgehalten; „31" -> geklemmt 30.04., Widerspruch; Monat „05" -> Tag 30 widerspricht noch immer; 8. Ziffer wird vor bits-ui abgefangen, `folge` verwirft den Rest, ein `onchange(2027-05-31)`. Februar-Basis: „3" schliesst bei bits-ui den Tag als 03 ab (Fokus springt zum Monat), Widerspruch greift ueber Position in der Ziffernfolge. OK.
- (b) DS-2: Tag „15" bei Basis 08.: gemeldet 15.08. widerspricht nicht, `unfertig` falsch (Segment voll) -> geht ohne Verlassen hinaus. Wiederhergestellt (Unit-Test `kein Widerspruch (DS-2 Rueckkehr)`; E2E nur CI).
- (c) Edge Cases: MTJ (`#reihenfolge` je Taste gemerkt, Test + Mutation T5/T6 rot); angefangenes Segment (`startsWith`, T3 rot); Rücktaste: Nicht-Ziffer setzt Strom zurueck, naechste Ziffer startet ihn nur bei `data-placeholder` oder fertigem Segment nicht (siehe Mutation S4/S5); Strg+V/Pfeile/Tab setzen Strom zurueck (DatumFeld.svelte:131-135, datumTipp.ts:53); Jahr-Segment: `widerspricht` vergleicht auch Jahrziffern, nur erreichbar nach 4 Ziffern Tag/Monat, daher folgenlos; Februar/Schaltjahr: ueber `pruefeTipp` unveraendert.
- (d) Luecke: Hat die Basis einen 31-Tage-Monat (z. B. 15.05.2027) und wird 31.07. langsam getippt, meldet bits-ui nach „31" 31.05.2027; `widerspricht` ist wahr nur bei getippten, abweichenden Segmenten, der noch nicht getippte Monat zaehlt als vereinbar, `unfertig` ist falsch -> **PUT 31.05.2027 als Zwischenstand**, danach PUT 31.07.2027. Ebenso 20.xx bei jeder Basis. Bei ungueltigem Ziel (31062027 auf Basis 15.05.) bleibt 31.05.2027 gespeichert, obwohl die Meldung „Dieses Datum gibt es nicht." erscheint. Das ist der Kompromiss DS-2 (stimmige Tagesaenderung speichert sofort) gegen AC-7 (kein Zwischenstand); die AC-7-Spec (Basis 15.04./15.02.) deckt nur Monate mit weniger als 31 Tagen ab.

Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad, danach `cmp` je Datei identisch zur Sicherung und `git diff` der Quelldateien identisch zum Ausgangsstand; Zielsuite 10 Dateien, 712 Tests):
- datumTipp.ts: T1 `startsWith`-Treffer -> return false: 4 rot. T2 `getippt` -> immer true: 4 rot. T3 `startsWith` -> `===`: 2 rot. T5 Reihenfolge nicht gemerkt: 2 rot. T6 immer Standardreihenfolge: 2 rot. T7 `pos` nicht erhoeht: 4 rot. T8 Tag/Jahr vertauscht: 4 rot. **T4 UEBERLEBT** (`if (!getippt) return false` -> `continue`, 0 rot): aequivalent solange der Strom lueckenlos ist, kein Nutzer erreicht den Unterschied.
- DatumFeld.svelte (Verdrahtung, die die CI-Roete behebt): **alle UEBERLEBEN, 0 rot**: S1 `tipp.laeuft` statt `widerspricht` (die alte, kaputte Regel); S2 `widerspricht` entfernt; S3 `unfertig` entfernt; S4 `angefangen`-Bedingung in `taste()` entfernt; S5 Ausnahme `data-placeholder` entfernt; S6 `angefangen` nach `zaehler.taste` berechnet; S7 `folge`-Pruefung im `tick` entfernt. Diese Zusicherungen werden ausschliesslich von Playwright bewacht: S1 von den DS-2-Tests (CI-e2e); S2, S4-S7 und der Rest von AC-7/AC-10 nur durch die Staging-Spec (`/e2e-verify`), nicht durch die CI.

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:69
  Evidence: `widerspricht` haelt jeden Wert zurueck, der den fertig getippten Segmenten widerspricht; Unit-Tests belegen 30.04./03.01./30.05. (Mutationen T1-T3, T7, T8 rot). Gesamtverhalten im Browser nicht von mir ausgefuehrt.
  Status: CONFIRMED (Logik), E2E ausstehend

Confirmation:
  AC: AC-1 / AC-2 / AC-3 / AC-4 / AC-5 / AC-6 / AC-8 / AC-9 / AC-10 / AC-11 / AC-12
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:126
  Evidence: Strom, 8.-Ziffer-Abfangen, Meldung und Folgenummer unveraendert gegenueber Runde 2; `taste()` aendert nur die Strombeginn-Bedingung (:141), `geaendert()` nur die Zurueckhalte-Regel (:104). Node-Suite 712 gruen; Browserbeleg ausstehend.
  Status: CONFIRMED

Confirmation:
  AC: Testdateien (geaenderte Dateien)
  Code reference: frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts:133
  Evidence: 6 neue Tests pruefen Widerspruch, Nicht-Widerspruch, leeren Strom, angefangenes Segment und MTJ; die Mutationen T1-T3, T5-T8 werden gefangen.
  Status: CONFIRMED

Confirmation:
  AC: AC-7 langsam (E2E)
  Code reference: frontend/e2e/s2999-datumfeld-tag-31.spec.ts:197
  Evidence: Ziffer-fuer-Ziffer-Test mit 1 s Pause und Stabilitaetsfenster, zwei Basen (04., 02.); belegt nur Monate mit weniger als 31 Tagen. Nicht ausgefuehrt.
  Status: CONFIRMED (Lesart), Ausfuehrung ausstehend

Confirmation:
  AC: AC-11 (Staging-Lauf)
  Code reference: frontend/playwright.2999-datumfeld.staging.config.ts:19
  Evidence: Config unveraendert, testMatch auf die 2999-Spec.
  Status: CONFIRMED

Finding:
  ID: F005
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:104
  Description: `zurueck = tipp.widerspricht(iso) || zaehler.unfertig(feld)` haelt nur Werte zurueck, die einem getippten Segment widersprechen. Basis mit 31-Tage-Monat (15.05.2027), Ziel 31.07.2027 oder 31.06.2027, langsam getippt: nach „31" meldet bits-ui 31.05.2027, der noch nicht getippte Monat gilt als vereinbar, der Wert geht hinaus (PUT 31.05.2027).
  Spec requirement: AC-7 — kein Zwischenstand gespeichert, genau ein Speichervorgang; AC-5 — bei ungueltigem Datum nichts gespeichert
  Conflict: Zwei Speichervorgaenge (31.05. dann 31.07.) bzw. bei ungueltigem Ziel bleibt 31.05.2027 gespeichert, obwohl „Dieses Datum gibt es nicht." erscheint. Nach der Spec-Formulierung (Basis 15.04.) nicht verletzt; DS-2 verlangt dieses Hinausgehen. Im Browser nicht reproduziert.
  Remediation: Entscheidung dokumentieren (DS-2 hat Vorrang) oder Zusatz-AC/E2E-Basis 15.05. (31-Tage-Monat) aufnehmen; alternativ nur zuruckhalten, solange ein Segment des Stroms noch aussteht und der Wert aus einem Strom ab erstem Segment stammt (widerspricht DS-2).

Finding:
  ID: F006
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:141
  Description: Die gesamte neue Verdrahtung (`widerspricht` im Melde-Weg, `angefangen`-Bedingung) hat keinen Node-Test: 7 von 7 Mutationen an DatumFeld.svelte ueberleben die Kernsuite. Die AC-7-langsam-Tests laufen nur in der Staging-Config, nicht im CI-e2e; im CI haengt der Schutz allein an den DS-2-Tests.
  Spec requirement: AC-7 / AC-10 — Zusicherung muss dort geprueft sein, wo sie wirkt
  Conflict: Ein Rueckfall auf die alte Regel (S1) faellt zwar in CI-DS-2 auf, die Entfernung von `widerspricht` (S2) oder der `angefangen`-Bedingung (S4-S6) nur im `/e2e-verify` gegen Staging.
  Remediation: `/e2e-verify` gegen Staging als Pflicht vor Prod; optional die AC-7-langsam-Spec in die CI-Auswahl aufnehmen oder die Entscheidungsfunktion aus `geaendert()` in eine reine Funktion in datumTipp.ts ziehen und per Node testen.

Finding:
  ID: F007
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/molecules/datumTipp.ts:80
  Description: `if (!getippt) return false;` -> `continue` ueberlebt (0 rot); aequivalent bei lueckenlosem Strom.
  Spec requirement: AC-7
  Conflict: Keine Nutzerwirkung.
  Remediation: Keine.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

Vorbedingungen (Systemuhr, Sprache, Basisdatum der Etappe) stammen aus der Spec und der Staging-Spec; nichts davon lief lokal, E2E in CI/Staging zu belegen.

## Verdict

VERDICT: AMBIGUOUS

Begruendung: Alle Node-Tests gruen (712), Logik von `widerspricht` ist per Mutation bewacht, die CI-Ursache (Zurueckhalten jedes Werts bis zur 8. Ziffer) ist im Code behoben. Offen: F005 (MEDIUM) zeigt, dass bei 31-Tage-Basismonaten ein stimmiger Zwischenstand gespeichert wird (DS-2 gegen AC-7); das ist eine Spec-Auslegungsfrage, keine Code-Panne. F006: die Verdrahtung ist nur durch Playwright bewacht, `/e2e-verify` gegen Staging ist Pflicht. Keine Findings ab HIGH. Quelldateien nach den Mutationen identisch zum Ausgangsstand.

## Geprüfte Dateien

- sha256:87374c880ada829b88a2a3765e7c1d3eed14df503823f8074df85075b98210a3  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- sha256:2f3abfd281364691f5860b2b12c6628feba324b84ec3ffac0f055ed0bab9b898  frontend/playwright.2999-datumfeld.staging.config.ts
- sha256:2bf4c970f9651728cf038f85dbc3ed92c82a3f82c38b63c4544b8cfd0851db88  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:c056a1f8d5931e6701ab9a096de8280a9f0dba29897fb98b6f9d7a97ea4deb3e  frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts
- sha256:e335d5188765882cbeeafa40bd6d195eaac6d54161fafe3babbd8bc930a221eb  frontend/src/lib/components/molecules/datumTipp.ts
- sha256:94af5c4b785420ae17441fae0967a9240834081cb2ac88ce3793c1d83fd94837  frontend/src/lib/components/trip-new/TripNewEditor.svelte

## Prüfbasis

- base: 53b92080f4b3bb85fe6d4f7c958d33cc847e430a
- blob:7c253c683a49c1c80c368154233719359c34026b  frontend/e2e/s2999-datumfeld-tag-31.spec.ts
- blob:352a7111b7fbcc89849cb7b96d5762f12d20e30b  frontend/playwright.2999-datumfeld.staging.config.ts
- blob:a1b627b60cbc1526e34b51c1cadc110252a322df  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:75093f6818e9e3c27f621b671ab53194caf66811  frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts
- blob:ba8401c20227fbd2b1235582fc7a4597d90fe538  frontend/src/lib/components/molecules/datumTipp.ts
- blob:e50104be46874d648bb8b244e16baeff8ea7140e  frontend/src/lib/components/trip-new/TripNewEditor.svelte

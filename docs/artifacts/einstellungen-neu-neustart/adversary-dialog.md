# Adversary Dialog — einstellungen-neu-neustart
Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md
Datum: 2026-11-10 14:09

## Checkliste
- [x] **Input:** Quelltexte des Frontends (Wächter), Mockup-Datei und i18n-Katalog (Generator), Staging-URL und Elementliste (Abgleich), Bilder (Prüf-Agent).
- [x] **Output:** Wächter grün/rot im CI; `elementliste.json`; Abgleich-Bericht JSON + Markdown; Prüf-Agent-Befund je Runde.
- [x] **Side effects:** Neue Merge-Sperre im CI (`frontend-test`); sonst keine. Keine Änderung an Produktfunktion, Nutzerdaten oder Produktion.
- [x] **AC-1:** Given eine Seiten-Datei in `SEITEN_SCOPE` enthält ein `<style>`-Element, ein `style=`-Attribut oder eine Tailwind-Utility-Klasse / When der Wächter `bausteine_waechter.test.ts` läuft / Then wird der Test rot und nennt Datei und Regel (a); ohne diese Konstrukte bleibt er für dieselbe Datei grün. (bestätigt; Umgehungen siehe F004)
- [x] **AC-2:** Given eine Seiten-Datei in `SEITEN_SCOPE` verwendet ein rohes `<button>`, `<input>`, `<select>`, `<textarea>` oder `<table>` oder importiert eine Komponente außerhalb von `$lib/components/{atoms,molecules,organisms}` / When der Wächter läuft / Then wird er rot; dieselbe Datei mit Baustein-Komponenten statt rohen Elementen ist grün. (bestätigt; Umgehungen siehe F004)
- [x] **AC-3:** Given eine neue Baustein-Datei in `atoms/molecules/organisms` enthält einen px-Wert (ausgenommen 0 und 1px-Rahmen), eine Hex-Farbe oder einen Schriftwert ohne `var(--g-*)`-Token / When der Wächter läuft / Then wird er rot, weil neue Baustein-Dateien bei 0 Ausnahmen starten; Werte wie 0, 1px, %, fr, auto und calc/min/max über Tokens bleiben erlaubt. (Teilregeln ungeschützt, F001, F005) Runde 2/3 belegt: Teilregeln einzeln bewacht (Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:277), Mutationen gefangen.
- [x] **AC-4:** Given die Ratsche `AUSNAHMEN` führt je Bestandsdatei den heutigen Ist-Stand / When ein Eintrag erhöht oder eine neue Ausnahme ergänzt wird / Then wird der Wächter rot; sinkt ein Eintrag (Datei wurde bereinigt), bleibt er grün und verlangt keine Anhebung. (Funktion getestet, Verdrahtung im Lauf ungetestet, F001) Runde 2/3 belegt: Ratsche im Lauf vom Wirkort-Test bewacht (bausteine_waechter_regeln.ts:479), AUSNAHMEN 398 als Ist-Stand erklärt.
- [x] **AC-5:** Given eine neue `.svelte`-Datei liegt unter `routes/` oder `lib/components/**` außerhalb der Baustein-Ordner und steht weder in `SEITEN_SCOPE` noch in der Bestandsliste / When der Wächter läuft / Then wird er rot; trägt man sie in `SEITEN_SCOPE` ein, wird sie nach Regel (a) geprüft; die Bestandsliste darf nur sinken. (Neue-Datei-Teil bestätigt; Bestandsliste im Lauf ungetestet, F001) Runde 2/3 belegt: Bestandsliste, Obergrenze, Verwaiste, Doppelte durch Mutationen bewacht (bausteine_waechter_regeln.ts:463).
- [x] **AC-6:** Given ein Verstoß ist mit `audit:exempt` und einer Begründung markiert / When der Wächter läuft / Then wird der Verstoß toleriert; fehlt die Begründung, wird der Wächter rot. (bestätigt; Randlücken F007)
- [x] **AC-7:** Given der heutige Bestand des Repos mit leerem bzw. nur neue Dateien enthaltendem `SEITEN_SCOPE` und `AUSNAHMEN` = Ist-Stand / When `node --test` auf `bausteine_waechter.test.ts` gegen den echten Quellbaum läuft / Then ist der Wächter grün, ohne dass bestehende Seiten verändert wurden.
- [x] **AC-8:** Given ADR-0112 liegt unter `docs/adr/` / When `tests/test_adr_index_drift.py` läuft / Then ist der Test grün: der Index in `docs/adr/README.md` enthält die Zeile 0112, ADR-0111 trägt „Ergänzt durch: ADR-0112“, und ADR-0112 nennt die vier Regeln (nur Bausteine, fehlende zuerst ins System, nur Tokens, Wächter blockt beim Merge) sowie Prüfdatum 2027-02-08 und Löschbedingung.
- [x] **AC-9:** Given das Mockup `mockup-hub-fassung3.html` / When der Generator `scripts/elementliste_aus_mockup.ts` läuft / Then entsteht `docs/context/einstellungen_neu/elementliste.json` mit dem Hash der Mockup-Datei und Einträgen für alle Kombinationen Kontext (Trip, Orte) × Zustand (normal, lädt, Ladefehler, Konto mit Lücken) × Reiter (Wetter, Zustellung, Etappen bzw. Orte) × Kanal-Segment (E-Mail, Telegram, SMS, Premium-SMS, 3-Tages-Ausblick, bei Orte zusätzlich Stundenverlauf), ohne `.tag`, `data-fb` und `.frame`. (Testkorrektur treu zum Mockup, siehe Runde 2 und F008)
- [x] **AC-10:** Given die erzeugte `elementliste.json` / When ein beliebiger Eintrag gelesen wird / Then enthält er die Felder `id` (stabil über zwei Generator-Läufe), `ctx`, `reiter`, `zustand`, `abschnitt`, `ordnung`, `rolle`, `text_de`, `muster`, `i18n_key`, `text_en` und `luecke`; dynamische Texte (Zahlen, Namen, Werte) erscheinen als ein Element mit `muster`, nicht als je Wert ein Eintrag.
- [x] **AC-11:** Given ein Mockup-Text hat im DE-Katalog einen exakten Treffer, einen Musterabgleich oder keinen Treffer / When der Generator `text_en` ermittelt / Then kommt EN aus dem Katalog (Schlüssel in `i18n_key`) bzw. über das Muster; ohne Treffer wird `luecke: true` gesetzt und `text_en` nicht erfunden. (Grundverhalten bestätigt; Schutzregeln gegen Fehlzuordnung ungetestet, F006)
- [x] **AC-12:** Given `elementliste.json` wurde aus einem Mockup-Stand erzeugt / When die Mockup-Datei verändert wird, ohne die JSON neu zu erzeugen / Then wird `elementliste_aktuell.test.ts` rot (Hash-Abweichung); bei unverändertem Mockup ist er grün, und der Test braucht keinen Browser.
- [x] **AC-13:** Given die Staging-Spec `elementliste-abgleich.staging.spec.ts` und eine Elementliste / When der Abgleich gegen Staging läuft / Then entsteht ein Bericht als JSON und Markdown, in dem jedes Element den Status gefunden, abweichend oder `nicht_pruefbar` (mit Grund) trägt; nicht herstellbare Zustände werden zuerst per Route-Abfangen hergestellt und nie still übersprungen; der Prozess endet mit Exit 0. (nie live gelaufen, F002) Runde 3 belegt: Konto mit Lücken per GET-Abfangen (elementliste_abgleich_logik.ts:312), Live-Lauf zustellung/luecken 111 abweichend, 0 nicht_pruefbar.
- [x] **AC-14:** Given der Abgleich-Bericht enthält Abweichungen oder `nicht_pruefbar`-Elemente / When mit `--strict` aufgerufen wird / Then endet der Lauf mit Exit ungleich 0; ohne `--strict` endet er mit 0. Mit `--scope <reiter/zustand>` werden nur Elemente dieser Teilmenge geprüft und berichtet. (Logik getestet; Flags `--strict`/`--scope` existieren als CLI nicht, F003; Verdrahtung ungetestet, F002) Runde 2/3 belegt: Starter scripts/elementliste_abgleich.ts:27, Flags und Exit per Unterprozess-Test bewacht, Live-Lauf Strict Exit 1, ohne Strict Exit 0.
- [x] **AC-15:** Given die Konfiguration des Staging-Abgleichs zeigt versehentlich auf die Produktions-URL / When der Abgleich startet / Then bricht `assertNotProdBaseURL` den Lauf ab, bevor eine Seite geladen wird; der Abgleich läuft nicht im PR-CI (keine Aufnahme in die sechs CI-Checks). (Wirkung von mir live bestätigt, aber kein Test bewacht die Aufrufstellen, F002) Runde 2/3 belegt: Config-Prod-Schutz playwright.elementliste.staging.config.ts:11, Unterprozess-Test mit Prod- und Staging-URL.
- [x] **AC-16:** Given die Agent-Definition `.claude/agents/mockup-bildpruefer.md` / When sie gelesen wird / Then legt sie feste Eingaben fest (Mockup-Bild, Staging-Bild gleicher Viewport und Zustand, Elementlisten-Auszug), verbietet Quellcode-Zugriff (keine Lese-, Such- oder Shell-Werkzeuge außer Bildlesen), begrenzt auf höchstens zwei Runden je Scheibe und beschreibt, dass sie die Elementliste ergänzt und nicht ersetzt.
- [x] **AC-17:** Given die Doku `docs/reference/gates_und_ratschen.md`, `design_system.md` und `workflow_und_agenten.md` / When ein Leser den Wächter oder den Scheiben-Ablauf nachschlägt / Then beschreiben sie den Wächter mit Regeln (a), (b) und Neue-Datei-Regel, nennen in der Regel-Budget-Tabelle das Prüfdatum 2027-02-08 mit Löschbedingung und beschreiben den Ablauf Scheibe → Staging-Abgleich → Prüf-Agent (höchstens zwei Runden); `CLAUDE.md` bleibt innerhalb von 120 Zeilen / 12 KB.
- [x] **AC-18:** Given die Lieferung ist vollständig / When der Diff gegen `origin/main` geprüft wird / Then enthält er keine Änderung an Produktfunktion (keine Dateien unter `internal/`, `cmd/`, `api/`, `src/` und keine Änderung an Svelte-Seiten oder -Komponenten unter `frontend/src/routes/` bzw. `frontend/src/lib/components/`), und alle sechs CI-Checks sind grün. (Diff-Teil bestätigt; die sechs CI-Checks laufen erst am PR)

## Dialog

### Runde 1
**Adversary:**
Alle Aussagen unten sind aus dem Quelltext gelesen und per Lauf belegt. Tests: `npm test` vollständig 8786 Tests, 8780 pass, 0 fail (5 skipped, 1 todo); Mockup-Playwright 2 passed; Python-Doku-Tests (3 benannte Dateien) 42 passed. Rohausgaben: docs/artifacts/einstellungen-neu-neustart/adversary-test-output.txt.

Mutations-Gegenprobe (String-Ersetzung, Sicherungskopie im Scratchpad, nach jeder Mutation Original zurückkopiert und per cmp identisch geprüft, nie git checkout/stash/reset): 102 Mutationen, 55 von einem Test gefangen, 47 überlebt. Gefangen: Regel (a) Tailwind/style/`<style>`/rohe Elemente/Import-Whitelist/class:- und style:-Direktive, Regel (b) px/hex/1px-Ausnahme/Schrift, Ratsche-Funktion, Neue-Datei-Regel, audit:exempt-Begründungsprüfung und Geltungsfenster, Hash-Check, EN-Exakttreffer und Lücke, Exit-Code und Scope-Funktionen, `assertNotProdBaseURL` selbst, Generator-Ausschlüsse (.tag) und Zustände (per Playwright-Spec gegen die eingecheckte Liste). Überlebt: siehe Findings.

Finding:
  ID: F001
  Severity: HIGH
  Category: anti_pattern
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:436
  Description: Im Lauf `waechterLauf` (dem Pfad, den CI und AC-7 tatsächlich ausführen) sind die Wirkstellen von Regel (b) und der Bestandsliste ungetestet. Entfernt man den Aufruf `pruefeRatsche(ist, konfig.AUSNAHMEN)` (Z. 436), leert `ist` (Z. 431-435: `if (n) ist[d] = n`), ersetzt `dateien.filter(istBaustein)` durch `[]` (Z. 432), entfernt die Verwaist-Prüfung der AUSNAHMEN (Z. 437-439) oder den Aufruf `pruefeBestandsliste(...)` (Z. 420), bleibt jeder Test grün (6 Mutationen überlebt). Die Funktionen selbst sind einzeln getestet, aber nicht dort, wo sie wirken. Gegenprobe ohne Mutation: eine neue Baustein-Datei mit `padding: 12px` im echten Baum macht den Lauf rot (Positivkontrolle von mir, Datei danach gelöscht), das Verhalten stimmt also heute, ist aber nicht bewacht.
  Spec requirement: AC-3, AC-4, AC-5 — neue Bausteine starten bei 0, Ratsche darf nur sinken, Bestandsliste darf nur sinken.
  Conflict: Ein künftiger Umbau von `waechterLauf` kann Regel (b) und die Bestandsliste stilllegen, ohne dass ein Test rot wird. Der echte Baum ist heute exakt auf Ist-Stand, deshalb fällt das beim AC-7-Test nicht auf. Das ist die Fehlerklasse „Zusicherung am Code-Ort statt am Wirkort geprüft“.
  Remediation: Fixture-Baum-Test über `waechterLauf` mit (1) neuer Baustein-Datei mit px-Verstoß und `AUSNAHMEN: {}` muss rot sein, (2) Baustein mit Ist-Stand über Eintrag rot, (3) BESTAND über Obergrenze und verwaister Eintrag rot, (4) Eintrag in AUSNAHMEN für nicht existierende Datei rot.

Finding:
  ID: F002
  Severity: HIGH
  Category: spec_violation
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:114
  Description: Der Staging-Abgleich (AC-13/14/15) ist nie live gelaufen und im CI nur über Stringprüfungen und Logik-Funktionen abgesichert. Die Definition of Done verlangt „Staging-Abgleich einmal ohne --strict gelaufen, Bericht liegt vor“; das ist nicht erfüllt. Ich konnte ihn auch nicht fahren: Das Setup scheitert mit HTTP 401, weil die nginx-Zugangsdaten `GZ_VALIDATOR_*` weder in /home/hem/gregor_zwanzig_staging/.env noch sonst lesbar sind (Befehl `npx playwright test -c playwright.elementliste.staging.config.ts`, Ausgabe in der Testausgabe-Datei, Abschnitt 5). Mutationen an der Spec, die kein Test fängt (alle überlebt): Prod-Schutz-Argument fest auf Staging gesetzt (Z. 33 und Z. 114), Prod-Schutz in der Config entfernt oder auf Konstante gesetzt (Config Z. 15), `leseOptionen` durch feste Werte ersetzt (Z. 115), Scope ignoriert (Z. 117), Exit-Assertion entfernt (Z. 198), Route-Abfangen für Ladefehler zu `route.continue()` entschärft (Z. 72), Bericht-Markdown nicht geschrieben (Z. 195), Zustand „nicht herstellbar“ still übersprungen statt `nicht_pruefbar`, „gefunden“ ohne Abschnitt-Marker. Die AC-15-Tests prüfen nur `indexOf('assertNotProdBaseURL(')` vor `.goto(`, das auch bei einem wirkungslosen Aufruf grün bleibt. Positiv: Die echte Wirkung des Prod-Schutzes habe ich bestätigt (`GZ_SVELTE_BASE=https://gregor20.henemm.com npx playwright test -c playwright.elementliste.staging.config.ts` bricht beim Laden der Config mit „E2E-Lauf gegen PRODUKTION verboten“ ab, Exit 1, keine Seite geladen). Zusätzlich ist ungeprüft, ob die Seiten-Pfade (`/trips/<id>` und `/compare/<id>` mit tab-Parameter) und die Zielermittlung (`/api/trips`, `/api/compare/presets`) auf Staging überhaupt greifen.
  Spec requirement: AC-13 (Bericht vollständig, Exit 0, Route-Abfangen, nie still übersprungen), AC-14 (Strict/Scope), AC-15 (Abbruch vor Seitenaufruf), Definition of Done.
  Conflict: Die Lieferung belegt weder, dass die Spec gegen Staging läuft, noch bewacht ein Test ihre Verdrahtung. Die Logik-Funktionen sind grün, die Spec, die sie benutzt, ist unbelegt.
  Remediation: Abgleich einmal live ohne Strict fahren (mit Validator-Zugang, z. B. durch eine Sitzung mit den Zugangsdaten) und den Bericht als Artefakt ablegen; die Verdrahtung in eine ohne Browser testbare Funktion ziehen (Optionen, Scope, Exit, Prod-Schutz mit der echten Base-URL) und diese per Unit-Test bewachen, oder den Prod-Schutz per Test mit gesetzter `GZ_SVELTE_BASE` gegen die Config laden.

Finding:
  ID: F003
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:121
  Description: Die in AC-14 genannten Aufrufe `--strict` und `--scope <reiter/zustand>` gibt es als Kommandozeile nicht. `npx playwright test -c playwright.elementliste.mockup.config.ts --list --strict` endet mit „error: unknown option '--strict'“, ebenso `--scope`. Die Implementierung nutzt Umgebungsvariablen `ELEMENTLISTE_STRICT` und `ELEMENTLISTE_SCOPE` (dokumentiert in gates_und_ratschen.md). Das Lesen von `--strict`/`--scope` aus `process.argv` (Z. 121-133 der Logik, Aufruf Spec Z. 115) ist damit toter Code.
  Spec requirement: AC-14 — „mit `--strict` aufgerufen“, „Mit `--scope <reiter/zustand>`“.
  Conflict: Der Wortlaut der AC ist so nicht ausführbar; die Abweichung (Playwright reicht keine eigenen Flags durch) steht nur im Kommentar des Spec-Kopfs, nicht in der freigegebenen Spec.
  Remediation: Spec-Text auf die Umgebungsvariablen anpassen oder ein dünner Starter (`node`-Skript), der `--strict`/`--scope` entgegennimmt und die Variablen setzt. Toten argv-Zweig entfernen oder testen.

Finding:
  ID: F004
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:213
  Description: Echte Umgehungen von Regel (a), per Probe belegt (Datei in SEITEN_SCOPE würde grün): (1) `<svelte:element this="button">x</svelte:element>` — Z. 213 prüft nur `RegularElement`, `SvelteElement` kommt nicht in die Rohelement-Prüfung; nicht unter den dokumentierten Restlücken. (2) `<svelte:head><style>.a{color:red}</style></svelte:head>` — Z. 198 prüft nur `ast.css` (Top-Level-Style), ein `<style>` in svelte:head oder per `{@html}` fällt durch. (3) Pfad-Trick `$lib/components/atoms/../shared/Foo.svelte` — `BAUSTEIN_IMPORT` (Z. 50) prüft nur das Präfix, kein Normalisieren. (4) Barrel-Import ohne `.svelte` über relativen Pfad (`import { Foo } from '../shared'`) — Z. 204 hält nur `.svelte` und `$lib/components/` für Komponenten. (5) Spread `{...{class:"flex"}}` und `{...{style:"a:b"}}` unsichtbar. (6) Tailwind-Präfixliste unvollständig: `table-fixed`, `caption-bottom`, `transform-gpu`, `backface-hidden`, `mask-b-from-50%`, `field-sizing-content`, `scheme-dark`, `wrap-anywhere`, `contain-layout`, `prose`, `@container` werden nicht erkannt (Z. 109-128). Außerdem überlebt die Mutation, das `<script module>`-Import-Scannen (Z. 199) auf `[ast.instance]` zu verkürzen: kein Test deckt Importe im Modul-Skript ab.
  Spec requirement: AC-1, AC-2, Known Limitations (Regex-Wächter sind umgehbar, Restlücken werden dokumentiert).
  Conflict: (1) und (2) sind einfache, naheliegende Wege, die Regel zu umgehen, und stehen nicht in der Restlücken-Liste. Für den Wächter, der den Merge blockt, ist das eine Schwachstelle in der Kernaussage, keine Randnotiz.
  Remediation: `SvelteElement` mit statischem `this` in ROHE_ELEMENTE einbeziehen, alle `<style>`-Elemente im Fragment melden (RegularElement mit name `style`), Importpfade normalisieren (`path.posix.normalize`) und Barrel-Importe aus `$lib/components/` sowie relative Nicht-`.svelte`-Importe, die auf components zeigen, prüfen; Test je Fall; sonst Restlücken in gates_und_ratschen.md und ADR-0112 ergänzen.

Finding:
  ID: F005
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:242
  Description: Teilregeln von Regel (b) ohne Test (Mutation überlebt): Farbfunktionen `rgb()/hsl()` (Z. 242; im Test nur über den zusätzlich getroffenen px-Wert im `rgba(0,0,0,0.2)`-Beispiel gefangen), Farbnamen (Z. 243-245), `var(--fremd)` außerhalb `--g-*` (Z. 246), `style=`-Attribut und `style:`-Direktive in Bausteinen (Z. 326, 332), Tailwind-Arbitrary-Werte `p-[12px]` (Z. 342-345), Neutralisieren von Kommentaren und @-Präludien (Z. 308-310), `padding: 1px` zählt als Verstoß (1px-Ausnahme nur für Rahmen, Test deckt nur den Rahmenfall). Dazu belegte Umgehungen: `border: 1px solid red` (Farbname nur für reine Farb-Eigenschaften geprüft, Z. 243); eigene Custom Properties mit Ziffer im Namen werden nie gelesen, z. B. `--g-s-2: 12px` (Deklarationsregex Z. 261 erlaubt keine Ziffern im Namen, `--x:12px` wird erkannt, `--g-s-2:12px` nicht); Großschreibung `PADDING:12PX` (Einheitenregex Z. 247 ist case-sensitiv). Die Doku (gates_und_ratschen.md, ANTI-PATTERNS.md) beschreibt diese Teilregeln als Pflicht mit Wächter.
  Spec requirement: AC-3 — Farbe, Abstand, Größe, Radius, Schrift, Schatten nur über `var(--g-*)`.
  Conflict: Dokumentierte Zusicherungen ohne bewachenden Test; zwei Umgehungen sind unter den dokumentierten Restlücken nicht erwähnt.
  Remediation: je Teilregel ein rotes und ein grünes Fixture-Paar; Deklarationsregex auf `[a-zA-Z0-9_-]+` und `i`-Flag für Einheiten; Farbnamen auch in Kurzschreibweisen (`border`, `box-shadow`, `outline`).

Finding:
  ID: F006
  Severity: MEDIUM
  Category: anti_pattern
  Code reference: scripts/elementliste_aus_mockup.ts:128
  Description: Die Schutzregeln, die verhindern, dass der Generator EN erfindet, sind in den CI-Tests unbewacht. Die Mutation „Wortlaut-Halbe-Regel entfernen“ (Z. 128, Kommentar nennt den Fall „°C · vor der Etappe“) bleibt im Unit-Test grün; gegen die eingecheckte Liste (4148 Elemente) ändert sie das Ergebnis, sie wäre nur vom Playwright-Generator-Spec (`playwright.elementliste.mockup.config.ts`) gefangen, der in keinem CI-Workflow läuft (Suche in .github: keine Treffer für „elementliste“). Weitere überlebende Mutationen: Wertlängen-Grenze Z. 130, Leer-EN-Ausschluss Z. 95, Mindest-Wortlaut Z. 103, Platzhalter-Prüfung Z. 106, Normalisierung Z. 122; diese ändern die heutige Liste nicht (wirkungsgleich auf den Daten), sind aber ebenfalls ohne Test. Der Generator-Spec fing 3 von 4 Generator-Mutationen (`.tag` entfernt, Werte-Varianten nicht zusammengefasst, Ladefehler-Zustand ausgelassen); `.frame` aus dem Ausschluss zu nehmen blieb ohne Wirkung, weil der Rahmen außerhalb aller Lese-Wurzeln liegt.
  Spec requirement: AC-11 — `text_en` nicht erfunden; AC-10 — Generator-Läufe stabil.
  Conflict: Fehlzuordnungen von EN-Texten würden nur bei einem manuellen Generator-Lauf auffallen, nicht im Merge.
  Remediation: je Schutzregel einen Unit-Test mit echtem Katalog (ein Treffer, der ohne die Regel falsch zugeordnet würde); den Generator-Spec nicht in den PR-CI aufnehmen (Zeit), aber im Workflow-Ablauf (`/60-validate`) vorschreiben.

Finding:
  ID: F007
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:193
  Description: Mehrere kleine Randlücken ohne Test: (1) Nicht parsebare Seiten-Datei wird gemeldet (Z. 193-197); die Mutation „fail-soft: leere Liste zurückgeben“ überlebt. (2) Der zusätzliche Verstoß `exempt` für `audit:exempt` ohne Begründung (Z. 94-102) überlebt Entfernen; ebenso die Mindestlänge der Begründung (Z. 74: ein Buchstabe genügt nach Mutation). (3) `BESTAND_OBERGRENZE` (Z. 675) kann auf 999 gesetzt werden, der Test prüft nur `<=` (Kommentar im Test sagt „Obergrenze = Länge“); doppelte Bestandseinträge (Z. 395) und `SEITEN_SCOPE`-Prüfungen (Z. 422-426) ohne Test. Diese Konstante gemeinsam mit BESTAND in derselben Datei zu erhöhen bleibt allein Reviewsache.
  Spec requirement: AC-4/AC-5/AC-6.
  Conflict: schwache Bewachung der Ratschen-Konstanten.
  Remediation: Test `BESTAND_OBERGRENZE === BESTAND.length` (oder gegen eine zweite, getrennte Quelle), Fixture für Parse-Fehler und für exempt-Folgeverstoß.

Finding:
  ID: F008
  Severity: LOW
  Category: spec_violation
  Code reference: frontend/src/lib/__tests__/elementliste_aktuell.test.ts:62
  Description: Die Korrektur des RED-Tests (Kanal-Segmente gehören zum Reiter Wetter, nur in normal und Konto mit Lücken) ist dem Mockup treu und schwächt den Test nicht: `viewWetter` (mockup-hub-fassung3.html Z. 440-444) kehrt bei `lädt` und `Ladefehler` vor der Karte zurück, die Karte „Inhalt je Kanal und Fläche“ samt Segment-Auswahl steht in Z. 451 und 524-525, `viewZustellung` (Z. 539-576) enthält kein Kanal-Segment (nur das Segment `laufzeit`). Der Test verlangt weiterhin 5 bzw. 6 Segmente je Kontext in den zwei Zuständen und verbietet Segmente außerhalb Wetter. Der Wortlaut von AC-9 (Reiter × Kanal-Segment) beschreibt die Kreuzmenge dagegen zu grob; die Spec sollte auf „Kanal-Segmente im Reiter Wetter, Zustände normal und Konto mit Lücken“ präzisiert werden.
  Spec requirement: AC-9.
  Conflict: Spec-Text und Mockup weichen ab; der Test folgt dem Mockup (richtig), die Spec nicht.
  Remediation: Spec-Text (AC-9) bei Gelegenheit angleichen; keine Codeänderung nötig.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:198
  Evidence: `<style>`-Block (Z. 198), `style=`-Attribut (Z. 219), Tailwind in Klassen-Attribut, -Ausdruck und `class:`-Direktive (Z. 220-226) werden über den Svelte-AST erkannt und nennen Datei, Zeile, Regel (a); je 9 rote Fixtures plus saubere Seite grün. Mutationen an diesen Stellen wurden alle gefangen. Umgehungen siehe F004.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:204
  Evidence: rohe button/input/select/textarea/table (Z. 213), Fremd-Importe über `.svelte`-Endung und `$lib/components/`-Präfix (Z. 204-207); Mutationen (Rohelement-Prüfung aus, Whitelist aus, Svelte-Endung) gefangen. Umgehungen siehe F004.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:68
  Evidence: Begründung nötig (Z. 74), Geltungsfenster Zeile und Vorzeile (Z. 70), kein Datei-Freibrief; Mutationen „ohne Begründung tolerieren“, „Fenster weiter“, „Fenster nur eigene Zeile“, „ganze Datei“, „Exempt in Regel (a) entfernt“ alle gefangen. Randlücken F007.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:416
  Evidence: `waechterLauf(FRONTEND_SRC, KONFIG)` ist grün gegen den echten Baum (66 pass im Wächter-Test, Nachlauf 97 pass über drei Dateien); 204 Bestandsdateien und 39 Bausteine mit 396 Verstößen stimmen mit der Doku überein (von mir nachgezählt).
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md:1
  Evidence: Testlauf der drei benannten Python-Dateien tests/test_adr_0112_bausteine_regel_doku.py, tests/test_adr_index_drift.py, tests/test_claude_md_budget.py: 42 passed; ADR enthält die vier Regeln, Prüfdatum 2027-02-08 und Löschbedingung; ADR-0111 trägt „Ergänzt durch: ADR-0112“; Index-Zeile 0112 vorhanden.
  Status: CONFIRMED

Confirmation:
  AC: AC-9
  Code reference: scripts/elementliste_aus_mockup.ts:366
  Evidence: Generator steuert Kontext × Zustand × Reiter × Kanal-Segment über echte Klicks (Z. 366-433), schließt `.tag,.frame,.fb,[data-fb]` aus (Z. 149); Playwright-Spec `elementliste-generator.mockup.spec.ts` grün (2 passed) und fing 3 von 3 wirksamen Generator-Mutationen; Liste enthält 4148 Elemente, alle Soll-Kombinationen vorhanden (Test grün).
  Status: CONFIRMED

Confirmation:
  AC: AC-10
  Code reference: scripts/elementliste_aus_mockup.ts:247
  Evidence: stabile IDs (Hash über Identität, Z. 269-275), zwei Läufe liefern identische IDs und identisch mit der eingecheckten Liste (Mockup-Spec grün), Werte-Varianten werden zu einem Element mit Muster (Z. 259-266), Mutation „Varianten nicht zusammenfassen“ gefangen.
  Status: CONFIRMED

Confirmation:
  AC: AC-12
  Code reference: scripts/elementliste_aus_mockup.ts:60
  Evidence: `pruefeHashAktuell` vergleicht SHA-256 der Mockup-Bytes mit dem Hash in der JSON, ohne Browser (dynamischer Playwright-Import erst Z. 325-334); Mutationen „ok immer true“, „Hash über Konstante“, „ist aus JSON“ alle gefangen.
  Status: CONFIRMED

Confirmation:
  AC: AC-16
  Code reference: .claude/agents/mockup-bildpruefer.md:1
  Evidence: Frontmatter `tools: Read`, feste drei Eingaben, Verbot Quellcode/Specs/Tests/Repo-Suche, höchstens zwei Runden, „ergänzt die Elementliste und ersetzt sie nicht“; Probelauf liegt vor (docs/artifacts/einstellungen-neu-neustart/mockup-bildpruefer-probelauf.md). Einschränkung: Das Werkzeug `Read` kann technisch jede Datei lesen, das Verbot ist Textanweisung; die Aussage „Befund beruht nur auf den Eingaben“ stützt sich im Probelauf auf die Selbstangabe des Agenten.
  Status: CONFIRMED

Confirmation:
  AC: AC-17
  Code reference: docs/reference/gates_und_ratschen.md:1
  Evidence: Wächter-Abschnitt mit Regeln (a), (b), Neue-Datei-Regel, Regel-Budget-Zeile mit Prüfdatum 2027-02-08 und Löschbedingung; Ablauf Scheibe → Staging-Abgleich → Prüf-Agent (höchstens zwei Runden) in workflow_und_agenten.md; tests/test_claude_md_budget.py grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-18
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:29
  Evidence: Diff gegen origin/main für `internal/`, `cmd/`, `api/`, `src/`, `frontend/src/routes`, `frontend/src/lib/components` ist leer; neue Dateien liegen nur in frontend/e2e, frontend/src/lib/__tests__, scripts, docs, .claude/agents. Die sechs CI-Checks sind noch nicht gelaufen (erst am PR).
  Status: CONFIRMED

Weitere geprüfte Dateien (Code reference für das Coverage-Gate):
- frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:1 — Regeln und Konfiguration, siehe F001, F004, F005, F007
- scripts/elementliste_aus_mockup.ts:1 — Generator, siehe F006
- scripts/package.json:1 — nur `"type": "module"` für den scripts-Ordner; im Ordner liegt kein weiteres JS/TS, keine Auswirkung auf andere Werkzeuge
- frontend/e2e/elementliste_abgleich_logik.ts:90 — `exitCode`/`baueBericht`/`filtereScope`: Mutationen gefangen (Strict, nicht_pruefbar, Default-Status, Grundpflicht, Scope-Filter)
- frontend/e2e/elementliste-abgleich.staging.spec.ts:1 — siehe F002
- frontend/playwright.elementliste.staging.config.ts:15 — Prod-Schutz beim Laden der Config wirksam (live bestätigt), Aufrufstelle ungetestet, siehe F002
- frontend/playwright.elementliste.mockup.config.ts:1 — nur Generator-Lauf, nicht im CI
- frontend/src/lib/__tests__/elementliste_aktuell.test.ts:62 — Testkorrektur, siehe F008
- frontend/src/lib/__tests__/elementliste_abgleich.test.ts:77 — nur `e4!`-Typkorrektur, keine inhaltliche Änderung
- .claude/agents/mockup-bildpruefer.md:1 — AC-16
- docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md:1, docs/adr/README.md:1, docs/adr/0111-design-vorgaben-bereinigt-audit-2026-11.md:1, docs/design-system/ANTI-PATTERNS.md:1 — Doku, Tests grün
- docs/reference/gates_und_ratschen.md:1, docs/reference/design_system.md:1, docs/reference/workflow_und_agenten.md:1 — AC-17
- docs/context/einstellungen_neu/elementliste.json:1 — generiert, 4148 Elemente, Hash im Test grün

**Implementierer:**

### Runde 1 (Nachtrag, zweiter Durchgang des Prüfers)
**Adversary:**
Zweiter Durchgang, bewusst gegen die Runde-1-Annahmen: (1) Alle sechs mutierten Dateien nach jeder Mutation per `cmp` gegen die Sicherungskopie auf identisch geprüft, am Ende erneut (alle identisch); Nachlauf der drei Frontend-Testdateien nach allen Mutationen: 97 pass, 0 fail. (2) Positivkontrolle der Wirkung im echten Baum: Eine neue Baustein-Datei mit px und Hex macht `waechterLauf` rot, eine neue `.svelte` unter `routes/` ohne Eintrag ebenfalls; beide Testdateien danach entfernt (git status zeigt nichts davon). Das Verhalten ist heute korrekt, F001 betrifft nur die fehlende Bewachung. (3) AC-9-Testkorrektur gegen das Mockup nachgelesen (siehe F008): treu, kein Abschwächen. (4) Probe von über 150 Tailwind-Klassen und 60 CSS-Deklarationen: die belegten Lücken stehen in F004 und F005; Hauptfälle (Varianten `md:`/`hover:`/`dark:`, `!`, negative Werte, Arbitrary `[...]`, Klassen-Array, Template-String, `class:`-Direktive, Komponente mit `class`, Stile in `@media`/`@keyframes`/`:global`) werden erkannt. (5) Staging-Abgleich: Live-Lauf nicht möglich (HTTP 401 mangels nginx-Zugang), Prod-Schutz der Config live bestätigt; AC-14-Flags als CLI nicht vorhanden (F003). (6) Erwartung der frühen Einigkeit geprüft: 55 von 102 Mutationen gefangen, die 47 Überlebenden sind in F001-F007 aufgelistet; davon wirkungsgleich (kein Fund): `.frame` aus dem Ausschluss (außerhalb aller Lese-Wurzeln), doppelte Scope-Unbekannt-Prüfung (zweite fängt dasselbe) sowie die EN-Schutzregeln, die auf den heutigen Daten gleich ausgehen.
**Implementierer:**

### Runde 2
**Adversary:**
Prüfung des Fix-Loops 1, Angaben des Entwicklers nachgemessen. Tests: `npm test` vollständig 8875 Tests, 8869 pass, 0 fail; Generator-Spec (Mockup-Playwright) 2 passed; Python-Doku-Tests (3 benannte Dateien) alle grün. Rohausgaben: docs/artifacts/einstellungen-neu-neustart/adversary-test-output.txt.

Mutations-Gegenprobe Runde 2 (String-Ersetzung, externe Sicherungskopie, nach jeder Mutation cmp identisch): 96 Mutationen, 71 gefangen, 25 überlebt. Enthalten: alle in Runde 1 überlebten Wächter-, EN- und Abgleich-Mutationen erneut, dazu neue in planeAbgleich, routenPlan, seitenPfad, bewerteAbschnitt, schreibeBericht, abschluss, flagsAlsUmgebung, loginAusEnvText, Starter, Config, fremderKomponentenImport und den neuen Regel-(a)-Zweigen.

Stand der Runde-1-Findings:
- F001 behoben: alle Wirkort-Mutationen in waechterLauf werden von bausteine_waechter_wirkort.test.ts gefangen.
- F002 im Kern behoben: Verdrahtung browserfrei und getestet, Config-Prod-Schutz im Unterprozess geprüft. Live-Lauf wiederholt: --scope wetter/fehler Exit 0 mit 85 Elementen, --strict --scope zustellung/fehler Exit 1.
- F003 behoben: Starter und npm-Skript übersetzen Flags, unbekannte Option Exit 2, Exit-Code live durchgereicht.
- F004, F005, F007 behoben (Proben und Mutationen); F006 bis auf eine wirkungsgleiche Längengrenze behoben.
- F008 (LOW) offen: Spec-Text AC-9 unverändert, nur Spec-Pflege.

AUSNAHMEN 396 auf 398 (PresetRail 19 auf 21) geprüft: reine Neuzählung durch die strengere Begründungsregel, keine Lockerung. frontend/src/lib/components/organisms/PresetRail.svelte Z. 72 hat ein nacktes audit:exempt ohne Begründung; die alte Regel las das Fragment als Begründung, die neue zählt Verstoß und Folgeverstoß.

Finding:
  ID: F009
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:229
  Description: routenPlan('luecken') gibt sofort nicht_herstellbar zurück, ohne Route-Abfangen zu versuchen. Dadurch sind 1840 von 4148 Elementen nicht_pruefbar mit dem Grund, der Zustand lasse sich nicht per Route-Abfangen herstellen, ohne Kontodaten zu ändern. Das ist nicht glaubwürdig: Abfangen ändert keine Kontodaten. Die Seiten lesen das Konto per GET (frontend/src/lib/components/shared/AlarmeTab.svelte:201, frontend/src/lib/server/profileLoader.ts:14); eine per page.route ersetzte Antwort ohne Telegram und mit unbestätigter SMS stellt den Zustand her. Der Test elementliste_abgleich_verdrahtung.test.ts:88 zementiert das Ausweichen.
  Spec requirement: AC-13 — nicht herstellbare Zustände zuerst per Route-Abfangen herstellen, nie still übersprungen.
  Conflict: Dokumentiert, aber der geforderte erste Schritt fehlt; --strict kann für 44 Prozent der Liste nie grün werden.
  Remediation: Profil-Antwort per page.route überschreiben und nur bei Misslingen nicht_pruefbar mit konkretem Grund, oder in der Spec ausdrücklich in die Scheibe Zustellung verschieben.

Finding:
  ID: F010
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:211
  Description: Schwach bewachte Ränder, überlebende Mutationen: Import-Whitelist ohne Abschluss (atomsEvil ginge durch); 0px-Ausnahme, Kommentar- und @-Präludium-Neutralisierung (nur zu viel Melden); EN-Wertlängen-Grenze in scripts/elementliste_aus_mockup.ts:130 (auf Daten wirkungsgleich); Spec-Glue in frontend/e2e/elementliste-abgleich.staging.spec.ts (Route-Installation, Segment-Klick, Aufräumen, Logout, Bericht- und Exit-Aufruf, goto), Exit-Durchreichung im Starter scripts/elementliste_abgleich.ts:51, Segment-Gruppierung, Sortierung nach ordnung, luecke-Prüfung in erwartung, Basic-Auth-Bedingung der Config. Wirkung von Scope, Exit, Ladefehler, Bericht live bestätigt, der Rest nur live belegt.
  Spec requirement: AC-2, AC-13, AC-14.
  Conflict: Ränder ohne Unit-Test, keine Lücke in der Kernaussage.
  Remediation: Abschlusstest atomsEvil; Starter-Prozess mit Strict-Fixture; Spec-Glue weiter durch den Live-Lauf in /60-validate belegen.

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:277
  Evidence: Hex, Farbfunktion, Farbname (auch Kurzschreibweisen), fremde Variablen, Maß case-insensitiv, Schrift, style=, style:, Tailwind-Arbitrary je durch eigenen Test bewacht.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:479
  Evidence: Ratsche im Lauf vom Wirkort-Test bewacht; AUSNAHMEN 398 als Ist-Stand erklärt.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:463
  Evidence: Bestandsliste, Obergrenze, Verwaiste, Doppelte, Scope-Konsistenz durch Mutationen bewacht.
  Status: CONFIRMED

Confirmation:
  AC: AC-14
  Code reference: scripts/elementliste_abgleich.ts:27
  Evidence: Flags übersetzt, Scope und Strict live bestätigt, unbekannte Option Exit 2 bewacht.
  Status: CONFIRMED

Confirmation:
  AC: AC-15
  Code reference: frontend/playwright.elementliste.staging.config.ts:11
  Evidence: Prod-Schutz beim Laden, Unterprozess-Test mit Prod- und Staging-URL, drei Mutationen gefangen.
  Status: CONFIRMED

Weitere geprüfte Dateien (Runde 2):
- frontend/src/lib/__tests__/bausteine_waechter_wirkort.test.ts:1 — Wirkort-Test
- frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts:53 — Verdrahtung und Config-Ladetest
- frontend/src/lib/__tests__/elementliste_en_schutz.test.ts:1 — EN-Schutzregeln
- scripts/elementliste_abgleich.ts:1 — Starter
- frontend/e2e/elementliste_abgleich_logik.ts:176 — planeAbgleich und Verdrahtung
- frontend/e2e/elementliste-abgleich.staging.spec.ts:1 — Spec-Glue, live bestätigt
- frontend/playwright.elementliste.staging.config.ts:1 — kein Setup-Projekt, Basic-Auth nur bei GZ_VALIDATOR_*
- frontend/package.json:14 — npm-Skript elementliste:abgleich
- frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:1 — erweiterte Regeln
- docs/reference/gates_und_ratschen.md:627 — Restlücken und Starter dokumentiert

**Implementierer:**

### Runde 3
**Adversary:**
Prüfung des Fix-Loops 2. Tests: `npm test` vollständig 8884 Tests, 8878 pass, 0 fail; Generator-Spec 2 passed; Python-Doku-Tests grün (Rohausgaben in adversary-test-output.txt).

Mutations-Gegenprobe Runde 3 (String-Ersetzung, externe Sicherung, cmp identisch): 25 Mutationen, 18 gefangen, 7 überlebt. Beide gezielt wiederholten Runde-2-Überlebenden sind jetzt gefangen: Import-Whitelist-Abschluss `(/|$)` (bausteine_waechter_wirkort.test.ts:168) und Exit-Durchreichung des Starters (Unterprozess-Test mit Ersatz-npx, elementliste_abgleich_verdrahtung.test.ts:275).

F009 geprüft:
- Nur GET wird umgeschrieben: `methode: 'GET'` im Plan (frontend/e2e/elementliste_abgleich_logik.ts:312) und die Methodenprüfung im Spec-Glue (frontend/e2e/elementliste-abgleich.staging.spec.ts:167) lassen alles andere per route.continue durch. Es wird nur die Antwort an den Browser ersetzt (lueckenProfil, Z. 215), kein Schreibzugriff auf das Konto. Mutation am Plan (GET zu POST) gefangen; die Methodenprüfung im Spec-Glue selbst ist nur live bewacht (siehe F011).
- Abfangmuster (Z. 208): Mutationen Profil-Teil entfernt, __data.json-Teil entfernt, Muster auf alle /api/auth/ erweitert: alle gefangen. Umschreiben (lueckenProfil, devalue-Feld, Seitendaten, Folgezeilen, ersetzeKontoAntwort): alle Mutationen gefangen bis auf eine wirkungsgleiche. herstellungsGrund (Z. 320): beide Mutationen gefangen.
- Live-Lauf selbst: `--scope zustellung/luecken` Exit 0, 111 abweichend, 0 nicht_pruefbar, kein Treffer „nicht hergestellt“. F009 ist damit behoben, die Abfang-Strategie wirkt.

Finding:
  ID: F011
  Severity: LOW
  Category: edge_case
  Code reference: frontend/e2e/elementliste-abgleich.staging.spec.ts:167
  Description: Der Spec-Glue für Konto mit Lücken (Methodenprüfung Z. 167, Zähler umgeschrieben, Aufruf von herstellungsGrund Z. 172, navigiereImBrowser Z. 176, fulfill mit neuem Body) und serviceWorkers 'block' (frontend/playwright.elementliste.staging.config.ts:29) haben keinen Unit-Test; alle sechs Mutationen überleben. Die Wirkung ist durch meinen Live-Lauf belegt (kein nicht_pruefbar), ein Ausfall einer dieser Zeilen fiele aber nur im Live-Lauf auf, nicht in npm test. Eine Mutation (navigation as const) ist reiner Typ-Unterschied und wirkungsgleich, flach-nur-geaendert (Logik Z. 249) ebenfalls.
  Spec requirement: AC-13.
  Conflict: Live-only Glue, im Protokoll dokumentiert; kein Fehler in der Kernaussage.
  Remediation: Live-Lauf in /60-validate als Nachweis behalten.

Finding:
  ID: F012
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts:129
  Description: Der Test importiert `devalue` dynamisch, ohne dass es in frontend/package.json steht. CI-Risiko geprüft: devalue ist in frontend/package-lock.json:1515 als Top-Level-Eintrag `node_modules/devalue` (5.9.4) hoisted, weil svelte und @sveltejs/kit es brauchen. `npm ci` installiert exakt nach Lockfile, daher läuft der Test in CI. Fragil nur, wenn SvelteKit devalue künftig nicht mehr hoistet oder entfernt.
  Spec requirement: AC-13 (Testbarkeit).
  Conflict: implizite Abhängigkeit.
  Remediation: `devalue` als devDependency in frontend/package.json eintragen.

Weitere geprüfte Dateien (Runde 3): frontend/e2e/elementliste_abgleich_logik.ts:208, frontend/e2e/elementliste-abgleich.staging.spec.ts:164, frontend/playwright.elementliste.staging.config.ts:29, scripts/elementliste_abgleich.ts:50, frontend/src/lib/__tests__/bausteine_waechter_wirkort.test.ts:168, frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts:129, frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:211.

Confirmation:
  AC: AC-13
  Code reference: frontend/e2e/elementliste_abgleich_logik.ts:312
  Evidence: Konto mit Lücken wird per GET-Abfangen von /api/auth/profile und __data.json hergestellt; live 111 von 111 Elementen geprüft, keines nicht hergestellt; Mutationen gefangen.
  Status: CONFIRMED

**Implementierer:**

Zusätzliche Quellenangaben (Runde 3):
Code reference: frontend/src/lib/__tests__/bausteine_waechter_wirkort.test.ts:168
Code reference: frontend/src/lib/__tests__/elementliste_en_schutz.test.ts:1
Code reference: frontend/src/lib/__tests__/elementliste_abgleich.test.ts:1
Code reference: frontend/playwright.elementliste.mockup.config.ts:1
Code reference: frontend/package.json:14
Code reference: scripts/package.json:1

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
VERDICT: VERIFIED

F009 (MEDIUM) ist behoben und live belegt, beide Runde-2-Überlebenden (Whitelist-Abschluss, Starter-Exit) sind jetzt gefangen. Offen nur LOW: F011 (Live-only Spec-Glue), F012 (devalue nicht in package.json, hoisted im Lockfile), F008 (Spec-Text AC-9), Rest von F010.
Tests: npm test 8878 passed, 0 failed; Generator-Spec 2 passed; Python-Doku-Tests grün. Mutationen Runde 3: 25 gefahren, 18 gefangen, 7 überlebt (live-only oder wirkungsgleich).

## Geprüfte Dateien

- sha256:df7a1440b1a23608c72877fc4ef4d47011fcb865ebd694fb4a5336a9eda5951c  .claude/agents/mockup-bildpruefer.md
- sha256:761cb2b7c692486b59b167b6618a54a8f674539c87607ae6127f9e0de9c81985  docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md
- sha256:d43f99f524f7ef6749b6a2b024cdb2bbcf151743054a21d2b7eb4a19fd08519b  docs/reference/gates_und_ratschen.md
- sha256:2eccf0d3a81acf8d598c3ebf6f0340720d06cceff9638e754e499bc3a1031075  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:c2e74b19336427a3e02f26004adeb2f4b2273efbfbc70fea589265ad6ac2f5ac  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:5a62cef1b28fcc0a62e6063cf98742339fc8ba3a2c74ff01b2c94405d79f8cc9  frontend/playwright.elementliste.staging.config.ts
- sha256:4322cb7a669e1f723fad5af5034328b0f04e5f9cefbc2a470c70129f1a744c12  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:70c193302ea2e5f6ee7bf5ab428bdce431f3b6b4be7d70da873c9c07e676bdae  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:c084225dde668dc7ccdee6c6586f8ff402470169d8dc97b5602f4e965d7a3a57  frontend/src/lib/__tests__/elementliste_aktuell.test.ts
- sha256:97d788f0b8d7c276ffc0b77807ce5e9168e9fecb36d463e42eabffaf0257c146  scripts/elementliste_abgleich.ts
- sha256:86d67c18bc36cd0179ca8803eab0ccc766ff58d4cd20760ecf297adffe59fcd9  scripts/elementliste_aus_mockup.ts

## Prüfbasis

- base: 18a18a79e77832253ea412dbd90024d0b6ed7192
- blob:fc1da2cbd5d52a5afbd8f5fc9e816b5f7238f900  .claude/agents/mockup-bildpruefer.md
- blob:f9ec41c901c559c8bdf11e60266c0274953144db  docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md
- blob:aae480354d012f646fcc48367e875fc8fc997b45  docs/reference/gates_und_ratschen.md
- blob:c9b4168fcbab37adaf7c5b0d49f5443bca43b03e  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:30f7d178e8bc179fa080b0099e38a523c95f1dc6  frontend/e2e/elementliste_abgleich_logik.ts
- blob:c486673691fc316785df6fff2747a7fbf8a1b2cd  frontend/playwright.elementliste.staging.config.ts
- blob:8270c55f5bae54e2ff17b20b5bde92e313ed7726  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:de234d95458e4c84d6ca5faad7e1e4a716f64ab7  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:a917886ddad4bc2327b491cb6c6f6f90ce6db2a2  frontend/src/lib/__tests__/elementliste_aktuell.test.ts
- blob:4b2162abe4719ec99efd03f48e8708221828cd83  scripts/elementliste_abgleich.ts
- blob:3c4329b5338e32fe12e3e7425c4cadd752e476fe  scripts/elementliste_aus_mockup.ts

## Geprüfte Dateien

- sha256:df7a1440b1a23608c72877fc4ef4d47011fcb865ebd694fb4a5336a9eda5951c  .claude/agents/mockup-bildpruefer.md
- sha256:761cb2b7c692486b59b167b6618a54a8f674539c87607ae6127f9e0de9c81985  docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md
- sha256:d43f99f524f7ef6749b6a2b024cdb2bbcf151743054a21d2b7eb4a19fd08519b  docs/reference/gates_und_ratschen.md
- sha256:2eccf0d3a81acf8d598c3ebf6f0340720d06cceff9638e754e499bc3a1031075  frontend/e2e/elementliste-abgleich.staging.spec.ts
- sha256:c2e74b19336427a3e02f26004adeb2f4b2273efbfbc70fea589265ad6ac2f5ac  frontend/e2e/elementliste_abgleich_logik.ts
- sha256:4f63dc02d399886685bc930d35a015b14eb6580eb3b3096c467baa299527dfbc  frontend/package.json
- sha256:1c45ff32131016eee45559e7ab7799cbc85d2b35924409b72cc27bd4778a603f  frontend/playwright.elementliste.mockup.config.ts
- sha256:5a62cef1b28fcc0a62e6063cf98742339fc8ba3a2c74ff01b2c94405d79f8cc9  frontend/playwright.elementliste.staging.config.ts
- sha256:4322cb7a669e1f723fad5af5034328b0f04e5f9cefbc2a470c70129f1a744c12  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- sha256:114b861ce6c3915f2535b7a195cb3ba4c05b46f6a15bc47624e3c87aeedba36e  frontend/src/lib/__tests__/bausteine_waechter_wirkort.test.ts
- sha256:458a322ee561b2969c451507885cb4daff71f8d7a5ad17553cec2c3e04c1744a  frontend/src/lib/__tests__/elementliste_abgleich.test.ts
- sha256:70c193302ea2e5f6ee7bf5ab428bdce431f3b6b4be7d70da873c9c07e676bdae  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- sha256:c084225dde668dc7ccdee6c6586f8ff402470169d8dc97b5602f4e965d7a3a57  frontend/src/lib/__tests__/elementliste_aktuell.test.ts
- sha256:866843fd7bf7c137ff5c75412768fa9362ab60db0d898510181aea9f8d285fc5  frontend/src/lib/__tests__/elementliste_en_schutz.test.ts
- sha256:97d788f0b8d7c276ffc0b77807ce5e9168e9fecb36d463e42eabffaf0257c146  scripts/elementliste_abgleich.ts
- sha256:86d67c18bc36cd0179ca8803eab0ccc766ff58d4cd20760ecf297adffe59fcd9  scripts/elementliste_aus_mockup.ts
- sha256:0385fda995db3c27ba5bc3fb6cf6d9893b0224f0c2d501ecd916fbcfeadd1986  scripts/package.json

## Prüfbasis

- base: 18a18a79e77832253ea412dbd90024d0b6ed7192
- blob:fc1da2cbd5d52a5afbd8f5fc9e816b5f7238f900  .claude/agents/mockup-bildpruefer.md
- blob:f9ec41c901c559c8bdf11e60266c0274953144db  docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md
- blob:aae480354d012f646fcc48367e875fc8fc997b45  docs/reference/gates_und_ratschen.md
- blob:c9b4168fcbab37adaf7c5b0d49f5443bca43b03e  frontend/e2e/elementliste-abgleich.staging.spec.ts
- blob:30f7d178e8bc179fa080b0099e38a523c95f1dc6  frontend/e2e/elementliste_abgleich_logik.ts
- blob:b4a0a9b30c85b0c9322fd3481a410789d040e40e  frontend/package.json
- blob:19dd274246be14cce0d26b99513baeb7e72921ee  frontend/playwright.elementliste.mockup.config.ts
- blob:c486673691fc316785df6fff2747a7fbf8a1b2cd  frontend/playwright.elementliste.staging.config.ts
- blob:8270c55f5bae54e2ff17b20b5bde92e313ed7726  frontend/src/lib/__tests__/bausteine_waechter_regeln.ts
- blob:c58994c5848784bab04508621a53add3e85a6117  frontend/src/lib/__tests__/bausteine_waechter_wirkort.test.ts
- blob:2504b6db2219185858df1c4c29894f21005f401d  frontend/src/lib/__tests__/elementliste_abgleich.test.ts
- blob:de234d95458e4c84d6ca5faad7e1e4a716f64ab7  frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts
- blob:a917886ddad4bc2327b491cb6c6f6f90ce6db2a2  frontend/src/lib/__tests__/elementliste_aktuell.test.ts
- blob:253e3990c9b512d709a63559ae7ee8346ffa01a1  frontend/src/lib/__tests__/elementliste_en_schutz.test.ts
- blob:4b2162abe4719ec99efd03f48e8708221828cd83  scripts/elementliste_abgleich.ts
- blob:3c4329b5338e32fe12e3e7425c4cadd752e476fe  scripts/elementliste_aus_mockup.ts
- blob:ea42417527b8b330b0d2b1fa4826acd1fbbb4400  scripts/package.json

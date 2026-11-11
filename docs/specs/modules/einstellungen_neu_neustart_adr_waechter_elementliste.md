---
entity_id: einstellungen_neu_neustart_adr_waechter_elementliste
type: module
created: 2026-11-10
updated: 2026-11-10
status: draft
version: "1.0"
tags: [einstellungen-neu, adr-0112, waechter, elementliste, design-system, epic-2791, issue-2913]
---

# Einstellungen neu – Neustart Schritt 1–2: ADR-0112, Bausteine-Wächter, Elementliste, Staging-Abgleich, Prüf-Agent

## Approval

- [ ] Approved

## Purpose

Neustart von „Einstellungen neu“ (Issue #2913, Epic #2791): Bevor Seiten gebaut werden, wird die Regel „Oberflächen entstehen nur aus Design-System-Bausteinen und Tokens“ als ADR-0112 festgeschrieben und durch einen Merge-Wächter erzwungen. Zusätzlich entsteht eine maschinenlesbare Elementliste aus dem Mockup (Fassung 3) mit Staging-Abgleich und ein unabhängiger Prüf-Agent, damit „fertig“ künftig „Elementliste lückenlos“ heißt und nicht „Tests grün“.

## Source

- **File:** `docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md`, `frontend/src/lib/__tests__/bausteine_waechter.test.ts`, `scripts/elementliste_aus_mockup.ts`, `docs/context/einstellungen_neu/elementliste.json`, `frontend/src/lib/__tests__/elementliste_aktuell.test.ts`, `frontend/e2e/elementliste-abgleich.staging.spec.ts`, `frontend/playwright.elementliste.staging.config.ts`, `.claude/agents/mockup-bildpruefer.md`
- **Identifier:** ADR-0112; Wächter-Regeln (a) Aufbau und (b) Tokens; Generator `elementliste_aus_mockup`; Abgleich-Spec `elementliste-abgleich`; Agent `mockup-bildpruefer`
- **Schicht:** ausschließlich Frontend-Werkzeuge (`frontend/`, `scripts/`), Dokumentation und Agent-Definition. Kein Go-API-, kein Python-Core-Code.

## Nicht-Ziele (ausdrücklich)

- **Keine Produktfunktion ändert sich.** Kein sichtbares Verhalten, keine Daten, keine Kanäle, keine Texte der App werden verändert; es entstehen nur Regel, Wächter, Werkzeuge und Dokumentation.
- **Bausteine bauen** (inkl. Ampel-Tokens `--g-ampel-*` mit Dark-Block, Metrik-Zeile, Vorlage-Karte, Kanal-Tabelle usw.) ist ein eigener Folge-Workflow.
- **Die Scheiben (a)–(e)** (Wetter lesend, „Alarm ab“/„Grenzen ändern“, Warnungen/Radar/Anpassen, Zustellung komplett, „Test schicken“ + Etappen/Orte) sind je ein eigener Folge-Workflow mit eigener Spec, Elementlisten-Teilmenge und Prüf-Agent-Lauf.
- Das Alarmquellen-Gate (`alarm_ab`) gehört in Scheibe (b), nicht hierher.
- Der Bestand (heutige Seiten mit lokalem Styling) wird nicht nachträglich umgebaut; der Wächter startet als Ratsche und bricht den Bestand nicht.

## Scope

- **LoC:** ca. 900–1200 (ohne generiertes JSON, das mehrere tausend Zeilen umfassen kann)
- **Files:** ca. 12–14
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/__tests__/harte_farben_waechter.test.ts` | Muster | Ratsche `AUSNAHMEN`, `audit:exempt`; gleiches Muster, keine vierte Parallelstruktur |
| `.claude/hooks/pendant_gate.py` | Muster | Trip/Orte-Pendant (ADR-0097); bleibt unverändert |
| `frontend/src/app.css` | Quelle | Token-Namen `--g-*` |
| `frontend/src/lib/i18n/messages/{de,en}/*.json`, `hardcode_allowlist.json` | Quelle | EN-Texte der Elementliste aus dem Katalog (ADR-0104) |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Quelle | Soll für die Elementliste |
| `frontend/playwright.sprachwechsel.staging.config.ts` | Muster | Staging-Config mit setup-Projekt und storageState |
| `tests/test_adr_index_drift.py` | Gate | ADR-Index-Konsistenz |
| CI-Job `frontend-test` (`npm test`, `node --test`) | Gate | nimmt neue `__tests__/*.test.ts` automatisch auf |
| Playwright | Werkzeug | Rendern des Mockups per `file://` und Staging-Abgleich |

## Implementation Details

**1. ADR-0112** (`docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md`): Regel: (1) Jede Oberfläche entsteht ausschließlich aus Bausteinen in `atoms/molecules/organisms`; (2) fehlt ein Baustein, wird er zuerst im Design-System gebaut, nie in der Seite; (3) kein Styling außerhalb der Tokens; (4) ein Wächter blockiert Verstöße beim Merge. Enthält Prüfdatum 2027-02-08 und Löschbedingung (kein nachweisbarer Fang bis dahin). Index-Zeile in `docs/adr/README.md`; ADR-0111 erhält „Ergänzt durch: ADR-0112“; `docs/design-system/ANTI-PATTERNS.md` AP-006/007/008 erhalten den Vermerk „Pflicht mit Wächter, ADR-0112“. Neuer Wächter ersetzt das seit ADR-0111 außer Dienst gestellte Design-Gate (Regel-Budget).

**2. Wächter** (`bausteine_waechter.test.ts`, `node:test`, Svelte-AST über `svelte/compiler`, falls im node-Test nutzbar, sonst Regex mit expliziter Abdeckung der Umgehungswege):
- **(a) Aufbau**, Opt-in `SEITEN_SCOPE` (Seiten-/Reiter-Dateien; startet leer bzw. nur mit neuen Dateien späterer Scheiben): verboten sind `<style>`, `style=`-Attribut, Tailwind-Utility-Klassen, rohe `button/input/select/textarea/table`; Komponenten-Importe nur aus `$lib/components/{atoms,molecules,organisms}` (bzw. freigegebene Kompositionen). Ausnahme nur mit `audit:exempt` plus Begründung.
- **(b) Tokens** in `atoms/molecules/organisms`, Ratsche: Farbe, Abstand, Größe, Radius, Schrift, Schatten nur über `var(--g-*)`; erlaubt sind 0, 1px-Rahmen, %, fr, auto, calc/min/max über Tokens. `AUSNAHMEN` je Datei = Ist-Stand und darf nur sinken; neue Baustein-Dateien starten bei 0.
- **Neue-Datei-Regel:** Jede `.svelte` unter `routes/` oder `lib/components/**` außerhalb der Baustein-Ordner muss in `SEITEN_SCOPE` oder in der Bestandsliste stehen; die Bestandsliste darf nur sinken.

**3. Generator** (`scripts/elementliste_aus_mockup.ts`): Playwright rendert das Mockup per `file://`, steuert Kontext, Zustand, Reiter und Kanal-Segment per Klick (`data-ctx`, `data-zst`, `data-tab`, `data-seg`) und reine Script-Zustände (`openEdit`, `channelTab`, `pickerOpen`, `saveOpen`, `kebabConfirm`) per `page.evaluate("…; render()")`; `.tag`, `data-fb` und `.frame` werden ausgeschlossen. Ausgabe `elementliste.json` mit Mockup-Hash und Feldern `id` (stabil), `ctx`, `reiter`, `zustand`, `abschnitt`, `ordnung`, `rolle`, `text_de`, `muster`, `i18n_key`, `text_en`, `luecke`. EN: exakter Treffer im DE-Katalog liefert den EN-Wert desselben Schlüssels, sonst Musterabgleich, sonst `luecke: true`. Dynamische Texte (Zahlen, Namen, Werte) zählen als ein Element mit Muster. Entscheidung nach ADR-0104: EN-Lücken werden nicht akzeptiert, sondern sind Arbeitsposten der jeweiligen Scheibe (neuer Text nur über den Katalog).

**4. Hash-Check** (`elementliste_aktuell.test.ts`): ohne Browser, vergleicht Hash in der JSON mit dem Hash der Mockup-Datei.

**5. Staging-Abgleich** (`elementliste-abgleich.staging.spec.ts`, eigene Config `playwright.elementliste.staging.config.ts`, nicht im PR-CI): je Element Text sichtbar (normalisiert), richtiger Abschnitt, relative Reihenfolge im Abschnitt; keine Pixelpositionen. Nicht herstellbare Zustände (z. B. Ladefehler) über Route-Abfangen, sonst `nicht_pruefbar` mit Grund. Bericht als JSON und Markdown, Exit 0; `--scope <reiter/zustand>` filtert; `--strict` macht fehlende, abweichende oder `nicht_pruefbar`-Elemente rot. `assertNotProdBaseURL` schützt vor Produktion.

**6. Prüf-Agent** (`.claude/agents/mockup-bildpruefer.md`): Eingaben fest: Mockup-Bild, Staging-Bild (gleicher Viewport und Zustand), Elementlisten-Auszug; kein Quellcode-Zugriff; Aufruf am Scheibenende, höchstens zwei Runden; ergänzt die Elementliste um die Optik, ersetzt sie nicht. Hier nur Definition plus Probelauf.

**7. Doku:** `docs/reference/gates_und_ratschen.md` (Wächter, Regel-Budget-Tabelle mit Prüfdatum 2027-02-08), `docs/reference/design_system.md`, `docs/reference/workflow_und_agenten.md` (Ablauf Scheibe → Abgleich → Prüf-Agent).

**Querschnitts-Prüfpunkte:** Trip/Orte-Teilung: kein neuer Baustein mit Pendant, die Elementliste führt beide Kontexte (`ctx` Trip und Orte). Mandantentrennung: es werden keine Nutzerdaten bewegt; der Staging-Abgleich nutzt nur das Test-Konto und liest. Kanäle: die Elementliste führt alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) als Kanal-Segment; kein Briefing- oder Alarm-Inhalt wird geändert.

## Expected Behavior

- **Input:** Quelltexte des Frontends (Wächter), Mockup-Datei und i18n-Katalog (Generator), Staging-URL und Elementliste (Abgleich), Bilder (Prüf-Agent).
- **Output:** Wächter grün/rot im CI; `elementliste.json`; Abgleich-Bericht JSON + Markdown; Prüf-Agent-Befund je Runde.
- **Side effects:** Neue Merge-Sperre im CI (`frontend-test`); sonst keine. Keine Änderung an Produktfunktion, Nutzerdaten oder Produktion.

## Acceptance Criteria

- **AC-1:** Given eine Seiten-Datei in `SEITEN_SCOPE` enthält ein `<style>`-Element, ein `style=`-Attribut oder eine Tailwind-Utility-Klasse / When der Wächter `bausteine_waechter.test.ts` läuft / Then wird der Test rot und nennt Datei und Regel (a); ohne diese Konstrukte bleibt er für dieselbe Datei grün.
  - Test: `frontend/src/lib/__tests__/bausteine_waechter.test.ts` mit Fixture-Dateien (Verstoß rot, sauber grün), Aufruf der Prüffunktion auf echten Fixture-Texten.

- **AC-2:** Given eine Seiten-Datei in `SEITEN_SCOPE` verwendet ein rohes `<button>`, `<input>`, `<select>`, `<textarea>` oder `<table>` oder importiert eine Komponente außerhalb von `$lib/components/{atoms,molecules,organisms}` / When der Wächter läuft / Then wird er rot; dieselbe Datei mit Baustein-Komponenten statt rohen Elementen ist grün.
  - Test: `bausteine_waechter.test.ts`, Fixture-Paare je rohem Element und je Fremd-Import.

- **AC-3:** Given eine neue Baustein-Datei in `atoms/molecules/organisms` enthält einen px-Wert (ausgenommen 0 und 1px-Rahmen), eine Hex-Farbe oder einen Schriftwert ohne `var(--g-*)`-Token / When der Wächter läuft / Then wird er rot, weil neue Baustein-Dateien bei 0 Ausnahmen starten; Werte wie 0, 1px, %, fr, auto und calc/min/max über Tokens bleiben erlaubt.
  - Test: `bausteine_waechter.test.ts`, Fixtures für verbotene und erlaubte Werte.

- **AC-4:** Given die Ratsche `AUSNAHMEN` führt je Bestandsdatei den heutigen Ist-Stand / When ein Eintrag erhöht oder eine neue Ausnahme ergänzt wird / Then wird der Wächter rot; sinkt ein Eintrag (Datei wurde bereinigt), bleibt er grün und verlangt keine Anhebung.
  - Test: `bausteine_waechter.test.ts`, Ratschen-Prüfung gegen einen simulierten höheren und niedrigeren Ist-Stand.

- **AC-5:** Given eine neue `.svelte`-Datei liegt unter `routes/` oder `lib/components/**` außerhalb der Baustein-Ordner und steht weder in `SEITEN_SCOPE` noch in der Bestandsliste / When der Wächter läuft / Then wird er rot; trägt man sie in `SEITEN_SCOPE` ein, wird sie nach Regel (a) geprüft; die Bestandsliste darf nur sinken.
  - Test: `bausteine_waechter.test.ts`, Fixture-Verzeichnis mit eingetragener und nicht eingetragener Datei.

- **AC-6:** Given ein Verstoß ist mit `audit:exempt` und einer Begründung markiert / When der Wächter läuft / Then wird der Verstoß toleriert; fehlt die Begründung, wird der Wächter rot.
  - Test: `bausteine_waechter.test.ts`, Fixtures mit und ohne Begründung.

- **AC-7:** Given der heutige Bestand des Repos mit leerem bzw. nur neue Dateien enthaltendem `SEITEN_SCOPE` und `AUSNAHMEN` = Ist-Stand / When `node --test` auf `bausteine_waechter.test.ts` gegen den echten Quellbaum läuft / Then ist der Wächter grün, ohne dass bestehende Seiten verändert wurden.
  - Test: `bausteine_waechter.test.ts` gegen den echten Baum (Live-Lauf in CI-Job `frontend-test`).

- **AC-8:** Given ADR-0112 liegt unter `docs/adr/` / When `tests/test_adr_index_drift.py` läuft / Then ist der Test grün: der Index in `docs/adr/README.md` enthält die Zeile 0112, ADR-0111 trägt „Ergänzt durch: ADR-0112“, und ADR-0112 nennt die vier Regeln (nur Bausteine, fehlende zuerst ins System, nur Tokens, Wächter blockt beim Merge) sowie Prüfdatum 2027-02-08 und Löschbedingung.
  - Test: `uv run pytest tests/test_adr_index_drift.py` (benannte Datei); `# doc-compliance-test` nur für die Textmerkmale des ADR.

- **AC-9:** Given das Mockup `mockup-hub-fassung3.html` / When der Generator `scripts/elementliste_aus_mockup.ts` läuft / Then entsteht `docs/context/einstellungen_neu/elementliste.json` mit dem Hash der Mockup-Datei und Einträgen für alle Kombinationen Kontext (Trip, Orte) × Zustand (normal, lädt, Ladefehler, Konto mit Lücken) × Reiter (Wetter, Zustellung, Etappen bzw. Orte) × Kanal-Segment (E-Mail, Telegram, SMS, Premium-SMS, 3-Tages-Ausblick, bei Orte zusätzlich Stundenverlauf), ohne `.tag`, `data-fb` und `.frame`.
  - Test: Generator-Lauf im Test, danach Prüfung der Kombinationsmenge und der Ausschlüsse in der erzeugten JSON.

- **AC-10:** Given die erzeugte `elementliste.json` / When ein beliebiger Eintrag gelesen wird / Then enthält er die Felder `id` (stabil über zwei Generator-Läufe), `ctx`, `reiter`, `zustand`, `abschnitt`, `ordnung`, `rolle`, `text_de`, `muster`, `i18n_key`, `text_en` und `luecke`; dynamische Texte (Zahlen, Namen, Werte) erscheinen als ein Element mit `muster`, nicht als je Wert ein Eintrag.
  - Test: `elementliste_aktuell.test.ts` bzw. Generator-Test; zwei Läufe, Vergleich der IDs und Schemaprüfung.

- **AC-11:** Given ein Mockup-Text hat im DE-Katalog einen exakten Treffer, einen Musterabgleich oder keinen Treffer / When der Generator `text_en` ermittelt / Then kommt EN aus dem Katalog (Schlüssel in `i18n_key`) bzw. über das Muster; ohne Treffer wird `luecke: true` gesetzt und `text_en` nicht erfunden.
  - Test: Generator-Test mit je einem Eintrag je Fall (exakt, Muster, Lücke) gegen den echten Katalog.

- **AC-12:** Given `elementliste.json` wurde aus einem Mockup-Stand erzeugt / When die Mockup-Datei verändert wird, ohne die JSON neu zu erzeugen / Then wird `elementliste_aktuell.test.ts` rot (Hash-Abweichung); bei unverändertem Mockup ist er grün, und der Test braucht keinen Browser.
  - Test: `frontend/src/lib/__tests__/elementliste_aktuell.test.ts`, Prüfung gegen veränderte Kopie der Mockup-Datei und gegen den Originalstand.

- **AC-13:** Given die Staging-Spec `elementliste-abgleich.staging.spec.ts` und eine Elementliste / When der Abgleich gegen Staging läuft / Then entsteht ein Bericht als JSON und Markdown, in dem jedes Element den Status gefunden, abweichend oder `nicht_pruefbar` (mit Grund) trägt; nicht herstellbare Zustände werden zuerst per Route-Abfangen hergestellt und nie still übersprungen; der Prozess endet mit Exit 0.
  - Test: Lauf gegen Staging mit `playwright.elementliste.staging.config.ts`; Prüfung der Berichtsdateien auf Vollständigkeit (jedes Listenelement kommt im Bericht vor).

- **AC-14:** Given der Abgleich-Bericht enthält Abweichungen oder `nicht_pruefbar`-Elemente / When mit `--strict` aufgerufen wird / Then endet der Lauf mit Exit ungleich 0; ohne `--strict` endet er mit 0. Mit `--scope <reiter/zustand>` werden nur Elemente dieser Teilmenge geprüft und berichtet.
  - Test: Abgleich-Lauf mit und ohne `--strict` sowie mit Scope; Prüfung von Exit-Code und Berichtsumfang.

- **AC-15:** Given die Konfiguration des Staging-Abgleichs zeigt versehentlich auf die Produktions-URL / When der Abgleich startet / Then bricht `assertNotProdBaseURL` den Lauf ab, bevor eine Seite geladen wird; der Abgleich läuft nicht im PR-CI (keine Aufnahme in die sechs CI-Checks).
  - Test: Aufruf der Absicherung mit Prod-URL (muss werfen) und Staging-URL (läuft durch); CI-Workflow enthält keinen Aufruf der Config.

- **AC-16:** Given die Agent-Definition `.claude/agents/mockup-bildpruefer.md` / When sie gelesen wird / Then legt sie feste Eingaben fest (Mockup-Bild, Staging-Bild gleicher Viewport und Zustand, Elementlisten-Auszug), verbietet Quellcode-Zugriff (keine Lese-, Such- oder Shell-Werkzeuge außer Bildlesen), begrenzt auf höchstens zwei Runden je Scheibe und beschreibt, dass sie die Elementliste ergänzt und nicht ersetzt.
  - Test: Probelauf des Agenten mit einem Bildpaar eines vorhandenen Zustands; Prüfung, dass sein Befund nur auf den gelieferten Eingaben beruht (`# doc-compliance-test` nur für die Definitionsmerkmale).

- **AC-17:** Given die Doku `docs/reference/gates_und_ratschen.md`, `design_system.md` und `workflow_und_agenten.md` / When ein Leser den Wächter oder den Scheiben-Ablauf nachschlägt / Then beschreiben sie den Wächter mit Regeln (a), (b) und Neue-Datei-Regel, nennen in der Regel-Budget-Tabelle das Prüfdatum 2027-02-08 mit Löschbedingung und beschreiben den Ablauf Scheibe → Staging-Abgleich → Prüf-Agent (höchstens zwei Runden); `CLAUDE.md` bleibt innerhalb von 120 Zeilen / 12 KB.
  - Test: `uv run pytest tests/test_claude_md_budget.py` (benannte Datei) plus `# doc-compliance-test` für die Doku-Merkmale.

- **AC-18:** Given die Lieferung ist vollständig / When der Diff gegen `origin/main` geprüft wird / Then enthält er keine Änderung an Produktfunktion (keine Dateien unter `internal/`, `cmd/`, `api/`, `src/` und keine Änderung an Svelte-Seiten oder -Komponenten unter `frontend/src/routes/` bzw. `frontend/src/lib/components/`), und alle sechs CI-Checks sind grün.
  - Test: Diff-Prüfung der Dateipfade im PR; CI-Lauf `test`, `lint`, `go-test`, `svelte-check`, `frontend-test`, `e2e`.

## Test Plan

- `frontend/src/lib/__tests__/bausteine_waechter.test.ts` (AC-1 bis AC-7; `node --test`)
- `frontend/src/lib/__tests__/elementliste_aktuell.test.ts` (AC-9 bis AC-12; Hash-Check ohne Browser, Generator-Läufe)
- `frontend/e2e/elementliste-abgleich.staging.spec.ts` mit `frontend/playwright.elementliste.staging.config.ts` (AC-13 bis AC-15; nur Staging, nicht im PR-CI)
- `tests/test_adr_index_drift.py` (AC-8) und `tests/test_claude_md_budget.py` (AC-17), benannte Dateien
- Probelauf des Prüf-Agenten (AC-16)

**Testpolitik:** Frontend-Unit-Tests laufen über `node --test` (kein Vitest). Kein Mock-Theater: Der Wächter wird gegen echte Fixture-Dateien und den echten Quellbaum geprüft, der Generator gegen das echte Mockup und den echten Katalog, der Abgleich gegen echtes Staging. Dateiinhalt-Checks nur mit `# doc-compliance-test` für reine Dokumentationsmerkmale. Mutations-Gegenprobe (Pflicht): Wächter-Regeln werden per String-Ersetzung verfälscht (z. B. Regel (a) oder Ratsche ausgeschaltet) und müssen einen Test rot machen. `uv run pytest` nie ohne benannte Dateien.

## Definition of Done

- AC-1 bis AC-18 erfüllt und je durch den genannten Test belegt; Mutations-Gegenprobe des Wächters ohne unbewachte Verfälschung.
- ADR-0112 im Index, `tests/test_adr_index_drift.py` und `tests/test_claude_md_budget.py` grün.
- `elementliste.json` erzeugt, Hash-Check grün; Staging-Abgleich einmal ohne `--strict` gelaufen, Bericht liegt vor (Lücken sind Arbeitsposten der Folge-Workflows).
- Prüf-Agent-Definition liegt vor, ein Probelauf ist dokumentiert.
- Doku nachgezogen; Pull Request mit allen sechs CI-Checks grün gemergt; keine Produktfunktion verändert.

## Known Limitations

- Regex-basierte Wächter sind umgehbar (Direktiven, dynamische Klassen); Svelte-AST wird bevorzugt, Restlücken werden dokumentiert.
- Die Elementliste prüft Text, Abschnitt und Reihenfolge, keine Optik und keine Pixelpositionen; Optik deckt der Prüf-Agent ab.
- EN-Lücken bleiben sichtbar, bis die jeweilige Scheibe die Texte in den Katalog aufnimmt.
- Zustände, die sich auf Staging nicht herstellen lassen, erscheinen als `nicht_pruefbar` und verhindern den Abschluss im `--strict`-Lauf.
- Abschlusskriterium von #2913 (`--strict` ohne Scope grün, DE und EN) gilt erst nach den Folge-Workflows, nicht nach dieser Lieferung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0112 (neu); ergänzt ADR-0111
- **Rationale:** Es gab keine verbindliche Regel, dass Oberflächen nur aus Design-System-Bausteinen entstehen; der Atomic-Anteil in den Reitern war praktisch null. Die Regel ist eine Entscheidungsfläche (Design/Test-Strategie) und braucht ein ADR statt stiller Praxis. Prüfdatum 2027-02-08 (+90 Tage), Löschbedingung: kein nachweisbarer Fang bis dahin.

## Changelog

- 2026-11-10: Sektionen an CI-Spec-Gate angepasst (Scope, Definition of Done, Test Plan, AC-Listenformat)
- 2026-11-10: Initial spec created (Issue #2913, Workflow einstellungen-neu-neustart)

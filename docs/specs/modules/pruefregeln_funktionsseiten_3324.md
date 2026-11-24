---
entity_id: pruefregeln_funktionsseiten_3324
type: feature
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: feat-3324-pruefregeln-funktionsseiten
tags: [funktionsseiten, pruefregeln, drift-test, personendaten, epic-3318]
---

# Prüfregeln der Funktionsseiten nachschärfen

## Approval

- [ ] Approved

## Purpose

Die öffentlichen Funktionsseiten (`/funktionen`, Spec `oeffentliche_doku_3319`) sind heute sauber, aber drei Prüfregeln haben Lücken: die Erkennung von Handlungsempfehlungen übersieht gängige Formulierungen (DE/EN), die Bilder aus den Renderern laufen ohne Personendaten-Wächter, und der Befehlssatz für den Ortsvergleich ist nicht an die Befehls-Einzelquelle gebunden. Diese Spec schließt die drei Lücken, damit künftige Textänderungen oder neue Bilder nicht unbemerkt gegen ADR-0007 (nur Daten, keine Handlungsempfehlungen) oder die Personendaten-Regel verstoßen.

## Source

- **File:** `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts`, `scripts/landing_screenshots.py`, `tests/test_funktionen_befehle_drift.py`
- **Identifier:** `EMPFEHLUNG_DE` / `EMPFEHLUNG_EN` (Regex-Regeln), `funktionen_bilder` / Renderer-Aufnahme, Satz `funktionen.befehle.ortsvergleich`

> **Schicht-Hinweis:** Betroffen sind ausschließlich Test- und Skript-Schicht (Frontend-Katalogtest unter `frontend/src/lib/i18n/__tests__/`, Bild-Skripte unter `scripts/`, Python-Tests unter `tests/`). Es gibt keine Änderung an Go-API, Python-Core-Laufzeit, Katalogtexten oder Gate-Konfiguration.
>
> **Querschnitts-Prüfpunkte:** Trip/Ortsvergleich-Teilung: nicht betroffen (keine neue Komponente; der Drift-Test bindet nur den bestehenden Ortsvergleich-Satz an die Quelle für beide Kontexte). Mandantentrennung: nicht betroffen (keine Nutzerdaten, nur feste Fixtures und Katalog). Kanäle: nicht betroffen (kein Briefing- oder Alarm-Inhalt; der Befehlssatz selbst ist nur Prüfgegenstand).

## Estimated Scope

- **LoC:** ca. +200/−10
- **Files:** 5
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `oeffentliche_doku_3319` | Spec | Ursprung der Regeln (AC-7 keine Empfehlungen, AC-9 Wächter, AC-10 Befehlsliste) |
| `src/services/trip_command_processor.py` (`_COMMAND_SPECS`, `command_rows`) | module | Einzelquelle der Befehle je Kontext (`kinds`) für den Drift-Test |
| `scripts/funktionen_screenshots.py` (`pruefe_vor_aufnahme`, `FIKTIV_ERLAUBT`, `PersonendatenGefunden`) | module | Bestehender Personendaten-Wächter, wird im Renderer-Pfad wiederverwendet |
| `frontend/src/lib/i18n/messages/{de,en}/funktionen.json` | Katalog | Geprüfte Texte (nur lesend) |
| Playwright / Chromium | Werkzeug | Echter Browser für die Wächter-Gegenprobe |
| Pillow (`speichere_webp`) | Bibliothek | Bildausgabe im Renderer-Pfad |
| ADR-0007 | ADR | Nur Daten, keine Handlungsempfehlungen |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts` | MODIFY | `EMPFEHLUNG_DE`/`EMPFEHLUNG_EN` erweitern, Positiv-/Negativ-Korpus ergänzen |
| `scripts/landing_screenshots.py` | MODIFY | Renderer-Aufnahme als modulweiten Helfer herausziehen, vor dem Screenshot Wächter auf dem ganzen `body` |
| `tests/test_funktionen_screenshots_waechter.py` | MODIFY | Gegenprobe Renderer-Pfad mit echtem Chromium (alternativ neue Testdatei) |
| `tests/test_funktionen_befehle_drift.py` | CREATE | Satz DE/EN gegen `command_rows("vergleich")` und `command_rows("route")` |
| `docs/runbooks/funktionen_screenshots.md` | MODIFY | Wächter gilt auch für Renderer-Bilder; Archiv-Hinweis verweist auf #3327 |

### Estimated Changes

- Files: 5
- LoC: +200/−10

## Implementation Details

**Punkt 1, Ratschlag-Erkennung.** Die Regex-Regeln im Katalogtest werden erweitert, die Muster bleiben dort, wo sie heute sind. DE: Verbformen „empfiehlt“ und „empfehlenswert“ (heute trifft nur der Stamm „empfehl“), „am sichersten“, der Imperativ „Plane … um“ nur als Satzmuster mit nachfolgendem „um“ (nacktes „Plane“ ist mit dem Substantiv mehrdeutig) sowie weitere Imperative („beachte“, „denk“, „achte“) nur am Satzanfang. EN: „prudent“, „wise to“, „advisable“, „it is/it's best/wise/safer“, „you'd want to“, „be sure“, „keep in mind“, „consider“ nur am Satzanfang. Bewusst nicht aufgenommen: „check“ und „note that“, weil sie heute echte, zulässige EN-Katalogtexte treffen würden. Der Positiv-Korpus (muss erkannt werden) und der Negativ-Korpus (bleibt frei) stehen im Test; der echte Negativ-Korpus ist weiterhin der Lauf über alle `funktionen.*`-Texte beider Sprachen. Alle Beispielsätze sind fiktiv und enthalten keine Personendaten.

**Punkt 2, Wächter im Renderer-Bildpfad.** Die innere Aufnahmefunktion in `funktionen_bilder` wird zu einem modulweiten, testbaren Helfer. Vor `page.screenshot` wird `pruefe_vor_aufnahme` auf dem ganzen sichtbaren Seitentext (`body`) aufgerufen, auch bei Ausschnitt-Aufnahmen. Es wird nichts maskiert: Ein Befund bricht ab (`PersonendatenGefunden`), es entsteht keine Bilddatei, und die Fixture muss fiktiv korrigiert werden. Die Ausgabe nennt nur die Anzahl der Befunde, nicht die Werte. Vor dem Einbau werden alle Fixtures je Sprache einmal durch den Wächter geschickt; Treffer werden durch fiktive Fixture-Werte behoben, `FIKTIV_ERLAUBT` wird nicht erweitert. Zuerst ist zu prüfen, dass das Skript im Test importierbar ist (Top-Level-Imports).

**Punkt 4, Drift-Test Ortsvergleich-Satz.** Der Test liest beide Kataloge als Daten (JSON, Pfad relativ zur Testdatei) und holt über `command_rows("vergleich", lang=…)` und `command_rows("route", lang=…)` die Befehle aus der Einzelquelle. Beide Seiten werden normalisiert (Kleinschreibung, Umlaute wie ü zu ue). Der Satz wird in Wörter zerlegt. Geprüft wird: (a) jedes Befehlswort des Vergleichs kommt im Satz vor; (b) kein Wort aus der Menge „Route-Befehle minus Vergleich-Befehle“ kommt vor. Es gibt keine zweite handgepflegte Befehlsliste. Die Alternative, den Satz aus der Quelle zu erzeugen, ist verworfen, weil sie den Katalogvertrag ändern würde.

**Reihenfolge:** Punkt 4, dann Punkt 1, dann Punkt 2.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Katalogtest (`node --test`): Positiv-Korpus DE/EN wird von den erweiterten Regeln erkannt; vor der Regel-Erweiterung rot.
- [ ] Katalogtest: Negativ-Korpus und alle heutigen `funktionen.*`-Texte DE/EN bleiben frei von Treffern.
- [ ] Wächter-Test mit echtem Chromium: Renderer-HTML mit einer erfundenen, echt aussehenden Telefonnummer bricht ab, es entsteht keine Datei.
- [ ] Wächter-Test mit echtem Chromium: Renderer-HTML mit ausschließlich fiktiven Werten erzeugt eine WebP-Datei.
- [ ] Drift-Test: Satz DE und EN enthält alle Vergleich-Befehle und kein Nur-Route-Wort.
- [ ] Gegenproben je Regel (siehe AC-2, AC-4, AC-6, AC-7): Verfälschung macht den jeweiligen Test rot.

## Expected Behavior

- **Input:** Katalogtexte `funktionen.*` (DE/EN), HTML der Renderer-Fixtures, Befehls-Einzelquelle `_COMMAND_SPECS` über `command_rows()`.
- **Output:** Grüne Prüfungen bei sauberem Stand; rote Prüfung bzw. Abbruch des Bild-Skripts (ohne Bilddatei) bei Handlungsempfehlung, echt aussehender Mail-Adresse/Telefonnummer oder Abweichung zwischen Ortsvergleich-Satz und Befehlsquelle.
- **Side effects:** keine für Nutzer; öffentliche Seiten und Bilder bleiben unverändert.

## Definition of Done

- [ ] Positiv-Korpus DE/EN erkannt, Negativ-Korpus und alle `funktionen.*`-Texte ohne Treffer, Gegenprobe rot (AC-1, AC-2)
- [ ] Renderer-Bildpfad prüft vor jeder Aufnahme den ganzen sichtbaren Text; echt aussehende Nummer bricht ohne Datei ab, fiktive Fixtures erzeugen WebP, Gegenprobe „Wächteraufruf entfernt“ rot (AC-3, AC-4, AC-5)
- [ ] Drift-Test Ortsvergleich-Satz DE/EN gegen `command_rows()` grün, beide Gegenproben rot (AC-6, AC-7)
- [ ] Runbook nachgezogen (Wächter auch für Renderer-Bilder, Archiv-Hinweis auf #3327)
- [ ] Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, Kern-Schicht 100 % grün, ausgeliefert, Selftest grün

## Acceptance Criteria

- **AC-1:** Given der Katalogtest kennt einen Korpus empfehlender Sätze in Deutsch und Englisch („Es empfiehlt sich, früh zu starten.“, „Plane die Etappe um.“, „A prudent hiker turns back.“, „It is wise to start early.“, „It is advisable to carry water.“, „Consider a rain jacket.“, „You'd want to leave early.“) / When die Ratschlag-Erkennung auf diese Sätze angewendet wird / Then wird jeder dieser Sätze als Handlungsempfehlung erkannt.
  - Test: Der Positiv-Korpus läuft durch die Erkennung; jeder Satz muss einen Treffer liefern, vor der Erweiterung der Regeln sind „empfiehlt sich“, „Plane … um“ und „prudent hiker“ rot.

- **AC-2:** Given der Katalogtest kennt reine Funktionsbeschreibungen („Plane dienen als Schutz.“, „Plan: Free, Standard, Premium“, „Check the waypoints.“ mitten im Satz) sowie alle heutigen `funktionen.*`-Texte in DE und EN / When die erweiterte Erkennung darauf läuft / Then gibt es keinen Treffer, und die Seiten bleiben ohne Fehlalarm veröffentlichbar.
  - Test: Negativ-Korpus und der Lauf über alle `funktionen.*`-Katalogtexte beider Sprachen bleiben grün; Gegenprobe: Wird in einen Katalogtext testweise „Es empfiehlt sich, früh zu starten.“ eingefügt, wird der Test rot.

- **AC-3:** Given die Renderer-Bilder der Funktionsseiten entstehen aus festen Testdaten (Fixtures) / When das Bild-Skript ein Renderer-Bild aufnehmen soll / Then prüft es zuvor den gesamten sichtbaren Seitentext (auch bei Ausschnitt-Aufnahmen) auf Mail-Adressen und Telefonnummern außerhalb der Fiktiv-Liste, ohne etwas zu maskieren.
  - Test: Test mit echtem Chromium übergibt dem Renderer-Aufnahmeweg HTML und beobachtet, dass der Wächter auf dem ganzen sichtbaren Text läuft, auch wenn nur ein Ausschnitt fotografiert wird; kein Mock des Wächters.

- **AC-4:** Given ein Renderer-Fixture enthält eine erfundene, aber echt aussehende Telefonnummer (z. B. „+49 171 2345678“) / When die Aufnahme gestartet wird / Then bricht das Skript mit `PersonendatenGefunden` ab und es entsteht keine Bilddatei; die Meldung nennt nur die Anzahl der Befunde, nicht die Werte.
  - Test: Echter Chromium, Zielpfad vorher nicht vorhanden; nach dem Abbruch existiert die Datei nicht, die Fehlermeldung enthält die Nummer nicht. Gegenprobe: Wird der Wächteraufruf im Renderer-Pfad entfernt, wird der Test rot.

- **AC-5:** Given ein Renderer-Fixture enthält nur Fiktivwerte der Erlaubt-Liste / When die Aufnahme läuft / Then entsteht die WebP-Datei wie bisher, und alle heutigen Renderer-Fixtures in Deutsch und Englisch passieren den Wächter, ohne dass `FIKTIV_ERLAUBT` erweitert wurde.
  - Test: Echter Chromium erzeugt aus fiktivem HTML eine nicht leere WebP-Datei; ein Lauf über alle Renderer-Fixtures beider Sprachen wirft keine Ausnahme.

- **AC-6:** Given der Ortsvergleich-Satz `funktionen.befehle.ortsvergleich` nennt die Befehle in Deutsch und Englisch / When der Drift-Test ihn gegen `command_rows("vergleich", lang=…)` hält / Then kommt jedes Befehlswort des Ortsvergleichs im Satz vor (DE: HEUTE, MORGEN, PAUSE, WEITER, HILFE, KUERZEL, REPORT; EN: TODAY, TOMORROW, PAUSE, RESUME, HELP, CODES, REPORT), unabhängig von Groß-/Kleinschreibung und Umlauten.
  - Test: Der Test liest Katalog und Quelle als Daten; Gegenprobe: Wird ein Befehlswort aus dem Satz entfernt, wird der Test rot.

- **AC-7:** Given es gibt Befehle, die nur für Trips gelten (Differenz aus `command_rows("route")` und `command_rows("vergleich")`) / When ein solches Wort im Ortsvergleich-Satz steht oder ein Befehl in der Quelle den Kontext wechselt / Then schlägt der Drift-Test fehl, bis Satz und Quelle wieder übereinstimmen.
  - Test: Gegenprobe: Ein Nur-Trip-Befehl wird an den Satz angehängt bzw. die Zuordnung eines Befehls in der Quelle wird testweise verändert; beides macht den Test rot. Es existiert keine zweite handgepflegte Befehlsliste im Test.

## Out of Scope

- **Punkt 3 aus Issue #3324 (Archiv-Bild, leer wegen fehlendem archivierten Trip im Prüfkonto-Seed)** ist abgespalten nach #3327 im Epic #3318 (Staging-Daten, Seed-Erweiterung, Bildaufnahme, Alt-Text).
- Keine Änderung an Gate-Konfiguration, Katalogtexten, Befehlsquelle oder Bildinhalten.

## Known Limitations

- Die Ratschlag-Erkennung bleibt eine Regel-Heuristik; neue Formulierungen müssen bei Bedarf in den Korpus und die Regel nachgetragen werden. „check“ und „note that“ sind bewusst nicht erfasst, weil sie zulässige Texte treffen würden.
- Der Wächter erkennt nur Mail-Adressen und Telefonnummern im sichtbaren Text, nicht Personendaten in Bildpixeln; die Sichtprüfung neuer Bilder bleibt Pflicht (Runbook).
- Das Archiv-Bild bleibt bis #3327 leer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Nachschärfen bestehender Prüfregeln innerhalb bereits getroffener Entscheidungen (ADR-0007, Spec 3319); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-24: Initial spec created (Punkte 1, 2, 4 aus Issue #3324; Punkt 3 nach #3327 abgespalten)

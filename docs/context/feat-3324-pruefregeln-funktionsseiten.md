# Context: feat-3324-pruefregeln-funktionsseiten

## Request Summary
Issue #3324 (Teil von Epic #3318, Nebenbefunde der Prüfung zu #3319): die Prüfregeln der
öffentlichen Funktionsseiten `/funktionen` nachschärfen. Vier Punkte:
1. Ratschlag-Erkennung (F-ADV3) robuster: „Es empfiehlt sich …“, Imperativ „Plane … um“,
   EN „prudent hiker“ werden heute nicht erkannt.
2. Renderer-Bilder (F-ADV4) laufen ohne Personendaten-Wächter.
3. Archiv-Bild leer (F005): Seed legt keinen archivierten Trip an.
4. Nachtrag (Kommentar): Satz `funktionen.befehle.ortsvergleich` ist nicht per Drift-Test an
   `_COMMAND_SPECS` (kinds) gebunden.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts` (Z. 430–513) | AC-7: `EMPFEHLUNG_DE`/`EMPFEHLUNG_EN`-Regex (Modalwörter, Satzanfang-Imperative, feste Wendungen), Positiv-/Negativ-Korpus (F004-Gegenproben), Prüfung aller `funktionen.*`-Texte. Punkt 1. |
| `frontend/src/lib/i18n/messages/{de,en}/funktionen.json` | Die geprüften Texte; Z. 123 `funktionen.befehle.ortsvergleich` (Punkt 4). |
| `frontend/src/lib/components/organisms/funktionen/inhalt.ts:112` | Unterseite `befehle` zeigt Absätze `text`, `kanaele`, `ortsvergleich`. |
| `scripts/landing_screenshots.py` (`funktionen_bilder`, ~Z. 386–415) | Renderer-Bildpfad: `aufnehmen()` → `page.set_content(html)` → `page.screenshot` → `speichere_webp` OHNE Wächter. Punkt 2. |
| `scripts/funktionen_screenshots.py` (Z. 60–230) | Wächter: `FIKTIV_ERLAUBT`, `_MAIL_MUSTER`/`_TELEFON_MUSTER`, `personendaten_befunde`, `pruefe_vor_aufnahme` (wirft `PersonendatenGefunden`), `_MASKIEREN_JS`, `maskieren_und_pruefen(page)`; `aufnehmen()` als einziger Aufnahmeweg der Oberflächen-Bilder (prüfen, dann Screenshot). Wiederverwenden für Punkt 2. |
| `tests/test_funktionen_screenshots_waechter.py` | Bestehender Wächter-Test (reine Funktion + echter Browser mit lokalem Inhalt). Vorlage für die Gegenprobe des Renderer-Pfads. |
| `src/services/trip_command_processor.py` (Z. 290–380) | `_COMMAND_SPECS` (Einzelquelle; `kinds` = `_BEIDE_KINDS`/`_ROUTE_ONLY`), `command_rows(kind, lang)`. Vergleich-taugliche Befehle heute: heute, morgen, pause, weiter, hilfe, kuerzel, report (EN: today, tomorrow, pause, resume, help, codes, report). Punkt 4. |
| `tests/test_hilfe_befehle_drift.py` | Vorhandener Python-Drift-Test Hilfe-Katalog ↔ `command_rows()`; Muster für eine Bindung `funktionen.befehle.ortsvergleich` ↔ `command_rows("vergleich")`. |
| `scripts/staging_pruefkonto_mockupdaten.py` | Prüfkonto-Seed (kein archivierter Trip). Punkt 3. |
| `docs/runbooks/funktionen_screenshots.md` (Z. 17–21, 64, 76–87) | Bildliste, „Bekannte Schwäche Archiv-Bild“, Nachholweg `--nur archiv`, Alt-Text `funktionen.bild.archiv.alt`. |
| `docs/specs/modules/oeffentliche_doku_3319.md` | Spec der Funktionsseiten (AC-7 keine Empfehlungen, AC-9 Wächter, AC-10 Befehlsliste). |

## Existing Patterns
- Regel + Gegenprobe: jede Prüfregel hat Positiv-Korpus (muss erkennen) und Negativ-Korpus (reine Funktionsbeschreibung bleibt frei); so in AC-7 (F004) bereits angelegt — erweitern statt neu bauen.
- Wächter vor Aufnahme: Text prüfen, erst dann Screenshot; bei Befund Abbruch, Datei entsteht nicht (Befunde nicht ausgeben, nur Anzahl).
- Drift-Tests gegen Einzelquelle `_COMMAND_SPECS` über `command_rows()` statt Kopien (#2134, AC-10 #3319).
- Frontend-Tests laufen über `node --test` (kein Vitest).

## Dependencies
- Upstream: `_COMMAND_SPECS`/`command_rows`, Katalog-JSON, Playwright (Bildskripte), Pillow (`speichere_webp`), Prüfkonto-Seed.
- Downstream: öffentliche Seiten `/funktionen/*`, statische Bilder `frontend/static/funktionen/**.webp`, `bildmasse.json`.

## Existing Specs
- `docs/specs/modules/oeffentliche_doku_3319.md`
- ADR-0007 (nur Daten, keine Handlungsempfehlungen)

## Risks & Considerations
- Punkt 1: Regex-Erweiterung darf heutige korrekte Texte nicht fälschlich treffen (z. B. „empfiehlt“ als Funktionsbeschreibung, „Plane“ als Substantiv vs. Imperativ „Plane … um“). Negativ-Korpus aus echten Katalogtexten mitführen; „prudent“/„wise to“/„it is advisable“ u. ä. aufnehmen.
- Punkt 2: Renderer-Inhalte sind Fixtures; die Briefing-Mail enthält evtl. fiktive Absender/Empfängerzeilen → `FIKTIV_ERLAUBT` ggf. ergänzen; Gegenprobe: Fixture mit echt aussehender Nummer bricht ab und schreibt keine Datei.
- Punkt 3: Seed-Erweiterung ändert Staging-Prüfkonto (Read-Modify-Write, Mockup-Daten des Prüfkontos, nie PO-Trips); Bildaufnahme gegen Staging + Sichtprüfung + Alt-Text DE/EN. Größter Teil; ggf. eigenständig schneiden.
- Punkt 4: Satz ist Freitext mit lokalisierten Wörtern (DE: „Heute, Morgen, Report, Pause, Weiter, Hilfe und Kürzel“); Bindung entweder Test prüft, dass jedes Vergleichs-Befehlswort (DE/EN) im Satz vorkommt und kein Nur-Route-Wort, oder der Satz wird aus der Quelle erzeugt.
- Keine Bildänderung ohne Personendaten-Prüfung; öffentliches Repo: nur fiktive Daten.

## Analysis

### Type
Feature (Nachschärfen von Prüfregeln; kein Nutzerfehler, heutige Texte/Bilder sauber)

### Schnitt
- **In #3324:** Punkt 1 (Ratschlag-Erkennung), Punkt 2 (Wächter im Renderer-Bildpfad), Punkt 4 (Drift-Bindung Satz `funktionen.befehle.ortsvergleich`).
- **Abgespalten:** Punkt 3 (Archiv-Bild, Seed mit archiviertem Trip) → #3327 im Epic #3318 (Staging-Daten, Seed-Fake mit PATCH-Pfad, Verträglichkeit #2913, manuelle Bildaufnahme + Alt-Text). Wichtig dort: Body `{"archived": true}`, nicht `{"state":"archived"}`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts` | MODIFY | EMPFEHLUNG_DE/EN erweitern, Positiv-/Negativ-Korpus ergänzen |
| `scripts/landing_screenshots.py` | MODIFY | innere `aufnehmen` als modulweiten Helfer (z. B. `renderer_aufnahme`) herausziehen; vor `page.screenshot` `pruefe_vor_aufnahme(page.inner_text("body"), FIKTIV_ERLAUBT)` |
| `tests/test_funktionen_screenshots_waechter.py` (oder neue Datei) | MODIFY/CREATE | Gegenprobe Renderer-Pfad mit echtem Chromium: HTML mit `+49 171 2345678` → `PersonendatenGefunden`, keine Datei; fiktives HTML → WebP entsteht |
| `tests/test_funktionen_befehle_drift.py` | CREATE | Satz DE/EN ↔ `command_rows("vergleich", lang=…)` |
| `docs/runbooks/funktionen_screenshots.md` | MODIFY | Wächter gilt auch für Renderer-Bilder; Archiv-Hinweis → #3327 |

### Scope Assessment
- Files: 4–5
- Estimated LoC: ca. +200/−10 (Regex-Test +35, Skript +20, Wächter-Test +50, Drift-Test +70, Doku)
- Risk Level: LOW (nur Tests und ein Bild-Skript, keine Laufzeit des Dienstes)

### Technical Approach
**Punkt 1 – Ratschlag-Regex.** `\bempfehl` trifft „empfiehlt“ nicht → `\bempf(?:ehl|iehl)`, dazu `empfehlenswert`, `am sichersten`. Imperativ „Plane … um“ als `plane\b[^.!?]*\bum\b` (nicht nackt „Plane“, mehrdeutig mit Substantiv). Weitere Imperative (`beachte`, `denk`, `achte`) nur satzanfangs-verankert. EN: `\bprudent\b`, `\bwise to\b`, `\badvisable\b`, `\bit(?:'s| is) (?:best|wise|safer)\b`, `\byou(?:'d| would) want to\b`, `\bbe sure\b`, `\bkeep in mind\b`, `consider` nur am Satzanfang. NICHT aufnehmen: `check`, `note that` (treffen heute echte EN-Katalogtexte: `funktionen.trip_anlegen.text`, `funktionen.kanaele.text2`, `funktionen.bild.archiv.alt`). Gemessen: satzanfangs-verankerte neue Muster treffen keinen heutigen `funktionen.*`-Text. Positiv-Korpus: „Es empfiehlt sich, früh zu starten.“, „Plane die Etappe um.“, „A prudent hiker turns back.“, „It is wise to start early.“, „It is advisable to carry water.“, „Consider a rain jacket.“, „You'd want to leave early.“; Negativ: „Check the waypoints.“ mitten im Satz, „Plan: Free, Standard, Premium“, „Plane dienen als Schutz.“. Echter Negativ-Korpus = bestehender Lauf über alle `funktionen.*`-Texte.

**Punkt 2 – Wächter Renderer-Bilder.** Kein Maskieren (Fixtures sind feste Testdaten; ein Befund muss die Fixture korrigieren, nicht still überdecken). Prüfung auf dem ganzen `body`, auch bei Ausschnitt-Aufnahmen (`_AUSSCHNITT`). Vor dem Einbau einmal alle Fixtures je Sprache durch `pruefe_vor_aufnahme` schicken; Treffer → Fixture fiktiv machen, nicht `FIKTIV_ERLAUBT` erweitern. Stolperstein: Importierbarkeit von `scripts/landing_screenshots.py` im Test (Top-Level-Imports) zuerst prüfen. Mutationsprobe: Wächteraufruf entfernen → Test rot.

**Punkt 4 – Drift-Test.** `command_rows(kind, lang=…)` (lang keyword-only) liefert Befehl in Großbuchstaben/ASCII (DE `HEUTE, MORGEN, PAUSE, WEITER, HILFE, KUERZEL, REPORT`; EN `TODAY, TOMORROW, PAUSE, RESUME, HELP, CODES, REPORT`). Test: erstes Token je Zeile, casefold + Umlaut-Normalisierung (ü→ue usw.) auf beiden Seiten; Satz tokenisieren; (a) jedes Vergleichs-Befehlswort kommt vor, (b) kein Wort aus `command_rows("route") − command_rows("vergleich")` kommt vor (Quelle, keine zweite Liste). Katalog als Daten lesen (json.load, Pfad relativ zur Testdatei). Gegenprobe: Wort entfernen bzw. Nur-Route-Wort anhängen → rot. Alternative „Satz aus Quelle erzeugen“ verworfen (ändert Katalogvertrag).

### Reihenfolge
Punkt 4 → Punkt 1 → Punkt 2.

### Dependencies
`_COMMAND_SPECS`/`command_rows`, Katalog-JSON DE/EN, Playwright/Chromium (Wächter-Test), Pillow (`speichere_webp`), `funktionen_screenshots.pruefe_vor_aufnahme`/`FIKTIV_ERLAUBT`.

### Open Questions
- keine (Schnitt Punkt 3 technisch entschieden, #3327)

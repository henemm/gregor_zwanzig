---
entity_id: fix_3015_temp_spanne_en
type: bugfix
created: 2026-11-15
updated: 2026-11-15
status: draft
workflow: fix-3015-temp-spanne-en
version: "2.0"
tags: [i18n, email, adr-0104, epic-2644]
---

# Temperaturspanne bei Minusgraden sprachneutral (#3015)

## Approval

- [ ] Approved

## Purpose

Bei Minusgraden steht in englischen Briefing-Mails "-3 bis 0°C", weil das Bindewort "bis" fest deutsch im Code steht (#2210 C2-79). Per PO-Entscheidung vom 2026-11-15 wird die Spanne mit mindestens einem negativen angezeigten Wert künftig in beiden Sprachen ohne Bindewort geschrieben: Gedankenstrich mit je einem Leerzeichen davor und danach ("-3 – 0°C", "-12 – -4°C"). Zusätzlich nutzt die Lufttemperatur der Kurzzusammenfassung dieselbe geteilte Formel statt einer eigenen.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `format_temp_span`
- **Zweiter Aufrufer:** `src/output/renderers/compact_summary.py` (`_format_temperature`; `_format_felt_temperature` nutzt `format_temp_span` bereits)

Schicht: Python-Core (Renderer). Kein Frontend, keine Go-API. Trip-Briefing und Ortsvergleich teilen den Helper bereits (kein Pendant nötig). Kanäle: nur E-Mail betroffen; SMS, Telegram und Premium-SMS bleiben unverändert (geprüft: das feste "bis" steht nur an dieser einen Stelle). Keine Nutzerdaten bewegt (keine Zwei-Nutzer-Prüfung nötig).

## Estimated Scope

- **LoC:** ca. +10/-12 Source, ca. +70 Tests (inkl. Umstellung), +1 Zeile Vermerk in der Alt-Spec
- **Files:** 6
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/fix_2210_mail_renderfehler.md` | spec | C2-79 ("bis"-Regel, dort AC-3, AC-4, AC-6) wird abgelöst; Ablösungsvermerk wird ergänzt |
| `tests/tdd/test_temperaturspanne_negative_werte.py` | test | bestehende #2210-Tests werden auf die neue Schreibweise umgestellt |
| `tests/tdd/_hiking_window_fixtures.py` | test-helper | Regex `_DASH = "(?:–\| bis )"` (Zeile 369) kennt " bis " und muss die neue Form " – " akzeptieren |

Entfallen gegenüber Version 1.0: Katalog-Key `mail.pille.temp_spanne_negativ`, Änderungen an `mail.json`, Durchreichen von `lang` (die Ausgabe ist sprachunabhängig).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/email/helpers.py | MODIFY | `format_temp_span`: Minus-Zweig liefert `f"{lo} – {hi}°C"` (U+2013, je ein Leerzeichen) statt `f"{lo} bis {hi}°C"`; Kommentar Zeile ~1563 anpassen. "-0" zählt weiter nicht als negativ, Plus-Spannen bleiben `lo–hi°C` |
| src/output/renderers/compact_summary.py | MODIFY | `_format_temperature` baut die Spanne nicht mehr selbst, sondern `format_temp_span(int(round(lo)), int(round(hi)), decimals=0)` |
| tests/tdd/test_temperaturspanne_negative_werte.py | MODIFY | Erwartungen von " bis " auf " – " umstellen; Zusicherung "kein '-12–-4'" bleibt, ebenso "-0" nicht negativ |
| tests/tdd/_hiking_window_fixtures.py | MODIFY | `_DASH` fest auf `"(?:–\| – )"` umstellen (Gedankenstrich ohne oder mit je einem Leerzeichen; „ bis “ entfällt), Kommentar Zeile 368 anpassen |
| tests/tdd/test_temperaturspanne_en_3015.py | CREATE | neue Tests mit echten Renderer-Aufrufen für AC-1 bis AC-6 |
| docs/specs/modules/fix_2210_mail_renderfehler.md | MODIFY | Ablösungsvermerk: "C2-79-Schreibweise 'bis' abgelöst durch #3015: '-12 – -4°C', PO-Entscheidung 2026-11-15" (bei C2-79 sowie AC-3, AC-4, AC-6) |

Per Grep geprüft, nicht betroffen: `tests/golden/text_report/*`, `tests/unit/test_renderers_text_report.py`, `tests/unit/test_trip_result_adapter.py` (Textbericht "-15.0 bis -5.0°C" ist ein anderer Renderer, bleibt), `src/output/renderers/alert/render.py` (Alarm-Vorlage, kein Temperaturbereich).

## Implementation Details

Eine einzige geteilte Formel in `format_temp_span`: gleiche gerundete Werte ergeben den Einzelwert, ein negativer angezeigter Wert (nicht "-0") ergibt `"{lo} – {hi}°C"`, sonst `"{lo}–{hi}°C"`. Weil nichts mehr von der Sprache abhängt, ist kein Katalog und keine `lang`-Durchreichung nötig (Protokoll-/Zahlenformat, kein Nutzertext im Sinne von ADR-0104). Die Leerzeichen vermeiden die Folge "–-" direkt aneinander. Für die Lufttemperatur der Kurzzusammenfassung wird mit gerundeten Ganzzahlen aufgerufen (kein "-0"); gleicher gerundeter Min/Max ergibt Einzelwert statt "5–5°C". Damit teilen Kachel, Lufttemperatur und gefühlte Temperatur dieselbe Schreibweise (#1410: kein Nachbau).

## Test Plan

### Automated Tests (TDD RED)

Alle Tests rufen die echten Renderer auf, keine Mocks.

- [ ] Test 1: GIVEN englisches Konto, Etappe -3/0°C / WHEN Trip-Briefing-Mail gerendert / THEN Kachelzeile "-3 – 0°C", weder "bis" noch "to"
- [ ] Test 2: GIVEN dieselbe Lage im Ortsvergleich (englisch) / WHEN Mail gerendert / THEN Kachel "-3 – 0°C"
- [ ] Test 3: GIVEN deutsches Konto, dieselbe Lage / WHEN Mail gerendert / THEN "-3 – 0°C", kein "bis"
- [ ] Test 4: GIVEN Lufttemperatur -12/-4 und gefühlt -15/-8 / WHEN Kurzzusammenfassung de und en / THEN "-12 – -4°C" bzw. "-15 – -8°C", Folge "–-" kommt nicht vor
- [ ] Test 5: GIVEN Plus-Spannen 8/14 / WHEN kachel und Kurzzusammenfassung / THEN zeichengleich "8–14°C"
- [ ] Test 6: GIVEN Min/Max nach Rundung gleich (z. B. 4,6/5,2 und -0,2/0,2) / WHEN Kachel und Lufttemperatur / THEN Einzelwert, kein "5–5°C"
- [ ] Umgestellt: `test_temperaturspanne_negative_werte.py` erwartet " – " statt " bis "
- [ ] Renderer-Gate: Modus-Matrix-Test und Mail-Validator (Trip-Briefing) frisch grün

## Acceptance Criteria

- **AC-1:** Given ein Konto mit Sprache Englisch und eine Etappe mit Tiefstwert -3 und Höchstwert 0 Grad / When das Trip-Briefing als Mail gerendert wird / Then zeigt die Kachelzeile "-3 – 0°C" und weder das Wort "bis" noch "to"
  - Test: englische Briefing-Mail rendern und Kachelzeile prüfen

- **AC-2:** Given ein Konto mit Sprache Englisch und ein Ortsvergleich mit -3 und 0 Grad / When die Vergleichs-Mail gerendert wird / Then zeigt dieselbe Kachel "-3 – 0°C" ohne deutsches Bindewort
  - Test: englische Ortsvergleich-Mail rendern und Kachel prüfen

- **AC-3:** Given ein Konto mit Sprache Deutsch und dieselbe Minus-Lage / When die Mail gerendert wird / Then zeigt sie ebenfalls "-3 – 0°C" und nirgends mehr "bis" in der Temperaturspanne
  - Test: deutsche Mail rendern, Kachelzeile prüfen, umgestellte #2210-Tests grün

- **AC-4:** Given eine Lufttemperatur von -12 bis -4 Grad und eine gefühlte Temperatur von -15 bis -8 Grad / When die Kurzzusammenfassung in Deutsch und Englisch erzeugt wird / Then steht dort "-12 – -4°C" und "-15 – -8°C", und die Zeichenfolge "–-" direkt aneinander kommt nie vor
  - Test: beide Sprachen rendern (HTML und Plain), Zeichenfolge prüfen

- **AC-5:** Given eine Plusgrad-Spanne von 8 bis 14 Grad / When Kachel und Kurzzusammenfassung gerendert werden / Then bleibt die Schreibweise zeichengleich "8–14°C" ohne Leerzeichen
  - Test: Kachel und Kurzzusammenfassung rendern und Zeichen vergleichen

- **AC-6:** Given eine Spanne, deren Werte nach dem Runden gleich sind / When Kachel und Lufttemperatur der Kurzzusammenfassung erzeugt werden / Then erscheint nur der Einzelwert (z. B. "5°C") statt "5–5°C"
  - Test: Mail mit Min und Max, die gerundet übereinstimmen, rendern und Einzelwert prüfen

## Definition of Done

- AC-1 bis AC-6 sind durch Kern-Tests (offline, ohne Mocks) abgedeckt, vorher rot, nachher grün.
- Die auf " – " umgestellten #2210-Tests (`test_temperaturspanne_negative_werte.py`) und die Tests, die `_hiking_window_fixtures._DASH` nutzen, sind grün; der Ablösungsvermerk in `fix_2210_mail_renderfehler.md` ist gesetzt.
- Modus-Matrix-Test und Trip-Briefing-Mail-Validator (Staging-Mail) frisch grün.
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.

## Known Limitations

- Bei gleichem gerundetem Min/Max zeigt die Lufttemperatur der Kurzzusammenfassung den Einzelwert statt "5–5°C" (gewollt, konsistent zur Kachelzeile).
- Der Textbericht-Renderer ("-15.0 bis -5.0°C (Gipfel)") ist ein eigener Pfad und bleibt unverändert; er ist nicht Teil dieses Tickets.
- Die Schreibweise ist bewusst sprachneutral; für weitere Sprachen ist nichts zu tun.
- Befund Phase 5 (TDD RED): Die Ortsvergleich-Mail baut keine Kachelzeile über `format_temp_span`; Tiefst- und Höchstwert stehen dort als eigene Zeilen, der Ausblick als "-3/0°C". Ein deutsches Bindewort kann dort nicht entstehen. AC-2 ist deshalb als Regressionsschutz abgesichert (englische Vergleichs-Mail mit -3/0 Grad ohne "bis" und ohne "–-"), nicht als neue Kachel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; ersetzt eine frühere Spec-Entscheidung
- **Rationale:** PO-Entscheidung 2026-11-15 (per Auswahldialog, Alternativen vorgelegt): sprachneutraler Gedankenstrich mit Leerzeichen statt Bindewort, damit weder ein deutsches Wort in englischen Mails steht noch ein Katalog-Eintrag je Sprache nötig ist.
- **Ablösung:** löst die "bis"-Regel aus `fix_2210_mail_renderfehler.md` (C2-79, dort AC-3, AC-4, AC-6) ab. Dort wird ein Ablösungsvermerk ergänzt.

## Changelog

- 2026-11-15: Initial spec created (Issue #3015, Epic #2644)
- 2026-11-15: Überarbeitet nach PO-Entscheidung: sprachneutrale Schreibweise "-12 – -4°C" statt Katalog-Bindewort; Katalog-Key, mail.json-Änderungen und `lang`-Durchreichung entfallen; Kurzzusammenfassung nutzt `format_temp_span`; ACs neu; löst #2210 C2-79 ab
- 2026-11-15: Phase 5: Befund zum Ortsvergleich (keine geteilte Kachel) unter Known Limitations vermerkt; AC-2 als Regressionsschutz

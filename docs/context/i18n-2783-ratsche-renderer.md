# Context: i18n-2783-ratsche-renderer

Issue #2783 (Epic #2644, ADR-0104). Kombinierter Kontext + Analyse (Intake-Summe 2).

## Request Summary
Die Python-i18n-Ratsche (`tests/test_i18n_keine_hartkodierten_nutzertexte_python.py`) hat noch
7 Allowlist-Dateien mit 17 Funden, alle unter dem Renderer-Commit-Gate. Ziel: Allowlist leer,
`test_allowlist_ist_leer` ohne `xfail` grün.

## Messung (Stand origin/main a0a14c27a, `--messen`)
| Datei:Zeile | Text | Einordnung | Maßnahme |
|---|---|---|---|
| alert/hours.py:92 | `logger.warning("Stundenzeilen %s …")` | Log | `# i18n-log` |
| alert/model.py:375 | `"über"` (cmp-Protokollwert) | Protokoll-Token | `# i18n-fest: cmp-Protokollwert …` |
| alert/project.py:150 | KeyError „Unbekanntes summary_field …" | interne Exception | `# i18n-log` |
| alert/project.py:153 | `"über"` (cmp) | Protokoll-Token | `# i18n-fest` |
| alert/project.py:199 | KeyError „Kein Segment …" | interne Exception | `# i18n-log` |
| alert/project.py:362 | `logger.warning("Stundenzeilen fuer …")` | Log | `# i18n-log` |
| alert/project.py:442, 524 | ValueError „Leeres cmp …" | interne Exception | `# i18n-log` |
| alert/project.py:615, 631 | ValueError „… benötigt mindestens einen Ort" (mehrzeilig) | interne Exception | `# i18n-log` auf einer der überspannten Zeilen |
| alert/official_alerts.py:153,155,161 | Namen Lawinenwarndienste/SLF | Behördenname (Eigenname, Lizenz-Namensnennung CC BY 4.0) — Datei sagt schon „Behördennamen bleiben in jeder Sprache" (#2668) | `# i18n-fest: Behördenname …` |
| email/html.py:1565 | CSS-Kommentar `/* … durchgängig … */` im f-String | kein Nutzertext (CSS) | `# i18n-fest: CSS-Kommentar …` |
| email/thunder_branch.py:31 | Regex `[a-zA-Zäöü]` | Muster, kein Text | `# i18n-fest: Regex-Zeichenklasse …` |
| trip_report.py:800, 826 | „Gewitter möglich", „💨 Böen bis" in `_compute_highlights` | **toter Code** (s. u.) | Funktion + Aufruf entfernen |

## Kernbefund trip_report.py (löst auch #3016)
`TripReportFormatter._compute_highlights` (trip_report.py:760–887) wird in Zeile 187 berechnet und
als `highlights=` an `render_email()` übergeben. `render_email()` (email/__init__.py) nimmt
`highlights` seit #790 nur noch in `**_ignored` auf — html.py:837 / plain.py:145 dokumentieren
das. Kein anderer Konsument (grep src/api/tests: nur Testaufrufe mit `highlights=[]` an
`render_email`, die weiter über `**_ignored` laufen). Die Highlights erreichen also **keine**
Ausgabe, weder de noch en. Übersetzen wäre Arbeit an totem Code; richtige Maßnahme ist Rückbau
(Funktion + Aufruf + kwarg). Damit ist #3016 („englischen Pfad prüfen") beantwortet: nein,
tot → entfernt. `thunder_low_statement_sentence` bleibt (weitere Aufrufer in compact_summary,
email/helpers, trip_report_scheduler).

## Ausgegliedert
Zusatzpunkt aus #2783 (Frontend-Loader `GET /api/compare/metrics` ohne `?lang=`) ist Frontend
(Spur B) → eigenes Issue #3021 (Epic #2644, `strang:b-frontend`, `go-live-pflicht`).

## Related Files
| File | Relevance |
|------|-----------|
| tests/test_i18n_keine_hartkodierten_nutzertexte_python.py | Ratsche; `xfail` an `test_allowlist_ist_leer` entfernen, Docstring „Startstand/Restbefund" nachziehen |
| tests/fixtures/i18n_python_allowlist.json | auf `{}` |
| src/output/renderers/alert/{hours,model,project,official_alerts}.py | Marker-Kommentare |
| src/output/renderers/email/{html,thunder_branch}.py | Marker-Kommentare |
| src/output/renderers/trip_report.py | `_compute_highlights` + Aufruf entfernen |
| docs/reference/i18n_konventionen.md | Marker-Regeln (`# i18n-log`, `# i18n-fest: <Grund ≥10 Zeichen>`) |

## Existing Patterns
- #2751 hat dasselbe außerhalb des Renderer-Gates gemacht (BOT_COMMANDS `# i18n-fest`).
- Marker greift nur, wenn er auf einer Zeile innerhalb lineno..end_lineno der String-Konstante steht.

## Dependencies
- Renderer-Commit-Gate: Mail-Inhalts-Commits brauchen Modus-Matrix-Test + Validator frisch grün.
  Die Änderung ist ausgabeneutral (nur Kommentare + Entfernen toten Codes) → Mail-Ausgabe
  byte-gleich; Nachweis über bestehende Golden-/Modus-Matrix-Tests und Staging-Mail-Validator.

## Risks & Considerations
- `# i18n-fest`-Grund muss ≥10 Zeichen haben, sonst wirkungslos.
- html.py:1565 liegt mitten im großen f-String-Template (`html = f"""…` ab Zeile 1546). Ein
  Python-Kommentar-Marker ist dort unmöglich (alles ist String; ein `#` landete in der Mail).
  Entscheidung: den CSS-Kommentar aus dem Template nehmen und als Python-Kommentar über das
  Template setzen (interne Issue-Verweise gehören ohnehin nicht in die Kunden-Mail). Folge: die
  Mail-HTML verliert eine CSS-Kommentarzeile (sichtbar nichts) → betroffene Golden-Fixtures
  (u. a. tests/fixtures/issue_974_evening_night_mail.html, befehl_antwortzeit/golden_berichte.json)
  mechanisch nachziehen. Damit ist die Änderung NICHT byte-neutral → Renderer-Gate voll fahren
  (Modus-Matrix + Validator gegen echte Staging-Mail).
- Entfernen von `_compute_highlights`: Prüfen, dass kein Test die Methode direkt aufruft (grep: keiner).
- `tests/tdd/test_fix_911_visual_table.py` erwähnt den CSS-Kommentar-Text: in der Analyse prüfen, ob er ihn als Zusicherung abfragt (dann auf die CSS-Regel `table[data-table="resp"] td {…#f0ece1}` umstellen, nicht auf den Kommentar). Golden-Dateien mit dem Kommentar: tests/golden/email/*-html{,.en}.txt (≥7), issue_974-Fixture, golden_berichte.json.

## Analysis

### Type
Feature (Aufräumen/Ratsche, ausgabeneutral bis auf eine unsichtbare CSS-Kommentarzeile).

### Nachprüfung der Kontext-Befunde (Stand origin/main a0a14c27a)
- **Highlights tot bestätigt:** `render_email(..., **_ignored)` (email/__init__.py:75) schluckt
  `highlights`; einziger Produzent `trip_report.py:187`, einziger Durchreicher `trip_report.py:246`.
- **Korrektur zum Kontext:** Es GIBT einen direkten Testaufrufer:
  `tests/tdd/test_thunder_low_no_event_claim.py::test_compute_highlights_no_gewitter_word_for_low`
  (Z. 150–190). Der Test selbst dokumentiert (Z. 213) die Methode als seit #790 tot; die echte
  Zusicherung (kein „Gewitter" bei reiner CAPE-Herkunft) liegt am Wirkpfad `_pill_for_metric`
  (Test 5/5b, bleibt). → Test 4 mit entfernen, Kommentar Z. 213 nachziehen.
- Übrige `highlights=`-Treffer in Tests sind eigene kwargs-Dicts an `render_email/render_html`
  (absorbiert über `**_ignored`), unberührt. `ReportContext.highlights` (models.py:1429): die
  Dataclass wird nirgends instanziiert — außerhalb des Scopes, nicht anfassen.
- **html.py:1565 bestätigt marker-unfähig:** die String-Konstante spannt Z. 1565–1570 innerhalb
  des f-Strings (1546–1606); dort ist kein Python-Kommentar möglich. Entscheidung bleibt:
  CSS-Kommentar aus dem Template entfernen, als Python-Kommentar vor `html = f"""` setzen.
  Umgehung per Umlaut-Umschreibung („durchgaengig") ist ausdrücklich verworfen (Gate-Umgehung).
- `test_fix_911_visual_table.py` nennt „durchgängig" nur in Kommentar/Fehlermeldung, nicht als
  Zusicherung auf den CSS-Kommentar → unberührt.
- Golden-Dateien mit dem Kommentar (mechanisch nachziehen): tests/golden/email/{gr20-spring-morning,
  gr221-mallorca-evening, corsica-vigilance, gr20-summer-evening, arlberg-winter-morning}-html{,.en}.txt
  (10), tests/fixtures/issue_974_evening_night_mail.html, tests/fixtures/befehl_antwortzeit/golden_berichte.json.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/alert/hours.py | MODIFY | 1× `# i18n-log` |
| src/output/renderers/alert/model.py | MODIFY | 1× `# i18n-fest: cmp-Protokollwert` |
| src/output/renderers/alert/project.py | MODIFY | 6× `# i18n-log` (Logs/Exceptions), 2× `# i18n-fest` (cmp) |
| src/output/renderers/alert/official_alerts.py | MODIFY | 3× `# i18n-fest: Behördenname` |
| src/output/renderers/email/thunder_branch.py | MODIFY | 1× `# i18n-fest: Regex-Zeichenklasse` |
| src/output/renderers/email/html.py | MODIFY | CSS-Kommentar aus Template → Python-Kommentar |
| src/output/renderers/trip_report.py | MODIFY | `_compute_highlights` (Z. 760–887), Aufruf Z. 187, kwarg Z. 246, Docstring Z. 11 entfernen |
| src/output/renderers/email/__init__.py, helpers.py | MODIFY | Docstring-Verweise auf `_compute_highlights` nachziehen |
| tests/tdd/test_thunder_low_no_event_claim.py | MODIFY | Test 4 entfernen, Kommentar Z. 213 anpassen |
| tests/test_i18n_keine_hartkodierten_nutzertexte_python.py | MODIFY | `xfail` an `test_allowlist_ist_leer` weg, Docstring |
| tests/fixtures/i18n_python_allowlist.json | MODIFY | `{}` |
| tests/golden/email/*-html{,.en}.txt (10), issue_974-Fixture, golden_berichte.json | MODIFY | eine CSS-Kommentarzeile entfernen |

### Scope Assessment
- Quelldateien: 9 · Tests/Fixtures: ~15 (überwiegend mechanisch)
- Estimated LoC (Quellcode): +~20 / −~140 (größter Teil: toter `_compute_highlights`)
- Risk Level: LOW–MEDIUM — fachlich ausgabeneutral; Mail-HTML verliert nur eine unsichtbare
  CSS-Kommentarzeile. Renderer-Commit-Gate muss trotzdem voll gefahren werden (Modus-Matrix +
  Validator gegen echt zugestellte Staging-Mail, Official-Validator für official_alerts.py).

### Technical Approach
1. TDD RED: `xfail` an `test_allowlist_ist_leer` entfernen + Allowlist auf `{}` → Ratsche rot
   (17 Funde). Dazu Regressionstest „Mail-HTML enthält keinen CSS-Kommentar mit internem
   Issue-Verweis" ist verzichtbar (Golden-Vergleich deckt es ab).
2. GREEN: Marker setzen (Grund ≥10 Zeichen, auf einer Zeile im lineno..end_lineno-Bereich),
   CSS-Kommentar verlegen, toten Highlights-Pfad + Test 4 entfernen, Goldens nachziehen.
3. Nachweis: Ratsche grün ohne xfail; bestehende Golden-/Modus-Matrix-Tests grün (beweist
   Ausgabegleichheit außer der Kommentarzeile); Staging-Mail-Validatoren im Deploy.

### Dependencies
Keine neuen. #3016 wird mit erledigt (Highlights-Pfad tot → entfernt). #3021 (Frontend `?lang=`)
ist ausgegliedert.

### Open Questions
- keine (keine Produktentscheidung offen; Abweichung von Issue-Text „Katalog plus lang" für
  trip_report.py ist technisch begründet: toter Code wird nicht übersetzt, sondern entfernt).

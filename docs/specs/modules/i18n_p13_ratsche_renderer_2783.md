---
entity_id: i18n_p13_ratsche_renderer_2783
type: refactor
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: i18n-2783-ratsche-renderer
tags: [i18n, epic-2644, issue-2783, python, renderer-gate]
---

# i18n P13: Letzte Renderer-Gate-Dateien der Python-Ratsche abbauen

**Issue:** #2783 (löst #3016 mit) · **Epic:** #2644 · **Folge von:** #2751 (P12) · **Grundsatz:** ADR-0104, `docs/reference/i18n_konventionen.md`

## Approval

- [ ] Approved

## Purpose

Die Python-Ratsche `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` führt nach P12 noch 7 Dateien mit 17 Funden, alle unter dem Renderer-Commit-Gate. Dieses Paket baut sie vollständig ab: Logs und interne Exceptions bekommen `# i18n-log`, Protokollwerte, Behördennamen und Muster bekommen `# i18n-fest: <Grund>`, und toter Code, der nie eine Ausgabe erreichte, wird entfernt statt übersetzt. Danach ist die Allowlist leer und `test_allowlist_ist_leer` läuft ohne `xfail`.

## Source

- **File:** `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py`, `tests/fixtures/i18n_python_allowlist.json`
- **Identifier:** `test_allowlist_ist_leer` (xfail entfällt), Allowlist `{}`
- Betroffene Renderer: `src/output/renderers/alert/{hours,model,project,official_alerts}.py`, `src/output/renderers/email/{html,thunder_branch}.py`, `src/output/renderers/trip_report.py` (`TripReportFormatter._compute_highlights`)

Schicht: ausschließlich Python-Core (`src/output/renderers/`), kein Frontend, keine Go-API, keine Nutzerdaten.

## Scope

**In Scope:** Marker (`# i18n-log`, `# i18n-fest: <Grund>`) für alle 17 Restfunde in den sieben Renderer-Dateien, Verlegen des CSS-Kommentars aus dem Mail-Template in einen Python-Kommentar samt Golden-Bereinigung, Rückbau des toten Highlights-Pfads in `trip_report.py` (inkl. Test 4 in `test_thunder_low_no_event_claim.py`), Allowlist `{}`, `xfail` an `test_allowlist_ist_leer` entfernen, Ratschen-Zeile in `docs/reference/i18n_konventionen.md` auf „leer" nachziehen.

**Out of Scope:** Frontend `?lang=` für `GET /api/compare/metrics` (#3021), `ReportContext.highlights` in `models.py`, jede inhaltliche Änderung an Mail, Telegram, SMS oder Premium-SMS.

## Definition of Done

- AC-1 bis AC-6 erfüllt; Python-Ratsche meldet 0 Funde, Allowlist ist `{}`, `test_allowlist_ist_leer` grün ohne `xfail`.
- Bestehende Golden-/Modus-Matrix-Tests grün (Mail-Ausgabe bis auf die entfernte CSS-Kommentarzeile byte-gleich).
- Renderer-Commit-Gate voll gefahren: Trip-Briefing- und Official-Validator gegen echt zugestellte Staging-Mail grün.
- #3016 mit Verweis auf den Rückbau geschlossen; #2783 erst nach Prod-Selftest Exit 0 geschlossen.

## Estimated Scope

- **LoC:** Quellcode ca. +20/-140 (Großteil: toter `_compute_highlights`); Goldens je eine Zeile weniger
- **Files:** 9 Quelldateien, ca. 15 Test-/Fixture-Dateien (überwiegend mechanisch)
- **Effort:** medium (wegen Renderer-Gate)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/reference/i18n_konventionen.md` | Doku | Marker-Regeln; Tabellenzeile Ratsche (Z. 107) wird auf „leer" nachgezogen |
| Ratsche P11/P12 (`# i18n-fest: <Grund>`) | Test-Infrastruktur | Marker wirkt nur mit Grund ≥ 10 Zeichen auf einer Zeile im Bereich `lineno..end_lineno` der Konstante |
| Renderer-Commit-Gate (#811) | Gate | Modus-Matrix-Test plus Validatoren gegen echt zugestellte Staging-Mail |
| `briefing_mail_validator.py`, Official-Validator | Validator | Nachweis der unveränderten Mail-Ausgabe auf Staging |
| `render_email()` (`email/__init__.py`) | Funktion | schluckt `highlights` seit #790 in `**_ignored`, Beweis für toten Pfad |
| #3021 | Issue | Frontend `?lang=` für `GET /api/compare/metrics`, ausgegliedert |

## Implementation Details

**Marker (keine Ausgabeänderung):**

- `alert/hours.py` (1 Log) und `alert/project.py` (Logs und interne KeyError/ValueError, 6 Funde, davon zwei mehrzeilig: Marker auf einer der überspannten Zeilen) erhalten `# i18n-log`.
- `alert/model.py` und `alert/project.py`: der cmp-Protokollwert „über" erhält `# i18n-fest: cmp-Protokollwert, nie übersetzen`.
- `alert/official_alerts.py` (3 Funde): Namen der Lawinenwarndienste und SLF erhalten `# i18n-fest: Behördenname, Eigenname und Lizenz-Namensnennung`.
- `email/thunder_branch.py`: Regex-Zeichenklasse `[a-zA-Zäöü]` erhält `# i18n-fest: Regex-Zeichenklasse, kein Nutzertext`.
- Umgehung durch Umlaut-Umschreibung (z. B. „durchgaengig") ist ausdrücklich verworfen.

**CSS-Kommentar in `email/html.py` (~Z. 1565):** Er steht mitten im f-String-Template `html = f"""…"""`; dort ist kein Python-Marker möglich (ein `#` landete in der Mail). Der Kommentar wird aus dem Template genommen und als Python-Kommentar vor das Template gesetzt (interne Issue-Verweise gehören ohnehin nicht in die Kunden-Mail). Folge: die Mail-HTML verliert eine unsichtbare CSS-Kommentarzeile. Betroffene Goldens werden mechanisch um genau diese Zeile bereinigt: `tests/golden/email/{gr20-spring-morning,gr221-mallorca-evening,corsica-vigilance,gr20-summer-evening,arlberg-winter-morning}-html{,.en}.txt` (10 Dateien), `tests/fixtures/issue_974_evening_night_mail.html`, `tests/fixtures/befehl_antwortzeit/golden_berichte.json`. `test_fix_911_visual_table.py` nennt den Kommentar nur in Meldungen, nicht als Zusicherung, und bleibt unberührt.

**Toter Highlights-Pfad in `trip_report.py`:** `_compute_highlights` (Z. 760–887) wird in Z. 187 berechnet und als `highlights=` (Z. 246) an `render_email()` gereicht, das den Parameter seit #790 verwirft. Er erreicht keine Ausgabe, weder de noch en. Entfernt werden Methode, Aufruf, kwarg und Docstring-Verweise (`trip_report.py` Z. 11, `email/__init__.py`, `email/helpers.py`). `thunder_low_statement_sentence` bleibt (weitere Aufrufer). `ReportContext.highlights` in `models.py` bleibt unberührt (außerhalb des Scopes). Im Test `tests/tdd/test_thunder_low_no_event_claim.py` wird Test 4 (ruft die tote Methode) entfernt und der Kommentar Z. 213 angepasst; Test 5/5b bewachen die Zusicherung am Wirkpfad `_pill_for_metric`.

**Abweichung vom Issue-Text:** Das Issue sieht für `trip_report.py` „Katalog plus `lang`" vor. Die Analyse zeigt toten Code; Übersetzen wäre Arbeit an Code ohne Wirkung. Daher Rückbau statt Übersetzung. Damit ist #3016 („englischen Pfad prüfen") beantwortet: es gibt ihn nicht, weil der Code nie eine Ausgabe erreichte.

**Ausgegliedert (Out of Scope):** Frontend-Loader `GET /api/compare/metrics` ohne `?lang=` nach #3021 (Spur B).

**Kanäle:** Keine Änderung an Inhalt oder Form in E-Mail, Telegram, SMS oder Premium-SMS; betroffen ist nur die E-Mail-HTML um eine unsichtbare Kommentarzeile.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN `xfail` an `test_allowlist_ist_leer` entfernt und Allowlist auf `{}` WHEN die Ratsche vor der Umsetzung läuft THEN ist sie rot mit 17 Funden (Rot-Nachweis)
- [ ] GIVEN die Umsetzung WHEN die Ratsche läuft THEN 0 Funde, `test_allowlist_ist_leer` grün ohne xfail
- [ ] GIVEN bestehende Golden-Tests und Modus-Matrix-Test WHEN sie nach Entfernen des Kommentars und des toten Pfads laufen THEN grün
- [ ] GIVEN `test_thunder_low_no_event_claim.py` ohne Test 4 WHEN er läuft THEN Test 5/5b grün
- [ ] Keine Mock-Tests (Projektregel); Nachweis über echte Rendering-Läufe und Golden-Vergleich

## Acceptance Criteria

- **AC-1:** Given der Repo-Stand nach diesem Paket / When die Ratsche `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` läuft / Then ist `tests/fixtures/i18n_python_allowlist.json` gleich `{}`, `test_allowlist_ist_leer` läuft ohne `xfail` grün, und die Ratsche meldet 0 Funde.
  - Test: Ratsche und `--messen` über alle `src/output/**`-Dateien liefern null Funde; kein Fund ist durch Allowlist verdeckt.

- **AC-2:** Given Log-/Exception-Texte, cmp-Protokollwerte, Behördennamen und eine Regex-Zeichenklasse in den Renderer-Dateien / When die Ratsche sie prüft / Then tragen Logs und interne Exceptions in `alert/hours.py` und `alert/project.py` `# i18n-log`, und der cmp-Wert „über" (`model.py`, `project.py`), die Behördennamen (`official_alerts.py`) und die Regex-Zeichenklasse (`thunder_branch.py`) tragen `# i18n-fest: <Grund ≥ 10 Zeichen>` auf einer Zeile im Bereich `lineno..end_lineno` der Konstante, ohne Umlaut-Umschreibung.
  - Test: Ratsche zählt diese Literale nicht mehr; ein Marker ohne oder mit zu kurzem Grund würde weiter als Fund zählen; die Alarm-Ausgabe (cmp-Vergleich, Behördenhinweis) bleibt wertgleich.

- **AC-3:** Given der tote Highlights-Pfad in `trip_report.py` / When `TripReportFormatter._compute_highlights`, sein Aufruf, das `highlights=`-kwarg und die Docstring-Verweise entfernt sind / Then ist die Trip-Briefing-Mail (HTML und Plain, de und en) inhaltlich unverändert, und #3016 ist beantwortet: ein englischer Highlights-Pfad existiert nicht, weil der Code nie eine Ausgabe erreichte.
  - Test: bestehende Golden- und Modus-Matrix-Tests für Trip-Briefing in de und en bleiben grün; kein Aufrufer von `_compute_highlights` verbleibt.

- **AC-4:** Given der CSS-Kommentar im f-String-Template von `email/html.py` / When er aus dem Template entfernt und als Python-Kommentar vor das Template gesetzt ist / Then enthält die erzeugte Mail-HTML ihn nicht mehr, die Golden-Dateien (10× `tests/golden/email/*-html{,.en}.txt`, `tests/fixtures/issue_974_evening_night_mail.html`, `tests/fixtures/befehl_antwortzeit/golden_berichte.json`) sind genau um diese Kommentarzeile bereinigt und sonst byte-gleich, und die sichtbare Darstellung ist unverändert.
  - Test: Golden-Vergleich der gerenderten Mail gegen die bereinigten Dateien; Differenz zum Altstand ist genau eine Zeile je Datei.

- **AC-5:** Given die Zusicherung „kein ‚Gewitter' bei reiner CAPE-Herkunft" / When `tests/tdd/test_thunder_low_no_event_claim.py` läuft / Then bleibt sie am Wirkpfad `_pill_for_metric` durch Test 5/5b geprüft, und Test 4, der die tote Methode rief, ist entfernt.
  - Test: Test 5/5b rendern die Pille für reine CAPE-Herkunft und finden kein „Gewitter".

- **AC-6:** Given Änderungen an Dateien unter dem Renderer-Commit-Gate / When das Gate voll gefahren wird / Then ist der Modus-Matrix-Test grün, und der Trip-Briefing-Validator (`briefing_mail_validator.py`) sowie der Official-Validator laufen gegen echt zugestellte Staging-Mail grün.
  - Test: Validatoren lesen die zugestellte Staging-Mail im Test-Postfach (Exit 0); kein Mock, keine Gate-Umgehung.

## Known Limitations

- **Frontend:** Das Mitgeben von `?lang=` im Loader für `GET /api/compare/metrics` ist Frontend-Arbeit und liegt in #3021.
- **`ReportContext.highlights`** (`models.py`) wird nirgends instanziiert; bewusst nicht Teil dieses Pakets.
- Die Staging-Validatoren sind nur im Deploy-Lauf (nach Push) herstellbar; die Gate-Reihenfolge wird nicht umgangen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Setzt die bestehende Entscheidung (Katalog für Nutzertexte, Marker für Logs und Protokoll-Token, Protokoll-Token nie übersetzen) um; kein neues ADR nötig. Tote Pfade werden entfernt statt übersetzt.

## Changelog

- 2026-11-15: Erstfassung (#2783, löst #3016 mit); zusätzlich `docs/reference/i18n_konventionen.md` Z. 107 auf „leer" nachziehen

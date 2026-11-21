---
entity_id: tote_tests_inventur
type: refactor
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
issue: 3207
epic: 1196
workflow: rework-3207-tote-tests
tags: [tests, aufraeumen, regel-budget]
---

# Tote Tests fuer abgeloeste Funktionen entfernen (#3207)

## Approval

- [ ] Approved

## Purpose

Tests, die Funktionen pruefen, die es im Produkt nicht mehr gibt (Signal-Kanal, NiceGUI-Oberflaeche, alte Telegram-Zeilen, abgeloeste Befehle, entfernte Reiter und Komponenten), werden mit Beleg entfernt, ohne eine noch geltende Zusicherung zu verlieren. Zusaetzlich wird eine Prozessregel verankert, die kuenftig verlangt, beim Abloesen einer Funktion die zugehoerigen Tests im selben Umbau mitzuentfernen.

## Source

- **File:** `docs/context/rework-3207-tote-tests.md` (Abschnitt "Analysis": Kandidatenlisten, Bleibt-Liste, Technical Approach)
- **Identifier:** Testbestand unter `tests/` (Python) und `frontend/` (Playwright-Specs, Unit-Tests); Regel in `docs/reference/workflow_und_agenten.md`

Schicht: reine Testsuite-Sanierung, kein Produktcode in `src/`, `api/`, `internal/` oder `frontend/src/` wird veraendert. Kein Trip/Vergleich-Pendant, keine Nutzerdaten bewegt, kein Briefing-/Alarm-Inhalt veraendert (die vier Kanaele bleiben durch ihre Nachfolgetests bewacht).

## Estimated Scope

- **LoC:** ca. -2.500 bis -3.500 (reine Loeschungen), +ca. 60 (Regel, Meta-Test, Listenpflege)
- **Files:** ca. 45
- **Effort:** medium

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_issue_635_telegram_weather.py` | DELETE | modulweit skip "OBSOLET (#1001)", `render_narrow` fehlt in src/ |
| `tests/e2e/test_safari_preventive_fix.py`, `test_locations_add_button.py`, `test_subscriptions_safari.py`, `test_trips_start_time_buttons.py` | DELETE | NiceGUI-Oberflaeche stillgelegt (M4b), `src/web/` weg |
| `tests/tdd/test_issue_496_layout.py` | DELETE | testids `channel-preview-block`, `channel-fidelity-email` ohne Treffer (ADR-0109/0124) |
| `tests/tdd/test_701_alerts_metrik_sync.py` | DELETE | testid `alerts-add-rule` ohne Treffer |
| `tests/tdd/test_issue_934_wizard_schedule.py` | DELETE (nur bei vollstaendigem Beleg je Selektor) | alter Wizard-Aufbau (ADR-0109); sonst bleibt die Datei |
| `tests/tdd/test_issue_612_report_on_demand.py` (Z.179/184/195), `test_issue_360_channel_renderer.py` (Z.159/217/228), `test_bug_397_output_localtime.py` (Z.397), `test_issue_397_segment_timezone.py` (Z.186), `test_issue_887_report_inkonsistenz.py` (Z.145/160/175/262), `test_issue_614_telegram_kurzform.py` (Z.166/185), `tests/test_trip.py` (Z.98) | MODIFY | nur tote Testfaelle entfernen, Rest der Datei bleibt |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` (Z.98/108/132) | MODIFY | Namenslisten (701/496/934) mitpflegen |
| `frontend/e2e/weather.spec.ts`, `issue-407-waypoint-editor-screen.spec.ts`, `issue-294-home-kachel.spec.ts`, `startseite.spec.ts`, `trip-detail-overview-left.spec.ts`, `layout-tab-vergleich.spec.ts`, `orts-gruppen-c2.spec.ts`, `issue-88-report-config-dialog.spec.ts`, `accent-ctas.spec.ts` | DELETE | Ziel (Route, Komponente, Reiter) fehlt, alle nicht auf `.github/ci_e2e_specs.txt` |
| `issue-302-trip-detail-redesign`, `trip-detail-tabs`, `layout-tab-route`, `compare-layout-tab-dissolution`, `issue-343-horizon-chips`, `issue-452-smart-import-step2`, `mobile-stages-listen-only`, `issue-609-sms-profil`, `issue-313-design-showcase`, `anlege-rahmen-paritaet`, `issue-682-compare-editor-mobile`, `compare-editor-fidelity-s8d`, `hub-anlegen-ablauf` (je `.spec.ts` unter `frontend/e2e/`) | MODIFY | nur belegt tote Faelle entfernen; Abwesenheits-Zusicherungen (`toHaveCount(0)`) bleiben |
| `frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts` | MODIFY | 3x `test.skip` "obsolet durch #439" entfernen |
| `.github/ci_e2e_specs.txt` | MODIFY (nur falls noetig) | nur falls eine gelistete Spec ganz entfaellt; Mindestzahl `E2E_MIN_SPECS` mitziehen |
| `docs/reference/workflow_und_agenten.md` | MODIFY | neue Regel im Abschnitt Regel-Budget |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Zeile in der Pruefdaten-Tabelle |
| `tests/test_regel_tote_tests_mitentfernen_pruefdatum.py` | CREATE | Doku-Compliance-Meta-Test (`# doc-compliance-test`) |

Die endgueltige Dateiliste entsteht in der Umsetzung: jede Datei wird einzeln neu belegt, die Inventur ist nur Kandidatenliste. Was den Beweis nicht besteht, faellt aus dem Scope und bleibt.

### Estimated Changes

- Files: ca. 45
- LoC: -2.500 bis -3.500 / +60
- LoC-Limit-Override: wird beantragt und im PR begruendet. Das Limit zielt auf neu geschriebenen Code; hier sind rund 98 % der Zeilen reine Loeschungen toter Testdateien ohne neue Logik, das Risiko liegt im Beleg je Datei, nicht im Umfang.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0004 / Issue #610 | decision | Signal-Kanal entfernt: Beleg fuer Signal-Testfaelle |
| ADR-0109, ADR-0124, Issue #3154 | decision | alter Wizard, Layout-Reiter abgeloest |
| ADR-0108, Issue #3196 | decision | Aktivitaets-Chips entfernt |
| Issue #1001, #884, #409, #439 | issue | Abloese-Belege (Telegram-Bubbles, Befehlsblock, Detail-Redesign, Migration) |
| ADR-0094 | decision | Test-Schichten (Kern-Schicht 100 % gruen) |
| ADR-0100 | decision | Regel-Budget: neue Regel mit Pruefdatum +90 Tage |
| `tests/tdd/test_pytest_collection_and_timeout_safety.py` | test | Meta-Test mit Namenslisten, muss mitgepflegt werden |
| `.github/ci_e2e_specs.txt`, `.github/ci_tdd_excludes.txt` | config | Ratschen-Listen; Eintraege nur mitschrumpfen |
| `tests/test_regel_budget_pruefdatum_einstellung_auslieferung.py` | test | Vorbild und Nachbar fuer den neuen Doku-Meta-Test |
| Nachfolgetests (z. B. `test_issue_1001_telegram_bubbles`, #884-Tests, Renderer-Tests) | test | fangen die weiter geltenden Zusicherungen |

## Implementation Details

1. **Beweis-Dreiklang je Datei/Fall**, im PR-Beleg: (a) Ziel fehlt auf origin/main (grep auf Symbol/Route/Komponente/testid in `src`, `api`, `internal`, `frontend/src` mit Befehl und 0 Treffern; Kommentar-Treffer zaehlen nicht), (b) Abloese-Beleg (ADR/Issue/Spec), (c) Nachfolgetest benannt, der die geltende Zusicherung bewacht. Fehlt ein Kriterium, bleibt die Datei bzw. der Fall.
2. **Gemischte Dateien** (397, 887, 360, 612, 614, `test_trip.py`) werden nur um die toten Faelle gekuerzt. Vor/nach jeder Aenderung wird die Testliste (`pytest --collect-only -q` auf die benannte Datei) verglichen; es duerfen genau die gelisteten Tests verschwinden.
3. **Unangetastet:** Abwesenheits-Waechter (`*_removed.py`, `*dead*`, `tests/refactor/*`, `test_issue_610_signal_backend_red.py`, `assert not hasattr`), Umgebungs-Skips (SMTP, Staging, Playwright fehlt), Bug-/xfail-Skips, Migrationstests, `use_friendly_format`-Tests, alle Go-Tests (Inventur: keine toten Tests).
4. **Mutations-Gegenprobe** an mindestens drei Stichproben per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`): Telegram-Bubble-Zeile (Nachfolger von 635/887/614), Zeitzonen-Anzeige (#397), Befehlsblock (#884). Der benannte Nachfolgetest muss rot werden; danach wird der Produktcode aus der Sicherung wiederhergestellt.
5. **Regel:** reine Prozessregel "abgeloeste Funktion => Tests im selben Umbau entfernen, Beleg im PR" im Regel-Budget-Abschnitt von `docs/reference/workflow_und_agenten.md`; Zeile in der Pruefdaten-Tabelle von `docs/reference/gates_und_ratschen.md` mit Pruefdatum 2027-02-19 und Fang-Mass (Zahl der seither neu entstandenen toten Tests bzw. im selben Umbau mitentfernten Tests). Maschinell nur als Doku-Compliance-Meta-Test; kein neues Gate, keine Aenderung an wirksamer Gate-Konfiguration.
6. **PR-Text** enthaelt eine Tabelle aller entfernten Dateien/Faelle mit Begruendung und Beleg.

## Expected Behavior

- **Input:** Testbestand mit Kandidatenliste aus der Inventur.
- **Output:** Testbestand ohne belegt tote Tests; Kern-Schicht weiter vollstaendig gruen; Regel samt Pruefdatum dokumentiert.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt; Testanzahl sinkt um genau die gelisteten Tests.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN die neue Regel fehlt in der Doku WHEN `tests/test_regel_tote_tests_mitentfernen_pruefdatum.py` laeuft THEN schlaegt er fehl (RED), bis Regel und Tabellenzeile stehen.
- [ ] Test 2: GIVEN Regel und Zeile stehen WHEN der Meta-Test laeuft THEN ist er gruen und prueft Regeltext, Pruefdatum 2027-02-19 und Fang-Mass.
- [ ] Test 3: GIVEN Testdateien geloescht wurden WHEN `test_pytest_collection_and_timeout_safety.py` laeuft THEN ist er gruen (Namenslisten konsistent).
- [ ] Test 4: GIVEN je eine Stichproben-Mutation am Nachfolger-Produktcode WHEN der benannte Nachfolgetest laeuft THEN wird er rot (manuelle Gegenprobe, Ergebnis im PR).
- [ ] Test 5: GIVEN die Kern-Schicht WHEN die betroffenen und benachbarten Testdateien namentlich laufen THEN sind alle gruen.

## Definition of Done

- [ ] Jede geloeschte Datei und jeder entfernte Testfall mit Beweis-Dreiklang in der PR-Tabelle (AC-1, AC-7)
- [ ] Collect-Diff der gemischten Dateien entspricht exakt der Liste; Abwesenheits-Waechter, Umgebungs-/Bug-Skips, Migrations- und Go-Tests unveraendert (AC-2, AC-3)
- [ ] Mutations-Gegenprobe an mindestens drei Stichproben dokumentiert, Nachfolgetests rot und nach Wiederherstellung gruen (AC-4)
- [ ] Regel samt Pruefdatum 2027-02-19 in der Doku, Meta-Test gruen (AC-6)
- [ ] Adversary-Verdict VERIFIED, alle 6 CI-Checks gruen, Kern-Schicht 100 % gruen, ausgeliefert, Selftest gruen (AC-5)

## Acceptance Criteria

- **AC-1:** Given eine Testdatei oder ein Testfall ist Kandidat fuer die Loeschung / When der Umbau sie entfernt / Then liegt im PR je Datei der Beweis-Dreiklang vor (Ziel fehlt auf origin/main per grep mit 0 Treffern ausserhalb von Kommentaren, Abloese-Beleg per ADR/Issue/Spec, Nachfolgetest benannt), und fehlt ein Kriterium, bleibt die Datei bestehen (z. B. `test_issue_934_wizard_schedule` wird nur bei vollstaendigem Beleg je Selektor geloescht).
  - Test: Pruefung des PR-Belegs je Datei; fuer die Stichprobe wird das grep auf das Ziel erneut ausgefuehrt und liefert 0 Treffer in `src`, `api`, `internal`, `frontend/src`.

- **AC-2:** Given gemischte Dateien (397, 887, 360, 612, 614, `tests/test_trip.py`) enthalten tote und geltende Testfaelle / When nur die toten Faelle entfernt werden / Then zeigt der Vorher-Nachher-Vergleich der Testliste genau die gelisteten Tests als verschwunden und alle uebrigen Tests der Datei laufen unveraendert weiter.
  - Test: `pytest --collect-only -q` je betroffener Datei vor und nach der Aenderung; die Differenz entspricht exakt der Liste im PR.

- **AC-3:** Given Abwesenheits-Waechter, Umgebungs-Skips, Bug-/xfail-Skips, Migrationstests und Go-Tests / When der Umbau abgeschlossen ist / Then ist keiner davon veraendert oder entfernt worden.
  - Test: Diff des Umbaus enthaelt keine Datei aus diesen Gruppen (kein `*_removed.py`, kein `tests/refactor/*`, kein `*_test.go`, kein Migrationstest).

- **AC-4:** Given die entfernten Tests hatten Nachfolgetests / When an mindestens drei Stichproben der Nachfolger-Produktcode gezielt verfaelscht wird (Telegram-Bubble-Zeile, Zeitzonen-Anzeige aus #397, Befehlsblock aus #884) / Then wird der jeweils benannte Nachfolgetest rot, und nach Wiederherstellung des Produktcodes ist er wieder gruen.
  - Test: Mutation per String-Ersetzung mit externer Sicherungskopie, Ergebnis (rot/gruen) je Stichprobe im PR dokumentiert; keine geltende Zusicherung verloren.

- **AC-5:** Given Dateien werden geloescht, die in Meta-Tests oder Ratschen-Listen namentlich stehen / When der Umbau fertig ist / Then sind `test_pytest_collection_and_timeout_safety.py` und gegebenenfalls `.github/ci_e2e_specs.txt` samt `E2E_MIN_SPECS` mitgepflegt, alle 6 CI-Checks (`test`, `lint`, `go-test`, `svelte-check`, `frontend-test`, `e2e`) sind gruen und die Kern-Schicht ist zu 100 % gruen.
  - Test: CI-Lauf des PR mit allen 6 Checks gruen; Meta-Test laeuft lokal gruen.

- **AC-6:** Given die Prozessregel fehlt bisher / When der Umbau sie verankert / Then steht "abgeloeste Funktion => Tests im selben Umbau entfernen, Beleg im PR" im Regel-Budget-Abschnitt von `docs/reference/workflow_und_agenten.md` und eine Zeile in der Pruefdaten-Tabelle von `docs/reference/gates_und_ratschen.md` mit Pruefdatum 2027-02-19 und Fang-Mass, und der Doku-Compliance-Meta-Test `tests/test_regel_tote_tests_mitentfernen_pruefdatum.py` (Marker `# doc-compliance-test`) wird rot, sobald Regel, Zeile oder Datum fehlen.
  - Test: Meta-Test zuerst rot ohne Doku-Aenderung, danach gruen; es wird kein neues Gate und keine wirksame Gate-Konfiguration angelegt oder geaendert.

- **AC-7:** Given der Umbau ist fertig / When der PR geoeffnet wird / Then enthaelt der PR-Text eine Tabelle aller entfernten Dateien und Faelle mit Begruendung und Beleg, und die LoC-Limit-Abweichung ist als reine Loeschung begruendet.
  - Test: PR-Text enthaelt die Tabelle; jede geloeschte Datei im Diff taucht in ihr auf.

## Known Limitations

- Nicht verdrahtete Playwright-Specs (168 von 254 stehen nicht auf der Positivliste) und die Frage "verdrahten oder loeschen" sind Governance, nicht Teil dieses Umbaus (Kommentar in #1196).
- `tests/red/test_issue_435_format_modes.py` ist RED-Ablage einer gebauten Funktion, nicht abgeloest; bleibt (Kommentar in #1196).
- Dynamisch gebaute testids (z. B. `trip-detail-tab-${v}`) gelten nicht als Totbeweis; der Beweis erfolgt im Zweifel nicht, die Datei bleibt.
- Die Regel ist nicht maschinell durchsetzbar (Abwesenheits-Waechter waeren Fehlalarme); sie wird am Pruefdatum 2027-02-19 am Fang-Mass bewertet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Aufraeumen nach bestehenden Entscheidungen (ADR-0004, -0094, -0100, -0108, -0109, -0124); die neue Regel faellt unter das Regel-Budget aus ADR-0100 und fuehrt keine neue Architekturentscheidung ein.

## Changelog

- 2026-11-21: Initial spec created

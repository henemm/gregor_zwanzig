---
entity_id: feat_3232_validator_windrichtung
type: feature
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: feat-3232-validator-windrichtung
tags: [validator, mail, windrichtung, gate, epic-3222]
---

# Mail-Validatoren pruefen die Windrichtungs-Faerbung (Nachzug #3228)

## Approval

- [ ] Approved

## Purpose

Die beiden Mail-Validatoren (Trip-Briefing und Orts-Vergleich) pruefen die Windrichtungs-Faerbung aus #3228 (Toenung und Ampelpunkt der Wind-Zelle je Stunde, beim Vergleich zusaetzlich die Windrichtungs-Zeile) gegen ein explizites Soll, das per `--windrichtung JSON` uebergeben wird. Das Soll steht im Sendeskript und wird vom Validator nicht nachgerechnet (Schutz gegen Selbstbestaetigung). Ohne den Schalter bleibt jedes Verhalten unveraendert. Eigener Workflow, weil Validator-Aenderungen nie im Feature-Workflow laufen, dessen Ergebnis sie pruefen (Epic #3222, Issue #3232).

## Source

- **File:** `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py`
- **Identifier:** `pruefe_windrichtung`, `_etappen_tabellen_attrs`, `pruefe_windrichtung_orte`, `validate_message(windrichtung=...)`, CLI `--windrichtung`

> **Schicht-Hinweis:** Reines Tooling (`.claude/hooks/`, `scripts/`, `.claude/commands/`, `docs/`) plus Tests unter `tests/tdd/`. Keine Aenderung an Go-API, Frontend oder Python-Core-Renderer.

> **Querschnitts-Pruefpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Validatoren nutzen die gemeinsame Hilfsfunktion `zellstufe()` aus `_soll_aus_konfiguration.py`; nur das Auffinden der Zelle ist je Mail-Template eigen. Kein neues Pendant-Bauteil.
> - **Mandantentrennung:** Keine Nutzerdaten bewegt; die Validatoren lesen nur eine zugestellte Mail.
> - **Kanaele:** Betrifft ausschliesslich die E-Mail-Pruefung; Telegram, SMS, Premium-SMS unberuehrt (Kanal-Paritaet folgt in Epic #3222 S3).

## Estimated Scope

- **LoC:** ca. +150/-15 Code, +170 Tests, +25 Doku
- **Files:** 6 MODIFY, 1 CREATE
- **Effort:** medium (Gate-Code unter `.claude/hooks/`: PO-`override`, Adversary mindestens 2 Runden)

## Scope

- **Im Umfang:** Windrichtungs-Pruefung in `briefing_mail_validator.py` und `email_spec_validator.py` (Schalter `--windrichtung`), gemeinsame Hilfsfunktion `zellstufe()`, explizites Soll im Sendeskript `scripts/send_gate_test_mails.py`, Aufrufe in `.claude/commands/e2e-verify.md`, Doku `docs/reference/mail_validators.md`, Tests `tests/tdd/test_feat_3228_windrichtung_validatoren.py`.
- **Nicht im Umfang:** Renderer-Aenderungen (Mail-Inhalt bleibt wie in #3228), Telegram/SMS/Premium-SMS (Kanal-Paritaet in Epic #3222 S3), andere Mailpfade ohne Windrichtungs-Soll, Nachrechnen der Soll-Stufe im Validator.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3228 (Renderer Wind-Zelle mit Kompass, Toenung) | feature | Liefert die zu pruefende Mail-Ausgabe |
| `src/output/renderers/email/helpers.py` | module | Ampelpunkt der Wind-Zelle: `mit_windrichtung(...)` ergibt die Stufe, `_ampel_dot_css(level) if level else "–"` |
| `design_tokens.tone_css` | module | Zelltoenung je Stufe |
| `.claude/hooks/_soll_aus_konfiguration.py` (`ampel_farbe`, `_soll_modul()._REG`) | tooling | Farb-/Stufenerkennung aus `<td>`-Attributen |
| `scripts/send_gate_test_mails.py` | tooling | Sendet Gate-Mails und druckt die Soll-Zeile |
| `.claude/commands/e2e-verify.md` | tooling | Ruft die Validatoren mit dem Soll auf |
| `docs/specs/modules/feat_3228_windrichtung_mail.md` | spec | Soll-Stufen, Abschnitt Validatoren |
| `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` | spec | `--konfig`-Muster (optionales Soll) |

## Implementation Details

Entwurf (Patches und Testdatei) steht im Body von Issue #3232 und laesst sich sauber anwenden. Zusaetzlich gelten diese Korrekturen:

1. **Soll-Format.** `--windrichtung` ist JSON-Objekt. Briefing: Schluessel `wind_zellen` (Segment-ID als Zahl-Text, Wert: Liste der erwarteten Stufen je Stunde). Vergleich: Schluessel `orte` (je Ort erwartete Stufe der Windrichtungs-Zeile und der Wind-Zellen je Stunde). Positionsregel Briefing: Segment N = N-te Etappen-Stundentabelle (ohne Nacht), lueckenlose IDs ab 1; im Docstring und in `mail_validators.md` festgehalten.
2. **Eingabepruefung.** Soll wird frueh geparst und validiert (Objekt, erforderlicher Schluessel, numerische Segment-IDs). Fehler: Ausgabe `FEHLER: --windrichtung ungueltig: <Grund>` und `sys.exit(2)` in beiden CLIs (Exit 1 bleibt "Spec verletzt").
3. **Format.** Ist ein Soll gegeben und `X-GZ-Format` ist nicht `full`, meldet der Briefing-Validator `SOLL: Windrichtung nur im Format full pruefbar (X-GZ-Format=...)`.
4. **Segment-Grenzen.** Pruefung `not 1 <= int(sid) <= len(tabellen)` ergibt eine Meldung; fehlende Tabelle ist ein Fehler, nie stilles Ueberspringen.
5. **`zellstufe()` (Stufe aus `<td>`-Attribut).** Punkt-Erkennung mit demselben Regex wie `ampel_farbe` (`border-radius:\s*50%`), damit abweichende Schreibweise laut wird.
6. **Regel "Toenung ohne Punkt" (Renderer-Fakt, geprueft).** `helpers.py` Z. 878-883: im Ampel-Modus mit Windrichtung ist der Punkt `_ampel_dot_css(level)`, wenn eine Stufe existiert, sonst "–" (kein Punkt, keine Staerke-Stufe). Eine getoente Wind-Zelle traegt daher immer einen Ampelpunkt derselben Stufe. Soll-Regel: ist die Toenung ungleich green und fehlt der Punkt, liefert `zellstufe` `Toenung X/Punkt fehlt` und der Validator meldet das laut (kein stilles "Punkt = Toenung").
7. **Refaktorierung.** Tabellen-Parsing aus `_soll_ampel` wird in `_etappen_tabellen_attrs` herausgezogen, beide Pruefungen nutzen es; `_soll_ampel` bleibt verhaltensgleich.
8. **Vergleich.** `_find_location_hour_table(roh=)`, `pruefe_windrichtung_orte`: Windrichtungs-Zeile und Wind-Zelle je Ort; Stundenverlauf als Liste verglichen, damit die Meldung die Stunde nennt.
9. **Sendeskript.** `RAD_ETAPPEN` erhaelt als 4. Tupel-Element die Soll-Stufe je Stunde; `windrichtung_soll()["wind_zellen"]`, `COMPARE_WIND_STUFEN` und `compare_windrichtung_soll()["orte"]` liefern das Soll explizit; es wird als Zeile "Soll Windrichtung:" gedruckt (bereits vorhanden).
10. **e2e-verify.** Die Validator-Aufrufe (DE und EN) in `.claude/commands/e2e-verify.md` werden um `--windrichtung '<Zeile "Soll Windrichtung">'` ergaenzt.

## Expected Behavior

- **Input:** zugestellte Mail (`.eml`/Postfach) plus optional `--windrichtung JSON`.
- **Output:** Exit 0 wenn Soll erfuellt; Exit 1 mit je verfaelschter Zelle genau einer Meldung (Segment/Ort, Stunde, erwartet, gefunden); Exit 2 bei ungueltiger Eingabe.
- **Side effects:** keine; ohne `--windrichtung` identisch zu heute.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_feat_3228_windrichtung_validatoren.py` (neu): echte Renderer, dann `build_mime_message`, dann `validate_message`; Gegenprobe per String-Ersetzung auf dem erzeugten HTML. Kein `Mock()`/`patch()`.

- [ ] GIVEN Gate-Mail mit Soll WHEN Briefing-Validator laeuft THEN keine Meldung.
- [ ] GIVEN eine verfaelschte Wind-Zelle (Toenung getauscht) WHEN geprueft THEN genau eine Meldung je Zelle.
- [ ] GIVEN Toenung orange ohne Ampelpunkt WHEN geprueft THEN Meldung `Punkt fehlt`.
- [ ] GIVEN Vergleichs-Mail WHEN Windrichtungs-Zeile und Wind-Zelle je Ort stimmen THEN Exit 0; verfaelscht THEN je eine Meldung.
- [ ] GIVEN kein `--windrichtung` WHEN beide Validatoren laufen THEN Ergebnis identisch zu vorher (bestehende Tests #733, #3047, einstellung_gleich).
- [ ] GIVEN ungueltiges JSON WHEN beide CLIs laufen THEN Exit 2 und `FEHLER: --windrichtung ungueltig`.
- [ ] GIVEN Format compact und Soll WHEN Briefing-Validator laeuft THEN Meldung `nur im Format full pruefbar`.
- [ ] GIVEN Segment-ID 0 oder groesser als Tabellenzahl WHEN geprueft THEN Meldung.
- [ ] GIVEN Sendeskript WHEN `windrichtung_soll()` und `compare_windrichtung_soll()` aufgerufen THEN explizite Soll-Stufen je Stunde und Ort.
- [ ] Bestehende Tests `test_issue_733_briefing_mail_validator.py` und `test_einstellung_gleich_mail_validatoren.py` bleiben gruen (Refaktorierung `_soll_ampel`).

## Acceptance Criteria

- **AC-1:** Given eine echt gerenderte Rad-Trip-Briefing-Mail (Format full) und ein Soll mit den erwarteten Stufen je Segment und Stunde / When der Briefing-Validator mit `--windrichtung` laeuft / Then endet er mit Exit 0 ohne Meldung.
  - Test: Rad-Trip rendern, als Mail bauen, `validate_message(windrichtung=Soll)` liefert keine Fehler.

- **AC-2:** Given dieselbe Mail, in der genau eine Wind-Zelle per String-Ersetzung auf eine falsche Toenung gesetzt wurde / When der Briefing-Validator laeuft / Then meldet er genau eine Meldung, die Segment und Stunde der verfaelschten Zelle nennt.
  - Test: Gegenprobe je Zelle einzeln verfaelschen, je Verfaelschung genau eine Meldung.

- **AC-3:** Given eine echt gerenderte Orts-Vergleichs-Mail mit Windrichtungs-Zeile und Wind-Zellen je Ort / When der Vergleichs-Validator mit `--windrichtung` laeuft / Then pruefen sie Windrichtungs-Zeile und Wind-Zelle je Ort gegen das Soll; bei Erfuellung Exit 0, bei verfaelschter Zelle eine Meldung mit Ort und Stunde.
  - Test: Vergleichs-Mail rendern, Soll erfuellt gleich Exit 0, Zelle eines Orts verfaelscht gleich genau eine Meldung.

- **AC-4:** Given eine Mail und kein `--windrichtung` / When beide Validatoren laufen / Then ist ihr Ergebnis (Meldungen und Exit-Code) identisch zum Stand vor dieser Aenderung.
  - Test: Bestehende Validator-Tests (#733, #3047, einstellung_gleich) laufen unveraendert gruen; Aufruf ohne Schalter erzeugt keine Windrichtungs-Meldungen.

- **AC-5:** Given ein ungueltiger Wert fuer `--windrichtung` (kein JSON, kein Objekt, fehlender Schluessel, nicht numerische Segment-ID) / When einer der beiden CLIs aufgerufen wird / Then gibt er `FEHLER: --windrichtung ungueltig: <Grund>` aus und endet mit Exit 2, nicht mit Exit 1 und ohne Traceback.
  - Test: Beide CLIs per Subprozess mit kaputtem JSON, Exit-Code 2 und klare Meldung.

- **AC-6:** Given ein Soll und eine Mail mit `X-GZ-Format` ungleich full / When der Briefing-Validator laeuft / Then meldet er `SOLL: Windrichtung nur im Format full pruefbar` statt still nichts zu pruefen.
  - Test: Compact-Mail mit Soll validieren, Meldung vorhanden.

- **AC-7:** Given ein Soll mit Segment-ID 0 oder groesser als die Zahl der Etappen-Stundentabellen / When der Briefing-Validator laeuft / Then meldet er die ungueltige Segment-ID als Fehler und prueft nicht still eine falsche Tabelle.
  - Test: Soll mit sid 0 und sid N+1, je eine Meldung.

- **AC-8:** Given eine Wind-Zelle mit Toenung ungleich green, aus der per String-Ersetzung der Ampelpunkt entfernt wurde / When der Validator laeuft / Then meldet er laut `Toenung X/Punkt fehlt` (der Renderer setzt bei jeder Toenung einen Punkt) und wertet es nicht als "Punkt = Toenung".
  - Test: Punkt aus einer getoenten Zelle entfernen, genau eine Meldung `Punkt fehlt`.

- **AC-9:** Given die Refaktorierung von `_soll_ampel` in `_etappen_tabellen_attrs` / When die bestehenden Ampel-Pruefungen des Briefing-Validators laufen / Then verhalten sie sich unveraendert und alle bisherigen Validator-Tests bleiben gruen.
  - Test: `tests/tdd/test_issue_733_briefing_mail_validator.py` und Folgetests ohne Aenderung gruen.

- **AC-10:** Given das Sendeskript `send_gate_test_mails.py` / When es die Gate-Mails sendet / Then druckt es eine explizite Zeile "Soll Windrichtung:" mit Soll-Stufen je Stunde (Briefing) und je Ort (Vergleich), die nicht aus der gerenderten Mail abgeleitet sind.
  - Test: `windrichtung_soll()` und `compare_windrichtung_soll()` liefern feste Stufenlisten; Gegenprobe: Aenderung der Renderer-Ausgabe aendert das Soll nicht.

- **AC-11:** Given der Befehl `/e2e-verify` / When er die Validatoren gegen die Staging-Mail aufruft / Then uebergibt er die Soll-Zeile per `--windrichtung` an beide Validatoren (DE und EN).
  - Test: Doku-Pruefung der Aufrufzeilen in `.claude/commands/e2e-verify.md` (`# doc-compliance-test`); Wirkung zusaetzlich in AC-12 nachgewiesen.

- **AC-12:** Given eine echt zugestellte Staging-Mail im Stalwart-Test-Postfach / When beide Validatoren mit `--windrichtung` aus der Soll-Zeile des Sendeskripts laufen / Then enden beide mit Exit 0; eine bewusst verfaelschte Mail ergibt Exit 1.
  - Test: Live-Nachweis in `/e2e-verify` gegen echte Staging-Mail (kein Mock, kein Gmail).

## Definition of Done

- AC-1 bis AC-12 gruen; bestehende Validator-Tests (#733, #3047, einstellung_gleich, #3228) unveraendert gruen.
- Adversary VERIFIED (mindestens 2 Runden, Gate-Code): jede verfaelschte Zelltoenung bzw. jeder entfernte Ampelpunkt wird genau einmal gemeldet.
- Beide Validatoren bestehen mit `--windrichtung` eine echt zugestellte Staging-Gate-Mail (Exit 0); Doku und `e2e-verify.md` ergaenzt.
- PR mit allen 6 CI-Checks gruen gemergt, Prod-Deploy mit Selftest Exit 0.

## Known Limitations

- Segment-Zuordnung ist positionsabhaengig (N-te Etappen-Stundentabelle); ein Soll mit luckenhaften IDs gilt als ungueltig.
- Prueft nur Format full; compact-Mails liefern bei gegebenem Soll eine Meldung.
- Gilt nur fuer den Ampel-Modus (Punkt-Anzeige); ohne Ampelpunkt-Modus gibt es keine Windrichtungs-Faerbung.
- Zwei Falllisten-Tests (`test_testverweise_auffindbar`, `test_template_literal_titel_alle_gefunden`) suchen Frontend-Testdateien und sind in Kopien ohne `frontend/` erwartbar rot; im Worktree erneut laufen lassen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung bestehender Validatoren nach dem `--konfig`-Muster (#3047); keine neue Grundsatzentscheidung.

## Changelog

- 2026-11-21: Initial spec created (Issue #3232, Epic #3222)

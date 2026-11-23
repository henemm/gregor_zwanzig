---
entity_id: rework_3267_i18n_dubletten
type: refactor
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
issue: 3267
epic: 1196
workflow: rework-3267-i18n-doppelte-tests
tags: [tests, aufraeumen, doppelte-zusicherungen, i18n, sprachkatalog]
---

# Doppelte Zusicherungen in den Sprachkatalog-Tests entfernen (#3267)

## Approval

- [ ] Approved

## Purpose

Dieselbe Regel soll an genau einer Stelle geprueft werden. Diese Scheibe (aus #3208 abgespalten, Teil von #1196) prueft die Sprachkatalog-Testdateien (`test_i18n_*`, `*_zweisprachig`; tatsaechlich 23 Dateien mit 214 Testfunktionen) auf doppelte Zusicherungen. Es gibt zehn belegte Dopplungen (F1-F10): zehn Stellen, die identisch oder echte Teilmenge einer bleibenden Zusicherung sind, vor allem Katalog-Paritaet und Allowlist-Leere. Alles nur Aehnliche bleibt. Die Hauptleistung ist der Mutationsnachweis, dass kein Schutz verloren geht.

## Source

- **File:** `docs/context/rework-3267-i18n-doppelte-tests.md` (Abschnitte "Analysis", "Affected Files", "F10", "Risks")
- **Identifier:** Gegenseite A `tests/unit/test_i18n_katalog_paritaet.py::test_echte_kataloge_paritaetisch`; Gegenseite B `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py::test_allowlist_ist_leer`. Vorbild fuer Methode und Aufbau: `docs/specs/modules/rework_3266_fixloop_dubletten.md` (#3266), `rework_3265_fallback_dubletten.md`, `rework_3264_nowcast_dubletten.md`, `rework_3208_doppelte_zusicherungen.md`

Schicht: reine Testsuite-Sanierung. Kein Produktcode in `src/`, `api/`, `internal/`, `scripts/`, `cmd/` oder `frontend/src/` wird veraendert (Mutationen an `src/` und am Katalog sind temporaer und werden aus externer Sicherung wiederhergestellt). Kanaele (E-Mail, Telegram, SMS, Premium-SMS), Mandantentrennung und Trip/Vergleich-Teilung sind nicht betroffen: keine Nutzerdaten bewegt, kein Briefing- oder Alarm-Inhalt veraendert. Die Zweisprachigkeit (ADR-0104) bleibt in jedem Kanal weiter geprueft, weil nur Dopplungen entfallen.

## Estimated Scope

- **LoC:** ca. -50 / +3 (Testcode, Docstrings)
- **Files:** 8 Aenderungen plus Protokoll-Artefakte
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #3208, #3263, #3264, #3265, #3266, `rework_3266_fixloop_dubletten` | spec | Vorgaenger; Kriterium (identisch oder echte Teilmenge) und Mutationsmethode |
| `tests/unit/test_i18n_katalog_paritaet.py` | test | Gegenseite A (`test_echte_kataloge_paritaetisch`, `parity_errors(MESSAGES) == []`) fuer F1, F2, F3, F10; bleibt unveraendert |
| `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` | test | Gegenseite B (`test_allowlist_ist_leer`) fuer F4, F5, F6; Aenderungsort fuer F4 |
| `src/i18n/catalog.py` (`parity_errors`, `MESSAGES_DIR`, `SCHLUESSEL_RE`, `BEREICHE`) | module | Mutationsziel der Katalog-Mutationen; bleibt unveraendert |
| `src/i18n/messages/` (Katalogdateien) | data | Mutationsziel (einseitiger Schluessel, Platzhalter-Abweichung); bleibt unveraendert |
| `tests/fixtures/i18n_python_allowlist.json` | fixture | Mutationsziel (Eintrag einfuegen); bleibt unveraendert |
| `src/output/renderers/alert/render.py` (`render_sms`, Vorgabe `limit=140`) | module | Gegenseite zu F7; bleibt unveraendert |
| `tests/helpers/vergleichs_mail_fixture.py` | test-helper | Gegenseite zu F8/F9; bleibt unveraendert |
| `tests/test_alarm_zweisprachig.py`, `tests/test_vergleichs_mail_zweisprachig.py`, `tests/test_telegram_briefing_zweisprachig.py`, `tests/test_i18n_api_katalog_paritaet.py`, `tests/test_i18n_inbound_katalog_paritaet.py`, `tests/test_i18n_ratsche_narrow_telegram.py`, `tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py` | test | weitere Aenderungsorte F1-F3, F5-F10 |
| `tests/unit/test_paritaet_begruendung_marker.py`, `tests/test_i18n_doku_vollstaendig.py`, `tests/tdd/test_765_backend_hygiene_compliance.py`, `tests/tdd/test_telegram_live_datenwurzel_zuruecksetzen_2813.py` | test | verweisen nur auf Dateinamen; Dateien bleiben alle |
| ADR-0094, ADR-0095, ADR-0104 | decision | Test-Schichten; Kanal-Paritaet; Zweisprachigkeit |

## Implementation Details

### Kriterium

Entfernt wird nur, was identisch ist (gleiche Funktion, gleiche Eingabe, gleiche Erwartung) oder echte Teilmenge einer bleibenden Zusicherung. "Aehnlich" (andere Ebene, andere Werte, anderer Eingangsweg, anderer Kanal, anderer Nutzer) bleibt. Zweifelsregel: ist etwas nur durch die Kombination zweier Tests impliziert, bleibt es.

### Gegenseite A: Katalog-Paritaet (F1, F2, F3, F10)

`parity_errors(MESSAGES) == []` in `tests/unit/test_i18n_katalog_paritaet.py` meldet ueber alle `BEREICHE` fehlende oder kaputte Dateien, einseitige Schluessel, abweichende Platzhalter und die Schluesselform (`SCHLUESSEL_RE`, `key.split(".")[0] == bereich`).

- **F1** `tests/test_i18n_api_katalog_paritaet.py:168-174` `test_api_schluessel_und_platzhalter_paritaet`: ganzer Test entfaellt.
- **F2** `tests/test_i18n_inbound_katalog_paritaet.py:52` und `:54-55`: nur diese Zeilen entfallen; `:53` (`len >= 150`) und `:56` (Werte nicht leer) bleiben, der Testname bleibt.
- **F3** `tests/test_telegram_briefing_zweisprachig.py:235-236` (`set(de) == set(en)`, Praefix `telegram.`): nur diese Zeilen entfallen (Praefix folgt aus der Formpruefung); `:237-239` bleiben, der Testname bleibt.
- **F10** `tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py:232-236` `test_ac6_katalog_paritaet_de_en`: ganzer Test entfaellt, da woertlich identisch mit Gegenseite A. Die Imports `parity_errors`/`MESSAGES_DIR` werden nur entfernt, wenn sie sonst in der Datei unbenutzt sind.

### Gegenseite B: leere Allowlist (F4, F5, F6)

`test_allowlist_ist_leer` (`:175-177`) prueft `_allowlist() == {}` auf `tests/fixtures/i18n_python_allowlist.json` (fehlt die Datei: `{}`). Alle drei Funde lesen denselben Pfad und sind bei leerer Allowlist zwingend wahr.

- **F4** `test_i18n_keine_hartkodierten_nutzertexte_python.py:166-172` `test_allowlist_hat_keine_toten_eintraege`: ganzer Test entfaellt. Der Helfer `_tote_eintraege` bleibt (er dient `test_ratsche_erkennt_bekannte_faelle`). Der Modul-Docstring Z. 17-21 ("nur sinken") wird an den Endstand angepasst (Allowlist ist leer, `test_allowlist_ist_leer` ist der Waechter). Der Docstring-Verweis in `test_i18n_inbound_katalog_paritaet.py:78` auf den entfernten Test wird angepasst. Die Spec `i18n_p11_api_meldungen_ratsche_2674.md` nennt den Namen historisch und bleibt.
- **F5** `test_i18n_ratsche_narrow_telegram.py:97-101` `test_kein_allowlist_eintrag_fuer_narrow_py`: ganzer Test entfaellt.
- **F6** `test_i18n_inbound_katalog_paritaet.py:66-72` `test_allowlist_traegt_keine_paket_datei`: ganzer Test entfaellt; die dadurch unbenutzte Konstante `PAKET_MODULE` (Z. 33-35) entfaellt mit.

### Weitere Teilmengen (F7, F8, F9)

- **F7** `tests/test_alarm_zweisprachig.py:295`: der Parametrisierungsfall `limit=140` entfaellt, es bleibt `[60, 30]`. Gegenseite `:286-292` `test_ac4_sms_in_jeder_sprache_byte_gleich[fall]` rendert ueber `render_sms(msg)` mit Vorgabe `limit=140` fuer None/de/en; Golden-Gleichheit beider Sprachen plus `len <= 140` impliziert den entfernten Fall. Testname bleibt.
- **F8** `tests/test_vergleichs_mail_zweisprachig.py:326` (SMS Anna == SMS Bernd): entfaellt; Gegenseite `:244` ruft `render_compare_sms` ohne `lang` (`vergleichs_mail_fixture.py:143`), also fuer beide Nutzer identisch. Testname bleibt.
- **F9** `tests/test_vergleichs_mail_zweisprachig.py:307` (`treffer` auf `render_mail("en")`): entfaellt; Gegenseite `:107-108` `test_ac1_kein_deutscher_katalogtext...` prueft `_englisch_alles()` als Obermenge (`sichtbar(html) + text.splitlines()` von `render_mail("en")` mit eingefrorener Zeit plus Telegram-Zeilen). `:305-306` bleiben. Testname bleibt.

### Grenzfaelle und "Geprueft, bleibt"

- **G1** `tests/unit/test_i18n_katalog_paritaet.py:37-42` (alle zehn Bereichsdateien) bleibt: erst `:33` plus `:45` zusammen wuerden es implizieren.
- **G2** `test_telegram_briefing_zweisprachig.py:88-95` bleibt: `:93` ist anderswo nur lueckenhaft belegt, der Rumpftest bliebe uebrig.
- Bleibt ausdruecklich (aehnlich, nicht doppelt): Golden-Vergleiche gegen Katalog-Teilstring-Tests (Schnappschuss gegen Katalogquelle); Zwei-Nutzer-Tests ueber `resolve_user_lang`; alarm `byte_gleich` gegen `ac7` (`lang=None` und de-Golden nur dort); Validator Funktion gegen Prozess (anderer Eingangsweg); gate_testmails de-Basispostfach gegen `byte_gleich` (nur 3 von 4 Pfaden ueberlappen); versand `ac5` gegen `jeder_code` und `ac2` gegen `berichtsart` (andere kwargs bzw. Werte); tagesvergleich `aehnlich[de]` gegen `...deutsch_wie_vorher` (`lang="de"` gegen ohne `lang`); format_datum Locale-Test (andere Prozess-Locale); inbound `test_restbefund_p11_...` (verlangt Existenz der Allowlist-Datei).

### Mutationsnachweis (vorher UND nachher)

Jede Mutation per String-Ersetzung mit externer Sicherungskopie im Scratchpad, danach Wiederherstellung aus der Sicherung, nie `git checkout/stash/reset`. Es laufen nur benannte Testdateien, Kern-Schicht mit `-m "not live"`. Das Protokoll (Mutation, rot vorher mit Nennung der fangenden Tests, rot nachher durch die Gegenseite, wiederhergestellt gruen, Begruendung je bleibendem Paar) steht unter `docs/artifacts/rework-3267-i18n-doppelte-tests/`.

| Mutation | Ziel | Vorher | Nachher |
|---|---|---|---|
| M1 | Katalog: einseitiger Schluessel (api, inbound, telegram) und abweichender Platzhalter in `src/i18n/messages/` | F1, F2, F3, F10 und Gegenseite A rot | Gegenseite A rot |
| M2 | `tests/fixtures/i18n_python_allowlist.json`: ein Eintrag (z. B. Paket-Datei, `narrow.py`) | F4, F5, F6 und Gegenseite B rot | Gegenseite B rot |
| M3 | `render_sms`-Vorgabe `limit=140` in `src/output/renderers/alert/render.py` abweichend (z. B. 141) oder de/en-Abweichung | Fall 140 und `byte_gleich` rot | `byte_gleich[60/30]` oder Golden rot, soweit je Fall erreichbar; sonst im Protokoll benannt |
| M4 | Vergleichs-SMS haengt vom Nutzer ab (Stelle im Protokoll benannt) | F8 und `:244` rot | `:244` rot |
| M5 | `render_mail("en")` enthaelt deutschen Katalogtext | F9 und `ac1` rot | `ac1` rot |

Ist eine Mutation nachher gruen, obwohl sie vorher von einem entfernten Teil gefangen wurde, wird nicht ausgeliefert, sondern der Teil bleibt.

### Nicht im Umfang

- Aenderungen an Gegenseite A und B, an G1/G2 und an allem unter "Geprueft, bleibt"; Loeschen von Testdateien oder Helfern (ausser `PAKET_MODULE` und gegebenenfalls unbenutzten Imports).
- Aenderung an Produktionscode.
- Aenderung an Gate-Konfiguration: keine; kein Schritt braucht eine menschliche Gate-Sperre oder einen Override.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/test_i18n_api_katalog_paritaet.py` | MODIFY | F1: Test entfernen |
| `tests/test_i18n_inbound_katalog_paritaet.py` | MODIFY | F2 Zeilen, F6 Test plus `PAKET_MODULE`, Docstring-Verweis Z. 78 |
| `tests/test_telegram_briefing_zweisprachig.py` | MODIFY | F3: Zeilen 235-236 |
| `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` | MODIFY | F4: Test plus Docstring Z. 17-21 |
| `tests/test_i18n_ratsche_narrow_telegram.py` | MODIFY | F5: Test |
| `tests/test_alarm_zweisprachig.py` | MODIFY | F7: Fall `limit=140` |
| `tests/test_vergleichs_mail_zweisprachig.py` | MODIFY | F8, F9: Zeilen |
| `tests/tdd/test_radar_verschaerfung_kennzeichnung_renderer.py` | MODIFY | F10: Test, ggf. ungenutzte Imports |
| `docs/artifacts/rework-3267-i18n-doppelte-tests/` | CREATE | Mutationsprotokoll M1-M5 vorher/nachher inkl. Paar-Begruendungen |

Nicht geaendert (geprueft): `tests/unit/test_i18n_katalog_paritaet.py`, alle anderen Dateien der Gruppe, `src/` und aller sonstige Produktionscode.

## Expected Behavior

- **Input:** Testbestand mit zehn Dopplungen (F1-F10) in der Sprachkatalog-Testgruppe.
- **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; rund 50 Zeilen weniger; Kern-Schicht der betroffenen Dateien weiter 100 % gruen.
- **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.

## Test Plan

Es entsteht kein neuer Produktionscode. Der RED-Schritt ist der Mutationsnachweis "vorher", der Nachweis "nachher" der GREEN-Beleg. Keine Mock-Tests, keine Dateiinhalt-Checks als Verhaltensnachweis.

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN der Stand vor dem Umbau WHEN M1 bis M5 einzeln angewendet werden THEN sind jeweils die entfernten Teile und ihre Gegenseite rot (Ausgangsprotokoll).
- [ ] Test 2: GIVEN der Stand nach dem Umbau WHEN M1 bis M5 einzeln angewendet werden THEN ist jeweils die Gegenseite rot und nach Wiederherstellung wieder gruen.
- [ ] Test 3: GIVEN die betroffenen Dateien vorher und nachher WHEN `pytest --collect-only -q` laeuft THEN gibt es keine Collect-Fehler, und die Testanzahl sinkt genau um die entfernten Tests (F1, F4, F5, F6, F10 = 5 Tests, F7 = 1 Parametrisierungsfall).
- [ ] Test 4: GIVEN alle betroffenen Dateien, beide Gegenseiten und die Namensverweis-Dateien WHEN sie namentlich mit `-m "not live"` laufen THEN sind alle gruen (`uv run pytest` nie ohne benannte Dateien, #1477).

## Definition of Done

- [ ] F1-F10 entfernt wie beschrieben, Testnamen der Teil-Faelle bleiben (AC-1)
- [ ] Gegenseiten A und B und weitere Gegenseiten unveraendert (AC-2)
- [ ] Mutationsnachweis vorher/nachher fuer M1-M5 (AC-3)
- [ ] G1/G2 und "Geprueft, bleibt" unveraendert (AC-4)
- [ ] Docstring-Anpassungen F4 und Verweis `inbound:78` (AC-5)
- [ ] Betroffene Dateien gruen, alle 6 CI-Checks gruen, Adversary-Verdict VERIFIED, kein Produktionscode geaendert (AC-6)

## Acceptance Criteria

- **AC-1:** Given die Funde F1-F10 sind identisch oder echte Teilmenge einer bleibenden Zusicherung / When der Umbau fertig ist / Then sind F1, F4, F5, F6 und F10 als ganze Tests entfernt (F6 inklusive der dann unbenutzten Konstante `PAKET_MODULE`, F10 mit Import-Entfernung nur wenn sonst unbenutzt), von F2, F3, F7, F8 und F9 nur die genannten Zeilen beziehungsweise der Fall `limit=140`, und die Testnamen dieser Teil-Faelle bleiben unveraendert.
  - Test: `pytest --collect-only -q` auf die betroffenen Dateien zeigt keine Collect-Fehler; die entfernten Namen kommen nicht mehr vor, die Teil-Test-Namen laufen gruen.

- **AC-2:** Given die Gegenseiten `test_echte_kataloge_paritaet` (A) in `tests/unit/test_i18n_katalog_paritaet.py`, `test_allowlist_ist_leer` (B) und die uebrigen genannten Gegenseiten (`byte_gleich`, `:244`, `ac1`) / When der Umbau fertig ist / Then sind diese Tests und ihre Dateien byte-identisch zum Stand davor und laufen gruen.
  - Test: `git diff origin/main` zeigt keine Aenderung an `tests/unit/test_i18n_katalog_paritaet.py`; die Gegenseiten laufen namentlich gruen.

- **AC-3:** Given Verfaelschungen M1-M5 (einseitiger Katalogschluessel, Allowlist-Eintrag, SMS-Limit, nutzerabhaengige Vergleichs-SMS, deutscher Text in englischer Mail) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht angewendet werden / Then wird jede Verfaelschung, die ein entfernter Teil vorher fing, nachher weiterhin von der Gegenseite gefangen, und nach Wiederherstellung aus der Sicherung sind die Dateien wieder gruen.
  - Test: Mutationsprotokoll M1-M5 (rot vorher, rot nachher, wiederhergestellt gruen) unter `docs/artifacts/rework-3267-i18n-doppelte-tests/`.

- **AC-4:** Given die Grenzfaelle G1 (`unit/test_i18n_katalog_paritaet.py:37-42`) und G2 (`test_telegram_briefing_zweisprachig.py:88-95`) sowie alles unter "Geprueft, bleibt" / When der Umbau fertig ist / Then sind diese Tests und Zeilen unveraendert, und das Protokoll begruendet je bleibendem Paar, warum es nur aehnlich und nicht doppelt ist.
  - Test: Diff enthaelt keine Aenderung an G1/G2; die Paar-Begruendungen stehen im Protokoll.

- **AC-5:** Given der Docstring Z. 17-21 in `test_i18n_keine_hartkodierten_nutzertexte_python.py` beschreibt eine sinkende Allowlist und `test_i18n_inbound_katalog_paritaet.py:78` verweist auf den entfernten F4-Test / When der Umbau fertig ist / Then beschreibt der Docstring den Endstand (leere Allowlist, `test_allowlist_ist_leer` als Waechter) und der Verweis nennt keinen entfernten Test mehr, waehrend der Helfer `_tote_eintraege` und `test_ratsche_erkennt_bekannte_faelle` bleiben.
  - Test: `test_ratsche_erkennt_bekannte_faelle` laeuft gruen; kein Docstring nennt einen nicht mehr existierenden Testnamen als Waechter.

- **AC-6:** Given alle betroffenen Testdateien, beide Gegenseiten und die Namensverweis-Dateien / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen, alle 6 CI-Checks des PR sind gruen, alle geaenderten Dateien liegen unter `tests/` oder `docs/`, und der Produktionscode ist byte-identisch zur Sicherung wiederhergestellt.
  - Test: lokaler Lauf der benannten Dateien; `git diff origin/main -- src/` ist leer; `git diff --name-only origin/main` enthaelt keinen Pfad ausserhalb von `tests/` und `docs/`; CI-Lauf des PR mit allen 6 Checks gruen.

## Known Limitations

- Mutationen werden von Hand gesetzt; ein automatischer Mutationslauf ist nicht Teil dieser Scheibe.
- Die Zahl der Testdateien (23) und Testfunktionen (214) weicht von der Issue-Schaetzung (~30) ab; massgeblich ist die Analyse im Kontextdokument.
- Der Mutationsnachweis fuer M3 haengt davon ab, dass sich die Verfaelschung je Fall in `byte_gleich[60/30]` zeigt; reicht sie dort nicht, wird das im Protokoll benannt und F7 bleibt bestehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testbereinigung nach bestehender Test-Politik (ADR-0094) und der in #3207/#3208 verankerten Regel; keine neue Architekturentscheidung, kein neues Gate.

## Changelog

- 2026-11-23: Initial spec created

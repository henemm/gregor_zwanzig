---
entity_id: fix_3217_flaky_thunder_ac3
type: bugfix
created: 2026-11-21
updated: 2026-11-21
status: draft
version: "1.0"
workflow: fix-3217-flaky-thunder-ac3
tags: [dwd, gewitter, test, flaky]
---

# Fix #3217: Flaky Kern-Test DWD-Gewitter AC-3 deterministisch machen

## Approval

- [ ] Approved

## Purpose

Der Kern-Test fuer AC-3 des Gewitterabrufs (Haenger kostet hoechstens den Timeout, kein Retry) faellt auf ausgelasteten CI-Runnern gelegentlich mit "Zelle grau_gsp+5 leer" aus. Der Test soll deterministisch werden, ohne dass seine Zusicherung abgeschwaecht wird.

## Source

- **File:** `tests/tdd/test_dwd_thunder_parallel_fetch.py`
- **Identifier:** `test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt`

Schicht: reiner Testcode im Python-Core-Bereich (`tests/tdd/`); Produktivcode (`src/providers/dwd.py`) bleibt unveraendert. Kein Trip/Vergleich-Pendant, keine Nutzerdaten, kein Kanal-Inhalt betroffen.

## Ursache

Der Test setzt `dwd.THUNDER_REQUEST_TIMEOUT = 0.5`. Die Konstante gilt fuer jeden Gewitter-Einzelabruf, nicht nur fuer den Haenger. Der Test-Server erzeugt pro Anfrage ein frisches Raster (GeoTIFF + bz2), diese Rechenarbeit liegt innerhalb des Socket-Timeouts. Auf einem ausgelasteten Runner braucht eine normale Antwort laenger als 0,5 s, es kommt zum ReadTimeout, kein Retry (gewollt, Spec fix_2554), die Zelle bleibt `None`. Nachgestellt: wird nur die Datei `grau_gsp`+5 serverseitig um 0,6 s verzoegert, scheitert der alte Test mit identischer Meldung. Der Ausfall bei PR #3211 ("Abbruch ohne roten Test") ist ein anderer Mechanismus und nicht Teil dieses Fixes.

## Estimated Scope

- **LoC:** ca. +25/-8
- **Files:** 1 Test-Datei + diese Spec
- **Effort:** low

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_dwd_thunder_parallel_fetch.py | MODIFY | AC-3-Test: Timeout 2,0 s, Haenger 8 s, Dauer-Grenze Timeout + 3 s, Raster vorab erzeugen (neuer Helfer) |
| docs/specs/modules/fix_3217_flaky_thunder_ac3.md | CREATE | diese Spec |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dwd.THUNDER_REQUEST_TIMEOUT` (`src/providers/dwd.py`) | constant | per monkeypatch gesetzter Timeout des Gewitterwegs |
| `_raster`, `_Handler`, `_dwd_server`, `_RASTER_CACHE_BYTES` (Test-Helfer) | test helper | Server-Raster erzeugen und cachen |
| `docs/specs/modules/fix_2554_dwd_gewitterabruf_budget.md` | spec | Original-AC-3, bleibt inhaltlich gueltig |
| httpx, ThreadPool-Fan-out, tenacity | library | Timeout und Retry-Verhalten, unveraendert |

## Implementation Details

1. Timeout im Test 2,0 s statt 0,5 s, Haenger-Dauer 8,0 s statt 4,0 s. Dauer-Grenze `<= 2.0 + 3.0` (5 s, bleibt unter der Haengerdauer von 8 s).
2. Neuer Helfer erzeugt vor dem Abruf die Raster-Bytes aller im Test angefragten (param, lauf, ttt) aus `zeit.laeufe`, `dwd.THUNDER_PARAMS` und den benoetigten ttt und legt sie in `_RASTER_CACHE_BYTES`. Eine normale Antwort enthaelt dann keine Rechenarbeit im Server mehr.
3. Alle Zusicherungen bleiben wie sie sind; die Haenger-Freigabe beim Abbau (`freigabe.set()`) bleibt.
4. Eine injizierbare Uhr ist nicht anwendbar, der Timeout wirkt im Socket (httpx), nicht ueber `time.monotonic`.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN die alte Fassung des Tests und eine normale Datei (`grau_gsp`+5) serverseitig um 0,6 s verzoegert WHEN der Test laeuft THEN ist er ROT mit "Zelle grau_gsp+5 leer" (Nachstellung des Fehlers).
- [ ] Test 2: GIVEN dieselbe Verzoegerung WHEN der neue Test laeuft THEN ist er GRUEN.
- [ ] Test 3: GIVEN der neue Test WHEN er mehrfach hintereinander laeuft THEN ist er jedes Mal gruen.
- [ ] Test 4: Mutations-Gegenprobe (String-Ersetzung mit Sicherungskopie): Retry bei ReadTimeout zulassen, Grund-Timeout 30 s statt `THUNDER_REQUEST_TIMEOUT`, Zelle 0 statt None, jeweils ROT.

## Expected Behavior

- **Input:** Gewitterabruf gegen lokalen Testserver, eine URL haengt 8 s.
- **Output:** Abruf endet nach etwa 2 s, Haenger-Zelle `None`, alle anderen Zellen gefuellt.
- **Side effects:** keine; Test dauert wenige Sekunden laenger.

## Definition of Done

- AC-1 bis AC-5 erfüllt und im Test nachgewiesen.
- Nachstellung (normale Datei um 0,6 s verzögert): alte Fassung rot, neue Fassung grün.
- Neuer Test in mehreren Wiederholungen hintereinander grün.
- Alle drei Mutationen der Gegenprobe machen den Test rot.
- Kein Produktivcode geändert; Zusicherungen des Tests nicht abgeschwächt.

## Acceptance Criteria

- **AC-1:** Given der AC-3-Test fuer den haengenden Gewitter-Download / When er konfiguriert wird / Then nutzt er `THUNDER_REQUEST_TIMEOUT` = 2,0 s und eine Haengerdauer von 8 s, und seine Dauer-Grenze ist Timeout + 3 s (5 s), liegt also unter der Haengerdauer.
  - Test: Abruf gegen den lokalen Server mit haengender URL; ein Gewitterweg ohne wirksamen Timeout (Dauer ca. 8 s) faellt an der Dauer-Grenze durch.

- **AC-2:** Given der Test-Server und die im Test angefragten Kombinationen aus Groesse, Lauf und Zeitschritt / When der Abruf startet / Then sind alle zugehoerigen Raster vorab erzeugt (Cache gefuellt), sodass eine normale Antwort keine Rechenarbeit im Server mehr enthaelt.
  - Test: Eine normale Datei, die serverseitig um 0,6 s verzoegert wird, laesst den neuen Test gruen, waehrend der alte Test mit "Zelle grau_gsp+5 leer" rot wird.

- **AC-3:** Given ein einzelner Download haengt / When der Abruf laeuft / Then wurde die Haenger-URL genau einmal angefragt (kein Retry), die Haenger-Zelle ist `None` (nie 0), alle anderen Zellen sind gefuellt, nach dem Abruf laufen keine Pool-Threads mehr, und der Haenger wird beim Abbau freigegeben.
  - Test: Zusicherungen des bisherigen Tests bleiben wortgleich erhalten und werden gegen den lokalen Server geprueft; keine Abschwaechung.

- **AC-4:** Given die Mutations-Gegenprobe per String-Ersetzung mit externer Sicherungskopie / When Retry bei ReadTimeout zugelassen wird, der Gewitterweg den Grund-Timeout 30 s statt `THUNDER_REQUEST_TIMEOUT` nutzt oder die Zelle bei Timeout 0 statt `None` liefert / Then wird der Test in jedem der drei Faelle rot.
  - Test: Jede der drei Verfaelschungen im Produktivcode einzeln einspielen, Test laufen lassen, Rot beobachten, Original wiederherstellen.

- **AC-5:** Given der neue Test unter simulierter Verzoegerung und in Wiederholung / When eine normale Datei serverseitig um 0,6 s verzoegert wird und der Test mehrfach nacheinander laeuft / Then bleibt er jedes Mal gruen, der alte Test ist unter derselben Verzoegerung rot.
  - Test: Wegwerf-Nachstellung mit verzoegerter Datei gegen alte und neue Fassung; anschliessend mehrere Wiederholungen des neuen Tests.

## Known Limitations

- Der Test dauert durch den groesseren Timeout wenige Sekunden laenger.
- Reale CPU-Last auf dem Produktionshost wird bewusst nicht erzeugt; die Nachstellung geschieht per Server-Verzoegerung.
- Der Ausfall bei PR #3211 ("Abbruch ohne roten Test") ist nicht abgedeckt; taucht er wieder auf, eigenes Issue.
- `tests/test_befehl_antwortzeit.py` patcht den Timeout ebenfalls, liegt ausserhalb des Scopes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Test-Stabilisierung, keine Entscheidungsflaeche (Kanaele, Provider, Datenmodell, Auth, Deploy) beruehrt; Produktverhalten unveraendert.

## Changelog

- 2026-11-21: Initial spec created

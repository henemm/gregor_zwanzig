---
spec_file: docs/specs/modules/fix_1755_offline_volllauf.md
spec_sha256: 1bf872d6abd099081798d05cb6794d0521166e09d35903a21a7f57d5672d7ab9
spec_frozen_sha256: 40da0f6ceb38c01cc26c9af39e29635d593b6390f7cec5690d32098af98c7025
---

# PO-Briefing: fix-1755-offline-volllauf

- **Spec:** docs/specs/modules/fix_1755_offline_volllauf.md
- **Issue:** #1755
- **Erstellt:** 2026-11-08

## Was gebaut wird

Ein voller Testlauf ohne Internet wird nutzbar, ohne dass Tests versehentlich Produktion oder Staging auf diesem Rechner erreichen können.

## Definition of Done

Ein Volllauf mit dem neuen Aufruf zeigt keine Netz-Fehlalarme mehr, externe Adressen und fremde lokale Dienste bleiben gesperrt, und die Anleitung nennt den neuen Aufruf.

## Wie geprüft wird

Automatische Tests belegen Sperre und Freigabe-Regeln; der 42-Minuten-Volllauf wird einmal gemessen, Verbindungen aus Kindprozessen wie curl sind nicht abgedeckt.

## Kritische Anmerkungen

- Abweichung vom Issue: eigener Schutz statt einfacher Loopback-Freigabe, weil Produktion lokal lauscht; Begründung nachvollziehbar, Gegenprobe ist enthalten.
- Die zwei Issue-Tests werden nicht pauschal markiert, sondern gemessen; zusätzlich werden drei andere Testdateien ausgeschlossen, die Produktion ansprachen.
- Verbleibende echte Rote werden nicht repariert, sondern an die Sammelliste #1199 übergeben.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

## Hinweise aus Phase 5 (TDD RED) für den Developer

- RED-Tests: `tests/tdd/test_loopback_port_guard_offline_lauf.py` (AC-1 bis AC-4, AC-6), `tests/tdd/test_broad_test_run_gate_offline_form.py` (AC-5).
- Die Unterprozess-Tests laden das Plugin per `-p _loopback_port_guard` mit `tests/` auf dem PYTHONPATH; das Modul muss also unter genau diesem Namen importierbar sein. Zusätzlich muss `tests/conftest.py` es laden (`test_ac4_option_ueber_projekt_conftest_geladen`).
- **Fixture-Setup ist abgedeckt:** `test_fremder_port_aus_fixture_setup` verbindet im Setup einer Session- und einer Function-Fixture. Ein Wächter, der sich erst per `trylast` NACH pytest-socket in `pytest_runtest_setup` einhängt, sieht diese Verbindungen nicht. Der Wächter muss vor dem Fixture-Setup greifen.
- **Fixture-Teardown in Phase 6 messen:** pytest-socket hebt seine Sperre in `pytest_runtest_teardown` auf, vermutlich vor dem Abbau der Fixtures. Entweder deckt der Wächter den Abbau mit ab, oder es steht ausdrücklich in den Known Limitations der Spec.
- **Gate:** blockiert werden müssen auch `--allow-hosts 8.8.8.8` (mit Leerzeichen), doppeltes `--allow-hosts` (argparse nimmt den letzten Wert), `-pno:socket` (zusammengeschrieben) und jedes `PYTEST_ADDOPTS` im Kommando (Präfix, `env`, `export`).
- Kein bestehender Gate-Test erwartet `--disable-socket` allein als frei (geprüft per grep), es gibt also keinen Alt-Test anzupassen.
- `127.0.0.2` per `connect` blockt schon pytest-socket selbst; nur die `connect_ex`-Variante belegt dort den neuen Wächter.

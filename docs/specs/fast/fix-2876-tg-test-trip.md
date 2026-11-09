# Mini-Spec: fix-2876-tg-test-trip

Issue: #2876 (Refs #1196)

## Was ändert sich
- `test_ac4_live_delivery_and_cleanup` in `tests/tdd/test_issue_686_telegram_functional_live.py`
  ruft vor der Befehlsschleife selbst `ensure_test_user_with_active_trip(chat_id=chat_id)` auf,
  genau wie `test_ac3` (Zeile ~194).
- Damit legt der Test seinen Trip mit Etappen relativ zu heute (gestern bis übermorgen)
  selbst an, statt sich auf den vom Reset aus #2813 wiederhergestellten Altstand zu verlassen.

## Was darf sich nicht ändern
- Kein Produktcode, keine Änderung an `_telegram_live_fixture.py`.
- Der Test bleibt ein echter Live-Test ohne Mocks (sieben Befehle, Zustellung + deleteMessage).
- Der Reset aus #2813 (Wiederherstellen von `data/users/tg-live-e2e` nach jedem Test) bleibt unverändert.
- Der Staging-Schutz in `ensure_test_user_with_active_trip` (RuntimeError außerhalb Staging) greift weiter.

## Acceptance Criteria
- **AC-1:** Given der gesicherte Stand von `tg-live-e2e` enthält nur einen Trip ohne Etappe für heute, When `test_ac4_live_delivery_and_cleanup` läuft, Then legt er vorher selbst einen Trip mit Etappen für heute und morgen an und scheitert nicht mehr mit „No segments for trip“.
- **AC-2:** Given der Testlauf auf Staging, When `test_ac4` und die übrigen Telegram-Live-Tests laufen, Then sind alle grün, unabhängig vom Kalenderdatum.

## Manuelle Test-Schritte
1. Auf Staging den Trip von `tg-live-e2e` auf ein veraltetes Datum setzen (bzw. Stand ab 12.11. abwarten).
2. `uv run pytest tests/tdd/test_issue_686_telegram_functional_live.py` auf Staging laufen lassen.
3. `test_ac4` ist grün.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Nachweis rot→grün: Test-User mit veraltetem Trip (Etappen in der Vergangenheit) vorbereiten,
      `test_ac4` vorher rot („No segments“), nach dem Fix grün.

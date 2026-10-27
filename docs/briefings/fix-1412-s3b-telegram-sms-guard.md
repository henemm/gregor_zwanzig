---
spec_file: docs/specs/modules/fix_1412_s3b_telegram_sms_ausgang.md
spec_sha256: 4f26dbdafff10990393dd0ebc7b825ef1c1effe47cc7cde2d795bfb0a3ef85cb
---

# PO-Briefing: fix-1412-s3b-telegram-sms-guard

- **Spec:** docs/specs/modules/fix_1412_s3b_telegram_sms_ausgang.md
- **Issue:** #1412
- **Erstellt:** 2026-10-06

## Was gebaut wird

Telegram-Nachrichten laufen künftig über einen einzigen geprüften Ausgang, und ein Wächter-Test meldet jeden neuen Sendeweg daran vorbei.

## Definition of Done

Im Test-Modus wird jeder Telegram-Sendeversuch mit falscher Konfiguration blockiert, ohne dass etwas das Netz erreicht; bestehende Schutztests bleiben unverändert grün.

## Wie geprüft wird

Offline-Tests lösen echte Sendeversuche gegen eine Attrappe aus; auf Staging gibt es nur einen Smoke-Test, keinen Blockier-Beweis.

## Kritische Anmerkungen

- Ihr Entscheid vom 29.07. (produktiv wirksame Empfängerprüfung für Telegram und SMS) wird hier nicht erfüllt; Produktion bleibt bis S4 ungeschützt.
- SMS-Prüfungen wandern nicht in den gemeinsamen Ausgang, nur der Versand; das Ticket wollte den Schutz im gemeinsamen Pfad.
- Zwei Messpunkte (Fehlerreihenfolge, Telegram-Befehlsabfrage-Tests) sind offen; die Fertig-Kriterien könnten sich noch verschieben.

## Freigabe-Frage

Geben Sie diese reine Umbau-Scheibe frei, obwohl der produktive Empfängerschutz für Telegram und SMS erst mit S4 kommt?

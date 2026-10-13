---
spec_file: docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md
spec_sha256: 7f07add7cdd4be51cad7fc70405e11f10a619ec2085a0b53a46b8b86fbdbce48
---

# PO-Briefing: feat-1412-s4a-empfaengervertrag-telegram

- **Spec:** docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md
- **Issue:** #1412
- **Erstellt:** 2026-10-13

## Was gebaut wird

Telegram-Nachrichten gehen nur noch an den eigenen, belegten Chat des jeweiligen Nutzers; fremde oder unbelegte Empfänger werden blockiert.

## Definition of Done

Briefings, Befehlsantworten und der Knopf „Telegram testen“ erreichen den richtigen Chat des Nutzers; ohne hinterlegten Chat erscheint eine Fehlermeldung.

## Wie geprüft wird

Automatische Tests mit abgefangenem Versand belegen alle 13 Kriterien; auf Staging lässt sich der Blockschutz nicht beweisen, dort nur „nichts verstummt“.

## Kritische Anmerkungen

- Bis zur späteren Scheibe S5 kann das Profilfeld per Freitext gesetzt werden; der Schutz ist deshalb noch nicht lückenlos.
- Zusatz: Test-Knopf wird repariert; zudem fehlt der im Konzept geplante Betreiber-Zweck bewusst.
- Übersehene Versandstelle würde produktiv verstummen; Risiko mittel-hoch.

## Freigabe-Frage

Freigeben, dass Telegram nur noch an belegte Chats sendet, inklusive Reparatur des Test-Knopfs?

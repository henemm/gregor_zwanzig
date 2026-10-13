# Mini-Spec: fix-2455-nachpruefung

Issue #2455 (Telegram-Kurzform folgt der SMS-Auswahl, PO-Entscheidung 09.10.). Die Lieferung steht seit PR #2552 auf `main`.
Dieser Workflow schließt drei offene Prüfpunkte aus der verworfenen lokalen Validierung. Kein Renderer-Umbau.

## Was ändert sich
- Test (Kern, deterministisch): Alarmpfad Trip und Ortsvergleich — bei `telegram_style=kurzform` ist der Telegram-Text der SMS-Text und bleibt gleich, wenn nur die Telegram-Auswahl geändert wird. Hintergrund: Alarm-Texte lesen keine Kanal-Auswahl (kein Code dafür), die Zusicherung wird als Wächter festgeschrieben; er wird nicht rot durch eine Auswahl-Mutation.
- Mutations-Gegenprobe auf dem `main`-Stand am **Briefing-Pfad** (dort wird die Auswahl gelesen; Wächter `test_telegram_kurzform_ignoriert_telegram_auswahl.py`): Kurzform liest Telegram- statt SMS-Auswahl, per String-Ersetzung mit externer Sicherungskopie, Ergebnis in `docs/artifacts/fix-2455-nachpruefung/`.
- Prüfung: Ratschen-Tests (`context_herkunft_zweige_eingefroren`, `ac2_endbilanz_deckt_alle_47_ab`) und Gesamt-Frontend-Suite auf `main` grün. Nur falls rot: nachziehen.

## Was darf sich nicht ändern
- Produktivcode (`src/`, `frontend/src/`) bleibt unverändert, es sei denn die Mutation deckt einen echten Defekt auf — dann Abbruch und Rückfrage (Wechsel auf vollen Prozess).
- Kurzform = SMS-Auswahl 1:1; `rich` nutzt weiter die Telegram-Auswahl.

## Acceptance Criteria
**AC-1:** Given ein Trip mit `telegram_style=kurzform` und abweichender Telegram-Auswahl, When ein Alarm versendet wird, Then ist der Telegram-Text identisch zum SMS-Text und ändert sich nicht, wenn nur die Telegram-Auswahl geändert wird.
**AC-2:** Given ein Ortsvergleich mit `telegram_style=kurzform` und abweichender Telegram-Auswahl, When ein Alarm versendet wird, Then gilt dasselbe wie in AC-1.
**AC-3:** Given der Briefing-Pfad liest probeweise die Telegram- statt der SMS-Auswahl, When die Tests laufen, Then wird mindestens ein Test aus `test_telegram_kurzform_ignoriert_telegram_auswahl.py` rot (Mutation gefangen, Test-Name im Artefakt benannt).
**AC-4:** Given der aktuelle `main`-Stand, When Ratschen-Tests und Frontend-Suite laufen, Then sind sie grün.

## Manuelle Test-Schritte
1. `uv run pytest <benannte Testdateien>` grün.
2. Mutation per String-Ersetzung, Test rot, Original aus externer Kopie zurück, erneut grün.

## Inline-Test
- [ ] Alarm Trip abweichende Auswahl
- [ ] Alarm Ortsvergleich abweichende Auswahl

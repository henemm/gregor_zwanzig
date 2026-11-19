---
spec_file: docs/specs/modules/feat_3153_name_orte_ausliefern.md
spec_sha256: 597016da0023e560b8c073ffbcbdc32556e761b95488ef158bde6bde8c52022a
spec_frozen_sha256: 5353b54c93e89395c83d3984be5411f27e1b90e8387484ffc8a8eecb96f5d1c0
---

# PO-Briefing: feat-3153-name-orte

- **Spec:** docs/specs/modules/feat_3153_name_orte_ausliefern.md
- **Issue:** #3153
- **Erstellt:** 2026-11-19

## Was gebaut wird

Mail, Telegram, SMS und Befehlsantworten nennen Orte-Abos überall „Orte“, und Abos mit einem Ort lesen sich korrekt.

## Definition of Done

Zugestellte Mails, Telegram und SMS sagen nie „Vergleich“ oder „1 Orte“, die Befehlsantworten sagen „Orte-Abo“, und alles läuft live auf Produktion.

## Wie geprüft wird

Automatische Tests und vier echt zugestellte Test-Mails (ein und drei Orte, Deutsch und Englisch) belegen es; die Oberfläche ist nicht Teil davon.

## Kritische Anmerkungen

- Neues Wort „Orte-Abo“ in Befehlsantworten ist keine ältere PO-Entscheidung; es wird erst bei der späteren Abnahme gezeigt.
- Zuschnitt „Oberfläche bleibt bei #2798“ steht tatsächlich in der freigegebenen Epic-Spec (Teil B Nr. 16).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

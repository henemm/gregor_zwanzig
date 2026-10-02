---
spec_file: docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md
spec_sha256: 5ae5536c933ab67a97846e6f28a1a86e617e1a48ef6a6a396444a68e57b41537
---

# PO-Briefing: fix-2229-premium-sms-kanallisten

- **Spec:** docs/specs/bugfix/fix_2229_premium_sms_kanallisten.md
- **Issue:** #2229
- **Erstellt:** 2026-10-01

## Was gebaut wird

Ortsvergleich nennt Premium-SMS als vierten Kanal in Kachel, Übersicht und „Jetzt senden“-Dialog; Vorschau erklärt, dass sie den SMS-Text sendet.

## Definition of Done

Bei eingeschalteter Premium-SMS steht sie auf Kachel und Übersicht, im Sendedialog nur wenn zustellbar, und die Vorschau zeigt den Hinweis.

## Wie geprüft wird

Automatische Tests prüfen Anzeigetexte und eine Quelltext-Suche gegen neue Dreierlisten; der Vorschau-Hinweis im echten Zusammenspiel wird nur manuell auf Staging geprüft.

## Kritische Anmerkungen

- Kachel zeigt Premium-SMS auch bei gesperrtem Konto, der Sendedialog nicht — bewusst, kann aber verwirren.
- Verdrahtung des Vorschau-Hinweises hat keinen automatischen Test; ein Fehler fiele erst auf Staging auf.
- Quelltext-Suche erkennt nur exakt geschriebene Dreierlisten; andere Schreibweisen rutschen durch.

## Freigabe-Frage

Soll Premium-SMS im Ortsvergleich angezeigt werden, wenn eingeschaltet, im Sendedialog aber nur, wenn sie zustellbar ist?

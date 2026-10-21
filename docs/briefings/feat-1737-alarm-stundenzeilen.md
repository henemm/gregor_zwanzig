---
spec_file: docs/specs/modules/feat_1737_alarm_stundenzeilen.md
spec_sha256: 15a6fcba1ed70400cb53bcf0e5151cb100d9ab3b9767ecad583f40f379e8d4ac
spec_frozen_sha256: c336866d5b203d66f00c72fcda0e36c97e07ad5c54f69fda73b1bb962a11b65b
---

# PO-Briefing: feat-1737-alarm-stundenzeilen

- **Spec:** docs/specs/modules/feat_1737_alarm_stundenzeilen.md
- **Issue:** #1737
- **Erstellt:** 2026-10-21

## Was gebaut wird

Abweichungsalarme zeigen für Trips und Ortsvergleiche je betroffener Stunde Uhrzeit sowie alten und neuen Wert, in allen vier Kanälen.

## Definition of Done

Eine echte Alarm-Mail zeigt unter jedem Ereignis Stundenzeilen mit Uhrzeit und alt → neu; SMS nennt die Zeitspanne, Vorschau und Versand stimmen überein.

## Wie geprüft wird

Automatische Tests mit aufgezeichneten Wetterdaten prüfen alle Kanäle und Nutzertrennung; echte Zustellung wird erst auf Staging geprüft.

## Kritische Anmerkungen

- „6 stärkste Stunden“ ist nirgends messbar definiert; Auswahl bei langen Ereignissen bleibt Ermessen.
- Vorschau: Kopfzeile zeigt Regelwerte, Stundenzeilen echte Daten; ohne Anker fehlen sie, Vorschau wirkt leer.
- Ortsvergleich zeigt Stundenwerte nur roh (PO-Entscheid), nie als Punkte.

## Freigabe-Frage

Soll die Stundenansicht in allen vier Kanälen so gebaut werden, mit Ortsvergleich nur roh?

---
spec_file: docs/specs/modules/fix_2931_daywindowcard_rueckbau.md
spec_sha256: 76178756df4bf32ac091964e5f84b694e8a94dd7edffda7a3ad33b511e83196f
spec_frozen_sha256: abd25dc72aa63c8b6b96d3cb7cdb574ab314f05422b9c91f6620e9529c79440b
---

# PO-Briefing: fix-2931-daywindowcard-rueckbau

- **Spec:** docs/specs/modules/fix_2931_daywindowcard_rueckbau.md
- **Issue:** #2931
- **Erstellt:** 2026-11-15

## Was gebaut wird

Der ungenutzte alte Tagesfenster-Baustein wird entfernt; für Nutzer ändert sich nichts sichtbar.

## Definition of Done

Alte Tagesfenster-Karte ist gelöscht, Tagesfenster speichert weiter über die zwei Uhrzeitfelder, und Trip und Ortsvergleich sehen auf Staging vorher wie nachher gleich aus.

## Wie geprüft wird

Automatische Tests belegen, dass Abschnitt und Karte fehlen und Speichern erhalten bleibt; der Vorher-nachher-Bildvergleich ist manuell.

## Kritische Anmerkungen

- Ticket verlangt Löschen der ganzen Wetter-Metriken-Ansicht; Spec entfernt nur den toten Teil, Rest folgt in Folge-Ticket 3020.
- Referenzbilder werden bewusst neu erzeugt; Prüfung nur per Diff-Kontrolle.

## Freigabe-Frage

Genügt es, jetzt nur den toten Tagesfenster-Teil zu entfernen und die Wetter-Metriken-Ansicht selbst erst im Folge-Ticket abzubauen?

## Ampel

Ampel: rot

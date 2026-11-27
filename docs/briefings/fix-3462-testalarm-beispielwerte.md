---
spec_file: docs/specs/modules/fix_3462_testalarm_beispielwerte.md
spec_sha256: e30502a99088719a4f91b856616c5655959f85a22138ad3c96717e5d896c8f6c
spec_frozen_sha256: 041df520cf8cf8e68babca19ce9a0386adda6fee2ad3f3d1f19a0e201879d95f
---

# PO-Briefing: fix-3462-testalarm-beispielwerte

- **Spec:** docs/specs/modules/fix_3462_testalarm_beispielwerte.md
- **Issue:** #3462
- **Erstellt:** 2026-11-27

## Was gebaut wird

Der Test-Alarm zeigt Beispielwerte, die die Schwelle sichtbar überschreiten, und jede Wettergröße erscheint pro Block nur einmal.

## Definition of Done

In zugestellten Test-Alarm-Mails (Trip und Ortsvergleich, Deutsch und Englisch) steht kein „unter deiner Alarm-Schwelle“ und keine Wettergröße doppelt.

## Wie geprüft wird

Automatische Tests prüfen alle vier Kanäle auf Deutsch und Englisch; echt zugestellte Staging-Mails bestätigen es. Echte Alarme bleiben unberührt.

## Kritische Anmerkungen

- Rückfall-Beispiel ändert sich von 40→60 auf 40→100 km/h (Böen); sichtbar anders, vom Ticket gewollt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

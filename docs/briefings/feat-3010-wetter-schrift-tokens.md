---
spec_file: docs/specs/modules/feat_3010_wetter_schrift_tokens.md
spec_sha256: 660bea720a49117da19540b244af29e40d6aaf6e6565b29b1cf69a90dd9cf947
spec_frozen_sha256: 915629326e679a21810d261daa1fc34b866f2a6a5d63dff6c921d1bac5d7896f
---

# PO-Briefing: feat-3010-wetter-schrift-tokens

- **Spec:** docs/specs/modules/feat_3010_wetter_schrift_tokens.md
- **Issue:** #3010
- **Erstellt:** 2026-11-19

## Was gebaut wird

Schriftgrößen im Wetter-Reiter und in Tabellen kommen aus richtigen Schrift-Vorgaben, sichtbar bleibt alles unverändert.

## Definition of Done

Alle neun Stellen sind umgestellt, die Schriftgrößen messen vorher wie nachher gleich, und eine automatische Prüfung schlägt bei Rückfall an.

## Wie geprüft wird

Automatische Tests belegen Schriftgrößen und Rückfall-Wächter; der Bildvergleich gegen Staging ist nur manuell bewertbar, nicht in der Automatik.

## Kritische Anmerkungen

- Zwei bekannte Abweichungen vom Mockup (11,5 und 10 Pixel) bleiben bewusst bestehen; das Ticket-Bild verlangt evtl. Mockup-Gleichheit.
- Ursprungsticket wurde nur über die Kontext-Zusammenfassung geprüft, nicht im Volltext.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

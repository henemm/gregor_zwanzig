---
spec_file: docs/specs/modules/fix_2400_dark_mode_vollstaendig.md
spec_sha256: 8563cee2e956aaa20d0b28838dfcf1ac183e2002bc0a7b9bc26895dfd8dae82b
spec_frozen_sha256: c9beb831ed1120547d0a7c1ff731ef493e11dd8b81ce63cc2f45453f4b42b8dc
---

# PO-Briefing: fix-2400-darkmode-ink3

- **Spec:** docs/specs/modules/fix_2400_dark_mode_vollstaendig.md
- **Issue:** #2400
- **Erstellt:** 2026-11-09

## Was gebaut wird

Der Dunkelmodus wird vollständig: alle Seiten dunkel, Text überall gut lesbar, kein heller Blitz beim Laden.

## Definition of Done

Im Dunkelmodus ist auf keiner Seite Text schwer lesbar, keine weiße Karte sichtbar, und die Wahl bleibt nach Neuladen erhalten.

## Wie geprüft wird

Rechentests prüfen alle Farbpaare, ein Durchlauf auf Staging misst jede Seite an Desktop und Handy; Kartenkacheln und Mails bleiben ungeprüft.

## Kritische Anmerkungen

- Im Hellmodus werden orange Flächen mit weißer Schrift sichtbar dunkler (braun); bewusste Abweichung von der Analyse.
- Orangefarbener Text bleibt im Hellmodus knapp unter der Kontrastgrenze; Anhebung ist ein eigenes Ticket.
- Kartenkacheln bleiben im Dunkelmodus hell.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

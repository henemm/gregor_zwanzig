---
spec_file: docs/specs/modules/feat_2792_s1_profil_ampel.md
spec_sha256: c026dd8d6ce3dbc0852681c93ef493d511d883ecf51ef328999f30f38d949c21
spec_frozen_sha256: 3de26780575857b76ff97ee2e939f941019971ade85d2260e46a82b139b5808f
---

# PO-Briefing: feat-2792-s1c2-migration

- **Spec:** docs/specs/modules/feat_2792_s1_profil_ampel.md
- **Issue:** #2792
- **Erstellt:** 2026-11-05

## Was gebaut wird

Bestehende Wertebereiche der Orts-Vergleiche werden vollständig in die neue Profil-Ampel übernommen, damit nach dem Umschalten keine Grenzen fehlen.

## Definition of Done

Der Nachlauf meldet auf Staging und Prod beim zweiten Durchgang „nichts zu tun“, und jeder Vergleichs-Wertebereich steht als Ampel-Grenze oder begründet als nicht übernehmbar im Bericht.

## Wie geprüft wird

Automatische Tests mit zwei Nutzern prüfen Übernahme, Wiederholbarkeit und Schlüssel-Vollständigkeit; der Prod-Probelauf ist manuelle Vorbedingung, kein Test.

## Kritische Anmerkungen

- Abweichung von der Vorversion: falsche Schlüsselnamen (Windchill) korrigiert, sieben fehlende Schlüssel ergänzt; sonst wäre die Übernahme teils wirkungslos geblieben.
- Gewitter und CAPE werden nicht übernommen; ob deren Markierung heute sichtbar färbt, ist noch ungeprüft.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

---
spec_file: docs/specs/modules/feat_3203_metrikzeilen_mockup.md
spec_sha256: 23d604f39f1f0f3ec3f5d881e27d986a6af1f53013205e0e35f3fbba1a17aed5
spec_frozen_sha256: 98b2ac3ff13e3d7c00f4c29c8a9e68476439514b4fcb8380c90cb42ecf34e14c
---

# PO-Briefing: feat-3203-metrikzeilen-mockup

- **Spec:** docs/specs/modules/feat_3203_metrikzeilen_mockup.md
- **Issue:** #3203
- **Erstellt:** 2026-11-21

## Was gebaut wird

Der Abgleich Mockup gegen Reiter Wetter erkennt Skala, Gewitter-Stufen und Grünbereich als sichtbar; das Mockup übernimmt den Vorboten-Satz.

## Definition of Done

Der Staging-Abgleich aller Reiter in Deutsch und Englisch meldet keine Abweichung mehr für dieses Ticket, und keine neuen Abweichungen entstehen.

## Wie geprüft wird

Automatische Tests belegen die neue Sichtbarkeitsregel und den Screenreader-Schutz; Vorher-nachher-Abgleich auf Staging, die Bildprüfung bleibt manuell.

## Kritische Anmerkungen

- Das Ticket verlangte Anzeige-Angleichung; die Spec korrigiert stattdessen das Messwerkzeug, die Seite selbst bleibt unverändert (Tech-Lead-Entscheidung).
- „:00“ neben der Uhrzeit bleibt bewusst abweichend vom Mockup (Ausnahme laut früherer Stundenraster-Spec).
- Die neue Regel kann andere, bisher verdeckte Abweichungen sichtbar machen; dann folgt Nachbesserung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

---
spec_file: docs/specs/modules/fix_2224_warn_journal_rotation.md
spec_sha256: 6bbc98478e3637f1d679754f7aecf2fe4c9d9047e47ac4e9f124572a659de9fb
spec_frozen_sha256: ae2e1af657dc4e2a46ba428238785df9da78c613be43bcde549536ee7077f5c2
---

# PO-Briefing: fix-2224-warn-journal-rotation

- **Spec:** docs/specs/modules/fix_2224_warn_journal_rotation.md
- **Issue:** #2224
- **Erstellt:** 2026-11-09

## Was gebaut wird

Das Protokoll der Warn-Dienst-Abrufe wächst nicht mehr endlos, sondern bleibt auf etwa 16 MB begrenzt.

## Definition of Done

Auf dem Live-System ist die 65-MB-Altdatei archiviert, die aktuelle Datei klein, und der Warn-Ausfall-Monitor meldet danach keinen Fehlalarm.

## Wie geprüft wird

Automatische Tests mit echten Dateien belegen Rotation, parallele Schreiber und Statusabfrage; der Live-Übergang selbst wird nur nach dem Deploy beobachtet.

## Kritische Anmerkungen

- Drift-Zähler zählen künftig nur noch 13 bis 26 Tage statt seit Juli; der Monitor wertet nur den Zeitstempel.
- Gleichartige Protokolle für Wetterdaten (22 MB) und Anreicherung (6 MB) bleiben unbegrenzt; Folge-Ticket #2883.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

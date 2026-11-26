---
spec_file: docs/specs/modules/rework_3383_waisen_s1.md
spec_sha256: f8891e8872909d74039a421f594ead7fcfd3a2e510dd115c4a88f34d44eb7d54
spec_frozen_sha256: 395dd73214a10a1245390228b1ee5a0251a01114d1ac3d278e746bdc137208ce
---

# PO-Briefing: rework-3383-waisen-s1

- **Spec:** docs/specs/modules/rework_3383_waisen_s1.md
- **Issue:** #3383
- **Erstellt:** 2026-11-26

## Was gebaut wird

Ungenutzte Altbausteine der Wetter-Metriken- und Trip-Detail-Ansicht werden samt zugehöriger Tests und Zahlenvorgaben gelöscht; Nutzer sehen keine Änderung.

## Definition of Done

Die 14 Dateien sind weg, Prüfungen, Aufbau der Anwendung und Typprüfung laufen grün, und die Seiten sehen unverändert aus.

## Wie geprüft wird

Ein Wächter über alle Verknüpfungen und ein Löschnachweis belegen die Entfernung; Bildschirmverhalten wird nur indirekt über Suite, Build und Vergleichsbilder nachgewiesen.

## Kritische Anmerkungen

- Ticket nennt 15 Dateien, die Spec löscht 14; die Ticket-Aufzählung selbst enthält ebenfalls nur 14 (Zählfehler).
- Zusätzlich zum Ticket: Wächter schlägt bei einer ungenutzten Schreibweise laut Alarm; klein, aber nicht verlangt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

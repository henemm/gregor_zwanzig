---
spec_file: docs/specs/modules/rework_3425_compare_bausteine.md
spec_sha256: d7b3d5c308338561fdb948737371f1faf39adab10e39a0dfa8f19243ea589328
spec_frozen_sha256: 357409edcce6fb77981550e5c3313fca5eda864b961ac7236ac5cc21cd0082db
---

# PO-Briefing: rework-3425-compare-bausteine

- **Spec:** docs/specs/modules/rework_3425_compare_bausteine.md
- **Issue:** #3425
- **Erstellt:** 2026-11-26

## Was gebaut wird

Stundenwerte, Stundenüberschrift und Legenden-Regel der Vergleichsmail kommen für Text- und HTML-Fassung aus je einer gemeinsamen Quelle.

## Definition of Done

Beide Mail-Fassungen zeigen gleiche Stundenwerte und Legende; ohne Stundendaten erscheint auch im HTML keine leere Überschrift "Stundenverlauf"; alle Tests und die Staging-Mail bestehen.

## Wie geprüft wird

Automatische Tests rendern beide Fassungen und vergleichen sie; die bewusst unveränderten Teile sind nur gegen den bisherigen Stand gesichert, nicht gegeneinander.

## Kritische Anmerkungen

- Abschnitte je Ort und Einfach-Form der Übersicht, im Ticket genannt, bleiben bewusst doppelt; das entscheidet die Spec, nicht der PO.
- Zellformate (`213°` gegen `213 °`) sind in Folge-Ticket #3431 ausgelagert und bleiben vorerst unterschiedlich.
- Sichtbare Änderung: HTML-Mail ohne jede Stundendaten verliert die leere Überschrift.

## Freigabe-Frage

Soll das Ticket ohne gemeinsame Orts-Abschnitte und ohne gemeinsame Einfach-Form als erledigt gelten, oder müssen diese zwei Punkte mit hinein?

## Ampel

Ampel: rot

---
spec_file: docs/specs/modules/etappen_strip_sortable_list.md
spec_sha256: 5cee4de62b21bfd04dc5e741cb716002dbd8d123e5cc81b5678ac09e24432eac
---

# PO-Briefing: fix-2288-etappen-dnd

- **Spec:** docs/specs/modules/etappen_strip_sortable_list.md
- **Issue:** #2288
- **Erstellt:** 2026-10-07

## Was gebaut wird

Im Trip-Editor sortieren Sie Etappen am Desktop jetzt wie überall sonst: per Griff, Tastatur oder Fingergeste.

## Definition of Done

Etappen lassen sich per Griff mit Maus, Finger und Tastatur umsortieren, die Reihenfolge wird beim Ablegen gespeichert.

## Wie geprüft wird

Browser-Tests ziehen echte Karten per Maus, Finger und Tastatur; echte Endgeräte werden nicht getestet.

## Kritische Anmerkungen

- Neu: Die Reihenfolge wird beim Ablegen automatisch gespeichert, auch in der mobilen Liste – das hat niemand verlangt.
- Nachbarkarten gleiten beim Ziehen nicht mehr weich, sondern springen um; das ist ein Kompromiss für zuverlässiges Ablegen.
- Per Tastatur wird die Reihenfolge erst beim Ablegen gemeldet, nicht pro Pfeilschritt; Escape verwirft.

## Freigabe-Frage

Sind die drei Abweichungen akzeptabel, sodass die Spec freigegeben werden kann?

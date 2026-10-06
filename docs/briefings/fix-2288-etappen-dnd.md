---
spec_file: docs/specs/modules/etappen_strip_sortable_list.md
spec_sha256: edeb71c3df15d30ab0da5dd3ac2b695545c12e64e0e4261cfb2dc48f25b8ec2b
---

# PO-Briefing: fix-2288-etappen-dnd

- **Spec:** docs/specs/modules/etappen_strip_sortable_list.md
- **Issue:** #2288
- **Erstellt:** 2026-10-06

## Was gebaut wird

Etappen im Trip-Editor werden wie Orte per Griff sortiert, auch per Touch; die alte Sonderlösung entfällt.

## Definition of Done

Etappen lassen sich per Maus, Touch und Tastatur umsortieren, Änderung greift erst beim Ablegen, und keine alte Sortiertechnik bleibt im Code.

## Wie geprüft wird

Browser-Tests spielen Maus-, Touch-, Tastatur- und Randscroll-Gesten durch, ein Wächter verhindert Rückfall; die Doku-Änderung wird nur durchgesehen.

## Kritische Anmerkungen

- Randscrollen beim Ziehen ist ungewiss; scheitert es, wächst der Aufwand dieses Tickets.
- Gelöschte ungenutzte Gruppen-Komponente war nicht gefordert; vier Tests werden dafür angepasst (von Ihnen entschieden).
- Doku-Änderung (Entscheidungsdatei) hat keinen eigenen Test, nur Durchsicht.

## Freigabe-Frage

Keine offene Entscheidung — Freigabe der Spec als Ganzes?

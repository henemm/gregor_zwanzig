---
spec_file: docs/specs/modules/feat_3197_tempo_je_etappe.md
spec_sha256: deec3f3432e7694200f94c57436bfb8f17280839c232d01c82030851ea90e9f5
spec_frozen_sha256: 960b812c7675670be9355297bf732ea2be4824ec906ce1c1e356e2739b2e06b8
---

# PO-Briefing: feat-3197-tempo-je-etappe

- **Spec:** docs/specs/modules/feat_3197_tempo_je_etappe.md
- **Issue:** #3197
- **Erstellt:** 2026-11-20

## Was gebaut wird

Jede Etappe zeigt ihre Gehzeit und bekommt über „Tempo ändern“ ein eigenes Gehtempo, das nur sie betrifft.

## Definition of Done

Auf Staging lässt sich bei Etappe 3 das Tempo setzen und zurücknehmen; nur ihre Gehzeit und Wegpunkt-Stunden ändern sich, in allen vier Kanälen.

## Wie geprüft wird

Automatische Tests vergleichen die Rechnung, Speicherung mit zwei Nutzern und alle vier Kanäle; die Optik prüft Staging, nicht ein Test.

## Kritische Anmerkungen

- Zusatz: Beim Wechsel der Fortbewegung (zum Beispiel Rad) werden alle Etappen-Tempos still verworfen, nur mit Hinweis. Niemand hat das verlangt.
- Abweichung: Je Etappe ist nur ein Tempo änderbar, nicht getrennt „flach“ und „Aufstieg“; das folgt aus dem Grundsatzbeschluss zum Tempo.

## Freigabe-Frage

Sollen beim Wechsel der Fortbewegung alle Etappen-Tempos automatisch zurückgesetzt werden, oder sollen sie bestehen bleiben?

## Ampel

Ampel: rot

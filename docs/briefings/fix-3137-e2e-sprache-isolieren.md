---
spec_file: docs/specs/modules/e2e_seriell_haupt_suite.md
spec_sha256: d63e04f50588e232fb85c77d16f474182c7009f21f76efc7e69f602d2e1ec797
spec_frozen_sha256: c6b193c24af57cbe294392b9c4acff6b1193bc96ecb4433d8f410ed3e4197acd
---

# PO-Briefing: fix-3137-e2e-sprache-isolieren

- **Spec:** docs/specs/modules/e2e_seriell_haupt_suite.md
- **Issue:** #3137
- **Erstellt:** 2026-11-20

## Was gebaut wird

Lokale Testläufe laufen immer nacheinander, damit ein Sprachwechsel keinen gleichzeitig laufenden Test stört.

## Definition of Done

Lokal startet die Haupt-Suite mit einem Worker, ein Parallelstart bricht verständlich ab, und der Fall DS-2 bleibt grün.

## Wie geprüft wird

Echte Testläufe mit und ohne Parallelstart belegen das Verhalten; die Doku-Zeile wird nur auf Vorhandensein geprüft, nicht auf Wirkung.

## Kritische Anmerkungen

- Zusatz: Ein Wächter, der Parallelstarts abbricht, wurde nicht verlangt; die ganze Suite läuft seriell, nicht nur Sprach-Tests.
- Lokale Volläufe werden langsamer; Staging-Einzelkonfigurationen mit zwei Workern bleiben bewusst unberührt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

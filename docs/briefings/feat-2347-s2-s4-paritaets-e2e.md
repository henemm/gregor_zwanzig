---
spec_file: docs/specs/modules/feat_2347_s2_paritaets_e2e.md
spec_sha256: b0dc91c7afda80a4ae0499b8224a0872449f7e606152296ef8ac2556d006ad08
spec_frozen_sha256: da2d45d73cb42a7013e2aa777f9731a52b893261d85dc034f2440d51389a5c1d
---

# PO-Briefing: feat-2347-s2-s4-paritaets-e2e

- **Spec:** docs/specs/modules/feat_2347_s2_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-26

## Was gebaut wird

Kopf, Reiterleiste, Listenmenü und Speicheranzeige werden für Trip und Ortsvergleich künftig von denselben automatischen Tests geprüft.

## Definition of Done

Die Liste der noch getrennten Ortsvergleich-Tests sinkt von 48 auf 41, und die fünf neuen Tests laufen dreimal hintereinander grün.

## Wie geprüft wird

Browser-Tests bedienen Trip und Ortsvergleich identisch, auch mit simulierten Serverfehlern; der Sende-Dialog wird nur manuell auf Staging geprüft.

## Kritische Anmerkungen

- Anfrage verlangt eine leere Liste; hier nur 48 auf 41. Drei weitere Etappen folgen, Ticket bleibt offen.
- Die alten Tests liefen nie in der CI; wird ein Trip-Test rot, repariert man dafür Produktcode im selben Ticket.

## Freigabe-Frage

Gibst du diese erste Etappe frei, einschließlich möglicher Produktkorrekturen, falls ein Trip-Test beim Zusammenlegen rot wird?

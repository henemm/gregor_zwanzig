---
spec_file: docs/specs/modules/refactor_2989_compare_default_order_ssot.md
spec_sha256: d44a700ab3bd461a0364b4217b776fef5cd7f9eb838e2c0ddd652c576b551a3c
spec_frozen_sha256: 2de5aa4a9720d3c8de937f0246cd9fe44db6aa93a6f660b10fecba6f09eaaa83
---

# PO-Briefing: refactor-2989-compare-keys-ssot

- **Spec:** docs/specs/modules/refactor_2989_compare_default_order_ssot.md
- **Issue:** #2989
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Standardliste der Wettergrössen im Ortsvergleich kommt künftig aus einer einzigen Quelle statt aus einer handgepflegten Kopie.

## Definition of Done

Ortsvergleiche zeigen und mailen dieselben Wettergrössen in derselben Reihenfolge wie bisher, und die doppelte Liste existiert nicht mehr.

## Wie geprüft wird

Automatische Tests gegen den echten Katalog belegen Menge, Reihenfolge und Speicherschutz; zusätzlich prüft der Mail-Validator auf Staging die zugestellte Vergleichsmail.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

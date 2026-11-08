---
spec_file: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md
spec_sha256: e849afdcb9d79ffeb7de605a8f45a2bccbfdcb0b5d06a811480366ccf28a104f
spec_frozen_sha256: 897434f970a946d1ad5be6810bf0fe8bdf6a5b6bfb0d8af7154b60a2df65d748
---

# PO-Briefing: fix-2009-nowcast-8min-nachmessung

- **Spec:** docs/specs/modules/fix_2009_laufender_regen_vorlauf.md
- **Issue:** #2009
- **Erstellt:** 2026-11-08

## Was gebaut wird

Bei schon laufendem Regen protokolliert Gregor Vorlauf 0 statt „8 Minuten"; der Warntext an Nutzer bleibt unverändert.

## Definition of Done

Alle acht Prüfpunkte sind für Trip und Ortsvergleich erst rot, dann grün nachgewiesen; Staging-Prüfung und Produktiv-Selftest sind bestanden.

## Wie geprüft wird

Simulierte Regenverläufe belegen Vorlauf 0, Doppelmeldungs-Sperre und „läuft bereits" in allen vier Kanälen; echter Regen im Betrieb bleibt unbelegt.

## Kritische Anmerkungen

- Warnungen kommen nicht früher: Die „8" war überwiegend Protokoll-Artefakt, die Anzeige war schon korrekt.
- Bei vier Stunden Regen sind weiterhin zwei Alarme möglich; „genau einer" folgt in #2851 (von dir bereits eingegrenzt).
- Die August-Deutung ist nur ein Indiz, kein Beweis.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

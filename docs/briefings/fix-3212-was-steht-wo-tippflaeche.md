---
spec_file: docs/specs/modules/fix_3212_was_steht_wo_tippflaeche.md
spec_sha256: 3f3c3766be97238da0c0e486d88524b520343ae6574a6c0a3b1ddd0364f6b5e3
spec_frozen_sha256: 980591bb4ef2706787c2754a00a9b7f1ea1e684d64985e61f075864dfa9fa082
---

# PO-Briefing: fix-3212-was-steht-wo-tippflaeche

- **Spec:** docs/specs/modules/fix_3212_was_steht_wo_tippflaeche.md
- **Issue:** #3212
- **Erstellt:** 2026-11-20

## Was gebaut wird

Roh, Einfach und die E-Mail-Format-Knöpfe in „Was steht wo“ lassen sich auf Handy und Desktop sicher antippen.

## Definition of Done

Der Design-Wächter für Tippflächen ist auf Staging für Desktop und Mobil grün, die Knöpfe sehen unverändert nach Mockup aus.

## Wie geprüft wird

Automatische Tests und Staging-Klicktests an Ecken und Mitte der Knöpfe; ob es optisch dem Mockup entspricht, prüft nur der Sichtvergleich.

## Kritische Anmerkungen

- Die unsichtbare Tippfläche ragt etwa 6 Pixel in Nachbarknöpfe; Fehltreffer sind nur an den geprüften Punkten abgesichert.
- Die E-Mail-Format-Segmente wechseln auf die Mockup-Variante; ihr Aussehen kann sich leicht ändern.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

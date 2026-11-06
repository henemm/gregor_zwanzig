---
spec_file: docs/specs/modules/feat_2792_s1_profil_ampel.md
spec_sha256: 66dc858de529a45b1bb8faf8a3fd6bb33c238edaa71201f7fa5b59825dbf0df9
spec_frozen_sha256: d72637533b712056d23538f60665c0695caaaeb5f56d82018c0a575357188d23
---

# PO-Briefing: feat-2792-s1c4-umschalten

- **Spec:** docs/specs/modules/feat_2792_s1_profil_ampel.md
- **Issue:** #2792
- **Erstellt:** 2026-11-06

## Was gebaut wird

E-Mail, Telegram, SMS und Premium-SMS bewerten Wetterwerte gleichzeitig nach der Ampel des jeweiligen Trips oder Vergleichs.

## Definition of Done

Ein Skitouren-Trip und ein Allgemein-Trip mit +9 °C erscheinen in allen vier Kanälen verschieden bewertet; CAPE hat keine Farbe mehr.

## Wie geprüft wird

Tests vergleichen an allen 16 Einstiegen Skitouren gegen Allgemein; echte Staging-Mails prüfen die Validatoren, Farben selbst nur die Renderer-Tests.

## Kritische Anmerkungen

- Auch bei Vorlage Allgemein ändert sich Sichtbares: SMS und Mail nennen Wind erst ab 30 statt 10 km/h.
- Das Vorlagen-Label ersetzt in der Vergleichs-Mail-Kopfzelle „Profil“ den bisherigen Text, ebenfalls für alle Nutzer.
- Auf Prod ändert sich vor allem das Abo „zillertal“ (Wintersport) sichtbar in den Farben.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

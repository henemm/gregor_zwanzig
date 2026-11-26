---
spec_file: docs/specs/modules/feat_3419_elementliste_nachzug.md
spec_sha256: cd101ffcc05f16ee67275148c20e12db88a87f66a34d3aacaacc109f0efc452b
spec_frozen_sha256: a655fd29cf37de29a582a166b90ce624b7af9775acfc5b0f6f983ad6fea37a5b
---

# PO-Briefing: paket-3419-elementliste-nachzug

- **Spec:** docs/specs/modules/feat_3419_elementliste_nachzug.md
- **Issue:** #3419 (mit #3420, #3421, #3422)
- **Erstellt:** 2026-11-26

## Was gebaut wird

Der Abgleich von Soll-Bild und Live-Seite „Was steht wo“ meldet in Deutsch und Englisch keine ungeklärten Abweichungen mehr.

## Definition of Done

Der Abnahme-Lauf auf dem Testsystem zeigt in beiden Sprachen null Abweichungen ohne Besitzer, statt bisher 185 beziehungsweise 173.

## Wie geprüft wird

Automatische Tests belegen die Prüfregeln, Seed-Daten und Soll-Bild; der Abnahme-Lauf auf dem Testsystem belegt das Gesamtergebnis. Die Live-Seite bleibt unberührt.

## Kritische Anmerkungen

- Das Soll-Bild zeigt im Trip künftig „1 Abweichung“ statt „unverändert“ (Bewölkung); Metrik-Auswahl bleibt unverändert, Tech-Lead-Entscheid.
- Der Abgleich erklärt echte Prognosewerte als Beispieltexte nur seitenweise und nur nach Treffer; das lockert die Prüfung bewusst.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

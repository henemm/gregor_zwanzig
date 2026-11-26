---
spec_file: docs/specs/modules/feat_3419_elementliste_nachzug.md
spec_sha256: 5fae9f9cbb87c14af77b723d5dc24a68e5a61bf0d523e193c7caeca7997a4fad
spec_frozen_sha256: 8c6384e357b3860db541f17ae9c40fc72e3227a74a9b8082a7648e7a2de83f80
---

# PO-Briefing: paket-3419-elementliste-nachzug

- **Spec:** docs/specs/modules/feat_3419_elementliste_nachzug.md
- **Issue:** #3419 (Paket #3419–#3422)
- **Erstellt:** 2026-11-26

## Was gebaut wird

Das Soll-Bild und die Abnahme-Prüfung von „Was steht wo“ werden an die ausgelieferten Entscheidungen angepasst; die Live-Seite bleibt unverändert.

## Definition of Done

Der Abnahme-Lauf auf Staging meldet in Deutsch und Englisch null Abweichungen ohne Besitzer, statt bisher 185 bzw. 173.

## Wie geprüft wird

Automatische Tests belegen die Prüfregeln und den Prüfkonto-Seed; das Soll-Bild prüft ein Bildvergleich, nicht nachgewiesen wird die Live-Seite selbst.

## Kritische Anmerkungen

- „Nur morgens/abends“ wird im Soll-Bild nicht abgebildet, weil es im Prüfkonto nie sichtbar ist; bewusst gekürzt.
- Das Soll-Bild zeigt im Trip nun „1 Abweichung“ (Bewölkung) statt die Vorlage zu ändern; Tech-Lead-Entscheid.
- Grenzwerte werden nur als Zahlenmuster geprüft, nicht auf exakte Werte.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

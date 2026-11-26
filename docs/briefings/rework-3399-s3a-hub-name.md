---
spec_file: docs/specs/modules/rework_3399_vorlage_aufloesung.md
spec_sha256: 1c26ea231ebf148d50e3004d616ca96b1db4e8a7364481f0a8492880efb69819
spec_frozen_sha256: 751204a28e0015d9002c7880eba10f5cca00493da93e202ddb5c6b3b0bf99733
---

# PO-Briefing: rework-3399-s3a-hub-name

- **Spec:** docs/specs/modules/rework_3399_vorlage_aufloesung.md
- **Issue:** #3399
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Wetter-Karte in der Übersicht eines Ortsvergleichs zeigt als Titel den vom Server bestimmten Vorlagennamen.

## Definition of Done

Der Kartentitel zeigt die Server-Vorlage, bis zur Antwort und bei Fehler „—", niemals ein geratenes „Allgemein".

## Wie geprüft wird

Automatische Tests vergleichen den Titel mit der echten Server-Auflösung, inklusive Fehlerfall; ein Test im echten Browser gehört nicht zu dieser Lieferung.

## Kritische Anmerkungen

- Ortsvergleiche mit gesetztem Vorlagennamen zeigen künftig ggf. einen anderen Titel als bisher (Server gewinnt, in Spec beschlossen).
- Kurzes „—" beim Öffnen statt sofortigem Namen (dokumentierte Einschränkung).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

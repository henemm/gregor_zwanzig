---
spec_file: docs/specs/modules/saveuser_merge.md
spec_sha256: 62342c7eb6464fdb15679d0b7fa46107152cea64e03f12658d01e404e7c75afe
spec_frozen_sha256: 06e41fe78cd43338f67f994c648deb0078b79cbf30e85e62abeaad60f312c478
---

# PO-Briefing: fix-2687-saveuser-merge

- **Spec:** docs/specs/modules/saveuser_merge.md
- **Issue:** #2687
- **Erstellt:** 2026-11-03

## Was gebaut wird

Beim Speichern eines Kontos gehen zusätzliche, vom Programm nicht gekannte Angaben nicht mehr verloren.

## Definition of Done

Ein Konto mit Zusatzangabe behält sie nach Profiländerung, bewusst geleerte Felder bleiben leer, neue Konten und Konten anderer Nutzer funktionieren unverändert.

## Wie geprüft wird

Automatische Tests prüfen Speichern, Erstanlage, beschädigte Datei und zwei Nutzer; ein Test über das echte Profil-Formular ist nicht vorgesehen.

## Kritische Anmerkungen

- Beschädigte Kontodatei wird überschrieben statt abzubrechen; Konto bleibt speicherbar, Inhalt geht verloren.
- Unbekannte Angaben innerhalb von Passkey-Einträgen bleiben nicht erhalten (Grenze laut Spec).
- Gleichzeitiges Speichern kann weiter Änderungen überschreiben (laut Spec anderes Thema, ADR-0083).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

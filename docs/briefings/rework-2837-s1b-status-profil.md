---
spec_file: docs/specs/modules/rework_2837_s1b_status_profil.md
spec_sha256: bab309c99b1e76a2d1aaf5ce7c0dd6fd5df33956e3c39aa97c160fb5de14f77c
spec_frozen_sha256: 67612bf23579c744d6d0fd324b463be8726408252fd2dadc8ed5b3b879858787
---

# PO-Briefing: rework-2837-s1b-status-profil

- **Spec:** docs/specs/modules/rework_2837_s1b_status_profil.md
- **Issue:** #2837
- **Erstellt:** 2026-11-08

## Was gebaut wird

Trip und Vergleich zeigen dasselbe Status-Schild, und der Trip nennt sein Profil unter dem Titel wie der Vergleich.

## Definition of Done

Auf Staging sehen Trip- und Vergleichs-Kopf im selben Zustand gleich aus, und ein unabhängiger Bildvergleich findet keinen Unterschied außerhalb der erlaubten Liste.

## Wie geprüft wird

Automatische Tests und Bildvergleich auf Staging weisen gleiche Texte, Farben, Kontrast und Profil-Zeile nach; ob es gefällt, beurteilt nur Sie.

## Kritische Anmerkungen

- Optik ändert sich sichtbar: Vergleich-Aktiv nicht mehr orange gefüllt, Pausiert gelb-braun statt grau, "Entwurf" statt "draft"; Sie haben das nicht verlangt.
- Die Gelb-Farbe des umrandeten Schilds wird global geändert (Design-Regel), wirkt auch auf die Demo-Seite.

## Freigabe-Frage

Soll das gemeinsame Schild umrandet sein, mit Vergleich-Aktiv nicht mehr orange gefüllt und Pausiert in dunklem Gelb-Braun?

## Ampel

Ampel: rot

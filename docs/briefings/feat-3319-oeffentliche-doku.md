---
spec_file: docs/specs/modules/oeffentliche_doku_3319.md
spec_sha256: bef79f020a6313e203d23c3d1cae82acc6bd4f61406b6df086bd364b3d9a62de
spec_frozen_sha256: b34752a8fd4a1cb9d39878cc15994d10447680e9286879f4968fe3fed6de996d
---

# PO-Briefing: feat-3319-oeffentliche-doku

- **Spec:** docs/specs/modules/oeffentliche_doku_3319.md
- **Issue:** #3319 (gebündelt mit #3320, Epic #3318)
- **Erstellt:** 2026-11-24

## Was gebaut wird

Startseite nennt alle vier Kanäle und erklärt Free, Standard, Premium; dazu eine öffentliche Funktionsübersicht mit neun Unterseiten und Bildern, Deutsch und Englisch.

## Definition of Done

Ohne Anmeldung sind Startseite, Übersicht und alle neun Unterseiten in beiden Sprachen erreichbar, mit Level-Grenzen, Bildern ohne Personendaten, Navigation und Handy-Lesbarkeit.

## Wie geprüft wird

Automatische Tests prüfen Texte, Zugriffsgrenzen, Level-Zahlen gegen den Code, Bildgrößen, Navigation und Handy-Breite; ob Bilder Personendaten zeigen, prüft zusätzlich eine Sichtkontrolle.

## Kritische Anmerkungen

- Drei Level statt nur Free und Premium; Preise und Bezahlweg fehlen bewusst, Wechsel nur per Antrag.
- Claude-Konnektor, Admin und Design-Seiten werden öffentlich nicht erwähnt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

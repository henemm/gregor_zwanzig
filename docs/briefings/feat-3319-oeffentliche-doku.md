---
spec_file: docs/specs/modules/oeffentliche_doku_3319.md
spec_sha256: 723c4260d857e6ade7d785d3be38ce49ec29d6711c0b1f97546fa2b704a563b8
spec_frozen_sha256: b11d7a6c75babcdeaa18e3f813b60bcf338b69011992d584614cce5c295299ac
---

# PO-Briefing: feat-3319-oeffentliche-doku

- **Spec:** docs/specs/modules/oeffentliche_doku_3319.md
- **Issue:** #3319 (gebündelt mit #3320, Epic #3318)
- **Erstellt:** 2026-11-24

## Was gebaut wird

Startseite nennt alle vier Kanäle und erklärt Free, Standard, Premium; neue öffentliche Funktionsseite auf Deutsch und Englisch mit Bildern.

## Definition of Done

Ohne Anmeldung zeigen Startseite und Funktionsseite in beiden Sprachen vier Kanäle, Level-Grenzen und Bilder ohne Personendaten, auch auf dem Handy lesbar.

## Wie geprüft wird

Automatische Tests prüfen Texte, Zugriffsgrenzen, Level-Zahlen gegen den Code, Bildgrößen und Handy-Breite; Personendaten in Bildern prüft zusätzlich eine Sichtkontrolle.

## Kritische Anmerkungen

- Es gibt drei Level statt nur Free und Premium; Preise und Bezahlweg fehlen bewusst, Wechsel nur per Antrag.
- Claude-Konnektor, Admin und Design-Seiten werden öffentlich nicht erwähnt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

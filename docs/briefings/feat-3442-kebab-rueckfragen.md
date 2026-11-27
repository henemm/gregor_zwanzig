---
spec_file: docs/specs/modules/feat_3442_kebab_rueckfragen.md
spec_sha256: c4220bd8ab1b477f9df171416248be5cf4f33a5840f056902dcf65f230dc04b5
spec_frozen_sha256: 3b424fd1f0177b53dec2786a4371a3400ab5d3b32f0967f14c0cfc8ccf4250d0
---

# PO-Briefing: feat-3442-kebab-rueckfragen

- **Spec:** docs/specs/modules/feat_3442_kebab_rueckfragen.md
- **Issue:** #3442
- **Erstellt:** 2026-11-27

## Was gebaut wird

Im Menü von Trip und Orts-Vergleich fragen Archivieren und Löschen vorher nach; erst die Bestätigung führt sie aus.

## Definition of Done

Beide Aktionen zeigen die Rückfrage in Deutsch und Englisch, Abbrechen ändert nichts, Bestätigen archiviert oder löscht, danach erscheint die passende Meldung.

## Wie geprüft wird

Automatische Tests und ein Durchlauf gegen Staging belegen Ablauf, Texte und Fehlerfälle; reine Optik bleibt Augenschein.

## Kritische Anmerkungen

- Orts-Vergleich bleibt nach dem Archivieren auf der Seite, statt zur Liste zu springen (Verhaltensänderung nach Mockup).
- Reaktivieren verliert seine bisherige Rückfrage und läuft sofort (Mockup-Vorgabe).
- Meldung bei Serverfehler ist ein neuer Text des Tech Leads, nicht PO-Wortlaut.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

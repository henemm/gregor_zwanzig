---
spec_file: docs/specs/modules/i18n_katalog_sprache_3021.md
spec_sha256: 31e4e967ccbf2db10b4ef771ce188f7c14f0f2861f3f953ac399297943c519af
spec_frozen_sha256: 25ab35791fd2903d7765d30276133905909bb93b9bdd9e9d0d75e0cb71c20a01
---

# PO-Briefing: fix-3021-katalog-sprache

- **Spec:** docs/specs/modules/i18n_katalog_sprache_3021.md
- **Issue:** #3021
- **Erstellt:** 2026-11-16

## Was gebaut wird

Englischsprachige Nutzer sehen im Ortsvergleich die Begründung „stündlich nicht wählbar" künftig auf Englisch, deutsche Nutzer unverändert Deutsch.

## Definition of Done

Auf Staging und Produktion zeigt die Begründung bei Sonnenstunden für Englisch-Nutzer englischen, für Deutsch-Nutzer deutschen Text.

## Wie geprüft wird

Automatische Tests und ein Staging-Lauf mit je einem Englisch- und Deutsch-Nutzer belegen Sprache, Zwischenspeicher und Fehlerfall; Live-Umschalten im offenen Editor wird nicht geprüft.

## Kritische Anmerkungen

- Das Ticket nennt den Wertebereiche-Reiter; die Spec korrigiert auf den Stundenverlauf-Block, weil nur dort Servertext erscheint.
- Metrik-Namen und Auswertungsbezeichnungen der Katalogantwort bleiben bewusst Deutsch; das Frontend übersetzt sie separat (dokumentierte Einschränkung).
- Hinweis: Das Ticket selbst war nicht lesbar; Abgleich erfolgte gegen die Zusammenfassung im Kontext-Dokument.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

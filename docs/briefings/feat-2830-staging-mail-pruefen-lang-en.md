---
spec_file: docs/specs/modules/fix_2774_staging_mailweg.md
spec_sha256: f205f8fe9fcc50125fa76b343165438ce7b4419fcb98f347526959ca5b456630
spec_frozen_sha256: 46470d94a00f504e85fe7678f2cc69857b15650a0772839ee47dc034a449f916
---

# PO-Briefing: feat-2830-staging-mail-pruefen-lang-en

- **Spec:** docs/specs/modules/fix_2774_staging_mailweg.md
- **Issue:** #2830
- **Erstellt:** 2026-11-06

## Was gebaut wird

Das Prüfwerkzeug kann auch eine englische Test-Mail über Staging zustellen und prüfen, damit der Nachweis für beide Sprachen möglich wird.

## Definition of Done

Der Aufruf mit englischer Option stellt Trip- und Ortsvergleich-Mail an die en-Adresse zu, der Prüfer meldet Exit 0, der Nutzer en bleibt bestehen.

## Wie geprüft wird

Automatische Tests gegen Ersatz-Staging belegen Anmeldung, Aufräumen und Fehlerfälle; echte englische Zustellung zeigt nur der Live-Lauf in der Freigabeprüfung.

## Kritische Anmerkungen

- Fremde Objekte des Nutzers en können das Trip-Kontingent blockieren; das Werkzeug löscht sie bewusst nicht (dokumentierte Grenze).
- Der Vertretungshinweis (#1563) selbst wird nicht auf Staging gemessen, nur die Sprachlücke im Nachweis geschlossen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

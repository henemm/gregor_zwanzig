---
spec_file: docs/specs/modules/fix_3361_ausblick_anlegen.md
spec_sha256: 29f5b3d6ee877839be2e5c4d6846e292b33da578a05ebde008a5b7fdbdc434e5
spec_frozen_sha256: a6d6c929723774abdbef5908870602ffeadf7f323c69b0cccf75f79c3d8a2252
---

# PO-Briefing: fix-3361-ausblick-anlegen

- **Spec:** docs/specs/modules/fix_3361_ausblick_anlegen.md
- **Issue:** #3361
- **Erstellt:** 2026-11-26

## Was gebaut wird

Beim Anlegen von Trip oder Orts-Vergleich erscheint der 3-Tages-Ausblick auch nach „nur Morgen-Briefing“ im Morgen-Briefing.

## Definition of Done

Der bisher ausgesetzte Test E137 läuft unverändert grün, Trip und Orte sind mit zwei Nutzern geprüft, Staging und Produktion bestehen.

## Wie geprüft wird

Automatische Tests mit echtem Kern prüfen alle fünf Kriterien; die echte Oberfläche wird nur auf Staging, nicht in den Tests, durchlaufen.

## Kritische Anmerkungen

- Bestehende Trips ohne gespeicherte Tabelle behalten den Fehler beim ersten Bearbeiten; bewusst ausgeklammert, nur als Beobachtung vermerkt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

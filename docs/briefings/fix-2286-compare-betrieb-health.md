---
spec_file: docs/specs/modules/fix_2286_compare_betrieb_health.md
spec_sha256: 9d7e8558caea03cb8cc1f2f5817fbe325af0fe8bec750617b8aff636d653f6dc
spec_frozen_sha256: ad2b89471b0ba31c487c1d369fe82c0a23935abe6fa9fed38ec8e073afc98e55
---

# PO-Briefing: fix-2286-compare-betrieb-health

- **Spec:** docs/specs/modules/fix_2286_compare_betrieb_health.md
- **Issue:** #2286
- **Erstellt:** 2026-10-21

## Was gebaut wird

Der Ortsvergleich-Versand meldet Ausfälle, kaputte Dateien und Wetter-Störungen wie der Trip-Versand, statt still zu scheitern.

## Definition of Done

Fällt der Ortsvergleich-Versand aus, kommt eine Meldung; eine kaputte Datei stoppt andere Vergleiche nicht; die Statusseite zeigt Korrupt-Zähler nach Art.

## Wie geprüft wird

Automatische Tests prüfen Meldungen, Zähler und Fehlerfälle mit zwei Nutzern; die Monitor-Anpassung und die Code-Kommentare sind nicht automatisch getestet.

## Kritische Anmerkungen

- Bei Wetter-Totalausfall geht keine Vergleichs-Mail mehr raus, stattdessen Alarm; Empfänger bekommen dann nichts.
- Monitor-Skript im Infra-Repo muss vor dem Deploy geändert werden; dafür gibt es keinen Test.
- „Totalausfall“ meldet schon, wenn nur ein einziger Nutzer scheitert.

## Freigabe-Frage

Einverstanden, dass bei Wetter-Totalausfall keine Vergleichs-Mail mehr versendet wird und stattdessen ein Alarm ausgelöst wird?

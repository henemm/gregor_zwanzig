---
spec_file: docs/specs/modules/feat_3059_orte_kompakt_mail.md
spec_sha256: 4459d396154a45051f1630bd3ed9f29425fe0b549a3924d43c02b69891daf5ce
spec_frozen_sha256: c3bfa2773b6dfb755ef6227435df77beb11f6231f35ef0cea97bff5aa56905fe
---

# PO-Briefing: feat-3059-orte-kompakt-zusatzbloecke

- **Spec:** docs/specs/modules/feat_3059_orte_kompakt_mail.md
- **Issue:** #3059
- **Erstellt:** 2026-11-24

## Was gebaut wird

Orte-Abos lassen sich wie Trips wahlweise als kurze Text-Mail mit einer Zeile je Ort zustellen.

## Definition of Done

Eine echt zugestellte Staging-Mail im Kompaktformat besteht die Prüfung, bestehende Orte-Abos kommen unverändert ausführlich an, beides in Deutsch und Englisch.

## Wie geprüft wird

Tests und Prüfskript stellen echte Mails zu und prüfen Format, Größe, Sprache und Nutzertrennung; die Bedienung im Editor prüft nur die Abnahme.

## Kritische Anmerkungen

- „Vergleich mit gestern“ für Orte fehlt bewusst und ist nach #3342 verschoben (deine Entscheidung vom 24.11.).
- Bei vielen Orten kürzt die Mail vom Listenende auf 2 KB und nennt die Restzahl.
- Test-Plan-Liste nennt nicht jedes Kriterium einzeln, jedes Kriterium hat aber eine eigene Testbeschreibung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

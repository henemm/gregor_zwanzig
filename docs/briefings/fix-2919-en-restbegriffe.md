---
spec_file: docs/specs/modules/i18n_2919_en_restbegriffe.md
spec_sha256: 31367cb90fcdb4bb2c0e60dba827f6ca429e95b166cf47a9957e6b78626fe884
spec_frozen_sha256: d2996cdbea0486a8752f0fdfeac9a33fc13649c1264a82abb3589a98c78b7610
---

# PO-Briefing: fix-2919-en-restbegriffe

- **Spec:** docs/specs/modules/i18n_2919_en_restbegriffe.md
- **Issue:** #2919
- **Erstellt:** 2026-11-11

## Was gebaut wird

Bei englischer Profilsprache erscheinen Filterchips, Kartenstatus, Aktionsblatt-Überschrift und Logo-Untertitel auf Englisch; Deutsch bleibt unverändert.

## Definition of Done

Mit Sprache Englisch zeigen Trip-Liste, Vergleichsliste, Aktionsblatt und Logo keine deutschen Restbegriffe mehr; Deutsch sieht aus wie heute.

## Wie geprüft wird

Tests rendern alle vier Stellen auf Englisch und Deutsch; sie ersetzen keinen Blick im echten Browser, der auf Staging folgt.

## Kritische Anmerkungen

- Zusatz über das Ticket hinaus: Die Prüfautomatik erkennt künftig auch Überschriften-Attribute; kein Entscheidungsbedarf.
- Bekannte Grenze: Künftige Texte in Standardwerten oder Listen erkennt die Automatik weiterhin nicht selbst.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

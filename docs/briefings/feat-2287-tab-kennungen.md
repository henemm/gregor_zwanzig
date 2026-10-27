---
spec_file: docs/specs/modules/feat_2287_tab_kennungen.md
spec_sha256: c44a2404fe85631bb4fbf6c545eb7c974169f3493e9a721212b8fcb440c84c9b
---

# PO-Briefing: feat-2287-tab-kennungen

- **Spec:** docs/specs/modules/feat_2287_tab_kennungen.md
- **Issue:** #2287
- **Erstellt:** 2026-10-05

## Was gebaut wird

Trip- und Ortsvergleich-Seite nutzen dieselben Reiter-Namen in der Adresszeile; alte Links öffnen weiterhin den richtigen Reiter.

## Definition of Done

Beide Seiten zeigen dieselben Reiter-Kennungen in der Adresszeile, alte Links öffnen den richtigen Reiter, und zwei Bestandsfehler (Vorschau, Wetter-Link) sind behoben.

## Wie geprüft wird

Automatische Tests prüfen Umleitung, Speicherschutz und Sprunglinks in beiden Seiten; die Browser-Tests laufen nicht in der Ampel, nur auf Staging.

## Kritische Anmerkungen

- Unbekannte Adressen (Tippfehler) fallen weiterhin still auf die Übersicht, obwohl das Issue genau das bemängelte.
- Punkte-Reiter heißt weiter Etappen bzw. Orte statt einheitlich; Issue wollte eine gemeinsame Kennung.
- Zusatz: Anlege-Seiten und rund 100 Browser-Test-Dateien werden mit umbenannt; Brüche zeigen sich erst auf Staging.

## Freigabe-Frage

Akzeptierst du, dass Tippfehler-Adressen auf der Übersicht landen und der Punkte-Reiter zwei Namen behält?

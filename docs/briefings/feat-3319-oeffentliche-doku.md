---
spec_file: docs/specs/modules/oeffentliche_doku_3319.md
spec_sha256: 2cbed9953a8660e4cd4c996a33945c358542b845eb0d8f8f40401ef68d1bea9e
spec_frozen_sha256: 73d4fa26b2a7032e83f0bc7f4cef4fec417fd820812fc6f5340e4ee8ecb38b95
---

# PO-Briefing: feat-3319-oeffentliche-doku

- **Spec:** docs/specs/modules/oeffentliche_doku_3319.md
- **Issue:** #3319 (zusammen mit #3320, Epic #3318)
- **Erstellt:** 2026-11-24

## Was gebaut wird

Besucher ohne Anmeldung sehen eine aktuelle Startseite, die Level Free/Standard/Premium und eine zweisprachige Funktionsübersicht mit Bildergalerie.

## Definition of Done

Startseite und alle zehn Funktionsseiten sind ohne Login auf Deutsch und Englisch abrufbar, zeigen alle vier Kanäle, echte Level-Grenzen und anklickbare Bilder.

## Wie geprüft wird

Automatische Tests und eine Staging-Prüfung belegen Inhalt, Zugriffsgrenzen, Handy-Breite, Galerie und Zahlen-Abgleich; die Sichtprüfung der Bilder auf Personendaten bleibt manuell.

## Kritische Anmerkungen

- Der Testsatz zur Galerie steht im Testplan, nicht bei der Galerie-Anforderung selbst; inhaltlich ist sie abgedeckt.
- Preise und Bezahlweg werden bewusst nicht genannt; Level-Wechsel nur per Antrag. Der Claude-Konnektor fehlt absichtlich.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

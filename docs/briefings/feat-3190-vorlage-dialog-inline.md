---
spec_file: docs/specs/modules/feat_3190_vorlage_dialog_inline.md
spec_sha256: 3c321479c2034a1ff2efdc65d464c1766a3b59b46125a6ebaab43e3ba655d99a
spec_frozen_sha256: aa7a15707fd4b56f6bdc0cdb36fd52f1da11e6321cdde6b0542a33b2b9e22d5a
---

# PO-Briefing: feat-3190-vorlage-dialog-inline

- **Spec:** docs/specs/modules/feat_3190_vorlage_dialog_inline.md
- **Issue:** #3190
- **Erstellt:** 2026-11-20

## Was gebaut wird

Der Dialog „Vorlage speichern“ wird eine Karte unter der Vorlage-Karte mit Ankreuzfeld und einzeiligem Beschreibungsfeld statt eines Overlays.

## Definition of Done

Im Reiter Wetter öffnet der Knopf die Karte nach Mockup, Speichern und Abbrechen funktionieren, Staging-Prüfung und Soll/Ist-Bild liegen vor.

## Wie geprüft wird

Automatische Tests und Staging-Läufe prüfen Aufbau, Speichern, Fehler, Tastatur und beide Sprachen; die Optik wird nur per Bildvergleich beurteilt.

## Kritische Anmerkungen

- Zusatz: Auch der alte Anlege-Editor wird umgebaut, nicht verlangt; dort womöglich nie sichtbar.
- Escape schließt die Karte weiterhin, obwohl das Mockup keine Tastaturbehandlung zeigt; Bestandsverhalten bleibt bewusst erhalten.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

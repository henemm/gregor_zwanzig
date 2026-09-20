---
spec_file: docs/specs/modules/fix_1761_korsika_arome_sidecar.md
spec_sha256: 9e758a2773446fb83d389164ffd80cab4ec54bfd675578709e9d07b975d3f040
---

# PO-Briefing: fix-1761-korsika-radar-arome

- **Spec:** docs/specs/modules/fix_1761_korsika_arome_sidecar.md
- **Issue:** #1761
- **Erstellt:** 2026-09-20

## Was gebaut wird

Korsika-Wetternachrichten nutzen künftig die schärfere französische Regenvorhersage, ergänzt um italienische Gewitter-/Hagel-Daten.

## Definition of Done

Eine Abfrage für eine Korsika-Koordinate liefert Regen-Daten aus der französischen Quelle und Gewitter-/Hagel-Status aus der italienischen Zusatzquelle.

## Wie geprüft wird

Tests prüfen mit echten Koordinaten (Vizzavona, Conca, Grenze zu Sardinien) Quelle, Gewitter-Übernahme und Ausfallverhalten — keine Prüfung der tatsächlichen Vorhersagegüte vor Ort.

## Kritische Anmerkungen

- Zusätzlich zur Anfrage: eine komplexere Sidecar-Lösung statt einfacher Umschaltung, mit doppeltem Abfrage-Verbrauch pro Korsika-Nowcast (vom PO bereits entschieden).
- Fällt die italienische Zusatzquelle aus, bleibt der Gewitter-Status für diesen einen Aufruf unbeantwortet statt falsch auf „kein Gewitter" zu stehen.

## Freigabe-Frage

Ist die aufwendigere Sidecar-Lösung mit doppeltem Abfrage-Verbrauch für Korsika trotz höherer Komplexität die richtige Wahl?

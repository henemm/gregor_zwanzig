---
spec_file: docs/specs/modules/fix_1761_korsika_arome_sidecar.md
spec_sha256: ab6a538966aef961ad431ebc7254f6a1c48a586297bde2bb4d01ae3e8603d070
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

- Sidecar-Lösung ist aufwendiger als die im Issue vorgeschlagene einfache Umschaltung, mit doppeltem Abfrage-Verbrauch (vom PO entschieden).
- Fällt die italienische Zusatzquelle aus, bleibt der Gewitter-Status für diesen Aufruf unbeantwortet statt falsch „kein Gewitter".

## Freigabe-Frage

Ist die bereits gebilligte, aufwendigere Sidecar-Lösung mit doppeltem Abfrage-Verbrauch für dich weiterhin die richtige Wahl?

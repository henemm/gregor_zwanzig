---
spec_file: docs/specs/modules/feat_2913_s3_bausteine.md
spec_sha256: be28a4ad78bb1df0a697efe0e004138dda51ff9fac4a722dc3a70c7f2388b510
spec_frozen_sha256: ca9a06bccd1986c9940855cfbaeb18680ff77e8d5d72d8fea43da5822aad33be
---

# PO-Briefing: feature-2913-bausteine

- **Spec:** docs/specs/modules/feat_2913_s3_bausteine.md
- **Issue:** #2913
- **Erstellt:** 2026-11-11

## Was gebaut wird

Der rote Prüfwächter wird behoben, der Wetter-Reiter entsteht aus gemeinsamen Bausteinen mit neuen Ampelfarben.

## Definition of Done

Wächter grün, Wetter-Reiter erst unverändert, dann mit Ampelfarben; auf Staging bleibt ein geänderter Grenzwert gespeichert.

## Wie geprüft wird

Tests prüfen Wächter, Kontrast, Bausteine und Texte; ob die Ampelfarben gut aussehen, zeigt nur die Sichtprüfung.

## Kritische Anmerkungen

- Ticket verlangt alle fehlenden Bausteine; die Spec baut nur die für Scheibe (a)/(b).
- „Nahe am Mockup“ (Ampelfarben) ist nicht messbar; geprüft wird nur der Kontrast.

## Freigabe-Frage

Ist es in Ordnung, dass hier nur die Bausteine für Scheibe (a)/(b) entstehen und der Rest später folgt?

## Ampel

Ampel: rot

---
spec_file: docs/specs/modules/rework_2276_s6e_versand.md
spec_sha256: bfe41ca8fbfdc9031787962017903f620f2d72037e2c015abc106e2850cc2a94
---

# PO-Briefing: refactor-2276-s6e-versand-wertprops

- **Spec:** docs/specs/modules/rework_2276_s6e_versand.md
- **Issue:** #2276
- **Erstellt:** 2026-09-22

## Was gebaut wird

Der Versand-Reiter im Ortsvergleich speichert künftig direkt wie bei der Tour, ohne den alten Umweg-Mechanismus.

## Definition of Done

Fertig ist es, wenn der Versand-Reiter im Ortsvergleich weiterhin genauso funktioniert wie heute, nur technisch aufgeräumt.

## Wie geprüft wird

Automatisierte Tests prüfen den Umbau im Hintergrund, ein bereits bestehender Browsertest bestätigt, dass sich am Verhalten nichts ändert.

## Kritische Anmerkungen

- Die beiden „neuen Vergleich anlegen"-Wege werden nicht durch einen echten Browsertest abgesichert, nur durch eine automatische Code-Prüfung.
- Der E-Mail-Schalter merkt sich seine Einstellung weiterhin nicht dauerhaft — eine bekannte, hier nicht behobene Einschränkung.
- Es wird kein neuer End-to-End-Test ergänzt; die Absicherung stützt sich vollständig auf einen bereits bestehenden Test.

## Freigabe-Frage

Sollen wir den Versand-Reiter wie beschrieben umbauen und danach wie geplant mit dem letzten Bereich (Wetter-Metriken) fortfahren?

---
spec_file: docs/specs/modules/rework_2276_s6b_wetter_metriken.md
spec_sha256: c7fb0204ae773f81eed71a1d820270aac9e43350b98af60c082e8f1a5f269bdb
---

# PO-Briefing: rework-2276-s6b-wetter-metriken

- **Spec:** docs/specs/modules/rework_2276_s6b_wetter_metriken.md
- **Issue:** #2276
- **Erstellt:** 2026-09-21

## Was gebaut wird

Ein Software-Baustein im Stundenverlauf-Reiter wird intern umgebaut — für Nutzer unsichtbar.

## Definition of Done

Fertig ist es, wenn Metrikauswahl und Ein/Aus-Schalter im Stundenverlauf weiterhin unverändert funktionieren und gespeichert werden — geprüft im Live-Browser.

## Wie geprüft wird

Ein neuer Live-Browsertest deckt Auswahl, Schalter und Speichern ab; er beweist nur diese eine Bedienfläche, nicht den Rest des Ortsvergleichs.

## Kritische Anmerkungen

- Reiner Innenumbau ohne sichtbaren Nutzen für den PO — Aufwand ohne späteren sichtbaren Unterschied.
- Nur eine von sechs möglichen Aufräum-Stellen wird erledigt; vier weitere Scheiben (S6c–S6f) müssen noch folgen, bis das Ticket-Ziel erreicht ist.
- Eine bewusst nicht aufgeräumte Doppelprüfung bleibt bestehen — Schutz gegen Speichern im falschen Bereich (Tour statt Vergleich), nachvollziehbar begründet.

## Freigabe-Frage

Soll dieser für Nutzer unsichtbare Umbauschritt trotz Restaufwands freigegeben werden, obwohl das Ticket-Ziel erst in vier weiteren Scheiben erreicht wird?

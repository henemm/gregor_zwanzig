---
spec_file: docs/specs/modules/feat_2281_vergleich_versand_historie.md
spec_sha256: c8a42894b905fca1c75c4a1d129ec69e3b73d557b18ccfae5f6c961fcf9f92ac
spec_frozen_sha256: b0278364bdab90600cc49441067f6dff5d6caea7c6fb92ee0d42d60c6bb9831a
---

# PO-Briefing: feat-2281-vergleich-versand-historie

- **Spec:** docs/specs/modules/feat_2281_vergleich_versand_historie.md
- **Issue:** #2281
- **Erstellt:** 2026-10-21

## Was gebaut wird

Trip und Ortsvergleich zeigen im Reiter Übersicht, wann und über welche Kanäle ihr Briefing zugestellt wurde.

## Definition of Done

Nach einem Versand erscheint in beiden Reitern Übersicht ein neuer Eintrag mit Kanälen und Zeitpunkt; bisherige Trip-Einträge bleiben vollständig erhalten.

## Wie geprüft wird

Automatische Tests prüfen Eintragen, Nutzertrennung, Doppelversand-Schutz und Altdaten; das echte Aussehen sieht man erst per Sichtprüfung auf Staging.

## Kritische Anmerkungen

- Cockpit- und Archiv-Zahlen für Ortsvergleiche bekommen nur eine Schnittstelle, keine Anzeige; das Ticket verlangte sichtbare Zahlen.
- Ortsvergleiche heißen intern „compare" statt „vergleich" wie im Ticket; für Nutzer unsichtbar.

## Freigabe-Frage

Ist es für dich in Ordnung, dass Ortsvergleich-Zahlen in Cockpit und Archiv vorerst nicht angezeigt werden?

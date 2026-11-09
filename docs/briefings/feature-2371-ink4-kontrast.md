---
spec_file: docs/specs/modules/ink4_kontrast_2371.md
spec_sha256: ff55f54cf95cdc7806c1ef92d7536a359e534ac2a8b194c8ca1bda6d971ab4c2
spec_frozen_sha256: 075c9292814406f8760c66627bfb3a52c317a4dd8ee06bed58f0aebfec3817a9
---

# PO-Briefing: feature-2371-ink4-kontrast

- **Spec:** docs/specs/modules/ink4_kontrast_2371.md
- **Issue:** #2371
- **Erstellt:** 2026-11-09

## Was gebaut wird

Beschriftungen, Fortschritt und gesperrte Tabs in den Anlege-Seiten und im Archiv werden dunkler und lesbar; ein Wächter verhindert Rückfälle.

## Definition of Done

Alle Texte auf Trip-Anlegen, Vergleich-Anlegen und Archiv erreichen mindestens 4,5:1 Kontrast, gesperrte Tabs bleiben als gesperrt erkennbar, neue Verstöße werden rot gemeldet.

## Wie geprüft wird

Ein Messlauf gegen Staging prüft Kontraste auf dem Handy-Format; ein Wächter prüft den Quelltext. Das Aussehen beurteilt zusätzlich ein Blick auf Screenshots.

## Kritische Anmerkungen

- Gesperrte Tabs zeigen statt Schloss-Symbol das Zeichen ⊘; Abweichung vom Ticket-Wortlaut, geringe Folge.
- Bestand außerhalb Anlege-Pfad und Archiv (ca. 84 Stellen) bleibt vorerst unverändert; Abbau später.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

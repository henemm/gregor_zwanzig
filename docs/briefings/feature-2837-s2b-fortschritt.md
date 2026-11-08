---
spec_file: docs/specs/modules/rework_2837_s2b_anlege_fortschritt.md
spec_sha256: 97261b10c4874e326beeafa3a434e827f749a3e992424f7189ad87abba203280
spec_frozen_sha256: fee922737d769de2500a5011ea877259af75ef7d7595422804dd198c6c49d886
---

# PO-Briefing: feature-2837-s2b-fortschritt

- **Spec:** docs/specs/modules/rework_2837_s2b_anlege_fortschritt.md
- **Issue:** #2837
- **Erstellt:** 2026-11-08

## Was gebaut wird

Der Fortschrittsbalken beim Anlegen von Trip und Ortsvergleich sieht auf Computer und Handy überall gleich aus.

## Definition of Done

Beide Anlege-Seiten zeigen auf Computer und Handy fünf gleich gefärbte Segmente mit gleichem Zähler, auf Staging und Produktion bestätigt.

## Wie geprüft wird

Automatische Tests prüfen Segmentzahl, Farben und Zählertext in Deutsch und Englisch; ob es gut aussieht, beurteilt kein Test.

## Kritische Anmerkungen

- Ursprungsanfrage nur über Kontext-Dokument geprüft, Issue-Text selbst nicht gelesen.
- Der Ortsvergleich verliert auf dem Handy die orange Tönung des aktiven Schritts; Tech-Lead-Entscheid, der aktive Schritt bleibt in der Reiterleiste sichtbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

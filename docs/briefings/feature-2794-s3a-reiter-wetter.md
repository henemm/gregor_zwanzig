---
spec_file: docs/specs/modules/feat_2794_s3a_reiter_wetter.md
spec_sha256: 034b9b0f8c040cbe670dd0f9031c20256bcda3dad104d8f97810ef4d75ad922e
spec_frozen_sha256: b51cdb1551301661cc6a3dd2eed49901917e540af341d4150845cb05c8df6ef3
---

# PO-Briefing: feature-2794-s3a-reiter-wetter

- **Spec:** docs/specs/modules/feat_2794_s3a_reiter_wetter.md
- **Issue:** #2794
- **Erstellt:** 2026-11-08

## Was gebaut wird

Trip und Orts-Briefing bekommen vier Reiter; im neuen Reiter Wetter stellt man Vorlage, Ampel-Grenzen und Alarmschwelle ein.

## Definition of Done

Alle vier Reiter funktionieren in Trip und Orts-Briefing, alte Links leiten um, kein Bedienelement der Zustellung geht verloren, alle 36 Kriterien bestehen auf Staging.

## Wie geprüft wird

Browser-Tests auf Staging und Datenprüfungen mit zwei Nutzern belegen jedes Kriterium; das Aussehen gegenüber dem Mockup bleibt eine Augenprüfung.

## Kritische Anmerkungen

- Die Lieferung erfolgt in vier Teilpaketen; der Reiter Wetter wird erst nach Merge der Alarm-Vorarbeit (#2862) ausgeliefert.
- Zustellung bleibt bis zur Folgescheibe ein Übergangsreiter mit heutigen Bausteinen; wie vom PO entschieden, aber noch nicht der Zielzustand.
- Zwei Kriterien (Mockup-Übereinstimmung, mobile Überschrift) sind nur per Augenabgleich prüfbar, teils ohne Messwert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

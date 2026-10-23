---
spec_file: docs/specs/modules/feat_2282_s2_ortsvergleich_befehle_versand.md
spec_sha256: 242b37c78551831f40c6b65d838f1927664b457b9a86d6a6f16a2376ab988b67
spec_frozen_sha256: e3e09e1fbdda0eacec75a0ea6e8b3d4d4c6f8e4a49141da981720d5048a558cf
---

# PO-Briefing: feat-2282-s2-compare-report

- **Spec:** docs/specs/modules/feat_2282_s2_ortsvergleich_befehle_versand.md
- **Issue:** #2282
- **Erstellt:** 2026-10-22

## Was gebaut wird

Die Befehle report, heute und morgen liefern am Ortsvergleich ein echtes Wetter-Briefing statt der Übergangsantwort.

## Definition of Done

Auf Staging kommt per Befehl über alle vier Kanäle ein Vergleichs-Briefing an, jeder Lauf unter 60 Sekunden.

## Wie geprüft wird

Automatische Tests zählen Zustellungen je Kanal und trennen zwei Nutzer; Tempo und Mail-Qualität werden nur manuell auf Staging belegt.

## Kritische Anmerkungen

- Tempo wurde nur ohne Rendern und Versand gemessen; ob 60 Sekunden real halten, zeigt erst Staging.
- Der Anfragekanal wird auch ohne Aktivierung im Vergleich bedient (nur Tarif zählt) — bewusste Abweichung von der Alarm-Regel.
- Einige Erfolgskriterien sind vage: „kurze Bestätigung im selben Wortlaut-Muster", „verständlicher Text".

## Freigabe-Frage

Soll der Ortsvergleich Befehle ohne Namen bei Trip plus Vergleich immer rückfragen und den Anfragekanal auch ohne Aktivierung bedienen?

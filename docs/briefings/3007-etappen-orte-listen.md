---
spec_file: docs/specs/modules/feat_3007_etappen_orte_listen.md
spec_sha256: dd991784248262c82242b0b92e3fcf63daf4676d664a4c8816a0cbeff8736e1a
spec_frozen_sha256: 26ad1cfd73b6b8e26ee878747f81049bd2927e508fb29b920f1c7571be4a4c89
---

# PO-Briefing: 3007-etappen-orte-listen

- **Spec:** docs/specs/modules/feat_3007_etappen_orte_listen.md
- **Issue:** #3007
- **Erstellt:** 2026-11-17

## Was gebaut wird

Etappen und Orte erscheinen als ruhige Listen wie im Mockup, auf Deutsch und Englisch.

## Definition of Done

Beide Reiter zeigen die Mockup-Listen, alle bisherigen Funktionen bleiben, und der Abgleich auf Staging meldet für sie weder Abweichung noch Fremdtexte.

## Wie geprüft wird

Darstellungstests, Browsertests auf Staging und der Abgleich belegen Aussehen und Funktionen; die Tempo-Bedienung ist bewusst nicht Teil davon.

## Kritische Anmerkungen

- Etappen-Editor (Karte, Wegpunkte, Datum) ist nur noch per Klick auf eine Etappenzeile sichtbar; ein Editor gleichzeitig.
- Knopf „Tempo ändern" fehlt vorerst (gehört zu #2796); Tempo nur über den aufgeklappten Editor änderbar.
- Ziehgriff zum Sortieren der Orte bleibt, obwohl das Mockup keinen zeigt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

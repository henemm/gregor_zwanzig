---
spec_file: docs/specs/modules/feat_3151_pruefkonto_abgleich.md
spec_sha256: 187cfd41d148a18cc90690d916f90fea8662952e44a4c421800dc905c8f03669
spec_frozen_sha256: ea4daf7ca59fc19e230d8f8d27eaefaa6ffcf22f6027a66f48c0bb0dfb8620c1
---

# PO-Briefing: feat-3151-pruefkonto-abgleich

- **Spec:** docs/specs/modules/feat_3151_pruefkonto_abgleich.md
- **Issue:** #3151
- **Erstellt:** 2026-11-20

## Was gebaut wird

Das Staging-Prüfkonto zeigt die Kanalauswahl des Mockups, und alle 247 offenen Abgleich-Einträge sind aufgelöst oder umgehängt.

## Definition of Done

Der Seed läuft zweimal fehlerfrei auf Staging, der Abgleich DE und EN schreibt nichts, und kein Eintrag verweist mehr auf #2967.

## Wie geprüft wird

Automatische Tests prüfen Kanalwerte, Wiederholbarkeit, Nutzertrennung und Besitzerliste; Staging-Lauf und Klassifizierungs-Kommentar im Issue werden nur manuell abgenommen.

## Kritische Anmerkungen

- Das Schließen von #3145 fehlt in der Definition of Done der Spec.
- Zahl und Verteilung der neuen Kind-Issues steht erst nach dem Staging-Lauf fest.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

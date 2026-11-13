---
spec_file: docs/specs/modules/feat_2913_c2_seitenkopf.md
spec_sha256: ab082264a33d11d5e6e8dcc956e913793c5a756f5f3959f10474ee5fb129685c
spec_frozen_sha256: 4c505488c2126b0fce9a184d83e3c626361889821a1ab98897e2b6109536ad3c
---

# PO-Briefing: feature-2913-c2-seitenkopf

- **Spec:** docs/specs/modules/feat_2913_c2_seitenkopf.md
- **Issue:** #2913
- **Erstellt:** 2026-11-13

## Was gebaut wird

Trip- und Orts-Vergleich-Seitenkopf samt Reitern mit Zähler und Vorlage-Karte entsprechen dem freigegebenen Mockup, deutsch und englisch.

## Definition of Done

Auf Staging zeigen beide Köpfe in Deutsch und Englisch die Mockup-Elemente, der automatische Seitenabgleich meldet keine Abweichung, Henning erhält ein Soll/Ist-Bild.

## Wie geprüft wird

Automatische Tests und Staging-Läufe prüfen Texte, Zähler, Zustände, Mobilansicht und Zwei-Nutzer-Trennung; Aussehen im Detail beurteilt nur der Bildvergleich.

## Kritische Anmerkungen

- Profil-Zeile, Tempo-Karte und Mail-Kopf-Satz bleiben vorerst, obwohl das Mockup sie anders zeigt; verschoben auf spätere Scheibe #2796.
- Name/Region bleiben bearbeitbar, obwohl das Mockup das nicht zeigt; Stift nur noch als Symbol.
- „Test schicken ▾“ ist nur eine Beschriftung; das Menü folgt später mit #2797.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

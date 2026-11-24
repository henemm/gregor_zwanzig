---
spec_file: docs/specs/modules/feat_3333_zustellung_anlegen_orte.md
spec_sha256: 0c5dd0caf28dfa6c931043bedc96c0ec5f6c718915f39f08b1d1f5f6edb42273
spec_frozen_sha256: b3c5d749a24faa6f434903131a470eaf3582127e78bdeec94b13e9acaff01fec
---

# PO-Briefing: feat-3333-orte-anlegen-zustellung

- **Spec:** docs/specs/modules/feat_3333_zustellung_anlegen_orte.md
- **Issue:** #3333
- **Erstellt:** 2026-11-24

## Was gebaut wird

Beim Anlegen eines Ortsvergleichs stellt der Nutzer Zeiten, Kanäle und Alarme im Reiter Zustellung ein, wie bei gespeicherten Vergleichen.

## Definition of Done

Ein neu angelegter Ortsvergleich übernimmt genau die im Reiter Zustellung eingestellten Werte, auch E-Mail aus, und zeigt sie im Hub.

## Wie geprüft wird

Automatische Tests und Browser-Tests prüfen gespeicherte Werte, zwei Nutzer und unveränderte Standardwerte; Optik und Wortlaut prüfen sie nicht.

## Kritische Anmerkungen

- Reiter Alarme bleibt beim Anlegen, verliert aber Kanäle, Cooldown und Stille Stunden an Zustellung; Erklärtexte und Infobox des Alt-Panels entfallen.
- Amtliche Warnungen und Radar bleiben an zwei Stellen bedienbar; als Nebenbefund erfasst, nicht Teil dieses Auftrags.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

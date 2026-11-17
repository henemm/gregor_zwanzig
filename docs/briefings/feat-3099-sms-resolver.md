---
spec_file: docs/specs/modules/feat_3099_sms_resolver.md
spec_sha256: 30cff7fa18c603632d84a51aaccc4316f4a6ba5ba4d209e95f759eff2133f2c1
spec_frozen_sha256: 8e7108a0f5848ebee904e4d79f12ae9f233082cb4618ac03b7496d12f5f9b349
---

# PO-Briefing: feat-3099-sms-resolver

- **Spec:** docs/specs/modules/feat_3099_sms_resolver.md
- **Issue:** #3099
- **Erstellt:** 2026-11-17

## Was gebaut wird

Die Trip-SMS bezieht Auswahl und Reihenfolge künftig aus der gemeinsamen Einstellung; für Nutzer bleibt sie unverändert.

## Definition of Done

Alle zwölf Prüfpunkte sind grün, die zugestellte SMS ist auf Staging für Trip und Orte unverändert, der Prod-Selftest besteht.

## Wie geprüft wird

Bestehende Referenz-SMS bleiben Zeichen für Zeichen gleich; neue Fälle prüfen Folge, Format, Warnungen und Nutzertrennung, nicht aber eine eigene Premium-Liste.

## Kritische Anmerkungen

- Premium-SMS bekommt bewusst keine eigene Inhaltsliste, bleibt textgleich zur SMS; das Ticket verlangt sie nicht.
- Neue Fälle stehen im alten Format und werden beim Neuschnitt umformuliert (PO-Auflage bekannt).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

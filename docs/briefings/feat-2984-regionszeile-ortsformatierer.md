---
spec_file: docs/specs/modules/feat_2984_regionszeile_ortsformatierer.md
spec_sha256: 623857fe76318545e01c4af8a3e4c7fced650d570b482b5c8d55f00ba83154ae
spec_frozen_sha256: 0a9c4c5714c78aad43c987a72deaa66b50573fc5958591b7a89895ac6bb91840
---

# PO-Briefing: feat-2984-regionszeile-ortsformatierer

- **Spec:** docs/specs/modules/feat_2984_regionszeile_ortsformatierer.md
- **Issue:** #2984
- **Erstellt:** 2026-11-17

## Was gebaut wird

Bei amtlichen Warnungen nennen Kopf und Regionszeile derselben Nachricht künftig dieselbe Ortsangabe, etwa „km 12-20".

## Definition of Done

In einer echt zugestellten Alarm-Mail mit amtlicher Warnung und gemessener Strecke zeigen Kopf, Regionszeile und Telegram-Text dieselbe Kilometerangabe.

## Wie geprüft wird

Automatische Tests vergleichen Regionszeile und Kopf in beiden Sprachen und über den echten Versandweg; SMS bleibt unverändert, Mail-Prüfung auf Staging.

## Kritische Anmerkungen

- Sichtbare Änderung: Mit gemessener Strecke steht im Klartext und Telegram künftig „km 12-20" statt „Segment 3" (Entscheidung aus #2036).
- Entwarnungen bleiben bewusst bei „Segment"; Angleichung wäre ein eigenes Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen

---
spec_file: docs/specs/modules/pii_log_masking.md
spec_sha256: 6537937d08f330ea1d0f477b89219ae9ada62c205d26a5e5d2608bcc289ff589
---

# PO-Briefing: feature-2157-pii-log-maskierung

- **Spec:** docs/specs/modules/pii_log_masking.md
- **Issue:** #2157
- **Erstellt:** 2026-09-27

## Was gebaut wird

E-Mail-Adressen und Chat-Kennungen echter Nutzer werden in Protokollen und Verlaufsdateien künftig verschleiert statt im Klartext gespeichert.

## Definition of Done

Kein Protokoll und keine gespeicherte Versanddatei zeigt mehr die volle Adresse eines echten Nutzers; zwei Testadressen bleiben lesbar.

## Wie geprüft wird

Tests prüfen jede Fundstelle mit echten Beispieladressen; ein Wächter warnt künftig bei gleich benannten Klartext-Stellen, aber nicht bei Umbenennungen.

## Kritische Anmerkungen

- Ändert Ihre frühere Freigabe #1847: der Empfänger ist künftig nur bei zwei Testadressen unmaskiert.
- Statt des verlangten Hash nutzt die Spec dieselbe Verschleierung wie im Protokoll (Hash wäre zurückrechenbar).
- Der neue Warn-Mechanismus erkennt nur exakt benannte Fälle, nicht anders benannte künftige Stellen.

## Freigabe-Frage

Sind Sie einverstanden, dass „Empfänger nie maskiert" künftig nur für zwei Testadressen gilt, sonst wird immer maskiert?

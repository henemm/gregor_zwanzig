---
spec_file: docs/specs/modules/pii_log_masking.md
spec_sha256: 26d79d336bbb221d937b30b2dbc3974de481d2122696be8c136a889634c936c1
---

# PO-Briefing: feature-2157-pii-log-maskierung

- **Spec:** docs/specs/modules/pii_log_masking.md
- **Issue:** #2157
- **Erstellt:** 2026-09-27

## Was gebaut wird

E-Mail-Adressen und Telegram-Kennungen fremder Nutzer werden in Protokollen und gespeicherten Verläufen unkenntlich, außer bei zwei bekannten Testadressen.

## Definition of Done

Fremde Adressen erscheinen in Protokollen und Verläufen nur verkürzt, zwei bekannte Testadressen bleiben lesbar, ein Wächter meldet neue unverkürzte Stellen.

## Wie geprüft wird

Tests belegen die Verkürzung an den geänderten Stellen mit echten Adressen; der automatische Wächter erkennt aber nur drei feste Variablennamen, keine umbenannten Fälle.

## Kritische Anmerkungen

- Ändert eine frühere Freigabe: statt nie zu maskieren, bleiben nur zwei bekannte Testadressen im Klartext.
- Ticket wollte die gespeicherte Adresse verschlüsseln; umgesetzt wird stattdessen dieselbe Verkürzung wie in Protokollen.
- Zusätzlich: bestehende gespeicherte Adressen werden einmalig umgeschrieben, Erfolg nur per Zählervergleich nachweisbar.

## Freigabe-Frage

Sind die geänderte frühere Zusage, die Verkürzung statt Verschlüsselung und die einmalige Umschreibung bestehender Adressen für Sie akzeptabel?

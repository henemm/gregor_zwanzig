---
spec_file: docs/specs/modules/feat_1563_compare_vertretungshinweis.md
spec_sha256: 77de36d99de9f967b58b9bf0a86fec28d0a08a5931a2e2684390b5d50f6dcb11
spec_frozen_sha256: cdee9daf2f97099ede9a298c99a8a64361a866c9fa513090f703180ea021a168
---

# PO-Briefing: feat-1563-compare-vertretungshinweis

- **Spec:** docs/specs/modules/feat_1563_compare_vertretungshinweis.md
- **Issue:** #1563 (Text per Kontext-Dokument docs/context/feat-1563-compare-vertretungshinweis.md geprüft)
- **Erstellt:** 2026-11-04

## Was gebaut wird

Ortsvergleichs-Mails nennen künftig namentlich die Orte, bei denen eine Ersatz-Wetterquelle einsprang.

## Definition of Done

Bei vertretenem Ort zeigen E-Mail und Telegram eine Zeile mit Ortsnamen; ohne Vertretung bleibt die Mail unverändert.

## Wie geprüft wird

Tests mit echten Objekten prüfen Hinweis, Unverändertheit und Nutzertrennung; die Vertretungszeile selbst ist auf Staging nicht als zugestellte Mail belegbar.

## Kritische Anmerkungen

- SMS und Premium-SMS zeigen keinen Hinweis; das widerspricht gleichrangigen Kanälen und stützt sich nur auf die Trip-Präzedenz.
- Darstellung (Orte namentlich unter der Tabelle, nicht in der Spalte) entschied die Spec, nicht der PO.
- Alarm- und Vorschau-Mails bekommen keinen Hinweis.

## Freigabe-Frage

Akzeptierst du, dass SMS und Premium-SMS keinen Vertretungshinweis bekommen und Orte nur namentlich unter der Tabelle genannt werden?

## Ampel

Ampel: rot

---
spec_file: docs/specs/modules/fix_3364_nur_morgens_abends.md
spec_sha256: 9febdd9de8b616a43df6efc8bc0b95d14868860ade761d770a7d430ece5ba179
spec_frozen_sha256: 319060696f496e847a56090e741f7927514067e473a1a97beb22f0a3b636971a
---

# PO-Briefing: fix-3364-nur-morgens-abends

- **Spec:** docs/specs/modules/fix_3364_nur_morgens_abends.md
- **Issue:** #3364
- **Erstellt:** 2026-11-26

## Was gebaut wird

Größen, die nur morgens oder abends gelten, erscheinen im Reiter Wetter als gewählt, lassen sich abwählen und sind gekennzeichnet.

## Definition of Done

Nur-morgens-Größen sind im Reiter gewählt, nach „−“ in keiner Mail mehr, in der Karte gekennzeichnet, und der Ausblick-Haken stimmt mit den Briefings überein.

## Wie geprüft wird

Automatische Tests und eine Staging-Prüfung auf Deutsch und Englisch weisen alle sieben Kriterien nach; eine Einschränkung auf „nur morgens“ bleibt in der Tabelle unbedienbar.

## Kritische Anmerkungen

- Wiederanwahl einer abgewählten Größe hebt „nur morgens/abends“ still auf; das Ticket nennt das als Produktfrage, nicht entschieden.
- Kennzeichnung in der Karte ist im Ticket ebenfalls als offene Produktfrage markiert.

## Freigabe-Frage

Soll eine wieder angewählte Größe immer in beiden Briefings stehen, also die frühere Einschränkung „nur morgens/abends“ verlieren, und soll die Karte sie kennzeichnen?

## Ampel

Ampel: rot

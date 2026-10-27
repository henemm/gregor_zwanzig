---
spec_file: docs/specs/modules/feat_2277_s4_anlege_lockengine.md
spec_sha256: 3e17e6c11bc0f2f166e3de53b3d3bb5b3482bee78fc5434d1929226e3552a758
---

# PO-Briefing: feat-2277-s4-anlege-lockengine

- **Spec:** docs/specs/modules/feat_2277_s4_anlege_lockengine.md
- **Issue:** #2277
- **Erstellt:** 2026-10-01

## Was gebaut wird

Die Freischalt-Reihenfolge der Anlege-Seiten für Trip und Ortsvergleich wird intern zusammengeführt; sichtbar ändert sich nichts.

## Definition of Done

Beide Anlege-Seiten schalten Reiter, Anlegen-Knopf und Fortschrittszähler exakt wie bisher frei, und die doppelte Ortsvergleich-Logik existiert nicht mehr.

## Wie geprüft wird

Tests prüfen Reihenfolge, Anlegen-Knopf und Zähler an der echten Reiterleiste; Aussehen im Browser zeigt nur der Staging-Durchlauf.

## Kritische Anmerkungen

- Ticket-Anforderung 5 bleibt teilweise offen: Mail-Inhalt-Rest folgt in S5, Issue #2277 bleibt offen.
- Test an der Reiterleiste des Ortsvergleichs existiert noch nicht; Ausweichen auf Trip-Testaufbau würde den Nachweis abschwächen.
- Fortschrittszähler bleibt bewusst verschieden (Trip /4, Ortsvergleich bis 6); Angleichung nicht enthalten.

## Freigabe-Frage

Gibst du diesen reinen Umbau ohne sichtbare Änderung frei, obwohl Issue #2277 danach noch offen bleibt?

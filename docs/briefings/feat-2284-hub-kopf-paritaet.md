---
spec_file: docs/specs/modules/feat_2284_s1_subscription_header.md
spec_sha256: a4abd8cc2844e83b7919fbaf1612ce77811f9ff1b73e9e1b9ec31a22cb2e212d
---

# PO-Briefing: feat-2284-hub-kopf-paritaet

- **Spec:** docs/specs/modules/feat_2284_s1_subscription_header.md
- **Issue:** #2284
- **Erstellt:** 2026-10-03

## Was gebaut wird

Der Kopf des Vergleich-Hubs wird auf einen gemeinsamen Baustein umgebaut; für Nutzer ändert sich nichts Sichtbares.

## Definition of Done

Name, Region und Profil lassen sich im Vergleich-Hub wie bisher bearbeiten und speichern, Fehler erscheinen am Feld, bestehende Browser-Tests bleiben unverändert grün.

## Wie geprüft wird

Automatische Tests prüfen Aufbau und Wiederverwendbarkeit des Bausteins; Speichern und Fehlerfälle prüfen nur Browser-Tests, nicht die Trip-Seite selbst.

## Kritische Anmerkungen

- Trip-Region, Aktivität im Kopf und Speicher-Chip-Ort aus dem Issue fehlen hier vollständig; sie folgen erst in Scheibe S2.
- S2 wartet auf einen fremden Merge (PR 2486), Termin offen; Trip und Vergleich bleiben bis dahin ungleich.

## Freigabe-Frage

Genügt es, in dieser Scheibe nur den Vergleich-Hub umzubauen und die Trip-Parität erst in Folgescheiben zu liefern?

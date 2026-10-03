---
spec_file: docs/specs/modules/feat_2284_s1_subscription_header.md
spec_sha256: 14c165c3f103de2e80e5f03e53ba1755869079de51c8572ae1628f87f2f00fac
---

# PO-Briefing: feat-2284-hub-kopf-paritaet

- **Spec:** docs/specs/modules/feat_2284_s1_subscription_header.md
- **Issue:** #2284
- **Erstellt:** 2026-10-03

## Was gebaut wird

Der Kopf des Vergleich-Hubs wird auf einen gemeinsamen Baustein umgebaut; für Nutzer ändert sich nichts Sichtbares.

## Definition of Done

Name, Region und Profil lassen sich im Vergleich-Hub wie bisher bearbeiten, Fehler erscheinen am Feld, bestehende Browser-Tests bleiben grün.

## Wie geprüft wird

Automatische Tests prüfen Bausteinaufbau; Speichern und Fehlerfälle prüfen nur Browser-Tests, die Trip-Seite wird nicht geprüft.

## Kritische Anmerkungen

- Konfliktfall („Nochmal speichern“ bei Zwei-Tab-Bearbeitung) hat keine eigene Prüfbedingung; Schutz hängt nur an Bestandstests.
- Trip-Region, Aktivität im Kopf und Speicher-Chip-Ort folgen erst in Scheibe S2.
- Ein bestehender Browser-Test wird eingegrenzt (PO-Entscheid); Prüfaussage bleibt gleich.

## Freigabe-Frage

Genügt es, in dieser Scheibe nur den Vergleich-Hub umzubauen und die Trip-Parität erst in Folgescheiben zu liefern?

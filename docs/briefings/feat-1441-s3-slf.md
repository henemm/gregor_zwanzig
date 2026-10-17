---
spec_file: docs/specs/modules/feat_1441_s3_slf.md
spec_sha256: 3222832907460fbc513307e148da4d54ede48c2f042c236339b162b55d71499b
spec_frozen_sha256: cbf2a0872abbecede462fb875a99e797782743316a34be3ab3d4318092289be1
---

# PO-Briefing: feat-1441-s3-slf

- **Spec:** docs/specs/modules/feat_1441_s3_slf.md
- **Issue:** #1441
- **Erstellt:** 2026-10-17

## Was gebaut wird

Der amtliche Schweizer Lawinen-Lagebericht des SLF erscheint wie die österreichischen Berichte in allen vier Kanälen, inklusive Entwarnung.

## Definition of Done

Ein Schweizer Wegpunkt zeigt in allen vier Kanälen Lawinenstufe und Quelle; außerhalb der Saison bleibt es still, ohne Fehlermeldung.

## Wie geprüft wird

Aufgezeichnete Winterberichte laufen durch die echten Kanäle; nicht bewiesen ist ein echter Live-Abruf, den es erst zur Wintersaison gibt.

## Kritische Anmerkungen

- SLF-Lizenz ungeklärt: Betrieb auf Ihre Entscheidung, Anfrage läuft; bei Ablehnung wird die Quelle abgeschaltet.
- Stufe 4, 5 und Entwarnung nur mit abgewandelten Testdaten belegt; Issue bleibt bis zum Live-Beleg offen.
- Fällt das SLF im Mittelland aus, erscheint ein Ausfallhinweis, obwohl dort nie Berichte existieren.

## Freigabe-Frage

Soll die Schweizer SLF-Anbindung freigegeben werden, obwohl Lizenzanfrage offen ist und der Live-Beleg erst zur Wintersaison kommt?

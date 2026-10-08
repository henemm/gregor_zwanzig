---
spec_file: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
spec_sha256: f37ab817ac0caf60839fd69fd72ff1c9af2d25fa25a5c42d63e0ce79dd62b86a
---

# PO-Briefing: feat-1539-s1b-s2-abruf-baustein

- **Spec:** docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
- **Issue:** #1539
- **Erstellt:** 2026-10-08

## Was gebaut wird

Parallele Wetter- und Warnabrufe werden abgesichert und ein gemeinsamer begrenzter Abruf-Baustein bereitgestellt, jedoch noch von keinem Trip genutzt.

## Definition of Done

Gleichzeitige Zugriffe lösen je Warnquelle und Wetterpunkt genau einen Abruf aus, und das Tageskontingent wird bei parallelen Buchungen exakt gezählt.

## Wie geprüft wird

Automatische Tests mit gleichzeitigen Zugriffen weisen jede Anforderung nach; Alarm-Abbrüche und Lastverhalten im echten Betrieb werden nicht geprüft.

## Kritische Anmerkungen

- Alarm-Abbrüche sinken durch diesen Workflow nicht; erst die spätere Umstellung (S3) bringt Nutzen, #1539 bleibt offen.
- Bei Sperr-Timeout wird trotzdem erlaubt und nur gezählt; Nutzer-Grenzen können um bis zu N−1 Abrufe überschießen.
- Parallelitäts-Grenzen (3/1/4) sind ungemessen, die maximale Wartezeit ist nicht beziffert.

## Freigabe-Frage

Genügt dir ein reiner Unterbau, dessen Nutzen bei Alarm-Abbrüchen erst mit der Folgelieferung messbar wird?

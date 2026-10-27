---
spec_file: docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
spec_sha256: 6ee64709d48ad9d89be386c932a5c57ac67a991ed677067c8b6131a76565ec8a
---

# PO-Briefing: fix-2375-compare-konfliktschutz

- **Spec:** docs/specs/bugfix/compare_konfliktschutz_teilfelder.md
- **Issue:** #2375 (löst #2381 mit)
- **Erstellt:** 2026-09-29

## Was gebaut wird

Im Ortsvergleich geht eine Änderung aus einem zweiten Tab beim Speichern nicht mehr verloren; Konflikte werden sofort erkannt.

## Definition of Done

Bei Änderungen in zwei Tabs stehen nach "Nochmal speichern" beide Änderungen im Ortsvergleich, auch nach Neuladen.

## Wie geprüft wird

Automatische Zwei-Tab-Browsertests belegen, dass fremde Änderungen überleben; Einzeltests prüfen nur die Sendeform, nicht das Zusammenspiel.

## Kritische Anmerkungen

- Ticket-Wunsch "zeigen, was fremd geändert wurde" fehlt: Der Kopf zeigt einen fremd geänderten Namen erst nach Neuladen.
- Wer dieselbe Einstellung gleichzeitig ändert, überschreibt weiterhin den anderen; nur verschiedene Felder sind geschützt.
- Zusätzlich umgestellt: Pausieren und Kopf-Änderungen; Pausieren auf der Listenseite bleibt ohne Konfliktprüfung.

## Freigabe-Frage

Reicht es, dass nur verschiedene Felder geschützt sind und der Kopf fremde Namen erst nach Neuladen zeigt?

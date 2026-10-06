---
spec_file: docs/specs/modules/fix_2047_s2_ci_prod_gate.md
spec_sha256: 9b06f75ee4c03ae02c95b74bb5cc5428e2433308beed70f07c29ef284f05df7d
---

# PO-Briefing: fix-2047-s2-prod-gate

- **Spec:** docs/specs/modules/fix_2047_s2_ci_prod_gate.md
- **Issue:** #2047
- **Erstellt:** 2026-10-06

## Was gebaut wird

Die automatische Auslieferung nach Produktion liefert denselben Stand nie doppelt aus, läuft nie parallel und prüft sich danach selbst.

## Definition of Done

Ein bereits ausgelieferter Stand startet keine Dienste neu, jede automatische Auslieferung endet mit bestandenem Selbsttest, und Telegram unterscheidet ausgeliefert, bereits ausgeliefert, fehlgeschlagen.

## Wie geprüft wird

Automatische Tests prüfen Ablaufdatei und Skript mit Ersatz-Verbindungen; eine echte Auslieferung auf Produktion wird dadurch nicht nachgewiesen.

## Kritische Anmerkungen

- Bei fehlendem Nachweis (Normalfall) bleibt Telegram stumm; der ursprünglich verlangte Hinweis „nicht ausgeliefert" entfällt.
- Doku-Anforderungen (Architekturentscheid, Playbook, Nachweis-Pfad) haben keinen eigenen Test, nur der ADR-Index wird geprüft.
- Das Auslieferungsskript liegt im Infra-Repo und wirkt sofort live; Reihenfolge muss stimmen, sonst doppelte Neustarts.

## Freigabe-Frage

Gibst du die verkleinerte Spec frei, obwohl bei fehlendem Nachweis keine Telegram-Meldung kommt?

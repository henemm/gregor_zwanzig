---
spec_file: docs/specs/modules/fix_2047_s2_ci_prod_gate.md
spec_sha256: 34059045108cb0403b9f77fa0f80dcd403d46379b667476ced3634dbf5eed736
---

# PO-Briefing: fix-2047-s2-prod-gate

- **Spec:** docs/specs/modules/fix_2047_s2_ci_prod_gate.md
- **Issue:** #2047
- **Erstellt:** 2026-10-07

## Was gebaut wird

Automatische Auslieferung nach Produktion startet denselben Stand nie doppelt, läuft nie parallel und prüft sich selbst.

## Definition of Done

Bereits ausgelieferter Stand startet keine Dienste neu, Selbsttest läuft nach jeder Auslieferung, Telegram meldet ausgeliefert, bereits ausgeliefert oder fehlgeschlagen.

## Wie geprüft wird

Tests prüfen Ablaufdatei und Skript mit Ersatz-Verbindungen; echte Auslieferung auf Produktion weisen sie nicht nach.

## Kritische Anmerkungen

- Ohne Nachweis (Normalfall) schweigt Telegram; der verlangte Hinweis „nicht ausgeliefert" entfällt.
- Doku-Anforderungen haben keinen eigenen Test; nur der Architektur-Index wird geprüft.
- Auslieferungsskript wirkt sofort live; falsche Reihenfolge verursacht doppelte Neustarts.

## Freigabe-Frage

Gibst du die verkleinerte Spec frei, obwohl ohne Nachweis keine Telegram-Meldung kommt?

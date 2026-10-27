---
spec_file: docs/specs/modules/staging_seed_endpoint.md
spec_sha256: fd9f4f1b6b5ac89be2ed8e040c9476c10a31992425afdd9d5cfd991c846ac043
---

# PO-Briefing: feat-2423-staging-seed-endpoint

- **Spec:** docs/specs/modules/staging_seed_endpoint.md
- **Issue:** #2423
- **Erstellt:** 2026-09-25

## Was gebaut wird

Ein reiner Testzugang auf Staging, der Tarif und SMS-Tageszähler des eigenen Testkontos auf Wunschwerte setzt.

## Definition of Done

Auf Staging setzt ein angemeldetes Testkonto Tarif und Zähler per Aufruf, die Kontingent-Anzeige zeigt diese Werte, auf Produktion antwortet der Aufruf mit „nicht gefunden".

## Wie geprüft wird

Automatische Tests belegen Sperre auf Produktion, Nutzertrennung und Anzeige-Werte; ob die echte Produktion sich so verhält, beweist erst der Deploy-Selbsttest.

## Kritische Anmerkungen

- Einzige Sperre gegen Tarifwechsel ohne Admin-Freigabe ist die Umgebungseinstellung „Staging"; ist sie auf Produktion falsch gesetzt, greift doppelte Sperre nur teilweise.
- Reiner Tarif-Aufruf bei Core-Ausfall liefert stillen Erfolg ohne Zählerwerte; Ticket verlangte keinen Fehlerfall, Spec widerspricht eigener „kein stilles OK"-Regel.
- Ticket sprach von Admin-Endpoint; Spec erlaubt jedem angemeldeten Staging-Nutzer, nur das eigene Konto zu ändern.

## Freigabe-Frage

Darf dieser Staging-Testzugang gebaut werden, damit die Kontingent-Anzeige aus #2412 danach auf Staging prüfbar ist?

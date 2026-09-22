---
spec_file: docs/specs/modules/forecast_go_pfad_kontingent.md
spec_sha256: 59bcb1a5098f98906bdc84c594ca61e5ab8b8eea374fd4bade93bf1d38368f0f
---

# PO-Briefing: feat-2391-forecast-kontingent-deckel

- **Spec:** docs/specs/modules/forecast_go_pfad_kontingent.md
- **Issue:** #2391 (Teilstück S3 von #2150, Epic #2138)
- **Erstellt:** 2026-09-21

## Was gebaut wird

`/api/forecast` ruft Wetterdaten direkt ab, am Kontingent-Wächter vorbei. Er wird jetzt daran angeschlossen: vor jedem Abruf wird geprüft, ob noch Kontingent übrig ist.

## Definition of Done

Ein Vielnutzer kann darüber nicht mehr das Tageskontingent aller anderen leerräumen — ab einem Punkt kommt eine Absage. Fällt die Kontrolle aus, läuft der Betrieb normal weiter.

## Wie geprüft wird

Automatisierte Tests in Go und Python mit zwei simulierten Nutzern. Kein echter Live-Test mit zwei Nutzern.

## Kritische Anmerkungen

- **Wichtigster Punkt:** Der Titel von #2150 spricht von einem "Deckel je Konto" — klingt nach eigenem Vollkontingent pro Nutzer. Das wird hier bewusst **nicht** gebaut (in #2387 verworfen, hätte das Schutzlimit vervielfacht). Stattdessen erweitert dies nur den bestehenden, fair verteilten gemeinsamen Topf um diesen Weg.
- Nebenpunkte: pauschal 2 Einheiten je Abruf gebucht; kein erkennbarer Frontend-Nutzer; ein ähnlicher blinder Fleck (Scheduler) folgt separat; minimal mehr Wartezeit je Abruf.

## Freigabe-Frage

Ist es okay, dass **kein eigenes Kontingent je Konto** entsteht, sondern nur der bestehende faire gemeinsame Topf erweitert wird?

# Öffentliche Funktionsübersicht und Level-Darstellung

> Stand: 2026-11-24 · Spec: `docs/specs/modules/oeffentliche_doku_3319.md` · Issue #3319 (Epic #3318)
> Vorgänger: `docs/specs/modules/oeffentliche_startseite_2520.md` (AC-6 abgelöst durch #3319)

## Was es ist

Besucher ohne Anmeldung sehen auf der Startseite (`/`) alle vier Kanäle (E-Mail, Telegram, SMS,
Premium-SMS über Garmin inReach) als verfügbar und eine Level-Kurzübersicht Free/Standard/Premium.
Die Funktionsübersicht `/funktionen` erklärt die Funktionen in neun Unterseiten, zweisprachig DE/EN.

## Öffentliche Pfade

- Exakte Pfade, kein Präfix-Vergleich: `/`, `/funktionen`, `/funktionen/<slug>` für jede Seite der Liste.
- Quelle der Liste: `frontend/src/lib/funktionen_seiten.ts` (Übersicht, Navigation und Hook nutzen dieselbe Liste).
- Die Sprache folgt dem Cookie `gz_lang`, dann `Accept-Language`, sonst Deutsch. Es gibt kein `/en/`-Präfix.
- Unbekannter Slug: für Angemeldete 404, für Abgemeldete die Anmeldeseite (wie jeder nicht freigegebene Pfad).
- Die Seiten laden keine Nutzerdaten und rufen keine API auf; sie tragen keinen Mandanten-Header.

Die Auth-Grenze steht in `frontend/src/hooks.server.ts` (Set `OEFFENTLICHE_SEITEN`).

## Unterseiten

| Slug | Thema |
|---|---|
| `trips` | Trips planen |
| `briefings` | Wetter-Briefings |
| `alarme` | Alarme und Warnungen |
| `ortsvergleich` | Ortsvergleich |
| `kanaele` | Kanäle und Zustellung |
| `befehle` | Antwort-Befehle |
| `wetterdaten` | Wetterdaten und Modelle |
| `konto` | Konto und App |
| `level` | Free, Standard, Premium |

Jede Unterseite hat Brotkrumen, Themen-Navigation, Weiter/Zurück und eigene Meta-Beschreibung.
Die Texte liegen im Katalog `frontend/src/lib/i18n/messages/{de,en}/funktionen.json`.

## Level-Zahlen: eine Quelle

- Alle Level-Grenzen stehen in `frontend/src/lib/level_grenzen.json` (`null` = unbegrenzt).
- Die Kataloge enthalten nur Platzhalter, keine Zahlen.
- Zwei Drift-Tests binden die JSON an den Code:
  - Go: `internal/model/tier_katalog_drift_test.go`
  - Python: `tests/test_level_grenzen_drift.py`
- Jeder Test hat eine Gegenprobe: ein verfälschter Wert muss rot werden.

## Bilder

- Renderer-Bilder (E-Mail, Telegram, SMS, Premium-SMS, Alarm): `scripts/landing_screenshots.py --funktionen`.
- Oberflächen-Bilder vom Staging-Prüfkonto: `scripts/funktionen_screenshots.py`.
- Ablage: `frontend/static/funktionen/` (DE) und `frontend/static/funktionen/en/` (EN), WebP, je unter 200 KB.
- Neuerzeugung und Sichtprüfung auf Personendaten: `docs/runbooks/funktionen_screenshots.md`.

## Änderungen

- 2026-11-24: Erstfassung mit Startseite, Level-Übersicht, Funktionsseiten DE/EN (Issue #3319)

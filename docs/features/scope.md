# Gregor Zwanzig – Scope

## Codename
Gregor Zwanzig

## User
- Primärer Nutzer: Henning (Hiker/PO) und zukünftig weitere Weitwanderer.
- Nutzungskontext: Mehrtägige Treks (z. B. GR20), eingeschränkte Konnektivität, kurze Nachrichtenkanäle.

## Problem
Während mehrtägiger Outdoor-Touren rechtzeitig und verlässlich vor gefährlichem Wetter gewarnt werden, ohne selbst permanent Forecasts prüfen zu müssen.

## Lösung (High-Level)
Ein automatisiertes System, das Wetterdaten aus mehreren Quellen abruft, normalisiert, Risiko-Regeln anwendet und kompakte Status-/Warnmeldungen versendet (E-Mail; später optional SMS/Push). Meldungen sind kurz, robust und auch bei schlechter Konnektivität zustellbar.

## Ziele (MVP) — DONE
- Abendbericht: Prognose für die **nächste Etappe**.
- Morgenbericht: aktualisierte Prognose (Letzte Änderungen, Risiken).
- Untertagswarnung: zusätzliche Warnung bei signifikanter Verschlechterung (z. B. Gewitteranstieg).

## Ziele (v2) — Geplant
- Kompakt-Summary: 3-5 Zeilen Kurzfassung fuer schnelle Erfassung (F2)
- Multi-Day Trend: 3-5 Tage Vorschau im Evening-Report (F3)
- Biwak-/Zelt-Modus: Erweiterte Nacht-Details fuer Zelter (F5)
- Trip-Briefing: Einmaliger Gesamt-Report am Vorabend (F4)
- SMS + Satellite Delivery (F1, F9)

## Nicht-Ziele (v1)
- Keine eigene meteorologische Modellierung.
- Kein „alles für alle Sportarten"; Fokus: Trekking/Gebirge.
- Keine paternalistischen Empfehlungen (Go/No-Go, Timing) — User entscheidet selbst.
- Kein Trip-Sharing, kein Wetter-Tagebuch.

## Datenquellen (Start)
- MET Norway (primär), DWD/MOSMIX optional, AROME optional.
- Abstraktionsschicht: Provider-Adapter + Normalisierung.

## Kommunikationskanäle
- E-Mail/SMTP (done, MVP)
- SMS via Gateway (F1, geplant Q2 2026)
- Garmin inReach Email-Bridge (F9, geplant Q2 2026, setzt Kompakt-Summary F2 voraus)

## Steuerung
- Asynchrone Trip-Umplanung per SMS/Email-Reply (F6, geplant Q3 2026)
- Kein UI noetig — Low-Connectivity-Paradigma

## Debug & Konsistenz
- Debug-Infos werden **konsistent** erzeugt: eine gemeinsame Debug-Struktur liefert identische Inhalte für Console und E-Mail (Console darf zusätzlich ausführlicher sein).
- CLI bietet Schalter (z. B. `--report`, `--channel`, `--dry-run`, `--config`), fällt bei fehlenden Optionen auf Konfiguration zurück.

## Qualitätskriterien
- TDD, kleine Commits, Live-Verifikation (echter Versand/echte Daten), klarer Rollback-Pfad.

## Acceptance Criteria (MVP)
- Abend- und Morgenbericht mit realen Forecast-Daten und echtem Versand möglich.
- Untertagswarnung triggerbar (konfigurierbare Schwellen).
- Debug-Infos in E-Mail stimmen **1:1** mit den entsprechenden Console-Zeilen überein.

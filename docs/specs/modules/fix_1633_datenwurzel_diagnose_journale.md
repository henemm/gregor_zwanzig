---
entity_id: fix_1633_datenwurzel_diagnose_journale
type: module
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [observability, data-root, diagnostics, adr-0018, regression]
---

<!-- Issue #1633 — Rest von #1595; blockiert #1628 -->

# Fix #1633 — Diagnose-Journale auf die Produktiv-Datenwurzel zurückholen

## Approval

- [x] Approved — PO-„go" 2026-08-09 (ACs auf Deutsch vorgelegt und freigegeben; Beleg als
      Kommentar an Issue #1633)

## Purpose

Vier fest verdrahtete, repo-relative `Path("data/…")`-Konstanten im Python-Kern haben den
Datenwurzel-Umzug nach `/var/lib/gregor` (#1595) nicht mitgemacht. Dadurch schreibt der
Python-Kern seine Diagnose-Journale in den Programmordner, während die Go-API sie an der
Produktiv-Datenwurzel liest — dort sind sie eingefroren. Die Ausfallüberwachung meldet seit
dem 2026-08-08 nachweislich falsche Werte; das von ADR-0018 Punkt 3 zwingend geforderte
Health-Signal ist wirkungslos.

## Source

- **File:** `src/providers/call_log.py` — `DIAGNOSTICS_PATH` (Zeile 21)
- **File:** `src/providers/openmeteo.py` — `DIAGNOSTICS_PATH` (Zeile 78), `AVAILABILITY_CACHE_PATH` (Zeile 204)
- **File:** `src/services/official_alerts/warn_egress.py` — `WARN_CALLS_PATH` (Zeile 100)

Alle vier liegen im **Python-Core** (`src/providers/`, `src/services/`). Die Go-Seite ist
**nicht** betroffen — sie liest korrekt über `config.DataDir` aus `GZ_DATA_DIR` und wurde in
`ae0553b3` bereits nachgezogen (`internal/provider/openmeteo/calllog.go`). Kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~40–60 (Code ~15, Tests ~30)
- **Files:** 3 geändert, 1 Testdatei neu
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_root()` | intern | Kanonische Auflösung `_DATA_ROOT` > `GZ_DATA_DIR` > `data` |
| `internal/scheduler/briefing_health.go` | Go-Leser | liest `<DataDir>/diagnostics/openmeteo_calls.jsonl` |
| `internal/scheduler/warn_service_health.go` | Go-Leser | liest `<DataDir>/diagnostics/warn_service_calls.jsonl` |
| ADR-0018 | Entscheidung | fordert das wachsende Health-Signal, das hier tot ist |

## Implementation Details

Muster exakt wie in `ae0553b3` (#1595) — **Auflösung im Rumpf, niemals im Default-Argument
oder als Modul-Konstante mit Initialisierer**. Eine Modul-Konstante wird beim Import gebunden,
also vor jeder Testfixture; das hebelt die Isolationsfixture `_DATA_ROOT` (#1133) aus und war
in `ae0553b3` der Grund, dieselbe Umstellung auf der Go-Seite vorzunehmen.

```
# vorher (Modul-Konstante, früh gebunden):
DIAGNOSTICS_PATH = Path("data/diagnostics/openmeteo_calls.jsonl")

# nachher (Funktion, bei jedem Zugriff aufgelöst):
def diagnostics_path() -> Path:
    from app.loader import get_data_root
    return get_data_root() / "diagnostics" / "openmeteo_calls.jsonl"
```

Gleiches Muster für `WARN_CALLS_PATH` und `AVAILABILITY_CACHE_PATH` (letztere unter
`get_data_root() / "cache" / "model_availability.json"`).

**Datenübernahme (einmalig, außerhalb des Codes):** Die im Programmordner aufgelaufenen Zeilen
werden nach Zeitstempel sortiert an die Journale unter der Produktiv-Datenwurzel **angehängt**
(append-only, kein Überschreiben), damit die Historie nicht reißt. Danach wird der verwaiste
Ordner entfernt. Reversibel: die Quelldateien bleiben bis zur bestätigten Übernahme liegen.

## Expected Behavior

- **Input:** Ein beliebiger Open-Meteo-Abruf bzw. Warn-Dienst-Abruf im Python-Kern.
- **Output:** Eine JSONL-Zeile im Journal **unter der Datenwurzel aus `GZ_DATA_DIR`**.
- **Side effects:** Keine fachliche Verhaltensänderung. Kein zusätzlicher Netzverkehr.
  Nach der Übernahme meldet `/api/scheduler/status` wieder frische Werte.

## Acceptance Criteria

- **AC-1:** Given `GZ_DATA_DIR` zeigt auf ein Verzeichnis abseits des Programmordners / When der
  Python-Kern einen Open-Meteo-Abruf protokolliert / Then landet die Zeile unter
  `$GZ_DATA_DIR/diagnostics/openmeteo_calls.jsonl` und **nicht** in einem `data/`-Ordner relativ
  zum Arbeitsverzeichnis.
  - Test: Abruf mit gesetztem `GZ_DATA_DIR` auf ein temporäres Verzeichnis auslösen, Zielpfad
    auf die neue Zeile prüfen **und** gegenprüfen, dass kein `data/diagnostics/` neben dem
    Arbeitsverzeichnis entstanden ist.

- **AC-2:** Given dieselbe Vorbedingung / When ein Warn-Dienst-Abruf protokolliert wird / Then
  landet die Zeile unter `$GZ_DATA_DIR/diagnostics/warn_service_calls.jsonl`.
  - Test: wie AC-1 für den Warn-Dienst-Pfad.

- **AC-3:** Given dieselbe Vorbedingung / When der Modell-Verfügbarkeits-Cache geschrieben wird /
  Then landet die Datei unter `$GZ_DATA_DIR/cache/model_availability.json`.
  - Test: wie AC-1 für den Cache-Pfad.

- **AC-4:** Given ein Test setzt die Isolationsfixture `_DATA_ROOT` auf ein temporäres
  Verzeichnis / When eines der drei Journale geschrieben wird / Then folgt der Schreibvorgang
  dieser Fixture und berührt den echten Datenbestand nicht.
  - Test: Beweist, dass die Auflösung **zur Laufzeit** und nicht beim Import erfolgt — ein
    Import vor dem Setzen der Fixture darf das Ergebnis nicht festlegen.

- **AC-5:** Given im Repo existiert eine `Path("data/…")`-Konstante in `src/` oder `api/` /
  When die Testsuite läuft / Then schlägt ein Wächter-Test fehl und benennt Datei und Zeile.
  - Test: Der Wächter findet die vier heutigen Fundstellen **vor** dem Fix (rot) und keine
    danach (grün). Ausnahmen nur mit begründetem Zeilenkommentar, Muster wie `gz-main-path`.
  - *Regel-Budget: neuer Wächter, **Prüfdatum 2026-11-07**. Fang-Beleg bei Einführung: die vier
    Fundstellen dieses Issues, drittes Auftreten desselben Musters nach #1265 und #1595. Am
    Prüfdatum ohne neuen Fang → Rückbau.*

- **AC-6:** Given der Fix ist ausgeliefert und die aufgelaufenen Zeilen sind übernommen / When
  `/api/scheduler/status` abgefragt wird / Then liegt `warn_service_health.<dienst>.last_attempt_at`
  für einen aktiven Dienst **innerhalb der letzten Stunde**, statt auf einem Tag in der
  Vergangenheit stehenzubleiben.
  - Test: Verifikation gegen Staging bzw. Produktion nach dem Deploy — der eigentliche
    Wirkungsnachweis. Ein grüner Schreibtest allein beweist die Heilung **nicht**.

- **AC-7:** Given die Datenübernahme läuft / When sie abgeschlossen ist / Then enthält das
  Zieljournal alle vorher in beiden Kopien vorhandenen Zeilen, aufsteigend nach Zeitstempel,
  ohne Verlust und ohne Dublette.
  - Test: Zeilenzahl vorher (Summe beider Kopien) gegen Zeilenzahl nachher; Stichprobe auf
    Zeitstempel-Monotonie.

## Nicht in dieser Scheibe

- Rotation der Journale (`warn_service_calls.jsonl`: 370k Zeilen / 57 MB, rotiert nie) —
  bestehendes, bewusst akzeptiertes Problem, eigener Auftrag.
- Der eigentliche NowCast-Sichtbarkeits-Fix (#1628) — folgt nach diesem Fix.
- Nutzer-Datenpfade (`data/users/…`) — durch #1595/#1602 bereits erledigt.

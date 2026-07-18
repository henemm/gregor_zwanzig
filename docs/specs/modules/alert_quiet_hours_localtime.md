---
entity_id: alert_quiet_hours_localtime
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [alerts, quiet-hours, timezone, bugfix, issue-1312, epic-1301]
---

<!-- Issue #1312 — Scheibe D1 von Epic #1301 (#1292 P7) -->

# Stille Stunden in Lokalzeit (D1 — Bugfix)

## Approval

- [ ] Approved

## Purpose

Die „Stillen Stunden" für Alarme (`is_quiet_hours`) vergleichen die vom Nutzer
in gefühlter Lokalzeit eingegebene Uhrzeit (z. B. „22:00–06:00") bisher gegen
**UTC**, weil alle sechs Aufrufstellen `now` in UTC übergeben. Im Sommer
(Europe/Vienna = UTC+2) verschiebt das die tatsächlich wirksame Ruhezeit auf
00:00–08:00 Lokalzeit: Zwischen 22:00 und 24:00 Uhr Ortszeit gehen Alarme
fälschlich raus, zwischen 6:00 und 8:00 Uhr Ortszeit werden sie fälschlich
unterdrückt. D1 behebt das **einmal zentral** in `is_quiet_hours`, indem
`now` vor dem Vergleich nach Europe/Vienna konvertiert wird — Vorbild
`alert_daily_limit.py`, das dieselbe Konvention bereits für den
Tageszähler-Reset nutzt.

## Source

- **File:** `src/services/deviation_alert_engine.py:72-83`
- **Identifier:** `DeviationAlertEngine.is_quiet_hours` (staticmethod)

> Schicht: Python-Core/Domain-Backend (`src/services/`) — kein Go-/Frontend-Bezug.

## Estimated Scope

- **LoC:** ~10 (Konvertierung + Import + Docstring in `is_quiet_hours`)
- **Files:** 1 Quelldatei (`deviation_alert_engine.py`) + bis zu 6 Testdateien
  (Audit, s. u.; nicht alle brauchen zwingend Änderungen)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_daily_limit.py:9-30` | Vorbild | `VIENNA = ZoneInfo("Europe/Vienna")`, `now.astimezone(VIENNA)`; `now` bleibt Funktionsparameter, kein `datetime.now()` im Modul — D1 übernimmt exakt dieses Muster |
| `deviation_alert_engine.py:226` (`DeviationAlertEngine.evaluate`) | Aufrufer 1 (Δ-Wächter) | übergibt UTC an `is_quiet_hours` — **unverändert**, profitiert automatisch vom zentralen Fix |
| `compare_official_alert.py:107` | Aufrufer 2 | `datetime.now(timezone.utc)` — **unverändert** |
| `compare_radar_alert.py:103` | Aufrufer 3 | `datetime.now(timezone.utc)` — **unverändert** |
| `trip_alert.py:161, :653, :986` (via `_is_quiet_hours`-Wrapper `:394-410`) | Aufrufer 4-6 | `datetime.now(timezone.utc)` / `now_utc` — **unverändert** |
| `tests/tdd/test_alert_cooldown_quiet.py` | Bestandstest | Kern-Testfälle für `is_quiet_hours`/`_is_quiet_hours` — Audit s. u. |

Alle sechs Aufrufstellen bleiben **unverändert** — sie übergeben weiterhin
aware UTC-Zeitstempel. Die Konvertierung passiert ausschließlich innerhalb
von `is_quiet_hours` selbst, damit kein Aufrufer den Fix vergessen oder
doppelt anwenden kann.

## Implementation Details

```python
# src/services/deviation_alert_engine.py — is_quiet_hours (Z. 72-83)
from datetime import timezone as timezone  # bereits importiert
from zoneinfo import ZoneInfo

VIENNA = ZoneInfo("Europe/Vienna")  # Vorbild alert_daily_limit.py:21


class DeviationAlertEngine:
    @staticmethod
    def is_quiet_hours(
        now: datetime, quiet_from: Optional[str], quiet_to: Optional[str]
    ) -> bool:
        """Prüft, ob `now` (in Europe/Vienna-Lokalzeit) innerhalb des
        konfigurierten Ruhezeit-Fensters liegt — inkl. Mitternachts-Wrap.

        Issue #1312 (Scheibe D1): `now` wird VOR dem Vergleich nach
        Europe/Vienna konvertiert, weil Nutzer die Uhrzeiten in gefühlter
        Lokalzeit eingeben. Naive datetimes (kein tzinfo) werden als UTC
        interpretiert (konservativ, deckungsgleich mit dem bisherigen
        De-facto-Verhalten aller sechs Aufrufer). DST wird durch ZoneInfo
        automatisch korrekt behandelt (Sommer +2h, Winter +1h).
        """
        if not quiet_from or not quiet_to:
            return False
        aware_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        local_now = aware_now.astimezone(VIENNA)
        # time_type = Import-Alias des Moduls (deviation_alert_engine.py:20:
        # `from datetime import time as time_type`) — Bestandscode, unveraendert.
        from_time = time_type.fromisoformat(quiet_from)
        to_time = time_type.fromisoformat(quiet_to)
        current = local_now.time()
        if from_time > to_time:
            return current >= from_time or current < to_time
        return from_time <= current < to_time
```

Die Mitternachts-Wrap-Logik (`if from_time > to_time: ...`) bleibt **byte-für-byte
unverändert** — es ändert sich ausschließlich, welcher Zeitwert (`current`)
in den Vergleich eingeht.

## Bestandstest-Audit (Pflichtabschnitt)

Alle Kern-Tests verwenden feste aware-UTC-Zeitstempel (kein `datetime.now()`
in Kern-Tests) — Vienna liegt 2026 während der Sommerzeit (CEST, UTC+2) vom
29.03. bis 25.10. Für jeden gefundenen Fall gilt: bleibt das Ergebnis nach
der Konvertierung gleich, ändert sich der Test nicht. Kippt es, MUSS die
Erwartung mit Docstring-Begründung umgestellt werden (keine stillen Umbauten).

| Datei:Zeile | Fall | UTC-Eingabe | Vienna-Lokalzeit (Fix) | Alt-Ergebnis | Neu-Ergebnis | Aktion |
|---|---|---|---|---|---|---|
| `test_alert_cooldown_quiet.py:102` (AC-4) | Wrap aktiv, Fenster 22:00–07:00 | 2026-06-15 23:30 UTC | 2026-06-16 01:30 (CEST) | True | True | **unverändert** — beide Zeitwerte liegen im Wrap-Bereich |
| `test_alert_cooldown_quiet.py:114` (AC-5) | Wrap beendet | 2026-06-16 07:01 UTC | 09:01 (CEST) | False | False | **unverändert** |
| `test_alert_cooldown_quiet.py:126` (AC-6) | Normalfenster 08:00–22:00 | 2026-06-15 15:00 UTC | 17:00 (CEST) | True | True | **unverändert** |
| `test_alert_cooldown_quiet.py:187` (Grenzwert) | exakt `to`=07:00 | 2026-06-16 07:00 UTC | 09:00 (CEST) | False | False | Ergebnis **unverändert**, prüft aber nach dem Fix keine echte Zeitgrenze mehr (09:00 liegt nicht mehr am Rand des Fensters). Optionale Schärfung: UTC-Eingabe auf das Vienna-Äquivalent der Grenze (05:00 UTC → 07:00 CEST) verschieben, damit der Test seinen ursprünglichen Zweck (Grenzwert `< to_time`, nicht `<=`) weiter belegt. Kein Pflicht-Fix (kein Rot-Risiko), aber Docstring sollte den Bedeutungsverlust vermerken, falls nicht geschärft. |
| `test_alert_cooldown_quiet.py:199` / `:211` (kein Setting / Halbkonfiguration) | early return vor jeder Zeitkonvertierung | beliebig | — | False | False | **unverändert** — `if not quiet_from or not quiet_to: return False` greift vor der Konvertierung |
| `test_issue_1168_alert_engine_extract.py:335` (AC-2 Teil 1) | Wrap 22:00–06:00, fixer Zeitpunkt | 2026-04-05 23:30 UTC | 2026-04-06 01:30 (CEST, DST bereits seit 29.03. aktiv) | True | True | **unverändert** |
| `test_issue_1168_alert_engine_extract.py:347-359` (AC-2 Teil 2) | dynamisches Fenster ±1h um `datetime.now(timezone.utc)`, End-to-End über `check_and_send_alerts()` | echte Wanduhrzeit | UTC-Wert + 1h (Winter) bzw. + 2h (Sommer) | True (immer, Fenster ist per Konstruktion um UTC-`now` zentriert) | **bricht im Sommer** (CEST-Offset +2h > Puffer ±1h → Lokalzeit fällt außerhalb des Fensters, Test wird flaky/rot je nach Jahreszeit) | **MUSS geändert werden:** Fenster künftig um die Vienna-lokale „jetzt"-Zeit legen (`datetime.now(VIENNA)` bzw. `datetime.now(timezone.utc).astimezone(VIENNA)`) statt um UTC-`now`, mit Docstring-Verweis auf #1312 |
| `test_compare_radar_alert.py:146-156` (`_quiet_hours_window_now`, genutzt in `:365` AC-5) | dynamisches Fenster ±3 Min um `datetime.now(timezone.utc)` | echte Wanduhrzeit | UTC-Wert + 1h/+2h | True (immer, analog oben) | **bricht ganzjährig** (Puffer ±3 Min ≪ jeder mögliche Vienna-Offset von 60/120 Min) | **MUSS geändert werden:** Helper auf Vienna-lokale „jetzt"-Zeit umstellen, Docstring-Begründung mit #1312-Verweis; Puffer kann bei 3 Min bleiben, sobald das Zentrum stimmt |
| `test_issue_883_acute_danger_override.py:358-368` (AC-5 Guard) | dynamisches Fenster ±2h um `datetime.now(timezone.utc)` | echte Wanduhrzeit | UTC-Wert + 1h/+2h | True (immer) | Grenzwertig: bei CEST (+2h) liegt die Vienna-Zeit exakt am oberen Fensterrand (`< to_time` strikt) → **potenziell flaky im Sommer** | Empfehlung: analog zu den beiden Fällen oben auf Vienna-lokale „jetzt"-Zeit umstellen, um den Rand-Fall strukturell auszuschließen (kein reiner Zufallstreffer mehr) |
| `test_compare_official_alert.py:584-610` (AC-1, #1233-Repro) | Wrap 22:00–06:00, `datetime`-Klasse via `monkeypatch` eingefroren | 2026-07-12 00:00 UTC | 02:00 (CEST) | True | True | **unverändert** — beide Werte liegen im Wrap-Bereich (22:00–06:00) |
| `test_throttle_store.py:483` | nur Docstring-Erwähnung, kein `is_quiet_hours`-Aufruf | — | — | — | — | keine Aktion |

**Zusammenfassung:** Drei Dateien mit dynamisch um `datetime.now(timezone.utc)`
gelegten Ruhezeit-Fenstern (`test_issue_1168_alert_engine_extract.py`,
`test_compare_radar_alert.py`, `test_issue_883_acute_danger_override.py`)
konstruieren ihr Fenster bislang um den UTC-Zeitpunkt statt um den nach dem
Fix tatsächlich verglichenen Vienna-Zeitpunkt. Zwei davon brechen strukturell
(Puffer kleiner als der mögliche Vienna-Offset), der dritte wird
DST-abhängig flaky. Alle drei müssen im selben Commit wie der Fix auf ein um
Vienna-lokale „jetzt"-Zeit zentriertes Fenster umgestellt werden — sonst
werden bestehende, heute grüne Tests durch D1 rot.

## Expected Behavior

- **Input:** `now` (aware datetime, i. d. R. UTC von allen sechs Aufrufern;
  naive datetimes werden als UTC interpretiert), `quiet_from`/`quiet_to`
  als `"HH:MM"`-Strings in gefühlter Lokalzeit (Europe/Vienna)
- **Output:** `bool` — `True` unterdrückt den Alarm, `False` lässt ihn zu.
  Die Entscheidung basiert ab D1 auf der nach Europe/Vienna konvertierten
  Uhrzeit statt auf der rohen UTC-Uhrzeit
- **Side effects:** keine — reine Funktion, kein State, kein I/O. Die
  bestehende Nachliefer-Mechanik (State wird bei Unterdrückung nicht
  verbraucht, z. B. `compare_official_alert.py`, `compare_radar_alert.py`,
  `deviation_alert_engine.py` vor `save()`) bleibt unangetastet — D1 ändert
  nur, WANN die Unterdrückung greift, nicht OB nachgeliefert wird

## Acceptance Criteria

- **AC-1:** Given eine konfigurierte Ruhezeit 22:00–06:00 und es ist Sommer
  (Europe/Vienna, UTC+2) / When um 22:30 Uhr Ortszeit ein Alarm ausgelöst
  würde / Then wird der Alarm unterdrückt und erst nach Ende der Ruhezeit
  nachgeliefert (heute: er geht sofort raus, weil 22:30 Ortszeit = 20:30 UTC
  außerhalb des als UTC interpretierten Fensters liegt).
  - Test: `is_quiet_hours` mit festem aware UTC-Zeitstempel 20:30 (Sommerdatum)
    und Fenster 22:00–06:00 aufrufen, Ergebnis `True` erwarten (rot vor Fix,
    grün danach).

- **AC-2:** Given dieselbe Ruhezeit 22:00–06:00 im Sommer / When um 07:00 Uhr
  Ortszeit ein Alarm ausgelöst würde / Then geht der Alarm sofort raus, keine
  Fehl-Unterdrückung mehr (heute: 07:00 Ortszeit = 05:00 UTC liegt noch im
  als UTC interpretierten Fenster bis 06:00 UTC und wird fälschlich
  unterdrückt).
  - Test: `is_quiet_hours` mit festem aware UTC-Zeitstempel 05:00
    (Sommerdatum) und Fenster 22:00–06:00 aufrufen, Ergebnis `False`
    erwarten (rot vor Fix, grün danach).

- **AC-3:** Given dieselbe Ruhezeit 22:00–06:00, aber im Winter (Europe/Vienna,
  UTC+1) / When um 22:30 Uhr Ortszeit ein Alarm ausgelöst würde / Then wird
  er ebenfalls korrekt unterdrückt (21:30 UTC).
  - Test: `is_quiet_hours` mit festem aware UTC-Zeitstempel 21:30
    (Winterdatum) und Fenster 22:00–06:00 aufrufen, Ergebnis `True` erwarten
    — belegt, dass die Konvertierung DST-sensitiv korrekt arbeitet (nicht
    nur zufällig für den Sommerfall).

- **AC-4:** Given eine Ruhezeit mit Mitternachts-Wrap (22:00–06:00) / When die
  Ortszeit innerhalb des Wrap-Bereichs liegt (z. B. 23:30 Ortszeit) bzw.
  außerhalb (z. B. ein UTC-Zeitpunkt, dessen Vienna-Äquivalent bei 21:00
  Ortszeit liegt) / Then verhält sich die Wrap-Erkennung nach dem Fix exakt
  wie vor dem Fix — nur bezogen auf die korrekte Ortszeit statt auf UTC.
  - Test: zwei feste aware UTC-Zeitstempel, deren Vienna-Äquivalent einmal
    innerhalb (23:30 Ortszeit) und einmal außerhalb (21:00 Ortszeit) des
    Fensters liegt, gegen dasselbe Fenster 22:00–06:00 prüfen.

- **AC-5:** Given ein Trip oder Vergleichs-Preset ohne konfigurierte stille
  Stunden (`quiet_from`/`quiet_to` fehlen oder sind leer) / When ein Alarm
  ausgewertet wird / Then ändert sich am Verhalten nichts — es wird
  weiterhin nie unterdrückt (`False`), unabhängig von Uhrzeit oder Jahreszeit.
  - Test: `is_quiet_hours` ohne `quiet_from`/`quiet_to` mit beliebigem festen
    Zeitstempel aufrufen, `False` erwarten — Regressionsschutz für den
    unveränderten early-return-Pfad.

- **AC-6:** Given die drei Alarmarten Trip-Alarm (`trip_alert.py`),
  offizielle Vergleichs-Warnung (`compare_official_alert.py`) und
  Radar-Alarm (`compare_radar_alert.py`) / When jede für sich während
  derselben, nach Ortszeit korrekt berechneten Ruhezeit ausgelöst würde /
  Then unterdrücken alle drei gleichermaßen, weil sie denselben zentralen
  `is_quiet_hours`-Aufruf über `DeviationAlertEngine` teilen (kein
  Aufrufer-spezifischer Sonderfall).
  - Test: pro Alarmart mindestens einen Bestandstest mit einem festen
    Sommerzeit-Zeitstempel im „22:00–24:00 Ortszeit"-Bereich grün bekommen
    (bzw. in den drei Audit-Fällen oben das Fenster auf Vienna-lokale
    „jetzt"-Zeit umstellen, damit der End-to-End-Pfad den Fix überhaupt
    durchläuft statt zufällig immer wahr zu sein).

## Known Limitations

- **Zeitzone fest Europe/Vienna:** Es gibt kein Nutzer-Feld für die
  Zeitzone (Projekt-Konvention, vgl. `alert_daily_limit.py` und
  `scheduler_dispatch_service.py:146`). D1 führt bewusst **keine**
  konfigurierbare Zeitzone ein — das wäre eine eigene, größere Entscheidung
  außerhalb dieses Bugfixes.
- **Naive datetimes:** Werden als UTC interpretiert (konservativ). Alle
  sechs bekannten Aufrufer übergeben heute durchweg aware UTC-Zeitstempel;
  der naive Fallback ist reine Absicherung, kein aktiver Nutzungspfad.
- **Nachliefer-Mechanik unverändert:** D1 ändert nur, WANN die Ruhezeit
  greift (Lokalzeit statt UTC), nicht OB und WIE nach Ende der Ruhezeit
  nachgeliefert wird — dieses Verhalten existiert bereits in allen drei
  Aufrufer-Services und bleibt unangetastet.
- **Testfenster-Umstellung ist Teil des Fixes, kein Nebenbefund:** Die drei
  in der Audit-Tabelle markierten dynamischen Testfenster (`test_issue_1168_
  alert_engine_extract.py`, `test_compare_radar_alert.py`,
  `test_issue_883_acute_danger_override.py`) MÜSSEN im selben Commit
  angepasst werden, sonst werden sie durch D1 rot bzw. saisonal flaky.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine neue Architekturentscheidung getroffen,
  sondern eine bereits im Projekt etablierte Konvention (Europe/Vienna via
  `ZoneInfo`, `now.astimezone(VIENNA)`, siehe `alert_daily_limit.py`) auf
  eine zweite Stelle angewendet, an der Lokalzeit-Vergleiche nötig sind.
  Kein neues strukturelles Muster, kein neuer Dienst, keine neue
  Konfigurationsoption.

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1312, Scheibe D1 von Epic #1301

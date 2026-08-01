---
entity_id: fix_1448_s2_dateisperren
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [fcntl, dateisperre, alerts, zeitbudget]
---

# Fix #1448 Scheibe S2 — Dateisperren bekommen eine Zeitgrenze

## Approval

- [ ] Approved

## Purpose

Drei Stellen im Alarm-Pfad nehmen eine `fcntl.flock(fd, fcntl.LOCK_EX)`
**ohne `LOCK_NB`, ohne Zeitgrenze** — der Aufruf blockiert unbegrenzt,
solange ein anderer Prozess dieselbe Sperrdatei hält. Nutzersichtbar
bedeutet das: ein Alarm-Lauf kann an einer Dateisperre hängen bleiben,
ohne dass die neue Job-Lauf-Grenze aus #1447 S1 (`ALERT_RUN_DEADLINE_SECONDS`)
oder die Mail-Zeitgrenze aus S1 dieser Scheibe (`fix_1448_s1_mail_zeitgrenze.md`)
das je erreichen — die Sperre hängt vorher.

Diese Scheibe gibt einem gemeinsamen neuen Helfer (`file_lock.py`) eine
harte, im Test schrumpfbare Zeitgrenze für das Erwerben einer Dateisperre,
nach dem Vorbild von `FETCH_DEADLINE_SECONDS` (`src/providers/dwd.py:69`),
und lässt die drei betroffenen Zähler-Klassen diesen Helfer statt des
nackten `flock` nutzen.

## Source

- **Datei (neu):** `src/services/file_lock.py`,
  Funktion `acquire_exclusive(fd, timeout_s) -> bool`
- **Aufrufer (geändert):**
  - `src/services/forecast_budget.py`, `ForecastBudgetGate._safe_update()` (`:169-196`)
  - `src/services/throttle_store.py`, `ThrottleStore._update()` (`:102-123`)
  - `src/services/official_alerts/meteoalarm_budget.py`, `MeteoAlarmBudgetGate._safe_update()` (`:221-243`)

> **Schicht-Hinweis:** Reine Python-Core-Änderung (`src/services/`). Keine
> Go-, keine Frontend-Änderung. Kein Mail-Renderer betroffen, das
> Renderer-Commit-Gate #811 greift auf keiner der vier Dateien.

## Estimated Scope

- **LoC:** ~+90/-30 Code (Helfer + drei Aufrufer) plus ~+220 Test
  (Kontext-Schätzung, `docs/context/fix-1448-s2-dateisperren.md`) — liegt
  über dem 250er-Workflow-Budget, PO-Freigabe über `loc_limit_override`
  nötig.
- **Files:** 5 (1 neuer Helfer, 3 geänderte Aufrufer, 1 neue Testdatei)
- **Effort:** medium — klar umrissener Mechanismus nach etabliertem
  Vorbild (`FETCH_DEADLINE_SECONDS`), aber mit einer echten Testfalle
  (`fcntl.flock` ist prozessweit) und drei Stellen, die konsistent
  umgestellt werden müssen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.dwd.FETCH_DEADLINE_SECONDS` | Referenz-Pattern (nicht importiert) | Monotone Uhr, Prüfung mit Zeitgrenze statt unbegrenztem Warten — hier auf den Sperren-Erwerb übertragen |
| `fix_1448_s1_mail_zeitgrenze.md` (Schwester-Scheibe) | Spec (bestehend) | Liefert die Lehre, die diese Scheibe trägt: eine neue Zeitgrenze hinter einem zu breiten `except` wird zum stillen Fehler (Adversary-Fund F001, CRITICAL) |
| `ThrottleStore.record()`-Aufrufer `trip_alert.py:315`/`:985`/`:1208` | Python-Aufrufstellen (nicht geändert) | Begründung fürs Überspringen statt Werfen: `record()` läuft ausnahmslos **nach** erfolgreicher Zustellung — ein Ausfall verliert keinen Alarm, nur die Notiz „schon gesendet" |
| `alert_daily_limit.increment` (#1070) | Python-Modul (nicht geändert) | Zusätzlicher Schutz gegen Alarm-Wiederholung, falls `throttle_store` die Notiz verpasst |
| `reference_python_core_logging_blind_spot` (Memory) | Hintergrundwissen | Der Root-Logger ist erst seit #1447 S1 konfiguriert (`GZ_LOG_LEVEL`) — vorher wäre die neue WARNING wirkungslos verpufft |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/file_lock.py` | CREATE | Gemeinsamer Helfer `acquire_exclusive(fd, timeout_s)`, Modulkonstante `LOCK_TIMEOUT_SECONDS = 2.0` |
| `src/services/forecast_budget.py` | MODIFY | `_safe_update()` nutzt den Helfer statt nacktem `flock`; WARNING bei Überspringen; Fail-open-Zusage (`except Exception: pass`) bleibt unverändert bestehen |
| `src/services/throttle_store.py` | MODIFY | `_update()` nutzt den Helfer; **neu** ein schmaler Fail-open **nur** für den Sperre-Timeout-Fall (bisher kein try/except); IO-/JSON-Fehler bleiben unverändert durchgereicht |
| `src/services/official_alerts/meteoalarm_budget.py` | MODIFY | dito `forecast_budget.py` |
| `tests/tdd/test_file_lock_timeout.py` | CREATE | Nachweis: echte gehaltene Sperre aus einem zweiten Prozess, WARNING per `caplog` |

### Estimated Changes

- Files: 5 (1 neu Helfer, 3 geändert, 1 neu Testdatei)
- LoC: +90/-30 Code, +220 Test (Kontext-Schätzung)

## Implementation Details

### Neuer Helfer `src/services/file_lock.py`

```
LOCK_TIMEOUT_SECONDS = 2.0  # analog FETCH_DEADLINE_SECONDS (dwd.py:69):
# die geschützte Arbeit ist Lesen+Schreiben einer kleinen JSON-Datei, also
# Millisekunden -- 2s sind ~drei Größenordnungen Reserve gegenüber dem
# Normalfall und vernachlässigbar gegenüber dem 90s-Alarm-Lauf-Budget
# (ALERT_RUN_DEADLINE_SECONDS, trip_alert.py:40, #1447 S1).

def acquire_exclusive(fd: int, timeout_s: float) -> bool:
    """Versucht, eine exklusive Dateisperre auf `fd` zu erwerben, gibt
    nach `timeout_s` auf. Kein Exception-Fallthrough -- Rückgabe True/False,
    der Aufrufer entscheidet selbst, wie er auf ein Fehlschlagen reagiert."""
```

Schleife mit `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` in einem
`try/except BlockingIOError`, kurze Pause zwischen Versuchen (`time.sleep`,
kleiner Bruchteil der Gesamtfrist), Abbruch sobald `time.monotonic()` die
Frist erreicht. Erfolg → `True`, Frist abgelaufen → `False`. Keine eigene
Exception-Klasse — bewusst, damit kein Aufrufer versehentlich einen zu
breiten `except` braucht, um sie zu fangen (die Lehre aus S1).

### Die drei Aufrufer

Jeweils:

```
fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
try:
    if not acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS):
        logger.warning(
            "Dateisperre %s nicht innerhalb %.1fs erhalten -- Schreibvorgang "
            "uebersprungen", lock_path, LOCK_TIMEOUT_SECONDS,
        )
        return
    try:
        data = self._load...()
        mutate(data)
        self._write(data)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
finally:
    os.close(fd)
```

Reihenfolge Reload → Mutate → Write **innerhalb** der Sperre bleibt in
allen drei Klassen unverändert. Die WARNING wird **vor** dem `return`
geloggt, nicht danach — sonst würde ein Fehler im Logging-Aufruf selbst
den Skip verschlucken.

`forecast_budget.py` und `meteoalarm_budget.py` haben aktuell **keinen**
`logger` (kein `import logging`) — der wird mit dieser Änderung ergänzt,
Modulname analog `throttle_store` (`logging.getLogger("forecast_budget")`
bzw. `logging.getLogger("meteoalarm_budget")`).

### Fail-open-Präzisierung in `throttle_store._update()`

`throttle_store._update()` hat heute **kein** umschließendes
`try/except` — ein Fehler propagiert. Diese Scheibe fügt **gezielt** nur
für den Sperre-Timeout-Fall ein Überspringen ein (der `if not
acquire_exclusive(...): ... return`-Zweig oben), **kein** neues
blanket `except Exception`. IO-Fehler beim Lesen/Schreiben oder ein
kaputtes JSON bleiben unverändert unbehandelt und propagieren wie
heute — das ist bewusst enger als `forecast_budget`/`meteoalarm_budget`,
die bereits vor dieser Scheibe jeden Fehler schlucken (Fail-open-Zusage
in ihrem jeweiligen Docstring, unverändert).

## Reichweite je Sperre (aus der Analyse übernommen)

| Sperre | Reichweite | Was bei Überspringen ausbleibt | Bewertung |
|---|---|---|---|
| `forecast_budget` | **global — alle Nutzer, alle Jobs**, zusätzlich je Segment genommen (`segment_weather.py:146/152/194`, `radar_service.py:179/182/434`) | Zähler für Abrufe/Cache-Treffer | hinnehmbar — bestehende Fail-open-Zusage |
| `meteoalarm_budget` | global | Zähler für amtliche Warnungen | hinnehmbar — dito |
| `throttle_store` | pro Nutzer | Zeitstempel „gerade gesendet" | hinnehmbar, s. Purpose — `record()` läuft immer nach erfolgreichem Versand |

`forecast_budget` ist der heikelste Fall: nicht nutzergetrennt und mit der
höchsten Aufruffrequenz. Das Bündeln dieser je-Segment-Aufrufe ist eine
Durchsatz-Optimierung und **nicht Teil dieser Scheibe** (s. u.).

## Expected Behavior

- **Input:** unverändert — `_safe_update(mutate)` / `_update(mutate)`.
- **Output (Normalfall, keine Konkurrenz):** unverändert, Sperre wird
  sofort erworben, Daten werden geschrieben wie heute.
- **Output (Sperre von anderem Prozess gehalten, Timeout erreicht):**
  Aufruf kehrt nach spätestens `LOCK_TIMEOUT_SECONDS` zurück, eine
  WARNING-Zeile mit Sperrpfad und gewarteter Zeit erscheint, der
  Schreibvorgang wird übersprungen, der Aufrufer läuft normal weiter
  (kein Werfen, außer bei `throttle_store` für Nicht-Timeout-Fehler wie
  bisher).
- **Side effects:** neue WARNING-Log-Zeile bei Timeout; sonst keine
  neuen Log-Formate.

## Was sich NICHT ändert

- Die Fail-open-Zusage von `forecast_budget` und `meteoalarm_budget`
  (`except Exception: pass`) bleibt für alle Fehlerklassen bestehen.
- Die Sidecar-Lock-Datei-Strategie (`<state>.lock` statt Sperre auf der
  Zieldatei, wegen `os.replace`) bleibt unverändert.
- Die Reihenfolge Reload → Mutate → Write innerhalb der Sperre bleibt
  unverändert.
- `throttle_store` bekommt Fail-open **nur** für den
  Sperre-Timeout-Fall, nicht für IO-/JSON-Fehler — kein neuer blanket
  `except`.

## Ausdrücklich nicht Teil dieser Scheibe

Das Bündeln der je-Segment-Aufrufe von `forecast_budget`
(`segment_weather.py:146/152/194`, `radar_service.py:179/182/434`) auf
einen einzigen Aufruf je Job-Lauf. Das ist eine Durchsatz-Optimierung,
kein Blockade-Fix — die Zeitgrenze aus dieser Scheibe löst das Hängen
bereits unabhängig von der Aufrufhäufigkeit. Nebenbefund, nicht
mitgenommen (Sammel-Issue #1199, sofern nicht nutzersichtbar).

## Test-Plan / Test-Politik

**Die entscheidende Falle:** `fcntl.flock` ist **prozessweit** — ein
zweiter Erwerb im selben Prozess auf demselben Deskriptor gelingt sofort.
Ein Test, der die Sperre im selben Prozess hält, ist immer grün und
beweist nichts (`reference_regex_guard_matches_nothing_always_green`).

Deshalb zwingend: Sperre in einem **zweiten Prozess**
(`multiprocessing.Process` oder `subprocess`) auf derselben Sperrdatei
halten, `LOCK_TIMEOUT_SECONDS` per `monkeypatch` auf Millisekunden
schrumpfen, messen, dass `acquire_exclusive()`/der Aufrufer innerhalb der
Frist zurückkehrt, und dass die WARNING-Zeile erscheint (`caplog`). Kein
Mock, kein Mock-Theater.

Alle Tests in `tests/tdd/test_file_lock_timeout.py`, Namensregel nach
Verhalten (keine Issue-Nummer im Dateinamen). Pfadregel #1409: Prüfling
relativ zur eigenen Testdatei auflösen (`Path(__file__).resolve().parents[2]`),
niemals über einen festen Hauptrepo-Pfad. `pytest-timeout` steht global
auf 30s — mit geschrumpften Konstanten bleiben alle Tests deutlich
darunter.

## Acceptance Criteria

- **AC-1:** Given eine zweite Prozess-Instanz hält bereits eine exklusive
  Sperre auf derselben Sperrdatei / When `acquire_exclusive(fd,
  timeout_s)` mit einer (per Test auf Millisekunden geschrumpften)
  Zeitgrenze aufgerufen wird / Then kehrt der Aufruf spätestens nach
  `timeout_s` mit `False` zurück, statt unbegrenzt zu blockieren.
  - Test: `test_acquire_exclusive_returns_false_when_locked_by_other_process`
    — Sperre in einem `multiprocessing.Process` gehalten, Timeout auf
    Millisekunden geschrumpft, gemessene Rückkehrzeit liegt innerhalb der
    erwarteten Obergrenze.

- **AC-2:** Given `acquire_exclusive()` liefert `False`, weil die Sperre
  einer der drei Zähler-Klassen (`ForecastBudgetGate`, `ThrottleStore`,
  `MeteoAlarmBudgetGate`) nicht innerhalb der Frist erworben werden kann
  / When der jeweilige `_safe_update()`/`_update()`-Aufruf diesen Fall
  durchläuft / Then wird eine WARNING-Zeile mit Sperrpfad und gewarteter
  Zeit geloggt.
  - Test: `test_update_logs_warning_with_lock_path_when_timed_out` —
    parametrisiert über alle drei Klassen; Sperre extern gehalten,
    `caplog` prüft WARNING-Level und dass der Sperrpfad im Log-Text
    vorkommt.

- **AC-3:** Given die Sperre einer der drei Zähler-Klassen kann nicht
  innerhalb der Frist erworben werden / When der jeweilige Aufruf
  zurückkehrt / Then läuft der Aufrufer normal weiter, ohne eine
  Exception zu werfen — insbesondere `ThrottleStore._update()`, das vor
  dieser Scheibe **kein** umschließendes `try/except` hatte und den
  Fehler propagiert hätte.
  - Test: `test_update_does_not_raise_when_lock_times_out` —
    parametrisiert über alle drei Klassen; Sperre extern gehalten, der
    Aufruf kehrt ohne Exception zurück.

- **AC-4:** Given ein IO- oder JSON-Fehler tritt in
  `ThrottleStore._update()` auf, der **nicht** die Sperre betrifft (z.B.
  kaputtes JSON in der Zustandsdatei) / When `_update()` läuft / Then
  wird dieser Fehler weiterhin durchgereicht wie vor dieser Scheibe —
  kein neues blanket Fail-open, nur der Sperre-Timeout-Fall wird neu
  abgefangen.
  - Test: `test_update_still_raises_on_non_lock_error` — Zustandsdatei
    mit ungültigem JSON vorbereitet, keine Sperren-Konkurrenz, Aufruf
    wirft weiterhin.

- **AC-5:** Given keine Konkurrenz auf der Sperrdatei (Normalfall) / When
  eine der drei Zähler-Klassen `_safe_update()`/`_update()` aufruft /
  Then bleibt das Verhalten unverändert: die Sperre wird sofort
  erworben, die Daten werden korrekt geschrieben, keine WARNING
  erscheint.
  - Test: `test_update_writes_immediately_without_contention` —
    parametrisiert über alle drei Klassen; ohne externe Sperre wird nach
    dem Aufruf der erwartete Dateninhalt gelesen, `caplog` bleibt ohne
    WARNING.

## Known Limitations

- **Zählerstände können verloren gehen.** Bei dauerhaft blockierter
  Sperre (z.B. ein hängender Fremdprozess) wird der Schreibvorgang für
  `forecast_budget`/`meteoalarm_budget` dauerhaft übersprungen —
  Kontingent-Buchführung wird ungenau. Bewusst gegenüber unbegrenztem
  Warten eingetauscht.
- **Ein Alarm kann sich wiederholen.** Bleibt die `throttle_store`-Sperre
  dauerhaft blockiert, verpasst der Nutzer die „schon gesendet"-Notiz und
  derselbe Alarm kann im nächsten Lauf erneut verschickt werden. Zusätzlich
  abgefedert durch das bestehende Tageslimit (`alert_daily_limit.increment`,
  #1070), aber nicht vollständig verhindert.
- **`forecast_budget` bleibt je Segment aufgerufen** (nicht gebündelt,
  s. „Ausdrücklich nicht Teil dieser Scheibe") — unter echter Last bleibt
  die Sperre also die am häufigsten angefragte der drei.
- **`LOCK_TIMEOUT_SECONDS = 2.0` ist ein konservativer, aus der
  Belegrechnung hergeleiteter erster Wert**, keine empirisch in
  Produktion gehärtete Zahl — analog zur Einordnung von
  `ALERT_RUN_DEADLINE_SECONDS` in #1447 S1 und `SEND_BUDGET_SECONDS` in
  `fix_1448_s1_mail_zeitgrenze.md`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer architektureller Grundsatz. Diese Scheibe
  wendet dasselbe bereits etablierte Muster (monotone Zeitgrenze statt
  unbegrenztem Warten, Vorbild `FETCH_DEADLINE_SECONDS`) auf den
  Sperren-Erwerb an, das S1 dieser Scheibe bereits auf den Mail-Versand
  angewendet hat. ADR-0038 schließt „einzelne in sich unbegrenzt
  blockierende Schritte" ausdrücklich aus seinem Geltungsbereich aus und
  benennt Issue #1448 als die Stelle, an der sie gesondert behandelt
  werden — diese Spec ist Teil dieser gesonderten Behandlung, kein
  Widerspruch und keine neue Grundsatzentscheidung.

## Changelog

- 2026-08-01: Initial spec created

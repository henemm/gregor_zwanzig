# Kontext & Analyse: #1448 Scheibe S2 — Dateisperren ohne Zeitgrenze

**Workflow:** `fix-1448-s2-dateisperren` · **Typ:** Bug · **Issue:** #1448 (Blockierer B3)
**Erstellt:** 2026-08-01 · **Vorgänger:** S1 live (`5b97542a`), `docs/context/fix-1448-s1-mail-timeout.md`

## Type

Bug — nutzersichtbares Fehlverhalten: eine gehaltene Dateisperre kann einen Alarm-Lauf
unbegrenzt anhalten und damit eine Wetterwarnung verzögern.

## Befund (verifiziert am Code, Stand `5b97542a`)

Drei Stellen nehmen `fcntl.flock(fd, fcntl.LOCK_EX)` **ohne `LOCK_NB`, ohne Zeitgrenze**.
Der Aufruf blockiert unbegrenzt, solange ein anderer Prozess die Sperre hält.

| Stelle | Sperrdatei | Reichweite | Verhalten bei Fehler heute |
|---|---|---|---|
| `src/services/forecast_budget.py:178` | `<data_root>/diagnostics/forecast_budget.json.lock` | **global — alle Nutzer, alle Jobs** | `except Exception: pass` (fail-open, `:194-195`) |
| `src/services/throttle_store.py:115` | `<user>/throttle_state.json.lock` | pro Nutzer | **kein try/except** — Fehler propagiert |
| `src/services/official_alerts/meteoalarm_budget.py:231` | `data/diagnostics/*.lock` | global | `except Exception: pass` (fail-open) |

**Der heikelste ist `forecast_budget`:** nicht nutzergetrennt **und je Segment** genommen —
`segment_weather.py:146` (Cache-Treffer!), `:152`, `:194`, dazu `radar_service.py:179`, `:182`,
`:434`. Alle gleichzeitig laufenden Alarm-Jobs **aller** Nutzer serialisieren sich auf einer
einzigen Datei. Das Fail-open fängt Fehler, aber **nicht das Warten**.

## Was bei einer Zeitüberschreitung passieren soll — die Abwägung

Entscheidend ist, was der jeweilige Schreibvorgang bedeutet, wenn er ausfällt:

| Sperre | Was ausbleibt | Folge | Bewertung |
|---|---|---|---|
| `forecast_budget` | Zähler für Abrufe/Cache-Treffer | Kontingent-Buchführung wird ungenau | hinnehmbar — bereits heute die Fail-open-Zusage („ein Zähl-Defekt darf nie einen Versand verhindern") |
| `meteoalarm_budget` | dito für amtliche Warnungen | dito | dito |
| `throttle_store` | Zeitstempel „gerade gesendet" | derselbe Alarm kann im nächsten Lauf erneut rausgehen | hinnehmbar, s.u. |

**Entscheidend für `throttle_store`:** `record()` wird **ausnahmslos nach** erfolgreicher
Zustellung aufgerufen — `trip_alert.py:315` („Update throttle (only on success)"), `:985`
(„Recording nach Best-Effort-Zustellung"), `:1208` (`if result.sent:`). Ein Ausfall dort
**verliert also keinen Alarm**, sondern nur die Notiz, dass er schon raus ist. Ein *geworfener*
Fehler wäre dagegen deutlich schlimmer: er bräche den Lauf nach bereits versendetem Alarm ab.

⇒ Bei Zeitüberschreitung wird der Schreibvorgang **übersprungen**, nicht der Lauf abgebrochen —
für alle drei Stellen einheitlich. Gegen Alarm-Wiederholung greift zusätzlich das bestehende
Tageslimit (`alert_daily_limit.increment`, #1070), das unmittelbar nach `record()` läuft.

## Die Lehre aus S1, die hier zwingend gilt

In S1 hat die neu eingeführte Zeitgrenze aus einem *lauten* Hänger einen **stillen** Verlust
gemacht, weil ein zu breiter `except` im Weg saß (Adversary-Fund F001, CRITICAL). Genau dieses
Muster liegt hier zweimal offen vor: `except Exception: pass` in `forecast_budget.py:194-195`
und `meteoalarm_budget.py`.

⇒ **Eine übersprungene Sperre MUSS eine WARNING-Zeile erzeugen.** Sonst ist der Fehler
unsichtbar, und wir tauschen ein diagnostizierbares Hängen gegen eine unbemerkte
Fehlbuchführung. Der Root-Logger ist seit #1447 S1 konfiguriert (`GZ_LOG_LEVEL`), WARNING-Zeilen
kommen also tatsächlich an — vorher wäre das wirkungslos gewesen
(`reference_python_core_logging_blind_spot`).

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/file_lock.py` | CREATE | Gemeinsamer Helfer: Sperre mit Zeitgrenze (`LOCK_EX \| LOCK_NB` in begrenzter Wiederholung) |
| `src/services/forecast_budget.py` | MODIFY | Helfer statt nacktem `flock`; WARNING bei Überspringen |
| `src/services/throttle_store.py` | MODIFY | dito; zusätzlich Fail-open **nur** für den Zeitüberschreitungsfall |
| `src/services/official_alerts/meteoalarm_budget.py` | MODIFY | dito |
| `tests/tdd/test_file_lock_timeout.py` | CREATE | Nachweis: echte gehaltene Sperre aus einem zweiten Prozess |

**Warum ein gemeinsamer Helfer statt dreimal derselbe Block:** Die drei `_safe_update`-Methoden
sind schon heute fast wortgleich (`forecast_budget` verweist im Docstring ausdrücklich auf
„Muster `ThrottleStore`"). Dreifach kopierte Timeout-Logik wäre mehr Zeilen *und* dreifache
Driftfläche. Entspricht der Projektlinie „möglichst viel Code teilen".

## Scope Assessment

- Dateien: 1 neu (Helfer), 3 geändert, 1 Testdatei neu
- Geschätzt: ~+90/-30 Code, ~+220 Test ⇒ **über dem 250er-Budget**, Freigabe nötig
- Risiko: **MITTEL** — die Sperren schützen Schreibvorgänge auf geteilten Zustandsdateien.
  Ein zu kurzer Zeitwert würde unter echter Last Zähler verlieren. Kein Mail-Gate betroffen
  (keine Mail-Inhalts-Datei).

## Technischer Ansatz

1. **`acquire_exclusive(fd, timeout_s)`** im neuen Helfer: `fcntl.flock(fd, LOCK_EX | LOCK_NB)`
   in einer Schleife mit kurzer Pause, bis die Sperre da ist oder die Frist abläuft. Rückgabe
   `True`/`False` statt Exception — die Aufrufer entscheiden selbst, wie sie reagieren.
2. **`LOCK_TIMEOUT_SECONDS = 2.0`**: Die geschützte Arbeit ist ein Lesen + Schreiben einer
   kleinen JSON-Datei, also Millisekunden. 2 s sind rund drei Größenordnungen Reserve gegenüber
   dem Normalfall und zugleich vernachlässigbar gegenüber dem 90-s-Budget des Alarm-Laufs
   (`ALERT_RUN_DEADLINE_SECONDS`, `trip_alert.py:40`).
3. **Bei Fehlschlag:** WARNING mit Sperrpfad und gewarteter Zeit, Schreibvorgang überspringen,
   Aufrufer läuft normal weiter.
4. **Nicht Teil dieser Scheibe:** das Bündeln der je-Segment-Aufrufe von `forecast_budget`
   (Issue-Vorschlag 3). Das ist eine Durchsatz-Optimierung, kein Blockade-Fix — die
   Zeitgrenze löst das Hängen bereits. Als Nebenbefund festhalten, nicht mitnehmen.

## Nachweis (Muster)

Die Sperre muss **wirklich gehalten** werden, während der Prüfling sie anfordert — `fcntl.flock`
ist prozessweit, ein zweiter Erwerb im selben Prozess auf demselben Deskriptor gelingt sofort.
Also: Sperre in einem **zweiten Prozess** (`multiprocessing`/`subprocess`) halten, Zeitgrenze per
`monkeypatch` auf Millisekunden schrumpfen, messen, dass der Aufruf zurückkehrt statt zu hängen,
und dass die WARNING-Zeile erscheint (`caplog`). Kein Mock.

⚠️ **Falle:** Ein Test, der die Sperre im selben Prozess/Deskriptor hält, ist immer grün und
beweist nichts — vgl. `reference_regex_guard_matches_nothing_always_green`.

## Open Questions

- [x] Werfen oder überspringen bei Zeitüberschreitung? → überspringen; `record()` läuft immer
      nach erfolgreichem Versand, ein geworfener Fehler wäre schlimmer als eine fehlende Notiz.
- [ ] Zeitwert 2,0 s — in der Spec mit Begründung, PO-Freigabe über die ACs.

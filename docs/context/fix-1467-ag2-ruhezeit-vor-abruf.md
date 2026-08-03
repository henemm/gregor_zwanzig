# Context: fix-1467-ag2-ruhezeit-vor-abruf

**Issue:** #1467 Scheibe S2, Arbeitsgang **AG2** von sechs (Epic #1458)
**Spec:** `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — freigegeben (PO-„go" 2026-08-03),
AG2 = **AC-4, AC-5, AC-6**
**Vorgänger:** AG1 committet (`a31a2bf0`) — Compare-Kanalregel steht nur noch an einer Stelle

## Request Summary

Der Ortsvergleich prüft die Ruhezeit heute erst, nachdem er das Wetter bereits abgerufen hat.
AG2 zieht die Prüfung davor. Wirkung: während der Ruhezeit wird kein Wetter mehr abgerufen —
gleiches Meldeverhalten, weniger Abrufe.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/compare_alert.py` | Der zu ändernde Ablauf. Sperrzeit `:112`, Tages-Obergrenze `:118`, Erkennung `:124` → `_detect_triggered_locations()` `:164` → `_evaluate_one_location()` `:187` mit **Wetterabruf `:194`**. Ruhezeit-Werte des Presets: `alert_quiet_from`/`alert_quiet_to` (`:240-241`) |
| `src/services/deviation_alert_engine.py` | `is_quiet_hours()` `:75` — die geteilte Prüffunktion, rechnet in Europe/Vienna (`:28`, `:94`), Mitternachts-Wrap `:98-100`, fehlendes Feld ⇒ `False` `:91-92`. Aufruf in der Engine `:243`, also nach dem Abruf |
| `src/services/compare_official_alert.py` | **Vorbild:** vorgezogener Ruhezeit-Riegel `:105-113` |
| `src/services/trip_alert.py` | Trip prüft explizit vor allem anderen `:205`, zusätzlich in der Engine — die Doppelprüfung ist dort seit jeher unauffällig |
| `tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` | Die roten Tests (bereits geschrieben): AC-4 rot, AC-5/AC-6 als Invarianten-Schutz grün |
| `tests/test_success_status_guard.py` | Struktur-Wächter `:1523-1530`/`:1782-1786` verankert `compare_alert.py::check_all_compare_presets` per `datei::funktion::ordinal` samt `try/except`-Zahl |

## Existing Patterns

- **Riegel früh in der Preset-Schleife**, bevor Daten geholt werden — genau so macht es der
  amtliche Pfad (`compare_official_alert.py:105-113`).
- **Eine geteilte Prüffunktion, mehrere Aufrufer:** `DeviationAlertEngine.is_quiet_hours()` wird
  von Trip, Engine und amtlichem Pfad benutzt. Es wird **keine zweite Fassung** gebaut.
- **Doppelte Prüfung ist zulässig:** Der Trip prüft die Ruhezeit zweimal (vorgeschaltet + in der
  Engine). Die Engine-Prüfung bleibt bestehen — sie hat andere Aufrufer.

## Dependencies

- **Upstream:** `DeviationAlertEngine.is_quiet_hours`, `ThrottleStore`, `alert_daily_limit`,
  `CompareLocationWeatherSource`
- **Downstream:** `api/routers/scheduler.py:70-77` (`/compare-alert-checks`),
  `internal/scheduler/scheduler.go:151` (Cron `*/15`)

## Existing Specs

- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — AG2-Abschnitt + AC-4/5/6 (freigegeben)
- `docs/specs/modules/issue_1169_compare_alert_consumer.md` — der Ortsvergleich als zweiter
  Engine-Konsument
- ADR-0021 — geteilter Auswertungskern

## Risks & Considerations

1. **Kein Zähler darf sich verschieben.** Sperrzeit und Tages-Obergrenze werden heute während der
   Ruhezeit nur *gelesen*; geschrieben wird erst nach erfolgreichem Versand (`:158-159`).
   AC-6 nagelt das fest.
2. **Halb ausgefülltes Ruhezeit-Fenster darf nicht dauerhaft stummschalten** (AC-5) —
   `is_quiet_hours` liefert bei fehlendem Feld `False`, das muss so bleiben.
3. **Struktur-Wächter (R6 der Spec):** Ein zusätzlicher Riegel kann die Ordinal-Zählung in
   `test_success_status_guard.py` verschieben. Dann Schlüssel nachziehen, **Wächter nicht
   aufweichen**.
4. **Zeitzone:** `is_quiet_hours` rechnet in Europe/Vienna, nicht in der Ortszeit des Vergleichs.
   Das ist Ist-Verhalten und wird in AG2 **nicht** angefasst (wäre eine eigene Entscheidung).
5. **Abgrenzung:** Nowcast (`compare_radar_alert.py`, S3) und amtlicher Pfad
   (`compare_official_alert.py`, S4) werden nicht verändert.

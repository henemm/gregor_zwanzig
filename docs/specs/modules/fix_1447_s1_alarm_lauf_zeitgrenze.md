---
entity_id: fix_1447_s1_alarm_lauf_zeitgrenze
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [alerts, scheduler, observability, zeitbudget]
---

# Fix #1447 Scheibe S1 — Harte Zeitgrenze für den Alarm-Lauf + Sichtbarkeit

## Approval

- [ ] Approved

## Purpose

`TripAlertService.check_all_trips()` prüft in einer Schleife alle Trips
eines Nutzers auf Wetter-Änderungen und amtliche Warnungen — ohne jedes
Gesamt-Zeitbudget. Der Go-Scheduler, der diesen Lauf über
`/api/scheduler/alert-checks` anstößt, bricht seinerseits nach 120 Sekunden
ab (geteilter `http.Client{Timeout: 120s}`). Reißt der Python-Lauf diese
Grenze, geht der Alarm-Zyklus für den betroffenen Nutzer komplett verloren,
Folge-Nutzer werden verzögert — und **nichts davon ist im Nachhinein
feststellbar**, weil der Root-Logger im gesamten Projekt nirgends
konfiguriert ist (kein `basicConfig`/`dictConfig`), wodurch jede
`logger.info(...)`-Zeile aus `src/` verworfen wird.

Diese Scheibe gibt `check_all_trips()` eine harte, im Test schrumpfbare
Obergrenze deutlich unter den 120 Sekunden des Go-Clients (Vorbild:
`FETCH_DEADLINE_SECONDS` in `src/providers/meteofrance.py`/`dwd.py`) und
macht Lauf und Abbruch durch Root-Logger-Konfiguration erstmals sichtbar.
Sie begrenzt die **Summe** der Arbeit eines Laufs — nicht einzelne in sich
unbegrenzt blockierende Schritte (siehe „Known Limitations").

## Source

- **Datei:** `src/services/trip_alert.py`, Klasse `TripAlertService`,
  Methode `check_all_trips()` (`:275-362`)
- **Datei:** `api/routers/scheduler.py`, Funktion `trigger_alert_checks()`
  (`:45-52`) — einziger Produktiv-Aufrufer von `check_all_trips()`
- **Datei:** `api/main.py` (`:1-18`) — Root-Logger-Konfiguration fehlt bisher
  vollständig

> **Schicht-Hinweis:** Alle drei Dateien sind Python-Core
> (`api/`, `src/services/`). Keine Go-Änderung, kein Frontend-Anteil in
> dieser Scheibe — der Go-Scheduler (`internal/scheduler/scheduler.go`)
> wird ausschließlich gelesen, um sein Verhalten gegenüber der neuen
> Antwort zu verstehen (s. „Vertragsänderung"), nicht verändert.

## Estimated Scope

- **LoC:** ~150-190 Code (Modul-Konstante + Schleifen-Prüfung +
  Ergebnis-Datentyp + Router-Anpassung + Root-Logger-Konfiguration) zzgl.
  zwei neue Testdateien (~90-110 LoC) → geschätzt **~240-300 added+deleted**
  gegen das Workflow-Limit von 250. **Das ist knapp bis leicht über dem
  Limit** — siehe „LoC-Einschätzung" unten. `docs/reference/api_contract.md`
  und dieses ADR/diese Spec zählen laut Konvention nicht mit.
- **Files:** 3 Quelldateien modifiziert, 1 Bestandstest modifiziert
  (Zeilennummer-Pflege, s. u.), 2 neue Testdateien
- **Effort:** medium — kleiner, klar umrissener Mechanismus nach
  etabliertem Vorbild, aber mit einer Vertragsänderung am einzigen
  Produktiv-Aufrufer und einer sorgfältig zu behandelnden Wechselwirkung
  mit dem #1405-Wächter (`tests/test_success_status_guard.py`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.meteofrance.FETCH_DEADLINE_SECONDS`-Muster | Referenz-Pattern (nicht importiert) | Monotone Uhr, Prüfung vor jedem Einzelschritt, sichtbarer Abbruch statt stillem Teilergebnis — wird auf Job-Ebene übertragen, nicht 1:1 wiederverwendet |
| `app.loader.load_all_trips()` | Python-Funktion | Liefert die zu prüfenden Trips; unverändert |
| `time.monotonic()` | Python-Stdlib | Wall-Clock-unabhängige Zeitmessung für die Deadline, analog zum Vorbild |
| `api/routers/scheduler.py::trigger_alert_checks` | Python-Endpunkt | Einziger Aufrufer von `check_all_trips()` — Antwort-Body ändert sich (s. u.) |
| `internal/scheduler/scheduler.go::triggerEndpointForUser` | Go-Funktion (nur gelesen) | Bestimmt, wie der Go-Scheduler die neue Antwort interpretiert — siehe „Vertragsänderung" |
| `tests/test_success_status_guard.py` (`KNOWN_VIOLATIONS`, `SPEC_LISTED_FINDINGS`) | Wächter (#1405) | Muss nach der Änderung weiterhin grün sein — Zeilennummer-Pflege nötig, s. u. |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` | MODIFY | Neue Modul-Konstante `ALERT_RUN_DEADLINE_SECONDS = 90.0`; `check_all_trips()` berechnet einmalig `deadline_at = time.monotonic() + ALERT_RUN_DEADLINE_SECONDS`, prüft sie **vor jeder Tour** in der Schleife, zählt `checked`/`skipped`, loggt INFO (Gesamtlaufzeit, jeder Lauf) und WARNING (bei Abbruch: Obergrenze, geprüfte/übersprungene Touren); Rückgabetyp wechselt von `int` auf ein kleines Ergebnis-Objekt (s. Implementation Details) |
| `api/routers/scheduler.py` | MODIFY | `trigger_alert_checks()` leitet `status` (`ok`/`partial`), `count`, `checked`, `skipped`, `duration_s` und ggf. `reason: "deadline"` aus dem neuen Ergebnis-Objekt ab, statt `status` fest auf `"ok"` zu setzen |
| `api/main.py` | MODIFY | Neue Funktion `configure_logging()`, konfiguriert den Root-Logger (Zeitstempel, Stufe, Modulname), Stufe aus `GZ_LOG_LEVEL` (Default `INFO`); Aufruf beim Modul-Import, vor `app = FastAPI(...)` |
| `tests/tdd/test_alert_run_deadline.py` | CREATE | Nachweis Teil A: Obergrenze wird geprüft, bricht sichtbar ab, meldet Teilerfolg; vollständiger Lauf bleibt unverändert |
| `tests/unit/test_logging_configuration.py` | CREATE | Nachweis Teil B: Root-Logger konfiguriert, Stufe über `GZ_LOG_LEVEL` steuerbar, Format enthält Zeitstempel/Stufe/Modul |
| `tests/test_success_status_guard.py` | MODIFY | Zeilennummer-Pflege des B9-Eintrags in `KNOWN_VIOLATIONS` (s. „Wechselwirkung mit dem #1405-Wächter") — **keine inhaltliche Änderung**, der Fund bleibt bestehen |
| `docs/reference/api_contract.md` | MODIFY (zählt nicht gegen LoC-Limit) | Neuer Abschnitt für `POST /api/scheduler/alert-checks` (bisher nur im Routen-Index gelistet, nicht im Detail dokumentiert) mit den beiden Antwortformen und `GZ_LOG_LEVEL` |

### Estimated Changes

- Files: 7 (3 Quelldateien, 1 Bestandstest, 2 neue Testdateien, 1 Doku-Datei)
- LoC: s. „LoC-Einschätzung"

## LoC-Einschätzung

Grobe Schätzung der Code-Anteile (ohne `docs/`):

| Datei | ~LoC |
|---|---|
| `src/services/trip_alert.py` (Konstante, Deadline-Logik, Ergebnis-Typ, Logging) | 55-70 |
| `api/routers/scheduler.py` (Response-Ableitung) | 15-20 |
| `api/main.py` (`configure_logging()`) | 20-25 |
| `tests/tdd/test_alert_run_deadline.py` | 55-70 |
| `tests/unit/test_logging_configuration.py` | 35-45 |
| `tests/test_success_status_guard.py` (Zeilennummer-Pflege) | 1-2 |

Summe grob **180-230 hinzugefügte Zeilen**, dazu wenige gelöschte Zeilen
(alter `-> int`-Rückgabepfad, alte feste `{"status": "ok", "count": count}`).
Realistisch **~200-250 added+deleted** — nah am Limit, aber voraussichtlich
noch darstellbar ohne Override. Sollte die Implementierung during TDD-RED
über 250 hinauswachsen (z. B. weil der Ergebnis-Typ mehr Boilerplate
braucht als hier angenommen), ist `workflow.py set-field loc_limit_override
300` der vorgesehene Weg — **nicht** eine der beiden Testdateien
verkleinern, indem sie weniger echte Fälle abdecken.

## Implementation Details

### Teil A — harte Obergrenze je Nutzer-Lauf

Neue Modul-Konstante in `src/services/trip_alert.py`, nach dem Vorbild von
`FETCH_DEADLINE_SECONDS`:

```python
# Gesamt-Zeitbudget je check_all_trips()-Lauf (Issue #1447): der
# Go-Scheduler wartet pro Nutzer maximal 120s (scheduler.go:82) und bricht
# danach die HTTP-Verbindung ab, ohne dass der Python-Lauf davon erfährt.
# 90s Reserve gegenueber diesen 120s, analog FETCH_DEADLINE_SECONDS in
# providers/meteofrance.py und providers/dwd.py.
ALERT_RUN_DEADLINE_SECONDS = 90.0
```

`check_all_trips()` berechnet `deadline_at = time.monotonic() +
ALERT_RUN_DEADLINE_SECONDS` **einmal**, vor der Schleife über
`load_all_trips(...)`. Vor jeder Tour (d. h. vor dem Betreten des
Schleifenrumpfs, nicht innerhalb eines bestehenden `try`) wird geprüft, ob
`time.monotonic() > deadline_at`. Ist das der Fall: die Schleife wird
**verlassen** (nicht `continue` — die restlichen Trips werden nicht mehr
angefasst), die Anzahl noch nicht geprüfter Trips fließt in `skipped`.

Jede tatsächlich geprüfte Tour (auch eine übersprungene wegen abgelaufenem
Trip oder fehlendem Cache, s. bestehende `continue`-Zweige) erhöht
`checked` — die Deadline-Prüfung selbst zählt **nicht** als „geprüft".

Rückgabe als kleiner, unveränderlicher Ergebnis-Typ statt `int`:

```python
@dataclass(frozen=True)
class AlertCheckRunResult:
    alerts_sent: int
    checked: int
    skipped: int
    duration_s: float
    hit_deadline: bool
```

`check_all_trips() -> AlertCheckRunResult`. Die Docstring-Angabe „Returns:
Number of alerts sent" wird entsprechend korrigiert.

**Kein stilles Weglassen (ADR-0018 sinngemäß):** Beim Abbruch wird eine
WARNING-Zeile mit `ALERT_RUN_DEADLINE_SECONDS`, `checked` und `skipped`
geschrieben. Bei jedem Lauf (ob abgebrochen oder vollständig) wird eine
INFO-Zeile mit der tatsächlichen Gesamtlaufzeit (`duration_s`) geschrieben.

### Teil B — Root-Logger konfigurieren

Neue Funktion in `api/main.py`:

```python
def configure_logging() -> None:
    """Root-Logger fuer den gesamten Python-Core (Issue #1447 Teil B):
    ohne das gibt es keine einzige sichtbare logger.info/.warning-Zeile aus
    src/, weder in Betrieb noch fuer die Fehlersuche. Stufe ueber
    GZ_LOG_LEVEL (Default INFO). `force=True` macht die Funktion
    deterministisch wiederholbar (Tests, mehrfacher Import) statt vom
    Zufall abzuhaengen, ob der Root-Logger bereits Handler traegt."""
    level_name = os.environ.get("GZ_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=logging.getLevelName(level_name),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
```

Aufruf direkt nach der Modul-`logger`-Definition, vor `app = FastAPI(...)`.
`force=True` ist bewusst gewählt: ohne diese Option ist `basicConfig()`
laut Python-Dokumentation ein No-Op, sobald der Root-Logger bereits
irgendeinen Handler trägt — das würde die Funktion vom Aufrufkontext
abhängig und damit schwer testbar machen.

**Uvicorn-Verträglichkeit:** Uvicorn konfiguriert per Default ausschließlich
seine eigenen Logger (`uvicorn`, `uvicorn.error`, `uvicorn.access`), nicht
den Root-Logger — das ist im Analyse-Kontext (`docs/context/fix-1447-alarm-timeout.md`)
belegt und namensgebend für das Beobachtbarkeitsloch. `uvicorn.access` trägt
`propagate=False`, Zugriffszeilen laufen also nicht zusätzlich über den
Root-Logger — keine doppelten Zeilen. Diese Eigenschaft wird beim
Staging-Nachweis (s. Nachweisplan) stichprobenhaft bestätigt, nicht separat
im Kern automatisiert (dafür müsste ein echter uvicorn-Prozess mit seiner
realen Logging-Konfiguration hochgefahren werden — das sprengt die
Kern-Schicht und gehört, falls je nötig, in die Live-Schicht).

**Nebenwirkung Fremdbibliotheken (Adversary-Befund F001, behoben):** Die
fehlenden doppelten Zugriffszeilen sind nicht die einzige Nebenwirkung der
Root-Logger-Aktivierung. `httpx`/`httpcore` protokollieren auf INFO/DEBUG bei
jedem Request die vollständige URL. Die Telegram-Bot-API kodiert den
Zugangsschlüssel als URL-Pfadsegment (`.../bot{token}/sendMessage`) — mit dem
Root-Logger auf INFO wäre der Bot-Token sonst bei jedem Alarm und jedem
Briefing im Klartext ins Prozess-Log (`journalctl -u gregor-python`)
gewandert. Gegenmaßnahme: `configure_logging()` nagelt die Log-Stufe von
`httpx` und `httpcore` fest auf `WARNING`, unabhängig von `GZ_LOG_LEVEL` —
auch bei `GZ_LOG_LEVEL=DEBUG` zur Fehlersuche bleibt das Leck geschlossen.
Regressionsschutz: `tests/unit/test_logging_configuration.py` (echter
Telegram-Bot-Call gegen lokalen Test-Socket, prüft Abwesenheit eines
Platzhalter-Tokens in der gesamten aufgefangenen Log-Ausgabe).

## Expected Behavior

- **Input:** `POST /api/scheduler/alert-checks?user_id=<id>`, wie heute.
- **Output (vollständiger Lauf):** `{"status": "ok", "count": N, "checked":
  C, "skipped": 0, "duration_s": D}` — identische Alarm-Anzahl und
  Trip-Abdeckung wie vor dieser Scheibe.
- **Output (abgebrochener Lauf):** `{"status": "partial", "count": N,
  "checked": C, "skipped": S, "duration_s": D, "reason": "deadline"}`.
- **Side effects:** Root-Logger schreibt fortan INFO/WARNING-Zeilen aus
  `src/`, die vorher verworfen wurden. `httpx`/`httpcore` sind bewusst fest
  auf `WARNING` gehalten (s. „Uvicorn-Verträglichkeit" oben) — sonst wäre der
  Telegram-Bot-Token im URL-Pfad mitgeloggt worden. Kein Verhalten des
  Go-Schedulers ändert sich (s. u.).

## Vertragsänderung — Auswirkung auf den Go-Scheduler (recherchiert, nicht verändert)

`internal/scheduler/scheduler.go:361-399` (`triggerResponseBody`,
`triggerEndpointForUser`) wertet aus der Python-Antwort **ausschließlich**
das Feld `failed` als Ganzzahl aus:

```go
type triggerResponseBody struct {
    Status string `json:"status"`
    Count  int    `json:"count"`
    Failed int    `json:"failed"`
}
...
if jsonErr := json.Unmarshal(body, &parsed); jsonErr == nil && parsed.Failed > 0 {
    return fmt.Errorf(...)  // -> recordRun() speichert Status "error"
}
```

`Status`, `checked`, `skipped`, `duration_s` und `reason` werden von Go
**gar nicht gelesen** — `json.Unmarshal` ignoriert unbekannte Felder
stillschweigend, und `Status` wird nur in die Struct eingelesen, nie
abgefragt. Fehlt `failed` in der Antwort komplett (wie in der neuen
`"partial"`-Antwort dieser Scheibe vorgesehen), bleibt `parsed.Failed` auf
seinem Nullwert `0` — die Bedingung `parsed.Failed > 0` ist **falsch**.

**Ergebnis, ausdrücklich festgehalten:** Ein `"status": "partial"` **ohne**
`failed`-Feld kommt beim Go-Scheduler **als Erfolg** an. `recordRun()`
schreibt `Status: "ok"` in `lastRuns`, `/api/scheduler/status` zeigt für
diesen Job weiterhin „ok". Diese Scheibe ändert daran **nichts** — das
Go-Verhalten anzupassen (z. B. `failed` auch für `alert-checks` zu befüllen
und/oder `status` auszuwerten) ist ausdrücklich **Scheibe S2**, eigene
Spec. Bis dahin ist die INFO/WARNING-Logzeile aus Teil B der **einzige**
Ort, an dem ein abgebrochener Alarm-Lauf überhaupt sichtbar wird — der
Go-seitige Status bleibt blind dafür. Das ist eine bewusst in Kauf
genommene Zwischenlage dieser Scheibe, keine übersehene Lücke.

## Wechselwirkung mit dem #1405-Wächter (`tests/test_success_status_guard.py`)

Der Wächter listet `check_all_trips()` bereits als bekannten, bewusst noch
offenen Befund (Klasse 2, „teilerfolg-blind"):

- `KNOWN_VIOLATIONS["src/services/trip_alert.py:291"]` — Fundzeile ist die
  Zeile der `for`-Anweisung (`:291` heute).
- `SPEC_LISTED_FINDINGS["src/services/trip_alert.py::check_all_trips"] = 1`
  — funktionsnamen-basiert, zeilenunabhängig.

**Geprüft, was mit dem `skipped`-Zähler dieser Scheibe passiert:** Der
Scanner (`_find_partial_success_blind_violations`) erkennt eine Funktion
als „hat bereits einen echten Gegenzähler" (und überspringt sie komplett)
nur, wenn ein zurückgegebener Name **innerhalb eines
`except`-Handlers** hochgezählt wird (`_failure_counter_names()`,
`tests/test_success_status_guard.py:533-547` — geprüft werden ausschließlich
`handler.body`-Knoten). Der neue `skipped`-Zähler dieser Scheibe wächst in
einem gewöhnlichen `if time.monotonic() > deadline_at:`-Zweig, **nicht** in
einem `except`-Handler — er erfüllt die Ausnahmebedingung damit **nicht**.

**Folge:** Der zugrundeliegende B9-Befund (der `except Exception as e:
logger.error(...)`-Zweig um `check_and_send_alerts(...)` zählt Fehlschläge
nicht) bleibt nach dieser Scheibe **unverändert bestehen** — er wird von S1
weder behoben noch verschlimmert, weil S1 diesen `except`-Zweig nicht
anfasst. Das ist beabsichtigt: die Reparatur dieses konkreten
Gegenzähler-Defizits gehört zum #1405-Reparaturprogramm, nicht zu #1447.

**Was sich trotzdem ändern MUSS:** Die neuen Zeilen vor der Schleife
(Deadline-Berechnung, Zähler-Initialisierung) verschieben die `for`-Zeile
nach unten. `KNOWN_VIOLATIONS["src/services/trip_alert.py:291"]` wird damit
auf eine falsche Zeile zeigen und `test_known_violations_only_shrink`
schlägt fehl, weil der Scanner an Zeile 291 nichts mehr findet — **nicht,
weil der Befund behoben wäre**, sondern weil er umgezogen ist. Der
Eintrag MUSS deshalb als letzter Implementierungsschritt auf die neue
tatsächliche Zeile der `for`-Anweisung umgehängt werden (Text/Begründung
unverändert lassen, nur der Schlüssel ändert sich). **Der Eintrag darf
nicht gelöscht werden** — der Befund besteht fort. `SPEC_LISTED_FINDINGS`
braucht keine Änderung (funktionsnamen-basiert).

## Test-Plan / Test-Politik

Kein Mock-Theater. Kern-Schicht, deterministisch, kein echtes Warten.

- **Teil A (`tests/tdd/test_alert_run_deadline.py`):** Vorbild
  `tests/tdd/test_meteofrance_direct_fallback.py:476-517` — statt eines
  echten langsamen HTTP-Servers reicht hier ein Fake/eine kleine
  Testdouble-Trip-Liste mit mehreren Trips und einer künstlichen, echten
  `time.sleep(...)`-Verzögerung je geprüftem Trip (z. B. über eine
  monkeypatchte `_get_cached_weather`/`check_and_send_alerts`), kombiniert
  mit `monkeypatch.setattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS",
  0.05)` — echte, aber winzige Wartezeit statt 90 echter Sekunden.
  `pytest-timeout` (global 30s, `pyproject.toml:63`) bleibt damit
  unproblematisch.
- **Teil B (`tests/unit/test_logging_configuration.py`):** Ruft
  `api.main.configure_logging()` direkt auf (mit `monkeypatch.setenv`
  für `GZ_LOG_LEVEL`), liest danach `logging.getLogger().level` bzw.
  formatiert eine Test-`LogRecord` über den installierten Handler/
  Formatter und prüft, dass Zeitstempel, Stufe und Modulname im
  formatierten Ergebnis auftauchen — keine bloße String-Suche im
  Quelltext, echtes Verhalten des konfigurierten Loggers.
- **Namensregel:** Beide Testdateien nach Verhalten benannt, keine
  Issue-Nummer im Dateinamen.
- **Pfadregel #1409:** Beide Testdateien lösen ihren Prüfling relativ zur
  eigenen Testdatei auf (`Path(__file__).resolve().parents[2]`), nie über
  einen festen Hauptrepo-Pfad.
- **Bestandstest-Pflege:** `tests/test_success_status_guard.py` — s.
  vorheriger Abschnitt, nur Zeilennummer-Pflege, keine Signatur-Änderung
  am Wächter selbst.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer-Lauf von `check_all_trips()` hat die
  Zeitobergrenze bereits überschritten, während noch weitere, ungeprüfte
  Trips in der Liste stehen / When die Schleife die nächste Tour erreichen
  würde / Then wird diese und jede weitere verbleibende Tour **nicht**
  mehr geprüft, der Lauf endet stattdessen sofort.
  - Test: Mit künstlich verzögerter Prüfung und geschrumpfter Obergrenze
    (`monkeypatch`) bleiben nachweislich Trips hinter dem Abbruchpunkt
    ungeprüft (kein Aufruf der Prüf-Funktion für sie).

- **AC-2:** Given der Alarm-Lauf für einen Nutzer wird durch die
  Zeitobergrenze abgebrochen / When der Scheduler-Endpunkt
  `/api/scheduler/alert-checks` antwortet / Then enthält die Antwort
  `status: "partial"`, die Anzahl tatsächlich geprüfter Touren, die
  Anzahl übersprungener Touren und einen erkennbaren Grund für den
  Abbruch.
  - Test: HTTP-Antwort des Endpunkts (TestClient) enthält alle genannten
    Felder mit plausiblen, aus dem Lauf abgeleiteten Werten.

- **AC-3:** Given ein Alarm-Lauf für einen Nutzer schließt innerhalb der
  Zeitobergrenze vollständig ab / When der Scheduler-Endpunkt antwortet /
  Then meldet er `status: "ok"`, dieselbe Anzahl versendeter Alarme wie
  vor dieser Änderung, und keine einzige übersprungene Tour — das
  Verhalten unterscheidet sich für diesen Fall in nichts vom heutigen
  Stand.
  - Test: Ein vollständiger Durchlauf mit mehreren Trips und mindestens
    einem echten Alarm-Versand liefert identische Alarm-Anzahl wie der
    heutige `int`-Rückgabewert, plus `skipped: 0`.

- **AC-4:** Given ein Alarm-Lauf wird durch die Zeitobergrenze
  abgebrochen / When der Abbruch eintritt / Then wird eine WARNING-Zeile
  geschrieben, die die Obergrenze, die Anzahl geprüfter und die Anzahl
  übersprungener Touren nennt.
  - Test: `caplog` fängt eine WARNING-Zeile mit den drei genannten Werten
    ab.

- **AC-5:** Given irgendein Alarm-Lauf, egal ob vollständig oder
  abgebrochen / When der Lauf endet / Then wird eine INFO-Zeile mit der
  tatsächlichen Gesamtlaufzeit dieses Laufs geschrieben.
  - Test: `caplog` fängt für beide Fälle (vollständig und abgebrochen)
    je eine INFO-Zeile mit einem plausiblen Zeitwert ab.

- **AC-6:** Given der Python-Core-Prozess startet / When irgendein Modul
  unter `src/` eine INFO-Zeile protokolliert / Then landet diese Zeile
  mit Zeitstempel, Log-Stufe und Modulname sichtbar im konfigurierten
  Root-Logger-Ausgang, und die sichtbare Mindeststufe lässt sich über die
  Umgebungsvariable `GZ_LOG_LEVEL` verändern.
  - Test: `configure_logging()` direkt aufgerufen (einmal mit Default,
    einmal mit `GZ_LOG_LEVEL=DEBUG`/`WARNING` gesetzt), formatierte
    Ausgabe eines Test-Log-Eintrags enthält Zeitstempel, Stufenname und
    Modulnamen; bei `GZ_LOG_LEVEL=WARNING` wird eine INFO-Zeile
    nachweislich nicht ausgegeben.

- **AC-7:** Given die Zeitobergrenze ist im Produktivcode als benannte
  Konstante hinterlegt / When ein Test sie testweise verkleinern will /
  Then lässt sie sich per `monkeypatch.setattr` auf einen beliebigen,
  auch sehr kleinen Wert setzen, ohne Produktivcode anzufassen.
  - Test: Ein Testfall setzt die Konstante testweise auf einen Wert im
    Millisekundenbereich und beweist damit den Abbruch, ohne echte
    90 Sekunden zu warten.

## Known Limitations

- **Die Prüfung sitzt zwischen den Touren, nicht innerhalb einer Tour.**
  Eine einzelne Tour, deren Prüfung selbst unbegrenzt hängen kann (allen
  voran der SMTP-Versand ohne `timeout=` in
  `src/output/channels/email.py:433`, dazu der garantierte 50s-Retry-Schlaf
  dort und der ebenso ungeschützte Ersatzweg; ferner die Telegram-Bremse
  `src/output/channels/telegram.py:210-250` und die globalen
  `fcntl.flock`-Dateisperren ohne Timeout, z. B.
  `src/services/forecast_budget.py:178`), wird durch diese Scheibe **nicht**
  begrenzt — die Deadline-Prüfung wird für die hängende Tour selbst nie
  wieder erreicht. Diese Scheibe begrenzt die **Summe** der Arbeit eines
  Laufs, nicht den Einzelfall. Der Einzelfall ist Issue **#1448**, bewusst
  nicht Teil dieser Scheibe.
- **`openmeteo.fetch_forecast()` hat weiterhin kein eigenes
  `FETCH_DEADLINE`** (anders als `meteofrance.py`/`dwd.py`) — auch das
  gehört in dieselbe Klasse wie #1448, nicht zu S1.
- **Der Go-Scheduler bleibt gegenüber `status: "partial"` blind**, solange
  `failed` nicht mitgeliefert wird (s. „Vertragsänderung") — Scheibe S2
  behebt das auf Go-Seite (Überlappungsschutz + Auswertung), nicht diese
  Scheibe.
- **Offen bleibt unverändert:** Ob ein durch den Go-Client abgebrochener
  HTTP-Request den synchronen Python-Thread im Threadpool tatsächlich
  stoppt, ist weiterhin nicht bewiesen. Die neue Deadline-Prüfung in
  `check_all_trips()` deckelt die Arbeit unabhängig davon — sie braucht
  diese Antwort nicht, um zu wirken.
- **`ALERT_RUN_DEADLINE_SECONDS = 90.0` ist eine erste, konservative
  Reserve** gegenüber den 120s des Go-Clients (analog zur Begründung in
  ADR-0038) — keine empirisch hergeleitete Zahl. Sollte sich in Betrieb
  zeigen, dass 90s selbst für sehr große Nutzer mit vielen Trips zu knapp
  ist, ist das ein Folge-Befund, keine Verletzung dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0038
- **Rationale:** Es gab bislang kein ADR zu Zeitgrenzen/Wiederholungen für
  wiederkehrende Job-Läufe — beide bestehenden Retry-Specs (#1128, #1155)
  haben das ausdrücklich geprüft und offen gelassen. Diese Scheibe ist der
  erste konkrete Anwendungsfall des neu geschaffenen Grundsatzes: „Jeder
  wiederkehrende Job-Lauf bekommt eine harte Zeitobergrenze deutlich unter
  der Wartezeit seines Aufrufers; wird sie gerissen, bricht der Lauf
  sichtbar ab und meldet Teilerfolg." ADR-0038 hält diesen Grundsatz fest,
  inklusive der explizit verworfenen Alternative „Aufrufer-Wartezeit
  anheben" (verschärft das fehlende `SkipIfStillRunning` im
  Go-Cron-Scheduler, statt das Problem zu lösen).

## Changelog

- 2026-08-01: Initial spec created

---
entity_id: fix_2302_s1_provider_zeitbudget_baustein
type: module
created: 2026-09-11
updated: 2026-09-11
status: draft
version: "1.0"
tags: [provider, zeitbudget, deadline, retry, httpx, tenacity, alarm]
---

# fix_2302_s1_provider_zeitbudget_baustein

## Approval

- [ ] Approved

## Purpose

Ein geteilter Baustein `src/providers/http.py` fasst die drei Bestandteile des unter #1448 S3
in `openmeteo.py` gebauten Zeitbudget-Musters (Deadline-Hook, Stop-Bedingung, Timeout-Deckelung)
zusammen und wird von **zwei** Providern genutzt: `openmeteo.py` wird darauf migriert (reiner
Mechanik-Tausch), und der bisher ungeschützte Météo-France-**Grundpfad** (`meteofrance.py`,
`_request`/`_request_once`) bekommt dasselbe Zeitbudget wie der bereits geschützte
Gewitterpfad. Damit deckelt die Retry-**Kette** eines einzelnen `_request`-Aufrufs verlässlich
die verstrichene Wanduhrzeit, statt nur zwischen zwei `_request`-Aufrufen zu prüfen.

Diese Spec beschreibt ausschließlich **Scheibe A** von #2302 (Epic #2257 Block 2). Scheibe B
(`dwd.py` + `dwd_eu.py` + D5-Testüberarbeitung) und Scheibe C (`geosphere.py`, D2) folgen als
eigene Workflows unter demselben Issue.

## Source

- **File:** `src/providers/http.py` (neu), `src/providers/openmeteo.py`, `src/providers/meteofrance.py`
- **Identifier:** `make_deadline_before_hook`, `stop_at_deadline`, `capped_timeout_or_raise`
  (Schicht: Python-Core, `src/providers/`)

## Estimated Scope

- **LoC:** ~180–220 Code plus neue Tests
- **Files:** 4 — `src/providers/http.py` (neu), `src/providers/openmeteo.py`,
  `src/providers/meteofrance.py`, neue Testdatei unter `tests/tdd/` (Name nach Verhalten, z. B.
  `test_provider_request_deadline.py` — **nicht** nach Issue-Nummer)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_send_slot_and_fetch_deadline.py:140-188` | Fixture | `_HangingServer` (httpx-Kopie) — Regressionsnetz für die Open-Meteo-Migration und Quelle des Hänger-Bausteins für den neuen Wächter; übernehmen, nicht nachbauen |
| `tests/tdd/test_mail_send_deadline.py:63-116` | Fixture | Original von `_HangingServer` — hier verwenden, wer `.connection_count` braucht (fehlt in der httpx-Kopie) |
| `docs/specs/modules/fix_1448_s3_telegram_openmeteo.md` | Vorlage | Verbindlich ist nur das Ergebnis (Versuchszahl *und* verstrichene Zeit begrenzt), nicht die Bauform; Team-Lead-Präzisierung `:157-176` macht den `before`-Hook-Ersatzweg zur geforderten Eigenschaft |
| `src/providers/base.py` (`:7-16`) | Upstream | Registry und Fehlerklassen, bewusst **ohne** `httpx`/`tenacity`-Import — Grund, warum der Baustein in `http.py` liegt, nicht in `base.py` |

## Implementation Details

### Neue Datei `src/providers/http.py`

| Funktion | Aufgabe |
|---|---|
| `make_deadline_before_hook(deadline_attr: str)` | Fabrik; liefert einen tenacity-`before`-Hook, der `kwargs["deadline_at"]` setzt, wenn keiner übergeben wurde. Der `if … is None`-Wächter ist der Kern — ohne ihn wäre die Ersatzfrist rollend und die Obergrenze wirkungslos. **Kein** `getattr`-Default: fehlt der Accessor am Provider, soll es knallen, nicht still `None` liefern. |
| `stop_at_deadline(retry_state) -> bool` | generisch, keine Fabrik nötig — liest nur `retry_state.kwargs.get("deadline_at")` gegen `time.monotonic()` |
| `capped_timeout_or_raise(*, provider_name, base_timeout, deadline_at, budget_label, budget_seconds)` | Verallgemeinerung von `openmeteo.py:666-673`; Fehlertext-Bausteine (`budget_label`, `budget_seconds`) kommen vom Aufrufer, damit jede Datei ihren eigenen Wortlaut behält |

Je Provider-Modul eine Accessor-Methode, die das Modul-Global zur **Aufrufzeit** frisch liest:

```python
# je Provider-Modul, z. B. openmeteo.py / meteofrance.py
def _fetch_deadline_seconds(self) -> float:
    return FETCH_DEADLINE_SECONDS   # Modul-Global, Lookup zur AUFRUFZEIT
```

Der geteilte Hook schließt über den **Methodennamen** (stabil), nie über den **Wert**
(volatil, von Tests gepatcht) — eine Closure, die den Wert beim Dekorieren einfriert (z. B.
`make_deadline_before_hook(60.0)`), fällt genau in die verbotene Falle und muss vermieden
werden.

**Jeder Provider baut seinen `@retry(...)` weiterhin selbst.** Es entsteht **kein** gemeinsames
`Retrying`-Objekt — die Bausteine sind Fabriken/Funktionen, kein Modul-Level-Dekorator-Objekt.

### Migration `openmeteo.py`

Reiner Mechanik-Tausch, kein Verhaltenswechsel:

| Bestehend | Ersetzt durch |
|---|---|
| `_resolve_request_deadline` (`:286-301`) | `make_deadline_before_hook("_fetch_deadline_seconds")` |
| `_stop_at_request_deadline` (`:304-313`) | `stop_at_deadline` |
| Kopf-Check + Deckelung (`:666-673`) | `capped_timeout_or_raise(provider_name="openmeteo", base_timeout=TIMEOUT, ...)` |

Neue Methode `_fetch_deadline_seconds(self) -> float: return FETCH_DEADLINE_SECONDS` an
`OpenMeteoProvider`.

**Migrationsnachweis:** `tests/tdd/test_send_slot_and_fetch_deadline.py` bleibt **unverändert**
grün. Diese Datei trägt `pytestmark = pytest.mark.live` (`:91`) und wird vom Normallauf
(`pyproject.toml:65`, `addopts = -q -m 'not email and not live and not staging'`) komplett
verworfen — ein schlichter `uv run pytest`-Lauf sammelt dort null Tests und endet mit Exit 5,
sieht also fälschlich erfolgreich aus. Der Nachweis wird deshalb mit `-m ''`-Override gefahren
**und** mit einem `--collect-only`-Beleg (Anzahl gesammelter Tests > 0) im QA-Artefakt
hinterlegt. Die Datei wird in Scheibe A **nicht** entmarkert — die allgemeine
Marker-Bereinigung gehört laut D4 nach #1196. Stattdessen decken AC-4 und AC-5 unten den
migrierten Open-Meteo-Pfad zusätzlich im neuen, ungemarkerten Wächter ab, damit die Migration
nicht allein von einem im Normallauf unsichtbaren Testsatz bewacht wird.

### `meteofrance.py` — Grundpfad

Der Grundpfad `fetch_forecast` → `_fetch_series` (`:508`) → `_request` (`:428`) →
`_request_once` (`:436`) ist heute **ohne** Zeitbudget: `_request` trägt keinen
`deadline_at`-Parameter, `_request_once` erhält keinen `timeout=` von dort. Das steht im
Gegensatz zum bereits geschützten Gewitterpfad (`fetch_thunder_signals_multi` → `_request_once`
direkt, `:644-648`), der bereits `timeout=restzeit` selbst berechnet und durchreicht (K2).

`_request` bekommt einen `deadline_at: Optional[float] = None`-Parameter, wird mit denselben
geteilten Bausteinen dekoriert (`make_deadline_before_hook("_fetch_deadline_seconds")`,
`stop_at_deadline` per `|` mit `stop_after_attempt(RETRY_ATTEMPTS)`), und reicht den
verbleibenden Rest der Frist an `_request_once`s `timeout`-Parameter (`:478`,
`request_timeout = TIMEOUT if timeout is None else min(TIMEOUT, timeout)`) durch — analog zum
bestehenden Gewitterpfad. Neue Methode `_fetch_deadline_seconds(self) -> float: return
FETCH_DEADLINE_SECONDS` an `MeteoFranceDirectProvider` (Modul-Global `:93`, 180.0).

### Bewusst NICHT geteilt (kein Versehen)

- `RETRY_STATUS_CODES` bleibt divergent. `meteofrance.py:86` dokumentiert die 500 explizit als
  Reaktion auf Adversary #1143 F002 — ein Vereinheitlichen wäre eine stille
  Verhaltensänderung mit eigener Vorgeschichte.
- `_is_retryable_error` bleibt je Modul (nur `openmeteo.py` hat den `__cause__`-Zweig `:277-282`).

### Portier-Falle

`retry_with(stop=…)` **ersetzt** den `stop`-Parameter, es ergänzt ihn nicht
(`tenacity/__init__.py:262-275`, `stop=_first_set(stop, self.stop)`). Der `before`-Hook
überlebt einen solchen Aufruf, die Stop-Seite nicht. In Scheibe A relevant nur als
Warnhinweis für künftige Nutzer des Bausteins — beide hier migrierten Pfade (`openmeteo.py`
Kandidatenschleife ausgenommen, `meteofrance.py`-Grundpfad) bauen `@retry(...)` direkt am
Dekorator, nicht über `retry_with`.

### Harte Randbedingung für die Migration

Die Modul-Globals `TIMEOUT` und `FETCH_DEADLINE_SECONDS` dürfen **nicht** nach `http.py`
verschoben oder umbenannt werden — `test_send_slot_and_fetch_deadline.py:409-413`, `:593-597`,
`:641-645` patchen sie direkt (`monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", ...,
raising=False)`). Der Baustein liest diese Werte ausschließlich über die providereigene
Accessor-Methode, nie direkt aus `http.py` heraus.

## Expected Behavior

- **Input:** Aufruf von `_request` (Météo-France Grundpfad oder Open-Meteo), mit oder ohne
  explizit übergebenes `deadline_at`.
- **Output:** Bei einer hängenden Gegenstelle bricht die Retry-Kette spätestens bei erreichter
  Frist mit `ProviderRequestError` ab; die tatsächlich verstrichene Wanduhrzeit bleibt unter
  einer großzügig bemessenen Obergrenze. Ein normal antwortender Server liefert unverändert
  Daten.
- **Side effects:** Keine geteilten `Retrying`-Objekte — jeder Provider behält sein eigenes,
  von den anderen unabhängiges Retry-Verhalten. `TIMEOUT` und `FETCH_DEADLINE_SECONDS` bleiben
  Modul-Globals in `openmeteo.py` bzw. `meteofrance.py`.

## Acceptance Criteria

- **AC-1:** Given der Météo-France-**Grundpfad** ruft gegen eine Gegenstelle, die die Verbindung annimmt und nie antwortet (`_HangingServer`), mit auf Millisekunden gepatchtem `FETCH_DEADLINE_SECONDS` / When `fetch_forecast` bzw. direkt `_request` aufgerufen wird / Then bricht der Aufruf mit `ProviderRequestError` ab, und die tatsächlich verstrichene Wanduhrzeit liegt unter einer großzügig bemessenen Obergrenze.
  - Test: Neuer Test gegen `_HangingServer` (übernommen aus `test_send_slot_and_fetch_deadline.py:140-188`) mit gepatchtem `FETCH_DEADLINE_SECONDS`, misst `elapsed` per `time.monotonic()` und prüft `elapsed <` einer großzügigen Obergrenze innerhalb von `pytest.raises(ProviderRequestError)`. Zusicherungsform ist ausdrücklich die Wanduhr, **nicht** Aufrufzählung und **nicht** „`timeout=` wurde durchgereicht".

- **AC-2:** Given dieselbe hängende Gegenstelle, aber die Wartepausen zwischen den Retry-Versuchen werden **nicht** per `wait_none()` neutralisiert, sondern bleiben spürbar stehen (Muster `test_stop_condition_limits_retry_backoff_within_deadline`, `wait_fixed(...)`) / When der Grundpfad mehrfach retryt / Then deckelt die Frist die **Kette aus Versuchen und Wartepausen gemeinsam**, nicht nur die Dauer eines einzelnen Versuchs.
  - Test: Wie AC-1, aber mit stehen gelassenem `wait_fixed(...)` statt `wait_none()`; `elapsed` bleibt trotz mehrerer Wartepausen unter der Obergrenze. Begründung: In der 390-Sekunden-Rechnung des Tickets sind 4 × bis 60 s Pause der größere Anteil gegenüber 5 × 30 s — eine AC, die die Pausen neutralisiert, würde diesen Anteil unbewacht lassen.

- **AC-3:** Given ein normal antwortender lokaler Server (kein Hang) / When derselbe migrierte bzw. neu geschützte Pfad aufgerufen wird / Then liefert er unverändert Daten und bricht **nicht** vorzeitig ab.
  - Test: Muster `test_send_slot_and_fetch_deadline.py:439` (`test_normal_case_unaffected_by_new_deadlines`) — Gegenprobe gegen einen Server, der sofort antwortet. Pflichtbestandteil: Ohne diese AC wäre ein Fix, der alles sofort abbricht, ebenfalls grün.

- **AC-4:** Given `_request` wird **ohne** den Parameter `deadline_at` aufgerufen / When der geteilte `before`-Hook feuert / Then setzt er die Frist selbst aus der providereigenen `_fetch_deadline_seconds()`-Accessor-Methode, und die Frist hält — die Zusicherung hängt nicht daran, dass eine Aufrufstelle sie durchreicht.
  - Test: Gegen `_HangingServer`, `_request` ohne `deadline_at`-Argument aufgerufen, für **beide** in Scheibe A berührten Provider (Météo-France und Open-Meteo) — jeweils `elapsed <` Obergrenze. Wörtliche Begründung aus `fix_1448_s3_telegram_openmeteo.md:157-176`: „eine Absicherung, die man vergessen kann einzuschalten, ist im Ernstfall keine."

- **AC-5:** Given das Modul-Global `FETCH_DEADLINE_SECONDS` wird **zur Laufzeit** gepatcht (wie alle Bestandstests es tun, z. B. `monkeypatch.setattr(om_module, "FETCH_DEADLINE_SECONDS", ..., raising=False)`) / When `_request` aufgerufen wird / Then gilt der gepatchte Wert.
  - Test: Für **beide** Provider ein Test, der `FETCH_DEADLINE_SECONDS` per `monkeypatch` auf einen anderen Wert setzt und prüft, dass die Frist entsprechend reagiert (z. B. auf einen sehr kleinen Wert gesetzt → sofortiger Abbruch trotz erreichbarem Server). Eine Bauform, die den Wert beim Dekorieren in eine Closure einfriert (z. B. `make_deadline_before_hook(60.0)` statt `make_deadline_before_hook("_fetch_deadline_seconds")`), muss an dieser AC scheitern, weil der Patch dann ins Leere liefe.

- **AC-6:** Given der geteilte Baustein ist in beiden Providern verdrahtet / When die Retry-Konfiguration des einen Providers verändert wird (z. B. `MeteoFranceDirectProvider._request.retry.wait` gepatcht) / Then bleibt das Verhalten von `OpenMeteoProvider._request` unverändert — es existiert **kein** geteiltes `Retrying`-Objekt.
  - Test: **Verhaltensbasiert**, nicht nur `is`-Vergleich: Patcht die Retry-Konfiguration eines Providers (z. B. `wait`) und misst, dass sich die Laufzeit/Retry-Anzahl des anderen Providers dadurch **nicht** ändert. Ergänzend die strukturelle Invariante `MeteoFranceDirectProvider._request.retry is not OpenMeteoProvider._request.retry` — aber allein genügt sie nicht, weil sie nur den Draht prüft, nicht die Wirkung.

- **AC-7:** Given die neue Testdatei trägt **keinen** der Marker `live`/`email`/`staging` (Vorlage `tests/tdd/test_alert_run_deadline.py`) / When ein normaler `uv run pytest --collect-only`-Lauf über die Datei läuft / Then sammelt er `N > 0` Tests aus dieser Datei.
  - Test: `uv run pytest --collect-only tests/tdd/<neue Datei>.py` im Normallauf (ohne `-m`-Override) zeigt eine Anzahl gesammelter Tests größer 0; das Ergebnis geht ins QA-Artefakt. Jeder Hänger-Test trägt zusätzlich ein eigenes `@pytest.mark.timeout(N)`, weil `pyproject.toml:69` global `timeout = 30` setzt. D4 macht das ausdrücklich zur AC, nicht zum Nebensatz.

## Known Limitations

- **Tröpfel-Fall (D6, Weg b — vertagt, eigenes Ticket):** Das httpx-Skalar-Timeout begrenzt die
  Wartezeit auf das **nächste Stück Daten**, nicht die Gesamtdauer. Selbst gemessen: ein Byte
  alle 0,3 s bei 0,5 s Timeout → Erfolg nach 6,08 s, Faktor 12,2. Das kopierte Muster schließt
  das **nicht**. Der Fix deckelt die Wiederholungs**kette**, nicht eine einzelne beliebig lang
  hingezogene Antwort.
- **K3-Lauf-Rückfall** (`meteofrance.py:641`, drei Modell-Lauf-Kandidaten ohne Budgetprüfung
  dazwischen) bleibt in Scheibe A offen.
- **Anreicherungskette / Kandidatenschleife** von Open-Meteo ist ADR-0038-Gebiet und
  ausdrücklich nicht gedeckt (`openmeteo.py:1147/1169/1239/1247` laufen alle nach Ablauf der
  Kandidatenschleifen-Frist, keine unter ihr).
- **Cross-Provider-Totalausfall und Gewitter-Vertretung** bekommen laut ADR-0047 Entscheidung 6
  (PO, 06.08.2026) ihr **eigenes volles Budget**; eine Restzeit-Weitergabe zwischen Quellen wäre
  eine stille ADR-Umkehr und ist verboten.
- **Die einzige echte Verhaltensverschlechterung:** `min(base_timeout, restzeit)` kann am Ende
  einer langen Offset-Schleife **unter** die heutigen festen 30 s fallen — ein Abruf, der heute
  in 25 s durchkäme, kann nach dem Fix mit 5 s Restzeit scheitern. Gewollte Wirkung, aber im PR
  explizit zu benennen.
- **Nie beobachtet:** Der Nachweis bleibt Konstruktion gegen `_HangingServer`; es gibt keinen
  Live-Vorfall zu reproduzieren. Der einzige real aufgetretene Fehler (401 bei Météo-France)
  kann es nachweislich nicht auslösen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** ADR-0038 (`docs/adr/0038-…:91-94`) weist genau diese Klasse — „einzelne in
  sich unbegrenzt blockierende Schritte" — ausdrücklich #1448 zu und deckt sie selbst nicht ab;
  #2302 ist die dort ausgenommene Klasse. ADR-0047 Entscheidung 6 bleibt unberührt (keine
  Restzeit-Weitergabe zwischen Quellen). ADR-0018 (Fallback ohne Kaschieren) verlangt, dass ein
  Fristabbruch als solcher erkennbar bleibt und nicht als leeres Ergebnis durchgeht — deshalb
  bleibt `ProviderRequestError` der Abbruchmechanismus.

## Changelog

- 2026-09-11: Initial spec created (Scheibe A von #2302)

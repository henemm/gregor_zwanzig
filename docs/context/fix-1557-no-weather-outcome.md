# Context: fix-1557-no-weather-outcome

Issue: [#1557](https://github.com/henemm/gregor_zwanzig/issues/1557) · Label `type:bug`, `priority:high`, `session:khw`

## Request Summary

Der Test-Sendepfad eines Trip-Briefings meldet `sent` bzw. HTTP 200
`{"sent": true}`, obwohl für den Trip **keine** Wetterdaten beschafft werden
konnten. Erwartet wäre der ehrliche Outcome `no_weather` mit HTTP 422. Zu
klären ist, ob das Ist-Verhalten ein Produktfehler ist oder der Test veraltet.

## Reproduktion (gemessen 2026-08-14, offline)

```
uv run pytest tests/tdd/test_trip_report_test_send_past_stage_clamp.py \
  --allow-hosts=127.0.0.1,::1 -p no:randomly -q
→ ..FF   (AC-1 und AC-2 grün, beide AC-3-Tests rot)
```

- `TestAC3…::test_service_outcome_is_no_weather_when_today_also_fails`
  → `AssertionError: Erwartet ehrliches 'no_weather', bekommen 'sent'`
- `TestAC3…::test_router_returns_422_with_honest_no_weather_message`
  → `AssertionError: Erwartet 422, bekommen 200: {"status":"ok",…,"sent":true}`

Die Datei steht in `.github/ci_tdd_excludes.txt:88` (offline rot, von der
CI-Ampel ausgenommen).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_report_scheduler.py:1175` | Datums-Klemme im Test-Fallback-Pfad (`allow_test_fallback`) |
| `src/services/trip_report_scheduler.py:1244–1275` | `error_ratio` gegen `OUTAGE_WITHHOLD_RATIO`; `return "no_weather"`; `send_no_data_hint` + `_write_pending_marker` |
| `src/services/trip_report_scheduler.py:1807–1831` | `_fetch_weather` — beschafft Provider via `get_provider("openmeteo")`, baut `SegmentWeatherService` |
| `src/services/segment_weather.py:449–480` | zweite Beschaffungsstelle (Nacht-Wetter), `provider or get_provider("openmeteo")`, `except Exception → return None` |
| `src/providers/base.py:202` | `get_provider` — der vom Test gepatchte Einstieg |
| `api/routers/scheduler.py:204–262` | HTTP-Route `POST /api/scheduler/trips/{id}/send`; 422-Zweige für `no_stage` (`:236`), `no_weather` (`:246`), `no_channels` (`:257`) |
| `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` | Prüfling; Provider-Double `_DateSensitiveOpenMeteoDouble:106`, Patch `:139` |
| `docs/specs/modules/staging_selftest_stage_clamp.md` | Spec zu #1325 mit den freigegebenen ACs 1–3 |

## Existing Patterns

- **Outcome-String statt Boolean:** Der Sendepfad liefert einen von fünf
  Werten — `sent`, `no_stage`, `no_weather`, `no_channels`,
  `channels_unreachable`. Jeder bekommt in der Route einen eigenen
  422-Zweig mit sprechender Meldung (Muster aus #904 → #1325 → #1403).
- **Erfolg wird abgeleitet, nie behauptet** (#1405): `tests/test_success_status_guard.py`
  ist ein projektweiter Wächter gegen genau diese Fehlerklasse — die
  „unverdiente Erfolgsmeldung". Belegte Vorfälle im Wächter-Kopf: #1290,
  #1346, #1348, **#1403 („Sende-Endpunkt meldet `sent: true` ohne
  Zustellung")**. Die Norm im eigenen Code ist
  `run_briefing_dispatch()` → `(sent, failed)`-Tupel.
- **Teilausfall-Schwelle statt binär** (#1113): `_fetch_weather` liefert bei
  Provider-Fehlern pro Segment einen `has_error=True`-Platzhalter; erst
  `error_ratio > OUTAGE_WITHHOLD_RATIO` hält das Briefing zurück, darunter
  gibt es einen Teilausfall-Hinweis im Text.

## Dependencies

**Upstream** (was der betroffene Code nutzt): `providers.base.get_provider`
→ `OpenMeteoProvider`; `SegmentWeatherService`; `NotificationService`
(`send_no_data_hint`, `_send_email`); `app.loader` (`load_all_trips`,
`get_briefings_dir`).

**Downstream** (was die Outcomes verbraucht):

| Verbraucher | Verhalten bei `no_weather` |
|---|---|
| `api/routers/scheduler.py:246` | HTTP 422, „keine Wetterdaten für die gewählte Etappe verfügbar" |
| `src/services/dispatch_orchestrator.py:85` | zählt als **`failed`**, nicht als `sent` (#1012 c) |
| `src/services/trip_report_scheduler.py:94` `VERMERK_AUSGAENGE` | Slot **wird** vermerkt — sonst stündliche „keine Daten"-Mail plus stündlicher voller Wetterabruf gegen das Kontingent (#1329); die Nachlieferung deckt der Pending-Marker ab (#1012) |
| `src/services/trip_command_processor.py:247` | On-Demand-Antworttext „Wetterdaten aktuell nicht verfügbar — bitte später erneut versuchen." |
| Go (`internal/`, `cmd/`) | **kein** Verbraucher (grep leer) |

## Existing Specs

- `docs/specs/modules/staging_selftest_stage_clamp.md` — **AC-3 ist dort
  freigegeben und wörtlich das, was der rote Test prüft**: „Given ein
  Test-Sendeversuch, bei dem trotz gültigem (heutigem) Datum tatsächlich
  keine Wetterdaten beschafft werden können, … Then liefert
  `api/routers/scheduler.py` eine ehrliche, unterscheidbare Fehlermeldung
  bzw. der Service einen klar benannten Outcome". Der Test Plan (`:168`)
  benennt beide Ebenen (Service-Outcome **und** Router-422) exakt so.
- „Known Limitations" der Spec (`:110`) nennt Cron-Rechte und den toten
  Legacy-Persistenzpfad — **nicht** den AC-3-Fall. Der ist also nicht
  bewusst offengelassen worden.

## Angrenzende Tests (mögliche zweite Testfamilie)

`tests/test_success_status_guard.py` · `tests/tdd/test_issue_1012_no_data_guard.py` ·
`tests/tdd/test_issue_1113_partial_outage_guard.py` ·
`tests/tdd/test_issue_1007_heute_voll_briefing.py` ·
`tests/tdd/test_send_idempotenz_lock.py` — alle grün, alle mit Bezug zu
`no_weather`. Dass sie grün sind, während AC-3 rot ist, ist ein Hinweis auf
zwei Testfamilien in verschiedenen Welten; welche die *wirkende* Stelle
prüft, ist in der Analyse zu klären.

## Risks & Considerations

1. **Die Ursache ist nicht durch Lesen ableitbar.** Der `no_weather`-Zweig
   existiert (`trip_report_scheduler.py:1273`) und der 422-Zweig existiert
   (`scheduler.py:246`) — beide greifen trotzdem nicht. Erster Prüfpunkt der
   Analyse: **greift der Provider-Double überhaupt?** Beide Beschaffungs­stellen
   importieren `get_provider` funktionslokal, der Patch auf
   `providers.base.get_provider` sollte also wirken. Wenn er wirkt, muss
   irgendwo zwischen Fehler und Outcome Ersatz-/Restdaten entstehen.
2. **Zwei Fehlerrichtungen, beide teuer.** Wird der Test angepasst,
   zementiert das eine unverdiente Erfolgsmeldung — die laut #1405 „für den
   Betrieb schlimmer als ein Fehler" ist, weil sie den Alarm abschaltet.
   Wird am Rückhalte-Zweig gedreht, können Briefings unterdrückt werden, die
   heute korrekt rausgehen — das trifft **alle vier Kanäle** und den
   kritischen Pfad jedes Trips.
3. **`no_weather` schließt den Slot** (`VERMERK_AUSGAENGE`). Jede Änderung an
   der Outcome-Ableitung ändert damit auch Wiederholungs- und
   API-Kontingent-Verhalten (#1329) — nicht nur einen HTTP-Status.
4. **Provider-Double ist nicht der Produktionspfad.** Was der Double auslöst,
   muss gegen das reale Open-Meteo-Verhalten gehalten werden; ein Fix, der nur
   den Double zufriedenstellt, wäre wertlos.
5. **Nach dem Fix:** Zeile 88 aus `.github/ci_tdd_excludes.txt` entfernen
   (Ratsche #1196) — nur ENTFERNEN ist dort erlaubt.

---

# Analysis (Phase 2)

## Type

**Bug** — und zwar ein *Test-Isolationsfehler*, nicht der im Issue vermutete
Produktfehler und auch kein veralteter Test.

## Ursache (gemessen, nicht erschlossen)

| Messung | Ergebnis |
|---|---|
| AC-3 **isoliert**: `pytest …::TestAC3GenuineNoWeatherHonestOutcome` | **grün** (`..`) |
| Ganze Datei (AC-1 → AC-2 → AC-3) | `..FF` — AC-3 rot |

Der Unterschied ist allein die Vorgeschichte im Prozess. Mechanismus:

1. `SegmentWeatherService.fetch_segment_weather` fragt **zuerst** den geteilten
   Wetter-Cache (`src/services/segment_weather.py:143`) — ein Prozess-Singleton
   mit 600 s TTL (`src/services/weather_cache.py:294`).
2. AC-1 läuft mit `fail_for_today=False`, holt echte Fixture-Daten und füllt den
   Cache für das auf „heute" **geklemmte** Fenster.
3. AC-3 läuft mit `fail_for_today=True` gegen dasselbe geklemmte Fenster →
   **Cache-Treffer**. Der absichtlich scheiternde Provider-Double wird nie
   aufgerufen.
4. Damit gibt es keine `has_error`-Segmente, `error_ratio` bleibt `0.0`, die
   Bedingung `error_ratio > OUTAGE_WITHHOLD_RATIO` (0.75,
   `src/services/trip_report_scheduler.py:72`/`:1249`) ist falsch → kein
   `no_weather`, Briefing wird gebaut → `sent` → HTTP 200.

Der Provider-Double *ist* installiert; er wird nur nie erreicht. Das ist der
Unterschied zwischen „Patch wirkungslos" und „Patch wird umgangen".

**Zweiter, unabhängiger Befund:** Der Router-Test hängt an `Settings()` aus der
Umgebung. Ohne SMTP-Variablen antwortet die Route mit 422 „SMTP not configured"
(`api/routers/scheduler.py:230`), bevor sie den ehrlichen No-Weather-Zweig
erreicht. Lokal ist der Test nur deshalb aussagekräftig, weil eine echte `.env`
im Arbeitsordner liegt — dieselbe stille Rückfall-Mechanik wie in #1477. Auf
einem CI-Runner ohne `.env` prüft er etwas anderes als beabsichtigt.

## Vorarbeit auf einem nicht gemergten Branch

`origin/ws/fix-1557-no-weather` @ `6c3c7ec9` (2026-08-08) — **nicht** in `main`,
kein PR gemerged. Ändert nur zwei Dateien:

- `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` (+23):
  `@pytest.fixture(autouse=True) _isolated_weather_cache` **in der Testdatei**
  (Reset vor und nach jedem Testfall) plus `monkeypatch.setenv` für
  `GZ_SMTP_HOST`/`_USER`/`_PASS` im Router-Test.
- `.github/ci_tdd_excludes.txt` (+8/−1): Eintrag entfernt, Zähler 30 → 29.

Produktivcode unberührt. **Nicht nachgemessen**, ob der Commit die Datei
vollständig grün macht — das ist in Phase 5/6 zu belegen, nicht zu glauben.

## Wirkort der Isolation: `conftest.py`, nicht die Testdatei

Gemessen: **sieben** Testdateien setzen den geteilten Wetter-Cache bereits
selbst zurück — in zwei Bauarten:

- eigene `@pytest.fixture(autouse=True)`, funktions-scoped:
  `test_alarm_zeitfenster_ziel.py:60-64`, `test_alert_data_freshness.py:107-111`,
  `test_forecast_cache_sharing.py:200-206`, `test_forecast_budget_gate.py:106-110`
- direkter Aufruf an der Bedarfsstelle, ohne Fixture:
  `test_compare_alert_day_window.py:261`,
  `test_thunder_night_addendum_parity.py:209`,
  `test_segment_weather_snowfall_limit.py:116/128/149/156/184`

Eine frühere Fassung dieses Abschnitts behauptete „alle autouse, alle
funktions-scoped" — das war für vier der sieben Dateien nachgemessen und für
die übrigen drei verallgemeinert. Korrigiert.

Daraus folgt:

- Der blinde Fleck ist **repo-weit**, nicht dateispezifisch. Eine achte Kopie
  behebt den achten Fall und lässt den neunten offen.
- Der Präzedenzfall steht schon in `tests/conftest.py`: Radar-Cache (`:280`) und
  Thunder-Window-Cache (`:295`) wurden mit #1329 C2 genau dort zentral
  zurückgesetzt — der Wetter-Cache, das ältere und breiter genutzte Singleton,
  **fehlt** in dieser Reihe.
- **Kein Kollateralschaden zu erwarten**, aber nachweispflichtig: da alle
  bestehenden Reset-Fixturen funktions-scoped sind, verlässt sich kein Test auf
  Cache-Inhalt über Testfallgrenzen hinweg. Ein zentraler Reset macht die sieben
  lokalen Kopien redundant, nicht falsch. Belegt wird das durch einen Lauf der
  acht betroffenen Dateien plus der Scheduler-/Trip-Suiten — nicht durch dieses
  Argument.

Fällt dieser Nachweis negativ aus, ist die enge Variante aus `6c3c7ec9` der
Rückfallweg.

## Produktrisiko: geprüft und verneint

Der Cache hat die Blindheit erzeugt — daraus folgt aber kein Produktfehler.
TTL 600 s heißt: ein `sent` stützt sich auf höchstens zehn Minuten alte echte
Vorhersagedaten. Dass ein Provider-Ausfall dadurch bis zu zehn Minuten
unsichtbar bleibt, ist die beabsichtigte Wirkung von #1329 (API-Kontingent) und
keine unverdiente Erfolgsmeldung im Sinne von #1405. **Kein Produktcode-Änderungs­bedarf.**

## Rückfall-Wächter: keiner neu nötig

Die Fehlerart ist ein Reihenfolgen-Effekt — ein grüner Einzellauf verdeckt sie.
Genau dagegen wirken zwei bereits vorhandene Mechanismen, sobald die Datei die
Ausschlussliste verlässt: der CI-`test`-Job führt sie **im Verbund** aus (das ist
die Bedingung, unter der der Fehler auftritt), und `pytest-randomly` variiert die
Reihenfolge zwischen Läufen. Ein neues Dauergate wäre hier reiner Zuwachs ohne
Fangfläche — die Ratsche #1196 ist der Wächter.

## Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `tests/conftest.py` | MODIFY | autouse-Fixture `_reset_shared_weather_cache`, analog `:280`/`:295` |
| `tests/tdd/test_trip_report_test_send_past_stage_clamp.py` | MODIFY | Dummy-SMTP-Env im Router-Test (Hermetik) |
| `.github/ci_tdd_excludes.txt` | MODIFY | Zeile 88 entfernen (Ratsche — nur Entfernen erlaubt) |
| Produktivcode (`src/`, `api/`, `internal/`) | — | **unverändert** |

## Scope Assessment

- Dateien: 3 (alle Test-/CI-Seite)
- LoC: Produktiv **+0/−0**, Test ca. **+20/−1**
- Risiko: **MEDIUM** — nicht wegen der Größe, sondern weil ein zentraler
  Cache-Reset alle Suiten berührt. Der Nachweis, nicht die Änderung, ist die
  Arbeit.

## Nebenbefund (Triage separat, nicht Teil dieses Tickets)

`src/services/dispatch_orchestrator.py:85-88` zählt im regulären Scheduler-Lauf
**nur** `no_weather` als `failed`; `no_stage`, `no_channels` und
`channels_unreachable` zählen als `sent`. Der Lauf meldet dann
`status: "ok"` (`api/routers/scheduler.py:55-57`), obwohl niemand etwas bekommen
hat. Gleiche Fehlerklasse wie #1557 (unverdiente Erfolgsmeldung, #1405), aber
eigener Auslöser und nutzersichtbar im Monitoring ⇒ Kandidat für ein **eigenes
Issue**, nicht für #1199. Ebenfalls notiert: `trip_command_processor.py:270`
lässt jeden **unbekannten** Outcome still auf den „Keine Etappe geplant"-Text
fallen.

## Open Questions

- [ ] Keine offenen fachlichen Fragen. Die im Issue gestellte Frage ist
      beantwortet: Produktcode korrekt, Test gültig, Isolation defekt.

---

## Vorläufige fachliche Einordnung (Phase 1 — durch die Analyse bestätigt)

Die im Issue gestellte Frage „Bug oder veralteter Test?" lässt sich anhand
der Belege bereits eingrenzen: AC-3 ist eine **freigegebene** Spec-Anforderung
aus #1325, und das Projekt hat für exakt diese Fehlerklasse einen eigenen
Wächter (#1405). Es gibt keinen Beleg für eine spätere Gegenentscheidung.
Der Test bildet damit weiterhin die gewollte Anforderung ab — **wo** die
Zusicherung bricht, ist offen.

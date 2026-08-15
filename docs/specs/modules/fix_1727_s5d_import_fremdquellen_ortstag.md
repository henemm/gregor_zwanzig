---
entity_id: fix_1727_s5d_import_fremdquellen_ortstag
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [timezone, gpx-import, official-alerts, massif-closure, meteo-forets, debug-router, issue-1727, issue-1722, adr-0044, adr-0051]
workflow: fix-1727-s5d-import-fremdquellen
---

# Fix #1727 S5d — Import und Fremdquellen folgen dem Ortstag

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-15

## Purpose

Sieben Fundstellen in vier Dateien bestimmen den Kalendertag weiterhin über die Serveruhr
(`date.today()`/`datetime.now()` ohne Zone) statt über einen fachlich begründeten Ortstag —
ein Verstoß gegen die bereits akzeptierte ADR-0044. Anders als S5a–S5c (Kommando-, Versand-,
Vorschau-/Anzeigepfade eines konkreten Trips oder Presets) gibt es an diesen Stellen **weder
Trip noch Preset**, aus dem sich eine Zone ergäbe: Der GPX-Import (`gpx_to_stage_data`) hat nur
die Koordinaten der hochgeladenen Datei, die beiden französischen Behördenquellen
(`massif_closure`, `meteo_forets`) fragen den Kalendertag des Herausgebers ab, und der
Staging-Debug-Auslöser (`api/routers/debug.py`) hat ein Henne-Ei-Problem — er braucht den Tag,
bevor er weiß, welches Segment aktiv ist. Diese Scheibe schließt alle sieben, indem sie an jeder
Stelle die bereits vorhandenen Bausteine (`tz_for_coords`, `trip_local_today`) auf die dort
bereits vorliegenden Koordinaten bzw. den Trip anwendet — keine neue Zonen-Auflösung. Zusätzlich
entfällt `compute_default_start_date` (zwei der sieben Funde) ersatzlos, weil sie repoweit
keinen Produktiv-Aufrufer hat. Nach dieser Scheibe ist die Muster-A-Liste des Zeitzonen-Wächters
(`tests/test_output_timezone_guard.py::KNOWN_VIOLATIONS`) leer.

## Source

- **File:** `src/services/gpx_processing.py`
  **Identifier:** `compute_default_start_date` (Zeile 180, Verstöße Zeile 189 und 193) — wird
  entfernt; `gpx_to_stage_data` (Zeile 197, Verstoß Zeile 223, API-Vertrag „do not break")
- **File:** `src/services/official_alerts/massif_closure.py`
  **Identifier:** `_get_cached_daily_json` → `_do_request` (Zeile 96–103, Verstoß Zeile 102),
  `MassifClosureSource.fetch` (Zeile 122, Verstoß Zeile 127 `last_run`)
- **File:** `src/services/official_alerts/meteo_forets.py`
  **Identifier:** `MeteoForetsSource.covers` (Zeile 128, Verstoß Zeile 130 Saison-Gate)
- **File:** `api/routers/debug.py`
  **Identifier:** `trigger_radar_alert` (Zeile 20, Verstoß Zeile 66 `date_type.today()`;
  Staging-only, `settings.env != "staging"` → 404, Zeile 51)
- **Zonen-Auflösung (unverändert nutzen):** `src/utils/timezone.py::tz_for_coords(lat, lon)`,
  `src/services/trip_day.py::trip_local_today(trip, now_utc)` (Zeile 90–96, über `anchor_tz`,
  Zeile 55–71)
- **Zeilennummern gemessen am Basis-HEAD `57e36375`** (2026-08-15) — direkt an den vier
  Produktivdateien nachgelesen, nicht aus dem Kontext-Dokument übernommen.

## Estimated Scope

- **LoC:** Produktivcode ~+34/−10 (Löschung von `compute_default_start_date` überwiegt die
  Ergänzungen an den übrigen drei Fundorten). Testcode geschätzt 150–300 Zeilen — wie in allen
  Vorscheiben der eigentliche Kostentreiber. Das LoC-Limit (250) reicht für den Produktivteil
  ohne Override; bei Testcode ggf. das separate Test-Budget (500) nutzen.
- **Files:** 4 Produktivdateien (MODIFY, eine davon mit einer Löschung), 1 Wächterdatei
  (`tests/test_output_timezone_guard.py`, MODIFY), 1 Strukturtestdatei
  (`tests/refactor/test_epic_129a_2_module_structure.py`, MODIFY), 2 mechanisch mitgezogene
  Bestandstestdateien (`tests/unit/test_gpx_import_in_trip_dialog.py`,
  `tests/tdd/test_warn_services_rest.py`, je MODIFY), plus mindestens eine neue,
  nicht-`live`-markierte Testdatei der Kern-Schicht (CREATE).
- **Effort:** medium — Risiko **MEDIUM**: `massif_closure` wirkt auf eine amtliche
  Zugangssperren-Warnung, die Official-Alerts-Registry verdeckt Signaturfehler still
  (`try/except Exception` um jeden `covers()`/`fetch()`-Aufruf).

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/gpx_processing.py` | MODIFY | `compute_default_start_date` entfällt; `gpx_to_stage_data` löst den Rückfalltag über die Zone des ersten Wegpunkts auf |
| `src/services/official_alerts/massif_closure.py` | MODIFY | `ymd` aus dem Herausgebertag; `last_run` explizit UTC; `_get_cached_daily_json` bekommt `ymd` als zweiten Parameter |
| `src/services/official_alerts/meteo_forets.py` | MODIFY | Saison-Monat aus der Ortszone statt dem Servermonat |
| `api/routers/debug.py` | MODIFY | `trip_local_today(trip, now_utc)` statt `date_type.today()` |
| `tests/test_output_timezone_guard.py` | MODIFY | sieben `KNOWN_VIOLATIONS`-Einträge entfallen (s. AC-7) |
| `tests/refactor/test_epic_129a_2_module_structure.py` | MODIFY | Zusicherung auf „Symbol existiert nicht mehr" gedreht (s. AC-2) |
| `tests/unit/test_gpx_import_in_trip_dialog.py` | MODIFY | zwei Tests der entfallenden Funktion entfernt bzw. angepasst |
| `tests/tdd/test_warn_services_rest.py` | MODIFY | `_get_cached_daily_json("83")`-Aufruf (Zeile 146) bekommt das zweite Argument `ymd` |
| `tests/tdd/test_<verhalten>.py` | CREATE | neue, nicht `live`-markierte Kern-Schicht-Testdatei für alle vier Fundorte, nach Verhalten benannt |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `utils.timezone.tz_for_coords(lat, lon)` | module function | Einziger Baustein, der ohne Trip/Preset auskommt — Zone aus reinen Koordinaten (AC-1, AC-3, AC-5) |
| `services.trip_day.trip_local_today(trip, now_utc)` | module function | Löst das Henne-Ei-Problem in `debug.py`: liefert den Kalendertag über die Zone der Etappe des Weltzeit-Tages, bevor Segmente bestimmt sind (AC-6) |
| ADR-0044 (Akzeptiert) | decision | Verlangt Ortstag statt Servertag; Restliste „S5d" (Zeile 194–202) nennt dieselben sieben Funde, die diese Scheibe schließt |
| ADR-0051 (Vorgeschlagen), Regel 2 + Regel 3 | decision | Regel 2 (Zone gehört an die Daten) begründet `tz_for_coords`/`trip_local_today` statt einer festen Herausgeber-Zone; Regel 3 (keine Umgebungsuhr) bleibt an F3–F7 unerfüllt (s. eigener Abschnitt unten) |
| `tests/test_output_timezone_guard.py::KNOWN_VIOLATIONS` | guard | Die sieben zugehörigen Einträge müssen im selben Commit entfallen, sonst bleibt der Fund gelistet und `test_no_unlisted_output_timezone_violations` markiert einen NEUEN unlisted Fund, falls die Zeile am Fundort verschwindet, ohne den Eintrag zu entfernen |
| `tests/refactor/test_epic_129a_2_module_structure.py::test_gpx_processing_module` | guard | Prüft heute per `hasattr` auf Anwesenheit von `compute_default_start_date` (Zeile 35) — dreht mit dieser Scheibe auf Abwesenheit (AC-2) |
| `tests/refactor/test_epic_129a_2_module_structure.py::test_gpx_to_stage_data_signature` | guard | Prüft `inspect.signature(gpx_to_stage_data)` auf exakt fünf Parameter (Zeile 55–68) — bleibt UNVERÄNDERT grün, weil kein Parameter hinzukommt (AC-8) |
| `OfficialAlertSource`-Protocol (`official_alerts/base.py:29-35`) | guard | Zwei Positionsargumente (`covers(lat, lon)`, `fetch(lat, lon)`); Registry ruft beide generisch in `try/except Exception` — eine Signaturerweiterung würde die Quelle still deaktivieren statt laut zu brechen (AC-8) |
| `tests/tdd/test_warn_services_rest.py:146` (`mod._get_cached_daily_json("83")`) | test caller | Einziger Test-Aufrufer der privaten Funktion, wird durch das neue `ymd`-Argument (AC-3) mitgezogen — kein Nachweis, reine Anpassung |
| `internal/router/router.go:154`, `handler.GpxProxyHandler`, `internal/handler/gpx_proxy_test.go` | consumer (Go) | Go-Proxy von `POST /api/gpx/parse` — Vertrag bleibt unverändert (fünf Parameter, `stage_date` optional), keine Go-Änderung nötig |
| `frontend/src/routes/gpx-upload/+page.svelte:50-54` | consumer (Frontend) | Einzige Stelle, an der der Rückfall aus AC-1 tatsächlich greift. **Nachgemessen (2026-08-15): nicht, weil die Seite kein Datum sendete — sondern weil sie es auf dem falschen Weg sendet.** `stage_date` und `start_hour` gehen als **FormData** in den Body (`:51`/`:52`), während `api/routers/gpx.py:26-27` beide als `Query(...)` deklariert; damit kommen sie nie an und die Eingabefelder der Seite sind wirkungslos. `TripNewEditor.svelte:254` macht es richtig (`?stage_date=…&start_hour=7` als Query). Eigenständiger Bestandsfehler, **nicht** von dieser Scheibe verursacht und nicht in ihrem Umfang — als eigenes Issue gebucht. Für AC-1 heißt es: der Rückfallpfad ist auf dieser Seite immer aktiv, nicht nur bei leerem Feld. |
| `docs/specs/modules/fix_1727_s5c_vorschau_anzeige_ortstag.md` | pattern | Unmittelbares Formatvorbild; Präzedenzfall für Löschung ohne Aufrufer (`dict_to_comparison_result`, dort F6) |
| `_anker(now_utc, zone, erwarteter_ortstag)` (`tests/tdd/conftest.py:88-109`) | test fixture | Geteilter Vorbedingungs-Anker — keine vierte Kopie |
| `KIRITIMATI`/`PAGO`-Konstanten (`tests/tdd/test_befehlspfade_folgen_ortszone.py:56-59`) | test fixture | Extremzonen (UTC+14/UTC−11) für den diskriminierenden GPX-Import-Test (AC-1) |

## Implementation Details

Vier Fundorte, drei Lösungsmuster — kein neuer Baustein, jede Auflösung nutzt bereits
vorliegende Argumente:

| Fundort | Lage | Vorgehen |
|---|---|---|
| `gpx_to_stage_data` | Koordinaten liegen in der GPX-Datei vor | Rückfalltag über `tz_for_coords` des ersten Wegpunkts |
| `compute_default_start_date` | kein Aufrufer | ersatzlos entfernen, Struktur-Test auf Abwesenheit drehen |
| `massif_closure` (`_do_request`, `fetch`) | Koordinaten als Funktionsargumente vorhanden | Tag des Herausgebers über `tz_for_coords(lat, lon)` in `fetch()`, an die private `_get_cached_daily_json` durchgereicht |
| `meteo_forets.covers` | Koordinaten als Funktionsargumente vorhanden | Saison-Monat über `tz_for_coords(lat, lon)` |
| `api/routers/debug.py` | Trip liegt bereits vor, Segmente noch nicht | `trip_local_today(trip, now_utc)` statt `date_type.today()` |

**AC-1 — `gpx_to_stage_data`, Rückfalltag aus dem ersten Wegpunkt:**
```python
d = stage_date
if d is None:
    track = process_gpx_upload(content, filename, upload_dir=upload_dir)
    if track.points:
        p = track.points[0]
        d = local_dt(datetime.now(timezone.utc), tz_for_coords(p.lat, p.lon)).date()
    else:
        d = datetime.now(timezone.utc).date()  # Fail-soft: keine Punkte, kein Ortsbezug
```
**Wichtig:** Der Fail-soft-Zweig darf NICHT auf `date.today()` zurückfallen — das bliebe ein
Muster-A-Fund und ließe AC-7 scheitern. Fehlender Ortsbezug heißt hier *explizit UTC*, nicht
*Umgebungsuhr*.
Bei nicht auflösbarer Zone fällt `tz_for_coords` selbst schon fail-soft auf UTC zurück
(bestehendes Verhalten des Bausteins) — kein zusätzlicher Sonderfall nötig. `process_gpx_upload`
wird bereits zwei Zeilen weiter unten für dieselbe `track`-Variable aufgerufen; die
Implementierung zieht diesen Aufruf lediglich vor, statt ihn zu duplizieren.

**AC-2 — `compute_default_start_date`, ersatzlose Löschung:**
Die Funktion (`gpx_processing.py:180-194`) entfällt vollständig. Der Struktur-Test
(`test_epic_129a_2_module_structure.py:35`) verliert den Eintrag aus `expected` (analog zu
`test_epic_129a_1_module_structure.py:46-49`, dort für `dict_to_comparison_result` in S5c
bereits gemacht) — oder bekommt eine explizite `assert not hasattr(...)`. Die alte Spec
`docs/specs/epic_129a_2_gpx_helpers.md` bleibt unangetastet, sie dokumentiert einen
abgeschlossenen historischen Zustand.

**AC-3/AC-4 — `massif_closure`, Tag des Herausgebers + explizites UTC für `last_run`:**
```python
def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
    hits = massifs_at(lat, lon)
    if not hits:
        return []
    ymd = local_dt(datetime.now(timezone.utc), tz_for_coords(lat, lon)).strftime("%Y%m%d")
    _STATUS["last_run"] = datetime.now(timezone.utc).isoformat()
    for hit in hits:
        data = _get_cached_daily_json(hit.src, ymd)
        ...
```
`_get_cached_daily_json(src, ymd)` bekommt `ymd` als zweiten Parameter; die verschachtelte
`_do_request()`-Closure bleibt parameterlos und liest `ymd` weiterhin aus dem umgebenden
Namensraum — kein neuer Mechanismus, nur eine Ebene höher aufgelöst.

**AC-5 — `meteo_forets.covers`, Saison-Monat der Ortszone:**
```python
def covers(self, lat: float, lon: float) -> bool:
    monat = local_dt(datetime.now(timezone.utc), tz_for_coords(lat, lon)).month
    if not _is_season(monat):
        return False
    return (_AROME_FR_LAT_MIN <= lat <= _AROME_FR_LAT_MAX
            and _AROME_FR_LON_MIN <= lon <= _AROME_FR_LON_MAX)
```

**AC-6 — `debug.py::trigger_radar_alert`, `trip_local_today` vor der Segmentwahl:**
```python
now_utc = datetime.now(timezone.utc)
today = trip_local_today(trip, now_utc)
segments = convert_trip_to_segments(trip, today)
```
Ersetzt `today = date_type.today()` (bisher Zeile 66) — `trip_local_today` löst das Henne-Ei
bereits selbst über `anchor_tz` (Zone der Etappe des Weltzeit-Tages), ohne dass zuvor ein
Segment feststehen muss.

## Nicht in dieser Scheibe

- **`src/providers/openmeteo.py:320` (`_load_availability_cache`) und `:344`
  (`probe_model_availability`, `probe_date`).** Der Ticketkörper und der Zuschnitt-Kommentar
  vom 2026-08-14 hatten diese zwei Stellen S5d zugeschlagen; **ADR-0044 ordnet sie ausdrücklich
  S5e zu** („die vom Wächter nicht gescannten Bereiche (S5e)"), die jüngere der beiden Quellen.
  Der Wächter scannt nur `src/output/**`, `src/services/**`, `api/**` und sieben explizit
  gelistete Dateien — `src/providers/` gehört zu keiner dieser Mengen. Zusätzlich ist dort
  **offen, ob überhaupt ein Ortstag-Fix richtig ist**: Beide Stellen haben keinerlei Ortsbezug
  (`probe_model_availability` iteriert feste Referenzkoordinaten je Modell,
  `_load_availability_cache` vergleicht nur eine TTL) — strukturell eher der
  `forecast_budget._today_utc`-Fall („bewusst UTC", ADR-0044 „Bewusst NICHT betroffen") als der
  `massif_closure`-Fall. S5e entscheidet, ob dort explizites UTC die Dauerlösung ist.
- **Die Go-Seite.** `POST /api/gpx/parse` ist über `handler.GpxProxyHandler`
  (`internal/router/router.go:154`) verdrahtet, bleibt aber ein reiner Proxy — der fachliche
  Rückfalltag entsteht ausschließlich im Python-Core (`gpx_to_stage_data`). Keine Go-Änderung.
- **Die `raw_astimezone`-Fundart des Wächters** (stille Mid-Body-Rückfälle, per
  `BoolOp`/`getattr`/`If`/`IfExp` erkannt) — eine dritte, von Muster A unabhängige Fundart, die
  diese Scheibe nicht berührt und nicht auszählt.

## Benannte Grenze — ADR-0051 Regel 3 bleibt unerfüllt

ADR-0051 Regel 3 verlangt: „Jetzt" kommt als Parameter vom Aufrufer, keine Umgebungsuhr im
Funktionsrumpf. An `gpx_to_stage_data`, `MassifClosureSource.fetch`/`_get_cached_daily_json`,
`MeteoForetsSource.covers` und dem `debug.py`-Endpunkt ist das ohne Vertragsbruch **nicht
erreichbar**:

- `gpx_to_stage_data` ist ein dokumentierter API-Vertrag mit exakt fünf Parametern
  (`test_epic_129a_2_module_structure.py:55-68`, per `inspect.signature` geprüft) — ein sechster
  Parameter würde AC-8 verletzen.
- `covers(lat, lon)`/`fetch(lat, lon)` sind ein `Protocol` mit exakt zwei Positionsargumenten
  (`official_alerts/base.py:29-35`); die Registry ruft beide generisch für sechs Quellen in
  `try/except Exception` — ein `TypeError` aus einer Signaturerweiterung würde die Quelle nicht
  laut brechen, sondern **still deaktivieren**.
- `debug.py::trigger_radar_alert` ist ein FastAPI-Endpunkt ohne von außen sinnvoll setzbaren
  Zeitparameter (Staging-only Debug-Route, kein API-Vertrag mit einem UI-Aufrufer, der `now_utc`
  mitgeben könnte).

`datetime.now(timezone.utc)` bleibt an diesen Stellen deshalb funktionsintern. Der Wächter ist
damit zufrieden — Muster A greift nur bei Umgebungsuhr-Zugriff **ohne** anschließende
Zonen-Anwendung, nicht bei `datetime.now(timezone.utc)` gefolgt von `tz_for_coords`/
`trip_local_today`. Erreicht werden ADR-0044 (Ortstag), ADR-0051 Regel 2 (Zone an den Daten) und
Muster-A-Freiheit — nicht erreicht wird Regel 3 selbst. Derselbe Rest blieb in #1795 für
`send_on_demand_report` bereits bewusst offen; diese Spec benennt ihn ausdrücklich, statt ihn
stillschweigend zu übergehen.

## Wirkung, am echten Endpunkt gemessen

Die Kontextphase hatte zunächst angenommen, ein falsches Datum an `massif_closure._do_request`
führe zu HTTP 404 und über den fail-soft-Pfad zu „keine Sperr-Warnung". **Am echten Endpunkt
gemessen (2026-08-15):**

| Abruf | Antwort |
|---|---|
| `…/83/import_data/20260815.json` (heute) | HTTP 200, md5 `675a8459…` |
| `…/83/import_data/20260814.json` (gestern) | HTTP 200, md5 `76c84d74…` |

Beide Tage antworten mit HTTP 200 und **unterschiedlichem Inhalt** — die Vortagsdatei existiert
und trägt andere Werte. Die tatsächliche Folge ist deshalb gravierender als angenommen: nicht
„404 → keine Warnung", sondern `cached_fetch` wertet den 200er als Erfolg, legt ihn für
`success_ttl` (1800 s) ab, und das System meldet **die Zugangssperren von gestern als die von
heute**. Eine über Nacht neu verhängte Sperre erscheint nicht — der Wanderer bekommt „Zugang
frei" für ein amtlich gesperrtes Massiv gemeldet.

Fenster: 22:00–00:00 UTC = 00:00–02:00 Pariser Sommerzeit, **täglich**, durch den 30-Minuten-Cache
faktisch bis ~02:30. Der Alarmpfad läuft im 30-Minuten-Takt rund um die Uhr ohne
Tagesfenster-Gate (`trip_alert.py:383-388`), das Fenster wird also real getroffen.

## Nachweisführung

Kern-Schicht, kein Netz — sämtliche vier Fundorte offline belegbar:

- **`massif_closure` (AC-3):** Der bestehende lokale HTTP-Sentinel aus
  `tests/tdd/test_warn_services_rest.py:65-93` (echter `http.server` auf `127.0.0.1`, kein Mock)
  ist als Nachweisort für AC-3 **nicht** verwendbar — die Datei trägt `pytestmark =
  pytest.mark.live` auf Modulebene (Dateikopf-Begründung: „lief im Kern nie gruen"), gehört
  damit vollständig zur Live-Schicht und läuft im Kern-Gate nicht mit. Zusätzlich zeichnet der
  vorhandene `_local_server` (Zeile 65-72) nur die Anzahl eingehender Requests auf, nicht den
  angefragten Pfad — AC-3 braucht aber genau den, um `ymd` zu prüfen. Der Nachweis gehört
  deshalb in eine **neue, nicht `live`-markierte** Testdatei der Kern-Schicht: Sie bildet das
  Sentinel-Muster (echter `http.server` auf `127.0.0.1`, kein Mock — erfüllt die Test-Politik)
  nach, erweitert es um das Aufzeichnen des angefragten Pfads, und richtet
  `massif_closure._ENDPOINT` per `monkeypatch` auf diesen lokalen Server. Zeitpunkt so wählen,
  dass UTC-Tag und Paris-Tag auseinanderfallen (z. B. `2026-06-01T21:45:00Z` → Paris bereits
  02.06.); Assertion auf den empfangenen Pfad (`…/20260602.json`, **nicht**
  `…/20260601.json`). Ein Server auf `127.0.0.1` ist mit dem Egress-Wächter des Projekts
  vereinbar (`--allow-hosts=127.0.0.1,::1`). Unverändert nötig, aber kein Nachweis:
  `tests/tdd/test_warn_services_rest.py:146` ruft `mod._get_cached_daily_json("83")` einarmig
  auf und muss wegen des neuen zweiten Parameters mitgezogen werden.
- **`meteo_forets` (AC-5):** rein rechnerisch, kein Netz. Saisongrenze nutzen:
  `2026-05-31T22:30:00Z` → Paris 01.06. (Saison, `covers` liefert `True` bei passenden
  Koordinaten), UTC 31.05. (keine Saison) — der diskriminierende Fall für einen Servertag-Bug.
- **`gpx_to_stage_data` (AC-1):** synthetische Mini-GPX mit einem Trackpunkt in einer
  Extremzone (Kiritimati +14 / Pago Pago −11, Konstanten aus
  `test_befehlspfade_folgen_ortszone.py:56-59`) — die vorhandenen Fixtures liegen in
  Mitteleuropa und sind für diesen Bug nicht diskriminierend.
- **`debug.py` (AC-6):** `now_utc` NICHT zusätzlich mocken, sondern echt aus `freeze_time`
  lesen — sonst fallen Parameterwert und Systemuhr zusammen und die Zusicherung ist
  unfalsifizierbar (Befund F001 aus S5a, in S5c zweimal wiederholt).

Jeder neue Testfall trägt den geteilten Vorbedingungs-Anker `_anker(now_utc, zone,
erwarteter_ortstag)` (`tests/tdd/conftest.py:88-109`) **vor** der Hauptzusicherung — er belegt
zuerst, dass Ortstag, Weltzeit-Tag und Servertag bei der gewählten Fixtur zu diesem Zeitpunkt
wirklich auseinanderfallen; ohne ihn wäre die Hauptzusicherung strukturell nie falsifizierbar
(#1726 F002). Testdateien werden nach Verhalten benannt, nicht nach Issue-Nummer — durchgesetzt
von `test_naming_gate.py`, kein `test_issue_1727*`-Name.

## Expected Behavior

| Was passiert | Bisher | Nach dieser Scheibe |
|---|---|---|
| GPX-Import ohne `stage_date`, Trackpunkt in UTC+14 | Etappe erhält den **Servertag** | Etappe erhält den **Ortstag des ersten Wegpunkts** |
| `massif_closure`-Abfrage kurz nach lokaler Mitternacht in Paris | Datei des **Vortags** abgefragt, 200er mit veralteten Sperren gecacht | Datei des **heutigen** Pariser Tages abgefragt |
| `meteo_forets`-Saison-Gate an der Saisongrenze | Umschaltet am **Servertag** | Umschaltet am **Pariser Tag** |
| Staging-Debug-Auslöser vor Segmentwahl | `today` vom **Servertag** | `today` von `trip_local_today(trip, now_utc)` |

Unverändert bleibt jeder GPX-Import **mit** explizitem `stage_date` — der Rückfall aus AC-1
greift ausschließlich, wenn `stage_date` fehlt.

## Acceptance Criteria

- **AC-1:** Given `POST /api/gpx/parse` wird OHNE `stage_date` aufgerufen, für eine GPX-Datei
  deren erster Wegpunkt in einer Zone mit deutlichem UTC-Offset liegt (z. B. Kiritimati UTC+14
  oder Pago Pago UTC−11), sodass Ortstag und Servertag zum Aufrufzeitpunkt auseinanderfallen /
  When `gpx_to_stage_data(content, filename, stage_date=None, ...)` den Rückfalltag bestimmt /
  Then ergibt sich das Etappendatum aus dem Ortstag der Zone des ERSTEN Wegpunkts der Datei
  (`tz_for_coords` auf dessen Koordinaten), NICHT aus `date.today()`. Bei leerer Punktliste oder
  von `tz_for_coords` nicht auflösbarer Zone greift der bestehende Fail-soft-Rückfall auf UTC,
  konsistent zum Fail-soft-Verhalten des Bausteins selbst.
  - Test: synthetische Mini-GPX mit einem Trackpunkt in einer Extremzone,
    Parameter-gegen-Systemuhr-Probe (`freeze_time(X)` gegen einen Zeitpunkt, dessen Ortstag am
    Trackpunkt von X abweicht), Vorbedingungs-Anker davor Pflicht.

- **AC-2:** Given `compute_default_start_date` (`src/services/gpx_processing.py`) hat repoweit
  über alle drei Stacks (`*.py`, `*.go`, `*.ts`, `*.svelte`) keinen Produktiv-Aufrufer, nur
  Tests und den eigenen Struktur-Test / When die Funktion ersatzlos entfernt wird / Then gelingt
  `import services.gpx_processing` weiterhin, `hasattr(mod, "compute_default_start_date")`
  liefert `False`, und `tests/refactor/test_epic_129a_2_module_structure.py` dreht seine
  Zusicherung auf „Symbol existiert nicht mehr" (Vorbild: `test_epic_129a_1_module_structure.py:
  46-49`, dort für `dict_to_comparison_result` in S5c identisch gemacht). Die alte Spec
  `docs/specs/epic_129a_2_gpx_helpers.md` bleibt als historisches Dokument unangetastet.
  - Test: `tests/refactor/test_epic_129a_2_module_structure.py::test_gpx_processing_module`
    angepasst; die beiden Tests der entfallenden Funktion in
    `tests/unit/test_gpx_import_in_trip_dialog.py` entfernt oder auf `ImportError`/Abwesenheit
    gedreht.

- **AC-3:** Given `MassifClosureSource.fetch(lat, lon)` (`massif_closure.py`) baut die
  Tages-Abfrage-URL `…/import_data/{ymd}.json` für die französische Präfektur-Quelle / When
  `fetch()` `ymd` über `tz_for_coords(lat, lon)` auflöst und als neuen Parameter an die private
  `_get_cached_daily_json(src, ymd)` durchreicht / Then folgt `{ymd}` dem Tag des HERAUSGEBERS
  (Pariser Zeit über die Koordinaten des Trips), NICHT dem Servertag, während die verschachtelte
  `_do_request`-Closure parameterlos bleibt und `ymd` weiterhin aus dem umgebenden Namensraum
  liest.
  - Test: neue, nicht `live`-markierte Kern-Schicht-Testdatei mit lokalem HTTP-Sentinel
    (`http.server` auf `127.0.0.1`, Pfad-Aufzeichnung, `monkeypatch` auf `_ENDPOINT`),
    Zeitpunkt an der Paris-Mitternacht (z. B. `2026-06-01T21:45:00Z`), Assertion auf den
    empfangenen `ymd`-Pfadteil. Vorbedingungs-Anker davor Pflicht.

- **AC-4:** Given `MassifClosureSource.fetch` schreibt einen `last_run`-Zeitstempel für das
  interne Monitoring (`_STATUS["last_run"]`) / When der Zeitstempel gebildet wird / Then
  geschieht das EXPLIZIT in UTC (`datetime.now(timezone.utc)`), nicht über naives
  `datetime.now()` — ein Zeitstempel der Vergangenheit gehört nach ADR-0051 Regel 1 in UTC. Kein
  Konsument im Repo liest diesen Wert derzeit; die Umstellung ist reine Ehrlichkeit des Werts,
  keine Verhaltensänderung für Aufrufer.
  - Test: Assertion, dass `_STATUS["last_run"]` nach `fetch()` einen tz-aware
    UTC-ISO-Zeitstempel enthält (`endswith("+00:00")` oder äquivalent), nicht auf einen
    zusätzlichen Konsumenten.

- **AC-5:** Given `MeteoForetsSource.covers(lat, lon)` prüft das Saison-Gate (Juni–September)
  der Météo-France-Quelle, bevor sie überhaupt einen `fetch()` versucht / When der Monat für das
  Gate bestimmt wird / Then geschieht das über den Monat der ORTSZONE der übergebenen
  Koordinaten (`tz_for_coords(lat, lon)`), NICHT über den Servermonat — an der Saisongrenze kann
  das den Unterschied zwischen „Quelle liefert" und „Quelle liefert nicht" ausmachen.
  - Test: Zeitpunkt an der Saisongrenze (`2026-05-31T22:30:00Z`, Paris bereits 01.06. = Saison,
    UTC noch 31.05. = keine Saison), Assertion auf `covers()` bei Koordinaten innerhalb der
    AROME-Frankreich-Box. Vorbedingungs-Anker davor Pflicht.

- **AC-6:** Given `api/routers/debug.py::trigger_radar_alert` (Staging-only,
  `settings.env != "staging"` → 404) braucht den Kalendertag `today`, BEVOR die aktiven
  Segmente bestimmt sind — ein Henne-Ei-Problem, weil die Zone eigentlich aus dem noch
  unbekannten aktiven Segment käme / When `today` bestimmt wird / Then geschieht das über
  `trip_local_today(trip, now_utc)` statt `date_type.today()` — der Baustein löst das Henne-Ei
  bereits selbst über `anchor_tz` (Zone der Etappe des Weltzeit-Tages), ohne dass zuvor ein
  Segment feststehen muss.
  - Test: `freeze_time` liefert die Systemuhr, `now_utc` wird NICHT zusätzlich gemockt, sondern
    echt aus `datetime.now(timezone.utc)` gelesen (sonst fallen Parameterwert und Systemuhr
    zusammen, Befund F001); Assertion auf das an `convert_trip_to_segments` übergebene Datum bei
    einem Trip mit deutlichem Zonen-Offset. Vorbedingungs-Anker davor Pflicht.

- **AC-7:** Given alle sieben Fundstellen dieser Scheibe (`api/routers/debug.py::
  trigger_radar_alert::0`, `gpx_processing.py::compute_default_start_date::0`/`::1`,
  `::gpx_to_stage_data::0`, `massif_closure.py::_do_request::0`, `::fetch::0`,
  `meteo_forets.py::covers::0`) sind umgesetzt / When
  `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` und
  `::test_no_unlisted_output_timezone_violations` laufen / Then sind alle sieben zugehörigen
  `KNOWN_VIOLATIONS`-Einträge entfernt, und beide Tests bleiben grün. Die Rubrik „Muster A"
  trägt danach KEINEN Eintrag mehr — die Liste, die mit S5a begonnen hat, ist geschlossen.
  - Test: `tests/test_output_timezone_guard.py::test_known_violations_only_shrink`,
    `::test_no_unlisted_output_timezone_violations`.

- **AC-8:** Given keine der vier umgestellten Funktionen darf ihren bestehenden API-Vertrag
  brechen — weder `gpx_to_stage_data` (dokumentierter API-Vertrag, konsumiert vom Go-Proxy
  `GpxProxyHandler`) noch `MassifClosureSource.fetch`/`MeteoForetsSource.covers`
  (`OfficialAlertSource`-Protocol, generisch von der Registry mit `try/except Exception`
  aufgerufen) / When die Implementierung dieser Scheibe abgeschlossen ist / Then behält
  `gpx_to_stage_data` exakt fünf Parameter (`content, filename, stage_date, start_hour,
  upload_dir`) und `MassifClosureSource.fetch`/`MeteoForetsSource.covers` behalten exakt zwei
  Positionsargumente (`lat, lon`) — die bestehenden Wächter dafür
  (`test_epic_129a_2_module_structure.py:55-68` und das `OfficialAlertSource`-Protocol) bleiben
  UNVERÄNDERT grün, ohne dass diese Scheibe sie anfasst.
  - Test: `tests/refactor/test_epic_129a_2_module_structure.py::test_gpx_to_stage_data_signature`
    läuft unverändert weiter grün. Für die beiden Fremdquellen braucht es einen EIGENEN
    `inspect.signature`-Test auf `MassifClosureSource.fetch` und `MeteoForetsSource.covers`
    (exakt `self, lat, lon`). **Der Registry-Aufruf taugt dafür ausdrücklich NICHT:**
    `base.py:137/148` stehen beide in `try/except Exception` (`:138-141`) — ein `TypeError` aus
    einer Signaturerweiterung würde dort geschluckt, geloggt und die Quelle still übersprungen.
    Ein Test, der sich darauf verlässt, bliebe grün, während die Quelle in Produktion
    abgeschaltet wäre: Prüfort ≠ Wirkort.

## Known Limitations

- **`src/providers/openmeteo.py:320`/`:344`** — vom Wächter nicht gescannt, laut ADR-0044 S5e
  zugeordnet; dort zusätzlich offen, ob ein Ortstag-Fix überhaupt richtig ist (s. „Nicht in
  dieser Scheibe").
- **ADR-0051 Regel 3 bleibt an allen vier Fundorten dieser Scheibe unerfüllt** — „Jetzt" bleibt
  funktionsintern statt als Parameter vom Aufrufer zu kommen (s. eigener Abschnitt oben). Der
  Wächter ist zufrieden, die Regel nicht; derselbe Rest steht seit #1795 für
  `send_on_demand_report` offen.
- **Die `raw_astimezone`-Fundart des Wächters** (stille Mid-Body-Rückfälle) wird von dieser
  Scheibe nicht ausgezählt und nicht berührt.
- **Der Wächter bleibt blind für `datetime.utcnow()`** — der Detektor wird von dieser Scheibe
  nicht erweitert. Für die vier betroffenen Dateien nachgemessen (2026-08-15, `grep -n utcnow`
  über alle vier): **keine Treffer**, die Blindstelle wirkt sich hier also nicht aus.
- **`massif_closure`s Erfolgs-Cache (`success_ttl` 1800s)** bleibt unverändert bestehen — diese
  Scheibe behebt das Datum der Abfrage, nicht die Cache-Dauer. Bei einer Sperr-Änderung
  unmittelbar nach dem letzten Cache-Refresh kann weiterhin bis zu 30 Minuten ein veralteter
  Stand gemeldet werden — bekanntes, unverändertes Verhalten des geteilten Egress-Kerns
  (`warn_egress`, Issue #1348).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0044 (Akzeptiert), ADR-0051 (Vorgeschlagen, Regel 1 + Regel 2 + Regel 3)
- **Rationale:** Setzt die bereits akzeptierte ADR-0044-Entscheidung an den letzten vier
  Muster-A-Fundorten außerhalb von Kommando-, Versand- und Vorschau-/Anzeigepfaden um (S5a–S5c)
  und entfernt eine Funktion (`compute_default_start_date`) als toten Code — keine offene
  Produktfrage, ein Bug gegen eine bereits getroffene Entscheidung. ADR-0051 Regel 1
  (Vergangenes ist ein Zeitpunkt, in UTC) begründet den `last_run`-Fix (AC-4); Regel 2 (Zone
  gehört an die Daten) begründet `tz_for_coords`/`trip_local_today` statt einer festen
  Herausgeber-Zone oder Servereinstellung; Regel 3 (keine Umgebungsuhr) bleibt an allen vier
  Fundorten bewusst unerfüllt, weil die betroffenen Signaturen (API-Vertrag, Protocol,
  Debug-Endpunkt ohne UI-Aufrufer) keinen zusätzlichen Parameter tragen dürfen — dokumentiert im
  eigenen Abschnitt „Benannte Grenze" statt stillschweigend übergangen.

## Changelog

- 2026-08-15: Spec erstellt nach Kontext-Dokument `docs/context/fix-1727-s5d-import-fremdquellen.md`
  (Basis-HEAD `57e36375`), Formatvorbild `docs/specs/modules/fix_1727_s5c_vorschau_anzeige_ortstag.md`.
- 2026-08-15: Drei Fehler in der Erstfassung korrigiert. (1) Der Fail-soft-Zweig im
  AC-1-Codebeispiel fiel auf `date.today()` zurück — das wäre ein fortbestehender Muster-A-Fund
  gewesen und hätte AC-7 unerfüllbar gemacht. (2) AC-8 verwies für die Fremdquellen auf den
  Registry-Aufruf als Nachweis, obwohl die Spec zwei Abschnitte höher selbst festhält, dass
  dieser Aufruf `TypeError` still schluckt — ersetzt durch einen eigenen `inspect.signature`-Test
  (Prüfort ≠ Wirkort). (3) Registry-Aufrufstellen liegen in `base.py:137/148`, nicht in
  `__init__.py`. Zusätzlich die `utcnow()`-Blindstelle für die vier Dateien nachgemessen
  (keine Treffer) statt sie als ungemessen zu führen.
- 2026-08-15: Nachweisstrategie für AC-3 korrigiert — der bestehende lokale HTTP-Sentinel aus
  `tests/tdd/test_warn_services_rest.py` trägt `pytestmark = pytest.mark.live` auf Modulebene
  und zeichnet den angefragten Pfad nicht auf; der Nachweis gehört stattdessen in eine neue,
  nicht `live`-markierte Kern-Schicht-Testdatei, die das Sentinel-Muster mit Pfad-Aufzeichnung
  nachbildet.

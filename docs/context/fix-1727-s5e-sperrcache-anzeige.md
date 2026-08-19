# Context: fix-1727-s5e-sperrcache-anzeige

Issue #1727, Scheibe S5e. Erstellt 2026-08-19, Session `replicated-cuddling-sphinx`.

## Request Summary

Zwei Reste aus dem Umgebungsuhr-Umbau (ADR-0051): Der Zugangssperren-Cache schlüsselt nicht nach
Kalendertag und kann deshalb Vortagesdaten als heutige ausliefern. Die Konto-Seite beschriftet einen
technischen Prüftakt als Versandtermin und formatiert ihn fest in Wiener Zeit.

## 🔴 Der Issue-Umfang von #1727 S5 ist abgearbeitet

**Am Ist-Code gemessen (2026-08-19), nicht aus dem Issue-Text übernommen.** Alle acht dort genannten
Fundstellen sind durch S5a–S5d behoben; die Zeilennummern sind verschoben, die Muster nirgends mehr
vorhanden:

| Fundstelle laut Issue | Ist-Stand |
|---|---|
| `preview_service.py:94` | behoben — `now_utc` Pflichtparameter, Fallback `trip_local_today(trip, now_utc)` |
| `compare_preview_service.py:250` | behoben — `_resolve_target_date(..., datetime.now(timezone.utc))` → `local_dt(...)` (`:152/275`) |
| `comparison_engine.py:407` | kein Fund mehr in der ganzen Datei |
| `api/routers/compare.py:55/58` | behoben — `first_resolvable_tz`+`local_dt` (`:49-63`) |
| `inbound_telegram_reader.py:358` | behoben — `_find_active_trip(self, now_utc: datetime, ...)` (`:359-360`) |
| `trip_command_processor.py:1076/1227` | behoben — Kommentar `:1186` erinnert nur an den Altzustand |
| `gpx_processing.py:183/189/193/223` | behoben — `compute_default_start_date` entfernt, `tz_for_coords` (`:214`) |
| `compare_html.py:1377` | behoben — Tag jetzt `local_dt(datetime.now(timezone.utc), tz).date()` (`:1450`) |

Auch das Titelversprechen „Ausnahmeliste auf null" ist nicht der Ist-Stand: `KNOWN_VIOLATIONS`
(`tests/test_output_timezone_guard.py:526-654`) hat **43 Einträge** — 2 dauerhaft, 18 mit abgesicherter
Aufrufseite, 21 dokumentierte UTC-Umrechnungen. Die **Muster-A-Rubrik** (Umgebungsuhr) ist leer; das war
das Ziel von S5a–S5d und ist erreicht.

## (A) Zugangssperren-Cache

### Was falsch ist

`src/services/official_alerts/massif_closure.py` — `_get_cached_daily_json(src, ymd)` (`:98-112`) bildet
den Cache-Schlüssel als `cache_key=src`. Der Kalendertag `ymd` fließt in die Request-URL
(`:106`, `_ENDPOINT.format(src=src, ymd=ymd)`), **nicht** in den Schlüssel. TTL 1800 s bei Erfolg
(`:39-40`, `warn_egress.WARN_SUCCESS_TTL`).

`fetch()` selbst berechnet `ymd` bereits korrekt über
`local_dt(datetime.now(timezone.utc), tz_for_coords(lat, lon))` (`:125-131`) — das ist der S5d-Fix und
funktioniert. Die Lücke liegt allein in der Schlüsselbildung.

**Wirkung:** Wechselt der Kalendertag innerhalb der 30-Minuten-Frist, liefert der Cache den
Vortages-Datensatz für dieselbe Quelle zurück, ohne dass am Schlüssel erkennbar wäre, dass er zu einem
anderen Tag gehört. Eine über Nacht neu verhängte Waldbrand-Zugangssperre erscheint bis zu 30 Minuten
lang nicht.

Aus dem S5d-Abschluss (nachgemessen 2026-08-15): Beide Tage liefern **HTTP 200 mit verschiedenem Inhalt**
(`…/20260815.json` md5 `675a8459…` vs. `…/20260814.json` md5 `76c84d74…`). Der Fehlerpfad ist also
nicht fail-soft — veraltete Daten werden als gültige Antwort behandelt.

### Die Lücke ist singulär — 9 Aufrufstellen ausgezählt

`cached_fetch()` (`src/services/official_alerts/warn_egress.py:377ff`) wird von 6 Diensten an 9 Stellen
benutzt. Für jede geprüft, ob ein Datum in die Ressource fließt, das nicht im Schlüssel steht:

| Aufrufer | `cache_key` | Lücke? |
|---|---|---|
| `massif_closure.py:109` | `src` | **JA — die einzige** |
| `dpc.py:165` | `"national"` | nein — statische URL; Frische nach dem Abruf über `_select_day_records()` (`:172-181`) geprüft |
| `vigilance.py:94` | `"national"` | nein — kein Datumsparameter (`:89-90`) |
| `meteo_forets.py:92` | `department` | nein — nur `id-departement` (`:79-88`) |
| `geosphere_warn.py:100` | `_round_coord(lat, lon)` | nein — nur `lat/lon/lang` (`:90-96`) |
| `meteoalarm_feed.py:212` | `country` | nein — statischer Feed-Pfad (`:207-208`) |
| `meteoalarm.py:768` | `f"{country}:{slot}:p{page}"` | nein — **trägt den Zeitanteil explizit** (`_slot_key(slot_end)`, `:665-687`) |
| `meteoalarm.py:963/980` | ID-basiert (Geometrie/CAP) | nein — nicht datumsgebunden |

**`meteoalarm.py:768` ist das hausinterne Vorbild:** dort ist der Zeitanteil bereits Teil des Schlüssels.
`dpc.py` löst dasselbe Problem anders — es prüft nach dem Abruf, zu welchem Tag der Datensatz gehört, und
dokumentiert das ausdrücklich (`:173-174`: „NIE blind 'today' als 'heute' interpretieren").

### Cache-Mechanik

- **Speicher:** Prozessspeicher, ein eigenes Modul-Dict je Dienst (`massif_closure.py:43` `_cache = {}`);
  `_store_entry()` (`warn_egress.py:165-177`) legt `{"data", "fetched_at", "ttl"}` ab. Kein Redis, keine
  Datei, nichts prozessübergreifend (`warn_egress.py:17-18`).
- **Schlüssel:** `cached_fetch(cache, cache_key, ...)` nimmt den Schlüssel als Parameter und baut nichts
  selbst zusammen — die Verantwortung liegt vollständig beim Aufrufer.
- **Zeitquelle:** `clock: Callable[[], float] = time.monotonic` (`:385`) — bewusst **nicht**
  wanduhrgebunden und damit **nicht** über `freeze_time` steuerbar. Das ist für den Test entscheidend.
- **Invalidierung:** keine. Ablauf ausschließlich über TTL-Vergleich beim nächsten Zugriff (`:431-434`).
  `_cache.clear()` existiert nur als Test-Hilfsmittel.

### Testlage

**Kein Test deckt den Fall ab.** Vorhanden:

- `tests/tdd/test_issue_1037_massif_closure.py` — 10 Methoden zu Niveau-Badges, Massiv-Überlappung,
  Fail-soft, Attribution. Kein Cache-Bezug.
- `tests/unit/test_massif_closure_capture_ambiguity.py` — 3 Methoden zur Herkunfts-Kennung (#1944).
- `tests/tdd/test_import_und_fremdquellen_folgen_ortstag.py::test_ac3_massif_closure_ymd_folgt_dem_pariser_tag`
  (`:181-208`) — prüft nur, dass die **URL** den Pariser Tag trägt.

🔴 Der Testhelfer dort (`:162-178`) leert den Cache **vor jedem Aufruf** mit dem Kommentar, dass
`cached_fetch` `time.monotonic` statt `freeze_time` nutzt (`:164-166`). Das Gerüst **umgeht** die
Tagesgrenzen-Frage aktiv, statt sie zu prüfen — genau deshalb ist der Fehler nie aufgefallen.

### Anspruch vs. Implementierung

`docs/specs/_archive/modules/issue_1037_official_alerts_massif_closure.md:97` nennt die Funktion wörtlich
`_load_cached_daily_json(hit.src)  # Tages-Cache pro Source-DEPT`. **Die Spec nennt es „Tages-Cache",
obwohl der Tag nie im Schlüssel stand.** Die geteilte Spec `docs/specs/modules/warn_service_consumption.md:174`
listet `cache_key (Land/Koordinate/Département/Source-DEPT)` — ein Datum ist dort für keinen Dienst
vorgesehen.

## (B) Konto-Anzeige

### Was falsch ist

`frontend/src/routes/account/+page.svelte:264-281` — `formatNextRun()` enthält **vier** feste
`timeZone: 'Europe/Vienna'`-Literale (`:269, :270, :271, :279`). Gerendert bei `:598-599` als
`Nächster: {formatNextRun(job.next_run)}`, Jobname aus `userJobs` (`:288-290`, nur
`trip_reports_hourly` → „Trip-Checks").

### Die Zahl bedeutet etwas anderes, als die Beschriftung sagt

`next_run` stammt aus `internal/scheduler/scheduler.go:772/781` (`e.Next.Format(time.RFC3339)`) — dem
`robfig/cron`-Eintrag des Jobs `trip_reports_hourly` mit Ausdruck `"0 * * * *"` (`:189`), berechnet in
`SchedulerTimezone` (`internal/config/config.go:20`, Vorgabe `Europe/Vienna`). Das ist der **generische
stündliche Poll-Tick**, nicht der Versandzeitpunkt eines Trips.

**Der tatsächliche Versand** entsteht in `src/services/trip_report_scheduler.py:180-189`:
`vor_ort = trip_local_now(trip, moment)` wird gegen `_slot_stunde(trip, report_type)` in einem
3-Stunden-Nachholfenster geprüft (`:96-106`); die Zone kommt aus dem ersten Wegpunkt über
`tz_for_coords(...)` (`:1279`).

### Die Eingabe-Kette ist stimmig — hier ist kein Fehler

Nutzer tippt eine nackte Uhrzeit (`VTSchedulePlan.svelte:101-113`, Label nur „Uhrzeit", keine Zone) →
naiv gespeichert (`VersandTab.svelte:149` `toHHMMSS`, `internal/model/trip.go:157` `MorningTime *string`,
`src/app/models.py:1076-1077` naives `datetime.time`, **kein Zonenfeld**) → korrekt als **Ortszeit des
Trip-Startpunkts** ausgewertet. Das ist ADR-0051 Regel 2 konform.

Die Naht liegt **allein in der Anzeige**.

### Frontend-Bestand

- **Es gibt keinen geteilten Formatierungs-Baustein.** Vorhanden sind unabhängige Einzellösungen:
  `compare/subscriptionHelpers.ts:54-58` (`formatNextSend`, rohe `Date`-Getter),
  `:61-70` (`formatLastSent`), `_home/TripKachel.svelte:11`, `+page.svelte:50/141/407`,
  `lib/utils/tripHero.ts:5` (bewusst eigene Monatsnamen-Map).
- **Alle anderen Zeitanzeigen laufen ohne `timeZone`-Angabe**, also implizit in der Ausführungszone
  (Browser). `account/+page.svelte` ist die **einzige** Stelle mit fest verdrahteter Zone.
- **`timeZoneName` kommt im gesamten Frontend null-mal vor** — ein Zonenkürzel wird heute nirgends
  angezeigt.
- **Keine Tests** berühren die Konto-Seite oder `formatNextRun` (weder `frontend/src/**/*.test.ts` noch
  `frontend/e2e/`).

### Konsumenten

Einziger Konsument des Endpunkts ist `frontend/src/routes/account/+page.server.ts:23`. Route registriert
in `internal/router/router.go:202`, in `internal/middleware/auth.go:34` als **öffentliche Route ohne
Cookie-Pflicht** geführt. Andere Health-Aggregate schreiben in denselben Endpunkt
(`briefing_health.go:63`, `tier_request_health.go:11`), betreffen aber andere Felder.

**Nicht messbar von hier:** ob externes Monitoring in `henemm-infra` (anderes Repo) `next_run` parst.
Als Lücke benannt, nicht geschätzt.

## Dependencies

- **Upstream (A):** `warn_egress.cached_fetch`, `tz_for_coords`, `local_dt`
- **Downstream (A):** die Warnquellen-Registry ruft `covers`/`fetch` in `try/except Exception`
  (`base.py:137-148`) — ein Fehler **deaktiviert die Quelle still**, statt laut zu brechen. Signatur darf
  nicht erweitert werden (Präzedenz aus S5d).
- **Upstream (B):** `/api/scheduler/status` → `data.scheduler.jobs[].next_run`
- **Downstream (B):** nur die Konto-Seite

## Risks & Considerations

1. **Stiller Ausfall der Warnquelle.** `try/except Exception` in der Registry — ein Fehler in
   `massif_closure` macht die Quelle wirkungslos, ohne dass ein Test rot wird. Der Nachweis muss die
   **Wirkung** prüfen (kommt die neue Sperre an?), nicht nur den Schlüsselaufbau.
2. **Testbarkeit gegen `time.monotonic`.** Der Cache ist bewusst nicht wanduhrgebunden. Ein Test für den
   Tageswechsel kann die Uhr nicht einfrieren — er muss über den `clock`-Parameter (`warn_egress.py:385`)
   oder über zwei Aufrufe mit verschiedenem `ymd` bei gleichem `src` arbeiten. Der bestehende Helfer, der
   den Cache vorher leert, ist als Muster **untauglich** — er würde die Lücke erneut verdecken.
3. **Unbegrenztes Wachstum des Schlüsselraums.** Kommt `ymd` in den Schlüssel, entsteht pro Quelle und
   Kalendertag ein Eintrag, der nie entfernt wird (keine Invalidierung, Ablauf nur beim Zugriff). Klein,
   aber real. In der Analyse zu entscheiden: beim Schreiben ältere Einträge derselben Quelle verwerfen,
   oder als vernachlässigbar dokumentieren. `meteoalarm.py:768` hat dasselbe Muster ohne Aufräumen.
4. **Zonenwechsel des Nutzers ist eine sichtbare Änderung.** Wer heute in Wien sitzt, sieht dieselbe Zahl
   wie bisher; wer anderswo sitzt, sieht eine andere. Das ist beabsichtigt, gehört aber in die
   Screenshot-Prüfung.
5. **Kein Vorbild für Zonenkürzel im Repo.** `timeZoneName` wird erstmalig eingeführt — die Darstellung
   muss zu den Design-Leitprinzipien passen (Lesbarkeit vor weicher Optik).
6. **Sperrzone #1929:** `src/services/official_alerts/official_alerts.py:1896-2104` gehört einer fremden
   Session. `massif_closure.py` ist nicht betroffen, aber die Nachbarschaft ist zu beachten.

## Existing Specs

- `docs/specs/_archive/modules/issue_1037_official_alerts_massif_closure.md` — archiviert; nennt den
  „Tages-Cache" (`:97`), der nie einer war
- `docs/specs/modules/warn_service_consumption.md:174` — geteiltes Cache-Design aller Warndienste
- `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` — Regel 3 (`:67-69`), Status **„Vorgeschlagen"**
  (in #1199 gebucht)
- `docs/adr/0044` — die vier in ADR-0044 ausgegrenzten Befehlspfade (durch S5c erledigt)

## Abgegrenzt — nicht in dieser Scheibe

- **#1969** (neu angelegt): die Konto-Seite soll den tatsächlichen nächsten Versandzeitpunkt je Trip in
  dessen Ortszeit zeigen. Größerer Umbau, PO-entschieden ausgelagert.
- Suchfläche des Wächters auf `src/providers/` + `src/app/loader.py` ausweiten (4 ortsbezugslose Treffer)
  → #1199
- Muster 3 des Wächters (`.hour`/`.date()` auf nicht zonenaufgelöstem Zeitstempel) — eigener Umfang
- Go-Seite (225 × `time.Now()`) — laut Issue ausdrücklich nicht Teil von S5

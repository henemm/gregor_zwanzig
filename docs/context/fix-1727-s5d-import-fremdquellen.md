# Context: fix-1727-s5d-import-fremdquellen

Issue #1727 (Epic #1722), Scheibe S5d. Basis `origin/main` `57e36375`.
Vorgänger: S5a (`dbad9614`), S5b (`b26d88a9`), S5c (`e50cd575`) — alle live.

## Request Summary

Die letzten Umgebungsuhr-Fundstellen (`date.today()` / `datetime.now()` ohne Zone) außerhalb
von Versand-, Befehls- und Vorschaupfaden auf einen begründeten Tag umstellen: GPX-Import,
zwei französische Behördenquellen, der Staging-Debug-Auslöser — und, je nach Zuschnitt-Entscheid,
der Verfügbarkeits-Cache von Open-Meteo. Danach ist die Muster-A-Liste des Zeitzonen-Wächters
leer.

## Restliste — selbst ausgezählt, nicht aus dem Ticket übernommen

`KNOWN_VIOLATIONS` in `tests/test_output_timezone_guard.py` auf `origin/main` `57e36375`:
**7 Muster-A-Einträge in 4 Dateien**. ADR-0044 (Zeile 194–202) nennt dieselben sieben.

| # | Schlüssel | Zeile | Was daran hängt |
|---|---|---|---|
| 1 | `api/routers/debug.py::trigger_radar_alert::0` | :66 | Debug-Auslöser Radar-Alarm |
| 2 | `gpx_processing.py::compute_default_start_date::0` | :189 | Vorgabestart bei leerer Etappenliste |
| 3 | `gpx_processing.py::compute_default_start_date::1` | :193 | zweiter Rückfall bei unlesbarem Datum |
| 4 | `gpx_processing.py::gpx_to_stage_data::0` | :223 | **Etappendatum beim Import** |
| 5 | `official_alerts/massif_closure.py::_do_request::0` | :100 | `{ymd}` in der Abfrage-URL |
| 6 | `official_alerts/massif_closure.py::fetch::0` | :125 | `last_run`-Zeitstempel |
| 7 | `official_alerts/meteo_forets.py::covers::0` | :130 | Saison-Gate Juni–September |

**Strittig — zwei weitere Stellen ohne Wächterdeckung:** `src/providers/openmeteo.py:320`
(`_load_availability_cache`, TTL-Vergleich) und `:344` (`probe_model_availability`,
`probe_date`). Der Ticketkörper und der Zuschnitt-Kommentar vom 2026-08-14 zählen sie zu S5d;
**ADR-0044 ordnet sie ausdrücklich S5e zu** („die vom Wächter nicht gescannten Bereiche (S5e)").
Die ADR ist die jüngere Quelle (mit S5c geschrieben). → Entscheid in der Analysephase.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `src/services/gpx_processing.py` | 3 Funde; `gpx_to_stage_data` ist API-Vertrag (Docstring „do not break") |
| `src/services/official_alerts/massif_closure.py` | 2 Funde; französische Präfektur-Tagesdatei |
| `src/services/official_alerts/meteo_forets.py` | 1 Fund; Saison-Gate der Météo-France-Quelle |
| `api/routers/debug.py` | 1 Fund; **Staging-only** (`if settings.env != "staging": 404`, :51) |
| `src/providers/openmeteo.py` | 2 Funde ohne Wächterdeckung (Zuordnung strittig) |
| `tests/test_output_timezone_guard.py` | der Wächter; `KNOWN_VIOLATIONS` :526–666, Schrumpf-Test :706 |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | Restliste :194–202, Ausnahmen :218–228 |
| `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` | Regel 2 (Zone an die Daten), Regel 3 (keine Umgebungsuhr) |

## Existing Patterns

**Bausteine (keine neuen bauen):**

| Funktion | Ort | Eingang |
|---|---|---|
| `trip_local_today(trip, now_utc)` | `services/trip_day.py:90` | Trip + Zeitpunkt |
| `first_resolvable_tz(locations)` | `utils/timezone.py` | Liste von Orten |
| `tz_for_coords(lat, lon)` | `utils/timezone.py` | **Koordinaten** — der einzige Baustein, der ohne Trip/Preset auskommt |
| `location_tz` / `resolve_location_tz` | `utils/timezone.py` | Location-Objekt |
| `local_dt(dt, tz)` / `local_hour` | `utils/timezone.py` | UTC-Zeitpunkt + Zone |

**Umsetzungsmuster aus S5a/S5b/S5c (wörtlich wiederkehrend):**

1. `now_utc: datetime` als **Pflichtparameter**, kein Default auf die Systemuhr
2. Zonenwahl über den zum Gegenstand passenden Baustein — nie eine zweite Auflösung bauen
3. `local_dt(now_utc, zone).date()` statt `date.today()`
4. Nachweis: `freeze_time(X)` gegen `now_utc=Y` plus Vorbedingungs-Anker `_anker()`

## Dependencies

**Aufrufer (Produktivcode):**

| Funktion | Produktiv-Aufrufer |
|---|---|
| `gpx_to_stage_data` | `api/routers/gpx.py:43` (POST `/api/gpx/parse`, `stage_date` **optional**), `gpx_processing.py:298` (`process_bulk_gpx_uploads`) |
| `compute_default_start_date` | **keiner** — repoweit nur Tests + ein Symbol-Existenz-Test |
| `MassifClosureSource.fetch` | Official-Alerts-Registry (`official_alerts/__init__.py`) |
| `MeteoForetsSource.covers` | dieselbe Registry, als Gate vor `fetch` |
| `trigger_radar_alert` | HTTP-Endpunkt, Staging-only |
| `probe_model_availability` | `src/app/cli.py:182`, `openmeteo.py:1157` |
| `_load_availability_cache` | `openmeteo.py:418`, `openmeteo.py:1153` |

**Drei-Stacks-Prüfung** (Lehre aus S5c, wo „kein Aufrufer" falsch war):
`/api/gpx/parse` ist im Go-Stack verdrahtet — `internal/router/router.go:154`,
`handler.GpxProxyHandler`, eigene Go-Tests in `internal/handler/gpx_proxy_test.go`.
Frontend ruft an **zwei** Stellen: `trip-new/TripNewEditor.svelte:254` **mit**
`stage_date`, `routes/gpx-upload/+page.svelte:54` **ohne** — nur dort greift der Rückfall.

## Risks & Considerations

### 1. Es gibt nicht *eine* richtige Antwort, sondern drei

Anders als in S5a–S5c gibt es hier **keinen Trip und kein Preset**, aus dem sich eine Zone
ergäbe. Die Stellen zerfallen in drei Klassen mit unterschiedlicher fachlicher Antwort:

- **Tag des Herausgebers** — `massif_closure._do_request` baut
  `…/{src}/import_data/{ymd}.json`; `meteo_forets.covers` prüft die Saison, die eine
  Eigenschaft *der Quelle* ist („nur in diesen Monaten liefert die Quelle Werte", Modul-Docstring).
  Maßgeblich ist der französische Kalendertag, nicht der des Wanderers. Beide Funktionen haben
  über `covers(lat, lon)` / `fetch(lat, lon)` Koordinaten — beide Wege (`tz_for_coords` oder
  feste Herausgeber-Zone) sind gangbar und bedeuten Verschiedenes.
- **Tag des Nutzers bzw. der Route** — `gpx_to_stage_data`. Koordinaten liegen in der
  GPX-Datei vor.
- **Zählwerk ohne Nutzerdatum** — `openmeteo`-Cache, Präzedenzfall `forecast_budget._today_utc`
  (ADR-0044 „Bewusst NICHT betroffen"). Hier wäre das Ziel *explizites* UTC, nicht Ortstag.

### 2. Der Server läuft auf `Etc/UTC` — gemessen, nicht angenommen

`timedatectl`: `Time zone: Etc/UTC`. Damit ist naives `datetime.now()` deckungsgleich mit UTC
und `date.today()` der UTC-Tag. Die Fehlerfenster sind dadurch exakt bezifferbar:

| Stelle | Fenster | Folge |
|---|---|---|
| `massif_closure._do_request` | 00:00–02:00 Paris-Sommerzeit, **täglich** | Vortagsdatei abgefragt; 404 → fail-soft `[]` → **keine Sperr-Warnung** |
| `meteo_forets.covers` | 00:00–02:00 Paris an **2 Tagen/Jahr** (1.6./1.10.) | Quelle einen Tag zu spät an- bzw. zu spät abgeschaltet |
| `gpx_to_stage_data` | für UTC+12 **bis zu 12 h täglich** | Etappe bekommt einen Tag zu früh |
| `debug.py` | Staging-only | keine Produktivwirkung |

Die massif-Zeile ist damit **nicht** folgenlos — sie kann eine amtliche Zugangssperre
verschlucken. Im Epic waren Wirkungsaussagen des Tickets bereits dreimal veraltet; diese hier
ist am Code gemessen.

### 3. `compute_default_start_date` hat keinen Produktiv-Aufrufer

Repoweit über alle drei Stacks gesucht (`*.py`, `*.go`, `*.ts`, `*.svelte`, `*.md`, `*.conf`):
Treffer nur in `tests/`, `docs/` und der eigenen Definition. Der Docstring behauptet
„Used by the Multi-Upload-UI to pre-fill the date picker" — im Frontend gibt es dazu nichts.
S5c hat einen solchen Fall (`dict_to_comparison_result`) **ersatzlos entfernt**. Hier hängen
aber `tests/refactor/test_epic_129a_2_module_structure.py:35` und
`docs/specs/epic_129a_2_gpx_helpers.md` AC-2 am bloßen Vorhandensein des Symbols. Entfernen
heißt: beide mitziehen. → Entscheid in der Analysephase.

### 4. Der Zeitzonen-Wächter kennt keinen Zeilen-Ausnahme-Mechanismus

Der Zuschnitt sieht vor, bewusst-UTC-Stellen mit `# gz-main-path:` zu begründen statt sie in
der Liste zu lassen. **Gemessen:** Dieses Kommentar-Muster wird ausschließlich von
`tests/tdd/test_repo_path_hardcoding_ratchet.py` (und einigen Fidelity-Gates) gelesen — vom
Zeitzonen-Wächter **nicht**. Die S5c-Ausnahme in `tools/weather_validation.py:288` ist
folgerichtig reine Menschen-Dokumentation: `tools/` steht in keiner Scanfläche. Wer eine
gescannte Stelle als „bewusst so" markieren will, braucht dafür erst einen Mechanismus —
sonst bleibt nur `KNOWN_VIOLATIONS`, also genau die Vermischung, die das Ticket beenden will.

### 5. Nachweishürde: die vorhandenen Tests der Fremdquellen brauchen Netz

`tests/tdd/test_issue_1037_massif_closure.py` und `test_issue_1036_meteo_forets_source.py`
sind `@pytest.mark.live` und rufen die echten Endpunkte. Der Nachweis für diese Scheibe muss in
der **Kern-Schicht** liegen (ohne Netz). Vorlagen für Mehrzonen-Fixturen stehen:
`tests/tdd/conftest.py:56–76` (`trip_two_zones`, NZ + Korsika), die Drei-Zonen-Konstanten in
`tests/tdd/test_befehlspfade_folgen_ortszone.py:56–73` (Pago Pago −11 / Kiritimati +14) und der
Vorbedingungs-Anker `_anker()` (`tests/tdd/conftest.py:88–109`), der zuerst misst, dass Ortstag,
Weltzeit-Tag und Servertag bei der Fixtur wirklich auseinanderfallen.

### 6. `freeze_time` macht die Zusicherung unfalsifizierbar

Befund F001 aus S5a, in S5c zweimal wiederholt: `freeze_time` patcht `datetime.now()` global,
wodurch Parameterwert und Systemuhr im Test identisch werden. Jeder Test setzt deshalb
`freeze_time(X)` gegen `now_utc=Y`. Für die Zonen-Auflösung gilt zusätzlich die S5c-Lehre:
**DI-Spion direkt auf die Auflösung statt Ergebnis-Umweg** — ein Ergebnis-Umweg ist nur so
scharf wie die zufällige Lage der Fixtur-Daten.

## Analysis

### Type

Bug — die Kalendertag-Bestimmung folgt an sieben Stellen der Serveruhr statt dem fachlich
zuständigen Tag.

### Vier Entscheide, davon zwei gegen meine eigene Vorab-Position

**E1 — `providers/openmeteo.py` bleibt draußen (S5e).** Der Wächter scannt nur `src/output/**`,
`src/services/**`, `api/**` und sieben explizit gelistete Dateien (`test_output_timezone_guard.py:101–118`);
`src/providers/` ist in keiner der vier Mengen. ADR-0044 ordnet die ungescannten Bereiche
ausdrücklich S5e zu und ist die jüngste der drei Quellen. **Offene Frage für S5e, hier benannt
statt verdeckt:** Beide Stellen haben überhaupt keinen Ortsbezug — `probe_model_availability`
iteriert feste Referenzkoordinaten je Modell, `_load_availability_cache` vergleicht nur eine
TTL. Das ist strukturell der `forecast_budget._today_utc`-Fall („bewusst UTC", ADR-0044), nicht
der `massif_closure`-Fall. S5e entscheidet, ob dort explizites UTC die Dauerlösung ist.

**E2 — `compute_default_start_date` wird ersatzlos entfernt, nicht repariert.** Meine
Vorab-Position („fixen, weil Entfernen in eine fremde abgeschlossene Spec eingreift") ist
widerlegt: Der Präzedenzfall aus S5c ist nachgemessen — `test_epic_129a_1_module_structure.py:46–49`
dreht für `dict_to_comparison_result` schlicht die Zusicherung auf `assert not hasattr(...)`,
die alte Spec `epic_129a_1_compare_helpers.md` blieb **unangetastet**. Es kostet eine Testzeile,
nicht „beide mitziehen". Dazu: `docs/specs/epic_129a_2_gpx_helpers.md` trägt `status: draft` mit
**unangehaktem** `- [ ] Approved`, und der Docstring der Funktion verweist auf die
Multi-Upload-UI in `src/web/pages/` — die es seit dem SvelteKit-Rework (#355) nicht mehr gibt.
Ortstag-Logik in eine Funktion ohne Aufrufer zu bauen, verlängert nur die Lebensdauer eines
irreführenden Docstrings.

**E3 — Die Zone der Fremdquellen kommt aus `tz_for_coords(lat, lon)`, nicht aus einer festen
Konstante.** Eine `ZoneInfo("Europe/Paris")` wäre selbst ein Muster-B-Fund
(`test_output_timezone_guard.py:395–401` greift bei **jedem** Nicht-UTC-Literal in jeder
Ausdrucksform) und erzeugte einen neuen Wächter-Eintrag — genau das, was die Scheibe beendet.
Fachlich fallen Herausgeber- und Wanderertag hier ohnehin zusammen: die Massiv-Polygone decken
nur Var, Bouches-du-Rhône und Korsika (`massif_zones.py:9–10`), `meteo_forets.covers` zusätzlich
nur die AROME-Frankreich-Box (`radar_service.py:42–45`). Gemessen: `tz_for_coords(43.2, 6.1)`
und `tz_for_coords(42.15, 9.1)` liefern beide `Europe/Paris`; Kosten nach dem einmaligen
Laden des Singletons 0,1 ms.

**E4 — Keine einzige Signatur wird erweitert.** Zwei harte, bereits bestehende Sperren, beide
selbst nachgemessen:

- `test_epic_129a_2_module_structure.py:55–68` prüft `gpx_to_stage_data` per `inspect.signature`
  auf **exakt fünf** Parameter (`assert len(params) == len(expected_params)`).
- `OfficialAlertSource` ist ein `Protocol` mit genau zwei Positionsargumenten
  (`base.py:29–35`); die Registry ruft `source.covers(lat, lon)` / `source.fetch(lat, lon)`
  (`:137`, `:148`) generisch für sechs Quellen. **Verschärfend:** beide Aufrufe stehen in
  `try/except Exception` (`:138–141`) — ein `TypeError` aus einer Signaturerweiterung würde die
  Quelle nicht laut brechen, sondern **still deaktivieren**.

Die Zone wird deshalb überall lokal aus bereits vorhandenen Argumenten aufgelöst. Nur die
private `_get_cached_daily_json(src)` bekommt einen zweiten Parameter (`ymd`) — sie hat genau
einen Produktiv-Aufrufer und einen Test-Aufrufer (`test_warn_services_rest.py:146`).

### Benannte Grenze: ADR-0051 Regel 3 bleibt hier unerfüllt

Regel 3 verlangt, dass „Jetzt" als Parameter vom Aufrufer kommt. An den Protocol- und
AC-3-gebundenen Stellen ist das ohne Vertragsbruch **nicht erreichbar**; dort bleibt
`datetime.now(timezone.utc)` funktionsintern. Der Wächter ist damit zufrieden (Muster A greift
nur ohne Zonenargument, `:387–393`), die Regel nicht. Erreicht werden ADR-0044 (Ortstag),
ADR-0051 Regel 2 (Zone an den Daten) und Muster-A-Freiheit. Das ist derselbe Rest, den #1795
für `send_on_demand_report` bereits ausdrücklich offengelassen hat — er gehört zitierbar in die
Spec, nicht stillschweigend übergangen.

### Wirkung — vierte veraltete Aussage dieses Epics, diesmal meine eigene

Ich hatte in der Kontextphase geschrieben, `massif_closure` liefe bei falschem Datum in einen
404 und über den fail-soft-Pfad in „keine Sperr-Warnung". **Am echten Endpunkt gemessen
(2026-08-15):**

| Abruf | Antwort |
|---|---|
| `…/83/import_data/20260815.json` (heute) | **HTTP 200**, md5 `675a8459…` |
| `…/83/import_data/20260814.json` (gestern) | **HTTP 200**, md5 `76c84d74…` |

Die Vortagsdatei existiert und trägt **andere Werte**. Die Kette lautet also nicht
„404 → keine Warnung", sondern: `cached_fetch` wertet den 200er als Erfolg, legt ihn mit
`success_ttl` (1800 s) ab, und das System meldet **die Zugangssperren von gestern als die von
heute**. Eine über Nacht neu verhängte Sperre erscheint nicht — der Wanderer bekommt „Zugang
frei" für ein gesperrtes Massiv. Das ist gravierender als die fail-soft-Variante, nicht milder.

Fenster: 22:00–00:00 UTC (= 00:00–02:00 Pariser Sommerzeit) **täglich**, durch den 30-Minuten-Cache
faktisch bis ~02:30. Der Pfad läuft im 30-Minuten-Takt rund um die Uhr ohne Tagesfenster-Gate
(`trip_alert.py:383–388`, `:1362–1384`), das Fenster wird also real getroffen.

### Affected Files

| Datei | Änderung | Beschreibung |
|------|-------------|-------------|
| `src/services/gpx_processing.py` | MODIFY | `compute_default_start_date` entfällt; `gpx_to_stage_data` löst den Rückfalltag über die Zone des ersten Wegpunkts auf |
| `src/services/official_alerts/massif_closure.py` | MODIFY | `ymd` aus dem Herausgebertag; `last_run` explizit UTC; `_get_cached_daily_json` bekommt `ymd` |
| `src/services/official_alerts/meteo_forets.py` | MODIFY | Saison-Monat aus der Ortszone |
| `api/routers/debug.py` | MODIFY | `trip_local_today(trip, now_utc)` statt `date.today()` |
| `tests/test_output_timezone_guard.py` | MODIFY | sieben `KNOWN_VIOLATIONS`-Einträge entfallen |
| `tests/refactor/test_epic_129a_2_module_structure.py` | MODIFY | Zusicherung auf „Symbol existiert nicht mehr" drehen |
| `tests/unit/test_gpx_import_in_trip_dialog.py` | MODIFY | zwei Tests der entfallenden Funktion |
| `tests/tdd/test_warn_services_rest.py` | MODIFY | ein Aufrufer bekommt das zweite Argument |
| neue Testdatei | CREATE | Nachweis nach Verhalten benannt, nicht nach Issue-Nummer |

### Scope Assessment

- Produktivdateien: 4 · geschätzt **+34/−10** (Vergleich: S5a +74/−20, S5b +188/−40, S5c +76/−86)
- Testcode: geschätzt 150–300 Zeilen — der eigentliche Kostentreiber, wie in allen Vorscheiben
- Risiko: **MEDIUM** — zwei der Stellen wirken auf amtliche Warnungen; die Registry verdeckt
  Signaturfehler still
- Ein Workflow, kein Split nötig (Budget 250/500 komfortabel eingehalten)

### Nachweisstrategie (ohne Netz)

Die vorhandenen Tests beider Fremdquellen sind `@pytest.mark.live`. Der Nachweis dieser Scheibe
liegt in der Kern-Schicht:

- **`massif_closure`:** der lokale HTTP-Sentinel aus `test_warn_services_rest.py:34+` ist echt
  (kein Mock) und bereits vorhanden — er bekommt eine Zusicherung auf den **empfangenen**
  `ymd`-Pfadteil, den heute kein Test prüft. Zeitpunkt so wählen, dass UTC-Tag und Paris-Tag
  auseinanderfallen (z. B. `2026-06-01T21:45:00Z` → Paris bereits 02.06.).
- **`meteo_forets`:** rein rechnerisch, kein Netz. Saisongrenze nutzen: `2026-05-31T22:30:00Z`
  → Paris 01.06. (Saison), UTC 31.05. (keine Saison).
- **`gpx_to_stage_data`:** synthetische Mini-GPX mit einem Trackpunkt in einer Extremzone
  (Kiritimati +14 / Pago Pago −11, Konstanten aus `test_befehlspfade_folgen_ortszone.py:56–73`).
  Die vorhandenen Fixtures liegen in Mitteleuropa und sind nicht diskriminierend.
- **`debug.py`:** `now_utc` NICHT zusätzlich mocken, sondern echt aus `freeze_time` lesen —
  sonst fallen Parameter und Systemuhr zusammen (Befund F001 aus S5a).

Jeder Test trägt den Vorbedingungs-Anker (`conftest.py:88–109`), der zuerst misst, dass Ortstag,
Weltzeit-Tag und Servertag bei dieser Fixtur wirklich auseinanderfallen.

### Open Questions

- [ ] Keine offenen Fragen für diese Scheibe. Die Zuordnung der `openmeteo`-Stellen ist auf S5e
      vertagt und dort als offene fachliche Frage („Ortstag oder bewusst UTC?") notiert.

## Existing Specs

- `docs/specs/modules/fix_1727_s5c_vorschau_anzeige_ortstag.md` — unmittelbares Vorbild (8 ACs)
- `docs/specs/epic_129a_2_gpx_helpers.md` — AC-2 verlangt das Symbol `compute_default_start_date`
- `docs/specs/modules/issue_1036_meteo_forets_source.md`, `issue_1037_official_alerts_massif_closure.md`
- `docs/context/fix-1697-ortstag-statt-servertag.md` — vollständige Fundstellen-Karte des Epics

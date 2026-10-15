# RED-Vertrag: feat-1441-s1-lawinenlagebericht (Phase 5, TDD RED)

Dieser Vertrag legt die Namen/Signaturen fest, die die Tests importieren. /50 implementiert GENAU
diese Schnittstellen. Wo die Spec offen war, steht unten **ENTSCHEIDUNG** (mit Begruendung); die
mit **OFFEN-PO** markierten Punkte soll der Orchestrator vor/in /50 bestaetigen.

Testdateien (alle unter `tests/`, lesen Fixtures relativ zur eigenen Datei):
`test_avalanche_report_{source,parser,states,coverage,region_mapper,dedup,escalation,channels,sms,stufen_darstellung,docs}.py`
(`stufen_darstellung` = nur bestehende Felder/Renderer -> scheitert im RED an Assertions, nicht an Importen),
dazu `tests/helpers/avalanche_report_support.py` (geteilte Hilfen, Fixture-Transport, Uhr),
`tests/tdd/test_alert_urgency.py` (Ergaenzung), `tests/tdd/test_hazard_symbols.py` und
`tests/tdd/test_sms_official_alert_tokens.py` (angepasst, siehe "Bestandstests").

## 1. Modul `services/official_alerts/avalanche_report.py` (neu)

```python
SERVICE_NAME = "avalanche_report"          # Call-Log-service (warn_egress) UND AvalancheReportSource.name
SOURCE_PREFIX = "avalanche_report"         # OfficialAlert.source == f"{SOURCE_PREFIX}:{config.key}", z. B. "avalanche_report:AT-07"
DEFAULT_URL_PATTERN = "https://static.avalanche.report/bulletins/latest/{X}_de_CAAMLv6.json"

@dataclass(frozen=True)
class AvalancheRegionConfig:
    key: str                 # "AT-07"; fuellt {X} im URL-Muster UND ist Praefix der Mikroregions-IDs ("AT-07-28")
    url_pattern: str         # enthaelt "{X}"; Host steht darin (Tests setzen ihn nicht um -- der Transport faengt ab)
    regions_file: Path       # GeoJSON-FeatureCollection, Feature.properties.id == regionID
    display_name: str        # "Lawinenwarndienst Tirol"

AVALANCHE_REGION_TABLE: tuple[AvalancheRegionConfig, ...]   # genau 4 Eintraege: AT-07, IT-32-BZ, IT-32-TN, AT-02
#   display_name: "Lawinenwarndienst Tirol" / "... Suedtirol" (mit Umlaut: "Südtirol") / "... Trentino" / "... Kärnten"
#   regions_file: <package>/data/avalanche_regions_{key}.geojson.json  (byte-identisch zu tests/fixtures/avalanche_report/regions/{key}_micro-regions.geojson.json)

class AvalancheReportSource:
    def __init__(self, table: Sequence[AvalancheRegionConfig] = AVALANCHE_REGION_TABLE, *,
                 transport: httpx.BaseTransport | None = None,   # Test-Naht; None = echter Transport
                 clock: Callable[[], float] = time.monotonic,     # geht 1:1 als cached_fetch(clock=...)
                 now_fn: Callable[[], datetime] | None = None,    # aware datetime fuer Gueltigkeit; None = datetime.now(UTC)
                 cache: dict | None = None) -> None               # None = eigener leerer dict je Instanz
    @property
    def name(self) -> str                       # == SERVICE_NAME
    def covers(self, lat, lon) -> bool          # nur Bounding-Boxen der Tabellenzeilen (aus den Regionsdateien abgeleitet), KEIN Netz
    def fetch(self, lat, lon) -> list[OfficialAlert]

def parse_region_alert(doc: dict, region_id: str, *, source: str = SOURCE_PREFIX) -> OfficialAlert | None
    # Reiner Parser, KEINE Gueltigkeitspruefung. None, wenn region_id in keinem Bulletin steht.
```

**Ablauf `fetch(lat, lon)`** (Pflichtverhalten, von den Tests geprueft):
1. Jede Tabellenzeile fragt ihren `RegionMapper` (eine Datei je Zeile): welche Mikroregionen enthaelt der Punkt? Nur Zeilen mit
   Treffer werden abgerufen (**kein Abruf je Bounding-Box-Treffer**: AT-07 und AT-02 ueberlappen in der Bounding-Box ab lon 12.656;
   ein Punkt in AT-07-28 darf NUR die AT-07-Datei laden).
2. Abruf pro Zeile ueber `warn_egress.cached_fetch(cache=self._cache, cache_key=key, service=SERVICE_NAME, host=<Host der URL>,
   request_fn=..., parse_fn=..., clock=self._clock, ...)`. `request_fn` nutzt `httpx.Client(transport=self._transport,
   follow_redirects=True, timeout=...)` -- **Redirects MUESSEN gefolgt werden** (static.avalanche.report liefert 301 -> avalanche.report;
   `httpx.get` allein folgt nicht).
3. Gueltigkeit: Bulletin gilt, solange `validTime.endTime >= now_fn()` (Gleichheit = noch gueltig); danach "kein aktueller Bericht".
4. Pro getroffener Mikroregion `parse_region_alert`; **mehrere Treffer** (Grenzpunkt) -> hoechste `native_level`,
   Gleichstand -> kleinste Regions-ID (String-Vergleich); es wird GENAU EIN Alert je Punkt zurueckgegeben (auch ueber Tabellenzeilen hinweg).
5. Wirft nie; Fehler -> `[]` plus `cached_fetch`-Fehlermarker (-> `unavailable`).

**Drei Zustaende (AC-4/5/6), ENTSCHEIDUNG:**
- 404 und abgelaufenes Bulletin (HTTP 200) -> `[]`, KEIN `unavailable`. Netzfehler/5xx -> `[]` + `unavailable=True` (60-s-Fehler-TTL wie ueblich).
- **Aenderung in `warn_egress.cached_fetch`** (additiv, Default = Bestand bit-identisch):
  neuer Keyword-Parameter `not_covered_ttl: float = WARN_NOT_COVERED_TTL`. Die Quelle ruft mit
  `not_covered_statuses=frozenset({404})` und `not_covered_ttl=WARN_SUCCESS_TTL` (1800 s). Das neutrale Ergebnis `{}` bedeutet "kein Bericht".
  (404 darf nicht die 24-h-TTL bekommen; Mutation `not_covered_ttl=86400` wird von `test_avalanche_report_states.py` rot.)
- Abgelaufenes 200-Bulletin wird mit `success_ttl=WARN_SUCCESS_TTL` (1800 s) gecacht; die Gueltigkeit wird bei JEDEM `fetch` neu gegen `now_fn()` geprueft.

**Egress-Hosts / IsolationKind, ENTSCHEIDUNG (revidiert nach Review): `BLOCKED`** fuer `static.avalanche.report` und `avalanche.report`
(`src/app/egress_guard.py` UND `Blocked` in `internal/egress/inventory.go`), wie alle uebrigen Warn-Hosts (#1348 Scheibe 2b).
Begruendung: (1) der Kern ist netzfrei -- bei `TEST_ACCESS` wuerde jeder Kerntest, der eine In-Region-Koordinate (Osttirol, Kaernten, Innsbruck, Bozen,
Karnischer Hoehenweg) durch die echte Registry schickt, real bei avalanche.report anfragen; (2) ein ERFOLGREICHER zusaetzlicher Warn-Dienst veraendert
die `unavailable`-Bilanz bestehender Tests (kompensiert geblockte GeoSphere-/MeteoAlarm-Quellen), ein FEHLSCHLAGENDER laesst sie unveraendert.
Test: `test_ac20_standardquelle_macht_im_kern_keinen_echten_abruf_...` (echte Standardquelle -> gesperrt -> `unavailable=True`).
**OFFEN fuer /70 (Orchestrator):** auf Staging ist der Host damit ebenfalls gesperrt -> ein Tirol-Punkt zeigt dort "nicht abrufbar", nicht "sauber leer".
Der geplante Staging-Nachweis "sauber leer" muss denselben Mechanismus nutzen wie der #1430-/MeteoAlarm-Nachweis fuer geblockte Warn-Feeds
(Fixture-/Aufzeichnungsweg oder Freigabe in der Staging-Konfiguration) -- das ist keine RED-Frage.
Weder `lawinen-warnung.eu` noch ein EU-Sammelfeed-Host im Inventar.

## 2. Parser-Vertrag `parse_region_alert`

Eingabe = geparstes CAAML-v6-JSON (`{"bulletins":[...]}`), `region_id` = Mikroregions-ID. Ergebnis `OfficialAlert`:

| Feld | Wert |
|---|---|
| `source` | `f"avalanche_report:{key}"` (Parameter `source`) |
| `hazard` | `"avalanche_bulletin"` |
| `native_level` | 1..5 (`low`..`very_high`) = **hoechste** `mainValue` ALLER dangerRatings des Bulletins |
| `level` | abgeleitet: 1->1, 2->2, 3->3, 4->4, 5->4 |
| `scale` | `"eaws"` |
| `label` | `"Lawinenstufe {n} ({wort})"`, Woerter: 1 gering, 2 mäßig, 3 erheblich, 4 groß, 5 sehr groß |
| `valid_from` / `valid_to` | `validTime.startTime` / `endTime`, timezone-aware UTC |
| `url` | `https://avalanche.report/bulletin/{YYYY-MM-DD}?region={regionID}`; **Datum = Ortsdatum (Europe/Vienna) von `validTime.endTime`** (nicht `customData.ALBINA.mainDate`; endTime 2026-02-20T16:00Z -> 2026-02-20; Sommerzeit 2026-05-02T15:00Z -> 2026-05-02) |
| `region_label` | `regions[].name` der Mikroregion (z. B. "Lasörlinggruppe") |
| `dedup_id` | `f"avalanche_bulletin:{regionID}"` -- **stabil je Mikroregion** (NICHT die bulletinID: die aendert sich taeglich und wuerde taeglich 17:00 neu alarmieren) |
| `elevation_value` | `str | None`: Zahl als String (`"2200"`) oder `"Waldgrenze"` (aus `treeline`); `None` = keine Hoehenangabe. Kein erfundener Zahlenwert |
| `elevation_direction` | `"above"` (lowerBound) / `"below"` (upperBound) / `None` |
| `problems` | `tuple[str, ...]` CAAML-`problemType`-Codes in Bulletin-Reihenfolge, **dedupliziert**, inkl. `no_distinct_avalanche_problem`, `favourable_situation`, `cornices` |
| `time_of_day` | `None` | `"earlier"` | `"later"`: nur gesetzt, wenn die Hoechststufe von `earlier` und `later` verschieden ist; dann die Periode, die die Hoechststufe traegt. `all_day` -> `None` |

**ENTSCHEIDUNG Gleichstand der Hoechststufe in mehreren Ratings** (Fixture `2026-02-26`: `earlier` considerable ab Waldgrenze,
`later` considerable ohne Hoehe): bevorzugt wird das Rating **ohne Hoehenbegrenzung** (breiteste Aussage -- "ab Waldgrenze" wuerde die
Aussage fuer tiefere Lagen unterschlagen); danach `all_day` vor `later` vor `earlier`; danach Reihenfolge im Bulletin.
Ergebnis fuer die Fixture: `native_level 3`, `elevation_value None`, `time_of_day None` (Maxima beider Perioden gleich).

Neue `OfficialAlert`-Felder (`models.py`, alle mit Default, Bestand bit-identisch):
`scale: str = "awareness"`, `native_level: Optional[int] = None`, `elevation_value: Optional[str] = None`,
`elevation_direction: Optional[str] = None`, `problems: tuple[str, ...] = ()`, `time_of_day: Optional[str] = None`.
`level` bleibt Pflichtfeld.

## 3. `services/official_alerts/region_mapper.py` (neu)

```python
class RegionMapper:
    def __init__(self, geojson_path: Path | str) -> None     # laedt fail-soft (fehlende/kaputte Datei -> leer, kein raise), Cache je Instanz/Pfad
    def regions_at(self, lat: float, lon: float) -> list[str]   # ALLE getroffenen Regions-IDs, sortiert (String), Loecher beachtet
    def bbox(self) -> tuple[float, float, float, float] | None  # (min_lon, min_lat, max_lon, max_lat) ueber alle Features; None wenn leer

def point_in_geometry(lat: float, lon: float, geometry: dict) -> bool   # Polygon/MultiPolygon (+Loecher); sonst False
```
`meteoalarm.py` nutzt `region_mapper.point_in_geometry` (**AC-10**): `meteoalarm._point_in_geometry is region_mapper.point_in_geometry`;
die lokale `_point_in_ring`-Kopie entfaellt (`geo_ray_cast._point_in_ring` bleibt die einzige Implementierung).
Die vier Bestandskonsumenten werden nicht migriert.

## 4. Darstellung (`output/renderers/alert/official_alerts.py`)

- **Zentraler Text-Helfer:** `avalanche_bulletin_text(alert: OfficialAlert) -> str`
  `"Lawinenstufe {n} ({wort})"` + `" oberhalb|unterhalb {wert} m"` bzw. `" oberhalb|unterhalb Waldgrenze"` (nur wenn Hoehe gesetzt)
  + `" (vormittags)"` / `" (nachmittags)"` (nur wenn `time_of_day`) + `" · " + ", ".join(Problemnamen)` (nur wenn Probleme).
  Beispiel: `Lawinenstufe 4 (groß) oberhalb Waldgrenze · Triebschnee`.
  Problemnamen (Tabelle `AVALANCHE_PROBLEM_NAMES_DE`): new_snow Neuschnee · wind_slab Triebschnee · persistent_weak_layers Altschnee ·
  wet_snow Nassschnee · gliding_snow Gleitschnee · cornices Wechten · no_distinct_avalanche_problem "kein ausgeprägtes Lawinenproblem" ·
  favourable_situation "günstige Situation". Unbekannter Code -> der Code selbst (nie verschlucken).
- `_display_label(alert)` liefert fuer `avalanche_bulletin` den Helfer-Text; `_render_warn_block_embedded`, Standalone-HTML, Telegram,
  Plain nutzen ihn. Fuer diese Gefahrenart entfaellt die Leiter ("Stufe GELB (1/3)", "ROT · 0/3", "n/3", Ampelwort GELB/ORANGE/ROT in der Aussage);
  Farbe kommt aus dem abgeleiteten `level`, Stufe 5 hat dieselbe Farbe wie 4.
- **Telegram** haengt fuer `avalanche_bulletin` die `alert.url` an (Quellenname steht als `source_label`-Parameter schon in der Nachricht);
  **Mail** nimmt sie wie bisher als `source_url` des Quellen-Links (html.py unveraendert).
- **Ortsvergleich-Quellenfilter** (`compare_official_alert.py:435`, `official_warnings.sources`): Vokabular des Nutzers ist `avalanche_report`
  (= `AvalancheReportSource.name`, Konvention aus `test_official_warnings_source_filter.py`: Quellenname == Filterwert). Der Filter vergleicht den Teil des
  `alert.source` VOR dem ersten `:` (`avalanche_report:AT-07` -> `avalanche_report`); bestehende Quellen ohne `:` verhalten sich bit-identisch.
  Tests: `test_avalanche_report_coverage.py::test_ortsvergleich_quellenfilter_*`.
- **Registrierung:** `AvalancheReportSource()` (Standardtabelle) steht in `official_alerts/__init__.py` als LETZTE Quelle (Tie-Break-Reihenfolge, ADR-0016).
  Test: `test_quelle_ist_im_register_eingetragen_...`.
- `official_alert_source_label("avalanche_report:AT-07") == "Lawinenwarndienst Tirol, avalanche.report"`; analog `:IT-32-BZ` "Lawinenwarndienst Südtirol, avalanche.report",
  `:IT-32-TN` "Lawinenwarndienst Trentino, avalanche.report", `:AT-02` "Lawinenwarndienst Kärnten, avalanche.report" (je Tabellenzeile in `_SOURCE_LABELS`).
- Auch die Streifen/Plain-Pfade (`render_official_alerts_html`, `render_official_alerts_plain`, Mail-Plain, Standalone-HTML) zeigen fuer diese Gefahrenart
  den Helfer-Text (`_display_label`) statt `alert.label`; die Pro-Ort-Streifen des Ortsvergleichs (`render_compare_html`) tragen dadurch
  "Lawinenstufe 5 (sehr groß)". Ohne `native_level` (Alt-/Handbau) nutzt jeder Pfad das `level`.
- `compare_html._warn_short`: Ziffer = `native_level`, **ersatzweise `level`** (wenn `native_level is None`), also `("Lawine 3", "warn")`.
- Banner-Kopfzeile des Ortsvergleichs (`_render_warn_banner` -> `count_line`) und die `wb-count`-Zeile des Trip-Blocks duerfen fuer `avalanche_bulletin`
  keine `n/3`-Leiter tragen (Test: Regex `\d/3` in `wb-count`).
- `_HAZARD_LABELS["avalanche_bulletin"] = "Lawinenstufe"` (Typ-Wort; bleibt neben `"avalanche": "Lawine"`); `_HAZARD_DISPLAY` -> `("Lawinenstufe", "AV")`.
- **Alarm-/Premium-SMS** (`_sms_hazard_token`): `f"AV{native_level}"` -- ohne Doppelpunkt, ohne L/M/H, ohne Stunde (`AV5`).
  Premium-SMS nutzt dieselbe Funktion `render_official_alert_sms(..., limit=153)` (`channel_layout.CHANNEL_LIMITS["premium_sms"]["max_chars"]`);
  Alarm-SMS Standardlimit 140.
- **Trip-Briefing-SMS** (`official_alerts_to_sms_entries` -> `builder._official_alerts`): im `!`-Block als `AV4` (kein `:`, kein Buchstabe, kein `@h`),
  unabhaengig von der Metrik `AV`; Filter `alert.level >= min_level` wie bisher (abgeleitetes `level`).
  `LEVEL_LETTERS`, `MIN_SMS_LEVEL` bleiben unveraendert {2,3,4}/3 (TABU-Kommentar).
- **Ortsvergleich** (`compare_html.py`): `_warn_short(alert)` fuer `avalanche_bulletin` -> `("Lawine {native_level}", severity)`,
  severity `{1:"info", 2:"caution", 3:"warn", 4:"danger", 5:"danger"}`. `_render_warn_cell` rendert den Chip mit der Farbe des abgeleiteten `level`.
- `alert_urgency.urgency_from_official_level(1) == "LOW"` (Stufe 1 nie HIGH); 2->LOW, 3->MODERATE, 4->HIGH, unbekannt (z. B. 5, 9) bleibt HIGH (Bestandstest).

## 5. Eskalation / Dublettenwahl / Gedaechtnis

- `official_alert_state_entry(alert, iso)` schreibt `last_reported_value = float(native_level)` wenn `native_level` gesetzt, sonst `float(level)`.
- `official_alert_revision_verdict` (beide Pfade: exakter Schluessel UND Ueberlappungs-Kandidat, inkl. `merged_entry`) vergleicht `native_level` (falls gesetzt), sonst `level`.
  4->5 (abgeleitetes `level` bleibt 4) eskaliert; 4->4 in beruehrender Folgeperiode (17:00-Fenster) -> `should_report False`, `merged_entry` gesetzt.
- `base.get_official_alerts_with_status`: Pass 1 und Pass 2 vergleichen `native_level` falls gesetzt, sonst `level` (nie ueber Skalen hinweg -- eigene Gefahrenart).
- **OFFEN-PO / ENTSCHEIDUNG AC-13:** fuer "Absenkung/Entwarnung traegt die Dringlichkeit des alten Werts" gibt es im Bestand KEINEN Meldepfad
  (amtliche Absenkungen werden still fortgeschrieben). Der Vertrag fordert eine reine Funktion, Vorbild `_ordinal_severity` (max von alt/neu):
  `alert_urgency.urgency_from_official_transition(previous: OfficialAlert, current: OfficialAlert | None) -> str`
  = `urgency_from_official_level(max(previous.level, current.level if current else 0))`. Neues Verhalten -- bitte im Handoff bestaetigen/streichen.
  Zusaetzlich (Bestandspfad): `official_alert_revision_verdict` meldet eine Absenkung NICHT (`False`) und behaelt den alten Hoechstwert im Gedaechtnis
  (`merged_entry["last_reported_value"]` bzw. unveraenderter State = alter Wert).

## 6. Katalog / Builder / Register

- `hazard_symbols.HAZARD_SMS_SYMBOLS["avalanche_bulletin"] = "AV"` direkt hinter `"avalanche"`; `HAZARD_BEDEUTUNG_DE[...] = "Lawinenstufe"`, `_EN[...] = "avalanche level"`.
  `AV` gehoert damit EXKLUSIV `avalanche_bulletin`; Fallback `sms_symbol_for(<unbekannt>)` liefert nie `AV`.
- `builder._wintersport`: `("AV", ...)` aus `pairs` entfernt; `adapters/trip_result.py` liefert weiter `avalanche_level=None`.
- Die Kollisionswaechter `tests/unit/test_keine_doppelten_kennungen.py` (Punkt 3: Baustein vs. Warn-Kuerzel -- `("AV","wintersport")` in `builder.POSITIONAL`)
  und `tests/tdd/test_kuerzel_eindeutig.py` pruefen `AV` -- /50 muss sie GRUEN halten (Entscheid in /50: `AV` aus `POSITIONAL`/Register entfernen oder Waechter gezielt anpassen).

## 7. Bestandstests, die ich im RED angepasst habe
- `tests/tdd/test_sms_official_alert_tokens.py::test_ac5_catalog_matches_spec_table`: erlaubt zusaetzlich `{"avalanche_bulletin": "AV"}` (sonst rot, sobald der Katalog waechst).
- `tests/tdd/test_hazard_symbols.py`: neuer Test, der `AV` ausdruecklich NUR fuer `avalanche_bulletin` erlaubt; `avalanche` bleibt `AW`.
- Golden `tests/fixtures/official_alert_render_snapshot_1944.json` darf sich NICHT aendern (Bestandswarnungen bleiben byte-identisch).

## 8. Egress-Inventar
`src/app/egress_guard.py::INVENTORY` und `internal/egress/inventory.go` erhalten `static.avalanche.report` und `avalanche.report` (BLOCKED / Blocked, siehe Abschnitt 1);
Drift-Test `tests/test_egress_inventory_drift.py` bleibt gruen. `internal/scheduler/warn_service_health.go` aggregiert Dienste dynamisch nach Namen
(`canonicalWarnServiceName`) -- **keine Go-Aenderung dort noetig** (geprueft); Call-Log-`service` ist `avalanche_report`.

## 10. Fixtures / Ablage (Entscheidung)
`tests/fixtures/avalanche_report/` (README dort: Herkunft, echt vs. abgeleitet): `bulletins/` (echt), `derived/` (3 abgeleitete, dokumentiert),
`regions/` (4 GeoJSON, CC0), `404_latest_AT-02.json` (echte 404-Antwort). /50 kopiert `regions/{X}_micro-regions.geojson.json` byte-identisch nach
`src/services/official_alerts/data/avalanche_regions_{X}.geojson.json` (Test `test_ac7_standardtabelle_...` vergleicht die Bytes).
Der Test-Transport (`tests/helpers/avalanche_report_support.py::FixtureTransport`) ist ein echter `httpx.BaseTransport`; die Quelle MUSS ihn ueber den
Konstruktor-Parameter `transport` an `httpx.Client(..., follow_redirects=True)` geben (kein lokaler `http.server`: `--disable-socket` sperrt Loopback).

## 9. Bewusst gruene Tests (Regressionswachen, im RED nicht rot)
Siehe Tabelle am Ende von `test-red-output.txt`.


## 11. Bestandstests, die durch die Spec-Entscheidung "AV nicht mehr aus `_wintersport()`" VERALTEN (Kern muss 100 % gruen bleiben)
/50 muss diese Tests auf das neue Verhalten drehen oder loeschen (Test-Politik: veraltetes Verhalten -> fixen ODER loeschen). Sie sind im RED NICHT
angefasst (sie sind heute gruen und pruefen die alte `avalanche_level`-Quelle):
- `tests/golden/sms/arlberg-winter-morning.txt` (+ `tests/golden/test_sms_golden.py`): erwartet `... SL1800 AV3` aus `DailyForecast(avalanche_level=3)` -> `AV3` faellt weg, Golden neu erzeugen.
- `tests/tdd/test_sms_snow_symbols.py`: AC-5 (Reihenfolge SD, NS24+, SL, AV), DROP_ORDER-Test (`tail_symbols = ["AV", "SL", ...]`), Fixture `avalanche_level=3`.
- `tests/tdd/test_sms_extended_tokens_truncation.py` (~Z. 153): erwartet `"AV3"` im gekuerzten Text.
- `tests/unit/test_token_builder.py` (~Z. 279/299), `tests/unit/test_sms_symbol_grammar_classes.py` (~Z. 245/259, `_SYSTEM_SYMBOLS` enthaelt `AV`),
  `tests/unit/test_sms_token_symbol_register_ratchet.py` (~Z. 64/66, 872), `tests/tdd/test_issue_936_sms_stub.py` (live-markiert), `tests/tdd/test_sms_wintersport_tokens.py`: auf Abhaengigkeit pruefen.
- `tests/unit/test_keine_doppelten_kennungen.py` (Punkt 3: Baustein-Symbol `AV` aus `builder.POSITIONAL` vs. Warn-Kuerzel `AV`) und
  `tests/tdd/test_kuerzel_eindeutig.py` (~Z. 95/277: Text "AV Lawinenstufe"/"AV avalanche level" als "Weitere") -- `AV` darf nur EINMAL gelistet sein.
- `tests/tdd/test_hazard_symbol_catalog_docs.py`: Katalog-Doku-Konformitaet (neue Gefahrenart `avalanche_bulletin`/`AV` in `docs/reference/sms_format.md` ergaenzen).
Nicht betroffen: `tests/unit/test_trip_result_adapter.py` (Adapter liefert weiter `avalanche_level=None`, `_wintersport_default_config` bleibt), `tests/golden/text_report/*` (anderer Pfad).

## 12. Offene Entscheidungen fuer den Orchestrator (im Handoff bestaetigen)
1. **AC-13** `alert_urgency.urgency_from_official_transition(previous, current)` -- NEUES Verhalten ohne bestehenden Meldepfad (Absenkungen werden still fortgeschrieben).
2. **Gleichstandsregel AC-2** ("breiteste Aussage": Rating ohne Hoehenbegrenzung gewinnt) -- haftungsrelevante Auslegung der Spec.
3. **`cached_fetch(..., not_covered_ttl=...)`** -- additive Aenderung in `warn_egress.py` (Default = Bestand bit-identisch).
4. **IsolationKind BLOCKED** (siehe oben) und **Quellenschluessel** `avalanche_report:{key}` samt Prefix-Vergleich im Ortsvergleich-Filter.
5. Slice-Umfang: die Kollateral-Tests aus Abschnitt 11 erhoehen den Diff erheblich (Golden + ~6 Dateien).

## Tech-Lead-Entscheide zu den offenen Punkten aus /40 (2026-10-13, Orchestrator)

1. AC-13: `alert_urgency.urgency_from_official_transition(previous, current)` als reine Funktion (Maximum alt/neu) — bestätigt; setzt die PO-Regel „Entwarnung trägt die Dringlichkeit des alten Werts" um.
2. AC-2-Gleichstand: Höchststufe in mehreren Ratings → Rating ohne Höhenbegrenzung (breiteste Aussage) gewinnt — bestätigt (konservativ, keine Verengung der amtlichen Aussage).
3. `cached_fetch(..., not_covered_ttl=...)` additiv, Default = Bestand, Quelle nutzt 1800 s — bestätigt.
4. IsolationKind `BLOCKED` für beide Hosts (Python + Go) wie alle Warn-Hosts — bestätigt. Folge für /70: Staging-Nachweis „Tirol-Punkt sauber leer" über denselben Mechanismus wie die geblockten Warn-Feeds (#1430) planen; „nicht abrufbar" auf Staging ist dort zu erwarten und kein Befund.
5. Quellenschlüssel `avalanche_report:{key}`, Compare-Quellenfilter vergleicht Teil vor `:` — bestätigt.
6. Bestandstests, die durch „AV nicht mehr aus `_wintersport()`" veralten (Abschnitt 11): in /50 anpassen, nicht löschen-um-grün; jede Anpassung im Commit begründen.

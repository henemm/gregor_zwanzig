# Context: feat-1681-meteoalarm-de

Erhoben am 2026-09-19 für Issue #1681 („Amtliche Warnung: Deutschland an den MeteoAlarm-Feed
anbinden"), Epic-Bezug #1419 (Rang 10/E6), #2258. Zeilenangaben gegen `fa49e232` (main).
Live-Messungen vom 2026-09-19 ca. 16:50 UTC; Rohdaten nur im Session-Scratchpad, nichts eingecheckt.

## Request Summary

`MeteoAlarmFeedSource("DE")` registrieren, damit Punkte in Deutschland amtliche DWD-Warnungen
über den kontingentfreien Feed `feeds.meteoalarm.org` bekommen (heute nur IT und AT). Offen laut
Ticket: (1) Punkt→Zone-Auflösung für DE, (2) Feedgröße/gzip, (3) Drei-Zustände-Regel
„nicht zuständig" ≠ „nicht abrufbar" ≠ „keine Warnung", (4) Test gegen aufgezeichneten DE-Feed.
Nicht KHW-relevant (PO-Kommentar 2026-08-19), Priorität `medium`.

**Kernbefund vorab:** Der DE-Feed führt pro Gebiet **beide** Kennungen (`EMMA_ID` und
`WARNCELLID`). Damit ist **keine EMMA-Zuordnungstabelle nötig** — ein Punkt kann über die
öffentliche DWD-Warngebiets-Geometrie direkt auf eine WARNCELLID aufgelöst und gegen das
`WARNCELLID`-Geocode im Feed gematcht werden.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/official_alerts/meteoalarm_feed.py:50-54` | `FEED_BASE_URL`, `_FEED_PATHS` (nur `IT`/`AT`) — hier `DE: /api/v1/warnings/feeds-germany` ergänzen |
| `meteoalarm_feed.py:55` | `TIMEOUT = 15.0`, Kommentar „~1,4–2,4 MB, kein gzip" |
| `meteoalarm_feed.py:59` | Modul-Cache `_cache`, Schlüssel = Ländercode |
| `meteoalarm_feed.py:73-82` | `_zone_for_point` (IT): `dpc._zone_at` + Regionspräfix→EMMA-Tabelle, zweiwertig |
| `meteoalarm_feed.py:102-142` | `_zone_for_point_at` (AT): drei Zustände über gecachte ZAMG-Antwort |
| `meteoalarm_feed.py:145-164` | `_info_entries_from_alert` — übernimmt `responseType` **nicht** (s. Risiken) |
| `meteoalarm_feed.py:167-176` | `_emma_ids_for_alert` — filtert fest auf `valueName == "EMMA_ID"`; für DE ggf. auf `WARNCELLID` generalisieren |
| `meteoalarm_feed.py:179-198` | `_parse_feed` — verlangt `warnings`-Liste (F001) |
| `meteoalarm_feed.py:201-215` | `_get_cached_feed` — `httpx.get` ohne eigene Header, über `warn_egress.cached_fetch` |
| `meteoalarm_feed.py:218-271` | `_alerts_for_zone` — Zonenfilter vor Malformationsprüfung (F003/F005), `Cancel` ohne info still |
| `meteoalarm_feed.py:281` | `__init__(self, country: Literal["IT", "AT"])` — Typ erweitern |
| `meteoalarm_feed.py:288-319` | `covers()`: AT = INCA-Bbox, IT = echte Geometrie (Muster A) |
| `meteoalarm_feed.py:321-352` | `fetch()`: Länderverzweigung `if AT … else (IT)` — DE fiele heute in den IT-Zweig |
| `src/services/official_alerts/__init__.py:22-42` | Registrierung + verbindlicher Reihenfolge-Kommentar |
| `src/services/official_alerts/base.py:25-40` | `OfficialAlertSource`-Protokoll (`name`, `covers`, `fetch`) |
| `base.py:60-89` | `filter_alerts_to_window` — Alerts ohne `valid_from`/`valid_to` bleiben **immer** erhalten |
| `base.py:119-225` | `get_official_alerts_with_status`: covering/failed-Kompensation, Fenster, hazard-Dedupe über Quellen |
| `src/services/official_alerts/geo_ray_cast.py:12-28` | `_point_in_ring` (Ring = `(lon, lat)`, GeoJSON-Konvention) |
| `src/services/official_alerts/dpc.py:62-88` | Muster „eingecheckte Zonen-JSON": `_ZONES_PATH`, `_load_zones`, `_zone_at` (lineare Suche) |
| `src/services/official_alerts/department_mapper.py:64-96,199-231,326-376` | Muster FR: Datenherkunft im Docstring, Loader, Loch-Behandlung, `lru_cache` für Lookups |
| `src/services/official_alerts/fr_departments.py` | Code→Name-Tabelle (für DE nicht nötig, `areaDesc` liefert den Namen) |
| `src/services/official_alerts/data/` | `dpc_zones.json` 563 KB, `department_polygons.json` 438 KB, `massif_polygons.json` 180 KB |
| `src/services/official_alerts/warn_egress.py:40-46` | TTLs: Erfolg 1800 s, Fehlschlag 60 s, „nicht zuständig" 24 h |
| `warn_egress.py:71, 349, 377-581` | `mark_fetch_incomplete`, `log_zone_drift`, `cached_fetch` |
| `src/services/official_alerts/meteoalarm_budget.py` | Tagesbudget nur für den EDR-Index-Weg (`meteoalarm.py:31`) — **gilt nicht** für den Feed |
| `src/services/official_alerts/meteoalarm.py:595-644` | `_group_and_map_info_entries` — geteilter Mapper, filtert Level < 2, ohne `responseType` |
| `src/services/radar_service.py:40-43` | INCA-Bbox (46,3–49,1 N / 9,5–17,2 O) — schließt Südbayern ein |
| `tests/tdd/test_meteoalarm_feed_italien.py`, `test_meteoalarm_feed_oesterreich.py` | Vorbild-Tests je Land |
| `tests/tdd/test_meteoalarm_source.py`, `test_official_alerts_unavailable_hint.py`, `test_dpc_bulletin_source.py` | weitere Feed-Bezüge |
| `tests/fixtures/meteoalarm_feed/` | Fixtures IT/AT (Stichprobe 20–46 KB, Äquivalenz 179–614 KB) + `README.md` mit Herkunft |

## Existing Patterns

| | IT | AT | FR (Départements) | DE (Vorschlag aus Befund) |
|---|---|---|---|---|
| Zonenkennung im Feed | `EMMA_ID` IT001–IT020 | `EMMA_ID` ATxxx | — (Vigilance) | `EMMA_ID` DE… **und** `WARNCELLID` |
| Punkt→Zone | eingecheckte DPC-Polygone + Präfix-Tabelle | ZAMG-`gemeindenr`[:3] (Fremdendpunkt) | eingecheckte Polygone + Ray-Cast | eingecheckte DWD-Warngebiete + Ray-Cast → WARNCELLID |
| `covers()` | Geometrie (Muster A, ADR-0041) | INCA-Bbox (Muster B) | Geometrie | Geometrie (Muster A) |
| Zustände | 2 (Zone / None → nicht zuständig) | 3 (Zone / nicht zuständig / Fetch-Fehler) | 2 | 2 genügen, wenn `covers()` = Geometrie: kein Treffer ⇒ nicht zuständig, Feed-Fehler ⇒ `cached_fetch` meldet Ausfall, leere Zone ⇒ keine Warnung |

Muster A verlangt nach ADR-0041, dass die Geometrie lokal liegt; ADR-0041 warnt zugleich, dass
eingecheckte Geometrie driftet (#1434, #1397 S4). Die DWD-Warngebiete sind amtlich und mit
Stand-Kennung (Copyright-Feld „© GeoBasis-DE / BKG 2021") — Drift-Risiko s. Risiken.

## Dependencies

**Upstream**
- `https://feeds.meteoalarm.org/api/v1/warnings/feeds-germany` (öffentlich, ohne Auth, ohne Kontingent laut ADR-0039).
- Für die Geometrie (einmalig offline, nicht zur Laufzeit): DWD GeoServer WFS
  `https://maps.dwd.de/geoserver/dwd/ows` Layer `dwd:Warngebiete_Kreise` (+ ggf. `dwd:Warngebiete_Kueste`).
- Referenzliste: `https://www.dwd.de/DE/leistungen/opendata/help/warnungen/cap_warncellids_csv.csv`.

**Downstream** (rufen die Registry auf, bekommen DE automatisch mit)
- `src/services/comparison_engine.py:322-323` — Ortsvergleich, `get_official_alerts_with_status` (inkl. „nicht abrufbar").
- `src/services/trip_report_scheduler.py:1372-1374` — Trip-Briefing, `get_official_alerts_with_status`.
- `src/services/trip_alert.py:2579, 2631` — Trip-Alarme, `get_official_alerts_for_location`.
- `src/services/compare_official_alert.py:55, 378` — Ortsvergleich-Alarme, `get_official_alerts_for_location`.
- Kanäle/Renderer bekommen `OfficialAlert` wie bisher; `source` bleibt `"meteoalarm"`.

## Existing Specs/ADRs

- ADR-0039 (Feed statt EDR-Index): Folgepflichten „drei Zustände strikt trennen", „kein Daueralarm", „für weitere Länder eigenes Auffrischraster vorsehen". Ein weiteres Land ist kein neuer Bezugsweg ⇒ vermutlich kein neues ADR (offen, im Analyseschritt bestätigen).
- ADR-0041 (Zuständigkeit nach Endpunkt-Art, Muster A/B/C, Prüffrage „kann ein nicht zuständiger Punkt einen Ausfallhinweis auslösen?").
- ADR-0016 (amtliche Warnungen als additiver Typ).
- Specs: `docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md`, `feat_1445_s3_oesterreich_feed.md`, `fix_1397_s4_it_grenze.md`, `fix_1348_warn_kompensation.md`, `warn_unavailable_hint.md`, `rework_1467_s4b_entdopplung.md`, `fix_1685_warnfenster_revision.md`, `docs/specs/data_sources.md`.
- Keine DE-spezifische Spec vorhanden.

## Live-Messung DE-Feed (2026-09-19)

**Feed** `https://feeds.meteoalarm.org/api/v1/warnings/feeds-germany`

| Messgröße | Wert |
|---|---|
| HTTP | 200, `content-type: application/json`, `server: Cowboy`, `cache-control: max-age=0, private, must-revalidate` |
| Größe ohne `Accept-Encoding` | 5 004 980 Bytes, 1,4 s |
| Größe mit `Accept-Encoding: gzip` (auch `gzip, deflate, br`) | **identisch 5 004 980 Bytes**, kein `Content-Encoding` — **der Server komprimiert nicht** |
| Lokal gzip-komprimiert (nur Vergleich) | 295 693 Bytes (Faktor ~17) — nicht abrufbar, nur theoretisch |
| Vergleich gleicher Zeitpunkt | Italien 1 485 439 B, Österreich 368 410 B (beide ebenfalls ohne gzip) |
| ETag/Last-Modified | keine |
| JSON-Parse (`json.load`) | ~0,06 s |
| Einträge `warnings[]` | 254 (msgType: 122 `Alert`, 132 `Update`) |
| Sprachen je Warnung | 8 (`de-DE`, en, fr, es, ar, ru, tr, pl) — erklärt die Größe |
| Gebiete | 7 624 `area[]`-Einträge, **0 mit `polygon`, 0 mit `circle`** — keine Geometrie im Feed |
| Geocodes | je Gebiet genau 2: `EMMA_ID` (7 624×) und `WARNCELLID` (7 624×) |
| Distinkte IDs | 290 EMMA_ID, 290 WARNCELLID, Zuordnung im Feed **1:1** |
| Beispiele | `DE376`↔`103454000` (Kreis Emsland), `DE021`↔`909274999` (Kreis und Stadt Landshut), `DE022`↔`913075001` (Vorpommern-Greifswald – Binnenland Nord), `DE023`↔`914523002` (Vogtlandkreis – Bergland) |
| WARNCELLID-Arten im Feed | 207× `1…` (Kreis), 75× `9…` (zusammengefasste/geteilte Kreise), 8× `5…` (Küste/See, `501000001`–`501000008`) |
| Ereignisse (de-DE) | GEWITTER 156, STARKES GEWITTER 60, WINDBÖEN 15, NEBEL 9, … |
| Stufen (de-DE) | gelb 188, orange 65, rot 1 |
| `responseType` (de-DE) | `Prepare` 215, **`AllClear` 39** (Headline „AUFHEBUNG der WARNUNG vor …", Level weiterhin z. B. `2; yellow`) |
| `expires` (de-DE) | Spanne 14.09.–21.09.; Großteil (214) bereits am 16.09. abgelaufen ⇒ Feed enthält viele abgelaufene Fassungen; **4 Einträge ohne `expires`** (Seewetterdienst Hamburg, BÖEN/STARKWIND, Küstenzellen) |
| Vergleich IT/AT | `responseType` dort nur `None`/`Monitor`; Geocodes nur `EMMA_ID` — `AllClear` und `WARNCELLID` sind DE-spezifisch |

Die Ticketangabe „13,5 MB" ist heute nicht reproduziert (5,0 MB bei 254 Warnungen). Die Größe
skaliert mit der Warnanzahl × 8 Sprachen; an Unwettertagen sind 13,5 MB plausibel (offen, nicht gemessen).

**Geometriequelle für DE-Zonen**

| Quelle | Befund |
|---|---|
| DWD WFS `https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetCapabilities` | Layer vorhanden: `dwd:Warngebiete_Kreise`, `_Gemeinden`, `_Kueste`, `_Binnenseen`, `_Bundeslaender` (+ `Warnungen_*`) |
| `…&request=GetFeature&typeNames=dwd:Warngebiete_Kreise&outputFormat=application/json` | 402 Features (310× TYPE 1 = `1…`, 92× TYPE 10 = `9…`), 371 Polygon + 31 MultiPolygon, 41 301 Stützpunkte, 903 710 Bytes (4 Nachkommastellen), EPSG:4326, Felder u. a. `WARNCELLID`, `NAME`, `BL`, `MIN_HEIGHT`/`MAX_HEIGHT`, `COPYRIGHT` |
| Abdeckung | **282 von 290** Feed-WARNCELLIDs im Kreis-Layer; die 8 fehlenden sind genau die Küsten-/Seezellen `5010000xx` (Layer `dwd:Warngebiete_Kueste`) |
| Überlappung | 400 Zufallspunkte in DE-Bbox: 0 Mehrfachtreffer (Kreis- und 9er-Zellen überlappen nicht), 91 ohne Treffer (Ausland/See) |
| Kontrollpunkte (Ray-Cast gegen den Layer) | Zugspitze → 109180000 Garmisch-Partenkirchen; Garmisch → dito; Oberstdorf → 109780000 Oberallgäu; Berchtesgaden/Watzmann → 109172000 Berchtesgadener Land; München → 909184999; Helgoland → 901056002; Innsbruck, Kufstein, Salzburg, Basel, offene Nordsee → kein Treffer. 12 Lookups ~0,02 s (lineare Suche, ungesimplified) |
| `cap_warncellids_csv.csv` | 11 828 Zeilen, alle Ebenen (1/2/4/5/7/8/9); nur Liste, keine Geometrie |
| MeteoAlarm-EMMA-Geometrie | Keine öffentliche Geometrie gefunden. `https://api.meteoalarm.org/metadata/v1/geocodes` → HTTP 401 (Auth). Laut Websuche gibt es eine Geocode-Liste (Code/Name) auf `https://meteoalarm.org/en/page/re-users` (JS-gerendert, Download-URL nicht verifiziert) — **offen**, aber nicht nötig |

**EMMA_ID ↔ WARNCELLID:** Im Feed stehen beide pro Gebiet, 1:1. Die Nummerierung ist nicht
ableitbar (`DE021` = Landshut 909274999, `DE022` = Vorpommern-Greifswald 913075001) — eine
EMMA-Tabelle könnte nur aus dem Feed selbst angesammelt werden (heute 290 von ~410 Zellen). Der
Match über `WARNCELLID` umgeht das vollständig.

## Risks & Considerations

1. **Aufhebungen (`responseType: AllClear`) würden als aktive Warnung erscheinen.** 39 von 254
   de-DE-Infos sind „AUFHEBUNG der WARNUNG …" mit weiterhin gesetztem `awareness_level` (z. B. gelb).
   `_info_entries_from_alert` (`meteoalarm_feed.py:145-164`) und `_group_and_map_info_entries`
   (`meteoalarm.py:595-644`) werten `responseType` nicht aus. Bei IT/AT kommt `AllClear` nicht vor,
   daher bisher unbemerkt. Solange `expires` der Aufhebung in der Zukunft liegt, würde sie als gelbe
   Warnung gerendert. Behandlung (verwerfen? als Ende der Ursprungswarnung?) ist fachlich zu entscheiden — **offen**.
2. **Ausfall des DE-Feeds kann in Südbayern stumm „kompensiert" werden.** `base.py:119-225`: Hinweis
   „nicht abrufbar" nur bei `failed >= covering`. Für Punkte in der INCA-Bbox (u. a. Garmisch, Oberstdorf,
   Berchtesgaden, München) sind zusätzlich `GeoSphereWarnSource` und `MeteoAlarmFeedSource("AT")`
   (Bbox-`covers`) sowie ggf. `DpcSource` (Bbox 36–47,5 N) „zuständig"; ZAMG-404 zählt als Erfolg.
   Fällt der DE-Feed aus, gilt 1 von 3 als ausgefallen ⇒ **kein** Hinweis, obwohl keine einzige
   zuständige deutsche Quelle geantwortet hat. Genau die Bayerischen Alpen sind betroffen. Nicht gemessen,
   aus Code abgeleitet — im Analyseschritt mit echtem Pfad nachweisen.
3. **Drei-Zustände-Regel:** `fetch()` verzweigt heute `if AT … else` (`meteoalarm_feed.py:322-348`);
   DE fiele ungeprüft in den IT-Zweig (`_zone_for_point` = IT-Geometrie). Eigene DE-Auflösung nötig.
   Mit Geometrie-`covers()` (Muster A) gilt: kein Treffer ⇒ nicht zuständig (still); Feed-Fehler ⇒
   `cached_fetch` meldet Ausfall; Zone ohne Eintrag ⇒ keine Warnung. Punkte knapp außerhalb vereinfachter
   Polygone (Grenze, Küste) schweigen — Known Limitation wie IT.
4. **Küste/See:** 8 Feed-Zellen `5…` liegen nicht im Kreis-Layer; ohne `dwd:Warngebiete_Kueste` sind
   Küstenwarnungen unerreichbar. Die 4 Seewetter-Einträge **ohne `expires`** blieben über
   `filter_alerts_to_window` (fehlendes `valid_to` ⇒ immer behalten) dauerhaft sichtbar. Ob Küste
   überhaupt in den Scope gehört: **offen** (Wanderer-Produkt).
5. **Geocode-Filter:** `_emma_ids_for_alert` liest nur `EMMA_ID`. Match über `WARNCELLID` erfordert
   eine länderabhängige Geocode-Art; der Malformations-Schutz (F003/F005) muss dieselbe Art verwenden.
6. **Feedgröße/Bandbreite:** Server liefert kein gzip, keine Änderungskennung. 5 MB (bis ggf. 13,5 MB)
   je Abruf bei Erfolgs-TTL 30 min ⇒ ~240 MB/Tag im Normalfall (Rechnung, nicht gemessen; je Prozess —
   Prod und Staging getrennt). `TIMEOUT = 15.0` bei gemessenen 1,4–2,0 s ausreichend; bei 13,5 MB offen.
   ADR-0039 verlangt für weitere Länder ein „eigenes Auffrischraster". Speicher: der gesamte geparste
   Feed bleibt im Modul-Cache.
7. **Geometrie-Datei:** Kreis-Layer roh 904 KB; mit Rundung/Vereinfachung vermutlich im Rahmen der
   bestehenden Dateien (563/438 KB) — nicht gemessen. Drift: DWD ändert Warnzellen bei Kreisreformen;
   ein Drift-Wächter (Feed-WARNCELLID nicht in eingecheckter Geometrie ⇒ `log_zone_drift`) wäre das
   Gegenstück zu ADR-0041. Lizenz: Datensatz trägt „© GeoBasis-DE / BKG 2021 (Daten modifiziert)";
   Nutzungsbedingungen (DWD/GeoNutzV) für das Einchecken **offen** zu prüfen.
8. **Grenzpunkte DE/AT:** Zugspitze liegt im Layer auf DE-Seite; Innsbruck/Kufstein/Salzburg ohne Treffer.
   Punkte auf der Grenze können DE- und AT-Warnungen gleichzeitig erhalten — erwünscht (beide zuständig).
   Hazard-Dedupe (`base.py:201-225`) nimmt je Hazard nur die Quelle mit höchster Stufe; da DE und AT
   beide `source="meteoalarm"` tragen, kollabieren sie zu einer Quelle, gleiche Zeitfenster kollabieren
   auf die höhere Stufe — Verhalten an Grenzpunkten im Test festhalten.
9. **Registrierungsreihenfolge:** keine funktionale Abhängigkeit zu ZAMG (anders als AT); Gewitter-Tie-Break
   „zuerst registriert gewinnt" (Kommentar `__init__.py:27-31`) betrifft DE nur bei Überschneidung mit DPC.
10. **Multi-User:** unberührt — nationaler Cache ohne Nutzerbezug, Registry global, keine Persistenz je Nutzer.
11. **Fixture:** Rohfeed 5 MB ist zu groß zum Einchecken; Muster IT/AT = Stichprobe < 200 KB unverändert
    kopierter Einträge + README mit Herkunft. Stichprobe sollte `AllClear`, eine `9…`-Zelle, eine Küstenzelle,
    einen Eintrag ohne `expires` und einen Bayerische-Alpen-Kreis enthalten.

---

## Analysis (Phase 2, 2026-09-19)

### Type
Feature (Länder-Ergänzung einer bestehenden Quelle) mit zwei mitgezogenen Korrektheits-Befunden.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["DE"]`, `Literal[...,"DE"]`, `_zone_for_point_de` (Ray-Cast), 3-Wege-Verzweigung in `covers()`/`fetch()` (heute binär AT/sonst, Z. 311-352), Geocode-Art parametrisieren (`_emma_ids_for_alert` Z. 167-176 liest nur `EMMA_ID`; DE über `WARNCELLID`), `responseType` in `_info_entries_from_alert` (Z. 145-164) |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | AllClear-Einträge nicht als aktive Warnung mappen (`_group_and_map_info_entries` Z. 595-644 oder Filter auf Alert-Ebene davor) |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("DE"))` nach AT, vor DPC; Reihenfolge-Kommentar |
| `src/services/official_alerts/base.py` / AT-Zweig | MODIFY (klein) | „nicht zuständig" nach Fetch (ZAMG 404) darf nicht als zuständige, erfolgreiche Quelle zählen — sonst maskiert AT einen DE-Ausfall in Südbayern (s. Risiko 2) |
| `src/services/official_alerts/data/dwd_warngebiete_kreise.json` | CREATE | DWD-Layer `dwd:Warngebiete_Kreise` (402 Flächen, ~0,9 MB, WGS84), Kopf/README mit Quellenvermerk |
| Loader (in `meteoalarm_feed.py` oder eigenes Kleinmodul nach `dpc.py:62-88`) | CREATE | Laden + `geo_ray_cast.py` wiederverwenden, kein neuer Ray-Cast |
| `tests/tdd/test_meteoalarm_feed_deutschland.py` | CREATE | Verhaltenstests gegen aufgezeichnete Fixture |
| `tests/fixtures/meteoalarm_feed/feed_germany_sample.json` + README | CREATE/MODIFY | Stichprobe echter DE-Feed (AllClear, Bayern-Kreis, Küstenzelle ohne `expires`) |
| Drift-Wächter analog `test_dpc_zone_drift.py` | CREATE | WARNCELLIDs im Feed vs. eingecheckte Geometrie |
| IT/AT-Regressionstest AllClear | MODIFY | gemeinsamer Umsetzer ändert sich |

### Scope Assessment
- Files: ~6 Code/Test + 2 Daten
- Estimated LoC: Code ~+120–170; Tests separat
- Risk Level: MEDIUM (Alarmpfad aller vier Kanäle, gemeinsamer Umsetzer IT/AT)

### Technical Approach (Empfehlung)
1. **Zuordnung über `WARNCELLID`** (im Feed 1:1 zu `EMMA_ID`, 290 distinkt) — keine EMMA-Übersetzungstabelle.
2. **Eingecheckte DWD-Kreisgeometrie** + `geo_ray_cast.py`; ADR-0041 Muster A. **Dieselbe** Funktion `_zone_for_point_de` in `covers()` UND `fetch()` — genau diese Divergenz (grobe Bbox in `covers()`, Geometrie in `fetch()`) erzeugte bei IT 39 falsche „nicht abrufbar" auf einer Tour (#1397 S4, Docstring `meteoalarm_feed.py:300-310`).
3. **Küstenzellen (`501…`, 8 Stück) bewusst nicht enthalten** — Known Limitation, für Wanderer irrelevant. Damit ist Risiko 3 strukturell erledigt: alle 32 `info`-Einträge ohne `expires` tragen ausschließlich `WARNCELLID`-Präfix `501` (gemessen 19.09.) und können mangels Geometrie nie einer Zone zugeordnet werden. Kein Eingriff in `filter_alerts_to_window`.
4. **AllClear:** `responseType` ist im Feed eine Liste und je Alert einheitlich (312 AllClear-Infos / 8 Sprachen = 39 Alerts; 1720 Prepare / 8 = 215; Summe 254). Filter auf Alert-Ebene: ein AllClear-Eintrag ist keine aktive Warnung. **Berührt nicht die Entwarnungs-Dringlichkeitsregel aus #2177 (Δ-Alarme, PO 07.09.)** — dort geht es um den Rückgang unserer eigenen Gewitterstufe, hier um Feed-Einträge, die keine aktive Warnung mehr sind. Ob das Aufheben einer amtlichen Warnung aktiv als Entwarnung gemeldet werden soll, ist eine eigene Produktfrage (gilt heute schon für IT/AT: Verschwinden ist still) — nicht Teil dieses Tickets.
5. **Risiko 2 (Südbayern):** `base.py:195` meldet „nicht abrufbar" nur, wenn alle zuständigen Quellen ausfallen. `MeteoAlarmFeedSource("AT").covers()` ist die reine INCA-Bbox (Z. 315-316) und umfasst Südbayern; ZAMG antwortet dort 404 = „nicht zuständig", zählt aber als zuständige, erfolgreiche Quelle. **Mit DE-Registrierung** maskiert das einen DE-Feed-Ausfall genau in den Bayerischen Alpen → Verstoß gegen die Drei-Zustände-Pflicht des Tickets. Entscheidung: **in diesem Ticket** beheben (entsteht erst durch DE), per AC mit Test „DE-Ausfall an bayerischem Punkt ⇒ nicht abrufbar".
6. **TTL bleibt 1800 s / 60 s** (Parität IT/AT). ~240 MB/Tag Bandbreite werden bewusst in Kauf genommen; eine stundenalte amtliche Warnung wäre der größere Schaden. Erfüllt ADR-0039:53 als dokumentierte Entscheidung.
7. **Timeout 15 s bleibt:** gemessen 1,5–2,0 s für 5,5 MB (3 Abrufe, 19.09.) — Faktor ≥7 Reserve.

### Lizenz (Primärquelle geprüft, 19.09.)
- `https://www.dwd.de/copyright`: „Alle frei zugänglichen Geodaten und Geodatendienste … dürfen unter den Bedingungen der Lizenz Creative Commons BY 4.0 (CC BY 4.0) unter Beigabe eines Quellenvermerks weiterverwendet werden."
- Layer-Abstract (WMS GetCapabilities `dwd:Warngebiete_Kreise`): „Copyright GeoBasis-DE / BKG (http://www.bkg.bund.de) 2019 (Daten modifiziert)".
- Pflicht-Quellenvermerk (zweiteilig, wörtlich in Datei-README/Docstring): „Warngebiete: Deutscher Wetterdienst (DWD), CC BY 4.0; Copyright GeoBasis-DE / BKG (http://www.bkg.bund.de) 2019 (Daten modifiziert)".

### Dependencies
- Upstream: `warn_egress` (Cache/Fetch-Status), `geo_ray_cast.py`, `meteoalarm._group_and_map_info_entries`
- Downstream: `trip_alert.py`, `comparison_engine.py`, `compare_official_alert.py`, `trip_report_scheduler.py`, Renderer `official_alerts.py` → alle vier Kanäle

### Open Questions
- keine blockierenden. Produktfrage „aktive Entwarnung bei Aufhebung amtlicher Warnungen" separat.

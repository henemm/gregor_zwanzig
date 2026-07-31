# Context: feat-1427-dpc-fallback

Issue: [#1427](https://github.com/henemm/gregor_zwanzig/issues/1427) — Fallback für amtliche IT-Warnungen: DPC direkt bei MeteoAlarm-Ausfall

## Request Summary

MeteoAlarm ist unsere einzige Quelle amtlicher Warnungen für Italien und ist fremd
kontingentiert (Tageslimit real ~160 Abrufe, schon einmal gesprengt → #1397). Gesucht
ist eine Rückfallebene: Direktabruf der italienischen Zivilschutzbehörde (DPC), die
**nur** greift, wenn MeteoAlarm fehlschlägt — nicht als parallele Zweitquelle.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/services/official_alerts/base.py` | Registry + Abfrage-Schleife (`get_official_alerts_with_status`, Z. 120–146). **Hier müsste die Fallback-Semantik entstehen — heute gibt es sie nicht.** Cross-Source-Partitionierung Z. 155–172 |
| `src/services/official_alerts/__init__.py:24-28` | Registrierungs-Reihenfolge (Tie-Break-relevant): Vigilance → MeteoForets → MassifClosure → GeoSphereWarn → MeteoAlarm |
| `src/services/official_alerts/meteoalarm.py` | Abzulösende Quelle. `covers()` Z. 1001–1029 (BBox-Vorfilter IT via `_DPC_*`), `fetch()` Z. 1030–1076 (strikt fail-soft `[]`), `_TYPE_HAZARD_MAP` Z. 473–482, `_MeteoAlarmBudgetExhausted` Z. 135–149 (`self_throttled`) |
| `src/services/official_alerts/warn_egress.py` | Einziger Ort, der den echten Ausgang eines Abrufs kennt: `cached_fetch()` Z. 257, `_record_fetch_failure()` Z. 60, `observe_fetch_failure()` Z. 85, `mark_fetch_incomplete()` Z. 69. **Der Auslöser für einen Fallback muss hier abgegriffen werden** |
| `src/services/official_alerts/meteoalarm_budget.py` | Tageskontingent-Gate (`allow()` Z. 96, Default 100/Tag Z. 66) — selbst auferlegter Rückzug, von außen heute nicht von echtem Ausfall unterscheidbar |
| `src/services/official_alerts/geo_ray_cast.py` | `_point_in_ring(lat, lon, ring)` Z. 12 — flache `(lon, lat)`-Liste, ein Ring, keine Holes/MultiPolygon. Für Shapefile-Ringe nach Konvertierung nutzbar |
| `src/services/official_alerts/models.py:20` | `OfficialAlert.source` — trägt die Herkunft |
| `src/output/renderers/alert/official_alerts.py:89-124` | `_SOURCE_LABELS` + `official_alert_source_label()` — **kein DPC-Eintrag vorhanden**, Herkunfts-Fußzeile Z. 1242–1255 |
| `src/providers/radar_dpc.py` | Bestehende DPC-Anbindung (anderes Produkt: SRI-Radar). Wiederverwendbar: Retry-Konstanten Z. 39–42, `_is_retryable_error()` Z. 49–55. **Kein Cache, kein Zip-Handling** |
| `src/services/radar_service.py:48-51` | `_DPC_LAT/LON_MIN/MAX` = 36.0/47.5/6.5/19.0 — vorhandene Italien-BBox |

## Existing Patterns

- **Quellen-Protokoll:** `OfficialAlertSource` = `name` / `covers(lat, lon)` / `fetch(lat, lon) -> list[OfficialAlert]`, fail-soft (wirft nie). Eine neue Quelle ist strukturell billig.
- **Cache-Baustein für Warnquellen:** `warn_egress.cached_fetch()` (TTL für Erfolg *und* Fehler, 429-Backoff, Egress-Zähler). Vorbild-Aufrufer: `geosphere_warn._get_cached_warnings()` Z. 68, `vigilance.py:81`, `massif_closure.py:96`. **Nicht** `radar_dpc.py` — das hat gar keinen Cache.
- **Nicht-Kaschieren (ADR-0018):** Jedes Ausweichen muss in den Daten markiert, protokolliert und im Health-Aggregat sichtbar sein. Gilt ausdrücklich als Folgepflicht für *neue* degradierbare Datenpfade.
- **Herkunfts-Fußzeile (ADR-0034):** Zeile 2 nennt die reale Datenquelle, nie „unknown". Ein Fallback-Abruf muss also ohnehin als DPC ausgewiesen werden.
- **„Nicht abrufbar" ≠ „keine Warnungen" (#1348):** `get_official_alerts_with_status()` liefert `unavailable`, die Mail zeigt einen Hinweis. Ein greifender Fallback verändert genau diesen Zustand.

## Dependencies

- **Upstream:** `warn_egress` (Abruf/Cache/Fehlersignal), `radar_service`-BBox-Konstanten, `geo_ray_cast`, `httpx`, `zipfile` (Standardlib), Shapefile-Parsing (**keine Bibliothek im Projekt**)
- **Downstream:** alle 37 Aufrufer von `get_official_alerts_for_location()` (u.a. `trip_alert.py`, `compare_official_alert.py`, `comparison_engine.py`, `trip_report_scheduler.py`), Mail-/SMS-/Telegram-Renderer über `official_alert_source_label()`

## Existing Specs & ADRs

- `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md` — der akute Auslöser (Verbrauch 160 → 84/Tag)
- `docs/specs/modules/warn_unavailable_hint.md` (#1348) — „nicht abrufbar"-Hinweis
- `docs/specs/modules/fix_1422_warn_ausfall_alarm.md` (#1422, gerade live) — `WarnServiceHealth()` macht Ausfälle maschinenlesbar
- `docs/specs/modules/warn_service_consumption.md` — Ursprung `warn_egress`/Journal-Schema
- `docs/specs/modules/radar_nowcast_italy_arpae_fallback.md` — einzige bestehende Fallback-Kette (andere Domäne)
- **ADR-0016** (amtliche Warnungen = additiver Typ), **ADR-0018** (Fallback ohne Kaschieren), **ADR-0034** (Herkunftsfußzeile)

## Live-Befunde zur Datenquelle (selbst geprüft 2026-07-31, 04:57 UTC)

`https://raw.githubusercontent.com/pcm-dpc/.../files/all/latest_all.zip` → HTTP 200,
4,6 MB, kein Auth, `ETag` vorhanden (⇒ `If-None-Match` möglich), `cache-control: max-age=300`.

Inhalt: je ein Shapefile-Satz `<YYYYMMDD>_<HHMM>_today.*` und `..._tomorrow.*`,
dazu `Cap_*.xml`, PDF, README.

- **Geometrie:** 187 Zonen, CRS laut `.prj` = **GCS_WGS_1984 (lon/lat)** — *keine*
  Umprojektion nötig (anders als beim DPC-Radar).
- **Attribute (DBF):** `Zona_all` (Code, z.B. `Abru-A`), `Nome_zona`, `Criticita`,
  `Idrogeo`, `Temporali`, `Idraulico` — **kein `Comuni`-Feld**, obwohl das README es
  behauptet (README ≠ Wirklichkeit).
- **Stufen als Freitext**, keine Codes. Im Beispieltag nur drei Ausprägungen:
  `Assenza di fenomeni significativi prevedibili / NESSUNA ALLERTA`,
  `Ordinaria / ALLERTA GIALLA`, `Ordinaria per rischio temporali / ALLERTA GIALLA`.
  Muster `<Kritikalität> / ALLERTA <Farbe>` ⇒ Farbe ist der belastbare Anker.
- **`Cap_*.xml` ist ein Kurz-Bulletin** (hier 1 KB, ein `<info>`-Block mit `onset`/
  `expires`/`areaDesc`/Zonencode) — nennt nur *gewarnte* Zonen, ohne Geometrie. Die
  Shapefile-Attribute allein reichen bereits aus.

## Risks & Considerations

1. **🔴 Tagesversatz — die gefährlichste Falle.** Um 04:57 UTC am 31.07. enthielt
   „latest" das Bulletin von **30.07. 15:11**. Darin ist `today` = 30.07. (gestern)
   und `tomorrow` = 31.07. (heute). Wer naiv `today.shp` liest, zeigt morgens die
   Warnlage von **gestern**. Der Bezugstag muss aus dem Dateinamen-Zeitstempel
   abgeleitet werden.
2. **🔴 Zwei von drei Risikoarten haben kein Ziel-Vokabular.** `temporali` →
   `thunderstorm` passt. `idrogeologico` und `idraulico` sind Hochwasser/Erdrutsch —
   `_TYPE_HAZARD_MAP` mappt `flood` (MeteoAlarm-Typ 11) **bewusst nicht**. Entweder
   deckt der Fallback nur Gewitter ab (dünn) oder es braucht eine neue Gefahren-
   Kategorie, die bis in Mail-/SMS-Renderer und Alarm-Konfiguration reicht.
3. **🟠 Fallback-Semantik existiert bei amtlichen Warnungen nicht.** `base.py` fragt
   *immer alle* abdeckenden Quellen ab; die Konkurrenz wird erst danach über „beste
   Quelle je Gefahr" aufgelöst. „Nur bei Ausfall von A" ist ein **neues Muster** →
   Entscheidungsfläche, ADR-Prüfung nötig (Issue benennt das selbst).
4. **🟠 Registriert man DPC als normale 6. Quelle, kollidiert sie mit MeteoAlarm** —
   beide re-publizieren dieselben Rohdaten, die Partitionierung würde je Gefahr eine
   davon willkürlich verwerfen. Genau das darf nicht passieren.
5. **🟠 Auslöser sauber abgreifen.** Budget-Rückzug (`self_throttled`) und echter
   Anbieter-Ausfall sind heute von außen ununterscheidbar. Für einen Fallback ist die
   Unterscheidung womöglich egal (beide Male fehlen Daten) — muss aber entschieden
   und mit `WarnServiceHealth()` (#1422) verträglich sein.
6. **🟠 Neue Abhängigkeit vs. Projektmuster.** Es gibt **keine** Shapefile-Bibliothek
   (`pyshp`/`fiona`/`shapely` fehlen), und die bestehende Polygon-Logik ist bewusst
   dependency-frei. Entweder `.shp` mit Standardlib parsen oder erstmals eine
   Geo-Bibliothek aufnehmen. Präzedenz: `rasterio` (#1162) löste beim Deploy einen
   `uv sync`-Rebuild aus, der Staging 14 Min lahmlegte.
7. **🟡 Abdeckungslücke.** DPC deckt nur „heute + morgen", 1×/Tag aktualisiert. Kein
   rollierendes Fenster wie MeteoAlarm. Reicht das als Rückfallebene? (Offene Frage
   im Issue — PO-Entscheid nötig.)
8. **🟡 Übersetzung.** DPC liefert nur Italienisch; MeteoAlarm lieferte deutschen
   CAP-Text. ~12 feste Textbausteine (3 Risikoarten × 4 Stufen, „Rossa" fehlt bei
   `temporali`) müssen selbst übersetzt werden.
9. **🟡 4,6 MB je Abruf.** Egress-Budget beachten (`warn_egress`); `ETag`/
   `If-None-Match` und ein Tages-Cache drängen sich auf, da sich die Datei nur
   1×/Tag ändert.

## Offene Fragen für Analyse/Spec

- Deckt der Fallback nur `thunderstorm` ab, oder wird eine Hochwasser-Kategorie neu
  eingeführt? (bestimmt den Umfang maßgeblich)
- Genügt „heute + morgen" als Rückfall-Qualität?
- Wie wird die Fallback-Herkunft dem Nutzer gezeigt — reicht die bestehende
  Herkunfts-Fußzeile (ADR-0034) mit neuem Label „Protezione Civile (DPC)"?
- Shapefile-Parsing: Standardlib oder neue Abhängigkeit?

---

## Analysis

### Type

Feature (neue Rückfallebene). Kein Bug — der aktuelle Ausfall ist gewolltes
Schutzverhalten, kein Defekt.

### Belegte Ausgangslage (Messung 2026-07-31, 05:15 UTC)

| Warndienst | heute OK | heute Fehlschlag |
|---|---:|---:|
| `meteoalarm` | **0** | **322** |
| `geosphere_warn` | 161 | 0 |
| `vigilance` | 49 | 0 |
| `meteo_forets` | 49 | 0 |
| `massif_closure` | 49 | 0 |

- Letzter MeteoAlarm-Erfolg: **30.07. 14:00 UTC**. Ursache laut Journal
  `self_throttled: True` — das eigene Budget-Gate (`meteoalarm_budget.json`,
  `observed_reset_ts` = 31.07. 14:00 UTC) nach einer echten 429-Sperre.
  ⇒ **~24 h Totalausfall amtlicher Warnungen**, davon 15 h verstrichen.
- AT bleibt über GeoSphere abgedeckt, **IT ist in diesem Fenster blind**.
- Betroffene Echtdaten: Tour `KHW 403` (Karnischer Höhenweg, Nutzer `henning`),
  Punkte u.a. 46.7248/12.2254 und 46.7178/12.3265. Beide von GeoSphere live mit
  HTTP 404 „Could not find municipal for coords" abgelehnt ⇒ italienische Seite,
  MeteoAlarm ist dort die **einzige** Quelle.

### 🔴 Zentrale Einschränkung: DPC ist ein TEIL-Fallback

Das DPC-Bulletin ist ein *Zivilschutz-Kritikalitätsbulletin*, kein allgemeines
Wetterwarnungs-Bulletin. Es kennt **genau drei** Risikoarten: `Idrogeo`
(hydrogeologisch — Sturzflut/Erdrutsch), `Idraulico` (Hochwasser), `Temporali`
(Gewitter). **Hitze, Wind, Schnee, Kälte, Waldbrand kommen darin überhaupt nicht
vor.** DPC kann MeteoAlarm für Italien also niemals vollständig ersetzen.

Davon ist heute nur `Temporali` → `thunderstorm` im App-Vokabular abbildbar.
`Idrogeo`/`Idraulico` hätten kein Ziel (MeteoAlarm-Typ 11 `flood` ist bewusst
nicht gemappt). **Ohne neue Kategorie deckt der Fallback genau eine von drei
verfügbaren Risikoarten ab.**

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/official_alerts/dpc.py` | CREATE | Neue Quelle: Zip laden, DBF lesen, Bezugstag aus Dateinamen, Zone→Stufe |
| `src/services/official_alerts/data/dpc_zones.json` | CREATE (generiert) | 187 Zonen-Polygone, offline extrahiert — Muster `massif_polygons.json`. Zählt nicht zum LoC-Limit |
| `src/services/official_alerts/base.py` | MODIFY | Zweiter Schleifendurchlauf (Fallback), Namens-Buchhaltung statt reinem `failed`-Zähler, `unavailable`-Korrektur |
| `src/services/official_alerts/__init__.py` | MODIFY | Registrierung mit `fallback_for="meteoalarm"` |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `_SOURCE_LABELS` += „Protezione Civile (DPC)" |
| `src/output/tokens/hazard_symbols.py` | MODIFY (nur Variante B) | Neue Gefahrenart im SSOT-Katalog |
| `src/output/renderers/email/compare_html.py` | MODIFY (nur Variante B) | `_warn_short()` — einziges hartkodiertes if/elif (sonst Bug-Muster #1239) |
| `src/services/official_alerts/meteoalarm.py` | MODIFY (nur Variante B) | `_TYPE_HAZARD_MAP[11] = "flood"` — damit die Kategorie auch im Normalbetrieb existiert |
| Tests | CREATE | Aufgezeichnete DPC-Fixtures (Zip/DBF), Fallback-Pfad, `unavailable`-Rücknahme |

### Technical Approach (empfohlen)

1. **Geometrie offline, Stufen zur Laufzeit.** Zonen-Polygone einmalig extrahieren
   und als `data/dpc_zones.json` einchecken (etabliertes Muster, zweimal im Repo
   angewandt); Punkt-in-Fläche über das vorhandene `geo_ray_cast._point_in_ring`.
   **Keine neue Geo-Abhängigkeit** — `rasterio` (#1162) legte beim Deploy Staging
   14 Min lahm, dieser Präzedenzfall wird nicht wiederholt.
2. **Laufzeit liest die DBF, nicht die CAP-XML.** Die CAP-Probe war zwar im
   Stichprobentag vollständig, aber das war ein Tag mit *einer* gewarnten Zone —
   zu dünn als Beleg. Die DBF trägt garantiert alle 187 Zonen.
3. **Bezugstag aus dem Dateinamen-Zeitstempel ableiten**, nie `today.dbf` blind
   verwenden (Tagesversatz-Falle).
4. **Egress:** `warn_egress.cached_fetch()` mit TTL + `If-None-Match`/`ETag`
   (Bulletin ändert sich ~1×/Tag ⇒ sonst 304). Range-Reads auf das ZIP-Ende sind
   vorzeitige Optimierung und entfallen.
5. **Fallback-Mechanik:** optionales `fallback_for` am `OfficialAlertSource`-
   Protocol (strukturelles Subtyping ⇒ Bestandsquellen unverändert) + zweiter
   Schleifendurchlauf in `get_official_alerts_with_status()`, **vor**
   `filter_alerts_to_window` und vor der Zwei-Pass-Partitionierung. Dadurch
   stehen DPC und MeteoAlarm nie gleichzeitig in `results` — die
   „beste Quelle je Gefahr"-Partitionierung bleibt unangetastet.
6. **Nicht kaschieren (ADR-0018):** greifender Fallback setzt `unavailable`
   zurück, wird aber in der Herkunftsfußzeile (ADR-0034) und im Journal
   ausgewiesen.

### Scope Assessment

- Risiko: **MEDIUM** — `base.py` hat 37 Aufrufer, der Vertrag bleibt aber nach
  außen unverändert; Regressionsdruck liegt auf 6 Wächter-Tests
  (`test_official_alerts_unavailable_hint.py`, `test_meteoalarm_source.py:1440/1511`,
  `test_meteoalarm_index_coverage.py:466/692/705/713`, `test_sms_trip_unavailable_marker.py:178`).
- **Über dem 250-LoC-Limit** ⇒ zwei Scheiben, jede für sich auslieferbar:

| Scheibe | Inhalt | LoC (Produktiv/Test) | Nutzen für sich allein |
|---|---|---|---|
| **S1** | Neue Gefahrenart „Hochwasser/Erdrutsch" im SSOT-Katalog + deutsches Label + `compare_html._warn_short()` + `_TYPE_HAZARD_MAP[11]="flood"` bei MeteoAlarm | ~25–40 / ~40 | **Sofort:** MeteoAlarm-Hochwasserwarnungen kommen im Normalbetrieb an, statt still verworfen zu werden |
| **S2** | Generische Rückfall-Mechanik in `base.py` (`fallback_for`, zweiter Durchlauf, `unavailable`-Buchhaltung), geprüft mit Test-Dummy-Quelle | ~80–120 / ~60 | Wiederverwendbares Muster; ohne echte Fallback-Quelle **kein** Produktivverhalten geändert |
| **S3** | DPC-Quelle: `dpc.py`, `dpc_zones.json`, Label, Registrierung mit `fallback_for="meteoalarm"`, Mapping `Temporali`→`thunderstorm`, `Idrogeo`/`Idraulico`→`flood` | ~120–160 / ~120 | Das eigentliche Versprechen von #1427 |

Reihenfolge zwingend S1 → S2 → S3: S3 braucht die Gefahrenart aus S1 und die
Mechanik aus S2. Jede Scheibe bleibt unter dem 250-LoC-Limit.

### Dependencies

Keine neuen Pakete. Standardlib `zipfile`/`struct`/`xml.etree`, vorhandenes
`httpx`, `warn_egress`, `geo_ray_cast`, `radar_service`-BBox-Konstanten.

### ADR-Entscheidung

**Neues ADR nötig.** Erste amtliche Warnquelle, die nicht additiv, sondern
**primär/sekundär** ist — struktureller Bruch mit der Registry-Annahme aus
ADR-0016 und mit der „beste Quelle je Gefahr"-Partitionierung. Titel-Vorschlag:
*„Fallback-Quellen für amtliche Warnungen — sekundär statt additiv, nur bei
Primärausfall"*. Festzuhalten: (a) zweistufige Abfrage, (b) kein Wettbewerb über
die Partitionierung, (c) `unavailable` wird bei erfolgreichem Fallback
zurückgenommen, (d) Fallback-Nutzung bleibt sichtbar (ADR-0018/0034, #1422).

### Nebenbefund (nicht Teil von #1427)

`_TYPE_HAZARD_MAP` (`meteoalarm.py:473-482`) verwirft die MeteoAlarm-Typen 4
(Nebel), 7 (Küste), **9 (Lawine)** und 11 (Hochwasser) stillschweigend. In den
aufgezeichneten Echtdaten liegt mit `tests/fixtures/meteoalarm/cap_avalanche_plus_heat.xml`
eine reale Lawinenwarnung, die dadurch nie beim Nutzer ankommt — für ein
Wander-Sicherheitswerkzeug potenziell relevantes Fehlverhalten. Kandidat für ein
eigenes Issue (Triage-Kriterium a: nutzersichtbar).

### Open Questions

- [x] **PO-Entscheid 2026-07-31: Variante B.** Neue Warnart „Hochwasser/Erdrutsch"
      wird eingeführt, und zwar **dauerhaft** — nicht nur im Notbetrieb. Damit
      deckt der Fallback alle drei DPC-Risikoarten ab, und MeteoAlarm-Typ 11
      (`flood`) wird im Normalbetrieb ebenfalls sichtbar (heute verworfen).
      Konsequenz für den Zuschnitt: eigene erste Scheibe, s.u.
- [x] „heute + morgen" als Rückfall-Qualität — angenommen: ja, mehr gibt DPC
      strukturell nicht her; im Ausfallfenster besser als nichts.
- [x] Transparenz-Hinweis — angenommen: ja, über die bestehende
      Herkunftsfußzeile (ADR-0034 verlangt es ohnehin).
- [x] Shapefile-Abhängigkeit — entschieden: keine, Geometrie offline extrahiert.

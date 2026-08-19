# Context: 1506-s5b-ruc-hagel

## Request Summary

Issue #1506 (S5b zu #1475, Epic #1419, `session:gewitter`), am 2026-08-19 umbetitelt auf "Hagel-Kennzeichen über ICON-D2-RUC (DE/Alpen)". Ursprünglicher Weg (`hail_potential_grau_gsp`-Schwelle) ist laut Vorrecherche (Issue-Kommentare 2026-08-05/2026-08-07) endgültig tot: `GRAU_GSP` ist im operationellen Ein-Momenten-ICON-D2 physikalisch kein Hagelmaß, das Modell kennt keine Hagelkategorie. Neuer Weg laut Issue: `ICON-D2-RUC` (Zwei-Momenten-Schema, Seifert & Beheng, seit 2024-07-12 operationell) führt echte Hagelfelder (`DEMAX_HAIL_S`, `HAIL_GSP`, `KE_HAIL_S` u.a.), frei verfügbar unter `opendata.dwd.de/weather/nwp/v1/m/icon-d2-ruc/p/`.

**Ziel dieser Context-Phase:** Machbarkeit klären, bevor eine Spec entsteht — insbesondere, ob die bestehende Provider-Infrastruktur (GDAL/rasterio, kein neues GRIB-Toolkit, #1143) das RUC-Gitter überhaupt lesen kann.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/dwd.py:41,58` | Bestehender `de_direct`-Provider für reguläres ICON-D2. `BASE_URL = "https://opendata.dwd.de/weather/nwp/icon-d2/grib/"` (regulärer Pfadbaum, NICHT `icon-d2-ruc`). Decoder: `rasterio.io.MemoryFile` (GDAL-GRIB-Treiber) |
| `src/providers/dwd.py:4-8` | Docstring, explizite Design-Entscheidung: „liest die entpackten GRIB2-Antworten mit dem bereits im Projekt vorhandenen `rasterio`/GDAL-GRIB-Treiber (keine neue Dependency, #1143)" |
| `src/providers/dwd.py:194-203` (`_build_url`) | URL-Muster erwartet `icon-d2_germany_regular-lat-lon_single-level_...` — reguläres Rechteckgitter |
| `src/providers/dwd.py:208-245` (`_read_point_value`) | Kernmechanik: `dataset.index(lon, lat)` auf Basis der Affine-Georeferenzierung, dann `dataset.read(1)[row, col]`. Funktioniert nur auf regulären/projizierten Rastern mit Affine-Transformation |
| `src/app/models.py:161` | `hail_potential_grau_gsp: Optional[float] = None` — Rohwert-Feld, bislang kein Abnehmer |
| `src/app/models.py:205,496` | `hail_flag: Optional[bool] = None` in `ForecastDataPoint` und im Summary-Objekt |
| `src/providers/openmeteo.py:442-454,688` (`_parse_hail_flag`) | Einziger heute aktiver Befüller von `hail_flag`, aus Open-Meteo `wmo_code` (96/99) |
| `src/output/metric_format.py:557-572` (`hail_priority`) | Aggregationsregel: ja > unbekannt > nein, erwartet rohe (ungefilterte) Werte inkl. `None` |
| `src/output/metric_format.py:579` | `format_hail_note()` referenziert ADR-0007 (keine Handlungsempfehlung) explizit |
| `src/services/weather_metrics.py:1326-1338` (`aggregate_stage`) | Vorfilter-Umgehung für `hail_priority` bereits umgesetzt (S5a-Commit `2a72175b`) — Kommentar referenziert explizit S5a/S5b/S5c. Die im Issue-Text genannte "Known Limitation 3" ist damit bereits erledigt, unabhängig vom RUC-Weg |
| `src/providers/thunder_routing.py:26-35,60-64` | `_ThunderRegion` mit additivem `zusatzquellen`-Feld; `DE_ALPEN` trägt bereits `("geosphere",)` als Zusatzquelle neben `de_direct` |
| `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` | S5a-Spec (334 Zeilen, `status: draft`). Datenmodell: `True`=ja (WMO bestätigt), `None`=unbekannt (WMO kann nicht verneinen), `False`=nein — in S5a strukturell unerreichbar, "reserviert für S5b/S5c, sobald eine Quelle existiert, die ein echtes Nein liefert" |
| Downstream-Renderer | `sms_trip.py`, `compact_summary.py`, `narrow.py`, `comparison.py`, `email/outlook.py`, `email/helpers.py`, `email/compare_html.py`, `trip_report.py`, `tokens/dto.py`, `tokens/builder.py`, `trip_command_processor.py`, `trip_report_scheduler.py` — alle über `hail_priority()`/`format_hail_note()`, keine Kanal-eigene Zweitlogik |

## Existing Patterns

- **Additive Zusatzquelle je Region statt Ersatz der Primärquelle** (ADR-0057, #1758): `DE_ALPEN` bekommt GeoSphere als zweite Gewitter-Signalquelle neben `de_direct`, mit eigenem Gitter-Zuständigkeitscheck und eigenem (kurzem) Zeitbudget statt des vollen Retry-Backoffs. Direktes strukturelles Vorbild für "RUC als Zusatzquelle neben `de_direct`, nur für DE/Alpen".
- **Kein neues GRIB-Toolkit** (#1143, `dwd.py:4-8`): bewusste Architekturentscheidung, ausschließlich `rasterio`/GDAL zu nutzen statt eccodes/cfgrib. Bislang unangefochten, weil alle bisherigen DWD-/AROME-Quellen reguläre oder projizierte Raster liefern.
- **Model-/Region-Eichtabelle statt globaler Konstante** (`model_registry.CAPE_THRESHOLDS_JKG`, ebenfalls Vorbild in `docs/context/gewitter-1679-lpi-schwellen.md`): fehlender Eintrag → `None` = "nicht belegt", nie ein geratener Ersatzwert.

## Dependencies

- **Upstream:** #1475 S5a (Datenmodell/Renderer-Struktur für `hail_flag` existiert bereits, produktiv seit Commit `2a72175b`).
- **Nicht Teil dieses Workflows:** S5c (Météo-France FR/Korsika) ist eine separate Scheibe.
- **Downstream:** breite Fächerung aller Ausgabekanäle (s. Related Files), aber ausschließlich über den bereits gehärteten `hail_priority()`/`format_hail_note()`-Pfad — keine neue Downstream-Arbeit erwartet, nur ein zusätzlicher Befüller wie bei `openmeteo.py`.

## Existing Specs

- `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` — S5a-Spec, `status: draft`, keine dedizierte S5b-Spec vorhanden.
- `docs/adr/README.md` — relevante ADRs:
  - **ADR-0057** (akzeptiert 2026-08-18): mehrere Gewitter-Signalquellen je Gebiet, additiv, eigenes Gitter, eigenes Zeitbudget, fail-soft — direktes Vorbild.
  - **ADR-0047**: Gewitter-Vertretung zwischen Direktquellen bei echtem Ausfall — laut ADR-0057 bewusst NICHT auf additive Zusatzquellen angewendet, hier nicht einschlägig.
  - **ADR-0025**: eine Gewitter-Quelle je Konsum-Ebene (`dp.thunder_level`) — betrifft nicht die Beschaffungsseite, mit ADR-0057 vereinbar.
  - **ADR-0018**: Provider-Fallback ohne Kaschieren — allgemeines Prinzip für neue Anbindungen.
  - **ADR-0007**: keine Handlungsempfehlung, rein deskriptiv — bindend für jedes neue Hagel-Feature, unverändert.
  - Kein ADR erwähnt bislang `icon-d2-ruc` oder ein Dreiecksgitter — Neuland.
- `docs/reference/decision_matrix.md`: kein Eintrag zu `icon-d2-ruc` oder einem Dreiecksgitter-Provider.

## Risks & Considerations — 🔴 zentraler Befund dieser Phase

**Empirisch verifiziert (2026-08-19, eigene Messung, kein Mock):** Eine echte RUC-Datei (`DEMAX_HAIL_S`, Lauf 2026-08-19T14:00Z, `PT003H00M.grib2`, 68 853 Bytes) und die zugehörige Gitter-Geometriedatei (`CLAT`, gleicher Lauf, 585 941 Bytes) wurden vom DWD-Open-Data-Server geladen und mit dem produktiven `rasterio`-Decoder geöffnet:

```
RasterioIOError: ... is a grib file, but no raster dataset was successfully identified.
```

Bei **beiden** Dateien identisch. Das bestätigt die vorab vermutete Ursache: ICON-D2-RUC liegt auf dem **nativen Dreiecksgitter** (unstructured/icosahedral), nicht auf einem regulären oder projizierten Raster. GDAL/rasterios GRIB-Treiber erkennt die Datei als GRIB, kann aber keine Rasterstruktur daraus ableiten — exakt die Einschränkung, die in `dwd.py:4-8` (#1143) durch die bewusste Wahl "kein neues GRIB-Toolkit" bislang nie getestet wurde, weil sie nie gebraucht wurde.

**Weitere verifizierte Fakten:**
- `eccodes` ist weder im System-Python noch im Projekt-`uv`-Venv installiert (`ModuleNotFoundError`), `wgrib2`/`gdalinfo`-CLI ebenfalls nicht vorhanden. `pyproject.toml` führt einzig `rasterio>=1.4.4` als Geo-Lib.
- Der DWD-Server stellt **eigene Gitter-Geometriedateien** bereit (`CLAT/`, `CLON/` je Zeitschritt im selben Pfadbaum) — das bestätigt strukturell, dass ein unstructured Grid vorliegt: Bei einem regulären Raster bräuchte es keine separate Lat/Lon-pro-Zelle-Datei, die Georeferenzierung stünde direkt im Grid-Definitions-Header.
- Konsequenz für die Punktabfrage: Eine Standort-Anfrage (`lat, lon`) kann nicht mehr per `dataset.index(lon, lat)` (Affine-Transformation, O(1)) aufgelöst werden, sondern bräuchte einen **Nearest-Neighbor-Lookup** gegen die (potenziell sehr große) Liste der Zellmittelpunkte aus `CLAT`/`CLON` — ein strukturell anderer, aufwändigerer Mechanismus als der bestehende `_read_point_value()`.

**Bewertung:** Das ist kein Nebenbefund, sondern der zentrale Blocker für den bislang angenommenen Umfang. Um RUC-Daten überhaupt zu dekodieren, wäre mindestens eine der folgenden Optionen nötig:
1. **eccodes/cfgrib als neue Dependency** — widerspricht der dokumentierten #1143-Entscheidung "keine neue GRIB-Bibliothek" und bringt eine native System-Bibliothek (`libeccodes`) ins Deploy (Staging + Prod Systemd-Services), nicht nur ein Python-Paket.
2. **Eigener, minimaler GRIB2-Parser** für Template "unstructured grid" — deutlich mehr Code, höheres Fehlerrisiko, keine Wiederverwendung von GDAL-Härtung.
3. **Vorprozessierte/reprojizierte Variante** vom DWD beziehen, falls es eine gibt (bislang nicht recherchiert/nicht gefunden im Pfadbaum) — noch offen.

Zusätzlich unverändert aus der Issue-Recherche: `DEMAX_HAIL_S` ist laut DWD-Dokumentation intern durch **unveröffentlichte** Namelist-Schwellen begrenzt — ein `0`/niedriger Wert heißt "nichts oberhalb der internen Modell-Erkennungsgrenze", nicht "kein Hagel". Selbst nach gelöster Dekodierfrage bliebe die fachliche Aussagekraft von `DEMAX_HAIL_S`/`HAIL_GSP` unbelegt in dem Sinne, dass es (anders als bei WMO-Codes) keine veröffentlichte Schwelle Wert→ja/nein gibt — nur die physikalische Einheit (Durchmesser mm) passt zur DWD-Hagel-Definition (>5mm Korndurchmesser).

## Analysis

### Type
Feature — aber mit einer nicht-trivialen technischen Unsicherheit, die den ursprünglich angenommenen Umfang ("ein weiteres Kennzeichen wie `hail_flag` in S5a") strukturell sprengt: es handelt sich um eine **neue Provider-Klasse** (Dreiecksgitter statt Raster), nicht um eine Erweiterung des bestehenden Raster-Provider-Musters.

### Scope Assessment (grob, vorläufig — abhängig von der Dekodier-Entscheidung)
- Mit eccodes: neue System-Dependency (Staging+Prod-Deploy-Änderung), neuer Nearest-Neighbor-Lookup-Mechanismus, Caching der Gitter-Geometrie (CLAT/CLON ändert sich nur bei Modell-Updates, nicht pro Lauf — muss NICHT pro Request geladen werden), neuer Provider ähnlich `dwd.py` aber strukturell verschieden genug für eine eigene Datei. Deutlich über dem 250-LoC-Workflow-Limit für eine einzelne Slice — voraussichtlich mehrere Scheiben nötig (Grid-Infrastruktur separat von der eigentlichen Hagel-Ableitung).
- Risk Level: **HIGH** — neue Systemabhängigkeit, unklare Datenqualität (unveröffentlichte interne Schwellen), Architekturentscheidung (#1143) müsste explizit revidiert werden (ADR-Pflicht laut CLAUDE.md: Provider-Änderungen sind eine "Entscheidungsfläche").

### Open Questions (PO-relevant, nicht mehr rein technisch)
- [ ] Ist eine neue System-Dependency (`libeccodes` + `eccodes`/`cfgrib`-Python-Paket) auf Staging/Prod akzeptabel? Das widerspricht der bisherigen expliziten #1143-Entscheidung — bräuchte ein neues ADR ("Abgelöst durch", CLAUDE.md-Pflicht).
- [ ] Rechtfertigt der Nutzen (ein zusätzliches `ja`/`nein`/`unbekannt`-Kennzeichen für DE/Alpen, dessen `nein`-Aussagekraft durch unveröffentlichte interne DWD-Schwellen ohnehin unsicher bleibt) diesen Mehraufwand — oder ist der Aufwand/Ertrag ungünstig genug, um erneut zurückzustellen?
- [ ] Falls ja: eigenes Scheiben-Konzept nötig (mind. 2 Scheiben — Grid-Infrastruktur/Dekodierung zuerst, Hagel-Ableitung danach), keine einzelne S5b-Slice mehr.

## Nächster Schritt

Kein direkter Übergang zu `/20-analyse`/`/30-write-spec` ohne PO-Entscheidung: Die Machbarkeitsprüfung hat einen Architektur-Konflikt aufgedeckt (#1143 vs. neue GRIB-Dependency), der über den bisherigen Slice-Zuschnitt hinausgeht. Der PO muss entscheiden, ob der Mehraufwand (neue System-Dependency, ADR-Revision, mehrteiliges Vorhaben) angesichts der weiterhin unsicheren fachlichen Aussagekraft von `DEMAX_HAIL_S` gerechtfertigt ist.

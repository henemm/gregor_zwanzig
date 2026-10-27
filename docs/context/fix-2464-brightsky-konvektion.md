# Context: fix-2464-brightsky-konvektion

## Request Summary
Radar-Nowcast in Deutschland (BrightSky/RADOLAN) erkennt nie Gewitter/Hagel, weil `_fetch_brightsky` keinen Konvektions-Sidecar hat (INCA und Korsika haben einen). Ticket #2464 (PO-Entscheid 2026-09-30, aus Analyse #1443).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/radar_service.py:770-805` | `_fetch_frames_with_fallback`: DE (`_within_radolan`) -> BrightSky zuerst, Rueckgabe Label "radar" |
| `src/services/radar_service.py:807-817` | `_fetch_brightsky`: Offline-Fixture -> `[]`, sonst `BrightSkyProvider().fetch_radar`; KEIN Sidecar |
| `src/services/radar_service.py:819-852` | `_fetch_geosphere_inca`: Muster Sidecar (`_fetch_openmeteo_15` best_match + `_merge_convective`, sonst `_convective_checked=False`) |
| `src/services/radar_service.py:854-875` | `_fetch_corsica_arome_fr`: gleiches Muster mit ARPAE-Sidecar (#1761) |
| `src/services/radar_service.py:877-886` | `_merge_convective`: naechster Sidecar-Frame <=5 min |
| `src/services/radar_service.py:913-` | `_fetch_openmeteo_15`: einziger Open-Meteo-Funnel, Budget-Gate (`allow`/`record_call`), Offline-Fixture, `weather_code` -> `is_convective`/`hail` |
| `src/providers/brightsky.py:90-118` | Parser `precipitation_5` -> `RadarFrame(precip_mm_h)`; setzt nie `is_convective`/`hail` |
| `src/services/trip_alert.py:2166` | Akut-Override #1310 (haengt an Radar-`is_convective`) |
| `src/providers/thunder_enrichment.py:266` | Gewitter-Hebung #1759 |
| `tests/tdd/test_feature_656_radar_nowcast.py:98` | Parsen von `precipitation_5` heute nur live getestet (`@pytest.mark.live`) |
| `tests/tdd/test_radar_capture_is_convective.py` | bestehende Tests zu `is_convective` im Radar |

## Existing Patterns
- Sidecar: Frames der Niederschlagsquelle + `_merge_convective(frames, sidecar)`; Sidecar leer -> `self._convective_checked = False` (ADR-0018, kein Kaschieren als "kein Gewitter"); Ausgabe "Storm check not available." (`radar_service.py:~760`).
- Alle Open-Meteo-Zweige laufen durch `_fetch_openmeteo_15` -> Budget-Gate (#1329 C2) und Offline-Fixture (`_load_radar_fixture_frames`) kommen dort automatisch mit.
- Gewitter-Codes: `_is_convective_weathercode`, `_is_hail_weathercode`.

## Dependencies
- Upstream: BrightSky `/radar` (`format=plain`, braucht `Accept-Encoding: gzip|br|zstd`, sonst HTTP 400), Open-Meteo minutely_15 (`weather_code`), `ForecastBudgetGate`.
- Downstream: Radar-Alarmstufe Gewitter/Hagel (#660), Akut-Override #1310, Gewitter-Hebung #1759, Briefing-/Alarm-Texte aller vier Kanaele (`convective_checked`), Radar-Cache (Schluessel enthaelt Region-Bucket).

## Existing Specs
- `docs/specs/modules/radar_convective_stage.md`, `radar_nowcast.md`, `radar_nowcast_inca_fix.md`, `radar_nowcast_france.md`, `fix_1329_c2_radar_nowcast_cache.md`, `feat_1759_radar_vorhersage_fusion.md`
- ADR: `docs/adr/0018-provider-fallback-ohne-kaschieren.md`

## Risks & Considerations
- Sidecar-Quelle NICHT annehmen: live messen (Open-Meteo best_match vs. ICON-D2 `weather_code`), ob sie in DE ein Gewitter-Signal liefert (AROME-FR lieferte an Korsika strukturell keinen Code, #1761).
- Ein zusaetzlicher Open-Meteo-Call pro DE-Radarabfrage erhoeht Budget-Verbrauch; Gate muss greifen (Drosselung -> `_convective_checked=False`, nicht "kein Gewitter").
- Cache: Sidecar-Ergebnis/`convective_checked` muss mit gecacht bzw. korrekt abgeleitet werden (Lehre F001 aus #1329 C2).
- Offline-Fixture-Modus muss netzfrei bleiben (BrightSky liefert dort `[]`, Sidecar-Pfad darf nicht ohne Frames laufen).
- Ueberlappung `_within_radolan` / `_within_inca` an der AT-Grenze pruefen.
- Alarme muessen alle Kanaele erreichen; Mail/Telegram/SMS/Premium-SMS ziehen aus demselben Ergebnis.
- Mitlieferung: aufgezeichnete BrightSky-Fixture (versioniert) + Parser-Test im Kern.

## Analysis

### Type
Bug (nutzersichtbar: DE-Radar meldet nie Gewitter/Hagel).

### Live-Messung der Sidecar-Quelle (2026-09-30)
- Open-Meteo `minutely_15` `weather_code`, 96 Schritte, 4 DE-Punkte (München, Hamburg, Allgäu, Rügen): `weather_code` und `precipitation` **nie None**; `best_match` == `icon_d2` **identisch** in DE (`icon_seamless` ebenso). `icon_eu` weicht ab (gröber) — nicht nehmen.
- Rückblick 92 Tage, `icon_d2`: Code 95 (München 20, Frankfurt 36, Berlin 32, Düsseldorf 20, Allgäu 76 Viertelstunden) und 96 (München 24) kommen vor, 99 nicht. ⇒ ICON-D2 trägt in DE strukturell Gewitter-Codes (anders als AROME-FR an Korsika, #1761). Sidecar-Quelle = `_fetch_openmeteo_15(lat, lon, elevation_m=...)` ohne `models` (best_match), exakt wie INCA — kein eigenes Modell nötig.
- BrightSky `/radar?format=plain` mit `Accept-Encoding: gzip`: HTTP 200, **8,06 MB** roh, 25 Frames, Raster 401×401, `latlon_position` x/y fraktional. ⇒ Fixture muss auf ein kleines Fenster um die Zielzelle gekürzt werden (gleiche Struktur, `latlon_position` angepasst), sonst unbrauchbar groß.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/radar_service.py` (`_fetch_brightsky`) | MODIFY | Nach erfolgreichem BrightSky-Abruf Sidecar `_fetch_openmeteo_15` holen, `_merge_convective`; Sidecar leer ⇒ `self._convective_checked = False`. Offline-Modus bleibt `[]` (früher Return, Sidecar nie erreicht). |
| `src/services/radar_cache.py` | MODIFY | `convective_checked` mit im Cache-Eintrag führen (siehe Risiko F001) — `put(..., convective_checked)`, `get_nowcast` liest es beim Hit zurück. |
| `tests/tdd/test_radar_brightsky_convective_sidecar.py` | CREATE | Verhaltenstests: Sidecar liefert 95/96 ⇒ DE-Frame `is_convective`/`hail`; Sidecar gedrosselt/leer ⇒ `convective_checked=False`; Cache-Hit erhält `False`; Offline ⇒ netzfrei. |
| `tests/fixtures/brightsky/radar_de_kurz.json` | CREATE | aufgezeichnete, gekürzte BrightSky-Antwort + Parser-Test im Kern. |

### Scope Assessment
- Files: 2 produktiv + 1 Test + 1 Fixture
- Estimated LoC: +25–40 produktiv, Tests ~120
- Risk Level: MEDIUM (zentrale Nowcast-Kette; Alarm-Verhalten in DE ändert sich erstmals — Gewitter-Alarme werden möglich; Open-Meteo-Budget +1 Call je DE-Radarabfrage)

### Technical Approach
1. `_fetch_brightsky`: Frames holen; nur wenn Frames vorhanden Sidecar rufen (kein Sidecar ohne Frames). Muster wörtlich wie `_fetch_geosphere_inca`.
2. Budget-Gate kommt automatisch über `_fetch_openmeteo_15`; Drosselung ⇒ `_convective_checked=False` (ADR-0018), Ausgabe „Storm check not available." kommt bestehend.
3. Cache-Lücke schließen: heute wird `convective_checked` nicht gecacht; ein Cache-Treffer meldet immer `True` (gilt schon für INCA/Korsika). Für DE besonders relevant, weil BrightSky-Frames bei ausgefallenem Sidecar 5 min als „geprüft, kein Gewitter" weiterbedient würden ⇒ Flag im Cache-Eintrag mitführen (Lehre F001 #1329 C2). Das behebt die Lücke für alle Regionen mit.
4. `_within_radolan`/`_within_inca`-Überlappung irrelevant: RADOLAN wird zuerst versucht; nur wenn BrightSky leer ⇒ INCA/Kette wie bisher.
5. Kanäle: keine Änderung nötig — alle vier Kanäle ziehen aus `NowcastResult`; im Test mindestens Alarm-Pfad + eine Renderer-Stelle (`convective_checked`-Marker `#`) prüfen.

### Dependencies
Upstream: BrightSky, Open-Meteo, `ForecastBudgetGate`. Downstream: Radar-Stufe Gewitter/Hagel (#660), Akut-Override #1310 (`trip_alert.py:2166`), Hebung #1759, Alarm-Renderer (`convective_checked`).

### Open Questions
- [ ] Erhöhter Open-Meteo-Verbrauch: 1 Zusatz-Call je DE-Radarabfrage (Cache 5 min mildert). Gate greift; PO-relevant nur, falls Budget knapp — Empfehlung: kein Sonderweg.
- [ ] Cache-Flag als eigener Scheiben-Schritt im selben Ticket (Empfehlung: ja, im selben Ticket — bekannte Abweichung nicht vertagen).

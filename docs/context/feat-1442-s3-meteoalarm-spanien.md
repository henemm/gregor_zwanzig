# Context: feat-1442-s3-meteoalarm-spanien

## Request Summary
Issue #1442 Scheibe S3, **nur Spanien (ES)**: `MeteoAlarmFeedSource("ES")` an den kontingentfreien
MeteoAlarm-Feed anbinden, damit Wanderpunkte in Spanien (v. a. Mallorca / GR221, 25.02.–07.03.2027)
amtliche AEMET-Warnungen bekommen. PT, UK, NL/BE, PL bleiben offen. PO hat die Umsetzung beauftragt
(2026-10-30). S1 (CH) und S2 (NO/SE/FI) sind live.

## Messung Spanien-Feed (2026-10-30, live, vor dieser Phase)
- `GET https://feeds.meteoalarm.org/api/v1/warnings/feeds-spain` -> 200, 1,3 MB, 97 Warnungen.
- **Kein einziges Polygon**, nur `EMMA_ID`-Geocodes -> gleicher Fall wie Finnland (Zonenweg),
  **nicht** wie CH/NO/SE (Punkt-in-Polygon).
- 233 verschiedene Zonen: Landzonen `ES070`-`ES251`, Kanaren `ES120`-`ES132`, Küstenzonen
  `ES840`-`ES890` (Präfix `Costa - ...`).
- **Mallorca/Balearen:** Land `ES113` Ibiza/Formentera, `ES114` Sierra Tramontana,
  `ES115` Norte y nordeste de Mallorca, `ES116` Interior de Mallorca, `ES117` Sur de Mallorca,
  `ES118` Levante mallorquín, `ES119` Menorca; Küste `ES873`-`ES878`. GR221 verläuft durch
  `ES114` (Tramontana) und angrenzende Zonen.
- Sprachen je Warnung: `es-ES` und `en-GB` (Mapper wählt `de*`, Fallback `en*` -> greift als `en-GB`).
- Sender AEMET, `awareness_level` / `awareness_type` im Standardformat.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm_feed.py` | `_FEED_PATHS`, `_GEOCODE_NAME`, Literal in `__init__`, `covers()`/`fetch()`, FI-Zonenweg (`_zones_for_point_fi`, `_fetch_fi`, `_fi_known_zones`) als Vorlage |
| `src/services/official_alerts/__init__.py` | Registrierung nach FI, vor `DpcSource` (Tie-Break "zuerst registriert gewinnt") |
| `src/services/official_alerts/region_mapper.py` | `RegionMapper` (Punkt -> Regionen-IDs), wiederverwendbar für ES-Zonen |
| `src/services/official_alerts/data/meteoalarm_zones_FI.geojson.json` | Muster der Zonendatei (Land aufgeweitet 0,05°, Seezonen unverändert) |
| `src/services/official_alerts/data/README.md` | Herkunft/Lizenz/Aktualisierung jeder Datei, ES-Abschnitt nötig |
| `src/services/official_alerts/meteoalarm.py` | CAP-Mapper (Gefahrenart, Stufe), unverändert |
| `tests/fixtures/meteoalarm_feed/` | echte gekürzte Proben + README; ES-Probe ergänzen |
| `docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md` | Vorlage der Spec (Teil B = FI-Zonenweg) |
| `docs/context/feat-1442-s2-meteoalarm-nordics.md` | Vorgänger-Kontext |

## Existing Patterns
- FI-Zonenweg: Punkt -> `EMMA_ID`-Menge über eingecheckte Zonengeometrie; ein Küstenort liegt in
  Land- UND Seezone, `fetch()` wertet alle getroffenen Zonen aus, jede Warnung einmal.
- Drei Zustände: außerhalb -> `mark_not_covered`; Feed nicht abrufbar -> `mark_fetch_incomplete`;
  sonst Treffer oder leer. Drift-Wächter `log_zone_drift` für unbekannte Feed-Zonen.
- Zonengeometrie stammt aus MeteoAlarm `geocodes.json` (Google-Drive-ID `16s24hYH...`, 39 MB),
  nur der Länderauszug wird eingecheckt; Landzonen aufgeweitet + vereinfacht.

## Dependencies
- Upstream: `feeds.meteoalarm.org` (Host im Egress-Inventar bereits geführt), `warn_egress`
  (Cache, TTL 30 Min.), `RegionMapper`, MeteoAlarm-CAP-Mapper.
- Downstream: Registry der amtlichen Quellen -> Briefing (Trip/Ortsvergleich), Alarm- und
  Entwarnungspfad (ADR-0090), alle vier Kanäle. Keine Änderung dort nötig.

## Existing Specs
- `feat_1442_s1_meteoalarm_ch.md`, `feat_1442_s2_meteoalarm_nordics.md`, `feat_1681_meteoalarm_de.md`.
- ADR-0090 (Entwarnung für alle amtlichen Warnungen).

## Risks & Considerations
1. **Lizenz der Geocode-Datei weiterhin ungeklärt** (bei FI bereits offen, Antrag in
   `docs/specs/data_sources.md`). ES würde dasselbe Risiko verdoppeln -> mit dem PO-Antrag bündeln,
   nicht still erweitern.
2. **Geometrie-Genauigkeit:** Die MeteoAlarm-Umrisse sind grob (bei FI fielen Küstenstädte
   knapp heraus). Mallorca/GR221 liegt an Küste und Gebirge -> Aufweitung und Test mit echten
   GR221-Punkten (Sa Dragonera, Sóller, Lluc, Pollença) nötig.
3. **Unbekannte Zonen im Feed:** Die Zonenzahl (233) deckt sich evtl. nicht mit `geocodes.json`;
   Lücken müssen Drift-Journal statt stiller Leere auslösen.
4. **Größe:** Spanien-Auszug mit ~250 Zonen und Kanaren/Ceuta/Melilla; Dateigröße gegen den
   Nutzen abwägen (evtl. nur Festland + Balearen + Kanaren, Nordafrika-Exklaven mit Begründung).
5. **Überlappung:** Keine Nationalquelle ES vorhanden; Grenze zu FR (`lookup_department`/
   MeteoAlarm FR) und PT beachten, damit Grenzpunkte keine Doppelanzeige erzeugen.
6. **Live-Beleg:** Staging blockt Warn-Hosts (Egress-Guard); wie bei S1/S2 Live-Test lokal und
   Fixtures im Kern-Lauf.

## Analysis

### Type
Feature (Scheibe S3 von #1442, nur Spanien).

### Messung 2026-10-30 (Analyse-Phase, gegen echte Daten)
- `geocodes.json` neu geladen: sha256 identisch zu FI (`0c8fe7b9…5dd0`), 39 MB. **ES-Auszug: 233 Zonen
  (`type=EMMA_ID`) = exakt die 233 Feed-Zonen. Keine unbekannte, keine ungenutzte Zone** (anders als FI, das 3 Lücken hatte).
- **Eigenschaftsname in der Quelle ist `code`, nicht `id`.** `RegionMapper` liest `properties.id` ->
  beim Bau des Auszugs `code` -> `id` umschreiben (sonst lädt der Mapper keine einzige Zone).
- Rohgeometrie ES: 0,51 MB (FI-Auszug 46 KB nach Vereinfachung). Mit `simplify(0.005)` + Auf-
  weitung realistisch 150–300 KB; Gate: Dateigröße im Spec festschreiben.
- Punkttest (Rohumrisse, ohne Aufweitung):

| Punkt | Treffer | nächste Landzone |
|---|---|---|
| Sóller | ES114 (Tramontana, Land) | – |
| Lluc | ES114 | – |
| Sa Calobra | ES114 | – |
| Palma | ES117 (Land) | – |
| Formentera | ES113 | – |
| **Sa Dragonera** | nur **ES874** (Küste) | ES117: 0,035° entfernt |
| **Port d'Andratx** | nur **ES874** (Küste) | ES117: 0,043° entfernt |
| Madrid | ES219 | – |
| Ceuta | ES871 (Küste) | – |
| Gibraltar | ES853 (Küste) | ES077: 0,054° |
| Grenze PT (38,8/-7,2) | keine | ES194: 0,038° |

  -> Küstenpunkte an GR221 (Südwest) fallen ohne Aufweitung nur in die Seezone und bekämen
  keine Land-Warnungen (Wind/Gewitter/Hitze der Landzone). **Aufweitung der Landzonen um 0,05°
  wie bei FI ist nötig** (deckt 0,035/0,043), Seezonen `ES84x–ES89x` unverändert.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/data/meteoalarm_zones_ES.geojson.json` | CREATE | ES-Auszug, 233 Zonen, `id`=EMMA_ID, Land aufgeweitet/vereinfacht |
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["ES"]`, `_GEOCODE_NAME["ES"]="EMMA_ID"`, Literal, `_es_zones`, Zonenweg; FI-Zweig zu "Zonenländer FI+ES" verallgemeinern statt kopieren |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("ES"))` nach FI, vor `DpcSource` |
| `src/services/official_alerts/data/README.md` | MODIFY | ES-Abschnitt: Herkunft, sha256, Veränderungen, Beleg 1:1-Abgleich |
| `docs/specs/data_sources.md` | MODIFY | ES in den bestehenden Lizenz-Antrag aufnehmen (gebündelt mit FI) |
| `tests/fixtures/meteoalarm_feed/feed_spain_sample.json` + README | CREATE/MODIFY | echte gekürzte Probe (Mallorca-Zonen) |
| `tests/test_meteoalarm_feed_es.py` | CREATE | Zonenweg, Küste Land+See, Grenze/außerhalb, 3 Zustände, Drift |
| `docs/specs/modules/feat_1442_s3_meteoalarm_spanien.md` | CREATE | Spec |

### Scope Assessment
- Files: 8 (davon 1 Datendatei, 1 Fixture)
- Estimated LoC: +120 Code/Tests ~+200, Daten ~200 KB generiert
- Risk Level: MEDIUM -- Code folgt bewährtem FI-Muster (niedrig), Risiko liegt in Geometrie
  (Küste/Grenze) und der ungeklärten Lizenz der Geocode-Datei.

### Technical Approach
1. FI-Zonenweg verallgemeinern: Zonen-Mapper je Land (`{"FI": _fi_zones, "ES": _es_zones}`),
   `_zones_for_point(country)`, `_fetch_zones(country)`; kein ES-Zwilling von `_fetch_fi`
   (Teilungsprinzip, kein Copy-Paste). Bestehende FI-Tests müssen unverändert grün bleiben.
2. Auszug einmalig per Skript aus `geocodes.json` (Parameter wie FI: Land +0,05°, `simplify(0.005)`;
   Seezonen unverändert; `code`->`id`), Skript-Parameter im README dokumentieren.
3. `covers()` = Punkt in mindestens einer ES-Zone (lokal, kein Netz). Außerhalb -> `mark_not_covered`.
4. Drift-Wächter `unknown_zone` bleibt scharf (aktuell 0 Lücken).
5. Sprache: Feed liefert `es-ES` + `en-GB`; Mapper-Fallback `en*` greift -- per Test belegen.

### Dependencies
- Upstream: `feeds.meteoalarm.org/…/feeds-spain` (Egress-Inventar vorhanden), `warn_egress`, `RegionMapper`.
- Downstream: Registry -> Briefing Trip/Ortsvergleich, Alarm-/Entwarnungspfad (ADR-0090), alle vier Kanäle -- keine Änderung.
- Keine neue Python-Abhängigkeit zur Laufzeit (shapely nur beim einmaligen Bau des Auszugs, nicht im Repo-Code).

### Open Questions
- [ ] Lizenz Geocode-Datei: nicht neu entscheiden, ES wird im bestehenden PO-Antrag (data_sources.md) mitgeführt.
- [ ] Kanaren/Ceuta/Melilla im Auszug belassen? Empfehlung: ja (alle 233 Zonen, sonst Drift-Wächter-Dauerlärm; Zusatzgröße gering).
- [ ] Doppelanzeige an der FR/PT-Grenze: Aufweitung 0,05° (~5 km) kann Grenzpunkte beiderseits treffen; FR/PT haben aktuell keine MeteoAlarm-Quelle, Test "Punkt Frankreich nahe Grenze" in die Spec aufnehmen.

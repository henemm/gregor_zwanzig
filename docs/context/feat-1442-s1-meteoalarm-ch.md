# Context: feat-1442-s1-meteoalarm-ch

## Request Summary
Issue #1442, Slice S1: MeteoAlarm-Warnungen für die Schweiz (CH) anbinden. Das Ticket (31.07.) ist
überholt: Budget-Gate und EDR-Klasse sind mit #2266 zurückgebaut; neue Länder laufen über den
kontingentfreien Feed `feeds.meteoalarm.org` (`MeteoAlarmFeedSource(country)`), Vorbild #1681 (DE).
S2 (NO/SE/FI) und S3 folgen als eigene Workflows.

## Stand der Vorbedingungen (geprüft 2026-10-28)
- #1397 CLOSED, #1445 erledigt über Feed (MQTT entfällt), #2266 CLOSED (PR #2631, EDR-Rückbau).
- AC-2 des Tickets (24h-Abrufbudget) ist gegenstandslos; Feed ist kontingentfrei, Cache 30 min.
- Ticket-Label `needs-po-approval` steht noch (Antrag in `docs/specs/data_sources.md` PENDING).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm_feed.py` | `MeteoAlarmFeedSource(country)`, `_FEED_PATHS` (IT/AT/DE), `_GEOCODE_NAME`, `covers()`/`fetch()` je Land, `_alerts_for_zone` (zonenbasiert über EMMA_ID/WARNCELLID) |
| `src/services/official_alerts/__init__.py` | Registrierung + verbindliche Reihenfolge (Tie-Break „zuerst registriert gewinnt") |
| `src/services/official_alerts/meteoalarm.py` | geteilter CAP-Mapper (`_collect_cap_info_entries`, `_group_and_map_info_entries`) |
| `src/services/official_alerts/warn_egress.py` | `cached_fetch`, `mark_not_covered`, `mark_fetch_incomplete`, `log_zone_drift` |
| `src/services/official_alerts/base.py` | `get_official_alerts_with_status` — `unavailable` über alle Quellen, `not_covered` kompensiert keinen Ausfall |
| `src/services/official_alerts/slf.py` + `data/avalanche_regions_CH.geojson.json` | CH-Lawinen (andere Gefahrenart), liefert bereits eine CH-Geometrie (`regions_at`) — Kandidat für `covers()` |
| `src/services/official_alerts/dwd_zones.py`, `data/dwd_warngebiete_kreise.json` | Muster #1681: eingecheckte Geometrie + `warncell_at` |
| `src/app/egress_guard.py`, `internal/egress/inventory.go` | Host `feeds.meteoalarm.org` bereits Blocked-in-Test/Staging gelistet → kein neuer Host nötig |
| `tests/fixtures/meteoalarm_feed/` (+ README) | aufgezeichnete Feed-Samples je Land; für CH neu aufzuzeichnen |
| `docs/specs/modules/feat_1681_meteoalarm_de.md` | Spec-Vorlage (11 ACs: Treffer, Ausfall, Ausland, Cancel, Dedup, Alarm-Stufe, Tie-Break) |
| `docs/specs/modules/feat_1445_s3_oesterreich_feed.md`, `refactor_2266_meteoalarm_edr_rueckbau.md` | Feed-Architektur, Rückbau |

## Messbefund CH-Feed (live, 2026-10-28)
`GET https://feeds.meteoalarm.org/api/v1/warnings/feeds-switzerland` → 200, 5,6 MB, 143 Einträge
(136 Alert, 7 Update), je Eintrag 5 Sprachen (en/de/fr/it/rm) × 1 `info`.
- **KEIN Geocode** (weder EMMA_ID noch Schweizer Kennung): jede `area` hat nur
  `areaDesc` (Gemeindename, z. B. „Muotathal"), `altitude`, `ceiling`, **`polygon`** (Gemeinde-Umriss).
  715 Areas insgesamt.
- **Folge:** Der Zonen-Weg (`_emma_ids_for_alert`) greift nicht. Zuordnung Punkt→Warnung muss
  **Punkt-in-Polygon direkt gegen die Feed-Polygone** erfolgen (`geo_ray_cast.py` existiert) — keine
  eingecheckte CH-Geometrie nötig, aber ein anderer Algorithmus als bei IT/AT/DE.
- Warnstufe/Typ im CAP-`parameter`: `awareness_level` („2; yellow; Moderate"), `awareness_type`
  („1; wind") — wie bei IT/AT, Mapper geteilt nutzbar.
- 5 Sprachblöcke je Alert: Sprachwahl (de) muss feststehen (Mapper-Verhalten für IT/AT prüfen).
- `covers()` ohne Netz braucht eine CH-Landesgrenze: Bbox überlappt DE/AT/IT/FR/LI. Kandidat:
  `slf.py`-Mikroregionen-Polygon (`regions_at`), grober, deckt aber evtl. nicht alle CH-Gebiete
  (Mittelland ohne Lawinenregion?) → in /20-analyse klären.

## Existing Patterns
- Länder-Dispatch per `if self.country == ...` in `covers()`/`fetch()`; Cache-Schlüssel = Ländercode.
- Drei Zustände „zuständig/nicht zuständig/Ausfall" (`mark_not_covered` vs `mark_fetch_incomplete`).
- Registrierungsreihenfolge ist Tie-Break; neue Quelle vor `DpcSource`, SLF steht am Ende.
- Aufhebung: `Cancel` ohne `info`; Entwarnung nach #1441 S2 (ADR-0090) über Verschwinden.

## Dependencies
- Upstream: Feed-Host, `warn_egress`, CAP-Mapper, Punkt-in-Polygon.
- Downstream: Compare-Mail-/Briefing-Chips, Alarm-Pfade für alle vier Kanäle (#1701), Premium-SMS,
  Entwarnungs-Logik (#1441), Go-Scheduler-Health `warn_service_health.go` (Länder-Liste?).

## Existing Specs
- `docs/specs/modules/feat_1681_meteoalarm_de.md` (Vorlage), `feat_1445_s1/s3`, `fix_1397_meteoalarm_coverage_budget.md`,
  `fix_1430_meteoalarm_lawine.md`, `feat_1441_s3_slf.md`, ADR-0016, ADR-0090/0091.

## Risks & Considerations
- Rechenaufwand: 5,6 MB / 715 Polygone je Abruf — Punkt-in-Polygon pro Trip-Punkt; Parse-Cache (30 min) nötig, sonst Latenz.
- Überlappung mit SLF/avalanche.report: andere Gefahrenart (`avalanche_bulletin`) → voraussichtlich kein Doppel-Chip; AC-3 des Tickets prüfen.
- Grenzregionen (FR/DE/AT/IT/LI): `covers()` darf Nachbarländer-Punkte nicht fälschlich als CH führen (kein falscher Ausfallhinweis, vgl. #1397 S4).
- Lizenz/EUMETNET-Weitergabe (5–10 min Verzug) — #2266 Prüfpunkt 4, CH-Feed gleiche Klausel.
- Ticket-Update nötig (Budget streichen, Feed-Weg, Polygon-Befund). PO-Genehmigung `needs-po-approval` klären.
- Go-Seite (`warn_service_health.go`, `forecast_budget_health.go`) auf Länder-Annahmen prüfen.

## Analysis

### Type
Feature (Slice S1 von #1442: nur CH).

### Zusätzliche Messbefunde (2026-10-28)
- `SlfSource.covers()` (CH-Lawinenregionen, Polygon) deckt Zürich, Bern, Basel, Genf, Lugano, Davos, Schaffhausen ab
  (kein Mittelland-Loch) und schließt Konstanz, Lörrach, Annemasse, Bregenz, Feldkirch, Como, Livigno, Chamonix,
  Domodossola, Mulhouse korrekt aus. Einziger Ausreißer: Vaduz (FL) zählt als „CH" — vernachlässigbar.
- Mapper (`meteoalarm.py:103`) wählt bereits `de*`, Fallback `en*` → 5 Sprachblöcke je Alert brauchen keine Änderung.
- `_alerts_for_zone` ist zonenbasiert (Geocode); für CH gibt es keine Geocodes → eigener Pfad nötig.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `"CH"` in `Literal`/`_FEED_PATHS`; `covers()` über CH-Geometrie; `fetch()`-Zweig CH; neue `_alerts_for_point_polygon()` (Punkt-in-Polygon gegen `info[].area[].polygon`, Cancel/Malformation-Schutz wie `_alerts_for_zone`) |
| `src/services/official_alerts/__init__.py` | MODIFY | `MeteoAlarmFeedSource("CH")` registrieren nach DE, vor `DpcSource`/SLF |
| `src/services/official_alerts/geo_ray_cast.py` | REUSE | `_point_in_ring`; Löcher/Mehrfachringe beachten |
| `tests/fixtures/meteoalarm_feed/feed_switzerland_sample.json` (+README) | CREATE | aufgezeichnete, gekürzte CH-Probe (inkl. Update/Cancel) |
| `tests/…/test_meteoalarm_feed_ch*.py` | CREATE | Treffer, Ausland (DE/AT/IT/FR-Grenzpunkte), Ausfall, Cancel, Dedup, Tie-Break, 2 Nutzer irrelevant (keine Nutzerdaten) |
| `docs/specs/modules/feat_1442_s1_meteoalarm_ch.md` | CREATE | Spec nach Vorlage #1681 |
| `docs/specs/data_sources.md`, Ticket #1442 | MODIFY | PENDING-Antrag/Ticket auf Feed-Weg aktualisieren |

### Scope Assessment
- Files: 2 Produktiv + Fixture + Tests + Spec
- Estimated LoC: +120/-5 (Produktiv ~80, Rest Tests)
- Risk Level: MEDIUM (5,6-MB-Feed + Polygon-Rechnung pro Punkt; Grenzfälle Nachbarländer)

### Technical Approach
1. **Zuständigkeit (`covers`)**: lokal über `SlfSource`-Regionspolygone (`RegionMapper.regions_at`) — kein neues Datenfile, keine Netzabfrage; Vaduz-Ausreißer als Known Limitation dokumentieren.
2. **Zuordnung (`fetch`)**: Punkt-in-Polygon direkt gegen Feed-`polygon`; vorab Bounding-Box je Area, damit nur wenige Ringe voll gerechnet werden. Gemeindepolygone nur für gewarnte Gebiete im Feed → kein Treffer = keine Warnung (nicht Ausfall).
3. **Höhenband**: `altitude`/`ceiling` der Area im Spec-Entscheid behandeln (Warnung nur für Höhenlage? Vorschlag: ignorieren, wie bei IT/AT, in Spec festhalten).
4. **Performance**: geparster Feed bleibt 30 min im Cache (`_get_cached_feed("CH")`); Polygon-BBoxen einmal je Feed-Parse vorberechnen und mitcachen.
5. **Ausfall**: Feed nicht abrufbar → `mark_fetch_incomplete()` (Muster DE).
6. **Dedup/Tie-Break**: neue Quelle nach DE registrieren; SLF liefert andere Gefahrenart (`avalanche_bulletin`) → kein Doppel-Chip erwartet (in Spec per Test belegen).

### Dependencies
`warn_egress`, geteilter CAP-Mapper, `geo_ray_cast`, `RegionMapper`; Egress-Host `feeds.meteoalarm.org` bereits gelistet. Go-Seite: keine Länderliste in `internal/` gefunden (Grep) — in /30 nochmals bestätigen.

### Open Questions
- [ ] Höhenband (`altitude`/`ceiling`) ignorieren oder auswerten? (Empfehlung: ignorieren, wie IT/AT/DE)
- [ ] Ticket-Label `needs-po-approval`: Antrag bezieht sich auf Länderscope; Quelle ist bereits genehmigt — PO-Bestätigung für CH nötig?
- [ ] Vaduz/FL als „CH" akzeptieren (Empfehlung: ja)

# Context: feat-1442-s2-meteoalarm-nordics

## Request Summary
Issue #1442, Slice S2: MeteoAlarm-Länder Norwegen, Schweden, Finnland an den kontingentfreien
Feed `feeds.meteoalarm.org` anbinden. S1 (CH, Punkt-in-Polygon) ist live (PR #2637, `3fc6eeb`).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm_feed.py` | `_FEED_PATHS` (Z. 51), `_GEOCODE_NAME` (Z. 64), `covers()`/`fetch()`, CH-Polygonweg (`_ch_index`, `_hit_area`, `_alerts_for_point_polygon`, `_covers_ch`, `_fetch_ch`) — alles CH-fest verdrahtet, `_ch_index_memo` ein globaler Schlüssel |
| `src/services/official_alerts/__init__.py` | Registry-Reihenfolge, Z. 43-55 (IT, AT, DE, CH, dann DpcSource) |
| `src/services/official_alerts/geo_ray_cast.py` | `_point_in_ring`, unverändert wiederverwendbar |
| `src/services/official_alerts/meteoalarm.py` | geteilter CAP-Mapper, Sprachwahl `de*`, Fallback `en*` |
| `src/services/official_alerts/dwd_zones.py`, `dpc.py` | Vorbild für eingecheckte Zonengeometrie (DE/IT) — Muster für FI |
| `src/services/official_alerts/warn_egress.py` | `mark_not_covered`, `mark_fetch_incomplete`, `log_zone_drift` |
| `src/output/renderers/alert/official_alerts.py` | Konsument (Renderer), nur Lesen |
| `tests/fixtures/meteoalarm_feed/` (+ `README.md`) | Fixtures je Land; für NO/SE/FI neue Proben nötig |
| `tests/tdd/test_meteoalarm_feed_ch.py`, `..._ch_live.py` | Vorlage für Verhaltens- und Live-Tests |
| `docs/specs/modules/feat_1442_s1_meteoalarm_ch.md` | Vorlage-Spec (316 Zeilen) |
| `docs/specs/data_sources.md` | PENDING-Antrag, nachführen |
| `internal/egress/inventory.go` | Host `feeds.meteoalarm.org` bereits geführt; kein Go-Eingriff erwartet |

## Existing Patterns
- Geocode-Weg (IT/AT/DE): Punkt → Zonen-ID über eingecheckte Geometrie, dann Abgleich mit `EMMA_ID`/`WARNCELLID` im Feed.
- Polygon-Weg (CH, S1): kein Geocode im Feed; Punkt-in-Polygon direkt gegen `info[].area[].polygon`, BBox-Vorfilter, Cancel/Update-Schutz, 30-min-Cache samt Index.
- `covers()` ist rein lokal (kein Netz). CH nutzt SLF-Regionen als Geometrie, Fallback gecachter Feed.

## Feed-Befund (live abgerufen 2026-10-29)
| Land | HTTP | Größe | Warnungen | Gebietszuordnung | Sprachen |
|---|---|---|---|---|---|
| NO | 200 | 592 KB | 69 | Polygone (+`altitude`/`ceiling`), kein Geocode | `no`, `en-GB` |
| SE | 200 | 402 KB | 28 | Polygone, kein Geocode | `sv-SE`, `en-GB` |
| FI | 200 | 103 KB | 27 | nur `EMMA_ID`, kein Polygon | `fi-FI`, `sv-SE`, `en-GB` |

FI-Kennungen im Feed: `FI801`-`FI813` (Seegebiete, teils Lücken) und `FI029`, `FI032`, `FI043` (Land: Pohjanmaa, Varsinais-Suomi, Ahvenanmaa). Im Repo gibt es keine finnische Zonengeometrie.
Möglicher Geometrie-Ursprung (UNGEPRÜFT): FMI-CAP `alerts.fmi.fi/cap/` (CC BY 4.0), FMI-WFS `opendata.fmi.fi/wfs`.

## Dependencies
- Upstream: `feeds.meteoalarm.org` (kein Kontingent), `_get_cached_feed`, `warn_egress`, CAP-Mapper.
- Downstream: Alarm-/Briefing-Pfade beider Flächen (Trip, Ortsvergleich) über `get_official_alerts_*`, alle vier Kanäle ohne Sonderlogik.

## Existing Specs
- `docs/specs/modules/feat_1442_s1_meteoalarm_ch.md` (Vorlage), `feat_1681_meteoalarm_de.md`, `fix_1397_meteoalarm_coverage_budget.md`

## Risks & Considerations
- `covers()` für NO/SE: keine lokale Landesgeometrie; Fallback auf gecachten Feed allein startet nie den ersten Abruf. Vorfilter nötig (grobe Bbox).
- Bboxen NO/SE/FI überlappen sich und Nachbarländer (DK, DE, EE, RU).
- CH-Code ist fest auf `"CH"` verdrahtet (`_cache.get("CH")`, `_ch_index_memo`, Drift-Log `meteoalarm_feed:CH`) → länderweise verallgemeinern.
- FI braucht Geometrie-Quelle und Fixture aus echter Aufzeichnung; Seegebiete (FI80x) für Küstenpunkte.
- Sprachwahl `no`/`sv-SE`/`fi-FI` → Fallback `en-GB` per Test belegen.
- Mandantentrennung: Quelle global, keine Nutzerdaten (wie S1).
- Der alte S1-Workflow steht in Session `5f13f744` noch auf `phase6_implement` (nicht anfassen).

## Analysis

### Type
Feature (Slice S2 von #1442: MeteoAlarm NO, SE, FI)

### Befund FI (neu, live 2026-10-29)
Der FI-Feed enthält je Gebiet nur `geocode EMMA_ID` (`FI029` Pohjanmaa, `FI032` Varsinais-Suomi, `FI043` Ahvenanmaa; Seegebiete `FI801`–`FI813`), **kein Polygon**. Im Repo gibt es keine Geometrie dazu → FI ist der Geocode-Weg (wie IT/AT/DE) und braucht eine NEUE eingecheckte Zonengeometrie. FMI-CAP (`alerts.fmi.fi/cap/`) und FMI-WFS (`opendata.fmi.fi/wfs`) antworten HTTP 200; ob dort Geometrie mit EMMA_ID-Zuordnung liegt, ist UNGEPRÜFT (Spike nötig, eigene Aufgabe in /30).

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS` +NO/SE/FI; CH-Polygonweg auf Länderschlüssel verallgemeinern (`_ch_index_memo`, `_cache.get("CH")`, Drift-Log `meteoalarm_feed:CH`, `_covers_ch`, `_fetch_ch`); `country`-Literal erweitern; `covers()`/`fetch()` je Land |
| `src/services/official_alerts/__init__.py` | MODIFY | 3 Registrierungen nach CH, vor DpcSource |
| `src/services/official_alerts/data/` | CREATE | Landesumrisse NO/SE/FI (vereinfacht, lizenzfrei) für `covers()`; für FI zusätzlich Zonengeometrie `FI0xx/FI8xx` |
| `tests/fixtures/meteoalarm_feed/` | CREATE | aufgezeichnete Proben NO/SE/FI + README |
| `tests/tdd/test_meteoalarm_feed_nordics.py` (+`_live.py`) | CREATE | Verhalten (Treffer, Update/Cancel, Sprachfallback `en-GB`, nicht zuständig, Ausfall) + Live |
| `docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md`, `docs/specs/data_sources.md` | CREATE/MODIFY | Spec, PENDING-Antrag nachführen |

### Scope Assessment
- Dateien: ca. 8–10; LoC (produktiv): NO+SE ca. +90, FI ca. +80 plus Datendatei (Daten zählen nicht)
- Risiko: MEDIUM — Refactor des gerade live gegangenen CH-Wegs (Regressionsgefahr, S1-Tests müssen grün bleiben); FI-Geometriequelle ungeklärt

### Technical Approach
1. **NO/SE = Polygon-Weg wie CH.** CH-Funktionen parametrisieren (Länderschlüssel statt fester `"CH"`), kein zweiter Code.
2. **`covers()` braucht lokale Landesgeometrie.** Anders als CH gibt es für NO/SE keine Regionsdatei; „nur gecachter Feed“ startet nie den ersten Abruf. Lösung: eingecheckte, leicht aufgeweitete Landesumrisse (Küste!). Falsch-Ja ist harmlos (Abruf, „keine Warnung“), Falsch-Nein wäre stilles Schweigen → Umriss lieber großzügig.
3. **FI = Geocode-Weg** (`EMMA_ID`): Geometrie aus FMI beschaffen, Punkt → `FI0xx` (Land) bzw. `FI8xx` (See), dann bestehendes `_alerts_for_zone`.
4. Sprachwahl: Mapper nimmt `de*`, Fallback `en*` → `en-GB` greift in allen drei Ländern; per Test belegen.
5. Budget: Feed `feeds.meteoalarm.org` ist kontingentfrei, 30-min-Cache je Land; 3 Länder = max. 3 Abrufe/30 min (NO 592 KB größtes). AC-2 des Tickets (24h-Budget) greift auf diesem Feed nicht, im Spec ausdrücklich festhalten.
6. Dedup (AC-3): keine Überlappung mit nationaler Quelle für NO/SE/FI → entfällt; Grenzpunkte (z. B. NO/SE) zeigen höchstens je Land eigene Warnungen.

### Empfehlung zum Zuschnitt (Tech-Lead-Entscheidung)
Ein Ticket-Slice S2, in der Spec zwei Teile: **Teil A NO+SE**, **Teil B FI** (Geometrie-Spike zuerst). Wenn der FI-Spike keine verwendbare Geometrie liefert, bleibt FI in S2 offen und wird nicht als „erledigt“ gemeldet.

### Dependencies
`_get_cached_feed`, `warn_egress`, CAP-Mapper, `geo_ray_cast._point_in_ring`; Konsumenten (Trip + Ortsvergleich, alle vier Kanäle) unverändert.

### Open Questions
- [ ] FI: Liefert FMI-WFS/CAP Geometrie mit `EMMA_ID`-Zuordnung (FI029 …) oder braucht es Eurostat/NUTS als Ersatz? (Spike in /30)
- [ ] Lizenz/Quelle der Landesumrisse (Natural Earth = gemeinfrei) im `data/README.md` vermerken

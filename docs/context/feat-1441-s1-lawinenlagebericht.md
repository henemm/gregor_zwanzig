# Context: feat-1441-s1-lawinenlagebericht

## Request Summary
Issue #1441 Slice 1 (Epic #2258): amtlicher Lawinen-Lagebericht von avalanche.report (Landes-Lawinenwarndienste
AT, Bayern, Südtirol/Trentino) als neue `OfficialAlertSource` — Gefahrenstufe nativ 1–5 (Epic-Entscheid 2026-09-09:
nicht auf 1–4 quetschen), Höhenabhängigkeit, Lawinenproblem, Bulletin-Link. SLF (CH) = Slice 2, SMS-Token `AV` = #1473.

## Externe Quelle (am 2026-10-13 per Abruf verifiziert)

| Was | Fakt |
|---|---|
| Euregio (AT-07, IT-32-BZ, IT-32-TN) + Kärnten AT-02 | `https://static.avalanche.report/bulletins/latest/{X}_{lang}_CAAMLv6.json` (301 → `avalanche.report/bulletins/...`, Redirect folgen) |
| AT-03/04/05/06/08 + DE-BY | `https://static.lawinen-warnung.eu/bulletins/latest/{X}_{lang}_CAAMLv6.json` |
| Datierte Dateien | `.../bulletins/{D}/{D}_{X}_{lang}_CAAMLv6.json`, `{D}` = Gültigkeitstag |
| EU-Sammelfeed | `static.avalanche.report/eaws_bulletins/{D}/{D}-{X}.json` + `{D}.ratings.json` (Kurzform `"AT-07-01:high:pm": 3`), kein `latest/` |
| Struktur | `{"bulletins":[{bulletinID, publicationTime, validTime{startTime,endTime}, regions[{regionID,name}], dangerRatings[{mainValue, elevation{lowerBound|upperBound}, validTimePeriod}], avalancheProblems[{problemType, elevation, aspects, validTimePeriod}], tendency, source.provider}]}` |
| Stufen | `mainValue` low/moderate/considerable/high/very_high → 1–5 |
| Höhengrenze | String: Zahl (`"2600"`) **oder `"treeline"`** (Salzburg) — Parser muss beides können |
| Tageszeit | `validTimePeriod` `all_day` / `earlier` / `later`; `later` kann eigenen Höhensplit haben |
| Regions-Polygone | `https://regions.avalanches.org/micro-regions/latest/{X}_micro-regions.geojson.json`, CRS84 MultiPolygon, `id` == `regionID`; **nur `latest/`** (sonst ausgemusterte Regionen). Größe 27–349 KB je Land. Lizenz CC0 (gitlab.com/eaws/eaws-regions) |
| Web-Link | `https://avalanche.report/bulletin/{YYYY-MM-DD}?region={microRegionID}` |
| Lizenz | avalanche.report-Daten CC BY 4.0 (Namensnennung + Link); lawinen-warnung.eu-Spiegel: Bedingungen der jeweiligen Dienste **nicht verifiziert** |
| Key/Rate-Limit | kein Key, kein veröffentlichtes Limit; statische Dateien mit ETag |
| Rhythmus | 17:00 Ortszeit, gültig bis 17:00 Folgetag; Morgen-Update überschreibt in-place (nicht verifiziert) |
| **Außer Saison (heute)** | Euregio `latest/` → **HTTP 200 mit letztem Bulletin vom 2026-05-02** (veraltet!); andere Länder → **404** |

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/official_alerts/base.py:25-37` | Protocol `OfficialAlertSource` (`name`, `covers`, `fetch`) |
| `src/services/official_alerts/base.py:119-207` | `get_official_alerts_with_status`, Fail-soft/`unavailable` |
| `src/services/official_alerts/base.py:209-232` | Quellenübergreifendes Zusammenführen je Gefahrenart: höchster `level` gewinnt |
| `src/services/official_alerts/models.py:14-39` | `OfficialAlert` (frozen; `source, hazard, level, label, valid_from, valid_to, url, region_label, dedup_id, capture_id`), kein Feld für Höhe/Problem, kein Level-Check |
| `src/services/official_alerts/__init__.py:39-53` | Registry (Reihenfolge = Tie-Break) |
| `src/services/official_alerts/warn_egress.py:396` | `cached_fetch` (TTL 1800 s ok / 60 s Fehler / 24 h not-covered, 429-Backoff, Call-Log, single-flight), `mark_not_covered`, `mark_fetch_incomplete` |
| `src/services/official_alerts/meteoalarm_feed.py:256-270` | Vorbild für `cached_fetch`-Nutzung |
| `src/services/official_alerts/meteoalarm.py:471-481` | #1430: MeteoAlarm Typ 9 → `avalanche` (Awareness-Skala 1–4) |
| `src/services/official_alerts/meteo_forets.py:49-59,130-140` | Saison-Muster: `_SEASON_MONTHS` in `covers()`, Ortszeit (ADR-0044) |
| `src/services/official_alerts/dwd_zones.py:23-50`, `geo_ray_cast.py` | Polygon-Laden aus `data/` + Ray-Cast `(lon,lat)` even-odd |
| `src/services/official_alerts/data/` + `README.md` | Eingecheckte Geometrien mit Herkunftsnachweis |
| `src/services/official_alerts/massif_closure.py:61-72` | Präzedenz: emittiert bereits `level` 5 |
| `src/app/egress_guard.py:32-69` + `internal/egress/inventory.go` | Host-Inventar (Test/Staging), Drift-Test `tests/test_egress_inventory_drift.py` — neue Hosts eintragen |
| `src/app/models.py:29-30,55-320` | Ungenutzte DTOs `AvalancheProblem`, `AvalancheProblemInfo`, `AvalancheDanger(level 1-5, elevation_above_m, level_below, trend)`, `AvalancheReportMeta`, `AvalancheReport`; einziger Nutzer `tests/test_models.py` |
| `src/output/renderers/alert/official_alerts.py` | `_LEVEL_WORDS`(:43), `_LEVEL_POSITION`(:52), `_LEVEL_CLASS`(:56), `level_colors`(:219,:1655), `_SMS_LEVEL_LETTERS`(:2067), `_SOURCE_LABELS`(:99-116), Warnblock-Zeile „Warnstufe“ (:1576) |
| `src/output/renderers/email/compare_html.py` | `_ALERT_LEVEL_CELL`(:105), `_warn_short` Lawinen-Zweig (:569-571), `_render_warn_cell`(:584ff) |
| `src/output/renderers/email/html.py:1601-1648` | Trip-Briefing: Warnblock oben (`render_warn_block(variant="embedded", source_url=…)`) |
| `src/services/trip_report_scheduler.py:1463-1492` | Holt amtliche Warnungen je Segment |
| `src/output/tokens/hazard_symbols.py:24,53,60` | `AW`-Kürzel, `LEVEL_LETTERS` {2,3,4} (TABU-Kommentar), `MIN_SMS_LEVEL=3` |
| `src/services/alert_urgency.py:24-29,80-89` | Dringlichkeit aus amtlicher Stufe (Fallback „H“) |
| `src/output/tokens/dto.py:35`, `builder.py:314`, `adapters/trip_result.py:54,81` | Token `AV` existiert, immer `None` → #1473 |
| Trip-Feld `avalanche_regions` (`trip.py:194`, `loader.py`, `trip.go:118`, `types.ts:366`) | Nur im CLI-Textreport „noch nicht implementiert“ angezeigt |

## Existing Patterns
- **Quelle = `covers()` + `fetch()`**, registriert in `__init__.py`; `covers()` ist lokaler Vorfilter (bbox/Polygon), kein Länder-Erkennungsdienst.
- **Zuständigkeit nach ADR-0041** (Muster A/B/C): Ein Punkt, für den die Quelle nicht zuständig ist, darf nie den Hinweis „nicht abrufbar“ auslösen → `mark_not_covered`.
- **Saison** über `covers()` = False außerhalb der Monate (meteo_forets) — bei Lawine zusätzlich nötig: veraltete Bulletins (`validTime.endTime < jetzt`) als „kein aktueller Bericht“ werten.
- **Geometrie eingecheckt** unter `data/` mit README-Eintrag, Loader fail-soft.
- **Netzwerk wird im Test** über den autouse-Egress-Guard verhindert; aufgezeichnete Fixtures neben dem Test (`tests/fixtures/meteoalarm*/`).

## Dependencies
- Upstream: `warn_egress.cached_fetch`, `geo_ray_cast`, `tz_for_coords`/`local_dt`, Egress-Inventar.
- Downstream: alle Kanal-Renderer für amtliche Warnungen (Mail Trip-Briefing + Compare, Telegram, SMS, Premium-SMS, Alarm-Pfad `trip_alert.py:3090-3187`), Alarm-Dringlichkeit, Go-Monitor `warn_service_health.go` (Call-Log-`service`-Namen).

## Existing Specs / ADRs
- `docs/specs/modules/fix_1430_meteoalarm_lawine.md` (:76,:83,:252 — EAWS 1–5 gehört zu #1441/#1473)
- `docs/specs/modules/warnmail_official_alert_display.md`, `sms_official_alert_tokens.md`, `compare_official_alert_channels.md`, `egress_guard.md`, `egress_guard_go.md`
- `docs/specs/wintersport_extension.md:52-240` (alter, nie gebauter Plan, inkl. Stufen-Mapping 1-2/3/4-5)
- ADR-0016 (additiver Warntyp), 0018 (fail-soft, keine Maskierung), 0039 (MeteoAlarm-Feed), 0041 (Zuständigkeitsmuster), 0044 (Ortszeit)
- `docs/specs/data_sources.md:209-217` — **Datenquellen-Prozess: PENDING-Antrag + Genehmigung durch Henning vor Implementierung**

## Risks & Considerations
1. **🔴 Stufe 5 bricht stille Fallbacks:** Alle Anzeige-Tabellen kennen nur 1–4. Stufe 5 → „ROT“ ohne Unterscheidung, „Warnstufe 0/3“, im Compare schwächer gefärbt als Stufe 4 („warn“ statt „danger“), SMS-Buchstabe „H“. Jede Stelle muss bewusst entschieden werden.
2. **🔴 Zwei Skalen, eine Gefahrenart:** MeteoAlarm Typ 9 (Awareness 1–4) und EAWS (1–5) landen beide unter `avalanche`; die Zusammenführung „höchster Level gewinnt“ vergleicht Äpfel mit Birnen. Optionen: eigene Gefahrenart (z. B. `avalanche_bulletin`) oder Skalen-Kennzeichnung im Modell.
3. **🔴 Veraltete Daten im Sommer:** Euregio liefert HTTP 200 mit Bulletin vom Mai — ohne Prüfung von `validTime.endTime` würde eine fünf Monate alte Stufe als aktuell gemeldet (Haftung!).
4. **Datenquellen-Antrag fehlt:** avalanche.report steht nicht als genehmigte Quelle in `data_sources.md` → PENDING-Antrag in der Spec, Genehmigung mit der Spec-Freigabe.
5. **Lizenz:** CC BY 4.0 verlangt Namensnennung + Link → Quellenlabel + Bulletin-URL in der Ausgabe. Lizenz der lawinen-warnung.eu-Spiegel (AT-03..08, DE-BY) ungeklärt → evtl. S1 auf avalanche.report-Host (Euregio + AT-02) begrenzen oder Lizenz klären.
6. **Modell ohne Felder für Höhe/Problem:** `OfficialAlert` ist frozen und flach; Höhe/Problem in `label` stecken oder optionale Felder ergänzen (additiv, ADR-0016).
7. **„Keine Umdeutung“ (Haftung):** Stufe und Wortlaut des Warndienstes unverändert durchreichen; nur Daten, keine Handlungsempfehlung.
8. **Tageszeit- und Höhensplit:** Pro Bulletin bis zu vier Werte (vormittags/nachmittags × unter/über Grenze); Darstellung = Maximum mit Höhenangabe oder beides.
9. **Polygon-Last:** zehn GeoJSON-Dateien zusammen ~1,4 MB im Repo (Muster wie DWD-Warngebiete); nur `latest/`.
10. **Staging-Nachweis außer Saison:** Heute gibt es kein gültiges Bulletin → echte API-AC („Stufe 3 in Tirol“) erst ab Saisonstart (Ende Nov./Dez.) live messbar; bis dahin aufgezeichnete Winter-Fixtures (datierte Dateien, z. B. 2026-03-01) im Kern, live nur „sauber leer“.
11. **Kanalparität (CLAUDE.md):** amtliche Warnungen erreichen alle vier Kanäle — neue Quelle muss in Mail, Telegram, SMS, Premium-SMS ankommen (SMS-Token selbst ist #1473).

## Analysis

### Type
Feature (neue amtliche Warnquelle, Epic #2258, Slice 1)

### Ergebnisse der Recherche (2026-10-13, 3× Explore + Plan/Sonnet + Advisor)
- **Kanalfluss ist geschenkt:** Eine registrierte Quelle fließt über `get_official_alerts_with_status` (base.py:119) automatisch in Trip-Briefing (trip_report_scheduler.py:1463 → email/html.py:1644), Ortsvergleich (comparison_engine.py:320 → compare_official_alert.py:186/328 → notification_service.py:1397, SMS :1543, Telegram :1552) und Trip-Alarm (trip_alert.py:3056 → :3192 → notification_service.send_official_alert :1083: Mail/Telegram :1166, SMS :1199/:1221, Premium-SMS :1243). Arbeit liegt in **Darstellung** und **Zustandslogik**, nicht im Verdrahten.
- **Stufe 5 als `level` rendert still falsch** (kein Absturz): `_LEVEL_POSITION` {2,3,4} → „ROT · 0/3“ / „niedrigste“ (official_alerts.py:51,59,1088,1139,1576,1603,1732,1886); compare_html.py:562-570 Default `"warn"`. Stufe 1 hat ebenfalls keine Darstellung (`LEVEL_LETTERS` {2,3,4}; alert_urgency.py:28 `.get(1,"H")` → HIGH).
- **Eskalation/Dedup vergleichen nur `level`:** official_alerts.py:487 (`alert.level > last_reported_value`), :549 (`escalated = alert.level > kandidat_level`), base.py:209-232 (höchster level gewinnt / exakte Dublette). Mit abgeleitetem level (4,5→4) ginge der Sprung 4→5 verloren.
- **Alarm-Schlüssel** `official_alert_state_key` (official_alerts.py:389) enthält `valid_from/valid_to`; Nachfolgeperioden über `_identity_hazard_prefix` (#1685, :408). Tägliche Neuausgabe 17:00 erzeugt jeden Tag eine neue Periode.
- **`OfficialAlert`** (frozen) wird nirgends serialisiert; Go/Frontend kennen es nicht → additive optionale Felder sind billig. Alte DTOs `AvalancheDanger`/`AvalancheProblemInfo`/`AvalancheReport` (src/app/models.py:55-308) sind toter Code, Enum `AvalancheProblem` unvollständig ggü. CAAML (fehlen `no_distinct_avalanche_problem`, `favourable_situation`, `cornices`).
- **Regions-Mapping:** `geo_ray_cast.py` = nur `_point_in_ring`; 4 Konsumenten (dwd_zones, dpc, massif_zones, department_mapper) mit je eigener Lade- und Trefferpolitik; Dublette `meteoalarm.py:1008`. Kein generischer Mapper vorhanden.
- **Cache-Falle:** `cached_fetch` cacht „nicht zuständig“ (`not_covered_statuses`) **24 h** (warn_egress.py:47,628-642). Würden 404/veraltete Bulletins so behandelt, bliebe ein neues Bulletin bis zu 24 h unsichtbar (Saisonstart; tägliche Ausgabe 17:00) → **Haftungsfall bei Stufe 4**.
- **Hazard-Register:** official_alerts.py:90 indiziert `HAZARD_SMS_SYMBOLS[hazard]` hart → neue Gefahrenart braucht Einträge in `hazard_symbols.py` (Symbol, Bedeutung DE/EN, Reihenfolge) und `_HAZARD_LABELS`.
- **Zweiter Host:** EU-Sammelfeed `static.avalanche.report/eaws_bulletins/{D}/{D}-AT-05.json` bzw. `-DE-BY.json` liefert Salzburg und Bayern im **selben CAAML-Format** (HTTP 200 für 2026-03-01 geprüft; `source.provider` = „LWD Salzburg“), aber nur datiert, kein `latest/`. Lizenz für Nicht-Euregio-Dienste weder auf lawinen-warnung.eu noch avalanches.org ausgewiesen (WebFetch 2026-10-13).

### Technische Entscheidungen (Tech Lead)
1. **Eigene Gefahrenart `avalanche_bulletin`** (nicht `avalanche` teilen). MeteoAlarm-Typ-9 (Awareness 1–4, Kürzel AW) und EAWS-Lagebericht (1–5) sind zwei Skalen; gemeinsame Dedup würde Äpfel mit Birnen vergleichen. Beide dürfen parallel erscheinen (zwei amtliche Aussagen, bewusste Dublette, in Spec dokumentieren).
2. **Modell:** additive optionale Felder an `OfficialAlert`: `scale` (Default Bestand), `native_level`, Höhenangabe (Zahl oder „Waldgrenze“ wörtlich, Richtung ober-/unterhalb), `problems` (Tupel, CAAML-Codes), optional Tageszeit. `level` = abgeleitet nur für Farbe (1→1 … 4,5→4), wie PO-Entscheid. **Abweichung vom PO-Kommentar begründet:** alte DTOs in `src/app/models.py` werden NICHT wiederbelebt (anderes Modul, unvollständige Problem-Enum, nirgends verdrahtet) — der Kommentar nennt sie als Träger, Ziel (Stufe 1–5, Höhe, Problem) wird durch die neuen Felder erfüllt.
3. **Vergleiche mit Originalstufe:** Eskalation (official_alerts.py:487,:549) und Dublettenwahl (base.py:209-232) vergleichen `(level, native_level)`. 4→5 MUSS eskalieren.
4. **Darstellung:** zentraler Helfer „Lawinenstufe 4 (groß) oberhalb 2200 m · Triebschnee“ (EAWS-Wörter 1 gering, 2 mäßig, 3 erheblich, 4 groß, 5 sehr groß); Leiter „Warnstufe X · n/3“ entfällt für diese Gefahrenart; Weiche an allen Stufen-Renderstellen (Liste oben + compare_html.py:562-571). Bulletin-URL + Quellenname (CC BY 4.0) in `_SOURCE_LABELS` sichtbar.
5. **Höhen-/Tageszeitsplit:** gemeldet wird die **höchste** Stufe des Bulletins der getroffenen Region, mit der Höhenangabe des Ratings, das sie trägt; Tageszeit nur als Zusatz, wenn Vor-/Nachmittag verschieden. Ein Alert je Bulletin/Region.
6. **Drei Zustände ohne neues Flag:** (a) nicht abrufbar = Fetch-Fehler → `unavailable` wie bisher; (b) kein aktueller Bericht (404 oder `validTime.endTime` < jetzt, Ortszeit ADR-0044) → leeres Ergebnis + `mark_not_covered`, **aber kurze TTL** (nicht die 24-h-„nicht-zuständig“-TTL); (c) Stufe 1 = sichtbarer Alert (Info-Chip). Alarm/SMS ab Stufe 1 regelt die bestehende Kanal-Schwelle (Default LOW = ab 2). Kein sichtbarer „Saison“-Text in S1 (wäre neues Flag).
7. **SMS-Weg genau einer:** Lawinen-Lagebericht läuft über die Zeile amtlicher Warnungen mit eigenem Kürzel und **Ziffer der Originalstufe** (keine L/M/H-Umdeutung). Ob dafür das reservierte `AV` (#1473) genutzt und #1473 damit erledigt wird oder `day.avalanche_level` befüllt wird, legt die Spec fest — Doppelanzeige ist auszuschließen.
8. **RegionMapper:** generisches Modul extrahieren (Laden fail-soft mit Cache, Punkt→alle Regionen, ein Point-in-Polygon), neue Quelle nutzt es, Dublette `meteoalarm.py:1008` wird darauf umgestellt. Die vier Bestandskonsumenten werden **nicht** migriert (vier verschiedene Trefferpolitiken, Regressionsrisiko ohne Nutzerwert) — erfüllt „extrahieren“ des PO-Entscheids.
9. **Grenzpunkte:** mehrere Mikroregionen getroffen → höchste Stufe; deterministisch (Fixture-Test).
10. **Ein Slice, LoC-Override 500 gesetzt** (Schätzung 400–540 produktiv). Ein Schnitt Quelle/Darstellung wäre nutzerseitig unvollständig („nie Reste abspalten“, Kanalparität).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/official_alerts/avalanche_report.py | CREATE | Quelle: Fetch über `cached_fetch`, CAAML-v6-Parser (Zahl/„treeline“, all_day/earlier/later), Gültigkeitsprüfung, Max-Logik |
| src/services/official_alerts/region_mapper.py | CREATE | generischer Polygon-Mapper (GeoJSON laden, Punkt→Regionen) |
| src/services/official_alerts/data/avalanche_regions_*.geojson.json + README.md | CREATE/MODIFY | Mikroregionen (`latest/`, CC0) mit Herkunftsnachweis |
| src/services/official_alerts/models.py | MODIFY | additive Felder, abgeleitetes level |
| src/services/official_alerts/__init__.py | MODIFY | Registrierung |
| src/services/official_alerts/base.py | MODIFY | Dublettenwahl mit Originalstufe |
| src/services/official_alerts/meteoalarm.py | MODIFY | Dublette `_point_in_ring` → gemeinsame Funktion |
| src/services/official_alerts/warn_egress.py | MODIFY (ggf.) | kurze TTL für „kein aktueller Bericht“ |
| src/output/renderers/alert/official_alerts.py | MODIFY | Stufen-Helfer, Weichen, Eskalation `native_level`, Labels, Quellenlabel |
| src/output/renderers/email/compare_html.py | MODIFY | Lawinen-Lagebericht-Chip |
| src/output/tokens/hazard_symbols.py | MODIFY | Kürzel/Bedeutung/Reihenfolge |
| src/services/alert_urgency.py | MODIFY | Stufe 1 nicht als HIGH |
| src/app/egress_guard.py + internal/egress/inventory.go | MODIFY | Hosts `static.avalanche.report`, `avalanche.report` (Redirect) |
| internal/…/warn_service_health.go | MODIFY (prüfen) | neuer Call-Log-Service-Name |
| docs/specs/data_sources.md | MODIFY | Antrag-Eintrag (genehmigt 2026-09-09) |
| tests/fixtures/avalanche_report/ | CREATE | datierte Winter-Bulletins, Mai-Bulletin (veraltet), 404, Grenzpunkt |
| tests/test_avalanche_report_*.py | CREATE | Parser, Zustände, Kanäle, Eskalation, Mapping |

### Scope Assessment
- Files: ~16 produktiv/Daten + Tests
- Estimated LoC: +400–540 / −20 (produktiv), LoC-Override 500 gesetzt
- Risk Level: **HIGH** (sicherheitskritische Information, Haftung; Zustandslogik; außer Saison kein Live-Nachweis)

### Pflicht-Prüfpunkte für Spec/Adversary
- Veraltetes Bulletin (HTTP 200, Mai) → nichts angezeigt, **nicht** „nicht abrufbar“.
- Neues Bulletin nach Ablauf erscheint ohne 24-h-Verzögerung (TTL-Mutation muss rot werden).
- 4→5 eskaliert; gleiche Stufe am Folgetag (neue Periode) löst keinen erneuten Alarm aus; Absenkung/Entwarnung trägt die Dringlichkeit des alten Werts.
- Stufe 1 sichtbar, ≠ „kein Bulletin“, keine HIGH-Dringlichkeit.
- Keine Umdeutung: Text zeigt Originalstufe und Quell-Wortlaut („Waldgrenze“), Bulletin-URL in Mail/Telegram.
- Alle vier Kanäle mit Winter-Fixture (Trip-Briefing, Ortsvergleich, Telegram, SMS, Premium-SMS, Alarm).
- Kein Abruf für Punkte außerhalb der Regionen (Geo-Scope).
- Live auf Staging: nur „sauber leer“ (außer Saison); echter Nachweis ab Dezember.

### Dependencies
Upstream: `warn_egress.cached_fetch`, `geo_ray_cast`, `tz_for_coords`/`local_dt`, Egress-Inventar (Py+Go, Drift-Test). Downstream: alle Renderer amtlicher Warnungen, `alert_urgency`, Go-Monitor. Verwandt: #1473 (AV-Token), #1430 (MeteoAlarm-Lawine, live), S2 SLF.

### Open Questions
- [x] **PO-Entscheid 2026-10-13 („Belegte zuerst“):** S1 deckt NUR Euregio (AT-07 Tirol, IT-32-BZ Südtirol, IT-32-TN Trentino) + AT-02 Kärnten über `avalanche.report` ab. Salzburg (Hochkönig), Bayern, übrige AT-Länder werden nach Lizenzzusage der Warndienste per Konfigurationseintrag freigeschaltet — Quelle daher host-/länderkonfigurierbar bauen. Lizenzanfrage an die Warndienste steht noch aus (Entwurf durch Claude). Ursprüngliche Frage: Abdeckung S1 — nur Euregio (Tirol, Südtirol, Trentino) + Kärnten (CC BY 4.0 belegt), oder auch Salzburg (Hochkönig), Bayern und übrige AT-Länder über den EU-Sammelfeed, obwohl deren Lizenz nicht ausgewiesen ist?

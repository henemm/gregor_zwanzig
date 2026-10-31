# Context: feat-1442-s3-rest-eu

## Request Summary
Issue #1442, Slice S3: MeteoAlarm-Länder Spanien, Portugal, Vereinigtes Königreich, Niederlande,
Belgien, Polen an den kontingentfreien Feed `feeds.meteoalarm.org` anbinden. S1 (CH, PR #2637) und
S2 (NO/SE/FI, PR #2643) sind live. Konkreter Nutzerbedarf: PO-Trip GR 221 Mallorca (25.2.–7.3.2027).

## Feed-Befund (live abgerufen 2026-10-30)
| Land | Feed-Pfad | HTTP | Größe | Warnungen | Gebietszuordnung | EMMA-Zonen im Feed |
|---|---|---|---|---|---|---|
| ES | `feeds-spain` | 200 | 1,3 MB | 111 | nur `EMMA_ID` | 233 (`ES070`…; Mallorca u. a. `ES115` Norte y nordeste, `ES116` Interior, `ES117` Sur, Küste `ES874`/`ES876`) |
| PT | `feeds-portugal` | 200 | 9 KB | 5 | nur `EMMA_ID` | 5 (`PT001`…`PT024`) |
| UK | `feeds-united-kingdom` | 200 | 25 KB | 3 | **Polygone**, kein Geocode | – |
| NL | `feeds-netherlands` | 200 | 1,4 MB | 754 | nur `EMMA_ID` | 15 (`NL007`…) |
| BE | `feeds-belgium` | 200 | 240 KB | 61 | `EMMA_ID` **und** `NUTS2` gemischt | 2 (`BE004`, `BE801`) |
| PL | `feeds-poland` | 200 | 371 KB | 156 | nur `EMMA_ID` | 126 (fünfstellig nach Länderkürzel, `PL0202`…) |

Rohdaten (nicht eingecheckt): Scratchpad der Sitzung `58783cfb`, `feeds/*.json`.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm_feed.py` | `_FEED_PATHS` (Z. 55), `_GEOCODE_NAME` (Z. 69), `_POLYGON_COUNTRIES` (Z. 359), FI-Zonenweg `_fi_zones`/`_zones_for_point_fi`/`_fi_known_zones`/`_fetch_fi` (Z. 361, 513–520, 649–658), `covers()`/`fetch()` mit Länder-Verzweigungen, `Literal[...]` im Konstruktor (Z. 531) |
| `src/services/official_alerts/__init__.py` | Registry-Reihenfolge (Z. 43–68): IT, AT, DE, CH, NO, SE, FI, dann DpcSource, Lawine |
| `src/services/official_alerts/data/` + `README.md` | Eingecheckte Geometrie: `meteoalarm_outlines_nordics.geojson.json` (Natural Earth, gemeinfrei), `meteoalarm_zones_FI.geojson.json` (MeteoAlarm `geocodes.json`, **Lizenz ungeklärt**) |
| `src/services/official_alerts/region_mapper.py` | `RegionMapper.regions_at()` — Punkt → Zonen-IDs |
| `src/services/official_alerts/warn_egress.py` | `mark_not_covered`, `mark_fetch_incomplete`, `log_zone_drift` |
| `src/services/official_alerts/meteoalarm.py` | geteilter CAP-Mapper, Sprachwahl `de*` → Fallback `en*` |
| `tests/tdd/test_meteoalarm_feed_nordics.py`, `..._nordics_live.py` | Vorlage für Verhaltens- und Live-Tests (Zonenweg FI, Polygonweg NO/SE) |
| `tests/fixtures/meteoalarm_feed/` (+ `README.md`) | Aufgezeichnete Feed-Proben je Land; für die sechs Länder neue Proben nötig |
| `docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md` | Vorlage-Spec |
| `docs/specs/data_sources.md` (Z. 224, 306) | PENDING-Antrag je Slice, Lizenzvermerk `geocodes.json` |

## Existing Patterns
- **Zonenweg (IT/AT/DE/FI):** Punkt → Zonen-ID(s) über eingecheckte Geometrie; dieselbe Funktion für `covers()` und `fetch()`; `_alerts_for_zone` nimmt eine Zonen-Menge (Küstenort in Land- und Seezone); Drift-Wächter `_log_unknown_zone_drift` je Land und Feed-Momentaufnahme.
- **Polygonweg (CH/NO/SE):** Punkt-in-Polygon direkt gegen Feed-Polygone; Zuständigkeit lokal über aufgeweiteten Landesumriss (Natural Earth 5.1.1, `buffer(0.1)`, `simplify(0.01)`); BBox-Index-Memo je Land.
- Registrierung: eine `MeteoAlarmFeedSource(<Land>)`-Instanz je Land, vor `DpcSource` (Gewitter-Tie-Break „zuerst registriert gewinnt").
- Geometrie wird einmalig abgerufen und eingecheckt, zur Laufzeit nichts nachgeladen; Herkunft/sha256/Veränderungen in `data/README.md`.

## Dependencies
- Upstream: `feeds.meteoalarm.org` (kein Kontingent, kein neuer Host — in `internal/egress/inventory.go` geführt), `_get_cached_feed` (30-min-TTL), CAP-Mapper, `RegionMapper`.
- Downstream: Alarm- und Briefing-Pfade beider Flächen (Trip, Ortsvergleich) über die Registry; alle vier Kanäle ohne Sonderlogik.

## Existing Specs
- `docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md` (direkte Vorlage), `feat_1442_s1_meteoalarm_ch.md`, `feat_1681_meteoalarm_de.md`

## Risks & Considerations
- **Lizenz `geocodes.json` ungeklärt** (seit S2 offen). S3 würde fünf weitere Länder (ES, PT, NL, BE, PL) auf diese Datei stützen. Prüfen, ob es pro Land eine Geometrie mit klarer Lizenz gibt (z. B. AEMET-Warnzonen, IPMA-Distrikte, KNMI-Provinzen, IMGW-Kreise) oder ob die Lizenzfrage jetzt beim PO geklärt werden muss.
- **Belgien** mischt `EMMA_ID` und `NUTS2` — welche Kennung trägt welche Warnung? Zuordnung je Warnung prüfen, sonst gehen Warnungen verloren.
- **Polen** nutzt sechsstellige EMMA-Kennungen (Kreisebene, 126 aktiv) — Geometriegröße und Lookup-Performance beachten.
- **Spanien** hat 233 aktive Zonen inkl. Küstenzonen (`ES8xx`); Inseln (Balearen, Kanaren) und Exklaven (Ceuta, Melilla) müssen getroffen werden. Mallorca ist der Abnahmefall.
- **UK** Polygonweg: Landesumriss (Natural Earth) für GB + Nordirland; Grenze zu Irland (IE nicht im Scope) nicht überdecken.
- Überlappung der aufgeweiteten Umrisse bzw. Zonen an den Grenzen NL/BE, BE/DE, PL/DE, ES/PT, ES/FR — Doppelanzeige ausschließen (jede Quelle liefert nur eigene Zonen/Polygone).
- Keine nationale Bestandsquelle für diese Länder im Code (grep AEMET/IPMA/KNMI/Met Office/IMGW: kein Treffer) → kein Cross-Source-Dedup nötig.
- Sprachwahl (`es-ES`, `pt-PT`, `en-GB`, `nl-NL`, `nl-BE`/`fr-BE`, `pl-PL`) → Fallback `en*` je Land prüfen; nicht jeder Feed führt Englisch.
- Feedgröße ES/NL ~1,4 MB je 30 min — wie IT/DE, unkritisch.
- Mandantentrennung: Quelle global, keine Nutzerdaten (wie S1/S2).
- Slice-Größe: sechs Länder in einem Deploy ggf. zu groß → Analyse soll Zerlegung prüfen (z. B. S3a ES/PT mit Mallorca zuerst).

## Analysis

### Type
Feature (Issue #1442, Slice S3, Länderausbau MeteoAlarm-Feed)

### Wichtigster Befund: Spanien ist gebaut, aber nie ausgeliefert
- Branch `origin/worktree-greedy-skipping-raven` (Commits `904d33c6c` RED, `dcfa0bb79` GREEN, Adversary VERIFIED, 2026-10-30) enthält S3 Spanien inkl. Verallgemeinerung des FI-Zonenwegs zu `_zone_mappers` / `_zones_for_point(country)` / `_known_zones(country)` / `_fetch_zones(country)`.
- Kein PR (`gh pr list --head worktree-greedy-skipping-raven` leer), keine registrierte Sitzung hält den Workflow `feat-1442-s3-meteoalarm-spanien` (`workflow.py sessions`), Worktree gelöscht, Workflow-State fälschlich `phase8_complete`. `git merge-tree` gegen `origin/main` (Stand `134352b4d`): **konfliktfrei**.
- **Harte Abhängigkeit:** Dieser Workflow baut auf genau dieser Verallgemeinerung auf. ES muss **vor** der Implementierung (Phase 5) auf `main` liegen (PR aus dem Branch, CI 6/6, Deploy, Selftest), sonst entsteht eine zweite, konkurrierende Verallgemeinerung. Die ES-Auslieferung ist derselbe Epic und Claudes Aufgabe.
- **ES und Mallorca sind NICHT Teil dieses Workflows.**

### Feed-Messung 2026-10-30 (Rohdaten im Scratchpad der Sitzung `561149b3`, nicht eingecheckt)
| Land | Größe | Warnungen | Kennung | Zonen | Geometrie in `geocodes.json` | Sprachen |
|---|---|---|---|---|---|---|
| PT | 9 KB | 5 | nur EMMA_ID | 5 | 25 Features, 0 Lücken | pt-PT, en-GB |
| NL | 1,4 MB | 754, alle Stufe grün/„Minor" | nur EMMA_ID | 15 | 20 Features, 0 Lücken | nl-NL, en-GB |
| PL | 371 KB | 156 | nur EMMA_ID | 126 | 385 Features, 0 Lücken, ~273 KB vereinfacht | pl-PL, en-GB |
| UK | 25 KB | 3 | **nur Polygone**, keine Geocodes | – | fehlt (irrelevant, Polygonweg) | nur en-GB |
| BE | 240 KB | 61 | je Warnung genau eine Art: **50 nur NUTS2** (Provinzen BE21…BE35), 11 nur EMMA_ID | 8 NUTS2 + 2 EMMA | nur EMMA_ID, **keine NUTS2-Geometrie** | nl-BE, fr-BE, de-DE, en-GB |

`geocodes.json`: 39 MB, sha256 identisch zur ES/FI-Quelle; Lizenz weiterhin ungeklärt.

### Bewertung je Land
- **PT, NL, PL:** reine ES-Mechanik (Zonenweg), nur Konfiguration + Zonendatei je Land, kein Algorithmus-Umbau.
- **NL-Grünstufe:** Stufe 1 wird in `meteoalarm.py:178-180` (`level < 2: continue`) für alle Länder verworfen → kein Alarm-Spam, kein Briefing-Rauschen; nur Parse-Last (1,4 MB je 30 min, wie IT/DE).
- **UK:** Polygonweg wie NO/SE; Umriss Natural Earth GBR inkl. Nordirland; Irland unkritisch, weil Treffer nur Punkt-in-Feed-Polygon entstehen. Umrissdatei heißt `…_nordics…` → neutral benennen oder eigene Datei. Eigener Mechanismus → eigene Scheibe.
- **BE:** ohne NUTS2-Geometrie nicht lieferbar. „Nur EMMA_ID" ist **kein** stiller Verlust, sondern ein **Dauer-Fehlalarm**: NUTS2-only-Warnungen landen im Zweig „Zonenzugehörigkeit nicht bestimmbar" (`meteoalarm_feed.py:333-355`, `mark_fetch_incomplete`) → jede belgische Ortsabfrage meldet „nicht abrufbar". Lösung braucht zweite Geometriequelle (Eurostat GISCO NUTS-2021 Level 2, Attribution „© EuroGeographics", Lizenz vor Freigabe prüfen) und Mehrfach-Kennung (`_GEOCODE_NAME` von `str` auf Menge; `_emma_ids_for_alert` :215, `_area_desc` :175, Drift-Wächter :248, :316). Eigene Scheibe; bis dahin BE **nicht** registrieren.

### Empfohlener Zuschnitt
| Scheibe | Länder | Mechanik | Scope (geschätzt) |
|---|---|---|---|
| **S3a (dieser Workflow)** | **PT, NL, PL** | Zonenweg, nur Konfiguration + 3 Zonendateien | Prod ~40 LoC + Datendateien, Tests ~250 LoC + 3 Fixtures |
| S3b (Folge-Workflow) | UK | Polygonweg, GBR-Umriss | Prod ~30 LoC + Umriss, Tests ~120 LoC |
| S3c (Folge-Workflow) | BE | Zonenweg + NUTS2-Geometrie + Mehrfach-Kennung | Prod ~60 LoC + Datei, Tests ~150 LoC |

Begründung: S3b und S3c haben je einen eigenen Mechanismus; getrennt bleibt eine Regression isoliert und das LoC-Limit eingehalten.

### Affected Files (S3a, Basis = ES-Branch nach Merge)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS` (+PT/NL/PL), `_GEOCODE_NAME` (EMMA_ID), Tupel in `_zone_mappers` (:367), `Literal` (:539); veraltete Länder-Docstrings korrigieren |
| `src/services/official_alerts/data/meteoalarm_zones_PT.geojson.json` | CREATE | Auszug `geocodes.json`, `properties.id` = EMMA_ID |
| `src/services/official_alerts/data/meteoalarm_zones_NL.geojson.json` | CREATE | dito |
| `src/services/official_alerts/data/meteoalarm_zones_PL.geojson.json` | CREATE | dito (~273 KB) |
| `src/services/official_alerts/data/README.md` | MODIFY | Abschnitte PT/NL/PL: Herkunft, sha256, Vereinfachung, 1:1-Abgleich Feed-Zonen |
| `src/services/official_alerts/__init__.py` | MODIFY | Registrierung PT, NL, PL nach ES, vor `DpcSource` |
| `docs/specs/data_sources.md` | MODIFY | PT/NL/PL in den gebündelten `geocodes.json`-Lizenzantrag |
| `tests/fixtures/meteoalarm_feed/feed_{portugal,netherlands,poland}_sample.json` + `README.md` | CREATE/MODIFY | echte gekürzte Proben |
| `tests/tdd/test_meteoalarm_feed_pt_nl_pl.py` | CREATE | Kern-Verhaltenstests je Land (Muster `test_meteoalarm_feed_es.py`, Land parametrisiert) |
| `tests/tdd/test_meteoalarm_feed_pt_nl_pl_live.py` | CREATE | Live-Test gegen echte Feeds (skip, wenn keine gültige Warnung) |
| `tests/tdd/test_meteoalarm_feed_es.py` | MODIFY | ac9/ac12 Reihenfolge- und Länderprüfung erweitern statt brechen |

### Scope Assessment
- Files: ~12 (davon 3 Datendateien, 3 Fixtures)
- Estimated LoC: Prod +40/-5, Tests ~+250
- Risk Level: MEDIUM — Code folgt erprobter ES/FI-Mechanik; Risiko liegt in Geometrie an Grenzen, im Update/Cancel-Verhalten und in der ungeklärten Lizenz.

### Technical Approach
1. Vorbedingung: ES-Branch ausliefern (PR → CI 6/6 → Deploy → Selftest), Worktree danach per `merge --ff-only` auf `origin/main`.
2. PT/NL/PL als weitere Zonenländer eintragen, je Land Zonendatei aus `geocodes.json` nach ES-Rezept (README auf dem ES-Branch) erzeugen, 1:1-Abgleich Feed-Zonen ↔ Datei belegen.
3. Registrierung PT → NL → PL nach ES, vor `DpcSource` (Gewitter-Tie-Break).
4. Tests: Treffer, Küste (Land + See), nur See, Ausland schweigt (Grenzpaare PT/ES, NL/DE, NL/BE, PL/DE), Ausfall, ruhige Lage, Drift-Journal, NL-Grünstufe erzeugt nichts, Kanäle unverändert; Live-Test je Land.

### Risiken & zu prüfen in Spec/TDD
- **Update/Cancel im Zonenweg:** `_alerts_for_zone` (:292-356) kennt kein `superseded` (nur der Polygonweg). An den PL/NL-Fixtures prüfen, ob ersetzte Warnungen stehen bleiben; falls ja, kleine gemeinsame Ergänzung mit Test (wirkt auch für FI/ES).
- **Grenzüberlappung** der vereinfachten Zonen (BE/NL, NL/DE, PL/DE, PL/CZ, PL/LT, PT/ES): keine Doppel-Warnung (jeder Feed nennt nur eigene Zonen), aber `covers()` an der Grenze für zwei Länder wahr → je Grenzpaar ein Test.
- **Lizenz `geocodes.json`:** drei weitere Länder erweitern die Abhängigkeit; Antrag in `data_sources.md` bündeln.
- Mandantentrennung: Quelle global, keine Nutzerdaten (wie S1/S2/ES). Kanäle: alle vier unverändert, kein Mail-/UI-Pfad.

### Dependencies
- Upstream: ES-Branch (Verallgemeinerung Zonenweg), `feeds.meteoalarm.org` (bereits im Egress-Inventar), `_get_cached_feed` (30 min), CAP-Mapper `meteoalarm.py`, `RegionMapper`.
- Downstream: Alarm- und Briefing-Pfade Trip + Ortsvergleich über die Registry, alle vier Kanäle.

### Open Questions
- [ ] **PO (bei Spec-Freigabe per AskUserQuestion):** Lizenz der MeteoAlarm-`geocodes.json` ist weiter ungeklärt; S3a stützt drei weitere Länder darauf. Weiterbauen mit gebündeltem Antrag (wie FI/ES) oder vorher klären?
- [ ] Technisch (Spec/TDD, kein PO-Thema): Update/Cancel im Zonenweg an echten PL/NL-Fixtures prüfen.

# Context: Korsika im Radar-Nowcast auf Météo-France AROME statt ARPAE

## Request Summary

Issue #1761: Korsika (GR20) läuft im Radar-Nowcast auf dem italienischen ARPAE-ICON-2I-Modell
(2 km) statt auf dem fachlich zuständigen Météo-France AROME-FR (1,5 km), weil die
Prüfreihenfolge der Quellenkette die Italien-Bounding-Box vor der Frankreich-Bounding-Box
abfragt und Korsika komplett innerhalb der (viel größeren) Italien-Box liegt.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` | Kernstück. `_fetch_frames_with_fallback` (Zeile ~704-733) prüft die Quellenkette RADOLAN → INCA → **Italien → Frankreich** → ICON-D2 → minutely_15. `_region_bucket` (Zeile ~1205-1231) mischt **dieselbe Reihenfolge** für den Cache-Schlüssel — Docstring sagt explizit, dass sie synchron bleiben muss. `_within_italy_radar`/`_within_arome_france` (Zeile ~1181-1192) sind die betroffenen Bounding-Box-Prädikate. |
| `src/services/official_alerts/dpc.py` | **Kritische Kopplung:** importiert `_ITALY_RADAR_LAT_MIN/MAX/LON_MIN/MAX` **direkt** aus `radar_service.py` (Zeile 37-40) für `DpcSource.covers()`. Diese Konstanten dürfen für den Fix **nicht verändert** werden — sonst ändert sich stillschweigend auch die amtliche italienische Warnabdeckung. |
| `src/services/radar_cache.py` | Cache-Schlüssel nutzt `_region_bucket` — Kommentar bestätigt "dieselbe Reihenfolge wie die tatsaechliche Quellenkette". |
| `src/services/trip_alert.py:2348` | Liest den Nowcast über `_nowcast_source_key(lat, lon)` — hängt ebenfalls an `_region_bucket`. |
| `docs/specs/modules/radar_nowcast.md` | Bestehende Spec, referenziert im Datei-Docstring von `radar_service.py`. Enthält eine **Known-Limitation-Zeile**, die einen früheren PO-Stand festhält (siehe Risiken unten). |
| `docs/adr/0041-zustaendigkeit-warn-quellen-drei-muster.md` | Bestätigt explizit "Muster C": `DpcSource.covers()` darf ein zu breites Rechteck (die Italien-Box) als reinen **Vorfilter** behalten, weil `fetch()` selbst über `_zone_at()` still filtert — kein `unavailable`-Fehlalarm entsteht daraus. Das legitimiert, die Italien-Box unverändert zu lassen und stattdessen einen eigenen, vorgeschalteten Korsika-Check einzuführen. |
| `tests/tdd/test_dpc_official_alert_bbox.py` | **Harter Regressionswächter**: prüft `DpcSource().covers(42.1244, 9.1339)` (Vizzavona/Korsika) `== True` und muss es bleiben — Beleg, dass die Italien-Box-Konstanten nicht angetastet werden dürfen. |

## Existing Patterns

- **Bounding-Box-Vorfilter mit Fail-Soft-Kette**: jede Quelle prüft `_within_X(lat, lon)`, ruft bei Treffer ab, fällt bei leerem Ergebnis (`if frames: return`) zur nächsten Quelle durch. Neue Quellen/Sonderfälle docken nach demselben Muster an (vgl. ADR-0041, Muster C).
- **Region-Bucket muss die Fetch-Reihenfolge spiegeln** (explizit im Docstring von `_region_bucket` dokumentiert) — Änderungen an der Fetch-Kette MÜSSEN an beiden Stellen erfolgen, sonst kann der Cache eine Koordinate der falschen Quelle zuordnen.
- **Geteilte Konstanten zwischen Nowcast-Routing und Warn-Zuständigkeit**: `dpc.py` importiert Radar-Bbox-Konstanten statt sie zu duplizieren — bewusste Kopplung (Kommentar im Test), aber genau deshalb ein Risiko bei jeder Änderung an diesen Konstanten.
- Bereits real gemessene Korsika-Ausdehnung aus einer echten AROME-Antwort (Test-Fixture-Kommentar, `tests/tdd/test_thunder_signal_enrichment.py` u.a.): **41,30–43,11 N / 8,39–9,60 O** — deckt sich mit dem im Issue vorgeschlagenen Rechteck (41,3–43,1 N / 8,4–9,6 O).

## Dependencies

- **Upstream:** `_fetch_arome_france_hd` (bereits vorhanden, ruft Open-Meteo `models=arome_france_hd`), `_fetch_italy_arpae` (unverändert für echtes Italien nötig).
- **Downstream:** `trip_alert.py` (Alarm-Pfad, Stufe "akut" hängt am Nowcast-Ergebnis), `radar_cache.py` (Cache-Korrektheit), `official_alerts/dpc.py` (darf NICHT betroffen sein).

## Existing Specs

- `docs/specs/modules/radar_nowcast.md` — Hauptspec, Known-Limitations-Abschnitt braucht eine neue Zeile.
- `docs/specs/modules/radar_nowcast_france.md`, `radar_nowcast_italy_arpae_fallback.md` — Detailspecs der beiden betroffenen Zweige.
- `docs/specs/modules/fix_1648_radar_dpc_entfernen.md` — Ursprung der heutigen Italien-Box-Konstanten und des expliziten Kommentars "Korsika ist französisch ... Prüfreihenfolge, keine fachliche Entscheidung".

## Risks & Considerations

1. **🔴 Dokumentierter PO-Stand widerspricht scheinbar dem Issue.** `radar_nowcast.md` Zeile 128 schreibt: *"Für Italien (inkl. Korsika, PO-Entscheidung 2026-07-09) liefert seit Issue #1648 ausschließlich ARPAE ICON-2I ... den Nowcast."* Issue #1761 (später, 2026-08-12, ebenfalls `[triage:po]`) stellt das explizit als *unbeabsichtigten Reihenfolge-Effekt* dar, nicht als fachliche Entscheidung, und verweist auf #1648 selbst, wo dieser Punkt schon als offene Frage festgehalten war ("Korsika ist französisch; dass die italienische Box vorher greift, ist eine Folge der Prüfreihenfolge, keine fachliche Entscheidung"). Die neuere, spezifischere und mit Messung belegte PO-Aussage sticht die ältere pauschale Formulierung — trotzdem muss die Spec-Phase das explizit als **Korrektur einer dokumentierten Aussage** benennen (Known-Limitations-Zeile aktualisieren, ggf. Changelog-Eintrag in der Spec), nicht stillschweigend überschreiben.
2. **Zwei Call-Sites müssen synchron geändert werden** (`_fetch_frames_with_fallback` UND `_region_bucket`) — sonst behauptet der Cache-Schlüssel eine andere Quelle als tatsächlich abgerufen wurde. Das ist die naheliegende Adversary-Mutation.
3. **Bestehende Konstanten (`_ITALY_RADAR_*`) dürfen nicht verändert werden** — wegen der Kopplung zu `DpcSource.covers()` und dem harten Regressionstest. Lösung: neues, eigenständiges Korsika-Rechteck, das VOR der Italien-Prüfung greift, ohne die Italien-Box selbst zu verkleinern.
4. **Sardinien darf nicht mitgenommen werden** (Issue nennt das explizit) — Trennung über den Breitengrad bei ~41,3 N (Straße von Bonifacio). Braucht Grenzwert-Tests unmittelbar links/rechts der Trennlinie.
5. **Globaler Tausch der Boxen ist explizit verboten** (Issue-Text) — Frankreich-Box überlappt mit Italien im Bereich Ligurien/Piemont/Westlombardei; die müssen italienisch bleiben.
6. **Offene Fallback-Frage** (im Issue als "zu prüfen" markiert, noch nicht entschieden): Fällt eine Korsika-Koordinate bei AROME-FR-Ausfall auf ARPAE zurück oder direkt auf `minutely_15`? Für die Spec-Phase zu klären — naheliegend: Durchfallen zur bisherigen Kette (ARPAE dann `minutely_15`) für gleiche Ausfalltiefe wie zuvor, aber das ist eine Produktentscheidung, kein Automatismus.
7. **Keine bestehende Coverage-Prüfung für Ostküste/Conca** (GR20-Endpunkt) — laut Issue im Vorgängerprojekt bereits eine bekannte Fehlerquelle (fehlende Bbox im GetCapabilities-XML). Sollte als Testfall mitgeführt werden, auch wenn nur als Geometrie-Check (kein Live-Call in der Kernschicht).

## 🔴 KRITISCHER BEFUND (Live gemessen 2026-09-20): `arome_france_hd` liefert STRUKTURELL keinen `weather_code`

Das Issue misst nur Frame-Anzahl und Horizont ("96 Frames, 95 in der Zukunft") — genau diese
zwei Spalten sehen den folgenden Effekt nicht. Live gegen die echte Open-Meteo-API getestet
(`https://api.open-meteo.com/v1/forecast`, `minutely_15=precipitation,weather_code`,
`forecast_minutely_15=96`), 2026-09-20:

| Koordinate | Modell | non-null `precipitation` | non-null `weather_code` |
|---|---|---|---|
| Vizzavona `42.1244/9.1339` | `arome_france_hd` | 96/96 | **0/96** |
| Vizzavona `42.1244/9.1339` | `italia_meteo_arpae_icon_2i` (Ist-Zustand) | 96/96 | 96/96 |
| Conca (GR20-Ostküste) `41.7481/9.3548` | `arome_france_hd` | 96/96 | **0/96** |

Conca ist geometrisch abgedeckt (Niederschlag vorhanden) — das ist **nicht** dieselbe Lücke wie
die im Vorgängerprojekt dokumentierte fehlende Bbox. Es ist strukturell: `arome_france_hd` liefert
auf dem `minutely_15`-Endpunkt von Open-Meteo an KEINER getesteten Korsika-Koordinate einen
Wettercode.

**Warum das trägt:** `radar_service.py:857` fragt `minutely_15=precipitation,weather_code` ab.
`:875` (All-None-Guard) prüft nur `precip_vals`, nicht `wcodes` — er greift hier NICHT, weil
Niederschlag voll befüllt ist. Frames werden also reibungslos erzeugt, aber mit `code=None`.
`:888/891` leiten `is_convective`/`hail` ausschließlich aus `code in (95,96,99)` bzw. `(96,99)` ab
(`:469-475`) — mit `code=None` ist das für JEDEN Frame `False`. Der Unterschied zeigt sich in
KEINER der beiden vom Issue gemessenen Spalten (Frame-Anzahl, Horizont), nur im Wettercode selbst.

**Downstream-Wirkung ist kein Nebeneffekt, sondern der Alarm-Pfad:** `trip_alert.py:2271/2411`
speist `is_convective` direkt in `resolve_hazard_class()` ein — das ist die akute
Gewitter/Hagel-Alarmklassifizierung. Ein Wechsel auf AROME-FR würde also nicht nur "etwas
schärfer, aber gleichwertig" liefern, sondern für die **gesamte** Korsika-Nowcast-Strecke
(GR20) die Gewitter-/Hagel-Erkennung aus dem Radar-Nowcast strukturell auf "nie" setzen — bei
unverändertem Niederschlagsbild. Das ist derselbe Fehlermodus, den
[[reference_arome_ist_bei_uns_nur_ein_name_kein_modell]] bereits für die allgemeine
Wettercode-/Gewitterableitung gemessen hat (dort: `arome_france_hd` liefert über Open-Meteo
keinen `weather_code`, keinen `precipitation_probability`), hier zusätzlich bestätigt für den
`minutely_15`-Nowcast-Zweig speziell.

**Bestehendes Muster für einen Ausweg — mit echten Kosten:** `_merge_convective` (`:783-792`)
mischt bereits `is_convective` aus einer Sidecar-Quelle in die Frames einer anderen Quelle
(INCA + globaler `best_match`-Sidecar). Ein analoges Muster (AROME-FR für Niederschlag + ARPAE
oder `best_match` als Sidecar für `is_convective`/`hail`) wäre technisch möglich, kostet aber
einen **zweiten** Aufruf durch `_fetch_openmeteo_15` — den EINZIGEN budget-gegateten Funnel
(#1329 C2). Schlägt das Budget-Gate den Sidecar-Call ab, oder ist
`_openmeteo_unavailable_this_call` in diesem Aufruf schon gesetzt, entstehen AROME-Frames mit
durchgängig `is_convective=False` und OHNE das ADR-0018-Signal, das der INCA-Pfad an dieser
Stelle bewusst über `self._convective_checked = False` (`:775-776`) setzt. Jede Sidecar-Lösung
muss diese Behandlung mit übernehmen, sonst wird ein echter Ausfall lautlos als "kein Gewitter"
interpretiert.

**Reframing von Risiko 1 oben:** Die ältere, dokumentierte PO-Aussage (`radar_nowcast.md:128`,
"Italien inkl. Korsika liefert ARPAE") ist damit nicht einfach eine veraltete Formulierung, die
korrigiert gehört — sie hat sich als **unbeabsichtigte Tugend** herausgestellt: ARPAE liefert an
derselben Stelle einen echten Wettercode, AROME-FR nicht. Die neuere, spezifischere Forderung
aus #1761 hat einen Preis, den der ältere Zustand nicht hatte — nicht umgekehrt "der ältere
Zustand war einfach falsch".

**Offene Produktfrage statt technischer Detailfrage:** Für Korsika ist eine schärfere
Niederschlags-Auflösung (1,5 km statt 2 km) gegen den Verlust der Gewitter-/Hagel-Kennung aus dem
Radar-Nowcast abzuwägen — und zwar ausgerechnet auf der Strecke, die Epic #1419 (Auslöser
2026-08-02, GR20-Gewittertag) betrifft.

## Analysis

### Type
Feature (fachliche Korrektur einer Quellenzuordnung, PO-Triage: "keine Fehlfunktion")

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/radar_service.py` | MODIFY | Neues Korsika-Rechteck vor der Italien-Prüfung in `_fetch_frames_with_fallback` UND `_region_bucket` (synchron, siehe Docstring-Pflicht) — Umfang hängt an der PO-Entscheidung unten (reine Umschaltung vs. Sidecar-Merge) |
| `docs/specs/modules/radar_nowcast.md` | MODIFY | Known-Limitations-Zeile 128 aktualisieren — nicht als Korrektur einer falschen Aussage, sondern als bewusste Abwägung (siehe Kritischer Befund) |
| `tests/tdd/test_dpc_official_alert_bbox.py` | KEEP (Regressionswächter) | Muss unverändert grün bleiben — Beleg, dass `_ITALY_RADAR_*` nicht angetastet wurden |
| `tests/tdd/` (neu) | CREATE | Grenzwerttest ~41,3°N (Straße von Bonifacio, Sardinien-Abgrenzung), Wirkungstest an Korsika-Koordinate, bei Sidecar-Variante zusätzlich ein Test der `is_convective`/`hail`-Übernahme |

### Scope Assessment
- Files: 2 Kern-Dateien + 1 Spec + neue Tests
- Estimated LoC: +40/-5 bis +90/-5, je nachdem ob reine Umschaltung oder Sidecar-Merge (siehe Risiken)
- Risk Level: **HOCH** (nicht LOW/MEDIUM) — die im Issue vorgeschlagene Lösung hat einen bislang unentdeckten Nebeneffekt auf den Alarm-Pfad (siehe Kritischer Befund oben)

### Technical Approach

**Die im Issue vorgeschlagene Lösung ("Korsika-Rechteck vor Italien einschieben, sonst nichts ändern") ist nicht ohne Weiteres umsetzbar**, weil sie die Gewitter-/Hagel-Erkennung aus dem Radar-Nowcast für ganz Korsika strukturell auf "nie" setzen würde — siehe der oben dokumentierte Live-Befund vom 2026-09-20 (`weather_code` bei `arome_france_hd` an keiner getesteten Korsika-Koordinate befüllt, `is_convective`/`hail` daraus abgeleitet, fließt direkt in `resolve_hazard_class()` im Alarm-Pfad `trip_alert.py:2271/2411`).

Zwei technisch gangbare Wege, beide mit Kosten:

1. **Reine Umschaltung (Issue-Wortlaut):** Korsika bekommt die schärfere Niederschlagsauflösung (1,5 km), verliert aber die Gewitter-/Hagel-Kennung aus dem Radar-Nowcast vollständig. Geringster Aufwand, aber eine stille Funktionsreduktion auf der Strecke, die Epic #1419 ausgelöst hat.
2. **Sidecar-Merge (Muster bereits vorhanden, `_merge_convective`):** AROME-FR liefert Niederschlag, eine zweite Quelle (ARPAE oder globaler `best_match`) liefert `is_convective`/`hail` als Sidecar — analog zum bestehenden INCA+Sidecar-Muster. Erhält die Gewittererkennung, kostet aber einen zweiten Aufruf durch den budget-gegateten `_fetch_openmeteo_15`-Funnel (#1329 C2) und muss bei Sidecar-Ausfall das ADR-0018-Signal (`_convective_checked = False`) genauso behandeln wie der INCA-Pfad — sonst wird ein Ausfall lautlos als "kein Gewitter" gedeutet.

**Empfehlung:** vor der Spec-Phase eine PO-Entscheidung zwischen (1) und (2) einholen — das ist eine Produktabwägung (schärferes Regenbild vs. Gewitter-/Hagel-Sicherheit auf dem GR20), keine rein technische Wahl.

### Dependencies
- **Upstream:** `_fetch_arome_france_hd` (bereits vorhanden), `_fetch_italy_arpae` (unverändert für echtes Italien nötig), bei Variante 2 zusätzlich ein zweiter Sidecar-Fetch durch denselben `_fetch_openmeteo_15`-Funnel.
- **Downstream:** `trip_alert.py` (Alarm-Pfad `resolve_hazard_class`, Stufe "akut"), `radar_cache.py`/`_region_bucket` (Cache-Korrektheit), `official_alerts/dpc.py` (darf NICHT betroffen sein).

### Open Questions
- [ ] **Produktfrage an Henning:** Für Korsika ein schärferes Regenbild (1,5 km statt 2 km) gegen den Verlust der Gewitter-/Hagel-Kennung aus dem Radar-Nowcast — oder beides behalten (höherer technischer Aufwand, zweiter Datenabruf pro Anfrage)? Ausgerechnet die Strecke, um die es in Epic #1419 (GR20-Gewittertag 2026-08-02) geht.

### PO-Entscheidung 2026-09-20

**Sidecar-Merge (Variante 2).** Korsika bekommt die schärfere AROME-FR-Niederschlagsauflösung
(1,5 km), die Gewitter-/Hagel-Kennung wird per Sidecar-Merge (analog `_merge_convective`,
`radar_service.py:783-792`) aus einer Quelle mit echtem `weather_code` (ARPAE oder globaler
`best_match`) ergänzt — nicht ersatzlos aufgegeben. Der zusätzliche Aufruf durch den
budget-gegateten `_fetch_openmeteo_15`-Funnel (#1329 C2) und die ADR-0018-Fail-Soft-Behandlung
bei Sidecar-Ausfall (`_convective_checked = False` analog INCA-Pfad, `:775-776`) sind für
`/30-write-spec` verbindlicher Bestandteil, kein optionaler Ausbau.

# Context: gewitter-1679-lpi-schwellen

## Request Summary

Issue #1679 (Rang 2 aus dem Gewitter-Gesamtkonzept #1419, `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.5b/11): Die Blitzpotenzial-Schwellenleiter (LPI, DWD ICON-D2) steht heute auf 5/20/50 J/kg, davon ist die mittlere Schwelle (20) nicht belegt, sondern interpoliert. Belegt (Bína et al., Atmospheric Research 2022 / ASR Copernicus 2022, COSMO-D2 — dieselbe Modellfamilie wie ICON-D2) ist stattdessen **1/30/50 J/kg**.

Der CIN-Paarungs-Teil von #1679 hängt an #1531 (liefert `cin_ml`, Spec-Freigabe offen) und ist **nicht** Teil dieses Workflows.

**PO-Entscheidung (2026-08-10, während der Analyse):** Die Schwelle darf nicht blind global gelten — das Europa-Lückenfüller-Modell (ICON-EU, `lpi_con_max`) teilt sich heute denselben Wert/dieselbe Ladder wie ICON-D2, liefert aber strukturell deutlich höhere Werte (gemessener Faktor 51× am unteren Ende, Issue #1678). Eine reine Konstanten-Änderung würde die Fehlalarmquote für alle Orte außerhalb Alpen/Frankreich sofort verschlechtern. Beschlossen: **gebietsabhängige Tabelle**, analog zum bestehenden CAPE-Muster — ICON-D2-Gebiet bekommt sofort 1/30/50, ICON-EU-Gebiet bleibt vorerst auf 5/20/50, bis #1678 dafür eine eigene, eingemessene Leiter liefert.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/metric_format.py:284-293` | Modul-Konstanten `_LIGHTNING_POTENTIAL_LOW_MIN/MED_MIN/HIGH_MIN` (5/20/50) — Ziel der Korrektur; Kommentar dokumentiert die 20 als "nicht publiziert, interpoliert" (muss aktualisiert werden) |
| `src/output/metric_format.py:296-312` | `_thunder_level_from_ladder()` — generische Drei-Schwellen-Übersetzung, geteilt von Blitzdichte UND Blitzpotenzial. Bleibt unverändert, bekommt aber die Schwellen künftig als Parameter statt aus Modul-Konstanten |
| `src/output/metric_format.py:315-371` | `thunder_level_from_signals()` — Fusionspunkt. Ruft `_thunder_level_from_ladder()` für `lightning_potential_jkg` mit den drei Modul-Konstanten auf (Zeile 363-367). Muss künftig drei zusätzliche keyword-only Parameter annehmen (Muster `cape_threshold_jkg`, KEIN Default — Issue #1592 C1) |
| `src/app/model_registry.py:1-170` | **Vorbild-Muster**: `CAPE_THRESHOLDS_JKG: Dict[Tuple[model_id, region], float]` + `cape_threshold_jkg()`, einmal je Reihe aufgelöst in `enrich_thunder()`. Fehlende Kalibrierung → `None`, nie ein geratener Ersatzwert |
| `src/providers/thunder_routing.py:63-98` | `_REGIONS` (FR/DE_ALPEN/EU_REST, first-match-wins) + `thunder_region_for(lat, lon)` — bereits vorhandene, deterministische Gebietszuordnung. Region bestimmt eindeutig, welche Quelle das LPI-Signal liefert (DE_ALPEN → ICON-D2 `de_direct`, EU_REST → ICON-EU `eu_direct`) — **kein neues Raster nötig**, für LPI reicht die Region allein (anders als bei CAPE braucht es hier keinen `model_id`, da die Region das Modell für LPI bereits eindeutig fesstlegt) |
| `src/providers/thunder_enrichment.py:84-187` | `_fuse_thunder_levels()` / `enrich_thunder()` — ruft `thunder_level_from_signals()` auf. `enrich_thunder()` löst bereits `thunder_region_for(location.latitude, location.longitude)` für CAPE auf (Zeile 181) — dieselbe Auflösung kann für die LPI-Schwelle mitgenutzt werden |
| `tests/tdd/test_dwd_eu_thunder_signal_fetch.py:361-395` | Nutzt die Modul-Konstanten dynamisch (kein hartkodierter Wert) — bricht nicht allein durch die Zahlenänderung, muss aber ggf. um den Region-Parameter ergänzt werden |
| `tests/tdd/test_thunder_ladder_shared_across_signals.py:47-112` | Prüft, dass Blitzdichte und Blitzpotenzial dieselbe `_thunder_level_from_ladder()`-Funktion nutzen (DRY-Wächter, #1481). Muss mit den neuen Parametern kompatibel bleiben |
| `docs/features/gewitter-gesamtkonzept.md:270-330` | Führendes Konzeptdokument, Abschnitt 3.5b (Beleg), 3.7 (Zielverfahren — nennt ICON-EU explizit als "eigene Leiter — zu eichen (Rang 7), bis dahin nicht gleichwertig"), Abschnitt 11 (Fahrplan, heute korrigiert) |

## Existing Patterns

- **Modell-/gebietsabhängige Eichtabelle statt globaler Konstante** (`model_registry.CAPE_THRESHOLDS_JKG`): `(key) -> Schwelle`, fehlender Eintrag = `None` = "nicht belegt", nie ein geratener Ersatzwert. Für LPI reicht `region -> (low, med, high)` als Schlüssel (kein `model_id` nötig, s.o.).
- **Keyword-only Parameter ohne Default** an der Fusionsfunktion (`cape_threshold_jkg`, Issue #1592 C1): erzwingt, dass jeder Aufrufer — auch Tests — die Herkunft bewusst nennt, kein stiller Rückfall auf einen falschen Wert.
- **Einmal je Reihe auflösen, nicht je Datenpunkt** (`enrich_thunder()` löst `cape_threshold_jkg`/Region einmal auf und reicht sie durch `_fuse_thunder_levels()` an jeden Datenpunkt weiter).
- **`_thunder_level_from_ladder()` bleibt die einzige if/elif-Kette** (DRY-Pflicht #1481) — die Korrektur ändert nur, WELCHE drei Zahlen hineingereicht werden, nicht die Übersetzungslogik selbst.

## Dependencies

- **Upstream:** `thunder_routing.thunder_region_for()` (bereits vorhanden, unverändert nutzbar), `docs/features/gewitter-gesamtkonzept.md` Abschnitt 3.5b/3.7 als Beleg-Quelle für 1/30/50.
- **Downstream:** `thunder_level_from_signals()` wird von E-Mail-/SMS-/Telegram-Renderern, Ortsvergleich und Alarmen indirekt über `dp.thunder_level` konsumiert (nicht direkt aufgerufen) — Änderung wirkt sich auf jede Ausgabe aus, die die Gewitterstufe zeigt.
- **Nicht Teil dieses Workflows:** #1531 (liefert `cin_ml`, CIN-Paarung), #1678 (eigene, geeichte Leiter für ICON-EU/`lpi_con_max` — dieser Workflow liefert nur die Tabellen-Infrastruktur und den unveränderten Interims-Wert für EU_REST, nicht die Eichung selbst).

## Existing Specs

- Keine dedizierte Spec zu #1474c (Blitzpotenzial als viertes Signal) unter `docs/specs/modules/` gefunden auf den ersten Blick — `thunder_level_from_signals()`-Docstring referenziert Issue #1474c/#1592 C1 als Quelle der Anforderungen. Wird in der Spec-Phase genauer geprüft.
- `docs/adr/` — ADR-0025 (Blitzpotenzial als eigene Skala) und ADR-0048 (CAPE-Modellschwelle, Vorbild-Muster) sind relevant.

## Risks & Considerations

- **Gefundenes und vom PO entschiedenes Risiko:** globale Konstanten-Änderung hätte ICON-EU-Gebiet (Resteuropa) verschlechtert → gebietsabhängige Tabelle beschlossen (s.o.).
- Der Modul-Kommentar zu den Konstanten (Zeilen 284-290) behauptet aktuell "20 J/kg NICHT publiziert, interpoliert" — muss durch den neuen Beleg (Bína et al.) ersetzt werden, sonst widerspricht der Code-Kommentar der neuen Datenlage.
- Bestehende Tests, die die Modul-Konstanten importieren (`mf._LIGHTNING_POTENTIAL_LOW_MIN` etc.), funktionieren weiter, wenn die Konstanten als Fallback/Default für "kein Region bekannt" erhalten bleiben — muss in der Spec entschieden werden, ob es einen expliziten "unbekannte Region"-Fall gibt oder ob die Namen umbenannt werden (Breaking Change für die zwei Testdateien, die sie importieren).
- Mutations-Gegenprobe (Pflicht laut CLAUDE.md): muss zeigen, dass ein vertauschter Region-Schlüssel (z. B. EU_REST bekommt versehentlich 1/30/50) von einem Test gefangen wird — das ist genau der Fehler, den die heutige PO-Entscheidung verhindern soll.

## Analysis

### Type
Feature (Korrektur einer erfundenen/interpolierten Schwelle auf belegte Werte + strukturelle Vorbeugung gegen eine neu erkannte Nebenwirkung).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/model_registry.py` | MODIFY | Neue Tabelle `LPI_THRESHOLDS_JKG: Dict[str, Tuple[float, float, float]]` (Schlüssel: Region `FR`/`DE_ALPEN`/`EU_REST`) + `lpi_thresholds_jkg(region)`-Lookup, analog `CAPE_THRESHOLDS_JKG`/`cape_threshold_jkg()`. `DE_ALPEN → (1.0, 30.0, 50.0)`, `EU_REST → (5.0, 20.0, 50.0)` (unverändert, Interim bis #1678), `FR` ohne Eintrag (AROME liefert Blitzdichte, kein LPI) |
| `src/output/metric_format.py` | MODIFY | `thunder_level_from_signals()` bekommt drei neue keyword-only Parameter (`lpi_low_min`, `lpi_med_min`, `lpi_high_min`, kein Default) für den LPI-Zweig statt der Modul-Konstanten `_LIGHTNING_POTENTIAL_*`; Kommentar zu den alten Konstanten wird durch den neuen Beleg (Bína et al.) ersetzt oder die Konstanten werden zum expliziten "Region unbekannt"-Fallback |
| `src/providers/thunder_enrichment.py` | MODIFY | `enrich_thunder()` löst zusätzlich `lpi_thresholds_jkg(thunder_region_for(...))` auf (Region ist dort bereits aufgelöst für CAPE) und reicht die drei Werte durch `_fuse_thunder_levels()` an `thunder_level_from_signals()` durch |
| `tests/tdd/test_dwd_eu_thunder_signal_fetch.py` | MODIFY | Referenziert die Modul-Konstanten — an neue Signatur/Werte anpassen |
| `tests/tdd/test_thunder_ladder_shared_across_signals.py` | MODIFY | Prüft die DRY-Nutzung von `_thunder_level_from_ladder()` — muss mit den neuen Parametern weiterlaufen |
| `tests/tdd/test_thunder_level_from_signals_fusion.py`, `test_thunder_potential_level_classification.py`, `test_cape_not_selectable.py` | CHECK | Rufen `thunder_level_from_signals()` mit den bisherigen Positions-/Keyword-Argumenten auf — je nach gewählter Signatur ggf. Anpassung nötig |
| `docs/specs/modules/` | CREATE | Neue oder erweiterte Spec (wird in Phase 3 geprüft, ob eine bestehende Spec zu #1474c/#1592 C1 erweitert werden kann) |

### Scope Assessment
- Files: ~6-8 (3 Quelldateien, 3-5 Testdateien)
- Estimated LoC: ~ +60/-15 (neue Tabelle + Lookup-Funktion + Parameter-Durchreichung + Test-Anpassungen; unter dem 250-LoC-Workflow-Limit)
- Risk Level: MEDIUM (Blast Radius: mehrere Ausgabekanäle zeigen die Gewitterstufe; Mitigation: bestehendes, bereits produktiv gehärtetes Muster wird 1:1 wiederverwendet, kein neuer Mechanismus)

### Technical Approach
Region-Tabelle statt globaler Konstante, exakt nach dem Vorbild `model_registry.CAPE_THRESHOLDS_JKG`/`cape_threshold_jkg()` (Issue #1592 C1). Da `thunder_routing._REGIONS` das Blitzpotenzial-liefernde Modell bereits deterministisch über die Region festlegt (`DE_ALPEN` → ICON-D2, `EU_REST` → ICON-EU, `FR` → kein LPI), genügt ein Lookup nach Region allein — kein zusätzlicher `model_id`-Schlüssel wie bei CAPE nötig, das vereinfacht die neue Tabelle gegenüber dem Vorbild. `enrich_thunder()` hat die Region-Auflösung für CAPE bereits im Zugriff (`thunder_region_for(location.latitude, location.longitude)`, Zeile 181) und kann sie für den LPI-Lookup mitverwenden — kein zweiter Auflösungs-Ort.

### Dependencies
- Kein Abhängigkeit zu #1531 (der CIN-Teil von #1679 bleibt außen vor).
- #1678 (ICON-EU-eigene Leiter) wird durch diesen Workflow NICHT vorweggenommen — die neue Tabelle bekommt für `EU_REST` lediglich den unveränderten Interim-Wert (5/20/50); #1678 wird dadurch später zu einer reinen Tabellen-Ergänzung ohne weitere Plumbing-Arbeit.

### Open Questions
- [x] Umgang mit ICON-EU während der Übergangszeit — vom PO entschieden: gebietsabhängige Tabelle, ICON-EU unverändert (s. oben).
- [ ] Sollen die alten Modul-Konstanten `_LIGHTNING_POTENTIAL_*` als benannter "Region unbekannt"-Fallback erhalten bleiben, oder ist "Region unbekannt" für LPI ein strukturell unerreichbarer Fall (wie bei `thunder_region_for`, das laut Docstring nie `None` liefert, weil `EU_REST` die ganze Welt abdeckt)? Wird in der Spec-Phase entschieden.

## Nächster Schritt

Technischer Ansatz ist geklärt (gebietsabhängige Tabelle, Muster `CAPE_THRESHOLDS_JKG`). Weiter mit `/30-write-spec`.

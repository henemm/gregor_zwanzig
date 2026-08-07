# Context: 1506-hagel-schwelle-dwd

## Request Summary

Folge-Scheibe S5b zu #1475 (Epic #1419): Aus dem bereits vorhandenen DWD-Rohwert
`hail_potential_grau_gsp` (nur DE/Alpen/Österreich, Provider `de_direct`) soll ein
echtes `hail_flag=False` ("nein") abgeleitet werden — S5a (#1475, live) kann `hail_flag`
technisch nur `True`/`None` liefern, nie `False`. Voraussetzung ist eine **veröffentlichte**
DWD-Schwelle/Einheit für `grau_gsp` (keine eigene Kalibrierung, PO-Vorgabe analog #1456).

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py:161,178,442-445` | `ForecastDataPoint.hail_potential_grau_gsp` (Rohwert, seit #1457 S2b befüllt) und `hail_flag` (Kennzeichen, seit #1475 S5a); `SegmentWeatherSummary.hail_flag` mit `aggregation_config = {"hail_flag": "hail_priority"}` |
| `src/providers/openmeteo.py:645,848` | `_parse_hail_flag(weather_code)` — EINZIGE heutige Quelle von `hail_flag` (WMO 96/99 → `True`, sonst `None`). Grau_gsp fließt hier NICHT ein |
| `src/providers/thunder_enrichment.py` | Gemeinsamer Anschlusspunkt für Gewittersignale (`_SIGNAL_ZU_FELD`, `enrich_thunder()`). Befüllt `hail_potential_grau_gsp` bereits; hat noch KEINE Funktion, die daraus `hail_flag` ableitet (Analogon zu `_fuse_thunder_levels()`, das aber nur `thunder_level` betrifft, nicht `hail_flag` — Kommentar Zeile ~88 hält das explizit fest) |
| `src/providers/dwd.py:75-120` | `THUNDER_PARAMS=("lpi","grau_gsp")`, Fehlwert-Marker `9999.0`, Kumulations-Rückrechnung `_precip_series_from_cumulative` (grau_gsp ist seit Laufbeginn kumuliert, wie `tot_prec`) |
| `src/output/metric_format.py:382-410` | `hail_priority(values)` (ja>unbekannt>nein, **bereits `False`-fähig**), `format_hail_note(hail_flag)` (nur bei `True` Text, sonst kein Zusatztext — ADR-0007) |
| `src/services/weather_metrics.py:610-623,1141-1155` | `_compute_hail_flag()` (Level-1, ruft `hail_priority()` über rohe Punktwerte); `aggregate_stage()` Level-2 — **Sonderzweig für `agg_rule=="hail_priority"` bereits VOR dem generischen `is not None`-Vorfilter** (s. Risks) |
| `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` | Vorgänger-Spec (S5a), Referenzmuster für Feld-Semantik, AC-Format, Renderer-Anbindung an allen 9 Ausgabeorten |
| `docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md:95-103` | **Präzedenzfall für publizierte Schwellen**: Blitzpotenzial-Grenzen 5 J/kg (DWD-Betriebsschwelle) / 50 J/kg (obere Verifikationsspanne) mit Quellenangabe als Code-Kommentar (`asr.copernicus.org`, DWD-ICON-Bericht-PDF); 20 J/kg explizit als NICHT publiziert, sondern interpoliert gekennzeichnet — Vorbild für den Umgang mit `grau_gsp` |
| `docs/reference/decision_matrix.md:90-95` | Hagel dockt NICHT als fünftes Fusionssignal an `max_thunder()`/`thunder_level_from_signals()` an — bleibt eigenständiges Kennzeichen, anders als `lightning_potential_lpi_jkg` (#1474c) |
| `src/providers/thunder_routing.py:63-67` | `_REGIONS`, Eintrag `DE_ALPEN` (BBox → `de_direct`) — bestimmt, wo überhaupt `hail_potential_grau_gsp` befüllt wird; first-match-wins, ein Provider pro Ort |
| Alle 9 Ausgabeorte aus `reference_weather_metric_has_many_output_locations` (Memory) | Konsumieren `hail_flag` bereits fertig verdrahtet (S5a-Nachbesserung, Commit `7733d2fd`) — bei reiner Ableitungs-Änderung (WMO+Schwelle statt nur WMO) vermutlich **keine** Renderer-Änderung nötig, nur Verifikation, dass `False` überall korrekt "kein Zusatztext" ergibt |

## Existing Patterns

- **Schwellen-Dokumentationsmuster (#1474c):** Konstanten mit Kommentarblock,
  der Quelle(n) als URL nennt, "publiziert" vs. "interpoliert" explizit
  unterscheidet, PO-Freigabe-Datum im Kommentar.
- **Ein gemeinsamer Anschlusspunkt für Gewittersignale** (`thunder_enrichment.py`,
  ADR analog "keine Einzellösungen") — eine neue Ableitungsregel für `hail_flag`
  aus `grau_gsp` sollte dort andocken, nicht in `openmeteo.py` oder einem Renderer.
- **Drei-wertige Priorität ja>unbekannt>nein** (`hail_priority()`) ist bereits
  fertig und wurde in Vorbereitung auf S5b/S5c geschrieben (Docstring erwähnt
  ausdrücklich "erwartet die ROHEN Werte").
- **Region-Gating** existiert schon strukturell über `thunder_routing._REGIONS`
  (`DE_ALPEN`) — dieselbe Zuständigkeit, die `grau_gsp` überhaupt befüllt, grenzt
  automatisch auch die neue Ableitung ein (kein zusätzlicher Gating-Mechanismus
  nötig).

## Dependencies

- **Upstream:** #1475 S5a (live, Commit `2a72175b` + Nachbesserung `7733d2fd`),
  #1457 S2b (`grau_gsp`-Rohdatenpfad, live), ADR-0007 (Daten statt Empfehlungen,
  bindend für die Anzeige).
- **Downstream:** Alle 9 Ausgabeorte des Hagel-Kennzeichens (E-Mail, SMS, Telegram,
  Compare, Mehrtages-Vorschau …) — konsumieren `hail_flag`, nicht `grau_gsp`
  direkt; erwarten daher keine Struktur-, nur Werte-Änderung.

## Existing Specs

- `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` (S5a, Vorgänger, Referenzmuster)
- `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` (Rohdaten-Herkunft `grau_gsp`)
- `docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md` (Schwellen-Dokumentationsmuster)

## Risks & Considerations

- **PFLICHT-Recherchefrage zuerst klären, bevor überhaupt gebaut wird:** Gibt es
  eine veröffentlichte DWD-Schwelle/Einheit für `grau_gsp` (Graupel-Akkumulation,
  ICON-D2)? Kein bestätigter Treffer bisher im Repo/in der Doku. Scheitert die
  Recherche, ist die Scheibe nicht wie geplant umsetzbar — PO-Rückmeldung nötig,
  keine eigene Kalibrierung als Ausweg (ausdrücklich verboten, PO-Vorgabe).
- **Korrektur zur Issue-Beschreibung:** Die im Issue als offene Vorbedingung
  genannte "Known Limitation 3" aus der S5a-Spec (Vorfilter in `aggregate_stage()`
  entfernt `None` vor der `hail_priority`-Regel) ist **bereits im S5a-Commit
  `2a72175b` behoben** (`weather_metrics.py:1141-1155`, eigener Zweig VOR dem
  generischen Filter). Die S5a-Spec selbst wurde nach der Implementierung nicht
  nachgezogen und listet das Limitation-Item fälschlich weiter als offen. Für
  S5b bedeutet das: dieser Teil des Scopes entfällt vermutlich — muss in der
  Analyse-Phase gegen einen gezielten Test verifiziert werden (echtes `False`
  darf ein `None` nicht überstimmen), nicht blind neu gebaut werden.
- **Einheit/Kumulation:** `grau_gsp` ist seit Laufbeginn kumuliert (wie `tot_prec`)
  und wird bereits über `_precip_series_from_cumulative` auf ein Stunden-Signal
  zurückgerechnet — die Schwelle muss auf das zurückgerechnete Stunden-Signal
  passen, nicht auf den kumulierten Rohwert (Einheiten-Verwechslungsgefahr).
- **Fehlwert-Marker 9999.0** muss vor jedem Schwellenvergleich weiterhin als
  "keine Aussage" (nicht als Extremwert) behandelt werden (bereits vorhandene
  Regel aus #1457 S2b, gilt unverändert für die neue Ableitung).
- **ADR-0007 bindend:** Auch ein echtes "nein" bleibt rein deskriptiv, keine
  Handlungsempfehlung — Wortlaut-Grenze wie in S5a AC-8.
- **9-Ausgabeorte-Pflichtprüfung** (PO-Grundsatz 2026-08-05): auch wenn die
  Renderer strukturell fertig sind, muss die Spec explizit gegen alle 9 Orte
  verifizieren, dass ein echtes `False` überall korrekt "kein Zusatztext"
  produziert (nicht nur "kompiliert").
- **Rest-Europa/ICON-EU bleibt strukturell ausgeschlossen** — `hail_potential_grau_gsp`
  ist dort dauerhaft `None` (bewusst, #1457 S2c), diese Scheibe ändert daran nichts.

## Analysis

### Type

Feature (Folge-Scheibe S5b zu #1475, Epic #1419).

### Affected Files (with changes) — nur relevant, WENN eine Schwelle geklärt ist

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/thunder_enrichment.py` | MODIFY | Neue Ableitungsfunktion analog `_fuse_thunder_levels()`, kombiniert `dp.hail_flag` (WMO) mit `dp.hail_potential_grau_gsp` + Schwellenkonstante |
| `src/app/metric_catalog.py` (Alternative) ODER Konstante direkt in `thunder_enrichment.py` | MODIFY | Ablageort der Schwellenkonstante — Spec muss entscheiden, Muster #1474c (Kommentarblock mit Quellenlink) |
| `tests/tdd/test_hail_flag_wmo_signal.py`, `tests/tdd/test_hail_flag_aggregation.py` | MODIFY | Echte Testlücke: bisher nur `True`/`None` geprüft, `False`-Fälle fehlen |
| 9 bekannte Ausgabeorte (E-Mail/SMS/Telegram/Compare) | VERIFY (kein Code) | Bereits verdrahtet (S5a-Nachbesserung `7733d2fd`) — nur Nachweis, dass `False` überall "kein Zusatztext" ergibt |

**Kein** Fund in Go-API (`internal/`) oder Frontend außer reinem JSON-Passthrough (bestätigt, S5a-Stand unverändert).

### Scope Assessment

- Files: 3–4 Produktivdateien + 2 Testdateien
- Estimated LoC: ~80–120 (passt ins 250-LoC-Workflow-Budget)
- Risk Level: **HIGH** — nicht wegen Code-Umfang, sondern weil ein falsches `hail_flag=False`
  echte Sicherheitsrelevanz hat (Nutzer verlässt sich auf "kein Hagel")

### Technical Approach

Neue Ableitungsfunktion in `thunder_enrichment.py` (gemeinsamer Anschlusspunkt, kein
Einzellösungs-Antimuster), kombiniert WMO-Flag und `grau_gsp`-Schwellenvergleich zu einem
dreiwertigen `hail_flag`. Voraussetzung: eine belegte Schwelle/Einheit.

### Dependencies

Upstream: #1475 S5a (live), #1457 S2b (`grau_gsp`-Rohdaten, live), ADR-0007.
Downstream: alle 9 bestehenden Ausgabeorte (nur Verifikation).

### 🔴 Kernbefund der PFLICHT-Recherche: KEINE veröffentlichte DWD-Schwelle für `grau_gsp` auffindbar

Drei parallele Recherche-Agenten (Codebase-Audit, gezielte DWD-/Fachliteratur-Websuche,
Spec-/Issue-Historie) haben übereinstimmend bestätigt:

- `grau_gsp` = "Graupel, grid-scale precipitation" — akkumulierte Graupel-Bodenniederschlagssumme
  (kg/m², kumuliert wie `tot_prec`). Bedeutung/Einheit ist geklärt.
- **Keine DWD-eigene oder fachlich anerkannte Schwelle**, die `grau_gsp` als Hagel-ja/nein
  klassifiziert — anders als beim `lpi`-Präzedenzfall (#1474c: 5 J/kg DWD-Betriebsschwelle,
  50 J/kg Verifikationsspanne, beide belegt).
- Einzige gefundene Analogiegröße: "Graupel10"/"Graupel50" (10/50 kg/m²) aus einer
  Nature-Communications-Klimastudie 2025 — misst aber eine **andere physikalische Größe**
  (spaltenintegrierte maximale Graupel-Wassersäule, Momentanwert) als `grau_gsp`
  (akkumulierter Bodenniederschlag). Keine direkte Übertragbarkeit.
- Im gesamten bisherigen Issue-Verlauf (#1475, #1457, #1419, #1474, #1456) wurde nie eine
  konkrete grau_gsp-Zahl diskutiert — das ist keine übersehene Vorarbeit, sondern eine echte
  offene Lücke.

### Optionen (strategische Bewertung)

| Option | Bewertung |
|---|---|
| (a) Nature-Comm-Analogiewert stillschweigend verwenden | **Verworfen** — andere physikalische Größe, würde sich als "belegt" tarnen, verdeckte Verletzung der Issue-PFLICHT-Vorgabe, Sicherheitsrisiko bei falschem "nein" |
| (b) Issue zurückstellen, bis DWD-Doku/andere Quelle vorliegt | Sauber, kostet nichts, S5b bleibt aber blockiert |
| (c) Eigenkalibrierung wie #1456 jetzt explizit freigeben (Abweichung von der Issue-PFLICHT) | Möglich, aber PO-Entscheidung nötig — nicht stillschweigend |
| (d) Sonderfall `False` nur bei `grau_gsp==0` UND kein WMO-Hagelcode (keine echte Schwelle, sondern Nur-Null-Fall) | Vermeidet Kalibrierung eines Grenzwerts, ist aber selbst eine Modellannahme, die dem PO vorgelegt werden muss |

### Open Questions

- [ ] **PO-Entscheidung nötig, BEVOR eine Spec geschrieben wird:** Welche Option (b)/(c)/(d)
  oder eine vom PO genannte andere Quelle? Spec-Schreiben ohne geklärte Ableitungsregel wäre
  verfrüht (AC müsste die Regel konkret benennen).

## Next Step

Analyse abgeschlossen, aber mit offener PFLICHT-Frage. **Vor `/30-write-spec`:** PO-Entscheidung
zur Schwellenquelle einholen (siehe Open Questions) — Beleg im Issue #1506, nicht nur Chat
(Memory-Konvention: Freigabe nur im Chat zählt nicht als Freigabe).

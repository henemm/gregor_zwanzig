# Context: 1475-hagel-kennzeichen

## Request Summary
Issue #1475 (S5 zu Epic #1419): Hagel soll ein eigenes Kennzeichen (ja/nein/unbekannt)
werden, getrennt von der Gewitterstufe (`thunder_level`) — Hagel ändert nur die
Handlungsempfehlung ("Schutz suchen" statt "absteigen"), nicht die Dringlichkeit.
Betrifft drei Quellen unterschiedlich: DWD (`hail_potential_grau_gsp`, bereits
gefüllt, aber ohne Abnehmer), Météo-France (Hagel wird für FR/Korsika heute gar
nicht abgerufen), Open-Meteo WMO-Code (96/99 = Hagel, wird heute beim Einlesen zu
`HIGH` kollabiert und verworfen).

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py:137,151,160-161` | `wmo_code` (0-99, **bereits für jeden Punkt befüllt**, jede Region), `lightning_potential_lpi_jkg`, `hail_potential_grau_gsp` (DWD-Rohwert, **ohne Abnehmer**) |
| `src/providers/openmeteo.py:227,621-641,826-827` | `THUNDER_CODES={95,96,99}` kollabiert 95/96/99 gleich zu `HIGH` in `_parse_thunder_level`; `wmo_code` wird in derselben Zeile roh mitgespeichert — Unterscheidung 96 vs. 99 ist im Rohwert vorhanden, wird nur nicht ausgewertet |
| `src/providers/thunder_routing.py` | 3 Regionen: `FR`→`fr_direct` (Météo-France), `DE_ALPEN`→`de_direct` (DWD), `EU_REST`→`eu_direct` (ICON-EU, **kein Hagel-Pendant**, Known Limitation dokumentiert). First-match-wins, Reihenfolge tragend |
| `src/providers/meteofrance.py:189-195,466-668` | Holt bisher **nur** `LIGHTNING_COVERAGE` (Blitzdichte). Kein Hagel-Abruf vorhanden — `HAIL__GROUND_OR_WATER_SURFACE`/`GRAUPEL__GROUND_OR_WATER_SURFACE` sind laut Issue-Kommentar (2026-08-03) uber `GetCapabilities` bestätigt verfügbar, aber nicht angebunden |
| `src/providers/thunder_enrichment.py:38,88` | Mapping `"grau_gsp": "hail_potential_grau_gsp"` für DWD; Kommentar bestätigt: Hagel bleibt bewusst folgenlos seit #1474c |
| `src/providers/dwd.py:79-93,233` | `THUNDER_PARAMS=("lpi","grau_gsp")`; `grau_gsp` ist **kumulativ seit Laufbeginn** und muss auf Stunden-Signal zurückgerechnet werden (bereits gelöst, analog `lpi`) |
| `src/providers/dwd_eu.py:29-44` | ICON-EU hat **kein** `grau_gsp`-Pendant — bewusste Lücke, kein Fallback für EU_REST |
| `src/output/metric_format.py:296-370` | `_thunder_level_from_ladder` (geteilte 3-Schwellen-Leiter), `thunder_level_from_signals()` fusioniert `wettercode_level`/`lightning_density`/`cape`/`lightning_potential` zu EINEM `ThunderLevel` — **Hagel darf hier NICHT andocken** (Abgrenzung im Issue), braucht eigenen Pfad |
| `src/output/tokens/hazard_symbols.py` | SMS-Kürzel-Katalog (`HAZARD_SMS_SYMBOLS`), `"thunderstorm": "TH"` — Referenzmuster für ein eigenes Kürzel, falls Hagel im SMS-Alarmweg sichtbar werden soll (zu klären: separates Kürzel oder Suffix am bestehenden `TH:`-Forecast-Token) |
| `src/output/tokens/builder.py:16-18,49,70-85` | `FORECAST_TH="TH:"`, `FORECAST_THP="TH+:"` — bestehende Token-Struktur für die Gewitter-Vorhersage im SMS-Trip-Briefing |
| `src/services/trip_command_processor.py:165,228,864-925` | `_fmt_gewitter()` — der Klartext-Antwort-Block auf das `GEWITTER`-Kommando (Telegram/Mail). Zeigt heute nur die Stufe (`_THUNDER_LABEL`), **keine** Handlungsempfehlung — das ist der wahrscheinliche Ort für Scope-Punkt 4 |
| `src/output/renderers/email/plain.py:273-284` | "Gewitter-Vorschau"-Block (Mehrtages-Ausblick) — zeigt nur `level`/`text`, kein Hagel-Feld |
| `docs/reference/decision_matrix.md:26-27,43-132` | Aktueller Ist-Stand aller Gewitterquellen inkl. Hagel-Fussnoten; bereits vorbereiteter Satz "Für jede weitere Quelle (Hagel, S5/#1475): eine neue Größe dockt mit **einer** Zeile an" |

## Existing Patterns

- **Rohwert-Durchreichung ohne Stufenbildung** (analog #1457 S2b): neue Signale kommen
  zunächst nur als `Optional[float]`/`Optional[str]`-Rohwert ins Modell, Interpretation
  folgt in einer Folge-Scheibe (#1474c-Muster).
- **Geteilte Ladder-Funktion** (`_thunder_level_from_ladder`) — aber laut Issue-Abgrenzung
  explizit NICHT für Hagel gedacht, da Hagel keine Stufe ist, sondern ein Flag.
  Ein binäres ja/nein/unbekannt braucht eine eigene, kleinere Übersetzungsfunktion
  (Schwelle → Flag statt Schwelle → 4-stufige Leiter).
- **`None` = "keine Aussage"**, nie "kein X" — durchgängiges Prinzip in diesem Modul
  (`thunder_ampel_band`, `thunder_level_from_signals`, `hail_potential_grau_gsp`-Kommentar).
  Für das Hagel-Flag heißt das: `unbekannt` ist der Default, `nein` ist nur erlaubt, wenn
  eine Quelle aktiv "kein Hagel" aussagt — bei ICON-D2/AROME wahrscheinlich ein Rohwert
  unter einer Schwelle, bei WMO-Code außerhalb 96/99 aber uneindeutig (Code 95 sagt nicht
  "kein Hagel", er sagt nur "kein hagel-spezifischer Code").
- **Abrufnamen-Regel** (`reference_abrufnamen_gegen_getcapabilities_pruefen`): Vor der
  Météo-France-Anbindung die Namen `HAIL__GROUND_OR_WATER_SURFACE`/
  `GRAUPEL__GROUND_OR_WATER_SURFACE` erneut gegen eine frische `GetCapabilities`-Antwort
  prüfen (Namensfrage laut Kommentar geklärt, aber nicht mit eigener Forschung neu
  verifizieren — publizierte/gemessene Angaben verwenden).

## Dependencies

- **Upstream (Voraussetzung erfüllt):** #1457 S2 (Signale je Gebiet liegen an — Blitzdichte
  FR, Blitzpotenzial+Hagel-Rohwert DE/Alpen, Blitzpotenzial ICON-EU-Lückenfüller) und #1474/#1474c
  (S3, Befund + 4. Signal) sind beide geschlossen und live.
- **Downstream:** alle 3 Kanäle (E-Mail Klartext + Tabelle, Telegram, SMS-Token) sowie der
  `GEWITTER`-Kommando-Antwortblock. Keine bekannten Konsumenten, die durch das neue Feld
  brechen könnten (rein additiv).
- **Nicht Teil dieses Issues:** #1310 (Akut-Override bei Gewitter/Hagel), #1174 (Radar-Hagelsignal
  Italien, bereits eigenständig), #1419 S6 (Gewitter-Wahrscheinlichkeit).

## Existing Specs

- `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` — Muster für einen neuen
  Météo-France-Coverage-Abruf (Lauf-Wahl, `THUNDER_RUN_SAFETY_HOURS`, Namensprüfung)
- `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` — Muster für DWD-Rohwert-Anbindung
  inkl. kumulativer Rückrechnung (`grau_gsp` selbst schon gelöst)
- `docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md` — Muster für Andocken eines
  vierten Signals an die geteilte Ladder-Struktur (als Kontrastfolie: Hagel soll NICHT
  denselben Weg gehen, da Flag statt Stufe)
- `docs/reference/decision_matrix.md` — Provider-Ist-Stand, wird bei Umsetzung um die
  Hagel-Zeile ergänzt

## Risks & Considerations

- **Offene Forschungsfrage (aus Issue-Kommentar 2026-08-03 nicht vollständig gelöst):**
  Einheit/Bedeutung des AROME-Hagelwerts (`HAIL__GROUND_OR_WATER_SURFACE`/`GRAUPEL__…`)
  ist nur dem Namen nach geklärt, nicht dem Zahlenwert nach — braucht publizierte
  Météo-France-Doku, keine eigene Kalibrierung (PO-Vorgabe, analog #1456-Präzedenzfall).
- **Für `grau_gsp` existiert noch keine dokumentierte Schwelle** für ein binäres Flag —
  auch das ist offene Recherche, nicht Implementierungsdetail.
- **EU_REST (Rest-Europa) hat keine direkte Hagel-Quelle** — dort bliebe nur der WMO-Code
  (96/99) als Signal. Das deckt nicht dieselbe Präzision wie DE/Alpen (`grau_gsp`) oder
  FR (AROME) — muss in der Analyse als bewusste Known Limitation benannt werden, nicht
  stillschweigend als "unbekannt" verschwinden.
- **Kollisionsgefahr mit der Stufen-Fusion:** `thunder_level_from_signals()` ist der
  einzige Ort, an dem alle vier bisherigen Signale zusammenlaufen. Ein Implementierungsfehler
  könnte versehentlich das Hagel-Signal dort mit eintragen (genau das verbietet die
  Konzept-Abgrenzung) — Adversary-Mutationsprobe sollte gezielt prüfen, ob ein Hagel-Wert
  die Stufe verändert.
- **Handlungsempfehlungs-Text existiert heute nirgends** (weder "Schutz suchen" noch
  "absteigen" als generischer Sicherheitshinweis) — das ist keine Erweiterung eines
  bestehenden Textbausteins, sondern ein neuer Klartext-Baustein, der in mind. 3 Renderern
  + 1 Kommando-Handler konsistent auftreten muss (Trip/Compare-Teilungsinvariante beachten,
  falls Compare Gewitterdaten überhaupt zeigt — zu prüfen in der Analyse).
- **Sicherheitsrelevanter Kanal:** SMS ist der einzige Kanal, der Weitwanderer unterwegs
  erreicht (Projektkonvention) — Token-Format-Änderungen am `TH:`-Symbol brauchen die
  A/B-Prüfung Telegram-Kurzform = SMS-Prüfweg.
- **🔴 ADR-0007-Konflikt (neu gefunden in der Analyse-Phase, s. u.):** Scope-Punkt 4 des
  Issues widerspricht einer aktiven, nicht abgelösten Grundsatzentscheidung.

## Analysis

### Type
Feature

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/models.py:161` | MODIFY | `hail_potential_grau_gsp` bleibt Rohwert; neues abgeleitetes Feld `hail_flag: Optional[bool]` (3-wertig über `None`, kein eigenes Enum nötig) |
| `src/providers/openmeteo.py:621-641,826-827` | MODIFY | `wmo_code` auswerten: `{96,99}`→`True`, `95`→`False`, sonst `None` — einzige Quelle für `eu_direct` (Rest-Europa) |
| `src/providers/dwd.py` / `thunder_enrichment.py:38` | MODIFY (später, S5b) | Schwelle auf `hail_potential_grau_gsp` erst nach Klärung der Einheit; bis dahin bleibt Konsum `None` |
| `src/providers/meteofrance.py` | CREATE-artig (später, S5c) | Neuer Coverage-Abruf `HAIL__GROUND_OR_WATER_SURFACE`/`GRAUPEL__…`, analog bestehendem `LIGHTNING_COVERAGE`-Abruf |
| `src/services/weather_metrics.py:397,470,586-605,1037,1086,1131-1142` | MODIFY | `compute_basis_metrics()` (Trip), `summarize_points()` (Compare), `aggregate_stage()` + `aggregation_config` — neuer Aggregator "Priorität ja>unbekannt>nein" (NICHT `max()`-Missbrauch, da unbekannt keine Zwischenkategorie ist) |
| `src/output/metric_format.py:326-370` | UNVERÄNDERT LASSEN + Regressionstest verstärken | `thunder_level_from_signals()` darf Hagel NICHT fusionieren — Adversary-Mutationsprobe gezielt hierauf |
| `src/output/renderers/email/plain.py`, `html.py`, `compare_html.py` | MODIFY | Rein deskriptive Zusatzangabe neben Gewitterstufe (Format offen, s. Open Questions) |
| `src/output/renderers/sms_trip.py`, `src/output/tokens/hazard_symbols.py`, `builder.py` | MODIFY | Optionales SMS-Symbol nur bei `True`, kein Symbol bei `None`/`False` |
| `src/services/trip_command_processor.py:864-925` (`_fmt_gewitter`) | MODIFY | GEWITTER-Kommando-Antwort um Hagel-Angabe ergänzen |
| `api/routers/compare.py` | MODIFY | Serialisiert `ForecastDataPoint`-Felder — neues Feld muss durchgereicht werden |
| `frontend/` | KEINE Änderung vorgesehen | Hagel ist KEINE wählbare Trip-Editor-Metrik (Konvention analog `confidence_pct` #710) |
| Tests: `test_thunder_level_from_signals_fusion.py`, `test_dwd_eu_thunder_signal_fetch.py`, `test_thunder_enrichment_fuses_level_shared_path.py`, `test_weather_metrics.py` | MODIFY/CREATE | Fusions-Trennung, Aggregationsregel, Renderer-Ausgabe |

*Hinweis: Ein Recherche-Agent nannte fälschlich WMO-Codes 22/32/42/45/48/85-86 als "Hagel-Codes" — das ist **falsch** und verworfen. Korrekt (durch bestehenden Code belegt, `openmeteo.py:227`): 95=Gewitter, 96=Gewitter mit leichtem Hagel, 99=Gewitter mit schwerem Hagel.*

### Scope Assessment
- **Files:** ~14-16 (S5a WMO-Scheibe allein: ~8-10)
- **Estimated LoC:** S5a (WMO) ~150-250 · S5b (DWD-Schwelle) ~50-100 (+ Recherche, kein Code) · S5c (Météo-France) ~150-250 (+ Recherche)
- **Risk Level:** MEDIUM-HIGH (sicherheitsrelevanter Kanal SMS, Kopplungsrisiko mit Stufen-Fusion, aber additiv/fail-soft-fähig)

### Technical Approach
**Empfehlung: in Scheiben S5a→S5b→S5c aufteilen** (analog #1457 S2a/b/c-Präzedenz):
- **S5a zuerst:** WMO-Code-Auswertung — Quelle existiert bereits überall, deckt sofort ganz
  Europa ab (grob), etabliert Aggregator + Renderer-Pattern, das S5b/S5c nur noch befüllen.
- **S5b:** DWD-Schwelle für `hail_potential_grau_gsp` — braucht ZUERST fachliche
  Schwellenklärung (publizierte DWD-Doku, keine eigene Kalibrierung), das ist Recherche,
  kein Implementierungsdetail.
- **S5c:** Météo-France-Anbindung — neuer Abruf + Einheit/Schwelle ungeklärt, vergleichbarer
  Aufwand wie #1457 S2a.

Datenmodell: `Optional[bool]` statt eigenem Enum (3 Werte reichen über `None`=unbekannt).
Aggregation: eigene Prioritätsfunktion (`hail_priority`), kein `max()` auf numerischem Mapping.
Darstellung (unter der Annahme, dass Scope-Punkt 4 NICHT wörtlich umgesetzt wird, s.
Open Questions): rein deskriptiv, z. B. `Gewitter: hoch · Hagel: ja` — kein Symbol/Text bei
`unbekannt` (kein SMS-Rauschen), keine Formulierung wie "Vorsicht"/"Schutz suchen".

### Dependencies
Bestätigt: #1457 S2 (alle Quellen) + #1474/#1474c (S3, Stufenbildung) sind geschlossen und
live — Voraussetzung erfüllt. Kein Frontend-Dependency. Kein Go-API-DTO-Fund (Daten laufen
über den Python-Core, `api_contract.md` dokumentiert `hail_potential_grau_gsp` bereits als
Rohfeld ohne Rendering-Anweisung).

### Open Questions

- [x] ✅ **ADR-0007-Konflikt — PO-Entscheidung 2026-08-04: „Nur Fakten zeigen".**
  `docs/adr/0007-daten-statt-empfehlungen.md` bleibt unangetastet, KEIN neues ADR. Scope-Punkt 4
  des Issues ("Handlungsempfehlung … Schutz suchen") entfällt aus dem Umfang von #1475 —
  Hagel wird ausschließlich als deskriptives Kennzeichen (`ja`/`nein`/`unbekannt`) neben der
  Gewitterstufe angezeigt, wie eine amtliche Warnstufe, ohne Ratschlagstext. Damit reduziert
  sich der Umfang auf die Punkte 1–3 des Issues (Datenmodell-Feld, WMO 96/99 nicht mehr
  wegwerfen, Anzeige in allen 3 Kanälen als Fakt) — Punkt 4 wird NICHT umgesetzt.
- [ ] DWD-Schwelle für `hail_potential_grau_gsp` (Einheit g/m² vermutet, nicht verifiziert) —
  publizierte DWD-Doku nötig, sonst bleibt das Feld dauerhaft `None` für DE/Alpen/AT.
- [ ] Météo-France-Einheit/Schwelle für `HAIL__GROUND_OR_WATER_SURFACE`/`GRAUPEL__…` —
  ebenfalls offene Recherche, analog zur LPI-Schwellenklärung bei #1474c.
- [ ] Darstellungsformat je Kanal (E-Mail Tabelle vs. Klartext, SMS-Symbol ja/nein) — Detail
  für die Spec-Phase, keine Blockade.

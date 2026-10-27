# Context: feat-1507-mf-hagel-fr

## Request Summary
S5c zu #1475 (Epic #1419, Block C von #2257): Für FR/Korsika (`fr_direct`) fehlt bislang jeder Hagel-Rohwert von Météo-France — `hail_flag` wird dort ausschließlich aus dem WMO-Wettercode abgeleitet (nur "ja"-fähig, nie "nein"-fähig). Ein neuer Coverage-Abruf soll den echten Hagelwert von AROME beisteuern, analog zum bestehenden Blitzdichte-Abruf. PO hat am 20.09. entsperrt, mit Pflicht-Vorarbeit: Abrufnamen frisch gegen `GetCapabilities` prüfen, Einheit/Bedeutung aus veröffentlichter MF-Doku klären — keine eigene Kalibrierung.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/meteofrance.py:180-259, 561-779` | Blaupause: `LIGHTNING_COVERAGE`-Konstante, `THUNDER_RUN_SAFETY_HOURS`/`_thunder_run_candidates` (Lauf-Rückfall bei 404), `fetch_thunder_signals_multi` (Sammelabruf über Rechteck, geteilter Zwischenspeicher, Budget/Deadline, fail-soft). Ein neuer Hagel-Coverage-Abruf folgt demselben Muster — vermutlich als paralleler Abruf in derselben Methode oder als Schwester-Methode mit identischer Lauf-/Fenster-Logik |
| `src/providers/meteofrance.py:193-198` | **Warnung aus S2a:** der Name `LITOTA3__GROUND` aus der Konzept-Tabelle #1419 existierte beim Dienst nicht (0 Treffer, stiller 404). Der Issue-Text nennt für Hagel bereits zwei Kandidaten aus einer `GetCapabilities`-Prüfung vom 2026-08-03 (`HAIL__GROUND_OR_WATER_SURFACE`, `GRAUPEL__GROUND_OR_WATER_SURFACE`) — **diese Prüfung ist >1 Monat alt und laut #1647-Lehre vor Implementierung zu wiederholen**, nicht ungeprüft zu übernehmen |
| `src/app/models.py:158-209, 502-506` | `ForecastDataPoint.hail_flag: Optional[bool]` und `SegmentWeatherSummary.hail_flag` — Tri-State (True/None="unbekannt"), niemals `False` aus einem WMO-Code ableitbar. `hail_potential_grau_gsp: Optional[float]` (Zeile 165) ist das S5b-Pendant (DWD ICON-D2, roher Zahlenwert, noch NICHT in `hail_flag` konvertiert) |
| `src/providers/openmeteo.py:468-480, 723, 969` | `_parse_hail_flag(wmo_code)` — heute die EINZIGE Quelle für `hail_flag`. Ein neues MF-Signal muss zusätzlich einspeisen, ohne diese Quelle zu verdrängen (Kombinationsregel wie bei `thunder_level` nötig — vermutlich "ODER"-Verknüpfung, da `hail_flag` nie auf `False` gesetzt wird) |
| `src/providers/thunder_enrichment.py:37-59, 143-151` | Zentrales Fusionsmodul. `_PARAMETER`-Mapping (`"lpi"→"lightning_potential_lpi_jkg"`, `"grau_gsp"→"hail_potential_grau_gsp"`) zeigt das Namensschema für neue Rohfelder. Zeile 151: Hagel-Rohwerte bleiben **bewusst außerhalb** der `thunder_level`-Fusion (Gewitterstufe und Hagel sind getrennte Achsen, Epic-Prinzip Abschnitt 4/5) |
| `src/app/model_registry.py:120-142, 174-206` | Zentraler Schwellenkatalog (`CAPE_THRESHOLDS_JKG`, `LPI_THRESHOLDS_JKG` mit `region`-Schlüssel). Ein MF-Hagelwert-Schwelle würde nach demselben Muster hier eingetragen, sobald die Pflicht-Vorarbeit (Einheit/Bedeutung aus MF-Doku) abgeschlossen ist |
| `src/output/renderers/fallback_notice.py:84` | Anzeigename-Mapping `"hail_potential_grau_gsp": "Hagelsignal"` für Herkunfts-/Fallback-Hinweise — ein neues Feld braucht denselben Eintrag, falls es in Fallback-Meldungen sichtbar werden soll |
| `src/providers/dwd.py:84-106, 275` | S5b-Analogon: `grau_gsp`-Abruf, `THUNDER_CUMULATIVE_PARAMS` (Hagel ist beim DWD-Lauf KUMULIERT — Rechenregel könnte bei MF anders sein, muss separat geprüft werden) |
| `src/providers/dwd_eu.py:29-44` | Kommentar: "Ein Hagel-Pendant zu ICON-D2s `grau_gsp` gibt es NICHT" bei ICON-EU — bestätigt das Epic-Prinzip "leer heißt keine Aussage, nie keine Gefahr" pro Feld, nicht pro Provider |

## Existing Patterns

- **Coverage-Abruf-Muster** (`meteofrance.py`): Konstante für den ausgeschriebenen WCS-Namen + Kommentar mit Live-Verifikationsdatum, eigener Lauf-Sicherheitsabstand falls nötig, Sammelabruf über Rechteck mit geteiltem Zwischenspeicher, Budget/Deadline-Abbruch, fail-soft (wirft nie, `None` bei Fehler, nie `0`)
- **Tri-State-Hagel-Kennzeichen**: `hail_flag` ist `Optional[bool]`, kann nur auf `True` gesetzt werden (bestätigt), nie auf `False` — nur `None` ("unbekannt/keine Aussage")
- **Rohwert getrennt von Stufe**: jede Gewittergröße bekommt ein eigenes Feld (`lightning_density_per_km2_3h`, `lightning_potential_lpi_jkg`, `hail_potential_grau_gsp`), NIE ein gemeinsames Feld — Hagel-Rohwerte fließen nicht in `thunder_level` ein
- **Schwellen zentral, nie im Provider**: `model_registry.py` ist die einzige Stelle mit Zahlenwerten je Gebiet/Modell; Provider liefern nur Rohwerte
- **Coverage-Namen-Vorarbeit ist ein wiederkehrendes Muster** (S2a, S2b, S2c hatten jeweils eigene Namensfallen — siehe `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` und `fast/fix-1457-s2a-echte-abrufnamen.md`)

## Dependencies

- **Upstream:** Setzt #1475 S5a voraus (Datenmodell `hail_flag`, Renderer-Anbindung in SMS/Telegram/E-Mail existieren bereits und sind live) — dieses Ticket ändert nur die Datenquelle, nicht die Ausgabe
- **Downstream:** Alle Kanal-Renderer, die `hail_flag`/`format_hail_note` konsumieren, brauchen KEINE Änderung — sie lesen nur das bereits bestehende Feld

## Existing Specs

- `docs/specs/modules/feat_1475_s5a_hagel_wmo_flag.md` — Datenmodell/Renderer-Grundlage (S5a, live)
- `docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md` — Nachbesserung zu S5a
- `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md` + `docs/specs/fast/fix-1457-s2a-echte-abrufnamen.md` — direkte Blaupause für den Coverage-Abruf inkl. der Namens-Falle
- `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` — S5b-Pendant (DWD-Seite), zeigt wie ein Rohwert ohne Schwelle vorerst nur gespeichert wird

## Risks & Considerations

- 🔴 **Coverage-Name-Falle (höchstes Risiko):** die im Issue genannten Kandidatennamen sind >1 Monat alt. Erste Pflichthandlung der Implementierung ist eine frische `GetCapabilities`-Abfrage — Kurznamen aus der Konzept-Tabelle #1419 sind erwiesenermaßen keine Abrufnamen (S2a-Lehre)
- 🔴 **Einheit/Schwelle unbekannt:** keine eigene Kalibrierung erlaubt (Epic-Regel, Analogon zu #1456-Schließung) — Schwelle muss aus veröffentlichter MF-`DescribeCoverage`/Portal-Doku stammen; ist sie nicht auffindbar, wird nur der Rohwert gespeichert (analog S5b-Zustand von `hail_potential_grau_gsp`), keine Flag-Ableitung erzwingen
- **Rate-Limit:** Météo-France begrenzt Abrufe/Minute; ein zusätzlicher Coverage-Typ verdoppelt potenziell das Abrufvolumen, wenn er nicht in denselben Sammelabruf-Mechanismus (Rechteck + Zwischenspeicher) integriert wird wie die Blitzdichte
- **Kumulations-Semantik:** DWD `grau_gsp` ist kumulativ über den Lauf (`THUNDER_CUMULATIVE_PARAMS`) — ob MFs Hagelgröße dieselbe Eigenschaft hat, ist Teil der Pflicht-Vorarbeit (Doku-Klärung), nicht anzunehmen
- **Datenschema-Rework-Pflicht:** ein neues Feld in `ForecastDataPoint`/`SegmentWeatherSummary` triggert automatisch `data_schema_backup.py` (Pre-Snapshot-Hook) — Read-Modify-Write-Merge-Pflicht für Bestandsdaten gilt
- **ADR-0007 bleibt in Kraft:** keine Handlungsempfehlung, nur deskriptives Kennzeichen (bereits in #1475 S5a entschieden, gilt unverändert für S5c)
- **Abgrenzung:** S5b (#1506, DWD ICON-D2, `status:deferred`) ist eine separate Scheibe — dieses Ticket bearbeitet ausschließlich FR/Korsika

## Analysis

### Type
Feature (Folge-Scheibe S5c zu #1475, Epic #1419)

### PO-Freigabe (2026-09-20)
Issue war `status:deferred`, wurde heute vom PO entsperrt (Kommentar
2026-09-20T05:19:45Z): "Block C von #2257 wird fortgesetzt". Pflicht-Vorarbeit
laut PO-Kommentar: (1) Abrufnamen frisch gegen `GetCapabilities` prüfen —
Kurznamen aus der Konzept-Tabelle #1419 sind KEINE Abrufnamen (S2a-Lehre),
(2) Einheit/Bedeutung des Hagel-Rohwerts aus veröffentlichter
Météo-France-Doku klären, keine eigene Kalibrierung. Diese Prüfung gehört
projekt-konventionsgemäß (Vorbild `tests/tdd/test_thunder_coverage_name_live.py`,
S2a-Fix) als `pytest.mark.live`-Test in die TDD-RED-Phase — NICHT als
Ad-hoc-Shell-Recherche in der Analyse-Phase. Ein Versuch, den API-Key
außerhalb der etablierten `dotenv_env`-pytest-Fixture direkt in einem
Bash-Befehl zu verwenden, wird vom projekteigenen Secret-Gate blockiert
(beabsichtigtes Verhalten, kein Bug).

### Wesentlicher Architektur-Befund (ändert den Zuschnitt)
`MeteoFranceDirectProvider.fetch_forecast` setzt **kein** `wmo_code` — der
Provider baut `ForecastDataPoint`s direkt aus AROME-WCS-Rohdaten
(Temperatur/Wind/Niederschlag/Blitz), ohne Wettercode-Feld. `hail_flag` wird
pro Stunde von genau einem Provider gesetzt; es gibt keine feldweise
Cross-Provider-Fusion. Für Stunden, die tatsächlich von `fr_direct` bedient
werden, ist `hail_flag` heute strukturell IMMER `None` — die
WMO-Code-Ableitung (`openmeteo.py:_parse_hail_flag`) greift nur, wenn eine
Fallback-Quelle mit Wettercode diese Stunde bedient. Eine Kombination des
neuen MF-Rohwerts mit `hail_flag` würde eine feldweise Provider-Fusion
voraussetzen, die es aktuell nicht gibt — das ist eine eigene,
größere Architekturänderung, kein Teil dieser Scheibe.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `src/providers/meteofrance.py` | MODIFY | Neue Coverage-Konstante (Name aus AC-1-Live-Test), Coverage-Fetch parametrisieren (`_fetch_coverage_signals_multi(coverage_base, ...)` statt Kopie von `fetch_thunder_signals_multi`), dünner Wrapper `fetch_hail_signals_multi`, Verdrahtung in `fetch_forecast` analog `lightning_density_per_km2_3h` |
| `src/app/models.py` | MODIFY | Neues Rohwert-Feld auf `ForecastDataPoint` (Name abhängig vom AC-1-Ergebnis, z. B. `hail_potential_mf` oder `hail_intensity_mf_<einheit>`), Tri-State/Optional, kein Einfluss auf `hail_flag` |
| `tests/tdd/test_<neu>_coverage_name_live.py` | CREATE | `pytest.mark.live`-Namensverifikation (AC-1), Vorbild `test_thunder_coverage_name_live.py` |
| `tests/` (Kern, deterministisch) | CREATE/MODIFY | Fail-soft-Verhalten (404 → `None`, nie `0`), Budget-Teilung mit Blitzdichte |

### Scope Assessment
- Files: ~2 Produktivdateien + 1–2 Testdateien
- Estimated LoC: ca. 45–75 (Produktivcode), deutlich unter dem 250-LoC-Limit
- Risk Level: MEDIUM — Kernrisiko liegt nicht im Umfang, sondern in der
  Namens-/Einheiten-Unsicherheit (externe Abhängigkeit von Météo-France-Doku)

### Technical Approach
1. **AC-1 zuerst (Sperr-Voraussetzung):** Live-Test gegen `GetCapabilities`
   verifiziert den tatsächlichen Coverage-Namen (Kandidaten aus dem Issue,
   >1 Monat alt geprüft: `HAIL__GROUND_OR_WATER_SURFACE`,
   `GRAUPEL__GROUND_OR_WATER_SURFACE`) und klärt Einheit/Bedeutung über
   `DescribeCoverage`/Portal-Doku. Ohne grünen AC-1 wird kein Name in
   Produktivcode verdrahtet.
2. **Coverage-Abruf parametrisieren statt kopieren:** die Blitzdichte-Maschinerie
   (`fetch_thunder_signals_multi`, Sammelabruf über Rechteck, geteilter
   Zwischenspeicher, Budget/Deadline, fail-soft) ist stark auf einen
   Coverage-Typ zugeschnitten. Der Coverage-ID-Teil wird parametrisiert, damit
   Hagel denselben Mechanismus nutzt, statt ihn zu duplizieren. Lauf-/Fenster-
   Logik (`_thunder_run_candidates`, `THUNDER_RUN_SAFETY_HOURS`) wird
   übernommen, 404-Rückfallstufen bleiben pro Coverage separat prüfbar
   (Hagel könnte andere Verfügbarkeitszeiten haben als Blitzdichte).
3. **Reiner Rohwert, keine Flag-Ableitung (Szenario "b"):** der neue Wert
   landet in einem eigenen Feld, exakt nach Vorbild `hail_potential_grau_gsp`
   (S5b-Pendant, DWD) — gespeichert, aber (noch) nicht in `hail_flag`
   konvertiert. `hail_flag` bleibt unverändert (kein Zugriff, keine
   Ableitung). Eine Schwellen-/Flag-Ableitung (Szenario "a") wird nur verfolgt,
   falls AC-1 eine klare, aus MF-Doku belegte Einheit/Schwelle liefert —
   andernfalls bleibt es beim reinen Rohwert (keine eigene Kalibrierung,
   Epic-Prinzip).
4. **Budget teilen, nicht verdoppeln:** der zusätzliche Coverage-Abruf nutzt
   dasselbe `THUNDER_FETCH_DEADLINE_SECONDS`-Budget wie die Blitzdichte,
   kein zweites unabhängiges Vollbudget — sonst Verdopplung der
   Worst-Case-Laufzeit/Requests pro Anreicherungszyklus.

### Empfohlene Acceptance Criteria (für `/30-write-spec`)
- **AC-1 (Sperr-Voraussetzung):** Live-Test (`pytest.mark.live`) prüft den im
  Produktivcode hinterlegten Coverage-Namen gegen eine frische
  `GetCapabilities`-Antwort — AC-2/AC-3 hängen von einem grünen AC-1 ab
  (Reihenfolge explizit in der Spec vermerken).
- **AC-2 (Rohwert-Abruf):** Für Orte im AROME-FR-Zuständigkeitsgebiet liefert
  der neue Abruf pro Stunde einen Rohwert, best-effort/fail-soft, `None` bei
  Fehler/außerhalb Zuständigkeit, nie `0`.
- **AC-3 (Speicherung ohne Ableitung):** Rohwert landet in neuem Feld;
  `hail_flag` bleibt unverändert — kein Zugriff, keine Kombination mit
  WMO-Code in diesem Ticket.
- **AC-4 (Scope-Ausschluss, als Known Limitation formuliert):**
  Cross-Provider-Kombination von MF-Hagel-Rohwert und WMO-Code-Ableitung
  (`hail_flag`) ist nicht Teil dieses Tickets — architektonisch nicht ohne
  feldweise Provider-Fusion möglich (`fr_direct` führt keinen `wmo_code`).
- **AC-5 (Budget):** Der zusätzliche Coverage-Abruf teilt sich das bestehende
  Zeitbudget mit der Blitzdichte, kein zweites unabhängiges Vollbudget.

### Dependencies
- Setzt #1475 S5a voraus (Datenmodell/Renderer-Grundlage, live)
- AC-1 (Live-Namensverifikation) ist Voraussetzung für AC-2/AC-3 — muss in
  TDD-RED vor der eigentlichen Implementierung grün sein
- Downstream: Kanal-Renderer brauchen keine Änderung (neues Feld wird in
  diesem Ticket nicht gerendert)

### Open Questions
- [x] Existiert der Coverage-Name beim Dienst? → wird durch AC-1 (Live-Test in
  TDD-RED) beantwortet, nicht in der Analyse-Phase
- [x] Einheit/Bedeutung des Rohwerts? → wird durch AC-1 (`DescribeCoverage`/
  Portal-Doku) beantwortet
- [ ] Feldname für den neuen Rohwert (`hail_potential_mf` o. ä.) — final erst
  nach AC-1-Ergebnis benennbar, Spec kann Platzhalter setzen

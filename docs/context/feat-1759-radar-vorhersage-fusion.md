# Context: Radar-Nowcast-Beobachtung fließt in die Vorhersage-Stufe ein (#1759)

## Request Summary
Die bestehende Radar-Beobachtung (`NowcastResult.is_convective`, produktiv u.a. im `/jetzt`-Kommando und im Radar-Alarm) soll zusätzlich in die angezeigte Gewitter-Vorhersagestufe (`dp.thunder_level`) einfließen: Regel 1 aus dem Gesamtkonzept — "Beobachtung schlägt Vorhersage" — hebt die Stufe an, senkt sie nie, und gilt nur für die aktuelle/nächste Stunde.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/metric_format.py:513-526` | `thunder_level_from_signals()` — die Fusionsfunktion, fusioniert 4 Signale (Wettercode, Blitzdichte, CAPE, Blitzpotenzial) per `max_thunder()`. Alle Keyword-Args ohne Default (kein stiller Rückfall, ADR-0025-Linie). **Hat keinen Radar-Parameter.** |
| `src/output/metric_format.py:474-510` | `thunder_signal_carriers()` — Herkunfts-Liste für `dp.thunder_level_signals`, läuft aus DEMSELBEM Argumentsatz wie `thunder_level_from_signals()`, damit Stufe und Herkunft nie divergieren. |
| `src/providers/thunder_enrichment.py:143-203` | `_fuse_thunder_levels()` — Loop `for dp in data`, ruft je Datenpunkt die Fusion auf, überschreibt `dp.thunder_level`/`dp.thunder_level_signals` NUR bei Nicht-`None`-Ergebnis. Stundenbezug via `dp.ts`. |
| `src/providers/thunder_enrichment.py:234-289` | `enrich_thunder()` — ruft `_fuse_thunder_levels()` am Ende IMMER auf (Z.289), auch ohne Gewitter-Provider. Fail-soft beim Lightning-Fetch (Exceptions geschluckt Z.279-282), Fusion selbst ohne try/except. |
| `src/services/radar_service.py:85-104,170` | `RadarNowcastService.get_nowcast(lat, lon, priority="user_briefing") -> NowcastResult`. `NowcastResult`: `onset_minutes`, `intensity_label`, `source`, `frames`, `is_convective: bool=False`, `convective_checked`, `throttled`, `data_unavailable`. **Kein Blitz-Umkreis-Feld.** |
| `src/services/trip_alert.py:1186`, `src/services/compare_radar_alert.py:342`, `.../trip_command_processor.py:1375`, `.../trip_report_scheduler.py:1815` | Bestehende Aufrufstellen von `get_nowcast()` — alle auf der Alarm-/`/jetzt`-Schiene, keine berührt `dp.thunder_level`. |
| `src/app/models.py:101,214` | `ForecastDataPoint.ts: datetime` (Pflichtfeld, Stundenbezug) und `.thunder_level_signals: Optional[list[str]]`. |
| `src/output/renderers/trip_report.py:656` | `_dp_to_row()` — baut die Briefing-Stundentabelle aus `dp`, liest u.a. `dp.thunder_level`. Bestätigt: Fusion-Änderung kommt automatisch im Briefing an, kein separater Renderpfad. |

## Existing Patterns
- **Additive Fusion nur über explizite Parameter** (ADR-0057-Präzedenzfall GeoSphere-CAPE/CIN): eine neue Signalquelle fließt NICHT automatisch ein, nur weil sie technisch verfügbar ist — sie muss `thunder_level_from_signals()` als benannter Parameter bekannt gemacht werden. Reines "Daten sammeln, aber nicht lesen" ist laut Konzept §5 kein valider Zwischenzustand.
- **Kein stiller Fallback** (ADR-0025-Linie, PO-Korrektur 2026-08-08): alle Schwellen/Leitern werden explizit durchgereicht, kein Default in der Fusionsfunktion.
- **Stufe und Herkunft aus demselben Argumentsatz** (`thunder_level_from_signals()` + `thunder_signal_carriers()`), damit `dp.thunder_level` und `dp.thunder_level_signals` nie auseinanderlaufen.
- **max_thunder()-Symmetrie**: bisher sind alle 4 Fusionssignale gleichrangig ("schärfstes gewinnt"). Regel 1 aus dem Konzept ist aber KEIN gleichrangiges fünftes Signal, sondern ein Post-Fusion-Override ("mindestens mittel, nie senken") — passt strukturell nicht 1:1 in das bestehende Muster.

## Dependencies
- **Upstream:** `RadarNowcastService.get_nowcast(lat, lon)` braucht Koordinaten und macht einen (gecachten) Live-Call — bisher nur auf der Alarm-Schiene aufgerufen, nicht in `_fuse_thunder_levels()`.
- **Downstream:** `dp.thunder_level` wird von ALLEN Briefing-Kanälen gelesen (ADR-0025: eine Quelle für alle Kanäle) — eine Änderung an der Fusion wirkt sich automatisch auf E-Mail/Telegram/SMS/Premium-SMS aus, ohne dass Renderer angepasst werden müssen.

## Existing Specs
- `docs/specs/modules/radar_convective_stage.md` (#660) — spezifiziert nur `RadarFrame.is_convective → NowcastResult.is_convective →` Alarm-Text. Keine Verbindung zu `dp.thunder_level`.
- `docs/specs/modules/feat_1680_s4_gewitter_herkunft_trip_stundentabelle.md` — behandelt nur die Sichtbarkeit der Herkunft (`dp.thunder_level_signals`) in der Stundentabelle, kein neues Signal.
- `docs/features/gewitter-gesamtkonzept.md` §3.7 (Z.334-343) — listet "Radar-Beobachtung" bereits als Zutat der Zielarchitektur (kein=nicht konvektiv, mittel=konvektiv, KEINE hoch-Stufe), §4 Regel 1 (Z.388-392): genauer Wortlaut der Anheben-nie-senken-Regel, §5 (Z.656-682): IST-Zustand-Befund (Quelle des Issues).
- ADR-0025 (`docs/adr/0025-...md`): eine Quelle je Kanal-Aussage — Radar-Einspeisung ist erlaubt, solange sie in `dp.thunder_level` selbst mündet.
- ADR-0057 (`docs/adr/0057-...md`): additive Zweitquellen erlaubt, Fusionsort bleibt `_fuse_thunder_levels()`/`thunder_level_from_signals()` — kein zweiter Fusionsort.
- ADR-0048: modellabhängige Schwellen — hier vermutlich nicht direkt relevant, da `is_convective` ein Bool ist, kein Schwellenwert.

## Risks & Considerations
1. **Fusionsmuster-Bruch:** Regel 1 ist ein Anheben-nie-senken-Override, kein gleichrangiges Signal — Design-Entscheidung nötig, ob das als 5. Parameter in `thunder_level_from_signals()` oder als separater Nachbearbeitungsschritt in `_fuse_thunder_levels()`/`enrich_thunder()` umgesetzt wird (klärt die Spec-Phase).
2. **"Blitz im Umkreis" strukturell nicht vorhanden:** `NowcastResult` kennt nur `is_convective`, keine Blitz-Umkreis-Info. Die im Issue genannte Blitzdichte (`lightning_density_per_km2_3h`) ist bereits ein separates Fusionssignal — Klärungsbedarf, ob Regel 1 wirklich eine zweite, neue Bedingung braucht oder ob "Blitz im Umkreis" durch das bestehende Blitzdichte-Signal ohnehin schon abgedeckt ist.
3. **Performance/Kopplung:** `get_nowcast()` macht einen Live-Call mit `lat/lon`; `_fuse_thunder_levels()` läuft synchron über die ganze Zeitreihe je Location. Muss geklärt werden, ob pro Fusion-Lauf ein neuer Nowcast-Call gemacht wird (teuer) oder ein bereits vorhandenes Ergebnis injiziert wird.
4. **Zeitfenster "aktuelle/nächste Stunde":** `dp.ts` ist UTC — Vergleich gegen `now()` braucht Klarheit über Zeitzone (bekannte Zeitzonen-Fallen im Projekt, s. `reference_zeitzonen_waechter_zwei_blindstellen`).
5. **Keine Testbrücke vorhanden:** kein existierender Test kombiniert `thunder_level_from_signals` und `is_convective` — #1759 braucht komplett neue Tests, kein Vorbild zum Anpassen.

## Ausgeklammert (laut Issue-Abgrenzung)
- #1443 (DWD Radolan/Radvor Nowcast, zurückgestellt) ist eine ANDERE, neue Datenquelle — nicht Teil dieses Tickets.

## Analysis

### Type
Feature (Verdrahtung bestehender Beobachtung in bestehende Vorhersage-Stufe, keine neue Datenquelle).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/thunder_enrichment.py` | MODIFY | Neue Helper-Funktion `_apply_radar_override(data, nowcast_result, now)` NACH der bestehenden `_fuse_thunder_levels()`-Fusion in `enrich_thunder()` aufgerufen; try/except um den `get_nowcast()`-Call analog zum bestehenden Muster um `_fetch_lightning_density()` (Z.279-282) |
| `tests/tdd/test_thunder_radar_override_onset_window.py` | CREATE | Fälle: hebt LOW→MED, senkt HIGH nicht, wirkt nur im Onset-Fenster, Radar-Ausfall kippt nichts, `thunder_level_signals` bekommt `"radar"` ergänzt |
| `docs/adr/` (neues ADR oder Ergänzung 0057) | ggf. MODIFY/CREATE | Falls Post-Fusion-Override als Architekturentscheidung festgehalten werden soll (Entscheidungsfläche: Datenmodell/Fusion) |

**Nicht angefasst** (entgegen erster Vermutung im Kontext-Teil oben): `metric_format.py` (`thunder_level_from_signals()`/`thunder_signal_carriers()` bleiben unverändert — Override lebt bewusst außerhalb der 4-Signal-`max()`-Symmetrie), `radar_service.py` (kein neuer Parameter nötig), `openmeteo.py` (ruft `enrich_thunder()` unverändert auf, `location` mit lat/lon ist dort bereits vorhanden).

### Scope Assessment
- Files: ~2-3 (1 Produktivdatei, 1 Testdatei, optional ADR)
- Estimated LoC: +150/-0 bis +220/-0 (40-70 Produktivcode, 80-150 Tests)
- Risk Level: MEDIUM (kritischer Pfad `dp.thunder_level`, aber additiv/fail-soft — Fehler kann nur zu Über-, nie zu Untermeldung führen; strukturell also eher „zu vorsichtig" als „gefährlich falsch")

### Technical Approach
**Separater Post-Fusion-Override**, nicht 5. Parameter der bestehenden Fusion. Begründung: Regel 1 ist kein gleichrangiges Schwellenwert-Signal wie die anderen 4 (Wettercode/Blitzdichte/CAPE/Blitzpotenzial), sondern ein bedingter Deckel ("mind. MED, nie tiefer") mit Zeitfenster-Gate (nur aktuelle/nächste Stunde), das den anderen Signalen fremd ist. Ein 5. Parameter würde die dokumentierte Eigenschaft "jedes Signal wird eigenständig übersetzt" brechen und Zeitfenster-Wissen in eine bislang zeitlose Funktion ziehen.

Implementierung: `get_nowcast(lat, lon, priority="user_briefing")` wird 1× je Reihe (nicht je Datenpunkt) aufgerufen, nur wenn ein `dp` im Onset-Fenster liegt; Ergebnis nur auf den/die passenden `dp` angewendet; `dp.thunder_level_signals` bekommt `"radar"` addiert (nicht ersetzt).

### Dependencies
1. Onset-Fenster-Helper (`dp.ts` vs. `now()`, UTC-Vergleich — bekannte Zeitzonenfalle) isoliert bauen + testen.
2. Override-Funktion (Radar-Ergebnis → Deckel-Logik) isoliert testen, ohne echten `get_nowcast()`-Call (DI-Seam wie bei bestehenden Radar-Tests).
3. Verdrahtung in `enrich_thunder()` inkl. try/except, dann Integrationstest über `fetch_forecast()`.
4. `thunder_level_signals`-Erweiterung zuletzt.

### Risiken (aus Strategie-Bewertung)
- **Performance:** 1 zusätzlicher Live-Radar-Call je Ort und Briefing-/Vergleichslauf (nicht je Datenpunkt) — bei 9-15 Orten im Ortsvergleich ggf. spürbare Mehrlatenz auf dem Erzeugungspfad (`HTTPX_TIMEOUT=8.0`), sollte in der Spec als Zahl festgehalten werden.
- **Kein Drosselschutz:** `priority="user_briefing"` ist laut `forecast_budget.py` rate-limit-frei — Klärungsbedarf in der Spec, ob das bewusst ist.
- **Fail-Soft-Pflicht:** neuer `get_nowcast()`-Aufruf MUSS in try/except (analog `_fetch_lightning_density()`), sonst kippt ein Radar-Ausfall die gesamte Vorhersage-Anreicherung.

### Open Questions — PO-Entscheide 2026-08-19
- [x] **Override-Bedingung:** `is_convective` ODER Blitzdichte über Schwelle löst den Override aus (PO-Entscheid gegen die Empfehlung "nur is_convective" — deckt den Issue-Wortlaut "Blitz im Umkreis" wörtlich ab). Braucht in der Spec-Phase eine EIGENE, neue Schwelle nur für den Override-Pfad (getrennt von der bestehenden LPI-/Blitzdichte-Leiter der normalen Fusion, um Doppelzählung/Verwechslung zu vermeiden — Naht explizit benennen).
- [x] **Zeitfenster:** Enges, absolutes Fenster ±90 Min um `now()` (nicht an Stundenlinien der Tabelle orientiert). `dp.ts` (UTC) vs. `now()` — Zeitzone/Referenz in der Spec exakt festlegen (bekannte Zeitzonenfalle im Projekt).
- [ ] Ziel-Stufe des Deckels: "mindestens MED" (Konzept-Wortlaut) — gilt das unabhängig davon, was die 4-Signal-Fusion vorher ergeben hat (auch wenn sie `None`/"keine Aussage" ergab)? Für die Spec-Phase offen.

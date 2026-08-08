# Context: fix-1613-sms-multi-symbols

## Request Summary
`/api/sms-symbols` liefert nur Metriken mit genau EINEM SMS-Kürzel (`SMS_SYMBOL_BY_METRIC`). Metriken mit MEHREREN Kürzeln (`SMS_MULTI_SYMBOLS_BY_METRIC`: `wind_chill` → FN/FK/FD/WC, `temperature` → K/D, `temperature_night` → N, `thunder` → zusätzlich TH+:) fehlen strukturell in der Antwort und damit in jeder Legende/Anzeige, die sich auf den Endpoint stützt. PO hat konkret `WC` als fehlend im Trip-Editor bestätigt.

## Related Files

| File | Relevance |
|------|-----------|
| `api/routers/config.py:30-53` | `GET /api/sms-symbols` — Root Cause: serialisiert nur `SMS_SYMBOL_BY_METRIC.items()`, liest `SMS_MULTI_SYMBOLS_BY_METRIC` nie |
| `src/output/renderers/sms_trip.py:64-90` | `_SMS_SYMBOL_METRIC_IDS` (1:1) → `SMS_SYMBOL_BY_METRIC`, aus `metric_catalog.sms_code` abgeleitet (#1435 E3b) |
| `src/output/renderers/sms_trip.py:118-123` | `SMS_MULTI_SYMBOLS_BY_METRIC` — die fehlende Quelle: `temperature`→(K,D), `temperature_night`→(N,), `wind_chill`→(FN,FK,FD,WC), `thunder`→(TH:,TH+:) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:106-165` | `SmsSymbolCatalog`/`SmsSymbolEntry`-Typen, `smsSymbols` State, `metricSymbols`-Derived (Lookup metric_id → Symbol) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1350-1459` (Sektion „04 — Schwellwerte") | Einzige Stelle, die `metricSymbols[...]` tatsächlich anzeigt — als Badge in `ThresholdMetricRow`, für genau die 8 `SMS_SYMBOL_BY_METRIC`-Metriken (wind, gust, precipitation, rain_probability, thunder, snow_depth, snowfall_limit; `fresh_snow` fehlt hier ebenfalls, aber unstrittig — kein Bestandteil dieses Issues) |
| `frontend/src/lib/components/shared/weather-metrics-tab/ThresholdMetricRow.svelte` | Zeigt `smsSymbol` als `<code class="sms-symbol">`-Badge neben dem Label — bisheriges alleiniges Anzeige-Muster, ABER an `levels` (Segmented-Control Sensibel/Standard/Robust) gekoppelt |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:996-1024` (`officialAlertsToggle`-Snippet) | Die tatsächliche „Kürzel-Legende" (`official-alerts-symbol-legend`) — zeigt aber nur `smsSymbols.hazards` (9 Gefahrenarten), NICHT `smsSymbols.metrics`. Kein Ort, an dem Metrik-Kürzel als Fließtext-Legende erscheinen |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Grundauswahl.svelte` | Metrik-Checkbox-Grundauswahl (Sektion 02) — generisch aus `catalog`, zeigt aktuell KEIN Symbol pro Metrik |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte` | Zeigt `Kürzel <span>{short}</span>` — ANDERES Konzept (`short`/`metricById`, ein Register-Kürzel für Layout/Spalten-Editor), nicht die SMS-Multi-Symbol-Frage. Nicht Teil dieses Bugs |
| `tests/unit/test_sms_fidelity_preview.py:36-64` | `ALL_SMS_METRIC_IDS`/`METRIC_TO_SYMBOLS` — unabhängige, absichtlich dupliziert gehaltene Referenzliste für die SMS-Fidelity-Vorschau (#923); bestätigt exakt dieselben Symbol-Zuordnungen wie `sms_trip.py`, nutzt sie aber über einen anderen Endpoint (`/api/_validator/sms-fidelity-preview`) |
| `docs/reference/api_contract.md:166` | Endpoint-Liste, nur Pfad+Methode, kein Schema — keine Änderung nötig |

## Existing Patterns

- **Ableitung statt Handpflege (#1435 E3b):** `SMS_SYMBOL_BY_METRIC` wird aus `metric_catalog.get_sms_code()` abgeleitet, nicht mehr handgepflegt. `SMS_MULTI_SYMBOLS_BY_METRIC` bleibt bewusst eine eigene Handliste (Kommentar in `sms_trip.py:87-91`: mehrere Symbole pro Metrik, `SMS_SYMBOL_BY_METRIC` wird zusätzlich für Schwellwerte gelesen — Vermischung würde falsche Schwellwert-Einträge erzeugen).
- **Endpoint-Kommentar bekräftigt die Absicht** (`config.py:31-40`, Issue #1318 AC-9): „die Legende nicht von der tatsächlich versendeten SMS abweichen kann" — genau diese Zusicherung ist durch die Typ-Lücke gebrochen.
- **Anzeige-Muster bislang 1:1 an Schwellwert-Konfiguration gekoppelt:** Die einzige existierende Stelle, die ein Symbol tatsächlich rendert (`ThresholdMetricRow`), setzt zwingend `levels` (Segmented-Control) voraus. `wind_chill`/`temperature`/`temperature_night` sind aber KEINE Schwellwert-Metriken (keine konfigurierbaren Sensibel/Standard/Robust-Stufen) — für sie existiert **keine** analoge Zeilen-Komponente. Ein reines „Endpoint erweitern" behebt die Backend-Lücke, aber die Frontend-Seite braucht einen neuen Anzeigeort, kein Copy-Paste eines bestehenden.

## Dependencies

- **Upstream:** `metric_catalog.get_sms_code()` (Register), `_SMS_SYMBOL_GRAMMAR` (Ausnahmen TH:/NS24+), `SMS_MULTI_SYMBOLS_BY_METRIC`-Handliste selbst — beide sind bereits korrekt, nur der Endpoint liest die zweite nicht.
- **Downstream:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (`smsSymbols`/`metricSymbols`) ist der einzige bekannte Konsument von `/api/sms-symbols` im Trip- UND Vergleich-Kontext (`context === 'vergleich'` lädt denselben Endpoint, Zeile 506). Eine additive Erweiterung der Response (`metrics`-Array um weitere Einträge) bricht nichts Bestehendes.

## Existing Specs
- Kein dediziertes Spec-Dokument zu `/api/sms-symbols` selbst; Herkunft verteilt über `docs/specs/modules/` zu #1318 (AC-9, Endpoint-Einführung), #1410 (Mehrfach-Kürzel-Tabelle), #1450/#1482/#1484 (einzelne Symbol-Nachträge in `sms_trip.py`) — keine davon aktualisiert bislang den Endpoint für Mehrfach-Kürzel.

## Risks & Considerations

- **Offene Design-Frage für `/20-analyse`/`/30-write-spec`:** WO im Frontend sollen die neuen Mehrfach-Symbol-Einträge sichtbar werden? Es gibt noch KEINEN Anzeigeort für `wind_chill`/`temperature`/`temperature_night`-Symbole — weder Schwellwerte-Sektion (keine Levels) noch die Fließtext-Legende (nur Hazards) noch die Grundauswahl (kein Symbol-Slot). PO-Formulierung „Zeile mit Kürzel WC muss sichtbar sein" deutet auf eine NEUE Zeile analog zu `ThresholdMetricRow`, aber ohne Segmented-Control — das ist eine eigene Kompotenten-Entscheidung, nicht bloß eine Endpoint-Erweiterung.
- **`thunder`'s zweites Kürzel `TH+:`** kollidiert im Antwortformat: `thunder` steht bereits in `SMS_SYMBOL_BY_METRIC` (mit `TH:`) UND in `SMS_MULTI_SYMBOLS_BY_METRIC` (mit `TH:`, `TH+:`) — Response-Struktur muss klären, ob eine Metrik-ID mehrfach im `metrics`-Array erscheinen darf oder ob pro Metrik ein Array von Symbolen zurückkommt (Breaking Change für `SmsSymbolEntry`/`metricSymbols`-Lookup, das aktuell `metric_id → einzelnes sms_symbol` ist).
- **Bestandsschutz:** `SmsSymbolEntry`-Interface (Frontend, `sms_symbol: string`) müsste ggf. auf `sms_symbol: string | string[]` erweitert werden oder auf mehrere Einträge pro `metric_id` — beides berührt `metricSymbols`-Derived (aktuell `Map<metric_id, string>`, letzter Eintrag gewinnt bei Duplikaten).
- **Test-Politik:** Kern-Layer, kein Netz nötig — `TestClient(app).get("/sms-symbols")`-Pattern existiert bereits in `tests/tdd/test_sms_snow_symbols.py:539-577` als Vorbild für Backend-AC-Tests.

## Verwandtes Issue
- **#1435 E3b** — dort bereits als bekannte Lücke vermerkt („`wind_chill` (vier Kürzel) ... bleiben außerhalb"), nie zu eigenem Ticket gemacht. Root Cause und betroffene Zeilen sind identisch mit dieser Analyse.

## Analysis

### Type
Bug (Label `bug`, `[triage:a] nutzersichtbares Fehlverhalten`).

**Hinweis zum Investigations-Ablauf:** Der dispatchte `bug-intake`-Agent meldete sich zweimal `idle` ohne inhaltlichen Bericht (kein Write/Edit-Tool, konnte nichts hinterlassen — bekanntes Agenten-Muster, siehe Memory `feedback_developer_agents_go_idle_without_report`). Die Bug-Analyse unten stammt daher aus der eigenen Code-Recherche (Context-Phase) + einem `Plan/Sonnet`-Agenten für die strategische Bewertung; beide zentralen Design-Entscheidungen wurden stichprobenartig gegen den Code verifiziert (`buckets.off`-Gate bestätigt an den Zeilen 293/1357-1441).

### Root Cause (bestätigt)
`GET /api/sms-symbols` (`api/routers/config.py:43-50`) liest ausschließlich `SMS_SYMBOL_BY_METRIC` (1:1), nie `SMS_MULTI_SYMBOLS_BY_METRIC` (`sms_trip.py:118-123`). Frontend hat dadurch für `wind_chill`/`temperature`/`temperature_night` **keine** Symbol-Daten und (bestätigt per Grep) aktuell auch **keinen Anzeigeort** für diese Metriken — die einzige existierende Symbol-Anzeige (`ThresholdMetricRow.svelte`) ist zwingend an eine Schwellwert-Konfiguration gekoppelt, die für diese drei Metriken nicht existiert.

### Design-Entscheidungen (aus Plan-Agent, verifiziert)
1. **Response-Format:** `/api/sms-symbols` liefert pro `metric_id` künftig `sms_symbols: string[]` statt `sms_symbol: string`. `SMS_MULTI_SYMBOLS_BY_METRIC` hat Vorrang (deckt `thunder` bereits vollständig als `["TH:", "TH+:"]` ab, kein Duplikat mehr), die restlichen 7 `SMS_SYMBOL_BY_METRIC`-Metriken liefern ein Array mit einem Element.
2. **Neuer Anzeigeort:** Neue, schlanke Komponente (Arbeitstitel `MultiSymbolMetricRow.svelte`, im selben Ordner wie `ThresholdMetricRow.svelte`) — Label + Badge-Liste, **kein** Segmented-Control. Gated über `!buckets.off.includes('wind_chill')` etc. — exakt dasselbe, bereits verifizierte Gate-Muster wie die 7 bestehenden Schwellwert-Zeilen (Zeilen 1357-1441) und Sektion 05 (Zeile 293). Platzierung: Sektion 04 bzw. eigener Unterabschnitt „04b", da inhaltlich verwandt (SMS-Kürzel) aber ohne Schwellwert-Konfiguration.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/config.py` | MODIFY | `/api/sms-symbols`: `metrics`-Array liefert `sms_symbols: string[]`, Merge mit Vorrang für `SMS_MULTI_SYMBOLS_BY_METRIC` |
| `tests/tdd/test_sms_snow_symbols.py` oder neue Testdatei (Namensregel beachten, nicht issue-nummeriert) | CREATE/MODIFY | AC-Test: `wind_chill` → `["FN","FK","FD","WC"]`, `thunder` → genau `["TH:","TH+:"]` (kein Duplikat), bestehende 1:1-Metriken weiterhin 1-elementige Arrays |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `SmsSymbolEntry`/`SmsSymbolCatalog`-Typen, `metricSymbols`-Derived auf `Record<string, string[]>`, bestehende `ThresholdMetricRow`-Aufrufe auf `metricSymbols['wind']?.[0]` umstellen, neue Zeilen für wind_chill/temperature/temperature_night verdrahten |
| `frontend/src/lib/components/shared/weather-metrics-tab/MultiSymbolMetricRow.svelte` (Name in Spec final) | CREATE | Label + Badge-Liste, kein Segmented-Control |
| ggf. `frontend/src/lib/components/shared/weather-metrics-tab/ThresholdMetricRow.svelte` | KEINE ÄNDERUNG | Prop-Signatur (`smsSymbol?: string`) bleibt, Call-Sites liefern weiterhin Einzelwert |

### Scope Assessment
- Files: 4-5 (2-3 Backend/Test, 2 Frontend)
- Estimated LoC: ~150-200 (unter dem 250-LoC-Workflow-Limit, kein Override nötig)
- Risk Level: MEDIUM (Response-Format-Änderung ist technisch breaking, aber `WeatherMetricsTab.svelte` ist der einzige bekannte Konsument — Trip- und Vergleich-Kontext laufen durch dieselbe Instanz, Änderung bleibt kontrolliert)

### Technical Approach
Test-first im Kern-Layer (kein Netz nötig, `TestClient`-Muster aus `tests/tdd/test_sms_snow_symbols.py:539-577`). Reihenfolge: (1) roter Backend-Test für neues Array-Format inkl. `thunder`-Dedup, (2) Endpoint-Implementierung, (3) Frontend-Typen + Derived, (4) neue Anzeige-Komponente, (5) Wiring in `WeatherMetricsTab.svelte`. Eine Scheibe, kein Split nötig.

### Dependencies
- Kein bekannter zweiter Konsument von `/api/sms-symbols` außer `WeatherMetricsTab.svelte` (Trip + Vergleich-Kontext).
- Gates: Renderer-Commit-Gate (#811) greift nicht (`config.py` nicht in der gated Dateiliste). Pendant-Gate (#1481B) greift nicht (neue Komponente liegt in `shared/`). Frontend-Browser-Gate (#1558) greift automatisch beim Deploy, da Scope `frontend-only`/`full-stack` wird — keine Sonderbehandlung nötig.

### Open Questions
- [ ] Exakter finaler Name der neuen Komponente (Spec-Phase) — `MultiSymbolMetricRow.svelte` ist Arbeitstitel, keine PO-Entscheidung nötig (rein technisch).
- [ ] Reihenfolge/Platzierung der neuen Zeilen relativ zu den bestehenden 7 Schwellwert-Zeilen — visuell in Spec klären (z.B. als eigener Unterblock nach den Schwellwerten).

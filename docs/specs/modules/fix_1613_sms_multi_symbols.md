---
entity_id: fix_1613_sms_multi_symbols
type: module
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [bug, sms, frontend, api]
---

# Fix #1613 — SMS-Kürzel für Mehrfach-Symbol-Metriken fehlen im Endpoint und im Frontend

## Approval

- [ ] Approved

## Purpose

`GET /api/sms-symbols` liefert bislang nur die acht Metriken aus `SMS_SYMBOL_BY_METRIC`
(genau ein Kürzel je Metrik). Die drei Metriken `wind_chill` (FN/FK/FD/WC),
`temperature` (K/D) und `temperature_night` (N) tragen jeweils MEHRERE Kürzel
(`SMS_MULTI_SYMBOLS_BY_METRIC`) und fehlen dadurch strukturell in der Antwort —
und damit auch in jeder Anzeige, die sich auf den Endpoint stützt. Der PO hat
konkret bestätigt, dass `WC` (Gefühlte Temperatur) im Trip-Editor sichtbar
fehlt. Diese Spec behebt die Backend-Lücke und schafft den bislang nicht
existierenden Frontend-Anzeigeort für diese drei Metriken.

## Source

- **File:** `api/routers/config.py`
- **Identifier:** `get_sms_symbols()` (Zeilen 30-55)

> **Schicht-Hinweis:** Diese Spec berührt drei Schichten — Python-Core
> (`api/routers/config.py`, liest `src/output/renderers/sms_trip.py`),
> Frontend (`frontend/src/lib/components/shared/`) und einen Kern-Test
> (`tests/tdd/`). Go-API/`internal/` ist NICHT betroffen.

## Affected Files

| File | Change Type | Beschreibung |
|------|-------------|--------------|
| `api/routers/config.py` | MODIFY | `/api/sms-symbols`: `metrics`-Array liefert künftig `sms_symbols: string[]` statt `sms_symbol: string`; Merge mit Vorrang für `SMS_MULTI_SYMBOLS_BY_METRIC` |
| `tests/tdd/test_sms_snow_symbols.py` | MODIFY | Bestehende AC-8-Tests (`test_ac8_sms_symbols_endpoint_serves_register_symbols`, `test_ac8_sms_symbols_endpoint_keeps_official_snow_hazard`) lesen `e["sms_symbol"]` (Singular) — MUSS auf `e["sms_symbols"][0]` bzw. das neue Array-Format umgestellt werden, sonst brechen sie strukturell. Neue AC-Tests für dieses Issue ergänzen (Namensregel: nicht issue-nummeriert, im selben Modul-Testfile oder in `tests/unit/test_sms_symbols_endpoint.py`, falls thematisch sauberer trennbar) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `SmsSymbolEntry`/`SmsSymbolCatalog`-Typen auf `sms_symbols: string[]`; `metricSymbols`-Derived auf `Record<string, string[]>`; 7 bestehende `ThresholdMetricRow`-Aufrufe auf `metricSymbols[id]?.[0]` umstellen; 3 neue Zeilen für `temperature`/`temperature_night`/`wind_chill` verdrahten, gegated über `!buckets.off.includes(...)` |
| `frontend/src/lib/components/shared/weather-metrics-tab/MultiSymbolMetricRow.svelte` | CREATE | Neue, schlanke Zeilen-Komponente: Label + Badge-Liste, KEIN Segmented-Control (analog, aber unabhängig von `ThresholdMetricRow.svelte`) |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/multiSymbolMetricRowWiring.test.ts` | CREATE | Source-inspizierender Kern-Test (Präzedenz `day_window_card.test.ts`/`weatherMetricsTabDayWindowSave.test.ts`: kein Rendering-Harness für Svelte-5-Runen in `node:test`) — prüft Wiring, Gate und Prop-Übergabe im Quelltext |

## Estimated Scope

- **LoC:** ~150-200
- **Files:** 5 (2 Backend/Test, 3 Frontend/Test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `metric_catalog.get_sms_code()` (Register) | Upstream | Quelle für `SMS_SYMBOL_BY_METRIC` (unverändert) |
| `SMS_MULTI_SYMBOLS_BY_METRIC` (`src/output/renderers/sms_trip.py:118-123`) | Upstream | Bereits korrekte Handliste — bisher vom Endpoint nie gelesen, das ist die Root Cause |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Downstream | Einziger bekannter Konsument von `/api/sms-symbols`, Trip- UND Vergleich-Kontext (dieselbe Komponenten-Instanz, `context === 'vergleich'` lädt denselben Endpoint) |
| `ThresholdMetricRow.svelte` | Downstream (unverändert) | Prop-Signatur `smsSymbol?: string` bleibt bestehen; Call-Sites liefern künftig `metricSymbols[id]?.[0]` |

## Implementation Details

```
# api/routers/config.py — get_sms_symbols()

from output.renderers.sms_trip import SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC

def _symbols_for(metric_id: str) -> list[str]:
    # SMS_MULTI_SYMBOLS_BY_METRIC hat Vorrang (deckt z.B. "thunder" bereits
    # vollstaendig ab -> kein Duplikat-Eintrag mit SMS_SYMBOL_BY_METRIC).
    if metric_id in SMS_MULTI_SYMBOLS_BY_METRIC:
        return [s.rstrip(":") for s in SMS_MULTI_SYMBOLS_BY_METRIC[metric_id]]
    return [SMS_SYMBOL_BY_METRIC[metric_id].rstrip(":")]

all_metric_ids = list(SMS_SYMBOL_BY_METRIC.keys()) + [
    mid for mid in SMS_MULTI_SYMBOLS_BY_METRIC if mid not in SMS_SYMBOL_BY_METRIC
]
# -> 8 + 3 (temperature, temperature_night, wind_chill) = 11 Eintraege,
#    "thunder" erscheint genau einmal mit 2 Symbolen.

"metrics": [
    {"metric_id": mid, "sms_symbols": _symbols_for(mid)}
    for mid in all_metric_ids
]
```

```
# WeatherMetricsTab.svelte

interface SmsSymbolEntry {
    metric_id: string;
    sms_symbols: string[];   // vorher: sms_symbol: string
}
const metricSymbols = $derived(
    Object.fromEntries(
        (smsSymbols?.metrics ?? []).map((m) => [m.metric_id, m.sms_symbols])
    )
);
// bestehende ThresholdMetricRow-Aufrufe:
//   smsSymbol={metricSymbols['wind']?.[0]}   (statt metricSymbols['wind'])
// neue Zeilen (Beispiel wind_chill), Gate identisch zum bestehenden Muster:
{#if !buckets.off.includes('wind_chill')}
<MultiSymbolMetricRow
    metricId="wind_chill"
    label={metricById['wind_chill']?.label ?? 'Gefühlte Temperatur'}
    symbols={metricSymbols['wind_chill'] ?? []}
/>
{/if}
```

`MultiSymbolMetricRow.svelte` (Props): `metricId: string; label: string; symbols: string[]`.
Rendert `data-testid="sms-multi-symbol-row-{metricId}"`, je Symbol
`data-testid="sms-symbol-badge-{metricId}-{symbol}"` als `<code>`-Badge —
analog zur `.sms-symbol`-Badge-Optik aus `ThresholdMetricRow.svelte`, aber
ohne Segmented-Control/Schwellwert-Spalte.

## Expected Behavior

- **Input:** `GET /api/sms-symbols` (keine Parameter); Frontend lädt den
  Endpoint beim Öffnen des Trip- oder Vergleich-Editors (Sektion „04 —
  Schwellwerte").
- **Output:** `metrics`-Array mit 11 Einträgen (vorher 8), jeder Eintrag
  `{"metric_id": str, "sms_symbols": string[]}`; `thunder` einmalig mit
  `["TH", "TH+"]`; `wind_chill` mit `["FN","FK","FD","WC"]`; `temperature`
  mit `["K","D"]`; `temperature_night` mit `["N"]`. Frontend zeigt für jede
  nicht abgewählte Metrik aus diesen 11 eine Zeile mit Label + Kürzel-Badges.
- **Side effects:** keine (Read-only-Endpoint, keine Persistenz-Änderung).

## Acceptance Criteria

- **AC-1:** Given der Endpoint `/api/sms-symbols` wird aufgerufen / When die
  Antwort für `metric_id == "wind_chill"` gelesen wird / Then enthält
  `sms_symbols` genau `["FN","FK","FD","WC"]` (vorher fehlte der Eintrag
  strukturell — das ist der Bug-Nachweis, rot vor Fix, grün nach Fix).
  - Test: `TestClient(app).get("/sms-symbols")`-Pattern aus
    `tests/tdd/test_sms_snow_symbols.py:539-577`, Assertion auf das
    vollständige Array statt auf String-Presence.

- **AC-2:** Given `thunder` trägt laut `SMS_MULTI_SYMBOLS_BY_METRIC` zwei
  Kürzel (`TH:`, `TH+:`) / When `/api/sms-symbols` aufgerufen wird / Then
  erscheint `thunder` genau EINMAL im `metrics`-Array mit
  `sms_symbols == ["TH", "TH+"]` — kein Duplikat-Eintrag aus
  `SMS_SYMBOL_BY_METRIC`.
  - Test: Zählt Einträge mit `metric_id == "thunder"` (muss genau 1 sein) und
    prüft den vollständigen Array-Inhalt.

- **AC-3:** Given die sieben Nicht-thunder-Metriken aus
  `SMS_SYMBOL_BY_METRIC` (precipitation, rain_probability, wind, gust,
  snow_depth, snowfall_limit, fresh_snow) / When `/api/sms-symbols`
  aufgerufen wird / Then liefert jede davon ein einelementiges Array mit
  demselben Kürzel wie vor dieser Änderung (Regressionsschutz, u.a. gegen
  das bestehende AC-8 aus #1435 E3b für `snow_depth`→`SD`,
  `snowfall_limit`→`SL`).
  - Test: bestehende `test_ac8_sms_symbols_endpoint_serves_register_symbols`
    auf das neue Array-Format umgestellt, Werte unverändert erwartet.

- **AC-4:** Given ein Trip-Editor mit aktivierter Metrik „Gefühlte
  Temperatur" (`wind_chill` nicht in `buckets.off`) / When die
  Schwellwerte-Sektion im Quelltext auf ihr Wiring geprüft wird / Then ist
  eine `MultiSymbolMetricRow` mit `metricId="wind_chill"` und
  `symbols={metricSymbols['wind_chill']}` (nicht leer, nicht hartcodiert)
  im `!buckets.off.includes('wind_chill')`-Zweig verdrahtet — die
  Sichtbarkeit von Kürzel `WC`, nicht nur, dass der Endpoint es liefert.
  - Test: source-inspizierender Frontend-Test (Präzedenz
    `weatherMetricsTabDayWindowSave.test.ts`: kein Rendering-Harness für
    Svelte-5-Runen in `node:test`) extrahiert den `wind_chill`-Block und
    prüft Komponente, Prop-Bindung und Gate-Bedingung im Quelltext. Die
    tatsächliche Pixel-Sichtbarkeit von „WC" wird zusätzlich bei der
    Staging-Validierung vor dem Prod-Deploy (Liefer-Workflow Schritt 3,
    echter Browser) bestätigt — Kern-Layer kann das laut Projekt-Präzedenz
    nicht rendern.

- **AC-5:** Given `wind_chill` ist abgewählt (`buckets.off` enthält
  `'wind_chill'`) / When die Schwellwerte-Sektion rendert / Then erscheint
  KEINE `MultiSymbolMetricRow` für `wind_chill` — exakt dasselbe Gate-Muster
  wie die sieben bestehenden Schwellwert-Zeilen.
  - Test: derselbe source-inspizierende Test wie AC-4 prüft, dass der Block
    in ein `{#if !buckets.off.includes('wind_chill')}` eingebettet ist.

- **AC-6:** Given die sieben bestehenden `ThresholdMetricRow`-Aufrufe lesen
  künftig `metricSymbols[id]?.[0]` statt `metricSymbols[id]` (Typwechsel
  `string` → `string[]`) / When der Katalog geladen ist / Then zeigt z.B.
  die Wind-Zeile weiterhin exakt das Kürzel, das vor dieser Änderung
  angezeigt wurde — kein Wertverlust durch die Typumstellung.
  - Test: Backend-Test bestätigt `sms_symbols[0]` für `wind` unverändert;
    Frontend-Test prüft, dass alle 7 Call-Sites auf `?.[0]` umgestellt sind
    (kein verbliebener direkter String-Zugriff).

## Known Limitations

- Kein Rendering-Harness für Svelte-5-Runen in diesem `node:test`-Setup
  (`@testing-library/svelte` nicht installiert) — der Frontend-Kern-Test
  bleibt source-inspizierend (Präzedenz `day_window_card.test.ts`). Die
  echte Browser-Sichtbarkeit wird final bei der Staging-Validierung vor dem
  Prod-Deploy geprüft, nicht im Kern-Layer.
- Response-Format-Änderung (`sms_symbol: string` → `sms_symbols: string[]`)
  ist technisch ein Breaking Change, kein additiver — kontrolliert, da
  `WeatherMetricsTab.svelte` der einzige bekannte Konsument ist (Trip- und
  Vergleich-Kontext laufen durch dieselbe Instanz).
- `fresh_snow` fehlt weiterhin in der Schwellwerte-Sektion (kein Bestandteil
  dieses Issues, laut Kontext-Analyse unstrittig).
- Reihenfolge der drei neuen Zeilen (`temperature`, `temperature_night`,
  `wind_chill`) folgt der Reihenfolge in `SMS_MULTI_SYMBOLS_BY_METRIC` — keine
  gesonderte PO-Vorgabe dazu bekannt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche im Sinne von `docs/adr/README.md`
  (kein neuer Kanal, Provider, Datenmodell/Persistenz, Auth oder
  Editor-Paradigma) — reine Bugfix-Erweiterung eines bestehenden Read-only-
  Endpoints und eine neue, geteilte Anzeige-Komponente im etablierten Muster.

## Changelog

- 2026-08-08: Initial spec created (Issue #1613)

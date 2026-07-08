---
entity_id: issue_1104_compare_config_foundation
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [compare, preset, display_config, wiring, top_n, active_metrics]
workflow: fix-1094-compare-config
---

# Ortsvergleich A: Fundament — Editor-Config wirkt im Versand + Anzahl Orte

## Approval

- [x] Approved (PO „go", 2026-07-08)

## Purpose

Der Compare-Editor speichert Einstellungen (`display_config`) in `ComparePreset`, aber der
tatsächliche Versandpfad (`send_one_compare_preset`) liest daraus **nichts** — er ruft
`render_compare_email(result, profile=profile)` ohne `top_n_details`/`enabled_metrics` auf. Damit
verpuffen alle im Editor getroffenen Einstellungen folgenlos (Root-Cause von Issue #1094/#1092
Teil B). Dieses Slice legt das **Fundament**: einen kanonischen ID-Resolver, der die vier
inkompatiblen Metrik-Vokabulare des Compare-Features (Katalog, Renderer, Frontend-`active_metrics`,
Channel-Layout) für den Renderer-Aufruf zusammenführt, verdrahtet `display_config` erstmals in den
Versandpfad, und liefert mit **Punkt 5 („Anzahl Orte im Stundenverlauf")** den ersten Ende-zu-Ende
sichtbaren Beweis, dass Editor-Konfiguration jetzt wirklich in der versendeten Mail ankommt.

## Source

- **File:** `src/services/scheduler_dispatch_service.py`
- **Identifier:** `send_one_compare_preset()` — liest `display_config.top_n` /
  `display_config.active_metrics` und reicht sie an `render_compare_email()` durch.
- **Neues Modul:** `src/output/renderers/compare_metric_ids.py` —
  `resolve_enabled_metrics()`, kanonischer ID-Resolver.

> **Schicht-Hinweis:** Python-Core (`src/services/`, `src/output/renderers/`) für Wiring +
> Resolver. SvelteKit-Frontend (`frontend/src/lib/components/compare/`) für die UI-Control und
> den Preset-Save-Pfad. **Kein Go-Struct-Change nötig** — `display_config` ist in
> `internal/model/compare_preset.go:33` bereits `map[string]interface{}` und wird vom Handler
> (`internal/handler/compare_preset.go:207-208`) transparent durchgereicht, solange der Client
> (Frontend) das clientseitige Round-Trip-Spread-Prinzip einhält (siehe
> `compareEditorSave.ts::buildComparePresetSavePayload`).

## Estimated Scope

- **LoC:** ~220–260 (Implementierung ~90, Tests ~150–170 — nahe am 250-LoC-Limit; falls
  überschritten, User vor `loc_limit_override` explizit fragen, nicht eigenmächtig setzen)
- **Files:** 8 (1 neu: Resolver-Modul; 1 neu: Backend-Test; 1 neu: Frontend-Test; 5 geändert)
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/compare_metric_ids.py` | CREATE | Kanonischer ID-Resolver: Frontend-`active_metrics`-IDs → Renderer-/`CE_PROFILES`-IDs |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset()` liest `display_config.top_n`/`active_metrics`, übergibt beide an `render_compare_email()` |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | MODIFY | Neue UI-Control „Anzahl Orte mit stündlichem Detail" (1–10) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | `topN`-State in `saveNewPreset()`/`saveComparePreset()` (Preset-Pfad) statt nur im toten Legacy-Subscription-Pfad verdrahten |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits.topN` + Round-Trip-Merge in `display_config.top_n` |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | `state.topN` beim Laden eines bestehenden Presets aus `display_config.top_n` hydrieren |
| `frontend/src/lib/types.ts` | MODIFY | Dokumentationskommentar an `ComparePreset.display_config` um `top_n`/`active_metrics` ergänzt (kein neues typisiertes Feld nötig) |
| `tests/tdd/test_issue_1104_compare_config_foundation.py` | CREATE | Backend-Wiring-Tests (AC-2/AC-4), reale `ComparisonEngine` + Fixture-Provider, Funktions-Rebind-Sentinel statt Mock |
| `frontend/src/lib/components/compare/compareEditorTopN.test.ts` | CREATE | Pure-Function Round-Trip-Test für `topN` in `buildComparePresetSavePayload()` (AC-3, Client-Ebene) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.comparison::render_compare_email(top_n_details=, enabled_metrics=)` | Upstream, unverändert | Signatur existiert bereits (Zeile 462-496) und akzeptiert beide Parameter — nur der Aufrufer nutzt sie noch nicht |
| `output.renderers.email.compare_html::CE_PROFILES` / `_render_matrix()` | Upstream, unverändert | Renderer-Vokabular (`snow_depth_cm`, `snow_new_cm`, `sunny_hours`, `wind_max`, `cloud_avg`, `temp_max`, `gust_max`, `score`); Filter-Logik (`enabled_metrics is not None`, Zeile 432-434) bereits vorhanden |
| `frontend/.../compareMetricDefs.ts::ALL_METRICS` | Upstream, unverändert | Frontend-Vokabular (`snow_depth_cm`, `snow_new_sum_cm`, `sunny_hours_h`, `wind_max_kmh`, `cloud_avg_pct`, `temp_max_c`, u.a.) — Quelle der Frontend-seitigen IDs für den Resolver |
| `frontend/.../compareEditorSave.ts::buildComparePresetSavePayload` (Round-Trip-Spread) | Muster-Referenz | Etabliertes additives Merge-Prinzip für `display_config` — `top_n` folgt demselben Muster wie `active_metrics` (Zeile 53-60) |
| `frontend/.../compareWizardState.svelte.ts::topN` (Zeile 42) | Bestehender, toter State | `$state(3)` existiert bereits, ist aber nur im Legacy-Subscription-Pfad (`save()`) verdrahtet, NICHT im aktiven Preset-Pfad (`saveNewPreset()`/`saveComparePreset()`) — dieses Slice verdrahtet ihn dorthin um |
| `src/services/scheduler_dispatch_service.py::send_one_compare_preset` (Zeile 198-260) | Ziel-Funktion | Versandpfad für Daily-Loop UND Einzelversand-Button (`/send`) — beide teilen sich diese Funktion |
| Issue #1040 (`official_alerts_enabled`) | Muster-Referenz | Analoges additives, preset-basiertes Konfigurationsfeld mit Read-Modify-Write-Test-Pattern (`tests/tdd/test_issue_1040_alerts_toggle.py`) |
| Issue #764 (`forecast_hours`) | Muster-Referenz | Analoges Recording-Sentinel-Testmuster für den Versandpfad (`tests/tdd/test_issue_764_compare_forecast_hours_consume.py`) |

## Implementation Details

```python
# NEU: src/output/renderers/compare_metric_ids.py
# Kanonischer ID-Resolver: Frontend `active_metrics`-IDs -> Renderer/CE_PROFILES-IDs.
# Loest NUR Vokabular 3 -> Vokabular 2 (siehe docs/context/fix-1094-compare-config.md,
# Abschnitt "Vier inkompatible Metrik-Vokabulare"). Vokabular 1 (Katalog) und 4
# (Step4Layout Channel-Layout) sind nicht Teil dieses Slices.

FRONTEND_TO_RENDERER_METRIC_ID: dict[str, str] = {
    "snow_depth_cm": "snow_depth_cm",
    "snow_new_sum_cm": "snow_new_cm",
    "sunny_hours_h": "sunny_hours",
    "wind_max_kmh": "wind_max",
    "cloud_avg_pct": "cloud_avg",
    "temp_max_c": "temp_max",
    # visibility_min_m, precip_sum_mm, uv_index_max, thunder_level_max: kein
    # ComparisonResult-Feld -> bewusst nicht gemappt (Folge-Scope, s. Known Limitations).
}


def resolve_enabled_metrics(active_metrics: list[str] | None) -> set[str] | None:
    """Rueckgabe None (= kein Filter, alle Metriken sichtbar) wenn active_metrics
    leer/None ist -- rueckwaertskompatibler Default (AC-2/AC-4). Nicht mappbare
    IDs werden verworfen statt zum Absturz zu fuehren; bildet die Auswahl komplett
    auf nichts Mappbares ab -> ebenfalls None (kein leeres Matrix-Rendering)."""
    if not active_metrics:
        return None
    resolved = {
        FRONTEND_TO_RENDERER_METRIC_ID[m]
        for m in active_metrics
        if m in FRONTEND_TO_RENDERER_METRIC_ID
    }
    return resolved or None
```

```python
# src/services/scheduler_dispatch_service.py — send_one_compare_preset(), Zeile ~250
# VORHER: html_body, text_body = render_compare_email(result, profile=profile)
from output.renderers.compare_metric_ids import resolve_enabled_metrics

display_config = preset.get("display_config") or {}
top_n_raw = display_config.get("top_n")
top_n_details = int(top_n_raw) if top_n_raw is not None else 3  # Default 3 (AC-2)
enabled_metrics = resolve_enabled_metrics(display_config.get("active_metrics"))

html_body, text_body = render_compare_email(
    result,
    profile=profile,
    top_n_details=top_n_details,
    enabled_metrics=enabled_metrics,
)
```

```typescript
// frontend/.../compareEditorSave.ts — CompareEditorEdits (Zeile 13-26), analog
// activeMetricKeys/forecastHours. Optional -> rueckwaertskompatibel.
topN?: number;

// in buildComparePresetSavePayload(), analog Zeile 53-60 (active_metrics-Block)
if (edits.topN !== undefined) {
	displayConfig.top_n = edits.topN;
}
```

```typescript
// frontend/.../compareWizardState.svelte.ts — saveNewPreset() (Zeile 154-185):
// display_config-Objekt um top_n ergaenzen, analog active_metrics (Zeile 172).
...(this.topN !== undefined ? { top_n: this.topN } : {})

// saveComparePreset() (Zeile 193-217): topN an buildComparePresetSavePayload uebergeben,
// analog activeMetricKeys/forecastHours (Zeile 203-205).
topN: this.topN,
```

```typescript
// frontend/src/routes/compare/[id]/edit/+page.svelte — nach Zeile 35 (forecastHours-Hydration)
state.topN = (state.existingDisplayConfig.top_n as number) ?? 3;
```

```svelte
<!-- frontend/.../steps/Step5Versand.svelte — neue Sektion analog "Horizont"
     (Zeile 130-144), NICHT Step4Layout (dort geht es um Spalten-Layout pro
     Kanal, top_n betrifft die Stunden-Detail-Sektion selbst) -->
<section class="space-y-2">
	<Eyebrow>Stundenverlauf</Eyebrow>
	<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
		<label for="compare-step5-topn" class="text-sm text-[var(--g-ink-muted)]">
			Anzahl Orte mit stündlichem Detail
		</label>
		<input
			id="compare-step5-topn"
			type="number"
			min="1"
			max="10"
			data-testid="compare-step5-topn"
			bind:value={state.topN}
			class="w-20 border rounded px-2 py-1 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
		/>
	</GCard>
</section>
```

Frontend-Typ `ComparePreset.display_config` (`types.ts:494`) ist bereits `Record<string, unknown>`
— kein neues typisiertes Feld nötig (anders als `official_alerts_enabled` bei #1040, das ein
Top-Level-Feld war). Der bestehende Dokumentationskommentar an `display_config` wird um `top_n` /
`active_metrics` ergänzt (aktuell listet er nur `ideal_ranges, channel_layouts, region`, obwohl
`active_metrics` bereits seit #680 existiert — Nachpflege der Doku, kein Verhaltens-Fix).

## Expected Behavior

- **Input:** `ComparePreset.display_config.top_n` (Zahl 1-10 oder fehlend) und
  `display_config.active_metrics` (Liste von Frontend-Metrik-IDs oder fehlend/leer).
- **Output:** Die tatsächlich per E-Mail versendete Compare-Mail (Daily-Loop UND
  Einzelversand-Button) zeigt im Stunden-Verlauf-Abschnitt genau `top_n` Orte (bzw. 3 als
  Default). Ist `active_metrics` gesetzt, wird die resolvte Teilmenge nachweislich an
  `render_compare_email()` durchgereicht statt wie bisher komplett ignoriert zu werden.
- **Side effects:** Keine — reine Lesezugriffe auf bereits persistierte Preset-Felder, kein neuer
  Netzwerk-Call, keine Schema-Migration (Go-Seite unverändert).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat im Compare-Editor „Anzahl Orte im Stundenverlauf" auf einen Wert
  N (1 ≤ N ≤ Anzahl konfigurierter Orte) eingestellt und gespeichert, When der Versand ausgelöst
  wird (Daily-Loop oder Einzelversand-Button), Then zeigt die tatsächlich zugestellte Compare-Mail
  im Stunden-Verlauf-Bereich genau N Orte mit eigenem Stunden-Detail-Abschnitt — nicht mehr und
  nicht weniger.
  - Test: Preset mit `display_config.top_n=N` über den echten Preset-Pfad speichern, Versand
    real auslösen, Mail via IMAP aus `gregor-test@henemm.com` abrufen, Anzahl der
    „— Stundenverlauf"-Abschnitte (ein Abschnitt pro Ort) in der HTML-Mail zählen und gegen N
    prüfen. Kein Dateiinhalt-Check gegen Code — Beweis gegen die real zugestellte Mail.

- **AC-2:** Given ein Compare-Preset ohne das Feld `top_n` (Bestandsdaten, angelegt vor diesem
  Slice) oder ein Nutzer, der die Einstellung nie angefasst hat, When der Versand ausgelöst wird,
  Then zeigt die zugestellte Mail weiterhin genau 3 Orte im Stunden-Verlauf (identisches Verhalten
  zu vor diesem Slice) — keine Regression, Bestandsdaten laden und versenden sich unverändert still.
  - Test: Preset ohne `top_n`-Feld (simuliert Altdaten) über denselben realen Versandpfad senden,
    zugestellte Mail abrufen, genau 3 „— Stundenverlauf"-Abschnitte zählen.

- **AC-3:** Given ein bestehendes, persistiertes Compare-Preset mit befüllten Feldern (Empfänger,
  Zeitfenster, Profil, andere `display_config`-Einträge wie `region`/`ideal_ranges`), When der
  Nutzer im Editor ausschließlich „Anzahl Orte im Stundenverlauf" ändert und speichert, Then bleiben
  alle anderen Felder des Presets (Empfänger, Zeitfenster, Profil, `region`, `ideal_ranges`,
  `channel_layouts`) byte-identisch zum Zustand vor dem Speichern — kein Datenverlust durch
  Replace-statt-Merge. Derselbe Ablauf wird für zwei unterschiedliche Nutzer wiederholt, um
  auszuschließen, dass das Speichern eines Nutzers das Preset eines anderen Nutzers berührt.
  - Test: Preset mit mehreren befüllten Feldern über die reale Save-Route (`PUT
    /api/compare/presets/{id}`) laden, nur `top_n` über den Editor-Pfad ändern, gespeichertes
    Preset erneut laden und alle unveränderten Felder auf Gleichheit mit dem Vorzustand prüfen —
    für zwei getrennte `user_id`-Verzeichnisse.

- **AC-4:** Given ein Nutzer hat im Compare-Editor eine Metrik-Auswahl (Schritt Idealwerte)
  gespeichert, When der Versand ausgelöst wird, Then wird diese Auswahl nachweislich an den
  Rendering-Schritt weitergereicht (beobachtbar daran, dass der tatsächlich an
  `render_compare_email()` übergebene Metrik-Filter die gespeicherte Auswahl widerspiegelt) —
  statt wie bisher (vor diesem Slice) komplett ignoriert zu werden, weil der Versandpfad
  `display_config` gar nicht liest. Ist keine Auswahl gespeichert, wird kein Filter angewendet
  (alle Metriken wie vor diesem Slice). Die vollständige, korrekte Filterwirkung jeder einzelnen
  Metrik-Zeile in der Vergleichsmatrix (welche Zeile bei welcher Auswahl erscheint/verschwindet)
  ist Gegenstand von Folge-Issue #1105 und nicht Teil dieser Prüfung.
  - Test: Backend-Wiring-Test auf Höhe von `send_one_compare_preset()` — Preset mit
    `display_config.active_metrics=["wind_max_kmh","cloud_avg_pct"]` real durch den Versandpfad
    laufen lassen (echte `ComparisonEngine`, Offline-Fixture-Provider), den tatsächlich an
    `render_compare_email()` übergebenen `enabled_metrics`-Kwarg aufzeichnen (echte
    Funktions-Rebind-Sentinel-Technik wie in `test_issue_1040_alerts_toggle.py` /
    `test_issue_764_compare_forecast_hours_consume.py`, kein `Mock()`), und gegen
    `{"wind_max", "cloud_avg"}` prüfen. Zweiter Testfall ohne `active_metrics`: aufgezeichneter
    Kwarg muss `None` sein.

## Test Plan

**TDD RED (lokal, keine Mocks):**

- `tests/tdd/test_issue_1104_compare_config_foundation.py` — mirrort Stil/Muster von
  `test_issue_1040_alerts_toggle.py` (echte `ComparisonEngine`, Offline-`FixtureProvider` via
  `GZ_TEST_FIXTURE_DIR`, In-Memory-`SavedLocation` über `all_locations_cache`, keine Schreib-
  Seiteneffekte im echten `data/`-Verzeichnis):
  - AC-4-Testfall: `render_compare_email` auf Modul `output.renderers.comparison` real
    rebinden (plain Funktions-Rebind, kein `patch()`), Sentinel-Exception nach Aufzeichnung der
    Kwargs `top_n_details`/`enabled_metrics`, restauriert in `finally` — **kein Mock**, der echte
    `ComparisonEngine`-Lauf (inkl. Fixture-Provider) findet vollständig statt, nur der letzte
    Schritt (Render + SMTP) wird gezielt vor dem eigentlichen Rendern abgefangen.
  - Zusätzlicher reiner Unit-Test für `resolve_enabled_metrics()` (keine Fixtures nötig):
    bekannte IDs → korrektes Mapping-Set; leere/`None`-Eingabe → `None`; unbekannte IDs →
    verworfen statt Absturz.
- `frontend/src/lib/components/compare/compareEditorTopN.test.ts` — pure-function Node-Test
  (kein Browser, `node --experimental-strip-types`, Muster:
  `compareEditorForecastHours.test.ts`): `buildComparePresetSavePayload()` mit `edits.topN`
  gesetzt/ungesetzt gegen ein `original`-Preset mit mehreren befüllten `display_config`-Feldern
  prüfen (Round-Trip-Beweis für AC-3 auf Client-Ebene).

**E2E/Verhalten gegen echte Staging-Mail (Post-Push, `/e2e-verify`, PFLICHT vor „E2E bestanden"):**

- Echtes Compare-Preset über den Staging-Preset-Pfad mit `display_config.top_n=1` (bzw. `2`)
  anlegen/speichern, Versand real auslösen (Einzelversand-Button `/send` oder Daily-Loop-Trigger),
  Mail via IMAP aus dem Stalwart-Test-Postfach (`gregor-test@henemm.com`, Creds `GZ_IMAP_*`)
  abrufen. Vor dem Fix: 3 „— Stundenverlauf"-Abschnitte trotz `top_n=1` (rot). Nach dem Fix:
  genau 1 Abschnitt (grün) — direkter, aus Nutzersicht sichtbarer Beweis für AC-1.
  Zweiter Lauf ohne `top_n` bestätigt AC-2 (weiterhin 3 Abschnitte, keine Regression).
- Marker-Header `X-GZ-Mail-Type: compare` prüfen, `email_spec_validator.py` laufen lassen
  (Pflicht-Validator für den Compare-Mail-Pfad). Schlägt der Validator aus Gründen fehl, die mit
  dem bekannten Label-/Zeilenanzahl-Risiko (siehe Known Limitations) zusammenhängen und nicht mit
  `top_n`/`active_metrics`, wird dafür ein eigenes Follow-up-Issue angelegt statt der Validator
  im Rahmen dieses Fixes verändert.

## Known Limitations

- **Vollständige Matrix-Metrik-Filterwirkung ist #1105:** Dieses Slice reicht `enabled_metrics`
  durch (Fundament), verifiziert aber nicht row-genau, welche Matrix-Zeile bei welcher Auswahl
  erscheint/verschwindet — das ist Gegenstand von Folge-Issue #1105.
- **Schneehöhe-Abwählbarkeit ist #1105/#1106:** Punkt 2 (Schneehöhe weg/nicht wählbar) wird durch
  das Fundament technisch möglich (sobald der Filter greift, ist Schneehöhe abwählbar wie jede
  andere Metrik), die PO-Entscheidung „wie genau" und deren Verifikation ist nicht Teil dieses
  Slices.
- **Hourly-Metriken (Temp/Wind/Wolken im Stunden-Verlauf) sind #1107:** `_render_hourly_section()`
  bleibt hartkodiert (Temp/Wind/Wolken) — nur die Anzahl der Orte (top_n) wird in diesem Slice
  konfigurierbar, nicht die dort gezeigten Spalten.
- **Sektions-Toggles sind #1106/#1107:** Ein/Ausblenden ganzer Report-Elemente (Winner-Box, Tags,
  Warnungen, Matrix, Hourly) existiert in diesem Slice nicht.
- **Metriken ohne `ComparisonResult`-Feld nicht einschaltbar:** `visibility_min_m`,
  `precip_sum_mm`, `uv_index_max`, `thunder_level_max` sind im Frontend wählbar, haben aber kein
  Renderer-Pendant (kein `LocationResult`-Attribut) und werden vom Resolver bewusst nicht gemappt
  — Auswahl dieser Metriken hat in der Compare-Mail (anders als im Trip-Report) keine Wirkung.
  Würde Engine+Scoring-Erweiterung erfordern, nicht Teil des Regressions-Fixes.
- **Renderer-interne IDs ohne Frontend-Pendant (`score`, `gust_max`) unbehandelt:** Diese
  erscheinen in `CE_PROFILES`, haben aber keine wählbare Entsprechung in
  `compareMetricDefs.ts`. Wird eine `active_metrics`-Auswahl gespeichert, filtert der bestehende
  `enabled_metrics`-Mechanismus (`compare_html.py:432-434`) `score`/`gust_max`-Zeilen automatisch
  heraus, da sie nie im resolvten Set enthalten sind. Ob das erwünscht ist (z.B. „Score sollte
  immer sichtbar bleiben"), ist eine Design-Frage für #1105, nicht für dieses Fundament-Slice.
- **`CompareSubscription`-Legacy-Pfad (`compare_subscription.py`) unverändert:** Nur die
  CLI-getriebene, für den echten Mail-Versand tote Subscription-Route existiert dort; sie wird
  von diesem Slice nicht angefasst.
- **Bekanntes Validator-Risiko (nicht durch dieses Slice verursacht):** `email_spec_validator.py`
  erwartet aktuell englische Zeilenlabels („Snow Depth", „Wind/Gusts" etc.) und eine feste
  8-Zeilen-Matrix, während der aktive Renderer (`compare_html.py::METRIC_LABELS`) deutsche Labels
  und variable Zeilenanzahl (3 primary + 3 secondary je Profil) liefert. Dieser Verdacht ist im
  Analyse-Dokument (`docs/context/fix-1094-compare-config.md`, Risiken) bereits als separat zu
  prüfender Nebenbefund vermerkt — betrifft die Matrix-Struktur-Checks, nicht die in diesem Slice
  geprüften Hourly-Abschnitte/Location-Count-Checks. Falls dieses Risiko die E2E-Verifikation
  dieses Slices blockiert, wird dafür ein eigenes Follow-up-Issue angelegt statt den Validator
  selbst im Rahmen dieses Fixes aufzuweichen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additives Feld in einem bereits bestehenden, typlosen `display_config`-Blob nach
  etabliertem Muster (#1040 `official_alerts_enabled`, #764 `forecast_hours`, #680
  `active_metrics`). Der neue Resolver ist eine reine, seiteneffektfreie Mapping-Funktion ohne
  neue Abhängigkeiten oder Architektur-Entscheidung.

## Changelog

- 2026-07-08: Initial spec created (Issue #1104, Slice A von #1094/#1092 Teil B).
- 2026-07-08: Resolver von renderers/email/ nach renderers/ verschoben (renderer_mail_gate-Fehlklassifikation, s. #1112).

---
entity_id: output_token_builder
type: module
created: 2026-04-25
updated: 2026-04-26
status: draft
version: "1.1"
tags: [output, pipeline, refactor, epic-render-pipeline]
epic: render-pipeline-consolidation (#96)
phase: β1
---

# Output Token Builder

## Approval

- [x] Approved

## Purpose

Zentrale Funktion `build_token_line()` extrahieren, die aus `NormalizedForecast` und `UnifiedWeatherDisplayConfig` eine `TokenLine` (DTO) produziert. Diese ist die **Single Source of Truth** für alle Channels (SMS, E-Mail, Push) gemäß `sms_format.md` v2.0 §11.

Heute existiert die Token-Logik **dreimal** in unterschiedlichen Ausprägungen (`sms_trip.py`, `trip_report.py`, `wintersport.py`). β1 führt sie zusammen und richtet sie strikt nach `sms_format.md` v2.0 aus. Output-Verhalten der bestehenden Caller bleibt in β1 unverändert (additiver Builder, keine Migration).

## Source

- **File (neu):** `src/output/tokens.py` (≤500 LoC, bei Überschreitung Submodule, siehe Architektur-Entscheidungen)
- **Identifier:** `build_token_line()`, `TokenLine`, `Token`
- **Tests (neu):** `tests/unit/test_token_builder.py`, `tests/golden/test_sms_golden.py`

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.models.NormalizedForecast` | input | Tagesweise aggregierte Wetterdaten |
| `app.models.UnifiedWeatherDisplayConfig` | input | User-Config: enabled/aggregations/use_friendly_format |
| `app.metric_catalog.MetricDefinition` | input | Token-Symbole, Friendly-Labels, Default-Thresholds |
| `services.risk_engine.RiskEngine` | input | Risk-Klassifikation für Truncation-Priorisierung |
| `reference/sms_format.md` v2.0 | spec | **Authority** — Token-Reihenfolge §2, Definition §3, Threshold+Peak §5, Truncation §6 |

> **Hinweis (v1.1):** `formatters.sms_trip.SMSTripFormatter` wird **nicht mehr** als Cross-Check-Referenz verwendet. Begründung siehe Abschnitt "Architektur-Entscheidungen v1.1".

## Architektur-Entscheidungen v1.1

### A1. Authority ist `sms_format.md` v2.0 — kein Cross-Check gegen Legacy

In v1.0 forderte die Spec einen byte-Equal-Cross-Check `new == old` gegen `src/formatters/sms_trip.py`. Diese Anforderung wird **gestrichen**, weil:

1. **`sms_trip.py` ist deprecated dead code.** In aktuellen Pfaden ist `sms_text=None` — der Legacy-Formatter wird nicht mehr aktiv genutzt.
2. **Format-Inkompatibilität.** Legacy erzeugt Form `E1:T12/18 W30 R5mm | E2:...` (Slash-Temperaturen, Pipe-Trennzeichen, Symbol "T"). Das ist **unvereinbar** mit `sms_format.md` v2.0 §2 / §3.2, das `{Name}: N D R PR W G TH: TH+: HR:TH:` mit getrennten N/D-Tokens vorschreibt.
3. **Authority-Konflikt.** Ein byte-Equal-Vergleich würde β1 zwingen, v2.0 zu verletzen. Das widerspricht §11 (SSOT).

**Konsequenz:** Conformance wird strukturell gegen `sms_format.md` v2.0 geprüft (siehe `test_render_conforms_to_sms_format_v2`), nicht gegen Legacy. Erste β1-Implementierung wurde aus diesem Grund verworfen (Adversary-Verdict BROKEN, F001-F005).

### A2. Token-Reihenfolge ist **POSITIONAL §2**, nicht Risk-Priority

`sms_format.md` §2 schreibt eine **feste Token-Reihenfolge** vor:

```
{Name}: N D R PR W G TH: TH+: HR:TH: Z: M: [SN SN24+ SFL AV WC] DBG
```

Diese Reihenfolge ist **statisch in der Render-Phase**. Risk-Priority (Thunderstorm > Wind/Gusts > Rain > Temperatur) gilt **ausschließlich für Truncation gemäß §6** (welche Tokens fliegen zuerst raus). Sie steuert **nicht** die Anzeige-Reihenfolge.

**Konsequenz:** Algorithmus-Schritt 7 in v1.0 ("Sortierung nach priority — Thunder zuerst") **entfällt**. `Token.priority` bleibt als Feld erhalten, wird aber nur vom Truncation-Algorithmus konsumiert.

### A3. Token-Symbole strikt §3.2 — `N`/`D`, niemals `T`

| Symbol | Bedeutung | Quelle |
|---|---|---|
| `N` | **Nacht-Min** Temperatur (°C, ganzzahlig) — Wert am letzten GEO-Punkt der Etappe |
| `D` | **Tag-Max** Temperatur (°C, ganzzahlig) — MAX über alle GEO-Punkte |
| `R` | Regen mm, eine Nachkommastelle |
| `PR` | Regen-Wahrscheinlichkeit % (ganzzahlig) |
| `W` | Wind km/h (ganzzahlig) |
| `G` | Böen km/h (ganzzahlig) |
| `TH` | **Forecast**-Gewitter heute (zwischen `G` und `TH+:`, mit umgebenden Spaces) |
| `TH+` | Forecast-Gewitter morgen |
| `HR` | Heavy Rain Vigilance (FR-only, direkt vor `TH:`-Vigilance, **kein Space** dazwischen) |
| `TH:` (Vigilance) | Thunderstorm Vigilance (FR-only, direkt nach `HR`, **kein Space**) |
| `Z`/`M` | Fire-Zonen (Korsika) |
| `SN` / `SN24+` / `SFL` / `AV` / `WC` | Wintersport (nur bei `profile == "wintersport"`) |
| `DBG` | Debug, nur Dry-Run |

**Hartes Verbot:** `T` als alleinstehendes Token (Legacy-Form `T12/18`) ist **niemals** zu erzeugen.

**Klärung in `filter_for_subject()` Docstring:** `D` bedeutet hier **"Tag-Max"** (Temperatur) — nicht "Debug". Diese Disambiguierung ist im Docstring zwingend zu erwähnen, weil das Subject-Format `{Etappe} – {ReportType} – {MainRisk} – D{val} W{val} G{val} TH:{level}` (§11) den Token `D` für Tag-Max verwendet.

### A4. `@hour`-Pflicht für Forecast-Tokens mit Zeitbezug

Tokens **R, PR, W, G, TH, TH+, HR** haben **Pflicht-Format**:

```
{symbol}{value}@{hour}({max_value}@{max_hour})
```

- `hour` ist ganzzahlig 0–23, **ohne führende Null** (`@7`, nicht `@07`).
- **Threshold==Max-Optimierung (§5):** Wenn der Threshold-Wert UND die Threshold-Stunde exakt dem Tagesmaximum entsprechen, entfällt der `(max@h)`-Block. Beispiel: `R0.2@6` statt `R0.2@6(0.2@6)`.
- **Null-Form:** `-` ohne `@hour` (z.B. `R-`, `PR-`, `TH:-`, `HR:-TH:-`).

### A5. HR/TH-Fusion (Vigilance) als eigener Algorithmus-Schritt

`sms_format.md` §3.3 / §3.4 schreibt:

> Die zwei Tokens bilden einen **zusammenhängenden Block** ohne Leerzeichen dazwischen.

**Regeln (β1 zwingend):**

1. **Paarweise:** HR und Vigilance-TH treten **immer paarweise** auf — entweder beide oder keiner.
2. **Format:** `HR:{level}@{h}TH:{level}@{h}` (kein Space zwischen den beiden Tokens).
3. **Null-Form paarweise:** `HR:-TH:-`.
4. **Reihenfolge fix:** `HR` immer **vor** `TH` (Vigilance).
5. **Geographische Geltung:** Nur wenn `provider == "meteofrance"` (FR-only). **Außerhalb FR werden BEIDE Tokens komplett weggelassen** (keine `-`-Form).

Dies ist ein **eigenständiger Render-Schritt** im Algorithmus (siehe Implementation Details).

### A6. LoC-Budget — 500 LoC hartes Limit

`src/output/tokens.py` darf **maximal 500 LoC** umfassen. Bei Überschreitung ist Refactor in Submodule zwingend:

- `src/output/tokens/builder.py` — `build_token_line()` Orchestrierung
- `src/output/tokens/metrics.py` — Pro-Metric-Berechnung (Threshold, Peak, Aggregation)
- `src/output/tokens/render.py` — Render-Phase + HR/TH-Fusion + Truncation

**Kontext:** Vorheriger β1-Versuch hatte 638 LoC und wurde verworfen.

## Implementation Details

### TokenLine DTO

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Token:
    """Ein einzelner Token in der Token-Zeile."""
    symbol: str               # "N", "D", "R", "W", "G", "TH", "TH+", "HR", "SN", ...
    value: str                # "0.2@6(1.4@16)" oder "" für Pflicht-Null-Tokens
    category: Literal["forecast", "vigilance", "fire", "wintersport", "debug"]
    priority: int             # NUR für Truncation §6: 1=TH, 2=W/G, 3=R/PR, 4=N/D, 5=other
    morning_visible: bool     # M-Toggle
    evening_visible: bool     # A-Toggle

    def render(self) -> str:
        """Token im Wire-Format. Stunden ohne führende Null. Null-Form: '{symbol}-'."""
        ...


@dataclass(frozen=True)
class TokenLine:
    """Komplette Token-Zeile gemäß sms_format.md §2 / §3."""
    stage_name: str                   # "{Name}" — Etappenname/Trip-Identifier
    report_type: Literal["morning", "evening", "update", "compare"]
    tokens: tuple[Token, ...]         # In sms_format.md §2 POSITIONAL-Reihenfolge
    truncated: bool = False           # True wenn §6-Kürzung angewandt
    full_length: int = 0              # Länge OHNE Truncation (Subject-Filter)

    def render(self, max_length: int = 160) -> str:
        """
        Wire-Format: '{Name}: TOK1 TOK2 ... TOKn'.

        Tokens werden in der §2-Reihenfolge (positional) gerendert.
        HR/TH (Vigilance) werden ohne Space gefused: 'HR:M@17TH:H@17'.
        Truncation gemäß §6, falls > max_length.
        """
        ...

    def filter_for_subject(self) -> "TokenLine":
        """
        Subset für E-Mail-Subject (sms_format.md §11):
        '{Etappe} – {ReportType} – {MainRisk} – D{val} W{val} G{val} TH:{level}'.

        Hier ist D = Tag-Max-Temperatur (NICHT "Debug").
        β1: Stub — gibt self zurück. Echte Filter-Logik kommt in β2.
        """
        ...
```

### `build_token_line()` Signatur

```python
def build_token_line(
    forecast: NormalizedForecast,
    config: UnifiedWeatherDisplayConfig,
    *,
    report_type: Literal["morning", "evening", "update", "compare"],
    stage_name: str,
    profile: Literal["standard", "wintersport"] = "standard",
    risk_engine: RiskEngine | None = None,
) -> TokenLine:
    """
    Baut die kanonische Token-Zeile gemäß sms_format.md v2.0.

    Verhalten ist deterministisch: gleiche Inputs → bit-identischer Output.
    Wirft ValueError bei leerem forecast oder inkonsistenter Config.
    """
```

### Algorithmus (deterministische Reihenfolge — v1.1)

1. **Sammle aktivierbare Tokens** aus `config` mit `enabled=True` (plus Pflicht-Tokens N/D/R/PR/W/G/TH/TH+ gemäß §2).
2. **Berechne Werte** pro Token aus `forecast` (Aggregation gemäß `MetricConfig.aggregations`).
3. **Format-Entscheidung pro Token:**
   - Wenn `MetricConfig.use_friendly_format == True` und `MetricDefinition.friendly_label` existiert → Friendly-Label.
   - Sonst → Threshold+Peak (`{symbol}{val}@{h}({max}@{h})`) gemäß §5 mit `@hour`-Pflicht (A4).
   - **Threshold==Max-Optimierung:** wenn Threshold-Wert UND Threshold-Stunde dem Tagesmax entsprechen → `(max@h)`-Block weglassen.
   - **Null-Werte:** `{symbol}-` (kein `@hour`).
4. **M/A-Filter:** Tokens mit `morning_enabled=False` werden im Morning-Report weggelassen, analog Evening.
5. **Profil-Tokens** (Wintersport): Wenn `profile == "wintersport"`, zusätzliche Tokens `SN`, `SN24+`, `SFL`, `AV`, `WC` gemäß §3.6 injizieren.
6. **HR/TH-Fusion (Vigilance, A5):**
   - Nur wenn `provider == "meteofrance"`. Außerhalb FR: beide Tokens **komplett weglassen**.
   - HR und Vigilance-TH paarweise erzeugen, Reihenfolge `HR` vor `TH`.
   - Im Render: ohne Space verkettet — `HR:{l}@{h}TH:{l}@{h}` bzw. `HR:-TH:-`.
7. **Fire-Tokens** `Z:`/`M:` (§3.5) — nur wenn `trip.country == "FR"` und Zonen aktiv. Sonst Block komplett weglassen.
8. **Render in §2-POSITIONAL-Reihenfolge** (kein Sortieren nach Priority — A2):
   ```
   {Name}: N D R PR W G TH: TH+: HR:TH: Z: M: [SN SN24+ SFL AV WC] DBG
   ```
9. **Ggf. Truncation gemäß §6** — hier (und **nur hier**) wird `Token.priority` konsultiert: Reihenfolge der Entfernung ist `DBG → Wintersport → Fire → Peak-Werte → PR → D, N`. `{Name}:` plus mindestens ein Wert-/Risk-Token bleibt Pflicht (sonst `ValueError`).

### Was β1 NICHT tut

- **Keine Channel-Renderer:** `render_sms()`, `render_email()` kommen erst in β3.
- **Keine Subject-Logik:** `filter_for_subject()` ist Stub, echte Logik in β2.
- **Keine Migration der Caller:** `sms_trip.format_sms` und `trip_report.format_email` rufen weiterhin ihre eigene Logik auf. β3 stellt um.
- **Keine Subscription:** β5.
- **Keine Änderung an `src/formatters/sms_trip.py`** in β1.

β1 baut nur den Builder + den DTO + Goldens + Conformance-Test. Die alten Pfade laufen unverändert weiter.

## Expected Behavior

- **Input:** `NormalizedForecast` (≥1 Tag), `UnifiedWeatherDisplayConfig`, `report_type`, `stage_name`, optional `profile`, `risk_engine`.
- **Output:** `TokenLine` mit `tokens` in `sms_format.md` §2 POSITIONAL-Reihenfolge.
- **Side effects:** Keine. Pure function.
- **Determinismus:** Zwei Aufrufe mit identischen Inputs liefern bit-identisch dieselbe `TokenLine.render(max_length)`-Ausgabe.

## Test Plan

### Unit-Tests (`tests/unit/test_token_builder.py`)

| Test | Vorbedingung | Erwartung |
|---|---|---|
| `test_build_token_line_returns_tokenline` | Standard-Forecast + Default-Config | `isinstance(result, TokenLine)` |
| `test_token_order_thunderstorm_first` | Forecast mit TH=high und R=2mm | Token-Reihenfolge folgt **§2 POSITIONAL** (`N D R PR W G TH: TH+: …`). TH steht zwischen `G` und `TH+:` — **nicht** vor `R` (Risk-Priority gilt nur für Truncation). |
| `test_friendly_format_uses_friendly_label` | `use_friendly_format=True` + Metric mit `friendly_label="Niesel"` | Token enthält "Niesel" statt "R" |
| `test_threshold_peak_format` | R-Metric mit Threshold 0.2, Tagesmax 1.4@16h, Erst-Threshold 0.6h | `value == "0.2@6(1.4@16)"` (Stunde ohne führende Null, Threshold==Max-Optimierung greift hier nicht, da unterschiedlich) |
| `test_morning_filter_excludes_evening_only` | Token mit `morning_enabled=False` | Nicht im Output bei `report_type=morning` |
| `test_wintersport_profile_adds_sn_token` | `profile="wintersport"` | `SN`-Token im Output, an Position gemäß §2 |
| `test_render_max_length_truncates` | TokenLine mit 200 Zeichen Roh-Länge | `result.render(160) <= 160 chars` und `truncated=True` |
| `test_render_truncation_priority` | Forecast mit allen Tokens + max_length=80 | §6-Reihenfolge: `DBG → Wintersport → Fire → Peaks → PR → D/N`. Risk-Priority bestimmt **welcher Wert-Token** zuerst geht (TH bleibt am längsten). |
| `test_empty_forecast_raises` | `forecast.days == []` | `ValueError` |
| `test_determinism` | Zwei Aufrufe mit identischen Inputs | Beide `render()`-Outputs sind `==` |

### Conformance-Test (NEU in v1.1) — `tests/golden/test_sms_golden.py`

`test_render_conforms_to_sms_format_v2` ersetzt den entfernten Cross-Check und prüft strukturell gegen `sms_format.md` v2.0 §2/§3:

```python
def test_render_conforms_to_sms_format_v2():
    """Strukturelle Conformance gegen sms_format.md v2.0 für alle 5 Goldens."""
    for golden_name in ALL_GOLDENS:
        line = build_test_line(golden_name)
        rendered = line.render(160)

        # 1. Stage-Prefix '{Name}:' am Anfang
        assert rendered.startswith(line.stage_name + ":")

        # 2. Token-Reihenfolge §2 positional (N vor D vor R vor PR vor W vor G ...)
        assert_positional_order_v2(rendered)

        # 3. Forecast-Tokens haben @hour oder Null-Form
        for tok in ("R", "PR", "W", "G", "TH:", "TH+:"):
            assert_has_hour_or_null(rendered, tok)

        # 4. HR/TH-Fusion ohne Space (FR-only)
        if "HR:" in rendered:
            assert re.search(r"HR:[^\s]+TH:", rendered), "HR/TH must fuse without space"

        # 5. Niemals 'T' als alleinstehender Token (kein Legacy 'T12/18')
        assert not re.search(r"(^|\s)T\d", rendered), "Symbol 'T' is forbidden — use N/D"
```

### Golden-Master-Tests (`tests/golden/test_sms_golden.py`)

**Pflicht-Gate:** Vor β1-Implementierung müssen Goldens für 5 Profile aufgenommen sein.

| Profil | Quelle | Golden-Datei | Erwartung (beispielhaft) |
|---|---|---|---|
| GR20 Sommer | (synthetisch, Korsika Sommer-Forecast) | `tests/golden/sms/gr20-summer-evening.txt` | `GR20 E3: N12 D24 R0.2@15(2.5@17) W18@10(28@15) G25@10(40@15) TH:M@16(H@18)` |
| GR20 Frühjahr | (synthetisch, kalt + Niederschlag) | `tests/golden/sms/gr20-spring-morning.txt` | `GR20 E1: N2 D9 R0.2@4(18.5@11) W35@5(60@10) G55@5(85@10) TH:M@8(H@11)` |
| GR221 Mallorca | `data/users/default/trips/gr221-mallorca.json` | `tests/golden/sms/gr221-mallorca-evening.txt` | `GR221 Tag1: N8 D15 W25@12(40@16) G35@12(55@16)` |
| Wintersport Arlberg | (synthetisch, profile=wintersport) | `tests/golden/sms/arlberg-winter-morning.txt` | `Arlberg: N-12 D-4 W45@8(75@13) G70@8(110@13) WC-22 SN180 SN24+25 SFL1800 AV3` |
| Vigilance Korsika | (Forecast mit MétéoFrance Vigilance=high) | `tests/golden/sms/corsica-vigilance.txt` | `Corsica E5: N18 D32 R0.2@14(8@17) W30@10(55@15) G45@10(85@15) TH:H@13(H@17) HR:M@14TH:H@17 Z:HIGH208` |

> **Hinweis:** Die obigen Werte sind **Beispiele für die Spec**. Die exakten Golden-Strings werden vom Developer Agent in Phase 5/6 aus den realen Forecasts generiert und gefroren.

**Akzeptanz pro Golden:**
```python
def test_golden_gr20_summer_evening():
    forecast = load_test_forecast("gr20-summer-evening")
    config = load_test_config("gr20-summer")
    line = build_token_line(forecast, config, report_type="evening", stage_name="GR20 E3")

    expected = read_golden("sms/gr20-summer-evening.txt")
    assert line.render(160) == expected
```

### Property-Tests (Hypothesis, optional aber empfohlen)

```python
@given(forecast=normalized_forecasts(), config=display_configs())
def test_render_never_exceeds_max_length(forecast, config):
    line = build_token_line(forecast, config, report_type="morning", stage_name="X")
    assert len(line.render(160)) <= 160
```

## Akzeptanzkriterien (β1-Phase, v1.1)

- [ ] `src/output/tokens.py` existiert mit `build_token_line()`, `Token`, `TokenLine` — **≤500 LoC** (sonst Refactor in Submodule)
- [ ] Alle 10 Unit-Tests grün (in `tests/unit/test_token_builder.py`)
- [ ] Alle 5 Golden-Tests grün (in `tests/golden/test_sms_golden.py`)
- [ ] Conformance-Test `test_render_conforms_to_sms_format_v2` grün für alle 5 Goldens
- [ ] Token-Reihenfolge entspricht `sms_format.md` §2 **POSITIONAL** (kein Sortieren nach Risk-Priority im Render)
- [ ] Token-Symbole entsprechen `sms_format.md` §3.2 — `N` (Nacht-Min) und `D` (Tag-Max), **niemals** `T` alleinstehend
- [ ] HR/TH-Fusion korrekt: paarweise, kein Space, FR-only (außerhalb FR komplett weggelassen)
- [ ] `@hour`-Pflicht für R, PR, W, G, TH, TH+, HR; Stunde 0–23 ohne führende Null
- [ ] Threshold==Max-Optimierung: `(max@h)` entfällt wenn Threshold==Max
- [ ] **Keine Änderung an `src/formatters/sms_trip.py`** in β1
- [ ] Keine bestehenden Tests gebrochen (`uv run pytest` zeigt keine Regression)
- [ ] Public API dokumentiert (Docstrings auf `build_token_line` und `TokenLine`; `filter_for_subject`-Docstring klärt `D` = Tag-Max)
- [ ] Property-Tests **optional** (empfohlen, nicht Pflicht)

## Known Limitations

- **Subject-Filter ist Stub:** `TokenLine.filter_for_subject()` existiert, gibt aber `self` zurück. β2 implementiert die echte Filter-Logik gemäß §11.
- **Channel-Renderer fehlen:** `render_sms`/`render_email` sind nicht Teil von β1. Nutzer müssen `TokenLine.render(max_length)` direkt aufrufen.
- **Subscription nicht migriert:** `compare_subscription.py` nutzt weiterhin eigene String-Logik. β5.
- **Go-API nicht im Scope:** Die Go-Implementierung in `gregor-api` bleibt unangetastet (offene Frage im Epic #96).
- **Vigilance/Fire-Tokens:** Werden aus `forecast.metadata` gelesen, kein Provider-Refactor.
- **Legacy `sms_trip.py`:** Bleibt deprecated dead code, wird in β3/β4 entfernt.

## Risiken

1. **Drift gegen `sms_format.md` v2.0.** Der Conformance-Test (`test_render_conforms_to_sms_format_v2`) deckt §2-Reihenfolge, `@hour`-Pflicht, HR/TH-Fusion und das `T`-Verbot ab. **Mitigation:** Golden + Conformance gemeinsam.
2. **Wintersport-Tokens (`AV`, `WC`):** Provider-spezifisch. Falls ein Provider sie nicht liefert, dürfen sie nicht als leere Tokens erscheinen. **Mitigation:** `MetricDefinition.is_available(forecast)` prüfen; Wintersport-Block nur bei `profile == "wintersport"`.
3. **Threshold==Max-Optimierung ist subtil.** Floating-Point-Rundung kann zu Knapp-Treffern führen. **Mitigation:** Vergleich gegen die **gerundeten** Anzeigewerte, nicht gegen Roh-Floats; Golden mit gleichem Threshold/Max bewusst aufnehmen.
4. **LoC-Budget.** Vorheriger β1-Versuch (638 LoC) wurde verworfen. **Mitigation:** Submodul-Aufteilung als Plan B, klare Trennung von `metrics`/`render`.

## Migration / Rollout

β1 ist **additiv**. Nach Merge:

- Neuer Code unter `src/output/` existiert.
- Bestehende Pfade (`sms_trip.py`, `trip_report.py`, `wintersport.py`, `compare_subscription.py`) **unverändert**.
- Goldens + Conformance-Test schützen vor Regression in β2-β6.

Kein Feature-Flag nötig, da kein Caller umgestellt wird.

## Bezug zu existierenden Specs

| Spec | Beziehung |
|---|---|
| `sms_format.md` v2.0 | β1 implementiert §2 (Reihenfolge), §3 (Token-Definition), §4 (Null-Form), §5 (Threshold+Peak), §6 (Truncation) als kanonische Funktion. **Authority.** |
| `weather_config.md` v2.3 | `MetricConfig`-Felder (alle 7) sind Eingabe für den Builder |
| `weather_metrics_ux.md` v1.1 | `use_friendly_format` wird im Builder evaluiert |
| `sms_trip_formatter.md` v1.1 | Wird durch β3 obsolet. In β1 **kein** Cross-Check mehr (siehe A1). |
| `weather_metrics_dialog_unification.md` v1.0 | Bug #89, parallel — UI-Schicht des Epics |

## Changelog

### v1.1 (2026-04-26)

- **Cross-Check gegen Legacy entfernt** — `sms_format.md` v2.0 ist alleinige Authority. Legacy `sms_trip.py` ist deprecated dead code (`sms_text=None`), byte-Equal hätte β1 gezwungen v2.0 zu verletzen. Erste β1-Implementierung wurde aus diesem Grund verworfen (Adversary-Verdict BROKEN, F001-F005).
- **Token-Reihenfolge fixiert auf §2 POSITIONAL** (`N D R PR W G TH: TH+: HR:TH: Z: M: [SN…] DBG`). Algorithmus-Schritt "Sortierung nach priority" entfernt — Risk-Priority gilt nur noch für Truncation §6.
- **Token-Symbole explizit auf §3.2** — `N` (Nacht-Min) und `D` (Tag-Max), nicht `T`. `T` alleinstehend ist verboten. `D` in `filter_for_subject` als "Tag-Max" geklärt (nicht "Debug").
- **`@hour`-Pflicht** für R, PR, W, G, TH, TH+, HR explizit verankert. Stunde 0–23 ohne führende Null. Threshold==Max-Optimierung definiert.
- **HR/TH-Fusion** als eigener Algorithmus-Schritt: `HR:{l}@{h}TH:{l}@{h}` ohne Space, paarweise, FR-only. Außerhalb FR beide Tokens komplett weggelassen.
- **LoC-Budget**: 500 LoC hartes Limit für `src/output/tokens.py` (statt undefiniert). Bei Überschreitung Refactor in Submodule.
- **Cross-Check-Test entfernt**, ersetzt durch `test_render_conforms_to_sms_format_v2` (struktureller Conformance-Test gegen §2/§3).

### v1.0 (2026-04-25)

- Initiale Spec für β1 Token Builder.

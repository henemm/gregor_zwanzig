---
entity_id: output_subject_filter
type: module
created: 2026-04-26
updated: 2026-04-26
status: draft
version: "1.0"
tags: [output, pipeline, refactor, epic-render-pipeline]
epic: render-pipeline-consolidation (#96)
phase: β2
---

# Output Subject Filter

## Approval

- [x] Approved

## Purpose

Eine zentrale Funktion `build_email_subject(token_line) -> str` extrahieren, die das E-Mail-Subject als reinen **Filter über die `TokenLine`-DTO** produziert. Damit erfüllt das Subject die SSOT-Forderung von `sms_format.md` v2.0 §11 — das gleiche TokenLine-Objekt, das die SMS- und Push-Renderer speist, liefert auch das Subject, ohne paralleles Subject-Building.

Heute baut `src/formatters/trip_report.py::_generate_subject()` ein triviales Subject (`[Trip] Morning Report - DD.MM.YYYY`) ohne Wetter-Tokens und ohne Risk-Information. β2 ersetzt diese Funktion durch ein §11-konformes Subject mit MainRisk und den wichtigsten Wetter-Tokens (D, W, G, TH:/HR:), gekürzt auf 78 Zeichen für gute Postfach-Sichtbarkeit.

## Source

- **File (neu):** `src/output/subject.py` (≤200 LoC)
- **Identifier:** `build_email_subject()`
- **Tests (neu):** `tests/unit/test_subject_filter.py`, `tests/golden/test_subject_golden.py`
- **DTO-Erweiterung (β1-Nachbesserung):** `src/output/tokens/dto.py::TokenLine.main_risk: str | None = None`, `TokenLine.trip_name: str | None = None`
- **Builder-Erweiterung (β1-Nachbesserung):** `src/output/tokens/builder.py` füllt `main_risk` aus `RiskEngine`
- **Migration:** `src/formatters/trip_report.py::_generate_subject()` ruft `build_email_subject(token_line)` auf

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `output.tokens.dto.TokenLine` | input | Bereits in β1 erstellt; Felder `stage_name`, `report_type`, `tokens`, neu: `main_risk`, `trip_name` |
| `output.tokens.builder.build_token_line` | upstream | Liefert TokenLine inkl. `main_risk`-Feld (β1-Nachbesserung) |
| `services.risk_engine.RiskEngine` | upstream | Liefert MainRisk-Label, das vom Builder in TokenLine geschrieben wird |
| `reference/sms_format.md` v2.0 §11 | spec | **Authority** — Subject-Schema |

## Architektur-Entscheidungen

### A1. Subject-Schema (§11-konform, mit Trip-Präfix)

Das neue Subject-Format:

```
[{Trip}] {Etappen-Name} — {ReportType-DE} — {MainRisk} {D-Token} {W-Token} {G-Token} {TH:-Token}
```

Beispiele:

```
[GR221] Tag 3: Valldemossa → Sóller — Morgen — Thunder D24 W15 G30 TH:M
[GR20] Étape 7: Vizzavona — Abend — Storm D18 W30@14 G55@15 TH:H HR:M@13TH:H@14
[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15
```

**Begründung:** §11 schlägt `{Etappe} – {ReportType} – {MainRisk} – D...` vor; das Trip-Präfix in eckigen Klammern wurde in Phase 2 als wichtig für Mail-Filter ergänzt (Postfach-Regeln greifen typischerweise auf `[GR221]`/`[GR20]` als Header). Der Etappen-Name dient als Hauptdiskriminator: Multi-Tag-Trips erzeugen N E-Mails — die Subjects müssen unterscheidbar sein, sonst kollabiert das Postfach zu einem unlesbaren Thread.

### A2. ReportType-Mapping (Deutsch)

| `report_type` (en) | Subject-Label (de) |
|---|---|
| `morning` | `Morgen` |
| `evening` | `Abend` |
| `update` | `Update` |
| `compare` | (nicht in β2-Scope, siehe A6) |

Heute steht `Morning Report`, `Evening Report`, `WETTER-ÄNDERUNG` im Subject. β2 stellt auf kürzere deutsche Labels um — sie sparen Platz im 78-Zeichen-Budget und sind für die deutsche Zielgruppe natürlicher.

### A3. MainRisk kommt aus TokenLine (β1-Nachbesserung)

`TokenLine` wird um `main_risk: str | None = None` erweitert. Der Builder (`output.tokens.builder.build_token_line`) ruft `RiskEngine` und schreibt das Top-Risk-Label in dieses Feld. Damit bleibt `build_email_subject(token_line)` **single-input** — die SSOT-Idee bleibt intakt.

Risk-Labels werden im Subject **deutsch** ausgegeben (`Gewitter`, `Sturm`, `Hitze`, etc.). Heute liefert `RiskEngine` englische Labels wie `"Thunder"`, `"Storm"`. β2 führt eine Mapping-Konstante in `src/output/subject.py` ein:

```python
_RISK_DE: dict[str, str] = {
    "Thunder": "Gewitter",
    "Storm": "Sturm",
    "Heat": "Hitze",
    "Cold": "Kälte",
    "Rain": "Regen",
    "Snow": "Schnee",
    "Wind": "Wind",
    # weitere RiskEngine-Outputs nach Bedarf ergänzen
}
```

Unbekannte Risk-Labels werden 1:1 durchgereicht (Fail-soft). Bei Wachstum der Mapping-Tabelle ist ein i18n-Modul erforderlich (siehe Known Limitations).

### A4. Subject-Tokens — strikte Whitelist

Aus der `TokenLine.tokens` werden für das Subject **nur** folgende Tokens übernommen:

| Token-Symbol | Pflicht | Begründung |
|---|---|---|
| `D` | optional | Tag-Max-Temperatur (Hauptmetrik des Tages) |
| `W` | optional | Wind |
| `G` | optional | Böen |
| `TH:` (Vigilance) | optional | Thunderstorm-Vigilance, FR-only |
| `HR:` (Vigilance) | optional | Heavy-Rain-Vigilance, FR-only — paarweise mit `TH:`, gefused (`HR:...TH:...`) |

Alle anderen Tokens (`N`, `R`, `PR`, `TH+`, `Z:`, `M:`, `SN`, `SN24+`, `SFL`, `AV`, `WC`, `DBG`) werden **explizit weggelassen**. Begründung: Das Subject ist ein "Vorschau-Slot" mit ~78 Zeichen — es muss die wichtigsten Tageskennzahlen plus Risk vermitteln, nicht den vollständigen Forecast.

Reihenfolge im Subject-Output entspricht der Whitelist (D → W → G → TH:/HR:).

### A5. Truncation auf 78 Zeichen

E-Mail-Clients (Gmail, Apple Mail, Outlook) zeigen die ersten ~78 Zeichen prominent in der Subject-Spalte. β2 truncatiert auf **78 Zeichen** Zielwert.

**Truncation-Strategie (Reihenfolge des Streichens):**

1. Wenn nach allen Whitelist-Tokens > 78 Zeichen: streiche optionale Tokens in dieser Reihenfolge: `HR:/TH:` (Vigilance, paarweise) → `G` → `W` → `D`.
2. **Pflicht-Bestandteile (NIEMALS gekürzt):** Trip-Präfix, Etappen-Name, ReportType-Label, MainRisk-Label.
3. Wenn auch nach Streichen aller Wetter-Tokens noch > 78 Zeichen: **Trip-Präfix weglassen** (Etappen-Name + ReportType + MainRisk reichen aus).
4. Wenn immer noch > 78 Zeichen: Subject wird **nicht** weiter gekürzt — Etappen-Name bleibt vollständig (Hauptdiskriminator). Mail-Client schneidet visuell ab.

**Begründung:** Etappen-Name ist Hauptdiskriminator im Postfach (Multi-Tag-Trips). Lieber Wetter-Tokens streichen als Etappe verstümmeln. Trip-Präfix ist Komfort-Feature für Mail-Filter, kein semantischer Inhalt — daher streichbar.

### A6. Out-of-Scope: Subscription-Vergleich

`src/services/compare_subscription.py` baut heute paralleles Subject `Wetter-Vergleich: {name} ({datum})`. Die Migration auf `build_email_subject()` ist **explizit NICHT im β2-Scope**, sondern Teil von **β5 (Subscription auf Pipeline)**.

Grund: `compare_subscription.py` hat keine TokenLine-Integration und eine eigene Vergleichs-Domäne (zwei Forecasts gegenüberstellen). β2 hält sich klein und konzentriert sich auf Trip-Reports.

**Konsequenz:** Subscription-Subjects bleiben unverändert, bis β5 sie migriert. Drift-Quelle 2 ist in den Known Limitations dokumentiert.

## Implementation Details

### TokenLine-Erweiterung (in `src/output/tokens/dto.py`)

```python
@dataclass(frozen=True)
class TokenLine:
    stage_name: str
    report_type: ReportType
    tokens: tuple[Token, ...]
    truncated: bool = False
    full_length: int = 0
    main_risk: str | None = None  # NEU β2: Top-Risk-Label aus RiskEngine, deutsch
    trip_name: str | None = None  # NEU β2: Optional, für Subject-Präfix [{trip_name}]
```

Beide neuen Felder sind `Optional` mit Default `None` — bestehende Caller bleiben kompatibel. Der Builder (`build_token_line`) füllt sie wenn die Information verfügbar ist.

### Funktions-Signatur

```python
def build_email_subject(token_line: TokenLine, *, max_length: int = 78) -> str:
    """
    Baut das E-Mail-Subject als Filter über TokenLine gemäß sms_format.md §11.

    Format: '[{trip}] {stage_name} — {report_type_de} — {main_risk} D... W... G... TH:...'

    Hinweis: Hier ist D = Tag-Max-Temperatur (NICHT 'Debug').

    Truncation §A5: Wetter-Tokens fallen zuerst, Trip-Präfix als letztes,
    Etappen-Name niemals.
    """
```

### Algorithmus (deterministische Reihenfolge)

1. **Subject-Skelett** zusammenbauen: `[{trip_name}] {stage_name} — {report_type_de} — {main_risk}`
   - Trip-Präfix nur wenn `token_line.trip_name` gesetzt.
   - MainRisk nur wenn `token_line.main_risk` gesetzt; Übersetzung via `_RISK_DE`-Mapping.
   - ReportType-Übersetzung via fester Mapping-Konstante (`morning → Morgen`, etc.).
2. **Whitelist-Tokens** aus `token_line.tokens` extrahieren: nur D, W, G, TH:/HR:.
3. **Tokens in Whitelist-Reihenfolge anhängen** mit Space-Trennung (`D → W → G → TH:/HR:`).
4. **HR:/TH:-Vigilance-Fusion** respektieren (kein Space zwischen `HR:`- und `TH:`-Token, analog `sms_format.md` §3.3).
5. Wenn Länge ≤ `max_length`: zurückgeben.
6. Sonst: **Truncation gemäß A5** (HR:/TH: → G → W → D → Trip-Präfix), bis ≤ `max_length` oder nichts mehr Streichbares übrig ist.

Output ist deterministisch: gleiche `TokenLine` → bit-identisches Subject.

## Test Plan

### Neue Unit-Tests (`tests/unit/test_subject_filter.py`)

| Test | Vorbedingung | Erwartung |
|---|---|---|
| `test_subject_basic_format` | TokenLine mit `trip_name="GR221"`, `stage_name="Tag 1"`, `report_type=morning`, `main_risk="Thunder"`, leere Tokens | `[GR221] Tag 1 — Morgen — Gewitter` |
| `test_subject_with_weather_tokens` | TokenLine mit D=24, W=15, G=30, TH:M | D/W/G/TH: erscheinen in Whitelist-Reihenfolge |
| `test_subject_drops_non_whitelisted_tokens` | TokenLine mit N, R, PR, TH+ befüllt | N/R/PR/TH+ NICHT im Subject |
| `test_subject_german_report_type_labels` | `report_type` für alle 3 in-scope Werte | `morning → Morgen`, `evening → Abend`, `update → Update` |
| `test_subject_main_risk_german` | `main_risk="Thunder"` | Subject enthält `Gewitter`, nicht `Thunder` |
| `test_subject_truncation_to_78_drops_weather_first` | Subject roh > 78 Zeichen | HR:/TH: → G → W → D in dieser Reihenfolge gestrichen |
| `test_subject_truncation_keeps_stage_name_intact` | sehr langer Etappen-Name | Etappen-Name niemals gekürzt; ggf. Trip-Präfix gestrichen |
| `test_subject_no_trip_prefix_when_trip_name_none` | `trip_name=None` | Kein `[…]`-Präfix am Anfang |
| `test_subject_hr_th_vigilance_fusion` | TokenLine mit HR und TH: (Vigilance) | `HR:M@13TH:H@14` als zusammenhängender Block (kein Space) |

### Neue Golden-Tests (`tests/golden/test_subject_golden.py`)

5 Subject-Goldens (Strings werden vom Developer Agent aus realen TokenLines gefroren):

| Profil | Erwartung (beispielhaft) |
|---|---|
| GR221 Sommer-Morgen | `[GR221] Tag 3: Valldemossa → Sóller — Morgen — Hitze D32 W12 G20` |
| GR20 Frühjahr-Abend | `[GR20] Étape 7: Vizzavona — Abend — Sturm D18 W30@14 G55@15 TH:H HR:M@13TH:H@14` |
| Wintersport Update | `[Arlberg] Tag 2: Lech — Update — Schnee D-4 W45 G70` |
| FR-Vigilance-Trip | `[Corsica] E5: Vizzavona — Morgen — Gewitter D32 W30 G45 TH:H HR:M@14TH:H@17` |
| Single-Stage-Update (kurz) | `[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15` |

### Migrationen (existierende Tests anpassen)

- `tests/e2e/test_e2e_story3_reports.py` — Zeilen ~240-248, ~280-346: Subject-Erwartungen auf neues Schema umstellen.
- `tests/integration/test_trip_alert.py` — Zeilen ~185-194: `WETTER-ÄNDERUNG` → `Update`-Schema umstellen.
- `tests/test_formatters.py` — Zeilen ~175-184: Subject-Format-Erwartung an neues Schema anpassen.
- `tests/tdd/test_inbound_gate_errors.py` — Subject-Parsing für `[Trip]`-Präfix anpassen.
- `tests/tdd/test_sport_aware_scoring.py` — Subscription-Test BLEIBT unverändert (out-of-scope für β2, A6).

### E2E-Test

Senden via Gmail SMTP, Abrufen via IMAP, Subject-Format-Assertion gegen das neue Schema (siehe Test-Plan in CLAUDE.md "ECHTE E2E TESTS"). Hook:

```bash
uv run python3 .claude/hooks/e2e_browser_test.py email --check "Subject-Filter β2" --send-from-ui
```

Anschließend Pflicht: `uv run python3 .claude/hooks/email_spec_validator.py` (Exit 0 erforderlich).

## Expected Behavior

- **Input:** `TokenLine` mit befülltem `main_risk`, `trip_name`, `stage_name`, `report_type`, `tokens`.
- **Output:** `str` ≤ 78 Zeichen (Best-Effort), §11-konformes Subject-Format.
- **Side effects:** Keine. Pure function.
- **Determinismus:** Zwei Aufrufe mit identischer `TokenLine` liefern bit-identisches Subject.

## Akzeptanzkriterien (β2-Phase)

- [ ] `src/output/subject.py` existiert mit `build_email_subject()` — **≤200 LoC**
- [ ] `TokenLine`-DTO um `main_risk` und `trip_name` erweitert (β1-Nachbesserung)
- [ ] `build_token_line` füllt `main_risk` aus `RiskEngine`
- [ ] Alle 9 Unit-Tests grün (in `tests/unit/test_subject_filter.py`)
- [ ] Alle 5 Golden-Tests grün (in `tests/golden/test_subject_golden.py`)
- [ ] Migrierte Tests grün (`test_e2e_story3_reports`, `test_trip_alert`, `test_formatters`, `test_inbound_gate_errors`)
- [ ] `compare_subscription.py` und `test_sport_aware_scoring.py` UNVERÄNDERT (out-of-scope, A6)
- [ ] E2E-Test: Subject im Postfach entspricht §11-Schema
- [ ] `email_spec_validator.py` Exit 0
- [ ] Whitelist strikt eingehalten: nur D, W, G, TH:, HR: im Subject
- [ ] Truncation §A5: Etappen-Name niemals gekürzt
- [ ] HR:/TH:-Fusion ohne Space (FR-only)

## Known Limitations

- **`compare_subscription.py` bleibt unmigriert bis β5** — Drift-Quelle 2 dokumentiert. Subscription-Subjects nutzen weiterhin `Wetter-Vergleich: {name} ({datum})`.
- **Truncation auf 78 Zeichen ist Heuristik** — manche Mail-Clients zeigen mehr/weniger; Spec optimiert für Median-Mailbox. Bei sehr langen Etappen-Namen (> ~60 Zeichen netto) wird der Mail-Client visuell abschneiden.
- **MainRisk-Übersetzung Englisch→Deutsch wird in β2 hartcodiert** in `src/output/subject.py` (`_RISK_DE`). Bei Wachstum der Mapping-Tabelle ist ein eigenes i18n-Modul erforderlich.
- **Risk-Labels Fail-soft:** Unbekannte RiskEngine-Outputs werden 1:1 durchgereicht (statt Fehler). Erkennbar an englischem Label im Subject — Hinweis für Spec-Erweiterung.

## Risiken

1. **TokenLine-Erweiterung bricht β1-Tests.** `main_risk` und `trip_name` sind `Optional` mit Default `None` — bestehende Tests bleiben kompatibel. **Mitigation:** β1-Goldens unverändert weiterlaufen lassen, neue Felder nur additiv.
2. **MainRisk-Mapping unvollständig.** Wenn `RiskEngine` ein neues Label liefert, das nicht in `_RISK_DE` ist, erscheint englisches Label im deutschen Subject. **Mitigation:** Fail-soft + Test, der alle aktuellen RiskEngine-Outputs gegen `_RISK_DE` prüft (Mapping-Coverage).
3. **Truncation-Reihenfolge subtil.** Bei sehr langen Etappen-Namen kann das Subject auch nach allen Streichungen > 78 Zeichen sein. **Mitigation:** Algorithmus-Schritt 4 (kein weiteres Kürzen) ist explizit dokumentiert; Test `test_subject_truncation_keeps_stage_name_intact` deckt diesen Fall ab.
4. **Test-Migration-Aufwand.** 4 existierende Test-Dateien müssen angepasst werden. **Mitigation:** Migration in Test-Plan vollständig aufgelistet, kein Test übersehen.

## Migration / Rollout

β2 ist **migrierend** (anders als β1):

- `trip_report.py::_generate_subject()` wird umgestellt auf `build_email_subject(token_line)`.
- TokenLine-DTO erhält zwei neue Optional-Felder (additiv, β1 bleibt grün).
- 4 existierende Tests werden auf neues Subject-Schema migriert.
- `compare_subscription.py` BLEIBT unverändert (β5).
- Subscription-Test (`test_sport_aware_scoring`) BLEIBT unverändert.

Kein Feature-Flag nötig, da das alte Subject-Format ohnehin §11 verletzt und kein Caller darauf semantisch angewiesen ist (E-Mail-Filter müssen aber nach Deployment ggf. angepasst werden — User-Kommunikation einplanen).

## Bezug zu existierenden Specs

| Spec | Beziehung |
|---|---|
| `sms_format.md` v2.0 §11 | β2 implementiert das Subject-Schema als kanonische Funktion. **Authority.** |
| `output_token_builder.md` v1.1 (β1) | Liefert die `TokenLine`-DTO; β2 erweitert sie um `main_risk` und `trip_name` (β1-Nachbesserung). |
| `weather_metrics_dialog_unification.md` v1.0 | Bug #89, parallel — UI-Schicht des Epics. |

## Changelog

- 2026-04-27: β2 Validator-Findings Fixed — Trailing dangling em-dash when `main_risk=None` + `tokens=()` (HIGH), missing D/W/G tokens from aggregated segment data in TripReportFormatter (CRITICAL). Spec aligned with A5 §4 (no trailing dash without risk/tokens), TripReportFormatter now passes aggregated max/min temps to TokenLine for subject rendering.
- 2026-04-26: Initial spec created (β2 Output Subject Filter, Phase 2 abgeschlossen, Approval pending)

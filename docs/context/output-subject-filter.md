---
workflow: output-subject-filter
epic: render-pipeline-consolidation (#96)
phase: β2
created: 2026-04-26
---

# Context: Output Subject Filter (β2)

## Request Summary

Phase β2 des Epic #96: E-Mail-Subject als reinen Filter über die in β1 gebaute `TokenLine`-DTO ableiten. Heute erzeugt `trip_report.py::_generate_subject()` ein triviales Subject (`[Trip] Type - Datum`) ohne Wetter-Tokens — soll durch `build_email_subject(token_line) -> str` ersetzt werden, das gemäß `sms_format.md` v2.0 §11 ein Subset der TokenLine produziert.

## Related Files

| File | Lines | Relevance |
|------|-------|-----------|
| `src/formatters/trip_report.py` | 453–459, 108–110 | **DRIFT-QUELLE 1** — `_generate_subject(trip_name, report_type, dt)` |
| `src/output/tokens/dto.py` | 86–106 | `TokenLine` + Stub `filter_for_subject()` (gibt heute `self` zurück) |
| `src/output/tokens/dto.py` | 66–83 | `Token`-Struct (Symbol/Value/Category/Priority) |
| `src/output/tokens/builder.py` | — | Liefert `TokenLine` mit POSITIONAL-Tokens §2 |
| `src/output/tokens/render.py` | 92–101 | `render_line()` für SMS/Push — **NICHT** für Subject geeignet (≤160) |
| `src/outputs/email.py` | 66–71 | `EmailOutput.send(subject=...)` — 1:1 Pass-Through, keine Längenprüfung |
| `src/services/compare_subscription.py` | gesamt | **DRIFT-QUELLE 2** — eigenes Subject parallel zu TripReport |
| `docs/reference/sms_format.md` | 313–318 | **§11 Authority** — Subject-Schema |
| `docs/specs/modules/output_token_builder.md` | 69–87 | A3/A4: `D` = Tag-Max, Disambiguierung in Docstring Pflicht |

## Existing Patterns

### Subject heute (v1)
```python
# src/formatters/trip_report.py:453
f"[{trip_name}] {type_label} - {dt.strftime('%d.%m.%Y')}"
# Beispiel: "[Ballone] Morning Report - 26.04.2026"  (58 Zeichen)
```
- **Keine** Wetter-Tokens
- **Keine** Truncation
- Wintersport, Standard-Trips: gleiche Logik
- Subscription: **eigener** Subject-Path (Drift-Quelle 2)

### β1 TokenLine als Quelle
```python
# src/output/tokens/dto.py:86
@dataclass
class TokenLine:
    stage_name: str
    report_type: ReportType  # "morning" | "evening" | "update" | "compare"
    tokens: tuple[Token, ...]  # POSITIONAL §2: N D R PR W G TH: TH+: HR:TH: Z: M: [SN ...] DBG
    truncated: bool
    full_length: int

    def filter_for_subject(self) -> "TokenLine":
        # β1 Stub — β2 implementiert echten Filter
        return self
```

### sms_format.md §11 Schema
```
{Etappe} – {ReportType} – {MainRisk} – D{val} W{val} G{val} TH:{level}
```

## Dependencies

- **Upstream (β2 nutzt):**
  - `TokenLine` aus `src/output/tokens/dto.py` (β1 stable)
  - `Token`-Struct mit Symbol/Value/Category/Priority
  - `sms_format.md` §11 als Authority
- **Downstream (β2 verändert):**
  - `src/formatters/trip_report.py` — `_generate_subject()` ruft `build_email_subject(token_line)` auf
  - **Möglich (out-of-scope für β2):** `compare_subscription.py` Migration

## Existing Specs

- `docs/reference/sms_format.md` §11 — Authority für Subject-Schema
- `docs/specs/modules/output_token_builder.md` v1.1 — A3 (`D` = Tag-Max), A4 (Docstring-Disambiguierung)
- `docs/specs/modules/output_subject_filter.md` — **existiert NICHT**, in Phase 3 zu erstellen

## Tests heute

- `tests/tdd/test_html_email.py:156,239,...` — übergibt Subject, prüft aber Inhalt nicht
- `tests/integration/test_trip_alert.py` — vermutlich Alert-Subject
- **Lücke:** Keine Unit-Tests auf `_generate_subject()` Output-Format
- **Keine Golden-Tests für Subject** (nur SMS in `tests/golden/sms/`)

## Risks & Considerations

### KRITISCH: Akzeptanzkriterium-Konflikt
Das Epic-Akzeptanzkriterium *"Subject-Diff vs. heutige Outputs = 0 Zeichen"* widerspricht §11. Heutiges Subject (`[Ballone] Morning Report - 26.04.2026`) hat **keine** Wetter-Tokens; §11 verlangt sie aber (`D24 W15 G30 TH:M`). **Phase 2 (Analyse) muss klären:**
- (a) Bewusste **Subject-Format-Änderung** akzeptieren → Goldens neu fixieren
- (b) Subject-Schema in zwei Stufen: erst nur Format-Filter, später Tokens dazu
- (c) Akzeptanzkriterium umformulieren auf *"Subject ⊆ TokenLine (Property-Test)"*

### Sonderfälle
| Fall | Risiko | Aktion |
|------|--------|--------|
| Multi-Etappen-Trips | Subject 1× pro Trip; welche Stage? | Vermutlich erste Stage (segments[0]) |
| Wintersport | SN/SN24+/AV optional | Filter-Whitelist konfigurierbar |
| **Subscription** | Eigener Subject-Path in `compare_subscription.py` | **Out-of-scope β2** oder Mini-Adapter |
| **Vigilance/F14b** | Heute nicht im Subject | §11 erlaubt `HR:/TH:` — optional einblenden |
| **Truncation** | Heute keine; E-Mail-Clients schneiden ~78 Zeichen | β2 muss Limit definieren (78? 160?) |
| Alert/Update | Heute `"WETTER-ÄNDERUNG"` Label | `ReportType.update`-Mapping nötig |

### Drift-Quelle 2: Subscription-Subject
`src/services/compare_subscription.py` baut Subject **parallel**. Wenn β2 nur `trip_report.py` migriert, bleibt die Drift-Quelle bestehen. **Empfehlung:** β2-Scope auf TripReport beschränken, Subscription explizit als β5-Vorbereitung markieren — oder im Spec als "in einer eigenen Mini-Phase β2.1".

### Keine Truncation heute
Risiko 2 aus Epic-Skizze: E-Mail-Clients zeigen die ersten 78 Zeichen prominent. Wenn β2 plötzlich Tokens reinpackt, wird das Subject länger — Subject-Truncation muss Teil der Spec sein.

## Phase-2-Entscheidungen (User-bestätigt 2026-04-26)

| # | Entscheidung | Konsequenz |
|---|---|---|
| 1 | **Subject-Granularität:** 1 E-Mail pro Tag (Status quo). Subject diskriminiert über Etappen-Name, nicht Trip-Name. | Multi-Tag-Trips erzeugen N E-Mails mit unterschiedlichen Subjects → Postfach-Übersicht erhalten |
| 2 | **Trip-Präfix:** `[Trip]` als Klammer-Präfix vor Etappen-Name (für Mail-Filter) | Format: `[Trip] Etappe — ReportType — Risiko Tokens` |
| 3 | **Subject-Format:** §11-Schema gewinnt, Wetter-Tokens rein. 7+ Tests müssen angepasst werden. | Bewusste Format-Änderung. Goldens neu fixieren. |
| 4 | **MainRisk-Quelle:** `TokenLine.main_risk` als optionales Feld erweitern. Builder füllt es. | Kleine β1-Nachbesserung in `dto.py` + `builder.py`. Single-Input-Filter bleibt. |
| 5 | **Subscription-Scope:** `compare_subscription.py` bleibt out-of-scope für β2. Migration in β5. | β2 berührt nur `trip_report.py` + `output/`. Drift-Quelle 2 dokumentiert für β5. |
| 6 | **Truncation-Limit:** 78 Zeichen (Tech-Lead-Entscheidung, Mail-Client-Heuristik). | Truncation-Reihenfolge analog §6: erst Optional-Tokens (PR, Z:, M:), dann Peak-Klammern, MainRisk + Etappe + Trip-Präfix sind Pflicht. |
| 7 | **ReportType-Labels:** Deutsch — `Morgen`, `Abend`, `Update` (heute: `Morning Report`, `Evening Report`, `WETTER-ÄNDERUNG`). | Format-Konsistenz, kürzer. |

## Subject-Beispiele (Spec-Vorgaben)

```
[GR221] Tag 3: Valldemossa → Sóller — Morgen — Thunder D24 W15 G30 TH:M
[GR20] Étape 7: Vizzavona — Abend — Storm D18 W30@14 G55@15 TH:H HR:M@13TH:H@14
[GR221] Tag 1: Port d'Andratx → Esporles — Update — D26 W08 G15
```

Bei Truncation > 78 Zeichen: Tokens nach Priorität streichen, **Etappen-Name nie kürzen** (Hauptdiskriminator).

## Nächster Schritt

`/3-write-spec` — Spec `docs/specs/modules/output_subject_filter.md` v1.0 erstellen mit:
- DTO-Erweiterung `TokenLine.main_risk`
- Funktion `build_email_subject(token_line) -> str`
- Truncation-Strategie (78 Zeichen, Pflicht-/Optional-Tokens)
- ReportType-Mapping deutsch
- Test-Plan (inkl. Migration der 7+ existierenden Tests)
- Out-of-scope Marker für `compare_subscription.py`

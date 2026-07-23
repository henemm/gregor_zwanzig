---
entity_id: feat_1349_sms_unavailable
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [sms, official-alerts, unavailable, tokens, issue-1349, issue-1348]
---

<!-- Issue #1349 — Scheibe 1 (SMS): W?-Token für "amtliche Warnungen nicht abrufbar". Folge von #1348. -->

# Scheibe 1 (SMS) — W?-Token „amtliche Warnungen nicht abrufbar"

## Approval

- [x] Approved (PO „freigabe" 2026-07-23)

## Purpose

Der SMS-Trip-Report soll — analog zum bereits live gehenden E-Mail-Hinweis (#1348) —
einen kompakten Token **`W?`** zeigen, wenn für mindestens ein Segment mindestens eine
abdeckende amtliche Warn-Quelle beim Fetch ausgefallen ist. Bedeutung: „amtliche
Warnungen nicht abrufbar" — bewusst unterschieden von „keine Warnungen". Wiederverwendet
das bereits vorhandene Flag `SegmentWeatherData.official_alerts_unavailable` (kein
Neuaufbau der Erkennung).

## Source

- **File:** `src/output/tokens/dto.py` (MODIFY, +1 Feld) — `NormalizedForecast.official_alerts_unavailable: bool = False`
- **File:** `src/output/renderers/sms_trip.py` (MODIFY, ~+3 LoC) — Flag über Segmente aggregieren und ins DTO setzen (`_segments_to_normalized_forecast`)
- **File:** `src/output/tokens/builder.py` (MODIFY, ~+10 LoC) — bei gesetztem Flag eigenständigen `W?`-Token emittieren
- **File:** `tests/output/renderers/test_sms_trip_unavailable.py` (CREATE, ~25 LoC) — Kern-Regressionswächter

Schicht: **Python-Core / Domain-Backend** (`src/output/...`). Kein Go, kein Frontend.

## Estimated Scope

- **LoC:** ~+40
- **Files:** 4 (3 MODIFY + 1 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SegmentWeatherData.official_alerts_unavailable` (`src/app/models.py:426`) | intern | Quelle des Flags, bereits vom Scheduler am echten Fail-soft-Pfad gesetzt (#1348) |
| `NormalizedForecast` (`src/output/tokens/dto.py`) | intern | Transport-DTO für den SMS-Token-Builder |
| `build_token_line` / `_official_alerts` (`src/output/tokens/builder.py`) | intern | Token-Erzeugung + Truncation-Priorität |
| `any_official_alerts_unavailable` (`src/output/renderers/email/unavailable_hint.py`) | intern | Referenz-Muster für die Segment-Aggregation (`any(getattr(...))`) |

## Implementation Details

```
1. dto.py:   NormalizedForecast bekommt Feld
             official_alerts_unavailable: bool = False   (additiv, Default False)

2. sms_trip.py::_segments_to_normalized_forecast:
             unavailable = any(getattr(seg, "official_alerts_unavailable", False)
                               for seg in segments)
             -> NormalizedForecast(..., official_alerts_unavailable=unavailable)

3. builder.py::build_token_line:
             wenn forecast.official_alerts_unavailable:
                 eigenständigen Token "W?" hinzufügen
                 - EIGENE Kategorie / Position, NICHT category="official_alert"
                   (sonst erbt er den "!"-Warnblock-Marker und liest sich wie
                   "es liegt Warnung W vor")
                 - hohe Truncation-Priorität (>= OFFICIAL_ALERT_PRIORITY = 11),
                   damit der sicherheitsrelevante Marker unter 160-Zeichen-Druck
                   NICHT als erstes wegfällt
```

## Expected Behavior

- **Input:** Liste `SegmentWeatherData`, davon ≥1 mit `official_alerts_unavailable=True`.
- **Output:** SMS-Token-Zeile enthält den Marker `W?`, klar getrennt von echten Warn-Tokens.
- **Side effects:** Keine. Rein additiver Renderer-Pfad; keine Netz-/Persistenz-Effekte.

## Acceptance Criteria

- **AC-1:** Given ein SMS-Trip-Report, bei dem für mindestens ein Segment das Flag
  `official_alerts_unavailable=True` gesetzt ist / When die SMS gerendert wird / Then
  enthält die ausgegebene SMS den Token `W?`.
  - Test: `format_sms(segments)` mit einem Segment-Flag=True → Rückgabe-String enthält `W?`.

- **AC-2:** Given ein SMS-Trip-Report, bei dem KEIN Segment das Flag gesetzt hat (alle
  `official_alerts_unavailable=False`) / When die SMS gerendert wird / Then ist die
  Ausgabe byte-identisch zur heutigen SMS und enthält KEIN `W?`.
  - Test: identische Segmente einmal ohne Flag-Setzung → Ausgabe == Baseline-Ausgabe, `"W?" not in output`.

- **AC-3:** Given der `W?`-Marker und ein echter amtlicher Warn-Token liegen gleichzeitig
  vor / When die SMS gerendert wird / Then ist `W?` als eigener Marker erkennbar und wird
  NICHT als Teil des `!`-Warnblocks (echte Warnung) ausgegeben.
  - Test: Segment mit echter Warnung UND Flag=True → beide erscheinen, `W?` trägt keinen `!`-Warnblock-Charakter (nicht als Warnungs-Kürzel im Block).

- **AC-4:** Given das Flag wird am ECHTEN Fail-soft-Pfad gesetzt (Quelle liefert `[]`
  ohne zu werfen, `cached_fetch` gibt None zurück) / When die Segmente in den SMS-Renderer
  fließen / Then erscheint `W?` — der Regressionswächter benutzt KEIN werfendes Double.
  - Test: Fixture reproduziert den Fail-soft-Pfad (leere Alert-Liste + gesetztes Flag), nicht per `raise`.

## Known Limitations

- `W?` signalisiert nur „mindestens eine abdeckende Quelle ausgefallen" (strenge Regel aus
  #1348); es unterscheidet nicht, welche/wie viele Quellen betroffen sind — bewusst so.
- Positions-/Kategorie-Detail des Tokens ist Implementierungsentscheidung innerhalb der in
  AC-3 fixierten Semantik-Grenze (getrennt vom `!`-Warnblock).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine kanalspezifische Ausweitung eines bereits entschiedenen Features
  (#1348); keine neue Entscheidungsfläche (Kanäle/Provider/Datenmodell/Auth) berührt.

## Changelog

- 2026-07-23: Initial spec created (Scheibe 1 SMS von #1349)

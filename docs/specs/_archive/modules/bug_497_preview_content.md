---
entity_id: bug_497_preview_content
type: bugfix
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [bugfix, preview, sms, fixture-provider, demo-mode, issue-497]
---

<!-- Issue #497 — Trip/Preview inhaltlich falsch: SMS-Präfix schneidet Stage-Name falsch + 4 Fixture-Felder fehlen -->

# Issue #497 — Bug-Fix: SMS-Präfix falsch + FixtureProvider liefert 4 Felder nicht

## Approval

- [x] Approved

## Purpose

Zwei unabhängige Fehler machen den Trip/Preview-Inhalt unbrauchbar. Erstens kürzt `preview_service.py` Stage-Namen wie `"KHW_10: von Egger Alm nach Dolinza Alm"` falsch auf `"KHW_10 von"` statt `"KHW_10"`, weil `.replace(":", "")` das Trennzeichen entfernt bevor `[:10]` greift. Zweitens liefert der `FixtureProvider` im Demo-Modus für vier aktivierbare Metriken (`cloud_low_pct`, `pop_pct`, `snowfall_limit_m`, `wind_dir_deg`) immer `"-"`, weil die Fixture-JSONs die Felder nicht enthalten und das Mapping sie nicht liest.

## Source

**Geänderte Dateien:**
- `src/services/preview_service.py` Z. 151 — `render_sms_preview()`: `str.replace` durch `str.split` ersetzen
- `src/providers/fixture.py` — `ForecastDataPoint`-Konstruktor: 4 fehlende Felder im Mapping ergänzen
- `fixtures/openmeteo/innsbruck.json` — 4 neue Keys pro Datenpunkt hinzufügen
- `fixtures/openmeteo/stubai.json` — 4 neue Keys pro Datenpunkt hinzufügen
- `fixtures/openmeteo/zillertal.json` — 4 neue Keys pro Datenpunkt hinzufügen

**Neue Test-Datei:**
- `tests/tdd/test_bug_497_preview_content.py`

**NICHT ändern:** `src/output/tokens/builder.py` — `_sanitize_stage_name()` ist dort bereits korrekt implementiert und dient als Referenz für den Fix in `preview_service.py`.

> **Schicht-Hinweis:** Ausschließlich Python-Backend-Layer (`src/services/`, `src/providers/`) und statische Fixture-Dateien (`fixtures/openmeteo/`). Kein Frontend, kein Go-API betroffen.

## Estimated Scope

- **LoC:** ~15 (1 in preview_service, 4 in fixture.py, ~10 JSON-Zeilen pro Fixture × 3)
- **Files:** 5
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/preview_service.py` | Python-Modul | Enthält `render_sms_preview()` mit dem fehlerhaften `str.replace`-Aufruf |
| `src/output/tokens/builder.py` | Python-Modul | Referenz-Implementierung `_sanitize_stage_name()` — verwendet `split(":", 1)[0].strip()` (korrekt) |
| `src/providers/fixture.py` | Python-Modul | `FixtureProvider` liest Fixture-JSONs und baut `ForecastDataPoint`-Objekte — Mapping unvollständig |
| `src/app/models.py` | Python-Modul (Dataclass) | Definiert `ForecastDataPoint` mit optionalen Feldern `cloud_low_pct`, `pop_pct`, `snowfall_limit_m`, `wind_dir_deg` |
| `fixtures/openmeteo/innsbruck.json` | JSON-Fixture | Testdaten für Demo-Modus (Innsbruck) — 4 Felder fehlen pro Datenpunkt |
| `fixtures/openmeteo/stubai.json` | JSON-Fixture | Testdaten für Demo-Modus (Stubai) — 4 Felder fehlen pro Datenpunkt |
| `fixtures/openmeteo/zillertal.json` | JSON-Fixture | Testdaten für Demo-Modus (Zillertal) — 4 Felder fehlen pro Datenpunkt |

## Implementation Details

### Bug 1 — Fix in `preview_service.py` Z. 151

**Aktuell (falsch):**
```python
clean_stage = (stage_name or "Etappe").replace(":", "").strip()
```

**Fix:**
```python
clean_stage = (stage_name or "Etappe").split(":", 1)[0].strip()
```

Begründung: `.replace(":", "")` entfernt alle Doppelpunkte aus dem gesamten String, sodass `"KHW_10: von Egger Alm..."` zu `"KHW_10 von Egger Alm..."` wird. Das anschließende `[:10]`-Slice ergibt `"KHW_10 von"`. Der korrekte Ansatz `split(":", 1)[0]` extrahiert nur den Teil vor dem ersten Doppelpunkt (`"KHW_10"`) und entspricht exakt der Logik in `builder.py:_sanitize_stage_name()`.

### Bug 2 — Fix in `fixture.py`: 4 fehlende Felder im Mapping

Im `ForecastDataPoint(...)`-Konstruktoraufruf des `FixtureProvider` folgende 4 Zeilen ergänzen (direkt nach den bestehenden Feldern, vor der schließenden Klammer):

```python
cloud_low_pct=_maybe_int(p.get("cloud_low_pct")),
pop_pct=_maybe_int(p.get("pop_pct")),
snowfall_limit_m=_maybe_int(p.get("snowfall_limit_m")),
wind_dir_deg=p.get("wind_dir_deg"),
```

Hinweis: `wind_dir_deg` wird ohne `_maybe_int` eingelesen, analog zur bestehenden Behandlung dieses Feldes im echten OpenMeteo-Provider.

### Bug 2 — Fix in den 3 Fixture-JSONs

Zu jedem bestehenden Datenpunkt-Objekt in `innsbruck.json`, `stubai.json` und `zillertal.json` folgende 4 Keys mit plausiblen alpinen Werten hinzufügen:

```json
"cloud_low_pct": 30,
"pop_pct": 20,
"snowfall_limit_m": 2200,
"wind_dir_deg": 270
```

Wertebereiche orientieren sich an typischen alpinen Bedingungen:
- `cloud_low_pct`: 0–80 (30 = leicht bewölkt)
- `pop_pct`: 0–80 (20 = geringe Regenwahrscheinlichkeit)
- `snowfall_limit_m`: 1500–3000 (2200 = mittlere Schneefallgrenze)
- `wind_dir_deg`: 0–359 (270 = West, typisch für Alpen-Westströmung)

Die Werte müssen über alle Datenpunkte eines Fixtures identisch sein (statischer Demo-Wert reicht, da der FixtureProvider kein zeitlich variables Wetter simuliert).

## Acceptance Criteria

**AC-1:** Given a trip stage with name "KHW_10: von Egger Alm nach Dolinza Alm" / When `render_sms_preview()` is called / Then the SMS prefix contains "KHW_10:" and not "KHW_10 von:".
- Test: (populated after /tdd-red)

**AC-2:** Given a trip with `cloud_low_pct` enabled in display_config / When the email preview is rendered in demo mode via `FixtureProvider` / Then the cloud_low column contains a numeric value (not "-").
- Test: (populated after /tdd-red)

**AC-3:** Given a trip with rain probability (`pop_pct`) enabled in display_config / When the email preview is rendered in demo mode via `FixtureProvider` / Then the rain probability column contains a numeric value (not "-").
- Test: (populated after /tdd-red)

**AC-4:** Given a trip with snowfall limit (`snowfall_limit_m`) enabled in display_config / When the email preview is rendered in demo mode via `FixtureProvider` / Then the snowfall limit column contains a numeric value (not "-").
- Test: (populated after /tdd-red)

**AC-5:** Given a trip with wind direction (`wind_dir_deg`) enabled in display_config / When the email preview is rendered in demo mode via `FixtureProvider` / Then the wind direction column contains a numeric value (not "-").
- Test: (populated after /tdd-red)

## Expected Behavior

| Input | Expected Output |
|-------|----------------|
| Stage-Name `"KHW_10: von Egger Alm nach Dolinza Alm"` in `render_sms_preview()` | SMS-Präfix: `"KHW_10"` (nicht `"KHW_10 von"`) |
| Trip mit aktiviertem `cloud_low_pct` im Demo-Modus | E-Mail-Vorschau: Tiefwolken-Spalte zeigt `30` (nicht `"-"`) |
| Trip mit aktiviertem `pop_pct` im Demo-Modus | E-Mail-Vorschau: Regenwahrsch.-Spalte zeigt `20` (nicht `"-"`) |
| Trip mit aktiviertem `snowfall_limit_m` im Demo-Modus | E-Mail-Vorschau: Schneefallgrenze-Spalte zeigt `2200` (nicht `"-"`) |
| Trip mit aktiviertem `wind_dir_deg` im Demo-Modus | E-Mail-Vorschau: Windrichtung-Spalte zeigt `270` (nicht `"-"`) |
| Stage-Name ohne Doppelpunkt (z.B. `"Etappe 1"`) | Unverändert — kein Seiteneffekt durch Fix |

## Known Limitations

- Die Fixture-JSONs liefern statische Werte (keine zeitliche Variation). Das ist ausreichend für Demo-Modus, aber nicht repräsentativ für echte Tagesgänge.
- Stage-Namen ohne Doppelpunkt (z.B. `"Etappe 1"`) sind von Bug 1 nicht betroffen und bleiben unverändert.

## Changelog

- 2026-06-01: IMPLEMENTED & LIVE — 5 LoC production fix (preview_service + fixture.py + 3 JSONs); 12 tests (mock-free); Adversary VERIFIED on first pass
- 2026-05-31: Spec erstellt (Issue #497 — zwei Root-Cause-Bugs in preview_service.py und fixture.py)

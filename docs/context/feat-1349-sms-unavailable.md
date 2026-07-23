# Context: feat-1349-sms-unavailable (Scheibe 1 von #1349)

## Request Summary
Der SMS-Trip-Report soll — analog zum bereits live gehenden E-Mail-Hinweis (#1348) —
einen kompakten Token **`W?`** zeigen, wenn für mindestens ein Segment mindestens eine
abdeckende amtliche Warn-Quelle beim Fetch ausgefallen ist (`official_alerts_unavailable=True`).
Bedeutung: „amtliche Warnungen nicht abrufbar" ≠ „keine Warnungen". PO-Token bereits
entschieden: **`W?`** (analog zur Sicherheits-Token-Familie C+/C~/C?).

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/sms_trip.py` | Baut `NormalizedForecast` aus Segmenten (`_segments_to_normalized_forecast`, `_official_alert_entries`); Einhängepunkt für den W?-Emitter |
| `src/output/tokens/dto.py` | `NormalizedForecast`-DTO (`official_alerts`-Feld, Kategorien-Tuple); ggf. neues Feld `official_alerts_unavailable: bool` |
| `src/output/tokens/builder.py` | `build_token_line()`, `_official_alerts()`, `OFFICIAL_ALERT_PRIORITY=11`, `OFFICIAL_ALERT_POS`; W?-Token-Erzeugung + Truncation-Priorität |
| `src/app/models.py:426` | `SegmentWeatherData.official_alerts_unavailable: bool` — vorhandenes Flag (Quelle) |
| `src/services/trip_report_scheduler.py:797-812` | Setzt das Flag am echten Fail-soft-Pfad via `get_official_alerts_with_status()` |

## Existing Patterns
- **Flag-Aggregation über Segmente:** `any(getattr(seg, "official_alerts_unavailable", False) for seg in segments)` — exakt das Muster aus `unavailable_hint.py::any_official_alerts_unavailable` (E-Mail). Für SMS wiederverwenden bzw. spiegeln.
- **Token-Erzeugung:** `_official_alerts()` macht aus `(symbol, level, hour)`-Tripeln Tokens; ohne `level` entsteht ein reines Symbol-Token (`Token(symbol, "", "official_alert", ...)`). Ein `W?`-Token ist levellos.
- **Truncation:** `builder.py §6` — „lower drops first". Sicherheitsrelevanter Hinweis darf NICHT als erstes wegfallen → hohe Priorität (≥ `OFFICIAL_ALERT_PRIORITY`).
- **Position:** `OFFICIAL_ALERT_POS` sortiert den Warn-Block. Der `!`-Block-Marker bedeutet „amtliche Warnung liegt vor". **Semantik-Frage (Analyse/Spec):** W? = „nicht abrufbar", NICHT „Warnung liegt vor" — sollte daher als eigener, unterscheidbarer Token erscheinen, nicht als weiterer Eintrag hinter dem `!`-Warnblock, der wie eine echte Warnung liest.

## Dependencies
- **Upstream (liefert das Flag):** `trip_report_scheduler.py` → `SegmentWeatherData.official_alerts_unavailable`. SMS-Renderer liest nur, setzt nicht.
- **Downstream (erben den Token):** Telegram-Kurzform sendet `report.sms_text` direkt (notification_service) → bekommt `W?` automatisch mit (Scheibe 2 muss das nur bestätigen, nicht bauen).

## Existing Specs
- `src/output/renderers/email/unavailable_hint.py` (Doc-Header) — der E-Mail-Baustein und die Semantik des Flags.
- Issue #1348 — Eltern-Scheibe (Erkennung + E-Mail-Anzeige, live in Prod).
- Issue #1318 — Warn-Block-Token-System im SMS-Builder (`!`-Marker, `_official_alerts`).

## Risks & Considerations
- **Semantik-Verwechslung:** W? darf nicht als „es gibt eine Warnung W" gelesen werden. Klar abgrenzbar vom `!`-Warnblock.
- **160-Zeichen-Budget:** `W?` ist 2 Zeichen, sicherheitsrelevant → hohe Truncation-Priorität, damit es unter Platzdruck erhalten bleibt.
- **Byte-Identität ohne Flag:** Ist kein Segment-Flag gesetzt, muss die SMS-Ausgabe byte-identisch zur heutigen bleiben (Regressionsschutz).
- **Test am ECHTEN Fail-soft-Pfad:** Regressionswächter mit Quelle liefert `[]` via `cached_fetch`-None OHNE zu werfen — NICHT mit werfenden Doubles (das war der Bug in der Trip-Scheibe #1348).

## Analysis

### Type
Feature (Ausweitung eines live gehenden Features auf einen weiteren Kanal).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/tokens/dto.py` | MODIFY | Feld `official_alerts_unavailable: bool = False` auf `NormalizedForecast` (Default False = byte-identisch für Bestandsaufrufer) |
| `src/output/renderers/sms_trip.py` | MODIFY | In `_segments_to_normalized_forecast` das Flag aggregieren: `any(getattr(seg, "official_alerts_unavailable", False) for seg in segments)` und ins DTO setzen |
| `src/output/tokens/builder.py` | MODIFY | Bei gesetztem Flag einen eigenen `W?`-Token emittieren — hohe Truncation-Priorität (≥ `OFFICIAL_ALERT_PRIORITY`), unterscheidbar vom `!`-Warnblock (kein „es liegt eine Warnung vor") |
| `tests/output/renderers/test_sms_trip_unavailable.py` | CREATE | Kern-Test: Flag gesetzt → `W?` in SMS; Flag nicht gesetzt → byte-identisch ohne `W?`; Fixture am echten Fail-soft-Pfad (Quelle liefert `[]`, wirft nicht) |

### Scope Assessment
- Files: 4 (3 MODIFY + 1 CREATE)
- Estimated LoC: +40 / -0 (Test ~20)
- Risk Level: LOW — additiv, Default-False garantiert Byte-Identität für alle Bestandspfade; einziger Konsument neu.

### Technical Approach
1. `NormalizedForecast.official_alerts_unavailable: bool = False` (dto.py) — additives Feld, Default False.
2. `_segments_to_normalized_forecast` setzt es aus der Segment-Aggregation (gleiches `any()`-Muster wie E-Mail `any_official_alerts_unavailable`).
3. `build_token_line`/Builder emittiert bei True einen eigenständigen `W?`-Token. **Nicht** in die `official_alert`-Kategorie einreihen (sonst `!`-Blockmarker + Warnungs-Semantik) — eigener, sicherheitsrelevanter Marker mit hoher Priorität, damit er unter dem 160-Zeichen-Truncation-Druck erhalten bleibt. Genaue Position wird in der Spec als AC festgehalten (Empfehlung: eigener Positions-Slot, vom Warnblock getrennt).
4. Kein Flag → keine Änderung an der Token-Zeile (Byte-Identität).

### Dependencies
- Upstream: `SegmentWeatherData.official_alerts_unavailable` (schon gesetzt vom Scheduler am echten Fail-soft-Pfad, #1348).
- Downstream: Telegram-Kurzform (`report.sms_text`) erbt `W?` automatisch → Scheibe 2 bestätigt nur.

### Open Questions
- Keine offene PO-Frage: Token-String `W?` ist bereits PO-entschieden. Positions-/Mechanik-Detail ist eine reine Implementierungsentscheidung, wird in der Spec als AC fixiert.

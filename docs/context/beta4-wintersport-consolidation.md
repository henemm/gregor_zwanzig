# Context: β4 Wintersport-Profile-Konsolidierung

**Epic:** #96 Render-Pipeline-Konsolidierung — Phase β4
**Phase:** 1 (Context)
**Datum:** 2026-04-28

## Request Summary

`src/formatters/wintersport.py::format_compact` (240 LoC, eigener Renderer-Pfad) wird eliminiert. Wintersport-Tokens (`AV` Lawine, `WC` Wind-Chill, `SFL` Schneefallgrenze, `SN` Schneehöhe, `SN24+` Neuschnee) bleiben erhalten — produziert durch die β1-Pipeline `build_token_line(profile="wintersport")` + β3 `render_sms()`/`render_email()`. Netto: **−90 LoC** (Epic-Plan).

## Related Files

| Datei | Relevanz | LoC |
|---|---|---|
| `src/formatters/wintersport.py` | **Zu eliminieren.** `WintersportFormatter.format_compact()` produziert heute Token-Pairs `T-15/-5 WC-22 W45 G78 R0.2 SN25` ≤160 Zeichen | 240 |
| `src/output/tokens/builder.py` | `build_token_line()` hat schon `profile: Profile = "standard"` (Literal) und ruft `_wintersport(today, by_sym, rt)` auf — Wintersport-Tokens bereits implementiert | 210 |
| `src/output/tokens/dto.py` | `Profile = Literal["standard", "wintersport"]` | klein |
| `src/output/tokens/render.py` | `DROP_ORDER` mit WC/AV/SFL-Truncation-Prioritäten | klein |
| `src/output/renderers/sms/__init__.py` | β3 `render_sms()` — wrapped `render_line()` | 22 |
| `src/output/renderers/email/__init__.py` | β3 `render_email()` | 98 |
| `src/app/cli.py` | **Einziger Prod-Caller** von `format_compact()` (Zeile 223–225, `--compact` Flag, SMS-Pfad) | 1 Stelle |
| `src/app/trip.py:29-33` | `ActivityProfile = WINTERSPORT \| SUMMER_TREKKING \| CUSTOM` (Trip-Modell) | klein |
| `src/app/loader.py` | Lädt `profile` aus YAML → `AggregationConfig.for_profile()` | – |
| `tests/test_formatters.py` | 3 Tests für `format_compact()` + 6 für vollen Report | 9 |
| `tests/unit/test_token_builder.py` | 1 Wintersport-Test (`test_wintersport_profile_adds_sn_token`) | 12 total |
| `tests/golden/test_sms_golden.py` | Golden `arlberg-winter-morning.txt` | – |
| `tests/e2e/test_e2e_story3_reports.py:252` | E2E `test_sms_format_compact` | 1 |

## Existing Patterns

- **β1/β2/β3 Adapter-Pattern:** Public API (`format_email`, `format_sms`) bleibt importierbar, delegiert intern an `render_email`/`render_sms`. Gleiches Vorgehen bei `WintersportFormatter` (falls externe Caller existieren) ODER ersatzlos streichen wenn nur CLI ruft.
- **Profile-Flag bereits verdrahtet:** `build_token_line(profile="wintersport")` produziert AV/WC/SFL/SN-Tokens aus `DailyForecast`. β4 ist primär *Migration der Caller*, nicht *neue Tokens bauen*.
- **Pure-Function-Renderer (β3 §A5):** Keine Hidden State, alle Inputs als kwargs. Wintersport ist nur ein Profile-Flag, kein eigener Renderer mehr.
- **DROP_ORDER Truncation:** `render.py` priorisiert Wintersport-Tokens bereits — muss nur unter Wintersport-Last validiert werden.

## Dependencies

- **Upstream (was β4 nutzt):**
  - `build_token_line()` aus β1 — produziert TokenLine mit Wintersport-Tokens
  - `render_sms()` aus β3 — rendert TokenLine zu SMS-Zeile ≤160 Zeichen
  - `render_email()` aus β3 — falls Wintersport-Mails kommen
  - `DailyForecast` (Domain) — Felder `avalanche_level`, `wind_chill_c`, `snowfall_limit_m`, `snow_depth_cm`, `snow_new_24h_cm`
  - `Trip.aggregation.profile` (`ActivityProfile`) — Quelle für Profile-Flag

- **Downstream (was β4 ändert):**
  - `src/app/cli.py` — `--compact`-Pfad migriert von `WintersportFormatter` → Pipeline
  - `tests/test_formatters.py` — Wintersport-Tests müssen gegen `build_token_line` umgeschrieben werden
  - `tests/golden/sms/arlberg-winter-morning.txt` — Golden-Vergleich gegen neue Pipeline (bit-identisch oder kontrolliert geändert)
  - `tests/e2e/test_e2e_story3_reports.py` — E2E-Test umstellen

## Existing Specs

| Spec | Status |
|---|---|
| `docs/specs/modules/output_token_builder.md` | β1 (APPROVED, gemerged) |
| `docs/specs/modules/output_subject_filter.md` | β2 (APPROVED, gemerged) |
| `docs/specs/modules/output_channel_renderers.md` | β3 (APPROVED, gemerged) |
| `docs/specs/modules/wintersport_profile_consolidation.md` | **β4 — fehlt, Phase 3 Output** |
| `docs/specs/wintersport_extension.md` | Alt (2025-12-27), historische Wintersport-Feature-Spec — überholt durch β4 |
| `docs/reference/sms_format.md` v2.0 §3.6 | SSOT für Wintersport-Tokens (APPROVED 2026-04-25) |

## Risks & Considerations

1. **Avalanche-Aggregation fehlt im Domain-Layer.** `AggregatedSummary` hat keine `avalanche_level`. `format_compact()` greift heute direkt auf Roh-Felder zu. β4-Strategie: `DailyForecast.avalanche_level` direkt durch `build_token_line()` reichen — keine neue Aggregation nötig, da Tokens pro Tag gerendert werden.
2. **Provider befüllen `avalanche_level` heute teils nicht.** Out of Scope für β4. Tests mit Mock/Fixture-Daten bauen; Token wird einfach weggelassen wenn Feld `None`.
3. **CLI ist einziger Prod-Caller.** Migration daher überschaubar — eine Stelle in `cli.py:223`, plus Tests.
4. **Golden-Drift möglich.** `arlberg-winter-morning.txt` Golden wurde gegen alten `format_compact()` eingefroren. Vor β4-Migration: Golden bit-identisch reproduzieren oder kontrolliert neu schreiben (mit Diff-Begründung).
5. **`WintersportFormatter`-Import-Surface.** Falls externe Importer (Skript, anderer Service) `from formatters.wintersport import WintersportFormatter` nutzen → Adapter behalten. Grep zeigt aktuell nur CLI + Tests, also kann Klasse ersatzlos gelöscht werden — **muss Phase 2 verifizieren**.
6. **Truncation-Verhalten unter realistischer Wintersport-Last.** TokenLine mit AV+WC+SFL+SN+SN24+ + Standard-Tokens kann ≤160-Limit reißen. `DROP_ORDER` ist da, aber Test-Coverage dünn.
7. **Doppelte ActivityProfile-Enums.** `app/trip.py` (WINTERSPORT/SUMMER_TREKKING/CUSTOM) vs. `app/user.py` LocationActivityProfile (WINTERSPORT/WANDERN/ALLGEMEIN) — nicht harmonisieren in β4, nur Trip-Variante nutzen.

## Wintersport-Tokens (Soll-Zustand nach β4)

| Token | Bedeutung | Quelle | Aktiviert wenn |
|---|---|---|---|
| `AV{1-5}` | Lawinenstufe | `DailyForecast.avalanche_level` | profile=wintersport ∧ Feld≠None |
| `WC{°C}` | Wind Chill | `DailyForecast.wind_chill_c` | profile=wintersport ∧ Feld≠None |
| `SFL{m}` | Schneefallgrenze | `DailyForecast.snowfall_limit_m` | profile=wintersport ∧ Feld≠None |
| `SN{cm}` | Schneehöhe | `DailyForecast.snow_depth_cm` | profile=wintersport ∧ Feld≠None |
| `SN24+{cm}` | Neuschnee 24h | `DailyForecast.snow_new_24h_cm` | profile=wintersport ∧ Feld≠None |

## Akzeptanzkriterien (Epic-Level)

- [ ] `src/formatters/wintersport.py` ist gelöscht (kein Adapter-Stub — kein externer Importer existiert)
- [ ] CLI `--compact` (`format_compact`-Pfad) produziert bit-identische Outputs (Golden `arlberg-winter-morning.txt`)
- [ ] CLI Long-Report-Pfad (`format()` aus cli.py:228) produziert weiterhin alle Wintersport-Informationen — durch β3-Pipeline (`render_email(profile="wintersport")` oder Pipeline-Äquivalent)
- [ ] AV/WC/SFL/SN/SN24+ Tokens werden weiterhin erzeugt — Coverage durch Unit-Test mit profile=wintersport
- [ ] Netto −90 LoC oder mehr (Plan-Agent schätzt ca. −370 LoC inkl. Test-Cleanup)
- [ ] Bestehende Tests laufen grün; alte Wintersport-Tests sind migriert oder gelöscht
- [ ] sms_format.md §3.6 Wintersport-Token-Beispiele bleiben gültig

## Phase-2-Erweiterungen (User-Freigabe 2026-04-28)

**Hard Constraints (User):**
1. **Keine Information geht verloren.** Alle Outputs, die `wintersport.py::format()` und `format_compact()` heute produzieren, müssen weiterhin verfügbar sein.
2. **Architektur muss erweiterbar sein.** Weitere Sportarten kommen später (Bergsteigen, Klettern, MTB, …) — sie sollen als neue `Profile`-Werte + Token-Set in `build_token_line()` ergänzt werden können, **ohne** neue Renderer-Dateien anzulegen.

**Architekturentscheidung:** `WintersportFormatter` ersatzlos streichen. Alle Aufrufe (`cli.py:223` Compact + `cli.py:228` Long-Report) gehen durch die β1/β3-Pipeline. Neue Sportarten = neuer Profile-Literal + Token-Erweiterung in `_wintersport`-analoger Funktion.

**Typ-Impedanz als Kern-Implementierungsarbeit:** `format_compact()` konsumiert heute `TripForecastResult`/`AggregatedSummary` (waypoint-aggregiert), `build_token_line()` braucht `NormalizedForecast`/`DailyForecast` (tagesbezogen). β4 muss einen expliziten Adapter `_trip_result_to_normalized()` schreiben, isoliert testbar.

**Zwei zu migrierende Pfade:**
| CLI-Pfad | Datei:Zeile | Heute | Nach β4 |
|---|---|---|---|
| `--compact` | `cli.py:223–225` | `WintersportFormatter().format_compact(result)` | `build_token_line(forecast, config, profile="wintersport")` → `render_sms(token_line)` |
| Long-Report (default) | `cli.py:228` | `WintersportFormatter().format(result)` | `render_email(forecast, config, profile="wintersport")` (β3 `render_email` muss `profile`-Param erhalten) |

**Spec-Phase muss klären:**
- Wie Long-Report-Inhalte (Übersicht + Per-Waypoint-Details aus `format()`) durch `render_email()` darstellbar sind, wenn `render_email()` heute Trip-Stages erwartet
- Ob ein neuer Pipeline-Zweig `render_text_report(profile, …)` nötig ist (Plain-Text-Long-Report) oder ob bestehende `render_email().plain_body` reicht

**Out of Scope (verschoben):**
- Provider-Befüllung von `DailyForecast.avalanche_level` (eigenes Issue)
- Harmonisierung der Doppel-Enums `ActivityProfile` (trip.py) vs. `LocationActivityProfile` (user.py)
- Web-UI Wintersport-Scoring in `compare.py:62` (separater Stack)

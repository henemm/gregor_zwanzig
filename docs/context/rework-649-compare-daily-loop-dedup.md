# Context: Rework #649 — Compare-Daily-Loop Dedup

## Request Summary
`_run_compare_presets_daily()` enthält noch eine eigene Inline-Versand-Logik (EmailOutput/render/ComparisonEngine), während der On-Demand-Pfad bereits den extrahierten Helper `_send_one_compare_preset()` nutzt. Die Daily-Loop soll denselben Helper aufrufen — Duplizierung entfernen, Verhalten bit-identisch.

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/scheduler.py:241` | `_run_compare_presets_daily()` — Daily-Loop mit dupliziertem Versand (Z. 312–344) |
| `api/routers/scheduler.py:389` | `_send_one_compare_preset()` — gemeinsamer Helper (Ziel) |
| `api/routers/scheduler.py:461` | `_send_compare_preset()` — On-Demand-Pfad, nutzt Helper bereits |
| `api/routers/scheduler.py:349` | `_save_preset_status()` — RMW-Status, von beiden genutzt |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py` | Tests für Daily-Loop (manual-skip, weekly, empty location_ids, returns-count) |
| `tests/tdd/test_compare_preset_send.py` | Tests für On-Demand-Helper-Pfad |
| `docs/specs/modules/issue_627_631_compare_send_rhythm.md` | Spec, in der die bewusste Duplizierung dokumentiert wurde |

## Existing Patterns
- Schedule-Filterung (daily/weekly/weekday/manual-skip) lebt **in der Loop**, nicht im Helper — bleibt dort.
- Lazy `all_locations`-Cache: einmal pro Loop laden, an Helper als `all_locations_cache` durchreichen.
- Helper **wirft** `ValueError` bei fehlendem Empfänger/nicht auflösbaren Orten; Loop fängt heute stattdessen ab und macht `continue`. → Loop muss Helper-Call in try/except wrappen.
- Multi-Tenant: `user_id` wird durchgereicht, kein `"default"`-Fallback in echtem Pfad.

## Dependencies
- Upstream: `ComparisonEngine`, `render_compare_html`, `render_comparison_text`, `EmailOutput`, `load_all_locations`, `_parse_activity_profile` — alle bereits im Helper gekapselt.
- Downstream: `_run_compare_presets_daily()` wird von `/api/scheduler/run-compare-presets` + Scheduler-Job aufgerufen (Z. 85).

## Existing Specs
- `docs/specs/modules/issue_627_631_compare_send_rhythm.md` — dokumentiert die bewusste Duplizierung als Folge-Schuld (→ dieses Issue).

## Risks & Considerations
- **Live-Daily-Scheduler versendet echte Briefings.** Refactor darf das Versand-Verhalten nicht ändern (subject/html/text/empfaenger/status-write bit-identisch).
- **Log-Level-Nuance:** Heute logged „empfaenger leer" als WARNING + continue; Helper wirft ValueError. Im try/except kann das als ERROR landen. → ValueError separat als WARNING fangen, um Verhalten zu erhalten.
- **Lazy-Load-Nuance:** Heute wird `all_locations` erst bei erstem fälligen Preset *mit* location_ids geladen; künftig pro fälligem Preset. Gleiche Daten, vernachlässigbar.
- Helper schreibt zusätzlich `top_ort` ins Log (`top_ort=%s`) — kosmetisch, kein Verhaltensunterschied im Versand.

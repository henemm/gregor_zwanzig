# Context: #1319 Scheibe B — Tagesfenster pro Wanderung einstellbar

**Workflow:** issue-1319-slice-b
**Issue:** #1319 (Epic, OPEN) — Scheibe B
**Vorgänger:** Scheibe A (Commit `087f643f`, live) — festes Fenster 04–19 zentralisiert in `day_window.py`

## Analysis

### Type
Feature (Voll-Stack: Backend + Persistenz + UI — Scheibe B **und** C zusammengezogen, PO 2026-07-23)

### Scope dieser Scheibe (Issue #1319 B+C, PO-erweitert)
> „Einstellbares Fenster (Config + Persistenz): Feld pro Tour (Start-/Endstunde), Default 04–19, Read-Modify-Write (kein Datenverlust)." + „UI: Zeitfenster-Einstellung bei der SMS-Konfiguration."

Keine N-Logik (Scheibe D), kein TH+: (Scheibe E).

### PO-Entscheidungen (2026-07-23)
- **DEC-1 Feldname:** `day_window_start_hour`/`day_window_end_hour` (int, `None`/fehlend = Default 4/19). Tech-Lead-Entscheid — neutral, gilt für alle vier Kurzformen (Issue-Punkt 6), nicht nur SMS.
- **DEC-2 Validierung:** UI verhindert ungültige Eingabe (Endstunde > Startstunde erzwungen, nur 0–23 wählbar). Backend klemmt defensiv auf Default 4/19 bei ungültigen Werten (Defense-in-Depth: Import/Migration/API umgehen die UI). Kein HTTP-400 im Normalpfad — nie ein kaputtes Briefing.
- **DEC-3 Scope:** B+C merged inkl. UI. **LoC-Limit wird angehoben** (Voll-Stack, PO-autorisiert durch UI-Wunsch).
- **DEC-4 Compare-Ausschluss:** Fenster-Control nur im Trip-Kontext (`context="route"`), im geteilten `VersandTab.svelte` ausgeblendet bei `context="vergleich"`. Präzedenz: #1318 FB01.

### Zentraler Befund
Scheibe A hat das feste Fenster bewusst in **ein** Modul zentralisiert. Die Modul-Docstring
(`src/output/renderers/day_window.py:10-12`) nennt Scheibe B wörtlich: die Konstanten werden
„durch einen konfigurierbaren Wert ersetzt". Änderung ist eng lokalisiert, aber cross-language
(Python-Renderer + Python-Modell + Go-Store) und muss durch **5 Aufrufstellen** durchgereicht werden.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/day_window.py:23-24,59-63` | MODIFY | Konstanten → Parameter; `build_day_window_points(...)` bekommt Fenster (Default 4/19) |
| `src/output/renderers/sms_trip.py:170` | MODIFY | Fenster aus Trip-Config durchreichen (Kanal 1: SMS) |
| `src/output/renderers/compact_summary.py:175` | MODIFY | Kanal 2: E-Mail-Kurzzusammenfassung |
| `src/output/renderers/email/helpers.py:1514` | MODIFY | Kanal 3: Metriken-Pillen |
| `src/output/renderers/narrow.py:200` | MODIFY | Kanal 4: Telegram-Fußzeile |
| `src/services/notification_service.py:205-213` | MODIFY | **Kritische Kopplung:** `compute_has_gap()` nutzt dieselben Konstanten → muss dasselbe Fenster verwenden, sonst divergieren Gap-Erkennung und Anzeige |
| `src/app/models.py:723-782` (`TripReportConfig`) | MODIFY | Neues Feld-Paar `day_window_start_hour`/`_end_hour` (int, `None`=Default 4/19) |
| `src/app/loader.py` (`_parse_trip`, `_trip_to_dict`) | MODIFY | Feld lesen/schreiben; RMW via `_deep_merge_preserve_unknown` |
| `internal/store/slot_hour_normalization.go:71-95` | MODIFY | Validierung/Klemmung int 0–23 neben Slot-Normalisierung |
| `docs/reference/api_contract.md:471-496` (TripReportConfig) | MODIFY | DTO-Feld dokumentieren |
| `tests/tdd/test_sms_daywindow_aggregation.py` u.a. | MODIFY/CREATE | Fenster-Konfigurierbarkeit testen |

### Persistenz-Pfad (drift-getestet, kein Datenverlust)
- **Kein** eigenes `sms-settings`-DTO. Feld lebt additiv in `report_config`.
- Go: `report_config` = `map[string]interface{}` → neuer Key fließt automatisch durch
  `mergeConfigMap` (`internal/handler/config_merge.go:11`, aufgerufen `trip.go:241`). RMW-Merge.
- Python: `_deep_merge_preserve_unknown` (`loader.py:98`) bewahrt Keys; getyptes Lesen braucht
  Feld in `TripReportConfig` + `_parse_trip` + `_trip_to_dict`.
- Auth bereits abgedeckt: `s.WithUser(middleware.UserIDFromContext(...))` (`trip.go:192`).
- Speicherort: `data/users/<user_id>/briefings/<trip_id>.json`.

### Naming-Präzedenz
- `ComparePreset.hour_from`/`hour_to` (int-Stunden-Paar) — exaktes Vorbild.
- `time_window: Tuple[int,int]` (`src/app/user.py:175`).
- Modul + Konstanten heißen `day_window` / `DAY_WINDOW_*` → Feldname `day_window_start_hour` konsistent.

### Zusätzliche UI-Dateien (durch Scope-Erweiterung)
| File | Change | Description |
|------|--------|-------------|
| `frontend/src/lib/components/shared/VersandTab.svelte` bzw. `versand-tab/VTSchedulePlan.svelte` | MODIFY | Fenster-Control (Start-/Endstunde) unter SMS-/Zeitplan-Einstellung; nur `context="route"` |
| Frontend report_config-Typ/Binding | MODIFY | Neues Feld im DTO-Binding |
| `frontend/e2e/...` (Playwright) | CREATE | Staging-E2E: Fenster setzen, speichern, Persistenz + PUT-Count prüfen |

### Scope Assessment
- Files: ~14 (Python 6, Go 1, Frontend 2–3, Doku 1, Tests 3–4)
- Estimated LoC: +250/-40 → **über 250-Limit**, `loc_limit_override` nötig (PO-autorisiert via UI-Wunsch DEC-3)
- Risk Level: **MEDIUM–HIGH** — cross-language + UI, 5 Durchreich-Stellen, Gap-Kopplung, geteilter Baustein (Compare-Ausschluss), Datenverlust-Risiko (durch RMW-Merge abgedeckt), Svelte-5-Reaktivität (PUT-Count auf Staging)

### Technical Approach (Empfehlung)
1. `build_day_window_points()` bekommt optionalen Fenster-Parameter; ohne Wert Default 4/19 (Rückwärtskompatibilität für Alt-Trips + Alt-Aufrufer).
2. Feld-Paar `day_window_start_hour`/`day_window_end_hour` in `report_config`, `None`/fehlend = Default.
3. Ein Fenster-Wert speist ALLE vier Kurzformen **und** `compute_has_gap()` (Issue-Punkt 6: einheitlich).
4. Validierung: int 0–23, `start < end` (Tagesfenster, kein Wrap); ungültig → Klemmung/Default.

### Open Questions
Alle in DEC-1…DEC-4 (oben) geklärt (PO 2026-07-23). Keine offenen Fragen.

# Context: #627 Einzel-Sofortversand + #631 Wochen-Rhythmus erhalten

## Request Summary
Zwei Folge-Issues aus #626 am Compare-Preset-Listenmenü:
- **#627:** Kebab-Aktion „Briefing jetzt senden" soll das Vergleichs-Briefing sofort an die konfigurierten Empfänger versenden (echter Versand, kein Stub).
- **#631:** Pausieren/Reaktivieren eines Vergleichs darf den Wochen-Rhythmus (`weekly`) nicht verlieren (aktuell hartes `'daily'` beim Reaktivieren).

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/scheduler.py` `_run_compare_presets_daily` | Echte Versandlogik (ComparisonEngine → render_compare_html → EmailOutput.send). Einzel-Versand muss extrahiert werden (#627). |
| `internal/handler/compare_preset.go` `SendComparePresetHandler` | Stub (`{"status":"queued"}`) → muss Proxy auf Python werden (#627). |
| `internal/handler/proxy.go` `SendSubscriptionProxyHandler` | **Vorbild** für POST-Proxy mit `{id}` + `appendUserID` (#627). |
| `internal/model/compare_preset.go` `ComparePreset` | Struct braucht additives `previous_schedule`-Feld (#631). |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` `compareActions` / `deriveStatusFromPreset` | `send`-Aktion wieder aufnehmen (#627); Status-Ableitung (#631). |
| `frontend/src/lib/components/compare/CompareGrid.svelte` `handleAction` / `togglePause` | `send` mit Confirm verdrahten (#627); `togglePause` restauriert `previous_schedule` statt hart `daily` (#631). |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Detail-Ansicht: hat `previousSchedule` nur als Session-State (Z.164) — soll auf Backend-Feld umgestellt werden (#631). |
| `cmd/server/main.go` (Z.221) | Route `POST /api/compare/presets/{id}/send` registriert. |

## Existing Patterns
- **POST-Proxy mit user_id:** `SendSubscriptionProxyHandler` (proxy.go:224) — `chi.URLParam(id)` + `appendUserID(query, UserIDFromContext)` → `client.Do(POST)`, 120s Timeout. **Anti-Spoofing:** `appendUserID` ersetzt jedes client-gelieferte `user_id` durch das aus dem Auth-Kontext (Bug #200).
- **Read-Modify-Write Merge:** `UpdateComparePresetStateHandler` lädt Presets, ändert nur ein Feld, speichert zurück (CLAUDE.md Daten-Schema-Pflicht).
- **Weekly-Filter:** `_run_compare_presets_daily` verarbeitet `daily` + fällige `weekly`. Einzel-Versand (#627) muss `schedule` **ignorieren** (Sofortversand auch bei `manual`/pausiert).

## Dependencies
- **Upstream:** ComparisonEngine, render_compare_html, render_comparison_text, EmailOutput, load_all_locations, `_save_preset_status` (alle Python, vorhanden).
- **Downstream:** Frontend-Kebab-Menü (#626 hat `send` entfernt → wird wieder eingeführt). Detail-Ansicht CompareTabs für konsistentes Pause-Verhalten (#631 Akzeptanz: „Gleiches Verhalten in Liste und Detail").

## Existing Specs
- `docs/specs/modules/issue_458_compare_preset_backend.md` — ComparePreset-Datenmodell + CRUD.
- `docs/specs/modules/issue_472_compare_list_restore.md` — `deriveStatusFromPreset`.

## Risks & Considerations
- **#627 Cross-User-Leak (HART):** Python `_send_compare_preset` defaultet `user_id="default"`. Go-Proxy MUSS echte `user_id` durchreichen, sonst falsche Presets an falsche Empfänger. Test mit zwei Nutzern Pflicht.
- **#631 Datenmodell-Rework:** `previous_schedule` ist **rein additiv** (omitempty) — keine Feld-Umbenennung/-Removal. Altdaten ohne Feld laden als nil. Trotzdem Pre-Snapshot + Roundtrip-Test laut CLAUDE.md Pflicht.
- **LoC-Limit 250:** Beide Issues zusammen (Python + Go + Frontend + mock-freie Tests beider) liegen voraussichtlich nahe/über 250 LoC → ggf. PO um Split oder höheres Limit bitten.
- **Sofortversand-Semantik (#627):** Ein pausiertes/manuelles Preset MUSS trotzdem sofort senden können (Knopfdruck ≠ Zeitplan).

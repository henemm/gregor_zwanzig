# Context: Issue #232 — `summer_trekking` Preset-Behandlung in `rightColumn.ts`

## Request Summary

`getPresetLabel` und `getDefaultMetricsForProfile` in `frontend/src/lib/utils/rightColumn.ts` kennen nur die Profile `wintersport`, `wandern`, `allgemein` — fehlt `summer_trekking`. Trips, die vom Wizard via `mapActivityToProfile` auf `summer_trekking` gesetzt werden (`trekking`, `hochtour`, `klettersteig`), fallen daher in der Wetter-Metriken-Card auf das generische "Standard-Metriken"-Label und ein leeres Default-Metrik-Set zurück. Ziel: Profil `summer_trekking` korrekt behandeln.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/utils/rightColumn.ts` | **Fix-Ziel.** `getPresetLabel` Z. 16–22 + `getDefaultMetricsForProfile` Z. 24–31 ergänzen. |
| `frontend/src/lib/utils/rightColumn.test.ts` | Test-File analog AC-13/AC-14 erweitern. Enthält AC-13a/b/c/d/e/f + AC-14a/b/c als Vorbild. |
| `frontend/src/lib/types.ts` | `ActivityProfile` Union (Z. 68) kennt `summer_trekking` bereits — keine Änderung nötig. |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` | `mapActivityToProfile` Z. 71–84 produziert `summer_trekking` für `trekking`/`hochtour`/`klettersteig`. Quelle des Symptoms — keine Änderung. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | Setzt `trip.aggregation = { profile: mapActivityToProfile(this.activity) }`. Consumer, keine Änderung. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Konsumiert `getPresetLabel` + `getActiveMetrics`. Profitiert automatisch, keine Änderung. |
| `docs/specs/modules/epic_135_step5_right_column.md` | Original-Spec für die Helper. AC-13/AC-14 listen nur 3 Profile — Spec ist veraltet gegenüber `activity_profile.md`. Update-Kandidat. |
| `docs/specs/modules/activity_profile.md` | **Kanonische Quelle** des Enums: `{wintersport, wandern, summer_trekking, allgemein}`. |

## Existing Patterns

- **If-Chain pro Profil** in beiden Helpern (`if (profile === '…') return …`). Geradlinig, keine Map/Lookup-Tabelle — bewusst flach, weil 3 (jetzt 4) Werte.
- **Defensive Fallbacks** für unbekannte Werte, `null`, `undefined` sind eigene Tests (AC-13d/e/f) — neuer Case muss Fallback-Pfade nicht brechen.
- **Default-Metrik-Listen** je Profil:
  - `wintersport`: `temp_min, temp_max, wind_max, snow_new, snow_depth, thunder_level`
  - `wandern`: `temp_min, temp_max, wind_max, precip_sum, thunder_level, cloud_avg`
  - `allgemein`: `temp_min, temp_max, wind_max, precip_sum`
- **`METRIC_LABELS`** (Z. 72–83 in `rightColumn.ts`) übersetzt Metric-Keys zu deutschen Labels — Keys, die hier fehlen, fallen via `prettyLabel` auf den Original-Key zurück (kein Crash, aber UI-Drift).

## Dependencies

- **Upstream:** `Trip.aggregation.profile` (Type `ActivityProfile` in `types.ts`); Wizard-Mapping in `wizardHelpers.ts`.
- **Downstream:** `WeatherMetricsPreviewCard.svelte` (Trip-Detail Overview-Tab); ggf. Verwender von `getActiveMetrics` in anderen Cards.

## Existing Specs

- `docs/specs/modules/activity_profile.md` — Kanonisches Enum. Eindeutig: `summer_trekking` ist gültig.
- `docs/specs/modules/epic_135_step5_right_column.md` — Definiert AC-13/AC-14 nur für 3 Profile. **Drift** zur Realität nach Wizard-Erweiterung. Empfehlung: AC-13 + AC-14 in Phase 3 erweitern oder neue AC ergänzen.

## Risks & Considerations

- **Default-Metrik-Liste für `summer_trekking` ist eine Produkt-Entscheidung.** Issue empfiehlt: "ähnlich zu `wandern` plus `thunder_level`, `uv_index`, ggf. `temp_max`". Aber: `thunder_level` ist bei `wandern` schon dabei; `uv_index` ist **nicht** in `METRIC_LABELS` — würde als Roh-Key gerendert. Klärung in Phase 2/3 nötig.
- **Label-Wahl** "Sommer-Trekking-Standard" (mit Bindestrich) entspricht dem Issue-Vorschlag und passt zum Namensstil der anderen Labels.
- **Spec-Drift:** Wenn wir in `rightColumn.ts` ergänzen, ohne `epic_135_step5_right_column.md` zu aktualisieren, treibt die Spec weiter auseinander. Sollte in Phase 3 mit-erfasst werden.
- **LoC-Scope:** Produktivcode ~4–6 Zeilen, Tests ~20–30 Zeilen, Spec-Patch ~5 Zeilen. Klar unter dem 250-LoC-Limit.
- **Kein Backend-Touch.** Reine Frontend-Helper-Erweiterung; Go-API kennt `summer_trekking` bereits (`activity_profile.md`).
- **Test-Lauf:** `cd frontend && node --experimental-strip-types --test src/lib/utils/rightColumn.test.ts` (Pattern aus existierendem Test-Header).

## Open Questions für Phase 2/3

1. ~~Exakte Default-Metrik-Liste für `summer_trekking`?~~ **Geklärt (Phase 2, PO-Entscheidung):**
   - Liste: `temp_min, temp_max, wind_max, gust_max, precip_sum, thunder_level, cloud_avg, uv_index`
   - Begründung: Alpine Mehrtagestour → Böen als eigenständiges Risiko + UV im Hochgebirge.
2. ~~`METRIC_LABELS` erweitern?~~ **Ja:** Eintrag `uv_index: 'UV-Index'` hinzufügen. `gust_max` ist bereits vorhanden.
3. ~~Spec patchen oder Folge-Spec?~~ **Patch** in `epic_135_step5_right_column.md` (AC-13/AC-14 erweitern oder neue AC ergänzen).

## Phase-2-Entscheidungen (final)

- **Label:** `'Sommer-Trekking-Standard'`
- **Default-Metriken:** `['temp_min', 'temp_max', 'wind_max', 'gust_max', 'precip_sum', 'thunder_level', 'cloud_avg', 'uv_index']`
- **METRIC_LABELS-Patch:** `+ uv_index: 'UV-Index'`
- **Spec-Strategie:** Patch in `epic_135_step5_right_column.md`

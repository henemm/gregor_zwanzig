# Context + Analyse: feat-1186-arpae-it-fallback

Issue #1186 · Folge zu #1162 (Epic #1073 Punkt 5, Epic #1089 bereits geschlossen).

## Request Summary
#1162 (live, Commit `8b8524f0`) liefert für Italien Radar-DPC als Nowcast-Quelle.
Fällt DPC aus, springt die Kette direkt auf AROME-FR/ICON-D2 (nur Rand-Treffer)
bzw. den globalen `minutely_15`-Fallback — es fehlt eine italienische Modell-
Zwischenstufe. #1186 hängt **ARPAE ICON-2I** (Open-Meteo, 2 km, verifiziert ganz
Italien inkl. Süden) als Rückfall **direkt unter DPC** ein, bevor auf AROME-FR/
ICON-D2/generisch zurückgefallen wird.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` | Kern. `_DPC_*`-Box (Zeile 45–49) deckt bereits ganz Italien inkl. Korsika ab (36.0–47.5 N, 6.5–19.0 E) — **keine neue Box nötig**, ARPAE nutzt denselben `_within_dpc`-Guard. Kette in `_fetch_frames_with_fallback` (Zeile 200–228): DPC-Block (214–217) bekommt einen zweiten Schritt, bevor der `if`-Block endet. `_SOURCE_LABELS` (129–142) neuer Eintrag `"ARPAE-2I"`. Neue Methode `_fetch_italy_arpae` (analog `_fetch_arome_france_hd`/`_fetch_icon_d2`, Zeile ~298–306) ruft nur `_fetch_openmeteo_15(lat, lon, models="italia_meteo_arpae_icon_2i")`. |
| `tests/tdd/test_issue_1162_radar_dpc.py` | **MODIFY, nicht nur lesen.** `test_ac3_dpc_failure_falls_back_to_next_source` (Zeile 99–123) bricht DPC via `radar_dpc.BASE_URL`-Manipulation und erwartet für Rom `result.source in ("AROME-FR", "ICON-D2", "minutely_15")`. Nach der Änderung landet Rom korrekt bei `"ARPAE-2I"` (Rom liegt nicht in AROME-/ICON-D2-Box) — Assertion muss um `"ARPAE-2I"` erweitert werden, sonst bricht ein grüner Test. Das ist die erwartete Verhaltensänderung, kein Kollateralschaden. |
| `tests/tdd/test_feature_1186_arpae_it_fallback.py` | CREATE. Neue AC-Tests (s.u.). |
| `docs/specs/modules/radar_nowcast_italy.md` | Bereits existierender Spec-Entwurf aus der verworfenen Parallel-Session — Ausgangspunkt, wird an die tatsächliche Kette (Rückfall unter DPC statt eigenständige Box) angepasst. |

## Existing Patterns
- **Fail-soft-Zwei-Schritt innerhalb einer Box:** Es gibt noch keinen Präzedenzfall
  für zwei Quellen in derselben `if _within_X`-Bedingung — INCA hat den
  Konvektions-Sidecar (andere Funktion: Ergänzung, nicht Rückfall). Neu, aber
  strukturell trivial: zweiter `frames = ...; if frames: return ...`-Block
  direkt nach dem ersten.
- **`_fetch_openmeteo_15(models=...)`:** Geteilter Helper, dritte Nutzung nach
  AROME-FR/ICON-D2. Kein neuer HTTP-Code nötig.
- **`_SOURCE_LABELS`-Dict:** Einzige Anlaufstelle für Label-Text; alle Konsumenten
  (`trip_alert.py`, `alert/render.py`, `validator_render_service.py`) lesen nur
  über `source_label()` — kein weiterer Fix nötig (bereits in #1162/#1161 bestätigt).

## Verifizierte API-Fakten (aus #1162-Vorrecherche, live geprüft)
- `models=italia_meteo_arpae_icon_2i`, kein Auth, `weather_code` vorhanden
  (Konvektion inline, kein Sidecar wie bei DPC/INCA nötig).
- Rom (41.9/12.5) und Palermo (38.12/13.36) liefern valide Werte.
- Known Limitation: `minutely_15` für Italien bei Open-Meteo aus Stundenwerten
  interpoliert (kein natives 15-Min-Raster) — als Rückfall unter echtem Radar
  akzeptabel.

## Dependencies
- Upstream: `httpx`, `providers.brightsky.RadarFrame` (bestehend, keine neue Abhängigkeit).
- Downstream: unverändert — `NowcastResult`-Vertrag bleibt gleich, nur ein neuer `source`-Wert.

## Scope Assessment
- Files: 1 MODIFY (`radar_service.py`), 1 MODIFY (bestehender DPC-Test, 1 Assertion), 1 CREATE (neue Testdatei).
- LoC: ~40–50 produktiv + Tests.
- Risk Level: LOW — reiner Zusatzschritt in bestehender fail-soft-Kette, kein neuer Provider, kein neues Auth.

## Technical Approach
ARPAE-Fetch als zweiter Schritt **innerhalb** des bestehenden `_within_dpc`-Blocks
(nicht als eigene Box) — folgt exakt der Reihenfolge aus #1186-Issue-Text
("Radar-DPC → ARPAE-Modell → generisch"). Vermeidet eine zweite, praktisch
deckungsgleiche Bounding-Box.

## Open Questions
Keine — Quelle, Reihenfolge und Muster sind durch #1162-Vorrecherche und die
bestehende Codebase eindeutig festgelegt.

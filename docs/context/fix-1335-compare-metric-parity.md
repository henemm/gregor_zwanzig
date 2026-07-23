# Analyse: fix-1335-compare-metric-parity (Scheibe 1 von #1335)

Issue #1335 (`priority:high`, `type:bug`, `type:rework`, `bundle:D`, `bundle:G`). PO-Richtung:
volle Trip-Angleichung der Compare-Metriken, ausgeliefert in Scheiben. **Diese Scheibe 1:**
Beide Compare-Tabellen folgen der Config-**Auswahl UND -Reihenfolge**; **Windrichtung** wird
in der Stundentabelle möglich (wie beim Trip). Folge-Scheiben: #1350 (Katalog-Single-Source),
#1351 (Katalog-Lücken). Epic #1230.

## Type
Bug + Rework (Renderer-Parität Trip↔Compare). Reiner Render-/Auflösungs-Fix; Datenmodell
(`LocationResult`) liefert die Werte bereits.

## Root Cause (verifiziert gegen main HEAD 98967721)

Der Compare-Mail-Renderer nutzt **zwei feste Code-Listen** und **ignoriert die Config-Reihenfolge**:

1. **Übersichtsmatrix** — `src/output/renderers/email/compare_html.py`:
   - feste Liste `CV2_METRICS` (215–254), Windrichtung-Zeile bei :243.
   - `_visible_metrics` (473–480) filtert nur (Set-Membership), Reihenfolge = **CV2-Listenreihenfolge**.
   - Auswahl kommt als **ungeordnetes `set`** aus `resolve_enabled_metrics` (`compare_metric_ids.py:100–126`)
     → Ordnungsinformation aus `display_config.active_metrics` (Liste!) geht verloren.
2. **Stundentabelle je Ort** — `compare_html.py`:
   - feste Liste `HOUR_METRICS` (260–270, 9 Spalten), Reihenfolge fix.
   - `_visible_hour_metrics` (598–605), Auswahl aus `resolve_hourly_metrics` (`compare_hourly_metric_ids.py:25–44`).
   - **Windrichtung strukturell unmöglich:** kein Eintrag in `FRONTEND_TO_HOURLY_METRIC_ID`
     (`compare_hourly_metric_ids.py:12–22`), keine Spalte in `HOUR_METRICS`.
3. Verdrahtung: `src/services/report_config_resolver.py:227–234` liest `active_metrics` + `hourly_metrics`.

**Trip-Gegenstück (macht es richtig):** Der Trip-Stundenrenderer iteriert `dc.metrics` in **Config-
Reihenfolge** (`src/output/renderers/.../helpers.py:94`, `dp_to_row`) und mischt Windrichtung per
`should_merge_wind_dir()` (`helpers.py:64–83`) als Kompass-Pfeil in die Wind-Spalte
(`helpers.py:93,109–110,648–649`; HTML `html.py:270,295–319`). Der Compare-Pfad hat kein Äquivalent.

Daten liegen vor: `LocationResult.wind_direction_avg` (`src/app/user.py:131`, Zirkularmittel
`weather_metrics.py:895`); Stunden-Rohwerte je Ort existieren im Compare-Datenpfad.

## Ziel dieser Scheibe (Acceptance-Rahmen — ACs in der Spec)
1. **Reihenfolge (Übersicht):** Die Zeilen-Reihenfolge der Übersichtsmatrix folgt der Reihenfolge
   in `display_config.active_metrics` (nicht mehr der festen CV2-Reihenfolge). Auswahl-Filter bleibt.
2. **Reihenfolge (Stundentabelle):** Die Spalten-Reihenfolge folgt der Config-Reihenfolge
   (`hourly_metrics`), sofern gesetzt; sonst bisheriges Default-Verhalten.
3. **Windrichtung in Stundentabelle:** wird als Spalte bzw. als Kompass-Pfeil in der Wind-Spalte
   möglich — konsistent zum Trip-Muster (`should_merge_wind_dir`). Erscheint, wenn im Preset gewählt.
4. **Kein Trip-Regress:** Trip-Renderer unverändert (byte-identisch, Charakterisierung).
5. **Amtliche-Warnungen-Zeile** bleibt wie bisher an fester Position (nicht Teil der wählbaren Reihenfolge).

## Affected Files (Erwartung)
| File | Change | Description |
|------|--------|-------------|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | `resolve_enabled_metrics` reihenfolge-erhaltend (Liste statt Set) bzw. zusätzliche geordnete Auflösung. |
| `src/output/renderers/compare_hourly_metric_ids.py` | MODIFY | Windrichtung ins Stunden-Vokabular; reihenfolge-erhaltende Auflösung. |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_visible_metrics`/`_visible_hour_metrics` nach Config-Reihenfolge; Windrichtungs-Spalte/Merge in Stundentabelle. |
| `tests/...` | CREATE | Kern-Tests: Reihenfolge folgt Config; Windrichtung erscheint in Stundentabelle; Trip-Charakterisierung. |

## Scope / Risk
- Files: ~3 Code + Tests. Risk **MEDIUM** (zentraler Mail-Renderer; Renderer-Mail-Gate #811 greift).
- LoC-Wachsamkeit: falls Reihenfolge + Windrichtung zusammen > 250 LoC → in der Spec auf S1a
  (Reihenfolge) / S1b (Windrichtung) schneiden. Bevorzugt zusammen, wenn im Limit.

## Offene Punkte für die Spec
- [ ] Windrichtung in Stundentabelle: eigene Spalte ODER Kompass-Pfeil-Merge in Wind-Spalte (wie Trip)?
      Empfehlung: **Merge wie Trip** (Parität, spart Spaltenbreite).
- [ ] Reihenfolge-Auflösung: `active_metrics`/`hourly_metrics` sind im JSON geordnete Listen — die
      Set-Konvertierung in `compare_metric_ids.py` muss reihenfolge-erhaltend werden, ohne den
      Sichtbarkeits-Filter zu brechen.

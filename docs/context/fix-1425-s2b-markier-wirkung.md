# Context: fix-1425-s2b-markier-wirkung

**Issue:** #1425 Schritt 2, Teil 2 — **Scheibe A** (Markier-Wirkung).
Gewitter-Skalen-Migration (Scheibe B) und Banner-Text (Scheibe C) sind **nicht** Teil dieses Workflows.

## Request Summary

Seit #1425 Teil 1 (`7c42db9f`) bietet der Trip-Reiter *Wertebereiche* 23 Wettergrößen an, jede
mit „Markieren"-Schalter. Im Trip-Briefing wirkt die Markierung aber nur für die **5 alten
Route-Keys** — für die 17 mit Teil 1 dazugekommenen Katalog-Größen bleibt der Haken folgenlos.
Das ist die Fehlerklasse, wegen der #1384 überhaupt neu geschnitten wurde (Bedienelement ohne
Wirkung, Invariante 1 aus #1372).

## Ursache (belegt)

`TRIP_CORRIDOR_METRIC_TO_COL_KEY` (`src/output/renderers/email/html.py:563-569`) kennt nur
`wind_gust`, `temperature_min`, `temperature_max`, `thunder_level`, `snow_line`. Die 17
Katalog-Zusätze tragen Compare-Keys (`cape_max_jkg`, `humidity_avg_pct`, …), die dort nicht
vorkommen; `mark_lookup_multi()` überspringt sie stillschweigend
(`src/output/renderers/email/corridor_mark.py:43` — `if not c.mark or c.metric not in id_map: continue`).

Nachweis aus dem Audit (Issue-Kommentar 2026-07-31, Session `ws-overview-0725`): Korridor
`{metric: "cape_max_jkg", range: [1000, null], mark: true}` + aktive CAPE-Spalte + Stundenwert
1500 J/kg → CAPE-Zelle wird gerendert, aber **kein** `corridor-mark` im HTML. Gegenprobe: derselbe
Korridor markiert in der Vergleichs-Mail korrekt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/html.py:555-569` | Übergangs-Zuordnung (der Prüfling), Kommentar nennt sie selbst als „fällt mit dem Pool-Umzug" |
| `src/output/renderers/email/html.py:895` | Einziger Produktiv-Aufruf `mark_lookup_multi(corridors, TRIP_CORRIDOR_METRIC_TO_COL_KEY)` |
| `src/output/renderers/email/html.py:730-746` | Zellen-Renderung: `is_marked_any` → `corridor-mark` + Inline-Border |
| `src/output/renderers/email/corridor_mark.py` | **Geteilter Baustein** Trip+Compare (#1425 S1). Änderungen hier treffen beide Ausgaben |
| `src/output/renderers/compare_metric_ids.py:78-98` | Vorbild `CORRIDOR_METRIC_TO_HOUR_KEY` + fachliche Begründung der Ausnahmen |
| `src/app/metric_catalog.py:25-70, 499-502, 558-563` | Zentrale `MetricDefinition` mit `col_key`, Indizes `_METRICS_BY_ID` / `_METRICS_BY_COL_KEY` |
| `src/output/renderers/compare_metric_catalog.py:64-145, 216-232` | Compare-Katalog: `key` → `metric_id` + `aggregation`; `key_for()` als Umkehr-Index |
| `frontend/.../corridor-editor/corridorEditorState.ts:31-38, 153` | Herkunft der 6 Route-Keys + `buildRoutePool()` |
| `frontend/.../compareMetricCatalogLoader.ts:130-154` | `buildRouteMetricDefsFromCatalog()` — Herkunft der 17 Katalog-Zusätze |

## Existing Patterns

- **Zweistufige Auflösung ist vorhanden, wird aber nirgends verkettet:**
  Compare-`key` → `metric_id` (Compare-Katalog) → `get_metric(metric_id).col_key` (zentrale
  Registry). Diese Kette existiert im Code an keiner Stelle — genau sie ersetzt die
  Übergangs-Zuordnung.
- **Der Vergleich begrenzt bewusst:** `CORRIDOR_METRIC_TO_HOUR_KEY` hat nur 4 Einträge. Tages-Größen
  werden dort **nicht** gegen Stundenwerte gematcht, sondern in der Übersichtszeile markiert.
- **Alle 23 Größen haben eine `col_key`** (über ihre `metric_id`), aber nur **21 verschiedene
  Spalten**: `temperature_min`/`temperature_max` → `temp`, `wind_chill_min_c`/`wind_chill_max_c` →
  `felt`. Für genau diesen Fall existiert bereits `mark_lookup_multi`/`is_marked_any` (#1425 S1) —
  der Kollisionsfall ist gelöst und muss nicht neu erfunden werden.

## Der Zuschnitts-entscheidende Befund

Der Trip-Briefing hat **keine Übersichts-Tabellenzeile**, in der Tages-Aggregate stehen und eine
Markierung andocken könnte:

- Die Stundentabelle enthält ausschließlich Stundenzeilen, keine Summen-/Fußzeile
  (`_render_html_table`, `html.py:645-754`).
- Tages-Aggregate stehen nur im **„Metriken-Überblick"** — aber als `<span>`-Pillen
  (`helpers.py:1092-1104, 1621-1685`), nicht als Tabellenzellen; die Funktion kennt weder
  `corridors` noch `marks`.
- Die **Ausblick-Tabelle** (`outlook.py:42-238`) hat echte Zellen, zeigt aber nur die 3 Folgetage
  mit festen Spalten (kein UV, keine Sicht) und hat keinen `marks`-Parameter.

**Konsequenz:** Der Weg des Vergleichs („Tages-Größen in der Übersichtszeile markieren") steht im
Trip nicht zur Verfügung. Es bleibt: Stundenzelle markieren — oder gar nicht.

### Fachliche Einteilung der 23 Größen

| Klasse | Größen | Stundenmarkierung fachlich? |
|---|---|---|
| **Extrema (min/max)** — Stundenwert und Tageszahl sind dieselbe physikalische Größe | temperature_min/max, wind_gust, wind_max_kmh, thunder_level, snow_line, cape_max_jkg, pop_max_pct, wind_chill_min/max, snow_depth_cm, uv_index_max, visibility_min_m, freezing_level_m | **ja** — „bis 28 °C" heißt für den Nutzer sinnvoll: markiere Stunden ≤ 28 °C |
| **Mittelwerte (avg)** — gleiche Einheit, gleiche Größenordnung | cloud_avg_pct, humidity_avg_pct, dewpoint_avg_c, cloud_low/mid/high_avg_pct, pressure_avg_hpa | **ja** (mit Bedeutungsverschiebung: der eingestellte Bereich wird je Stunde geprüft, nicht gegen den Tagesmittelwert) |
| **Summen (sum)** — Tageszahl ist eine andere Größenordnung als der Stundenwert | precipitation_sum, snow_new_sum_cm, sunny_hours_h | **nein** — 28 mm Tagessumme ≠ 3,5 mm Stundenwert (`compare_metric_ids.py:85-88`, `html.py:560-562`) |

Für die 3 Summen ist zu entscheiden: Markieren-Schalter im Editor ausblenden (ehrlich, kein
wirkungsloses Element) oder Markierung still weglassen (Status quo, verstößt gegen Invariante 1).
→ **PO-Frage in der Spec-Phase.**

## Dependencies

- **Upstream:** `trip.corridors` (`src/app/trip.py`, Go `internal/model/trip.go:71-78`) — ungeprüfte
  Freitext-Metrik-IDs, keine Enum-Validierung. Die Auflösung muss unbekannte IDs still überspringen.
- **Downstream:** Trip-Mail HTML (Desktop-Tabelle, Mobile-Kompaktzeilen, Nacht-Tabelle — alle drei
  bekommen `_marks`, `html.py:1089/1100/1141/1158/1177/1183`).
- **Geteilt:** `corridor_mark.py` wird von `compare_html.py` mitbenutzt — Vergleichs-Mail darf sich
  **nicht** ändern.

## Existing Specs

- `docs/specs/modules/fix_1425_trip_wertebereiche_wirkung.md` — Schritt 1 (Markier-Wirkung eingeführt)
- `docs/specs/modules/fix_1425_s2_corridor_pool.md` — Teil 1 (Pool auf 23 erweitert). Sagt „Neue
  Metriken zeigen automatisch dasselbe einzige Bedienelement wie die alten 6" — dass es für sie
  wirkungslos ist, steht dort **nicht**; diese Lücke schließt der vorliegende Workflow.
- `docs/specs/modules/epic_191_state_migration.md` — AC-N-Formatvorbild

## Risks & Considerations

1. **Regression Schritt 1:** Die 5 alten Route-Keys müssen weiter exakt wie heute markieren.
   `snow_line` ist der heikelste Fall — er mappt heute auf `snow_limit`, die zentrale Registry führt
   `snowfall_limit` **und** `freezing_level` als getrennte Metriken.
2. **Vergleichs-Mail muss byte-identisch bleiben** (geteilter Baustein). Nachweis wie in Schritt 1:
   sha256 über HTML und Klartext.
3. **Renderer-Commit-Gate #811** greift (`html.py` ist eine Mail-Inhalts-Datei): Mode-Matrix-Test +
   `briefing_mail_validator.py` müssen frisch grün sein, sonst blockt der Commit.
4. **Datenerhalt:** Korridore mit unbekannter Metrik-ID dürfen weder crashen noch verloren gehen —
   sie werden bei der Auflösung still übersprungen (Verhalten von `mark_lookup_multi` bleibt).
5. **Klartext-Teil, Telegram, SMS** kennen keine Auszeichnung — bewusst außerhalb (wie Schritt 1).
6. **Nebenbefund (nicht Teil dieser Scheibe):** Der Trip-`<style>`-Block hat keine
   `.corridor-mark`-Regel (Compare schon, `compare_html.py:1351`) — sichtbar wird die Marke nur über
   den Inline-Border. Das ist so gewollt (E-Mail-Tauglichkeit), aber die Klasse ist im Trip
   funktionslos.

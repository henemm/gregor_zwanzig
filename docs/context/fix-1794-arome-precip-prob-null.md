# Context: fix-1794-arome-precip-prob-null

## Request Summary

Issue #1794 behauptet: Météo-France/AROME liefert `precipitation_probability` für
Frankreich/Korsika/GR20 strukturell `null`, und weil die Metrik `rain_probability`
(`default_enabled=False`) beim Aktivieren lautlos leer bliebe, ohne erkennbaren Hinweis
auf eine bekannte Lücke. Anders als bei echtem Ausfall (`fallback_model`/`fallback_notice.py`)
gäbe es keinen sichtbaren Marker.

**🔴 Kernkorrektur nach Live-Nachmessung (18.09.2026) — die Ausgangsannahme des Tickets
trifft im Regelfall NICHT mehr zu:**

## Befund 1: Die API liefert weiterhin null — aber unser Code kompensiert bereits

Live-Test heute gegen `https://api.open-meteo.com/v1/meteofrance` (Standard-Endpunkt,
`meteofrance_arome`-Eintrag in `REGIONAL_MODELS`): `precipitation_probability` **0 von 48
Werten belegt** (Korsika-Koordinate 42.2/9.0) — Vergleich ICON-D2 und ECMWF an anderer
Koordinate: 48/48 belegt. Der API-seitige Rohbefund aus 08/2026 ist also weiterhin korrekt.

**Titel-Korrektur:** "AROME liefert null" ist ungenau. Der Code ruft für die FR-Box
`/v1/meteofrance` ohne expliziten `models=`-Parameter ab, d.h. faktisch
`meteofrance_seamless` (Mischmodell AROME+ARPEGE), nicht reines AROME
(siehe [[reference_arome_ist_bei_uns_nur_ein_name_kein_modell]], PO-Memory). Betroffen ist
der Endpunkt, nicht ein bestimmtes benanntes Modell.

## Befund 2: WEATHER-05b (Model-Metric-Fallback) füllt die Lücke im Normalfall bereits automatisch

`src/providers/openmeteo.py` enthält bereits zwei implementierte (Spec-Status zwar
"draft", Code aber produktiv scharf) Mechanismen:

- **WEATHER-05a** `probe_model_availability()` (Z.337-392): probt pro `REGIONAL_MODELS`-Eintrag
  an einer Referenzkoordinate, welche Open-Meteo-Parameter `null` bleiben, Cache
  `data/cache/model_availability.json`, TTL 7 Tage, Auto-Probe bei Cache-Miss (Z.1181-1187).
- **WEATHER-05b** `_find_fallback_model()`/`_merge_fallback()` (Z.394-469, Aufruf Z.1180-1220):
  für jede in der Probe als `unavailable` markierte Metrik wird — sortiert nach Priorität,
  gefiltert auf Koordinaten-Abdeckung — das nächstbeste Modell gesucht, das die Metrik
  laut Cache liefert, per Zusatzabruf geholt und die fehlenden Felder **in die primäre
  Zeitreihe gemerged** (`timeseries.meta.fallback_metrics`/`fallback_model`/`fallback_reason`).

**Live-Gegenprobe (produktiver Code, `OpenMeteoProvider.fetch_forecast()`, Koordinate
Refuge de Petra Piana 42.22/9.07, GR20):**

```
Primaeres Modell: meteofrance_arome (bounds deckt Korsika ab)
fallback_model: icon_eu
fallback_reason: metric_gap
fallback_metrics: ['freezing_level_height', 'precipitation_probability', 'visibility',
                    'cape_ml_jkg', 'convective_inhibition_jkg', 'lightning_potential_lpi_jkg']
pop_pct: 48 von 48 Stunden belegt (kein einziger None-Wert)
```

**Damit ist der im Ticket beschriebene Kern-Fall — Nutzer aktiviert `rain_probability`
für eine GR20-Tour, bekommt lautlos leere Werte — im Normalbetrieb heute NICHT
reproduzierbar.** Icon-EU deckt Korsika ab (Bounds `29–71N / -24–45E`) und liefert laut
Probe echte `precipitation_probability`-Werte; der Fallback greift unabhängig davon, ob
die Metrik selektiert/aktiv ist (der Merge läuft für JEDE geprobte fehlende Metrik, nicht
nur für aktivierte).

## Befund 3: Die tatsächlich verbleibende Lücke ist eine allgemeine None-Handling-Schwäche, nicht FR-spezifisch

Wenn `pop_pct` aus irgendeinem Grund TROTZDEM `None` bleibt (Cache/Auto-Probe schlägt fehl,
Fallback-Kandidat erschöpft, Netzfehler beim Zusatzabruf, oder die von der Probe getestete
Referenzkoordinate weicht regional ab — dokumentiertes "Known Limitation" in
`docs/specs/modules/metric_availability_probe.md:215-216`), zeigen mehrere Renderer den
Wert NICHT erkennbar als "fehlt", sondern wie eine echte `0`:

| Kanal | Fundstelle | Verhalten bei `pop_pct=None` heute |
|---|---|---|
| E-Mail Haupttabelle | `src/output/renderers/email/helpers.py:893-894` (`fmt_val`) → `metric_format.py:113-114` | ✅ bereits sauber: `"–"` |
| E-Mail Ampel-Punkt | `helpers.py:710-727` (`_ampel_dot_severity`) | ✅ bereits sauber: `"–"` |
| E-Mail Risiko-Zeile (`worst`) | `html.py:234` `pop_sev = severity_for("rain_probability", _safe_float(r.get("pop")))` — `_safe_float` Default `0.0` (Z.162-168) | ❌ `None` → `0.0` → Severity `"green"` statt `None`; fließt in `worst` (Z.241) ein — "geprüft, unauffällig" statt "unbekannt" |
| E-Mail Mobile-Stundenliste | `html.py:343` `rain_pct = r.get("rain_probability") or r.get("pop_pct") or 0`, gerendert Z.447 `({int(rain_pct_val)}%)` | ❌ zeigt sichtbar **„(0%)"** statt eines Fehlend-Markers |
| SMS/Telegram/Premium-SMS (`PR`-Token) | `src/output/tokens/builder.py:389` → `metrics.py:47-48` `render_threshold_peak_value` → `"-"` bei leeren `samples` | ⚠️ rendert `"-"`, identisch falsch wie E-Mail-`(0%)`: "geprüft, kein Regen" statt "unbekannt". Gap-Erkennung (`_gap_or`, `builder.py:156-166`) hängt an segmentweitem `has_data_gap`, nicht pro Metrik — ein isolierter `pop_pct=None` bei sonst vollständigem Fetch triggert die `"?"`-Markierung nicht. |

**Wichtig — Scope-Abgrenzung:** `_safe_float(..., default=0.0)` in `_row_risk` (html.py:234)
und das `or 0`-Muster in `_render_mobile_hour_list` (html.py:343 ff.) betreffen NICHT nur
`pop`/`rain_probability`, sondern identisch auch `gust`, `wind`, `precip`, `thunder`,
`visibility`, `uv`, `freezing_level`. Eine Generalüberholung dieses Musters ist NICHT
Gegenstand von #1794 (Blast Radius zu groß, andere Metriken werden in der Praxis kaum
`None`) — der Fix hier bleibt auf `pop`/`rain_probability` beschränkt; das breitere Muster
gehört als Nebenbefund in #1199.

## Related Files

| File | Relevance |
|------|-----------|
| `src/providers/openmeteo.py:126-167` | `REGIONAL_MODELS` — Endpunkt-/Bounds-Konfiguration, `meteofrance_arome` |
| `src/providers/openmeteo.py:337-469` | WEATHER-05a/05b Probe + Fallback-Merge (bereits implementiert, Spec-Status "draft") |
| `src/providers/openmeteo.py:1180-1220` | Aufrufstelle des Fallback-Merges in `fetch_forecast()` |
| `src/app/metric_catalog.py:408-421` | `rain_probability`-Definition, `default_enabled=False`, `providers={"openmeteo": True}` — keine regionale Differenzierung |
| `src/app/model_registry.py:180-211` | Vorbild-Pattern `lpi_thresholds_jkg()`: `None` = "für dieses Gebiet strukturell nicht kalibriert", FR bewusst ohne Eintrag |
| `src/output/renderers/email/html.py:162-168,228-245,338-348,443-450` | `_safe_float`-Default-Falle + `or 0`-Muster (Fundstellen s.o.) |
| `src/output/renderers/email/helpers.py:710-727,893-894` | Bereits None-sichere Pfade (Referenzimplementierung für den Fix) |
| `src/output/tokens/builder.py:156-166,389` | `_gap_or`/`has_data_gap` (segmentweit, nicht pro Metrik), `PR`-Token-Aufbau |
| `src/output/tokens/metrics.py:47-48` | `render_threshold_peak_value` — `"-"` bei leeren `samples` |
| `src/output/renderers/fallback_notice.py` | Etabliertes Textbaustein-Modul für sichtbare Fallback-Hinweise (EIN Modul, drei Verpackungen: HTML/Plaintext/Telegram); `precipitation_probability` fehlt in `_METRIK_KLARTEXT`, nur generisches `precipitation` gelistet |
| `docs/specs/modules/metric_availability_probe.md` | Spec zu WEATHER-05a (status: draft, aber implementiert) |
| `docs/specs/modules/model_metric_fallback.md` | Spec zu WEATHER-05b (status: draft, aber implementiert) |
| `docs/reference/decision_matrix.md:303-312` | Bestehendes Doku-Muster "bekannte Lücke" (Météo-France-Kontingent) — Vorlage für Doku-Ergänzung |

## Existing Patterns

- **Regionaler Verfügbarkeits-Gap als `None`-Lookup:** `model_registry.py:180-211`
  (`lpi_thresholds_jkg`) — direktes Vorbild für einen analogen
  `known_metric_gap(model_id, metric_id)`-artigen Mechanismus, falls die Spec das braucht.
- **Fallback-Text-Baustein:** `fallback_notice.py` — "EIN Modul, drei Verpackungen"
  für alle Kanäle, aber an *Modell-Fallback* gekoppelt, nicht an *Metrik bei diesem Modell
  strukturell nie vorhanden*.
- **None-sichere Formatierung existiert bereits** in `helpers.py`/`metric_format.py` —
  zeigt, dass der Zielzustand ("–" statt "0"/"-") an anderer Stelle im selben Renderer
  schon Standard ist. Der Fix bringt `html.py`/`builder.py` auf dieses bestehende Niveau,
  keine neue Konvention.

## Dependencies

- **Upstream:** Open-Meteo `/v1/meteofrance`-Endpunkt (kein Einfluss unsererseits),
  WEATHER-05a/05b-Fallback-Kette (bereits produktiv, Spec-Approval fehlt formal)
- **Downstream:** alle vier Kanäle (E-Mail Haupttabelle + Mobile-Ansicht, SMS, Telegram,
  Premium-SMS/Garmin) — Epic #2133 verlangt konsistente Beantwortung über alle Kanäle

## Existing Specs

- `docs/specs/modules/metric_availability_probe.md` — WEATHER-05a, status draft
- `docs/specs/modules/model_metric_fallback.md` — WEATHER-05b, status draft
- Keine bestehende Spec deckt das None-Rendering in `html.py`/`builder.py` ab

## Risks & Considerations

- **Scope-Disziplin:** `_safe_float`/`or 0` ist ein breiteres Muster — Fix strikt auf
  `pop`/`rain_probability` begrenzen, Rest als Nebenbefund #1199 vormerken.
- **Kein Test deckt `pop_pct=None` für FR/Korsika ab** — TDD-RED muss das neu bauen,
  keine bestehende Fixture zum Anpassen gefunden.
- **Spec-Status-Drift:** WEATHER-05a/05b sind im Code scharf, aber als Spec nie formal
  freigegeben (`- [ ] Approved`). Nicht Gegenstand dieses Fixes, aber als Drift-Hinweis
  vermerkt (potenzieller Kandidat für `docs-updater`, nicht jetzt).
- **`fallback_metrics`/`fallback_reason=metric_gap` bereits vorhanden:** ein sichtbarer
  Hinweis könnte diese Metadaten direkt nutzen statt einen neuen Mechanismus zu bauen —
  zu klären in der Spec, ob "stiller Fallback-Erfolg" (Normalfall, kein Hinweis nötig) von
  "echter Restlücke nach Fallback" (Hinweis nötig) sauber unterscheidbar ist. Der
  Ansatzpunkt dafür ist vermutlich `dp.pop_pct is None` selbst (unabhängig vom Fallback-
  Verlauf) als alleiniges Kriterium für "zeige Fehlend-Marker" — nicht der Fallback-Status.
- **Priority:low, `default_enabled=False`:** Nutzersichtbarkeit bleibt bedingt (nur bei
  manueller Aktivierung UND einem der oben beschriebenen Restlücken-Fälle). Rechtfertigt
  weiterhin Standard Track, nicht Full Process — die eigentliche Änderung ist lokal
  (5-6 Dateien), aber testpflichtig über alle vier Kanäle.

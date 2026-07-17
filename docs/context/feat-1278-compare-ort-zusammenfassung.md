# Context: feat-1278-compare-ort-zusammenfassung

Issue: #1278 — Vergleichs-Mail: Kurz-Zusammenfassung je Ort im Trip-Stil
(geteilter Baustein, kein UI-Element). Abhängigkeit #1268 ist erfüllt
(geschlossen, auf `origin/main`, Commit d32bd0a5).

## Request Summary

Die Vergleichs-Mail soll je Ort einen kurzen, lesbaren Zusammenfassungssatz
bekommen — exakt im Stil der Trip-Zusammenfassung, platziert unterhalb der
Vergleichs-Matrix. Kein Frontend-UI, nichts einstellbar. Der Trip-Baustein
wird geteilt, nicht nachgebaut (Trip/Compare-Teilungs-Invariante, CLAUDE.md;
Anti-Pattern-Referenz #1170).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/compact_summary.py` | Der zu teilende Baustein: `CompactSummaryFormatter.format_stage_summary()` (:40). Erzeugt den Fließtext aus Aggregat + Stundendaten. Spec: `docs/specs/modules/compact_summary.md` v1.1 |
| `src/output/renderers/trip_report.py:699` | Einziger heutiger Aufrufer (`_generate_compact_summary()`, aufgerufen aus `format_email()` :126) |
| `src/output/renderers/email/html.py:1338-1393` | Platzierung im Trip-HTML (TAGESLAGE-Block), eingebettet in Body :1572 |
| `src/output/renderers/email/plain.py:125` | Platzierung im Trip-Plaintext |
| `src/output/renderers/email/compare_html.py:784` | Ziel-Renderer `render_compare_html()`; Body-Komposition :864-870 |
| `src/output/renderers/comparison.py:148` | `render_compare_email()` — Plaintext-Pendant des Vergleichs |
| `src/app/user.py:117` | `LocationResult` — Datenquelle je Ort |
| `src/app/models.py:339 / :397` | `SegmentWeatherSummary` / `SegmentWeatherData` — heutige Eingangstypen des Bausteins |

## Existing Patterns

- **Baustein-Aufbau** (`format_stage_summary`): reduziert intern auf zwei
  Größen — ein Aggregat (`_aggregate()` → `SegmentWeatherSummary`) und eine
  Stundenliste (`_collect_hourly_data()` → `list[ForecastDataPoint]`).
  Alle `_format_*`-Methoden arbeiten **nur** auf diesen beiden. Der Rest
  (Etappen-Segmente, Zeitfenster-Filter, Etappenname-Kürzung) ist
  Trip-spezifische Vorbereitung.
  → Die natürliche Schnittstelle für die Teilung liegt genau dort:
  kontextneutraler Kern `(summary, hourly, titel, dc, tz)`, zwei dünne
  Wrapper (`route` = Etappe, `vergleich` = Ort).
- **Kein `context="route"|"vergleich"` im Python-Renderer-Code vorhanden** —
  das Muster existiert bisher nur im Frontend (`LayoutTab`/`VersandTab`).
  Diese Arbeit legt das Python-Pendant an.
- **Compare-Mail v2-Vertrag:** pure function, kein Score/kein Ranking
  (PO 2026-07-08), Orte alphabetisch sortiert (`sort_locations_alphabetically`).
- **Anti-Erosion beim Body-Bau** (`compare_html.py:864`): nur nicht-leere
  Blöcke werden eingereiht — ein Ort ohne Daten darf keinen leeren Block
  erzeugen.

## Dependencies

**Upstream (was der Baustein braucht):**
- Aggregat je Ort: `LocationResult` hat `temp_min/temp_max/wind_max/gust_max/
  wind_direction_avg/cloud_avg/sunny_hours` — **andere Feldnamen** als
  `SegmentWeatherSummary` (`temp_min_c`, `cloud_avg_pct`, …) und **ohne**
  `precip_sum_mm`, `thunder_level_max`, `pop_max_pct`.
- Stundendaten je Ort: `LocationResult.hourly_data: list[ForecastDataPoint]`
  — **identischer Typ** wie im Trip-Pfad. Regen-/Böen-/Gewitter-Fenster sind
  daraus ableitbar; die fehlenden Aggregatfelder ebenso.
- Metrik-Konfiguration: Trip liefert `UnifiedWeatherDisplayConfig`
  (`dc.metrics[].metric_id` = "temperature"/"wind"/…, plus
  `use_friendly_format`). Compare liefert `enabled_metrics: set` mit
  **Renderer-IDs** ("wind_max"/"cloud_avg"). Zwei verschiedene Vokabulare —
  die Übersetzung ist die zentrale Design-Entscheidung dieser Arbeit.

**Downstream (was betroffen ist):**
- Trip-Briefing-Mail (HTML + Plaintext) — darf sich **nicht** ändern.
- Vergleichs-Mail (HTML + Plaintext) — bekommt den neuen Block.
- Renderer-Commit-Gate #811: `compare_html.py`/`compact_summary.py` sind
  gate-pflichtig → `test_issue_811_mode_matrix.py` grün +
  `briefing_mail_validator.py`-Lauf vor Commit.
- `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`) gegen echt
  zugestellte Staging-Mail.

## Existing Specs

- `docs/specs/modules/compact_summary.md` v1.1 — Vertrag des Bausteins
- `docs/specs/modules/compare_channel_preview_dispatch.md` — Compare-Versandpfad
- `docs/reference/api_contract.md` — DTOs

## Risks & Considerations

1. **Vokabular-Bruch Metriken:** `enabled_metrics` (Renderer-IDs) vs.
   `UnifiedWeatherDisplayConfig` (Metrik-IDs + friendly-Flag). Ohne saubere
   Übersetzung entsteht entweder eine Compare-eigene Textlogik (= Verstoß
   gegen die Teilungs-Invariante) oder ein stilfremder Satz.
2. **Aggregat-Lücke:** `LocationResult` kennt weder Niederschlagssumme noch
   Gewitterstufe als Aggregat. Beide müssen aus `hourly_data` abgeleitet
   werden — die Ableitung muss zur Trip-Aggregation passen, sonst weichen
   Vergleichs- und Trip-Aussage bei gleicher Wetterlage voneinander ab.
3. **Trip-Regression:** Jede Änderung an `format_stage_summary` trifft die
   Trip-Mail. Der bestehende Trip-Text muss zeichengleich bleiben.
4. **Titel-Konvention:** Der Baustein setzt `"<Etappenkurzname>: <Wetter>"`
   voran (`_shorten_stage_name`, :357). Beim Vergleich ist der Titel der
   Ortsname — die Etappen-Kürzungsregel ("von X nach Y" → "X → Y") darf dort
   nicht greifen.
5. **Fehler-/Leerfall:** `LocationResult.error` bzw. leere `hourly_data` →
   kein leerer Block (Anti-Erosion, s.o.).
6. **Plaintext-Pfad:** Der Vergleich hat neben HTML einen Plaintext-Renderer
   (`comparison.py:148`). Ob die Zusammenfassung dort ebenfalls erscheint,
   ist offen und gehört in die Spec.

## Nebenbefund (nicht Teil dieser Arbeit)

`compare_html.py:851` verdrahtet im Kopf der Stunden-Sektion fest
`"09–16 Uhr"` — ein toter Rest des mit #1268 abgeschafften Zeitfensters.
Nutzersichtbar falsch (die Bewertung läuft seit #1268 über den ganzen Tag,
`time_window=(0, 23)`). Triage-Kategorie (a) → eigenes Issue.

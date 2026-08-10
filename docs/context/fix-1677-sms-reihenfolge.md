# Context: fix-1677-sms-reihenfolge (#1677)

## Request Summary

PO-Auftrag (2026-08-10): Die im Editor per Drag & Drop gezogene Metrik-Reihenfolge
muss auch in der Trip-Kurzform (SMS/Telegram-Kurzform) wirken — „Der User ist
Experte, er wird nicht bevormundet." Dazu Vollständigkeits-Tests Kanal × Metrik
(Scheibe B), damit die Fehlerklasse „Bedienelement ohne Wirkung" strukturell
bewacht ist (#1450, #1362, #1660 A+B, #1677).

## Gemessener Ist-Zustand (3 Explore-Reports, 2026-08-10)

### Frontend (exp-frontend)
- Trip-Editor: **Reihenfolge JE KANAL** — `channelBuckets[email|telegram|sms]`
  (WeatherMetricsTab, Fallback auf globale `buckets`), gespeichert via
  `PUT /api/trips/{id}/weather-config` als `channel_layouts: {email:[…], telegram:[…], sms:[…]}`.
  **Es gibt einen eigenen SMS-Tab mit Drag & Drop — dessen Sortierung ist heute wirkungslos.**
- Compare-Editor: EINE globale Reihenfolge (`wiz.activeMetricKeys`), keine Kanal-Tabs.
- UI-Beschriftung nennt den Kanal nur über den aktiven Tab („Reihenfolge = von links nach rechts").

### Kanal-Verhalten (exp-channels)
- **Respektieren die Reihenfolge bereits:** E-Mail (`trip_report.py:135-138` → `dc.metrics`
  sortiert → `html.py:1021 _col_order`), Telegram rich (`narrow.py:644 render_for_channel`),
  Ortsvergleich Mail+Kurzform (`comparison.py:668/936-937/1017`, ordnungserhaltendes Dedup).
- **Lücke NUR Trip-Kurzform:** `trip_report.py:290-293` kollabiert die sortierte Liste aus
  `get_metrics_for_channel("sms", …)` in ein **Set** (`sms_metric_ids = {…}`); danach sortiert
  `builder.py::build_token_line` final nach fester `POSITIONAL`-Tabelle (Z. ~465-468).
- Sortier-Semantik überall: `models.py:647 _sorted_by_layout` — Bucket (primary vor secondary),
  darin `order`; auf JEDER Kaskaden-Ebene (#1575). SMS hat `max_table_cols=0`
  (`channel_layout.py:90-95`) — für die flache Zeile zählt effektiv die Gesamt-Listenreihenfolge.

### Pipeline-Bruchstellen bei Umstellung (exp-pipeline)
- **Bricht:** `builder.py` finale `tokens.sort(POS_INDEX)` (der zentrale Schalter);
  `render.py::_fuse()` Z.22-44 fusioniert `HR:`+`TH:` (Vigilance) nur bei ADJAZENZ —
  Format-Pflicht laut `sms_format.md` §3.3.
- **Bricht (Tests, ~7 Dateien):** `tests/golden/test_sms_golden.py` (5 Goldens +
  `_assert_positional_order_v2`), `tests/unit/test_token_builder.py`
  (`test_token_order_positional_per_sms_format_v2`), Goldstrings in
  `test_sms_official_alert_tokens.py`, `test_sms_unknown_on_missing_data.py` —
  **nur wenn sich die DEFAULT-Reihenfolge ändert; bleibt der Default POSITIONAL, bleiben sie grün.**
- **Unabhängig:** Kürzung (`_truncate`/`DROP_ORDER` nach Symbol, `_strip_peaks` nach Kategorie),
  Alert-SMS (`alert/render.py`, eigene Baustrecke), Compare-Text (`_ordered_rows`, keine
  Token-Pipeline), `filter_for_subject` (Stub).
- Doku: `sms_format.md` §2 dokumentiert POSITIONAL als fix → muss versioniert erweitert werden;
  §3.3 HR:/TH:-Adjazenz bleibt Pflicht.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/trip_report.py:289-293` | Set-Kollaps — hier geht die Reihenfolge verloren |
| `src/output/renderers/sms_trip.py` | `format_sms(…)`-Signatur; Spec-Zusammenbau (Threshold/Disabled/Nullform-Specs) |
| `src/output/tokens/builder.py` | finale Sortierung `POS_INDEX`; `MetricSpec`-Verbrauch; Schichtgrenze (kein app-Import) |
| `src/output/tokens/dto.py` | `MetricSpec` (Kandidat für additives `position`-Feld) |
| `src/output/tokens/render.py` | `_fuse()` (Vigilance-Adjazenz), Kürzung (unabhängig) |
| `src/app/models.py:647,735-775` | `_sorted_by_layout`, Kanal-Kaskade — Quelle der Ordnung |
| `docs/reference/sms_format.md` | §2 POSITIONAL (SSoT, Versionierung), §3.3 Adjazenz-Pflicht |
| `tests/golden/test_sms_golden.py` + `tests/golden/sms/*.txt` | Byte-Identitäts-Wachen des Defaults |

## Risks & Considerations

1. **Drahtformat-Kontrakt:** POSITIONAL ist dokumentierte Format-Zusicherung — Änderung nur als
   versionierte Erweiterung mit klarem Default (ohne Nutzer-Sortierung: exakt heutige Reihenfolge,
   byte-identisch — sonst brechen 5 Goldens + Bestandsnutzer-Erwartung).
2. **System-Blöcke nicht sortierbar:** Vigilance (HR:/TH:-Fusion!), amtlicher Warn-Block (`!`-Marker,
   sicherheitsrelevant ganz hinten/fix), Fire, `W?`, DBG — Nutzer-Reihenfolge gilt nur für
   Vorhersage-/Wintersport-Token wählbarer Metriken.
3. **Mehrfach-Symbole:** temperature→(K,D), wind_chill→(FK,FD,WC), thunder→(TH:,TH+:) — EIN
   Metrik-Anker, interne Reihenfolge fest; Position folgt der Metrik.
4. **Schichtgrenze:** `output/tokens/` darf `models.py` nicht lesen — Position muss über
   `MetricSpec` (additives Feld) oder geordnete Config transportiert werden.
5. **Kürzungs-Priorität bleibt sicherheitsbasiert** (Anzeige-Reihenfolge ≠ Überlebensrang) —
   sonst kürzt sich der Experte versehentlich die Gewitterwarnung weg.
6. **Compare-Kurzform** respektiert Reihenfolge bereits — nicht anfassen (Regressionsgefahr).
7. **LoC:** Scheibe A moderat; Scheibe B (Matrix-Tests) treibt das Gate-Delta — Override früh ansprechen.
